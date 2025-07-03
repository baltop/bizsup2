# -*- coding: utf-8 -*-
"""
한국보건산업진흥원(KOHI) 공지사항 스크래퍼 - Enhanced 버전
URL: https://www.kohi.or.kr/user/bbs/BD_selectBbsList.do?q_bbsCode=1013
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

try:
    from playwright.sync_api import sync_playwright, Page, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

logger = logging.getLogger(__name__)

class EnhancedKohiScraper(StandardTableScraper):
    """한국보건산업진흥원(KOHI) 전용 스크래퍼 - Enhanced 버전"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.kohi.or.kr"
        self.list_url = "https://www.kohi.or.kr/user/bbs/BD_selectBbsList.do?q_bbsCode=1013"
        
        # KOHI 사이트 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 2.0  # JavaScript 기반 사이트이므로 조금 더 여유
        
        # 공지사항 포함 수집 설정
        self.include_notices = True
        
        # Playwright 관련 설정
        self.playwright = None
        self.browser = None
        self.page = None
        
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
        
        logger.info("Enhanced KOHI 스크래퍼 초기화 완료")

    def get_list_url(self, page_num: int) -> str:
        """페이지별 목록 URL 생성"""
        if page_num == 1:
            return self.list_url
        return f"{self.list_url}&q_currPage={page_num}"

    def _init_playwright(self):
        """Playwright 초기화"""
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright가 설치되지 않았습니다. 'pip install playwright' 실행 후 'playwright install' 실행하세요.")
        
        if self.playwright is None:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=True)
            self.page = self.browser.new_page()
            
            # 페이지 설정
            self.page.set_default_timeout(self.timeout * 1000)
            logger.info("Playwright 브라우저 초기화 완료")

    def _close_playwright(self):
        """Playwright 정리"""
        if self.page:
            self.page.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        logger.info("Playwright 브라우저 정리 완료")

    def _get_page_announcements(self, page_num: int) -> List[Dict[str, Any]]:
        """페이지별 공고 목록 가져오기 - Playwright 방식으로 오버라이드"""
        try:
            self._init_playwright()
            
            # 페이지 이동
            url = self.get_list_url(page_num)
            logger.info(f"페이지 {page_num} 접속 중: {url}")
            
            self.page.goto(url, wait_until='networkidle')
            time.sleep(1)  # 추가 로딩 대기
            
            # HTML 가져오기
            html_content = self.page.content()
            return self.parse_list_page(html_content)
            
        except Exception as e:
            logger.error(f"페이지 {page_num} 요청 중 오류 발생: {e}")
            return []

    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱 - 테이블 기반"""
        announcements = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # KOHI 사이트는 테이블 구조 - tbody 내의 tr 요소들 찾기
            tbody = soup.find('tbody')
            if not tbody:
                logger.warning("tbody 요소를 찾을 수 없습니다")
                return announcements
            
            rows = tbody.find_all('tr')
            if not rows:
                logger.warning("테이블 행을 찾을 수 없습니다")
                return announcements
            
            logger.info(f"총 {len(rows)}개의 공고 행을 발견했습니다")
            
            for i, row in enumerate(rows):
                try:
                    cells = row.find_all('td')
                    if len(cells) < 6:  # 번호, 제목, 작성자, 등록일시, 조회수, 첨부
                        continue
                    
                    # 번호 (첫 번째 셀) - 공지사항 체크
                    number_cell = cells[0]
                    number = number_cell.get_text(strip=True)
                    is_notice = '공지' in number
                    
                    if is_notice:
                        number = "공지"
                    
                    # 제목 (두 번째 셀)
                    title_cell = cells[1]
                    link_elem = title_cell.find('a')
                    if not link_elem:
                        continue
                    
                    title = link_elem.get_text(strip=True)
                    
                    # JavaScript 함수에서 ID 추출
                    onclick = link_elem.get('onclick', '')
                    if 'opView' not in onclick:
                        continue
                    
                    # opView('20250306171911539') 형태에서 ID 추출
                    match = re.search(r"opView\('([^']+)'\)", onclick)
                    if not match:
                        continue
                    
                    announcement_id = match.group(1)
                    
                    # 상세 페이지 URL 구성 (추정)
                    detail_url = f"{self.base_url}/user/bbs/BD_selectBbs.do?q_bbsCode=1013&q_bbscttSn={announcement_id}"
                    
                    # 작성자 (세 번째 셀)
                    author = cells[2].get_text(strip=True)
                    
                    # 등록일시 (네 번째 셀)
                    date = cells[3].get_text(strip=True)
                    
                    # 조회수 (다섯 번째 셀)
                    views = cells[4].get_text(strip=True)
                    
                    # 첨부파일 여부 (여섯 번째 셀)
                    attachment_cell = cells[5]
                    has_attachment = bool(attachment_cell.find('img', src=re.compile('icon_file')))
                    
                    announcement = {
                        'number': number,
                        'title': title,
                        'url': detail_url,
                        'author': author,
                        'date': date,
                        'views': views,
                        'has_attachment': has_attachment,
                        'is_notice': is_notice,
                        'announcement_id': announcement_id
                    }
                    
                    announcements.append(announcement)
                    logger.info(f"공고 추가: [{number}] {title}")
                    
                except Exception as e:
                    logger.warning(f"테이블 행 {i+1} 파싱 중 오류: {e}")
                    continue
            
            logger.info(f"총 {len(announcements)}개의 공고를 파싱했습니다")
            
        except Exception as e:
            logger.error(f"목록 페이지 파싱 중 오류 발생: {e}")
        
        return announcements

    def get_page(self, url: str, **kwargs) -> Optional[object]:
        """상세 페이지 가져오기 - Playwright 사용"""
        try:
            # URL에서 announcement_id 추출
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            announcement_id = query_params.get('q_bbscttSn', [None])[0]
            
            if not announcement_id:
                logger.error(f"URL에서 announcement_id를 찾을 수 없습니다: {url}")
                return None
            
            # Playwright로 JavaScript 함수 실행
            if not self.page:
                self._init_playwright()
                self.page.goto(self.list_url, wait_until='networkidle')
            
            logger.info(f"JavaScript 함수 실행: opView('{announcement_id}')")
            
            # opView 함수 실행 (새 페이지로 이동)
            with self.page.expect_navigation():
                self.page.evaluate(f"opView('{announcement_id}')")
            
            time.sleep(1)  # 페이지 로딩 대기
            
            # HTML 반환을 위한 더미 response 객체 생성
            class PlaywrightResponse:
                def __init__(self, content, status_code=200, encoding='utf-8'):
                    self.text = content
                    self.status_code = status_code
                    self.encoding = encoding
                    self.headers = {'Content-Type': 'text/html; charset=utf-8'}
            
            html_content = self.page.content()
            return PlaywrightResponse(html_content)
            
        except Exception as e:
            logger.error(f"Playwright 페이지 가져오기 중 오류: {e}")
            return None

    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 제목 추출
            title = "제목 없음"
            title_selectors = [
                '.view_title h3',
                '.view_title',
                '.board_view .title',
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
            
            # 다양한 메타 정보 위치 시도
            info_section = soup.find('div', class_='board_view_info')
            if info_section:
                info_text = info_section.get_text()
                # 날짜 패턴 추출
                date_match = re.search(r'(\d{4}[-./]\d{1,2}[-./]\d{1,2})', info_text)
                if date_match:
                    date = date_match.group(1)
                # 조회수 패턴 추출
                views_match = re.search(r'조회\s*:?\s*(\d+)', info_text)
                if views_match:
                    views = views_match.group(1)
            
            # 본문 내용 추출
            content = ""
            content_selectors = [
                '.board_view_content',
                '.view_content', 
                '.content',
                '#content'
            ]
            
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    content = self.h.handle(str(content_elem))
                    break
            
            if not content:
                # 일반적인 div나 p 태그에서 내용 추출
                content_div = soup.find('div', class_=re.compile(r'content|view|board'))
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
            # KOHI 사이트의 첨부파일 패턴 찾기
            attachment_selectors = [
                'a[href*="ND_fileDownload"]',
                'a[onclick*="fileDownload"]',
                '.attach_file a',
                '.file_list a',
                '.board_file a'
            ]
            
            for selector in attachment_selectors:
                file_links = soup.select(selector)
                
                for link in file_links:
                    href = link.get('href', '')
                    onclick = link.get('onclick', '')
                    
                    # 다운로드 URL 추출
                    download_url = None
                    filename = link.get_text(strip=True)
                    
                    if href and 'ND_fileDownload' in href:
                        download_url = urljoin(self.base_url, href)
                    elif onclick and 'fileDownload' in onclick:
                        # JavaScript 함수에서 파라미터 추출
                        params_match = re.search(r"fileDownload\('([^']*)',\s*'([^']*)'\)", onclick)
                        if params_match:
                            file_sn, file_id = params_match.groups()
                            download_url = f"{self.base_url}/commons/file/ND_fileDownload.do?q_fileSn={file_sn}&q_fileId={file_id}"
                    
                    if download_url and filename:
                        # 파일명에서 아이콘 텍스트 제거
                        filename = re.sub(r'^\s*첨부파일\s*', '', filename)
                        filename = filename.strip()
                        
                        if filename:  # 빈 파일명이 아닌 경우만
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
        """파일 다운로드 - KOHI 특화 (Playwright 세션 활용)"""
        try:
            logger.info(f"파일 다운로드 시작: {file_url}")
            
            if not self.page:
                logger.error("Playwright 페이지가 초기화되지 않았습니다")
                return False
            
            # Playwright를 통해 쿠키 가져오기
            cookies = self.page.context.cookies()
            
            # requests 세션에 쿠키 설정
            for cookie in cookies:
                self.session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])
            
            # Referer 헤더 추가
            headers = self.session.headers.copy()
            headers['Referer'] = self.page.url
            
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

    def scrape_pages(self, max_pages: int = 3, output_base: str = "output") -> None:
        """페이지들을 스크래핑 - Playwright 정리 추가"""
        try:
            super().scrape_pages(max_pages, output_base)
        finally:
            # Playwright 정리
            self._close_playwright()


def main():
    """테스트용 메인 함수"""
    scraper = EnhancedKohiScraper()
    output_dir = "output/kohi"
    
    try:
        os.makedirs(output_dir, exist_ok=True)
        scraper.scrape_pages(max_pages=3, output_base=output_dir)
        print("✅ KOHI 스크래핑 완료")
        
    except KeyboardInterrupt:
        print("\n❌ 사용자에 의해 중단되었습니다")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()