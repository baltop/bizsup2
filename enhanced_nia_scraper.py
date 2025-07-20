#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced NIA 스크래퍼 - 한국지능정보사회진흥원 공지사항 수집
URL: https://www.nia.or.kr/site/nia_kor/ex/bbs/List.do?cbIdx=99835

한국지능정보사회진흥원 공지사항 게시판에서 공고와 첨부파일을 모두 수집하는 완전한 스크래퍼입니다.
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
        logging.FileHandler('enhanced_nia_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class EnhancedNIAScraper(EnhancedBaseScraper):
    """NIA 공지사항 완전한 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.nia.or.kr"
        self.list_url = "https://www.nia.or.kr/site/nia_kor/ex/bbs/List.do"
        self.cb_idx = "99835"  # 공지사항 게시판 ID
        
        # NIA 특화 설정
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # 사이트 특화 설정
        self.verify_ssl = True
        self.timeout = 30
        self.delay_between_requests = 1
        self.delay_between_pages = 2
        
    def get_list_url(self, page_num: int) -> str:
        """페이지별 URL 생성"""
        if page_num == 1:
            return f"{self.list_url}?cbIdx={self.cb_idx}"
        else:
            return f"{self.list_url}?cbIdx={self.cb_idx}&pageIndex={page_num}"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        try:
            # NIA는 JavaScript onclick 이벤트로 링크를 처리함
            # doBbsFView('99835','27590','16010100','27590') 패턴 찾기
            onclick_links = soup.find_all('a', onclick=True)
            
            logger.info(f"onclick 링크 {len(onclick_links)}개 발견")
            
            for i, link in enumerate(onclick_links):
                try:
                    onclick = link.get('onclick', '')
                    
                    # doBbsFView 함수 호출 패턴 매칭
                    match = re.search(r"doBbsFView\('(\d+)','(\d+)','(\d+)','(\d+)'\)", onclick)
                    if not match:
                        continue
                    
                    cb_idx, bc_idx, menu_no, bc_idx2 = match.groups()
                    
                    # 제목 추출 (링크 주변 텍스트에서)
                    title = self._extract_title_from_link(link)
                    if not title:
                        continue
                    
                    # "new" 표시 제거
                    title = re.sub(r'\s*new\s*', '', title, flags=re.IGNORECASE)
                    
                    # View.do URL 구성
                    detail_url = f"{self.base_url}/site/nia_kor/ex/bbs/View.do?cbIdx={cb_idx}&bcIdx={bc_idx}&menuNo={menu_no}"
                    
                    # 메타 정보 추출 (링크 주변 텍스트에서)
                    parent_text = self._get_parent_text(link)
                    
                    # 날짜 패턴 찾기
                    date = ""
                    date_pattern = r'(\d{4}\.\d{2}\.\d{2})'
                    date_match = re.search(date_pattern, parent_text)
                    if date_match:
                        date = date_match.group(1)
                    
                    # 조회수 패턴 찾기
                    views = ""
                    views_pattern = r'조회수\s*(\d+)'
                    views_match = re.search(views_pattern, parent_text)
                    if views_match:
                        views = views_match.group(1)
                    
                    # 작성자 정보 찾기
                    author = ""
                    department = ""
                    
                    # 첨부파일 존재 여부 확인
                    has_attachments = '첨부파일' in parent_text
                    
                    announcement = {
                        'title': title,
                        'url': detail_url,
                        'date': date,
                        'views': views,
                        'author': author,
                        'department': department,
                        'has_attachments': has_attachments
                    }
                    
                    announcements.append(announcement)
                    logger.debug(f"공고 추가: {title}")
                    
                except Exception as e:
                    logger.error(f"공고 항목 파싱 중 오류 (항목 {i}): {e}")
                    continue
            
            logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
            return announcements
            
        except Exception as e:
            logger.error(f"목록 페이지 파싱 중 오류: {e}")
            return announcements
    
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
                '#sub_contentsArea h1', '#sub_contentsArea h2'
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
        
        # NIA 특화 콘텐츠 선택자
        content_selectors = [
            '#sub_contentsArea',
            '.board_view_content',
            '.view_content',
            '.content_area',
            '.board_content',
            '.detail_content',
            '.article_content',
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
            # NIA 첨부파일 다운로드 링크 패턴
            # /common/board/Download.do?bcIdx=...&cbIdx=...&fileNo=...
            download_links = soup.find_all('a', href=re.compile(r'/common/board/Download\.do'))
            
            for i, link in enumerate(download_links, 1):
                try:
                    href = link.get('href', '')
                    if '/common/board/Download.do' not in href:
                        continue
                    
                    # 파일명 추출 (링크 텍스트에서)
                    filename = link.get_text(strip=True)
                    
                    # 파일명에서 다운로드 관련 텍스트 제거
                    filename = re.sub(r'-다운로드$', '', filename)
                    
                    if not filename:
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
    
    def _extract_title_from_link(self, link) -> str:
        """링크에서 제목 추출"""
        try:
            # 링크 자체의 텍스트 시도
            title = link.get_text(strip=True)
            if title and len(title) > 3:
                return title
            
            # 부모 요소에서 텍스트 찾기
            parent = link.parent
            if parent:
                # 부모의 모든 텍스트 가져오기
                parent_text = parent.get_text(strip=True)
                # 날짜, 조회수 등 제거하고 제목만 추출
                title_match = re.search(r'^(.*?)\s*(?:new\s*)?(?:\d{4}\.\d{2}\.\d{2}|조회수)', parent_text, re.IGNORECASE)
                if title_match:
                    title = title_match.group(1).strip()
                    if title:
                        return title
                
                # 백업: 첫 번째 의미있는 텍스트 블록 사용
                if parent_text and len(parent_text) > 3:
                    # 공백과 특수문자 정리
                    title = re.sub(r'\s+', ' ', parent_text)
                    # 너무 긴 제목은 자르기
                    if len(title) > 100:
                        title = title[:100] + '...'
                    return title
            
            return ""
            
        except Exception as e:
            logger.error(f"제목 추출 중 오류: {e}")
            return ""
    
    def _get_parent_text(self, link) -> str:
        """링크의 부모 요소에서 전체 텍스트 추출"""
        try:
            # 부모의 부모까지 올라가서 텍스트 찾기
            parent = link.parent
            if parent and parent.parent:
                return parent.parent.get_text(strip=True)
            elif parent:
                return parent.get_text(strip=True)
            else:
                return ""
        except Exception as e:
            logger.error(f"부모 텍스트 추출 중 오류: {e}")
            return ""


def main():
    """메인 실행 함수"""
    # 출력 디렉토리 설정
    output_dir = "output/nia"
    
    # 스크래퍼 생성
    scraper = EnhancedNIAScraper()
    
    try:
        logger.info("=== NIA 공지사항 스크래핑 시작 ===")
        
        # 3페이지까지 스크래핑
        success = scraper.scrape_pages(max_pages=3, output_base=output_dir)
        
        if success:
            logger.info("✅ NIA 공지사항 스크래핑 완료!")
            
            # 통계 출력
            stats = scraper.get_stats()
            logger.info(f"처리 시간: {stats.get('duration_seconds', 0):.1f}초")
            logger.info(f"HTTP 요청: {stats['requests_made']}개")
            logger.info(f"다운로드 파일: {stats['files_downloaded']}개")
            logger.info(f"전체 다운로드 크기: {scraper._format_size(stats['total_download_size'])}")
            
            if stats['errors_encountered'] > 0:
                logger.warning(f"발생한 오류: {stats['errors_encountered']}개")
            
            logger.info(f"저장 위치: {output_dir}")
        else:
            logger.error("❌ 스크래핑 실패")
            
    except Exception as e:
        logger.error(f"스크래핑 중 오류 발생: {e}")
        raise


if __name__ == "__main__":
    main()