# -*- coding: utf-8 -*-
"""
한국의료기기산업협회(KFME) 공지사항 스크래퍼 - Enhanced 버전
URL: https://www.kfme.or.kr/kr/board/notice.php?cate=1
"""

import os
import re
import time
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, unquote, parse_qs, urlparse
from bs4 import BeautifulSoup

try:
    from enhanced_base_scraper import StandardTableScraper
except ImportError:
    from enhanced_base_scraper import EnhancedBaseScraper as StandardTableScraper

logger = logging.getLogger(__name__)

class EnhancedKfmeScraper(StandardTableScraper):
    """한국의료기기산업협회(KFME) 전용 스크래퍼 - Enhanced 버전"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.kfme.or.kr"
        self.list_url = "https://www.kfme.or.kr/kr/board/notice.php?cate=1"
        
        # KFME 사이트 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1.5  # 적절한 간격
        
        # 공지사항 포함 수집 설정
        self.include_notices = True
        
        # 세션 설정
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        logger.info("Enhanced KFME 스크래퍼 초기화 완료")

    def get_list_url(self, page_num: int) -> str:
        """페이지별 목록 URL 생성"""
        if page_num == 1:
            return self.list_url
        else:
            start_page = (page_num - 1) * 10  # 10씩 증가 (0, 10, 20, 30...)
            return f"{self.list_url}&startPage={start_page}"

    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱 - DIV 기반"""
        announcements = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # KFME 사이트는 div.bbs-list-row 구조
            list_rows = soup.find_all('div', class_='bbs-list-row')
            if not list_rows:
                logger.warning("공지사항 목록을 찾을 수 없습니다")
                return announcements
            
            logger.info(f"총 {len(list_rows)}개의 공고 행을 발견했습니다")
            
            for i, row in enumerate(list_rows):
                try:
                    # 공지사항 여부 확인
                    is_notice = 'notice-row' in row.get('class', [])
                    
                    # 공지구분 (첫 번째 div)
                    notice_category = row.find('div', class_='bbs-notice-category')
                    if notice_category:
                        notice_text = notice_category.get_text(strip=True)
                        if '공지사항' in notice_text:
                            is_notice = True
                    
                    # 제목 및 링크 (두 번째 div)
                    title_div = row.find('div', class_='bbs-title')
                    if not title_div:
                        continue
                    
                    link_elem = title_div.find('a')
                    if not link_elem:
                        continue
                    
                    title = link_elem.get_text(strip=True)
                    href = link_elem.get('href', '')
                    
                    # 상대 경로를 절대 경로로 변환
                    detail_url = urljoin(self.base_url, href)
                    
                    # 공고 번호 추출 (URL에서 idx 파라미터)
                    parsed_url = urlparse(detail_url)
                    query_params = parse_qs(parsed_url.query)
                    idx = query_params.get('idx', [None])[0]
                    
                    if is_notice:
                        number = "공지"
                    elif idx:
                        number = idx
                    else:
                        number = f"item_{i+1}"
                    
                    # 첨부파일 여부 확인 (세 번째 div)
                    file_div = row.find_all('div', class_='bbs-inline')[0] if row.find_all('div', class_='bbs-inline') else None
                    has_attachment = False
                    if file_div:
                        # 첨부파일 아이콘이나 링크 확인
                        file_icon = file_div.find('img') or file_div.find('a')
                        has_attachment = bool(file_icon)
                    
                    # 작성자 (네 번째 div)
                    inline_divs = row.find_all('div', class_='bbs-inline')
                    author = ""
                    date = ""
                    views = ""
                    
                    if len(inline_divs) >= 2:
                        author = inline_divs[1].get_text(strip=True)
                    if len(inline_divs) >= 3:
                        date = inline_divs[2].get_text(strip=True)
                    
                    # 조회수 (마지막 div - bbs-m-display-none)
                    views_div = row.find('div', class_='bbs-m-display-none')
                    if views_div:
                        views = views_div.get_text(strip=True)
                    
                    announcement = {
                        'number': number,
                        'title': title,
                        'url': detail_url,
                        'author': author,
                        'date': date,
                        'views': views,
                        'has_attachment': has_attachment,
                        'is_notice': is_notice,
                        'idx': idx
                    }
                    
                    announcements.append(announcement)
                    logger.info(f"공고 추가: [{number}] {title}")
                    
                except Exception as e:
                    logger.warning(f"목록 행 {i+1} 파싱 중 오류: {e}")
                    continue
            
            logger.info(f"총 {len(announcements)}개의 공고를 파싱했습니다")
            
        except Exception as e:
            logger.error(f"목록 페이지 파싱 중 오류 발생: {e}")
        
        return announcements

    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 제목 추출
            title = "제목 없음"
            title_selectors = [
                'h1.bbs-tit',
                '.bbs-tit',
                'h1', 'h2', 'h3'
            ]
            
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    break
            
            # 메타 정보 추출
            author = ""
            date = ""
            views = ""
            
            # 메타 정보는 상세 페이지에서 다양한 위치에 있을 수 있음
            meta_info = soup.find('div', class_='bbs-view-info')
            if meta_info:
                meta_text = meta_info.get_text()
                # 날짜 패턴 추출 (YYYY-MM-DD)
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', meta_text)
                if date_match:
                    date = date_match.group(1)
                # 조회수 패턴 추출
                views_match = re.search(r'조회\s*:?\s*(\d+)', meta_text)
                if views_match:
                    views = views_match.group(1)
            
            # 작성자 정보 추출
            author_info = soup.find('span', class_='bbs-view-writer') or soup.find('div', class_='bbs-view-writer')
            if author_info:
                author = author_info.get_text(strip=True)
            
            # 본문 내용 추출
            content = ""
            content_selectors = [
                'div.bbs-view-content.editor',
                '.bbs-view-content',
                '.editor',
                '.content'
            ]
            
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    content = self.h.handle(str(content_elem))
                    break
            
            if not content:
                # 일반적인 div나 p 태그에서 내용 추출
                content_div = soup.find('div', class_=re.compile(r'content|view|bbs'))
                if content_div:
                    content = self.h.handle(str(content_div))
            
            # 첨부파일 추출
            attachments = self._extract_attachments(soup)
            
            return {
                'title': title,
                'author': author,
                'date': date,
                'views': views,
                'content': content,
                'attachments': attachments
            }
            
        except Exception as e:
            logger.error(f"상세 페이지 파싱 중 오류: {e}")
            return {
                'title': "파싱 오류",
                'author': "",
                'date': "",
                'views': "",
                'content': f"상세 페이지 파싱 중 오류가 발생했습니다: {e}",
                'attachments': []
            }

    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """첨부파일 정보 추출"""
        attachments = []
        
        try:
            # KFME 사이트의 첨부파일 패턴 찾기
            attachment_selectors = [
                'a[href*="bbs_download.php"]',
                'a[href*="download"]',
                '.bbs-view-file-info-box a',
                '.file-list a',
                '.attach a'
            ]
            
            for selector in attachment_selectors:
                file_links = soup.select(selector)
                
                for link in file_links:
                    href = link.get('href', '')
                    
                    if 'bbs_download.php' not in href:
                        continue
                    
                    # 다운로드 URL 구성
                    download_url = urljoin(self.base_url, href)
                    
                    # 파일명 추출 (링크 텍스트에서)
                    filename = link.get_text(strip=True)
                    
                    # 파일명이 비어있거나 너무 짧으면 URL에서 추출 시도
                    if not filename or len(filename) < 3:
                        # URL 파라미터에서 파일명 추출 시도
                        parsed_url = urlparse(download_url)
                        query_params = parse_qs(parsed_url.query)
                        idx = query_params.get('idx', [None])[0]
                        if idx:
                            filename = f"attachment_{idx}"
                    
                    # 파일명 정리
                    filename = filename.replace('+', ' ')  # URL 인코딩된 공백 처리
                    filename = re.sub(r'^\s*다운로드\s*', '', filename)  # "다운로드" 텍스트 제거
                    filename = filename.strip()
                    
                    if filename and download_url:
                        attachment = {
                            'filename': filename,
                            'url': download_url,
                            'size': "unknown"
                        }
                        
                        attachments.append(attachment)
                        logger.info(f"첨부파일 발견: {filename}")
                
                if attachments:  # 첨부파일을 찾았으면 다른 선택자는 시도하지 않음
                    break
            
        except Exception as e:
            logger.error(f"첨부파일 추출 중 오류: {e}")
        
        return attachments

    def download_file(self, file_url: str, save_path: str, attachment_info: Dict[str, Any] = None) -> bool:
        """파일 다운로드 - KFME 특화"""
        try:
            logger.info(f"파일 다운로드 시작: {file_url}")
            
            # Referer 헤더 추가 (중요)
            headers = self.session.headers.copy()
            headers['Referer'] = self.list_url
            
            response = self.session.get(
                file_url, 
                headers=headers,
                timeout=self.timeout,
                verify=self.verify_ssl,
                stream=True
            )
            
            if response.status_code == 200:
                # Enhanced Base Scraper가 이미 올바른 파일명으로 save_path를 설정했으므로 그대로 사용
                filename = save_path
                
                # 파일 저장
                os.makedirs(os.path.dirname(filename), exist_ok=True)
                
                with open(filename, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                file_size = os.path.getsize(filename)
                logger.info(f"파일 다운로드 완료: {filename} ({file_size} bytes)")
                
                return True
            else:
                logger.error(f"파일 다운로드 실패: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"파일 다운로드 중 오류: {e}")
            return False

    def sanitize_filename(self, filename: str) -> str:
        """파일명 정리"""
        # Windows 호환을 위한 특수문자 제거
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = filename.strip('. ')
        
        return filename if filename else "unnamed_file"


def main():
    """테스트용 메인 함수"""
    scraper = EnhancedKfmeScraper()
    output_dir = "output/kfme"
    
    try:
        os.makedirs(output_dir, exist_ok=True)
        scraper.scrape_pages(max_pages=3, output_base=output_dir)
        print("✅ KFME 스크래핑 완료")
        
    except KeyboardInterrupt:
        print("\n❌ 사용자에 의해 중단되었습니다")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()