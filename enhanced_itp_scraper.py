# -*- coding: utf-8 -*-
"""
Enhanced ITP 스크래퍼 - JavaScript 기반 스크래퍼
인천테크노파크(ITP) 전용 스크래퍼 (Enhanced 아키텍처)
itp_scraper.py 기반 리팩토링
"""

from enhanced_base_scraper import JavaScriptScraper
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
import os
import logging

logger = logging.getLogger(__name__)

class EnhancedITPScraper(JavaScriptScraper):
    """인천테크노파크(ITP) 전용 스크래퍼 - Enhanced 버전"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://itp.or.kr"
        self.list_url = "https://itp.or.kr/intro.asp?tmid=13"
        self.verify_ssl = False  # SSL 인증서 검증 비활성화
        
    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 반환"""
        if page_num == 1:
            return self.list_url
        else:
            # ITP는 GET 파라미터로 페이지네이션 처리
            return f"{self.list_url}&PageNum={page_num}"
            
    def parse_list_page(self, html_content: str) -> list:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 테이블 찾기
        table = soup.find('table', class_='list')
        if not table:
            logger.warning("목록 테이블을 찾을 수 없습니다")
            return announcements
            
        tbody = table.find('tbody')
        if not tbody:
            logger.warning("tbody를 찾을 수 없습니다")
            return announcements
            
        rows = tbody.find_all('tr')
        logger.info(f"ITP 목록에서 {len(rows)}개 행 발견")
        
        for row in rows:
            try:
                # 각 컬럼 찾기
                tds = row.find_all('td')
                if len(tds) < 4:
                    continue
                
                # 번호
                num = tds[0].get_text(strip=True)
                
                # 담당부서
                dept = tds[1].get_text(strip=True) if len(tds) > 1 else ''
                
                # 제목 (subject 클래스를 가진 td)
                subject_td = row.find('td', class_='subject')
                if not subject_td:
                    continue
                    
                link_elem = subject_td.find('a')
                if not link_elem:
                    continue
                    
                title = link_elem.get_text(strip=True)
                
                # JavaScript 함수에서 seq 추출
                href = link_elem.get('href', '')
                detail_url = self._extract_detail_url(href)
                
                # 날짜
                date = tds[3].get_text(strip=True) if len(tds) > 3 else ''
                
                # 상태 (이미지의 alt 속성에서 추출)
                status = self._extract_status(row)
                
                # 조회수
                views = tds[5].get_text(strip=True) if len(tds) > 5 else ''
                
                announcements.append({
                    'num': num,
                    'title': title,
                    'url': detail_url,
                    'status': status,
                    'writer': dept,  # 담당부서를 작성자로 사용
                    'date': date,
                    'period': '',  # ITP는 접수기간이 별도로 표시되지 않음
                    'views': views
                })
                
            except Exception as e:
                logger.debug(f"행 파싱 중 오류 (스킵): {e}")
                continue
        
        logger.info(f"ITP 목록에서 {len(announcements)}개 공고 파싱 완료")
        return announcements
    
    def _extract_detail_url(self, href: str) -> str:
        """JavaScript 함수에서 상세 URL 추출"""
        # JavaScript fncShow 함수에서 seq 추출
        seq_match = re.search(r"fncShow\('(\d+)'\)", href)
        if seq_match:
            seq = seq_match.group(1)
            return f"{self.base_url}/intro.asp?tmid=13&seq={seq}"
        else:
            # 다른 패턴이나 직접 링크인 경우
            return urljoin(self.base_url, href)
    
    def _extract_status(self, row) -> str:
        """상태 정보 추출"""
        status_img = row.find('img', alt=True)
        if status_img:
            return status_img.get('alt', '')
        return ''
        
    def parse_detail_page(self, html_content: str) -> dict:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 본문 내용 찾기
        content_area = self._find_content_area(soup)
        
        # 첨부파일 찾기
        attachments = self._find_attachments(soup)
        
        # 본문을 마크다운으로 변환
        content_md = ""
        if content_area:
            content_md = self.h.handle(str(content_area))
        else:
            # 전체 페이지에서 헤더/푸터 제외하고 추출 시도
            main_content = soup.find('div', class_='content_area') or soup.find('div', id='content')
            if main_content:
                content_md = self.h.handle(str(main_content))
                
        return {
            'content': content_md,
            'attachments': attachments
        }
    
    def _find_content_area(self, soup):
        """본문 영역 찾기"""
        # view 테이블에서 content 찾기
        view_table = soup.find('table', class_='view')
        if view_table:
            # 내용이 있는 td 찾기
            content_td = view_table.find('td', class_='content') or view_table.find('td', colspan=True)
            if content_td:
                logger.debug("view 테이블에서 본문 영역 발견")
                return content_td
        
        # 가능한 본문 선택자들
        content_selectors = [
            'div.view_content',
            'div.board_view',
            'div.content',
            'td.content',
            'div.view_body',
            'div.board_content',
            'div#content'
        ]
        
        for selector in content_selectors:
            content_area = soup.select_one(selector)
            if content_area:
                logger.debug(f"본문 영역 발견: {selector}")
                return content_area
        
        return None
    
    def _find_attachments(self, soup):
        """첨부파일 찾기 - ITP 특화"""
        attachments = []
        
        # ITP는 dl/dt/dd 구조로 첨부파일을 표시
        view_dl = soup.find('dl', class_='view')
        if view_dl:
            attachments.extend(self._extract_attachments_from_dl(view_dl))
        
        # 테이블 구조에서도 찾기
        if not attachments:
            attachments.extend(self._extract_attachments_from_table(soup))
        
        # 다른 패턴으로도 첨부파일 찾기
        if not attachments:
            attachments.extend(self._extract_attachments_by_patterns(soup))
        
        logger.info(f"첨부파일 {len(attachments)}개 발견")
        return attachments
    
    def _extract_attachments_from_dl(self, view_dl):
        """dl 구조에서 첨부파일 추출"""
        attachments = []
        dts = view_dl.find_all('dt')
        
        for dt in dts:
            if '첨부파일' in dt.get_text():
                # 다음 dd 태그 찾기
                dd = dt.find_next_sibling('dd')
                if dd:
                    file_links = dd.find_all('a', href=True)
                    for link in file_links:
                        attachment = self._process_file_link(link)
                        if attachment:
                            attachments.append(attachment)
        
        return attachments
    
    def _extract_attachments_from_table(self, soup):
        """테이블 구조에서 첨부파일 추출"""
        attachments = []
        file_rows = soup.find_all('tr')
        
        for row in file_rows:
            th = row.find('th')
            if th and '첨부파일' in th.get_text():
                td = row.find('td')
                if td:
                    file_links = td.find_all('a', href=True)
                    for link in file_links:
                        attachment = self._process_file_link(link)
                        if attachment:
                            attachments.append(attachment)
        
        return attachments
    
    def _extract_attachments_by_patterns(self, soup):
        """패턴 기반 첨부파일 추출"""
        attachments = []
        
        # 파일 다운로드 링크 패턴
        download_patterns = [
            'a[href*="download"]',
            'a[href*="file"]',
            'a[href*=".hwp"]',
            'a[href*=".pdf"]',
            'a[href*=".docx"]',
            'a[href*=".xlsx"]',
            'a[href*=".zip"]'
        ]
        
        for pattern in download_patterns:
            links = soup.select(pattern)
            for link in links:
                file_name = link.get_text(strip=True)
                file_url = link.get('href', '')
                
                if file_url and file_name:
                    # 상대 경로 처리
                    if not file_url.startswith(('http://', 'https://')):
                        file_url = urljoin(self.base_url, file_url)
                        
                    # 중복 제거
                    if not any(att['url'] == file_url for att in attachments):
                        attachments.append({
                            'name': file_name,
                            'url': file_url
                        })
        
        return attachments
    
    def _process_file_link(self, link):
        """개별 파일 링크 처리"""
        file_name = link.get_text(strip=True)
        file_url = link.get('href', '')
        onclick = link.get('onclick', '')
        
        # onclick 속성에서 JavaScript 함수 처리
        if onclick and 'fncFileDownload' in onclick:
            file_url = self._extract_download_url_from_onclick(onclick)
        # href에서 JavaScript 함수 추출
        elif 'fncFileDownload' in file_url:
            file_url = self._extract_download_url_from_href(file_url)
        elif file_url and not file_url.startswith(('http://', 'https://')):
            # 상대 경로 처리
            file_url = urljoin(self.base_url, file_url)
        
        # 파일명 정리 (크기 정보 제거)
        if file_name and not file_name.isspace():
            # "파일명.확장자(크기KB)" 형태에서 파일명만 추출
            file_name_match = re.match(r'^(.+?)\s*\(\d+KB\)$', file_name)
            if file_name_match:
                file_name = file_name_match.group(1).strip()
            
            if file_url:  # URL이 있을 때만 반환
                return {
                    'name': file_name,
                    'url': file_url
                }
        
        return None
    
    def _extract_download_url_from_onclick(self, onclick: str) -> str:
        """onclick 속성에서 다운로드 URL 추출"""
        match = re.search(r"fncFileDownload\('([^']+)',\s*'([^']+)'\)", onclick)
        if match:
            folder = match.group(1)
            filename = match.group(2)
            # 실제 다운로드 URL 구성
            return f"{self.base_url}/UploadData/{folder}/{filename}"
        return ""
    
    def _extract_download_url_from_href(self, href: str) -> str:
        """href 속성에서 다운로드 URL 추출"""
        match = re.search(r"fncFileDownload\('([^']+)',\s*'([^']+)'\)", href)
        if match:
            folder = match.group(1)
            filename = match.group(2)
            # 실제 다운로드 URL 구성
            return f"{self.base_url}/UploadData/{folder}/{filename}"
        return href