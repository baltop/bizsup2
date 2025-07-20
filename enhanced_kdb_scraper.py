#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced KDB 스크래퍼 - 한국산업은행 공지사항 수집
URL: https://www.kdb.co.kr/index.jsp (홍보센터 → 공지사항)

한국산업은행 공지사항 게시판에서 공고와 첨부파일을 모두 수집하는 완전한 스크래퍼입니다.
"""

import os
import re
import time
import logging
from typing import List, Dict, Any
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup
import requests
from enhanced_base_scraper import EnhancedBaseScraper

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('enhanced_kdb_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class EnhancedKDBScraper(EnhancedBaseScraper):
    """KDB 공지사항 완전한 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.kdb.co.kr"
        self.list_url = "https://www.kdb.co.kr/CHBIPR23N00.act"
        
        # KDB 특화 설정
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'X-Requested-With': 'XMLHttpRequest'
        })
        
        # 사이트 특화 설정
        self.verify_ssl = True
        self.timeout = 30
        self.delay_between_requests = 1
        self.delay_between_pages = 2
        
        # KDB 공지사항 페이지 정보
        self.announcements_base_url = "https://www.kdb.co.kr/CHBIPR23N00.act"
        self.data_endpoint = "https://www.kdb.co.kr/BOUBUF01R01.jct"
        
    def get_list_url(self, page_num: int) -> str:
        """페이지별 URL 생성"""
        return f"{self.announcements_base_url}?currentPage={page_num}"
    
    def get_announcements_page(self, page_num: int = 1, category: str = "ZZ") -> str:
        """공지사항 페이지 HTML 가져오기"""
        try:
            # 먼저 기본 페이지 로드하여 세션 설정
            response = self.session.get(self.announcements_base_url, timeout=self.timeout, verify=self.verify_ssl)
            response.raise_for_status()
            
            # AJAX 데이터 요청
            return self.get_announcements_data(page_num, category)
            
        except Exception as e:
            logger.error(f"페이지 {page_num} 로드 실패: {e}")
            return ""
    
    def get_announcements_data(self, page_num: int = 1, category: str = "ZZ") -> str:
        """AJAX를 통해 공지사항 데이터 가져오기"""
        try:
            # KDB의 AJAX 데이터 요청 파라미터
            data = {
                'currentPage': str(page_num),
                'pageSize': '10',
                'searchCate': category,  # ZZ: 전체, 05: 입찰공고, 08: 채용공고
                'searchKey': '',
                'searchValue': '',
                'orderBy': 'DESC'
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'text/html,*/*'
            }
            
            response = self.session.post(
                self.data_endpoint,
                data=data,
                headers=headers,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            
            response.raise_for_status()
            
            # 인코딩 처리
            if response.encoding is None:
                response.encoding = 'utf-8'
            
            logger.info(f"데이터 페이지 {page_num} 로드 완료 - 상태코드: {response.status_code}")
            return response.text
            
        except Exception as e:
            logger.error(f"데이터 페이지 {page_num} 로드 실패: {e}")
            return ""
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        try:
            # KDB 공지사항 테이블 찾기
            table = soup.find('table', {'class': 'bbs_table'}) or soup.find('table', {'summary': '공지사항'})
            
            if not table:
                # 다른 패턴으로 테이블 찾기
                tables = soup.find_all('table')
                for t in tables:
                    if '공지사항' in str(t) or '제목' in str(t):
                        table = t
                        break
            
            if not table:
                logger.warning("공지사항 테이블을 찾을 수 없습니다")
                return announcements
            
            # 테이블의 tbody 또는 직접 tr 찾기
            tbody = table.find('tbody')
            if tbody:
                rows = tbody.find_all('tr')
            else:
                rows = table.find_all('tr')[1:]  # 헤더 제외
            
            logger.info(f"테이블에서 {len(rows)}개 행 발견")
            
            for i, row in enumerate(rows):
                try:
                    cells = row.find_all(['td', 'th'])
                    
                    if len(cells) < 4:  # 최소 필요 컬럼 수
                        continue
                    
                    # 일반적인 KDB 공지사항 테이블 구조: 번호, 카테고리, 제목, 첨부파일, 작성일
                    
                    # 번호 (첫 번째 컬럼)
                    number = cells[0].get_text(strip=True) if cells[0] else ""
                    
                    # 카테고리 (두 번째 컬럼)
                    category = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    
                    # 제목 (세 번째 컬럼)
                    title_cell = cells[2] if len(cells) > 2 else None
                    if not title_cell:
                        continue
                    
                    # 제목 링크 찾기
                    title_link = title_cell.find('a')
                    if title_link:
                        title = title_link.get_text(strip=True)
                        
                        # 링크 URL 추출
                        href = title_link.get('href', '')
                        
                        # JavaScript 링크 처리
                        if href.startswith('javascript:'):
                            # JavaScript에서 URL 파라미터 추출
                            detail_url = self._extract_detail_url_from_js(href)
                        else:
                            detail_url = urljoin(self.base_url, href)
                    else:
                        title = title_cell.get_text(strip=True)
                        detail_url = ""
                    
                    if not title:
                        continue
                    
                    # 첨부파일 (네 번째 컬럼)
                    attachment_cell = cells[3] if len(cells) > 3 else None
                    has_attachments = False
                    if attachment_cell:
                        attachment_text = attachment_cell.get_text(strip=True)
                        has_attachments = bool(attachment_text and attachment_text != '-')
                    
                    # 작성일 (다섯 번째 컬럼)
                    date = cells[4].get_text(strip=True) if len(cells) > 4 else ""
                    
                    # 조회수 (여섯 번째 컬럼, 있는 경우)
                    views = cells[5].get_text(strip=True) if len(cells) > 5 else ""
                    
                    announcement = {
                        'number': number,
                        'category': category,
                        'title': title,
                        'url': detail_url,
                        'date': date,
                        'views': views,
                        'has_attachments': has_attachments
                    }
                    
                    announcements.append(announcement)
                    logger.debug(f"공고 추가: {title}")
                    
                except Exception as e:
                    logger.error(f"공고 항목 파싱 중 오류 (행 {i}): {e}")
                    continue
            
            logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
            return announcements
            
        except Exception as e:
            logger.error(f"목록 페이지 파싱 중 오류: {e}")
            return announcements
    
    def _extract_detail_url_from_js(self, js_code: str) -> str:
        """JavaScript 코드에서 상세 페이지 URL 추출"""
        try:
            # 일반적인 JavaScript 패턴들 확인
            patterns = [
                r"location\.href\s*=\s*['\"]([^'\"]+)['\"]",
                r"window\.open\(['\"]([^'\"]+)['\"]",
                r"goView\(['\"]([^'\"]+)['\"]",
                r"detail\(['\"]([^'\"]+)['\"]",
                r"view\(['\"]([^'\"]+)['\"]"
            ]
            
            for pattern in patterns:
                match = re.search(pattern, js_code)
                if match:
                    url = match.group(1)
                    return urljoin(self.base_url, url)
            
            logger.warning(f"JavaScript URL 추출 실패: {js_code}")
            return ""
            
        except Exception as e:
            logger.error(f"JavaScript URL 추출 중 오류: {e}")
            return ""
    
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출
        title = "제목 없음"
        try:
            # 다양한 제목 선택자 시도
            title_selectors = [
                'h1', 'h2', 'h3',
                '.board_view_title', '.view_title', '.title',
                '.sub_title', '.cont_title',
                'div.title', 'span.title'
            ]
            
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    potential_title = title_elem.get_text(strip=True)
                    if potential_title and len(potential_title) > 5:
                        title = potential_title
                        break
        except Exception as e:
            logger.warning(f"제목 추출 실패: {e}")
        
        # 본문 내용 추출
        try:
            content_text = self._extract_main_content(soup)
        except Exception as e:
            logger.error(f"본문 추출 실패: {e}")
            content_text = "본문 내용을 추출할 수 없습니다."
        
        # 첨부파일 추출
        try:
            attachments = self._extract_attachments(soup)
        except Exception as e:
            logger.error(f"첨부파일 추출 실패: {e}")
            attachments = []
        
        # 마크다운 형식으로 조합
        markdown_content = f"# {title}\n\n"
        markdown_content += "---\n\n"
        markdown_content += content_text
        
        return {
            'content': markdown_content,
            'attachments': attachments
        }
    
    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """상세 페이지에서 본문 내용 추출"""
        
        # 불필요한 요소들 제거
        unwanted_selectors = [
            'nav', 'header', 'footer', '.nav', '.navigation',
            '.menu', '.sidebar', '.breadcrumb', '.paging',
            'script', 'style', '.ads', '.advertisement',
            '.social_share', '.btn_area', '.button_area'
        ]
        
        for selector in unwanted_selectors:
            for elem in soup.select(selector):
                elem.decompose()
        
        # KDB 특화 콘텐츠 선택자
        content_selectors = [
            '.board_view_content',
            '.view_content',
            '.content_area',
            '.board_content',
            '.detail_content',
            '.article_content',
            '.cont_area',
            '.contents',
            'main',
            '[role="main"]'
        ]
        
        content_elem = None
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                logger.debug(f"콘텐츠 선택자 사용: {selector}")
                break
        
        if content_elem:
            # 추가 불필요한 요소 제거
            for unwanted in content_elem.select('.btn, .button, .pagination, .paging, .share'):
                unwanted.decompose()
            
            # 본문 텍스트 추출
            content_text = self._html_to_markdown(content_elem)
        else:
            # 백업 방법: 전체 페이지에서 가장 긴 텍스트 블록 찾기
            content_candidates = []
            
            for elem in soup.find_all(['div', 'p', 'article', 'section']):
                text = elem.get_text(strip=True)
                if len(text) > 100:  # 최소 길이 조건
                    content_candidates.append(text)
            
            # 가장 긴 텍스트를 본문으로 선택
            if content_candidates:
                content_text = max(content_candidates, key=len)
            else:
                content_text = "본문 내용을 찾을 수 없습니다."
        
        return content_text.strip()
    
    def _html_to_markdown(self, element) -> str:
        """HTML 요소를 마크다운으로 변환"""
        try:
            # BeautifulSoup을 사용한 간단한 마크다운 변환
            text = element.get_text(separator='\n\n', strip=True)
            
            # 연속된 줄바꿈 정리
            text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
            
            # 연속된 공백 정리
            text = re.sub(r'[ \t]+', ' ', text)
            
            # 이미지 태그 처리
            for img in element.find_all('img'):
                alt = img.get('alt', '')
                src = img.get('src', '')
                if alt or src:
                    text += f"\n\n![{alt}]({src})\n\n"
            
            # 링크 태그 처리
            for link in element.find_all('a'):
                href = link.get('href', '')
                if href and not href.startswith('#') and not href.startswith('javascript:'):
                    link_text = link.get_text(strip=True)
                    if link_text:
                        text += f"\n\n[{link_text}]({href})\n\n"
            
            return text
            
        except Exception as e:
            logger.warning(f"마크다운 변환 실패: {e}")
            return element.get_text(separator='\n\n', strip=True)
    
    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """첨부파일 정보 추출"""
        attachments = []
        
        try:
            # KDB 첨부파일 다운로드 링크 패턴
            # /fileView?groupId=xxx&fileId=xxx 또는 유사한 패턴
            download_links = soup.find_all('a', href=re.compile(r'fileView'))
            
            for i, link in enumerate(download_links, 1):
                try:
                    href = link.get('href', '')
                    if 'fileView' not in href:
                        continue
                    
                    # 파일명 추출 (링크 텍스트에서)
                    filename = link.get_text(strip=True)
                    
                    # 파일명이 없는 경우 href에서 추출 시도
                    if not filename or filename in ['다운로드', '첨부파일']:
                        # URL 파라미터에서 파일명 추출 시도
                        parsed_url = urlparse(href)
                        query_params = parse_qs(parsed_url.query)
                        
                        if 'fileName' in query_params:
                            filename = query_params['fileName'][0]
                        elif 'filename' in query_params:
                            filename = query_params['filename'][0]
                        else:
                            filename = f"attachment_{i}"
                    
                    # 전체 URL 구성
                    file_url = urljoin(self.base_url, href)
                    
                    # 파일 타입 결정
                    file_type = self._determine_file_type(filename)
                    
                    attachment = {
                        'filename': filename,
                        'url': file_url,
                        'type': file_type,
                        'download_method': 'direct'
                    }
                    
                    attachments.append(attachment)
                    logger.debug(f"첨부파일 발견: {filename}")
                    
                except Exception as e:
                    logger.error(f"첨부파일 처리 중 오류: {e}")
                    continue
            
            logger.info(f"첨부파일 {len(attachments)}개 발견")
            return attachments
            
        except Exception as e:
            logger.error(f"첨부파일 추출 중 오류: {e}")
            return attachments
    
    def _determine_file_type(self, filename: str) -> str:
        """파일 타입 결정"""
        if not filename:
            return 'unknown'
        
        filename_lower = filename.lower()
        
        if filename_lower.endswith('.pdf'):
            return 'pdf'
        elif filename_lower.endswith(('.hwp', '.hwpx')):
            return 'hwp'
        elif filename_lower.endswith(('.doc', '.docx')):
            return 'doc'
        elif filename_lower.endswith(('.xls', '.xlsx')):
            return 'excel'
        elif filename_lower.endswith(('.ppt', '.pptx')):
            return 'powerpoint'
        elif filename_lower.endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
            return 'image'
        elif filename_lower.endswith(('.zip', '.rar', '.7z')):
            return 'archive'
        elif filename_lower.endswith(('.txt', '.text')):
            return 'text'
        else:
            return 'unknown'
    
    def scrape_kdb_announcements(self, max_pages: int = 3, output_base: str = "output/kdb") -> bool:
        """KDB 공지사항 스크래핑 메인 함수"""
        try:
            logger.info("=== KDB 공지사항 스크래핑 시작 ===")
            
            # 먼저 입찰공고 카테고리로 테스트
            categories = ["05", "ZZ"]  # 05: 입찰공고, ZZ: 전체
            
            for category in categories:
                logger.info(f"카테고리 '{category}' 처리 중")
                
                # 첫 번째 페이지로 실제 공지사항 URL 확인
                html_content = self.get_announcements_page(1, category)
                if not html_content:
                    logger.error(f"카테고리 '{category}' 첫 번째 페이지 로드 실패")
                    continue
                
                # 수집된 공고 저장
                all_announcements = []
                
                for page_num in range(1, max_pages + 1):
                    logger.info(f"카테고리 '{category}' 페이지 {page_num} 처리 중")
                    
                    if page_num > 1:
                        time.sleep(self.delay_between_pages)
                        html_content = self.get_announcements_page(page_num, category)
                        
                        if not html_content:
                            logger.warning(f"페이지 {page_num} 로드 실패")
                            continue
                    
                    # 페이지 파싱
                    announcements = self.parse_list_page(html_content)
                    if not announcements:
                        logger.warning(f"페이지 {page_num}에서 공고를 찾을 수 없음")
                        continue
                    
                    logger.info(f"페이지 {page_num}에서 {len(announcements)}개 공고 발견")
                    all_announcements.extend(announcements)
                
                logger.info(f"카테고리 '{category}' 총 {len(all_announcements)}개 공고 수집 완료")
                
                # 간단한 처리 결과 출력
                for i, announcement in enumerate(all_announcements[:10], 1):  # 처음 10개만 출력
                    logger.info(f"공고 {i}: {announcement['title']}")
                
                if all_announcements:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"스크래핑 중 오류 발생: {e}")
            return False


def main():
    """메인 실행 함수"""
    # 출력 디렉토리 설정
    output_dir = "output/kdb"
    
    # 스크래퍼 생성
    scraper = EnhancedKDBScraper()
    
    try:
        logger.info("=== KDB 공지사항 스크래핑 시작 ===")
        
        # 3페이지까지 스크래핑
        success = scraper.scrape_kdb_announcements(max_pages=3, output_base=output_dir)
        
        if success:
            logger.info("✅ KDB 공지사항 스크래핑 완료!")
        else:
            logger.error("❌ 스크래핑 실패")
            
    except Exception as e:
        logger.error(f"스크래핑 중 오류 발생: {e}")
        raise


if __name__ == "__main__":
    main()