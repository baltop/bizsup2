# -*- coding: utf-8 -*-
"""
한국과학기술연구원(KIST) Enhanced 스크래퍼
표준 테이블 구조 기반의 게시판 스크래핑
"""

import re
import os
import time
from urllib.parse import urljoin, urlparse, unquote, parse_qs, urlencode
from bs4 import BeautifulSoup
import logging
from enhanced_base_scraper import StandardTableScraper

logger = logging.getLogger(__name__)

class EnhancedKistScraper(StandardTableScraper):
    """한국과학기술연구원(KIST) 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        
        # 기본 설정
        self.base_url = "https://www.kist.re.kr"
        self.list_url = "https://www.kist.re.kr/ko/notice/general-notice.do"
        
        # 사이트별 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1
        
        # 테이블 구조 설정
        self.table_selector = "table"
        self.tbody_selector = "tbody"
        self.row_selector = "tr"
        
        # 페이지네이션 설정 (오프셋 방식)
        self.items_per_page = 10
        
        logger.info("KIST 스크래퍼 초기화 완료")

    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 생성 (오프셋 방식)"""
        if page_num == 1:
            return f"{self.list_url}?mode=list&articleLimit=10&article.offset=0"
        else:
            offset = (page_num - 1) * self.items_per_page
            return f"{self.list_url}?mode=list&articleLimit=10&article.offset={offset}"

    def parse_list_page(self, html_content: str) -> list:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 테이블 찾기
        table = soup.find('table')
        if not table:
            logger.warning("테이블을 찾을 수 없습니다")
            return announcements
        
        # tbody 찾기 (없으면 table 전체 사용)
        tbody = table.find('tbody')
        rows = tbody.find_all('tr') if tbody else table.find_all('tr')
        
        # 헤더 행 제외 - 데이터가 있는 행만 선택
        data_rows = []
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 6:  # 번호, 제목, 작성자, 등록일, 첨부파일, 조회 - 6개 열
                data_rows.append(row)
        
        for i, row in enumerate(data_rows):
            try:
                cells = row.find_all('td')
                if len(cells) < 6:
                    continue
                
                # 번호 (첫 번째 셀)
                number_cell = cells[0]
                number = number_cell.get_text(strip=True)
                
                # 제목 (두 번째 셀)
                title_cell = cells[1]
                title_link = title_cell.find('a')
                if not title_link:
                    # 링크가 없는 경우 스킵
                    continue
                
                title = title_link.get_text(strip=True)
                href = title_link.get('href', '')
                
                # 상세 URL 처리
                if href:
                    # 상대 URL을 절대 URL로 변환 - KIST 특수 처리
                    if href.startswith('?'):
                        detail_url = f"{self.list_url}{href}"
                    else:
                        detail_url = urljoin(self.base_url, href)
                else:
                    logger.warning(f"유효하지 않은 링크: {title}")
                    continue
                
                # 작성자 (세 번째 셀)
                author_cell = cells[2]
                author = author_cell.get_text(strip=True)
                
                # 등록일 (네 번째 셀)
                date_cell = cells[3]
                date = date_cell.get_text(strip=True)
                
                # 첨부파일 (다섯 번째 셀)
                attachment_cell = cells[4]
                has_attachment = bool(attachment_cell.find('a'))
                
                # 조회수 (여섯 번째 셀)
                views_cell = cells[5]
                views = views_cell.get_text(strip=True)
                
                announcement = {
                    'number': number,
                    'title': title,
                    'url': detail_url,
                    'author': author,
                    'date': date,
                    'has_attachment': has_attachment,
                    'views': views,
                    'attachments': []
                }
                
                announcements.append(announcement)
                logger.info(f"공고 추가: [{number}] {title}")
                
            except Exception as e:
                logger.error(f"행 파싱 중 오류 발생: {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
        return announcements

    def parse_detail_page(self, html_content: str) -> dict:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출 - 여러 방법 시도
        title = ""
        
        # 방법 1: class에 'subject'나 'title'이 포함된 요소 찾기
        title_selectors = [
            '.subject',
            '.title',
            'h1',
            'h2',
            'h3',
            '[class*="subject"]',
            '[class*="title"]'
        ]
        
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                title = title_elem.get_text(strip=True)
                if len(title) > 5:  # 충분한 길이의 제목인 경우
                    break
        
        # 방법 2: strong 태그에서 제목 찾기
        if not title or len(title) < 5:
            strong_elems = soup.find_all('strong')
            for strong in strong_elems:
                text = strong.get_text(strip=True)
                if len(text) > 10 and len(text) < 200:
                    title = text
                    break
        
        # 본문 내용 추출
        content = ""
        
        # 방법 1: content, body, text 등의 클래스를 가진 요소 찾기
        content_selectors = [
            '.content',
            '.body',
            '.text',
            '.article-content',
            '.notice-content',
            '[class*="content"]',
            '[class*="body"]'
        ]
        
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                content = self.h.handle(str(content_elem)).strip()
                if len(content) > 50:  # 충분한 내용이 있는 경우
                    break
        
        # 방법 2: 테이블에서 가장 긴 텍스트가 있는 셀 찾기
        if not content or len(content) < 50:
            all_tds = soup.find_all('td')
            longest_content = ""
            for td in all_tds:
                # 링크나 이미지만 있는 셀은 제외
                if td.find('a') and not td.get_text(strip=True):
                    continue
                if td.find('img') and len(td.get_text(strip=True)) < 10:
                    continue
                
                td_text = td.get_text(strip=True)
                if len(td_text) > len(longest_content) and len(td_text) > 50:
                    longest_content = self.h.handle(str(td)).strip()
            
            if longest_content:
                content = longest_content
        
        # 방법 3: div 요소들에서 충분한 텍스트가 있는 요소들 조합
        if not content or len(content) < 50:
            all_divs = soup.find_all('div')
            content_parts = []
            for div in all_divs:
                text = div.get_text(strip=True)
                # 네비게이션이나 메뉴는 제외
                if any(word in text.lower() for word in ['menu', 'nav', 'footer', 'header']):
                    continue
                if len(text) > 30 and len(text) < 1000:
                    content_parts.append(text)
            
            if content_parts:
                content = '\n\n'.join(content_parts[:3])  # 처음 3개 부분만
        
        # 첨부파일 추출
        attachments = self._extract_attachments(soup)
        
        return {
            'title': title,
            'content': content,
            'attachments': attachments
        }

    def _extract_attachments(self, soup: BeautifulSoup) -> list:
        """첨부파일 정보 추출 - 개선된 버전"""
        attachments = []
        
        # Defense Tech News 링크 필터링 추가
        download_links = soup.find_all('a', href=re.compile(r'mode=download.*attachNo='))
        
        for link in download_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # Defense Tech News 필터링 (사이트 전역 네비게이션 제외)
            if any(keyword in href.lower() for keyword in ['defense_tech', 'newsandissue']):
                logger.debug(f"Defense Tech News 링크 제외: {href}")
                continue
            
            if any(keyword in text.lower() for keyword in ['defense tech', 'news&issue', 'newsandissue']):
                logger.debug(f"Defense Tech News 텍스트 제외: {text}")
                continue
            
            # 빈 텍스트나 "첨부파일"만 있는 경우 스킵
            if not text or text in ['첨부파일', 'attachment', '첨부']:
                continue
            
            # attachNo 추출하여 고유성 확인
            attach_match = re.search(r'attachNo=(\d+)', href)
            if not attach_match:
                continue
            
            attach_no = attach_match.group(1)
            
            # 파일명 추출 및 정제
            filename = self._clean_filename(text)
            
            # 다운로드 URL 구성
            if href.startswith('?'):
                download_url = f"{self.list_url}{href}"
            else:
                download_url = urljoin(self.base_url, href)
            
            if filename and len(filename) > 1:
                attachment = {
                    'filename': filename,
                    'url': download_url,
                    'original_text': text,
                    'attach_no': attach_no
                }
                
                attachments.append(attachment)
                logger.info(f"첨부파일 발견: {filename} (attachNo: {attach_no})")
        
        return attachments
    
    def _clean_filename(self, filename: str) -> str:
        """파일명 정제"""
        if not filename:
            return "attachment.pdf"
        
        # 대괄호로 감싸진 파일명 정제
        if filename.startswith('[') and ']' in filename:
            # [공고문] 파일명.pdf 형태에서 파일명 추출
            bracket_match = re.match(r'\[([^\]]+)\]\s*(.*)', filename)
            if bracket_match:
                prefix = bracket_match.group(1)
                actual_filename = bracket_match.group(2).strip()
                if actual_filename:
                    filename = actual_filename
                else:
                    filename = f"{prefix}.pdf"  # 확장자 추정
        
        # 파일 확장자 확인 및 추가
        if '.' not in filename or not any(ext in filename.lower() for ext in ['.pdf', '.hwp', '.doc', '.xls', '.jpg', '.png', '.zip']):
            # 기본적으로 PDF 확장자 추가
            filename += '.pdf'
        
        return filename
        
