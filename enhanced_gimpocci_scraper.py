# -*- coding: utf-8 -*-
"""
GIMPOCCI (김포상공회의소) 스크래퍼 - 향상된 버전 (SNCCI 패턴 기반)
https://gimpocci.net/%ea%b3%b5%ec%a7%80%ec%82%ac%ed%95%ad/
"""

import requests
from bs4 import BeautifulSoup
import os
import time
import html2text
from urllib.parse import urljoin, urlparse, parse_qs, unquote
import re
import json
import logging
from typing import Dict, List, Any, Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from enhanced_base_scraper import StandardTableScraper

logger = logging.getLogger(__name__)

class EnhancedGIMPOCCIScraper(StandardTableScraper):
    """GIMPOCCI 전용 스크래퍼 - Selenium 기반 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        
        # GIMPOCCI 기본 설정
        self.base_url = "https://gimpocci.net"
        self.list_url = "https://gimpocci.net/%ea%b3%b5%ec%a7%80%ec%82%ac%ed%95%ad/"
        
        # 사이트별 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 2
        self.delay_between_pages = 3
        
        # Selenium 설정
        self.driver = None
        self.use_selenium = True  # JavaScript 필요 사이트
    
    def _init_selenium(self):
        """Selenium WebDriver 초기화"""
        if not self.driver:
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--disable-features=VizDisplayCompositor')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
            
            try:
                # ChromeDriver 버전 문제 해결을 위한 대안 시도
                from selenium.webdriver.chrome.service import Service
                
                # 시스템 chromedriver 사용 (버전 불일치 무시)
                service = Service()
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                logger.info("Selenium WebDriver 초기화 완료")
            except Exception as e:
                logger.warning(f"Selenium 초기화 실패: {e}")
                logger.info("requests 방식으로 대체합니다")
                self.use_selenium = False
    
    def _close_selenium(self):
        """Selenium WebDriver 종료"""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 생성"""
        if page_num == 1:
            return self.list_url
        else:
            # URL 패턴: ?mode=list&board_page=2
            return f"{self.list_url}?mode=list&board_page={page_num}"
    
    def get_page(self, url: str):
        """페이지 가져오기 - Selenium 우선, requests 대안"""
        if self.use_selenium:
            return self._get_page_with_selenium(url)
        else:
            return super().get_page(url)
    
    def _get_page_with_selenium(self, url: str):
        """Selenium으로 페이지 가져오기"""
        try:
            if not self.driver:
                self._init_selenium()
                if not self.driver:
                    return None
            
            logger.info(f"Selenium으로 페이지 로딩: {url}")
            self.driver.get(url)
            
            # 페이지 로딩 대기
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "table"))
            )
            
            # 추가 대기 (동적 콘텐츠 로딩)
            time.sleep(2)
            
            html_content = self.driver.page_source
            
            # requests.Response 객체와 유사한 객체 생성
            class SeleniumResponse:
                def __init__(self, text, status_code=200):
                    self.text = text
                    self.status_code = status_code
                    self.headers = {}
            
            return SeleniumResponse(html_content)
            
        except Exception as e:
            logger.error(f"Selenium 페이지 로딩 실패: {e}")
            return None
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱 - GIMPOCCI 테이블 구조 (Selenium 기반)"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 메인 테이블 찾기 - caption이 "공지사항"인 테이블
        table = None
        for t in soup.find_all('table'):
            caption = t.find('caption')
            if caption and '공지사항' in caption.get_text():
                table = t
                logger.debug(f"공지사항 테이블 발견")
                break
        
        if not table:
            logger.warning("목록 테이블을 찾을 수 없습니다")
            # 디버깅을 위해 모든 테이블 로그
            tables = soup.find_all('table')
            logger.info(f"총 {len(tables)}개 테이블 발견")
            for i, t in enumerate(tables):
                caption = t.find('caption')
                caption_text = caption.get_text() if caption else "None"
                logger.info(f"테이블 {i+1} caption: {caption_text}")
                rows = t.find_all('tr')
                logger.info(f"테이블 {i+1} 행 수: {len(rows)}")
            return announcements
        
        # tbody 또는 전체 행에서 데이터 추출
        tbody = table.find('tbody')
        if tbody:
            rows = tbody.find_all('tr')
        else:
            # tbody가 없으면 모든 row에서 헤더 제외
            all_rows = table.find_all('tr')
            # 첫 번째 행이 헤더인지 확인
            if all_rows and all_rows[0].find('th'):
                rows = all_rows[1:]  # 헤더 제외
            else:
                rows = all_rows
        
        logger.info(f"총 {len(rows)}개 행 발견")
        
        for row in rows:
            try:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 3:  # 번호, 제목, 날짜
                    continue
                
                # 첫 번째 셀이 th인 경우 (헤더 행) 스킵
                if cells[0].name == 'th':
                    continue
                
                # 번호 (첫 번째 컬럼) - "공지" 또는 숫자
                no_cell = cells[0]
                no = no_cell.get_text(strip=True)
                
                # 제목 (두 번째 컬럼)
                title_cell = cells[1]
                link_elem = title_cell.find('a')
                
                if not link_elem:
                    continue
                
                title = link_elem.get_text(strip=True)
                
                if not title or title in ['제목', '']:
                    continue
                
                # URL 추출 - vid 파라미터 기반
                href = link_elem.get('href', '')
                if href and '?vid=' in href:
                    detail_url = urljoin(self.base_url, href)
                else:
                    logger.warning(f"상세 URL을 찾을 수 없습니다: {title}")
                    continue
                
                # 날짜 (세 번째 컬럼)
                date_cell = cells[2]
                date = date_cell.get_text(strip=True)
                
                # 첨부파일 여부 확인 (file 이미지 등)
                has_attachment = bool(title_cell.find('img', alt='file') or 'file' in title)
                
                announcement = {
                    'title': title,
                    'url': detail_url,
                    'date': date,
                    'no': no,
                    'has_attachment': has_attachment
                }
                
                announcements.append(announcement)
                logger.debug(f"공고 추가: {title}")
                
            except Exception as e:
                logger.error(f"행 파싱 중 오류: {e}")
                continue
        
        logger.info(f"파싱 완료: {len(announcements)}개 공고")
        return announcements
    
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출 - 테이블에서 "제목" 라벨 다음 셀에서 찾기
        title = ""
        title_header = soup.find('td', string=re.compile('제목'))
        if title_header:
            # 같은 행의 다음 셀에서 제목 찾기
            title_row = title_header.parent
            cells = title_row.find_all('td')
            if len(cells) >= 2:
                title = cells[1].get_text(strip=True)
        
        if not title:
            # 대체 방법: 페이지 타이틀에서 찾기
            page_title = soup.find('title')
            if page_title:
                title_text = page_title.get_text()
                # "제목 - 김포상공회의소" 형태에서 제목 부분만 추출
                if ' - ' in title_text:
                    title = title_text.split(' - ')[0].strip()
                else:
                    title = title_text.strip()
        
        # 메타 정보 추출 (날짜 등)
        meta_info = {}
        
        # 날짜 정보 추출
        date_pattern = r'\d{4}-\d{2}-\d{2}'
        date_match = re.search(date_pattern, html_content)
        if date_match:
            meta_info['date'] = date_match.group()
        
        # 본문 내용 추출
        content_sections = []
        
        # 본문이 포함된 테이블 셀 찾기 (GIMPOCCI 특화)
        # 보통 여러 행으로 구성된 테이블에서 본문이 포함된 셀을 찾음
        content_cells = soup.find_all('td')
        for cell in content_cells:
            cell_text = cell.get_text(strip=True)
            # 충분한 텍스트가 있고, 메타데이터가 아닌 경우
            if len(cell_text) > 50 and not re.match(r'^(제목|첨부파일|날짜|\d{4}-\d{2}-\d{2}).*', cell_text):
                content_sections.append(cell_text)
        
        # HTML을 마크다운으로 변환
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        
        if content_sections:
            content = '\n\n'.join(content_sections)
        else:
            # 전체 본문에서 불필요한 요소 제거 후 변환
            for unwanted in soup.find_all(['nav', 'header', 'footer', 'script', 'style']):
                unwanted.decompose()
            content = h.handle(html_content)
        
        # 첨부파일 추출
        attachments = self._extract_attachments(soup)
        
        return {
            'title': title,
            'content': content,
            'meta_info': meta_info,
            'attachments': attachments
        }
    
    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """첨부파일 링크 추출"""
        attachments = []
        
        # 첨부파일 섹션 찾기 - "첨부파일" 텍스트가 있는 셀
        attachment_header = soup.find('td', string=re.compile('첨부파일'))
        if attachment_header:
            # 첨부파일 목록이 있는 다음 셀 찾기
            attachment_cell = attachment_header.find_next_sibling('td')
            if not attachment_cell:
                # 같은 행의 다른 셀에서 찾기
                attachment_row = attachment_header.parent
                cells = attachment_row.find_all('td')
                if len(cells) > 1:
                    attachment_cell = cells[1]
            
            if attachment_cell:
                # 첨부파일 링크들 찾기
                links = attachment_cell.find_all('a')
                for link in links:
                    href = link.get('href', '')
                    filename_text = link.get_text(strip=True)
                    
                    if filename_text and href:
                        # 파일명과 크기 정보 분리
                        # 예: "파일명.hwp (109.5KB)" 형태
                        size_match = re.search(r'\(([^)]+)\)$', filename_text)
                        if size_match:
                            file_size = size_match.group(1)
                            filename = filename_text.replace(size_match.group(0), '').strip()
                        else:
                            filename = filename_text
                            file_size = ""
                        
                        # JavaScript 기반 다운로드 링크 처리
                        if href.startswith('javascript:'):
                            # JavaScript에서 실제 다운로드 URL 추출 시도
                            # 이 부분은 사이트별로 다를 수 있으므로 실제 테스트 필요
                            logger.warning(f"JavaScript 다운로드 링크: {filename}")
                            file_url = href  # 일단 원본 저장
                        else:
                            # 절대 URL 생성
                            file_url = urljoin(self.base_url, href)
                        
                        attachments.append({
                            'filename': filename,
                            'url': file_url,
                            'size': file_size
                        })
                        logger.debug(f"첨부파일 발견: {filename} ({file_size})")
        
        # 추가: 다른 패턴의 첨부파일 링크 찾기
        if not attachments:
            # .hwp, .pdf 등의 확장자를 가진 링크 찾기
            file_links = soup.find_all('a', href=re.compile(r'\.(hwp|pdf|doc|docx|xls|xlsx|ppt|pptx|zip|rar|jpg|png)$', re.I))
            for link in file_links:
                href = link.get('href')
                filename = link.get_text(strip=True) or os.path.basename(href)
                
                if href:
                    file_url = urljoin(self.base_url, href)
                    
                    attachments.append({
                        'filename': filename,
                        'url': file_url,
                        'size': ""
                    })
                    logger.debug(f"첨부파일 발견: {filename}")
        
        logger.info(f"총 {len(attachments)}개 첨부파일 발견")
        return attachments
    
    def download_file(self, file_url: str, save_path: str, filename: str = None) -> bool:
        """파일 다운로드 - JavaScript 링크 처리"""
        try:
            # JavaScript 링크인 경우 건너뛰기 (현재 구현 제한)
            if file_url.startswith('javascript:'):
                logger.warning(f"JavaScript 다운로드 링크는 현재 지원되지 않습니다: {filename}")
                return False
            
            # 기본 다운로드 로직 사용
            return super().download_file(file_url, save_path, filename)
            
        except Exception as e:
            logger.error(f"파일 다운로드 실패 {file_url}: {e}")
            return False
    
    def _get_page_announcements(self, page_num: int) -> List[Dict[str, Any]]:
        """페이지별 공고 목록 가져오기"""
        page_url = self.get_list_url(page_num)
        logger.info(f"페이지 {page_num} URL: {page_url}")
        
        response = self.get_page(page_url)
        if not response:
            logger.warning(f"페이지 {page_num} 응답을 가져올 수 없습니다")
            return []
        
        # 페이지가 에러 상태거나 잘못된 경우 감지
        if response.status_code >= 400:
            logger.warning(f"페이지 {page_num} HTTP 에러: {response.status_code}")
            return []
        
        announcements = self.parse_list_page(response.text)
        
        # 마지막 페이지 감지
        if not announcements and page_num > 1:
            logger.info(f"페이지 {page_num}에 공고가 없어 마지막 페이지로 판단됩니다")
        
        return announcements


    def __del__(self):
        """소멸자 - Selenium 리소스 정리"""
        self._close_selenium()


def test_gimpocci_scraper(pages=3):
    """GIMPOCCI 스크래퍼 테스트 - Selenium 기반"""
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    scraper = None
    try:
        scraper = EnhancedGIMPOCCIScraper()
        output_dir = "output/gimpocci"
        os.makedirs(output_dir, exist_ok=True)
        
        logger.info(f"GIMPOCCI 스크래퍼 테스트 시작 - {pages}페이지 (Selenium 기반)")
        scraper.scrape_pages(max_pages=pages, output_base=output_dir)
        logger.info("스크래핑 완료")
        
    except Exception as e:
        logger.error(f"스크래핑 중 오류: {e}")
    finally:
        if scraper:
            scraper._close_selenium()


if __name__ == "__main__":
    test_gimpocci_scraper(3)