# -*- coding: utf-8 -*-
"""
한국해양수산개발원(KMI) Enhanced 스크래퍼
표준 테이블 구조 기반의 게시판 스크래핑
"""

import re
import os
import time
from urllib.parse import urljoin, urlparse, unquote
from bs4 import BeautifulSoup
import logging
from enhanced_base_scraper import StandardTableScraper

logger = logging.getLogger(__name__)

class EnhancedKmiScraper(StandardTableScraper):
    """한국해양수산개발원(KMI) 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        
        # 기본 설정
        self.base_url = "https://www.kmi.re.kr"
        self.list_url = "https://www.kmi.re.kr/web/board/list.do?rbsIdx=68"
        
        # 사이트별 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1
        
        # 테이블 구조 설정
        self.table_selector = "table"
        self.tbody_selector = "tbody"
        self.row_selector = "tr"
        
        # 페이지네이션 설정
        self.items_per_page = 10
        
        logger.info("KMI 스크래퍼 초기화 완료")

    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 생성"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}&page={page_num}"

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
            if len(cells) >= 3:  # 번호, 제목, 작성일 최소 3개 열
                data_rows.append(row)
        
        for i, row in enumerate(data_rows):
            try:
                cells = row.find_all('td')
                if len(cells) < 3:
                    continue
                
                # 번호 (첫 번째 셀)
                number_cell = cells[0]
                number = number_cell.get_text(strip=True)
                
                # 제목 (두 번째 셀)
                title_cell = cells[1]
                title_link = title_cell.find('a')
                if not title_link:
                    # 링크가 없는 경우 텍스트만 추출
                    title = title_cell.get_text(strip=True)
                    detail_url = None
                else:
                    title = title_link.get_text(strip=True)
                    href = title_link.get('href', '')
                    # 상대 URL을 절대 URL로 변환
                    detail_url = urljoin(f"{self.base_url}/web/board/", href)
                
                # 작성일 (세 번째 셀)
                date_cell = cells[2]
                date = date_cell.get_text(strip=True)
                
                # 첨부파일 여부 확인 (제목 셀에서 아이콘 확인)
                has_attachment = bool(title_cell.find('img')) or bool(title_cell.find('i', class_='fa-paperclip'))
                
                if detail_url:  # 링크가 있는 공고만 수집
                    announcement = {
                        'number': number,
                        'title': title,
                        'url': detail_url,
                        'date': date,
                        'has_attachment': has_attachment,
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
        
        # 방법 1: h1, h2, h3 태그에서 제목 찾기
        for tag in ['h1', 'h2', 'h3']:
            title_elem = soup.find(tag)
            if title_elem:
                title = title_elem.get_text(strip=True)
                break
        
        # 방법 2: class나 id에 'title'이 포함된 요소 찾기
        if not title:
            title_elem = soup.find(['div', 'span', 'td'], class_=re.compile(r'title', re.I))
            if title_elem:
                title = title_elem.get_text(strip=True)
        
        # 방법 3: 첫 번째 큰 텍스트 블록을 제목으로 간주
        if not title:
            for elem in soup.find_all(['p', 'div', 'td']):
                text = elem.get_text(strip=True)
                if len(text) > 10 and len(text) < 200:
                    title = text
                    break
        
        # 본문 내용 추출
        content = ""
        
        # 방법 1: content, body, main 등의 클래스나 ID를 가진 요소 찾기
        content_selectors = [
            'div[class*="content"]',
            'div[class*="body"]',
            'div[class*="text"]',
            'div[id*="content"]',
            'td[class*="content"]'
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
                td_text = td.get_text(strip=True)
                if len(td_text) > len(longest_content) and len(td_text) > 50:
                    longest_content = self.h.handle(str(td)).strip()
            
            if longest_content:
                content = longest_content
        
        # 방법 3: body 전체에서 충분한 텍스트가 있는 요소들 조합
        if not content or len(content) < 50:
            all_paragraphs = []
            for elem in soup.find_all(['p', 'div', 'td', 'span']):
                text = elem.get_text(strip=True)
                if len(text) > 30:
                    all_paragraphs.append(text)
            
            if all_paragraphs:
                content = '\n\n'.join(all_paragraphs[:5])  # 처음 5개 문단만
        
        # 첨부파일 추출
        attachments = self._extract_attachments(soup)
        
        return {
            'title': title,
            'content': content,
            'attachments': attachments
        }

    def _extract_attachments(self, soup: BeautifulSoup) -> list:
        """첨부파일 정보 추출"""
        attachments = []
        
        # 다운로드 링크 찾기 - 여러 패턴 시도
        
        # 패턴 1: download.do가 포함된 링크
        download_links = soup.find_all('a', href=re.compile(r'download\.do'))
        
        for link in download_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # 파일명 추출
            filename = text
            
            # 이미지 태그가 있는 경우 파일 아이콘으로 판단
            if link.find('img'):
                # 링크 텍스트에서 파일명 추출
                clean_text = re.sub(r'\s+', ' ', text).strip()
                if clean_text and not clean_text.lower().startswith(('다운로드', 'download')):
                    filename = clean_text
            
            # 파일 확장자가 있는 텍스트 우선 추출
            if '.' in text:
                parts = text.split()
                for part in parts:
                    if '.' in part and any(ext in part.lower() for ext in ['.pdf', '.hwp', '.doc', '.xls', '.jpg', '.png', '.zip']):
                        filename = part
                        break
            
            # 다운로드 URL 구성
            download_url = urljoin(f"{self.base_url}/web/board/", href)
            
            if filename and filename != text:
                attachment = {
                    'filename': filename,
                    'url': download_url,
                    'original_text': text
                }
                
                attachments.append(attachment)
                logger.info(f"첨부파일 발견: {filename}")
        
        # 패턴 2: 파일 확장자가 포함된 링크 찾기
        if not attachments:
            file_links = soup.find_all('a', string=re.compile(r'\.(pdf|hwp|doc|docx|xls|xlsx|ppt|pptx|zip|jpg|png|gif)$', re.I))
            
            for link in file_links:
                href = link.get('href', '')
                filename = link.get_text(strip=True)
                
                if href:
                    download_url = urljoin(f"{self.base_url}/web/board/", href)
                    
                    attachment = {
                        'filename': filename,
                        'url': download_url,
                        'original_text': filename
                    }
                    
                    attachments.append(attachment)
                    logger.info(f"첨부파일 발견: {filename}")
        
        return attachments