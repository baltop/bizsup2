# -*- coding: utf-8 -*-
"""
AGRIX(농촌융복합산업지원센터) 스크래퍼 - Enhanced 버전
사이트: https://uni.agrix.go.kr/webportal/community/portalViewNoticeList.do
"""

import asyncio
import requests
from bs4 import BeautifulSoup
import os
import re
import logging
import time
import json
from urllib.parse import urljoin, urlparse, parse_qs, unquote
from typing import Dict, List, Any, Optional
from enhanced_base_scraper import EnhancedBaseScraper

# Playwright 임포트 (선택적)
try:
    from playwright.async_api import async_playwright, Page, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

logger = logging.getLogger(__name__)

class EnhancedAgrixScraper(EnhancedBaseScraper):
    """AGRIX 전용 스크래퍼 - JavaScript 기반 동적 사이트"""
    
    def __init__(self):
        super().__init__()
        
        # 기본 설정
        self.base_url = "https://uni.agrix.go.kr"
        self.list_url = "https://uni.agrix.go.kr/webportal/community/portalViewNoticeList.do"
        self.ajax_url = "https://uni.agrix.go.kr/webportal/community/selectPortalNoticeListAjax.do"
        self.detail_url = "https://uni.agrix.go.kr/webportal/community/portalViewNoticeDetail.do"
        
        # 사이트별 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 2
        
        # 중복 체크 활성화 및 파일명 설정
        self.enable_duplicate_check = True
        self.processed_titles_file = 'output/processed_titles_enhancedagrix.json'
        
        # Playwright 관련 설정
        self.use_playwright = PLAYWRIGHT_AVAILABLE
        self.browser = None
        self.page = None
        
        # 사이트별 헤더 설정
        self.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        })
        self.session.headers.update(self.headers)
        
        logger.info("AGRIX 스크래퍼 초기화 완료")
    
    async def initialize_browser(self):
        """Playwright 브라우저 초기화"""
        if not self.use_playwright:
            logger.error("Playwright가 설치되지 않았습니다")
            return False
        
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            
            # 다운로드 경로 설정
            import tempfile
            self.download_dir = tempfile.mkdtemp()
            
            context = await self.browser.new_context(
                accept_downloads=True
            )
            self.page = await context.new_page()
            
            # 타임아웃 설정
            self.page.set_default_timeout(30000)
            
            # 초기 페이지 방문하여 세션 설정
            await self.page.goto(self.list_url, wait_until='networkidle')
            await self.page.wait_for_timeout(2000)
            
            # 브라우저 쿠키를 requests 세션에 복사
            await self._sync_cookies_to_session()
            
            logger.info("Playwright 브라우저 초기화 완료")
            return True
            
        except Exception as e:
            logger.error(f"Playwright 브라우저 초기화 실패: {e}")
            return False
    
    async def _sync_cookies_to_session(self):
        """브라우저 쿠키를 requests 세션에 동기화"""
        try:
            cookies = await self.page.context.cookies()
            for cookie in cookies:
                self.session.cookies.set(
                    cookie['name'], 
                    cookie['value'], 
                    domain=cookie.get('domain', ''),
                    path=cookie.get('path', '/')
                )
            logger.debug(f"{len(cookies)}개 쿠키 동기화 완료")
        except Exception as e:
            logger.error(f"쿠키 동기화 실패: {e}")
    
    async def cleanup_browser(self):
        """Playwright 브라우저 정리"""
        try:
            if self.page:
                await self.page.close()
            if self.browser:
                await self.browser.close()
            if hasattr(self, 'playwright'):
                await self.playwright.stop()
            logger.info("Playwright 브라우저 정리 완료")
        except Exception as e:
            logger.error(f"브라우저 정리 중 오류: {e}")
    
    def get_list_url(self, page_num: int) -> str:
        """페이지 번호별 목록 URL 생성"""
        if page_num == 1:
            return f"{self.list_url}?currPage=1&textSrchVal=&BOARD_SNO=&selectSAUP_CD=&selectSearchOpt=SJT"
        else:
            return f"{self.list_url}?currPage={page_num}&textSrchVal=&BOARD_SNO=&selectSAUP_CD=&selectSearchOpt=SJT"
    
    async def parse_list_page_playwright(self, page_num: int) -> List[Dict[str, Any]]:
        """Playwright를 사용한 목록 페이지 파싱"""
        announcements = []
        
        try:
            # 페이지 로드
            url = self.get_list_url(page_num)
            await self.page.goto(url, wait_until='networkidle')
            
            # 페이지 로딩 대기
            await self.page.wait_for_timeout(3000)
            
            # 테이블 확인
            table = await self.page.query_selector('table')
            if not table:
                logger.warning("테이블을 찾을 수 없습니다")
                return announcements
            
            # tbody 내의 tr 요소들 찾기
            rows = await self.page.query_selector_all('table tbody tr')
            logger.info(f"발견된 행 수: {len(rows)}")
            
            for row in rows:
                try:
                    # 각 행의 셀들 가져오기
                    cells = await row.query_selector_all('td')
                    if len(cells) < 4:  # 번호, 제목, 등록일, 첨부
                        continue
                    
                    # 제목 셀에서 링크 찾기
                    title_cell = cells[1]  # 두 번째 셀이 제목
                    title_link = await title_cell.query_selector('a')
                    
                    if not title_link:
                        continue
                    
                    # 제목 추출
                    title = await title_link.inner_text()
                    title = title.strip()
                    
                    if not title:
                        continue
                    
                    # data 속성에서 파라미터 추출
                    board_sno = await title_link.get_attribute('data-boardsno')
                    curr_page = await title_link.get_attribute('data-currpage')
                    text_srch_val = await title_link.get_attribute('data-textsrchval')
                    select_saup_cd = await title_link.get_attribute('data-selectsaupcd')
                    select_search_opt = await title_link.get_attribute('data-selectsearchopt')
                    
                    if not board_sno:
                        continue
                    
                    # 공고 정보 구성
                    announcement = {
                        'title': title,
                        'board_sno': board_sno,
                        'curr_page': curr_page or '1',
                        'text_srch_val': text_srch_val or '',
                        'select_saup_cd': select_saup_cd or '',
                        'select_search_opt': select_search_opt or 'SJT',
                        'url': self.detail_url  # 실제 상세 페이지는 POST로 접근
                    }
                    
                    # 추가 메타데이터 추출
                    try:
                        # 번호
                        number_text = await cells[0].inner_text()
                        if number_text.strip().isdigit():
                            announcement['number'] = int(number_text.strip())
                        
                        # 등록일
                        date_text = await cells[2].inner_text()
                        if date_text.strip():
                            announcement['date'] = date_text.strip()
                        
                        # 첨부파일 여부 (4번째 컬럼)
                        if len(cells) > 3:
                            attachment_cell = cells[3]
                            attachment_img = await attachment_cell.query_selector('img')
                            announcement['has_attachment'] = attachment_img is not None
                        
                    except Exception as e:
                        logger.warning(f"메타데이터 추출 중 오류: {e}")
                    
                    announcements.append(announcement)
                    logger.debug(f"공고 추가: {title}")
                    
                except Exception as e:
                    logger.error(f"행 파싱 중 오류: {e}")
                    continue
            
            logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
            return announcements
            
        except Exception as e:
            logger.error(f"Playwright 목록 페이지 파싱 실패: {e}")
            return announcements
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """기본 requests를 사용한 목록 페이지 파싱 (폴백용)"""
        announcements = []
        
        try:
            # AJAX 요청으로 데이터 가져오기 시도
            ajax_data = {
                'currPage': '1',
                'textSrchVal': '',
                'BOARD_SNO': '',
                'selectSAUP_CD': '',
                'selectSearchOpt': 'SJT'
            }
            
            response = self.session.post(
                self.ajax_url,
                data=ajax_data,
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                rows = soup.find_all('tr')
                
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) < 4:
                        continue
                    
                    title_cell = cells[1]
                    title_link = title_cell.find('a')
                    
                    if title_link:
                        title = title_link.get_text(strip=True)
                        onclick = title_link.get('onclick', '')
                        
                        # data 속성에서 파라미터 추출 (폴백용)
                        board_sno = title_link.get('data-boardsno')
                        if board_sno:
                            announcement = {
                                'title': title,
                                'board_sno': board_sno,
                                'curr_page': title_link.get('data-currpage', '1'),
                                'text_srch_val': title_link.get('data-textsrchval', ''),
                                'select_saup_cd': title_link.get('data-selectsaupcd', ''),
                                'select_search_opt': title_link.get('data-selectsearchopt', 'SJT'),
                                'url': self.detail_url
                            }
                            announcements.append(announcement)
            
            logger.info(f"AJAX를 통해 {len(announcements)}개 공고 파싱 완료")
            return announcements
            
        except Exception as e:
            logger.error(f"AJAX 목록 페이지 파싱 실패: {e}")
            return announcements
    
    async def parse_detail_page_playwright(self, announcement: Dict[str, Any]) -> Dict[str, Any]:
        """Playwright를 사용한 상세 페이지 파싱"""
        result = {
            'content': '',
            'attachments': []
        }
        
        try:
            # 상세 페이지로 이동 (POST 요청 시뮬레이션)
            await self.page.goto(self.list_url, wait_until='networkidle')
            
            # 상세 페이지 POST 요청 시뮬레이션
            # AGRIX는 data 속성을 사용하는 다른 방식
            script = f"""
                // 폼 데이터 구성
                const form = document.createElement('form');
                form.method = 'POST';
                form.action = '{self.detail_url}';
                
                const params = {{
                    'BOARD_SNO': '{announcement["board_sno"]}',
                    'currPage': '{announcement["curr_page"]}',
                    'textSrchVal': '{announcement["text_srch_val"]}',
                    'selectSAUP_CD': '{announcement["select_saup_cd"]}',
                    'selectSearchOpt': '{announcement["select_search_opt"]}'
                }};
                
                for (const [key, value] of Object.entries(params)) {{
                    const input = document.createElement('input');
                    input.type = 'hidden';
                    input.name = key;
                    input.value = value;
                    form.appendChild(input);
                }}
                
                document.body.appendChild(form);
                form.submit();
            """
            
            await self.page.evaluate(script)
            await self.page.wait_for_timeout(3000)  # 페이지 로딩 대기
            
            # 제목 추출
            title_elem = await self.page.query_selector('h3, h2, .title')
            title = ""
            if title_elem:
                title = await title_elem.inner_text()
                title = title.strip()
            
            # 메타 정보 구성
            meta_info = []
            if title:
                meta_info.append(f"# {title}")
                meta_info.append("")
            
            # 상세 정보 추출
            info_list = await self.page.query_selector_all('ul li')
            for li in info_list:
                try:
                    text = await li.inner_text()
                    if ':' in text or '：' in text:
                        meta_info.append(f"**{text}**")
                except:
                    pass
            
            if meta_info:
                meta_info.append("")
                meta_info.append("---")
                meta_info.append("")
            
            # 본문 내용 추출
            content_parts = []
            
            # 다양한 방법으로 본문 찾기
            content_selectors = [
                'div.content',
                'div.detail_content',
                'div.board_content',
                '.content',
                'div p',
                'div'
            ]
            
            for selector in content_selectors:
                content_elem = await self.page.query_selector(selector)
                if content_elem:
                    content_text = await content_elem.inner_text()
                    if len(content_text.strip()) > 50:
                        content_parts.append(content_text.strip())
                        break
            
            # 첨부파일 추출
            attachments = await self._extract_attachments_playwright()
            
            # 결과 조합
            final_content = "\n".join(meta_info + content_parts)
            
            result = {
                'content': final_content,
                'attachments': attachments
            }
            
            logger.info(f"상세 페이지 파싱 완료 - 내용: {len(final_content)}자, 첨부파일: {len(attachments)}개")
            return result
            
        except Exception as e:
            logger.error(f"Playwright 상세 페이지 파싱 실패: {e}")
            return result
    
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """기본 상세 페이지 파싱 (폴백용)"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = {
            'content': '기본 파싱 방법으로는 JavaScript 기반 사이트의 완전한 파싱이 어렵습니다.',
            'attachments': []
        }
        
        return result
    
    async def _extract_attachments_playwright(self) -> List[Dict[str, Any]]:
        """Playwright를 사용한 첨부파일 추출"""
        attachments = []
        
        try:
            # 첨부파일 링크 찾기
            file_links = await self.page.query_selector_all('a[href*="javascript:fileDownloadCheck"]')
            
            for link in file_links:
                try:
                    href = await link.get_attribute('href')
                    if not href:
                        continue
                    
                    if 'fileDownloadCheck' in href:
                        # fileDownloadCheck('216','1','20241224') 형태에서 파라미터 추출
                        match = re.search(r"fileDownloadCheck\('([^']+)',\s*'([^']+)',\s*'([^']+)'\)", href)
                        if match:
                            board_sno = match.group(1)  # file_id -> board_sno
                            sno = match.group(2)        # file_seq -> sno
                            file_date = match.group(3)
                            
                            # 파일명 추출
                            filename = await link.inner_text()
                            filename = filename.strip()
                            
                            if not filename:
                                filename = f"attachment_{board_sno}_{sno}"
                            
                            # 실제 다운로드 URL (POST 방식)
                            download_url = f"{self.base_url}/webportal/backoffice/cmmn/fileDownLoad.do"
                            
                            attachment = {
                                'filename': filename,
                                'url': download_url,
                                'board_sno': board_sno,
                                'sno': sno,
                                'file_date': file_date,
                                'download_method': 'POST'  # POST 방식 표시
                            }
                            
                            attachments.append(attachment)
                            logger.debug(f"첨부파일 발견: {filename}")
                            
                except Exception as e:
                    logger.error(f"첨부파일 추출 중 오류: {e}")
                    continue
            
            logger.info(f"총 {len(attachments)}개 첨부파일 추출")
            return attachments
            
        except Exception as e:
            logger.error(f"첨부파일 추출 실패: {e}")
            return attachments
    
    async def download_file_with_browser(self, attachment_info: Dict[str, Any], save_path: str) -> bool:
        """브라우저를 사용한 파일 다운로드"""
        try:
            if not attachment_info:
                logger.error(f"첨부파일 정보가 없습니다: {save_path}")
                return False
            
            logger.info(f"브라우저 파일 다운로드 시작: {attachment_info.get('filename', 'unknown')}")
            
            # 다운로드 모니터링 설정
            downloaded_files = []
            
            async def handle_download(download):
                try:
                    # 다운로드 완료 대기
                    download_path = await download.path()
                    if download_path:
                        downloaded_files.append(download_path)
                        logger.info(f"다운로드 완료: {download_path}")
                except Exception as e:
                    logger.error(f"다운로드 처리 중 오류: {e}")
            
            self.page.on("download", handle_download)
            
            # JavaScript로 다운로드 실행
            board_sno = attachment_info.get('board_sno', '')
            sno = attachment_info.get('sno', '')
            file_date = attachment_info.get('file_date', '')
            
            script = f"""
                // fileDownloadCheck 함수 호출
                if (typeof fileDownloadCheck === 'function') {{
                    fileDownloadCheck('{board_sno}', '{sno}', '{file_date}');
                }} else {{
                    // 직접 cmmnFileDownLoad 호출
                    if (typeof cmmnFileDownLoad === 'function') {{
                        cmmnFileDownLoad('{board_sno}', '{sno}');
                    }} else {{
                        // 폼 직접 전송
                        const form = document.createElement('form');
                        form.method = 'POST';
                        form.action = '/webportal/backoffice/cmmn/fileDownLoad.do';
                        
                        const boardSnoInput = document.createElement('input');
                        boardSnoInput.type = 'hidden';
                        boardSnoInput.name = 'f_board_sno';
                        boardSnoInput.value = '{board_sno}';
                        form.appendChild(boardSnoInput);
                        
                        const snoInput = document.createElement('input');
                        snoInput.type = 'hidden';
                        snoInput.name = 'f_sno';
                        snoInput.value = '{sno}';
                        form.appendChild(snoInput);
                        
                        document.body.appendChild(form);
                        form.submit();
                    }}
                }}
            """
            
            await self.page.evaluate(script)
            
            # 다운로드 완료 대기 (최대 30초)
            for i in range(30):
                await self.page.wait_for_timeout(1000)
                if downloaded_files:
                    break
                logger.debug(f"다운로드 대기 중... {i+1}/30초")
            
            # 다운로드된 파일을 목적지로 이동
            if downloaded_files and os.path.exists(downloaded_files[0]):
                download_path = downloaded_files[0]
                
                # 디렉토리 생성
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                
                # 파일 이동
                import shutil
                shutil.move(download_path, save_path)
                
                file_size = os.path.getsize(save_path)
                logger.info(f"브라우저 다운로드 완료: {save_path} ({file_size:,} bytes)")
                return True
            else:
                logger.error(f"다운로드 파일을 찾을 수 없습니다: {attachment_info.get('filename', 'unknown')}")
                return False
                
        except Exception as e:
            logger.error(f"브라우저 파일 다운로드 실패: {e}")
            return False
    
    def download_file(self, url: str, save_path: str, attachment_info: Dict[str, Any] = None) -> bool:
        """파일 다운로드 - AGRIX 특화 (비동기 브라우저 다운로드 래퍼)"""
        try:
            # 비동기 함수를 동기적으로 호출하기 위한 헬퍼
            import asyncio
            
            # 현재 이벤트 루프가 있는지 확인
            try:
                loop = asyncio.get_running_loop()
                # 이미 이벤트 루프가 실행 중인 경우, create_task 사용
                return False  # 현재 구조에서는 동기 방식으로 처리 불가
            except RuntimeError:
                # 이벤트 루프가 없는 경우, 새로 생성
                return asyncio.run(self.download_file_with_browser(attachment_info, save_path))
                
        except Exception as e:
            logger.error(f"파일 다운로드 실패 {url}: {e}")
            return False
    
    async def _download_attachments_async(self, attachments: List[Dict[str, Any]], folder_path: str):
        """비동기 첨부파일 다운로드"""
        if not attachments:
            logger.info("첨부파일이 없습니다")
            return
        
        logger.info(f"{len(attachments)}개 첨부파일 다운로드 시작")
        attachments_folder = os.path.join(folder_path, 'attachments')
        os.makedirs(attachments_folder, exist_ok=True)
        
        for i, attachment in enumerate(attachments):
            try:
                # 파일명 추출 - 다양한 키 지원 (name, filename)
                file_name = attachment.get('filename') or attachment.get('name') or f"attachment_{i+1}"
                logger.info(f"  첨부파일 {i+1}: {file_name}")
                
                # 파일명 처리
                file_name = self.sanitize_filename(file_name)
                if not file_name or file_name.isspace():
                    file_name = f"attachment_{i+1}"
                
                file_path = os.path.join(attachments_folder, file_name)
                
                # 브라우저를 사용한 파일 다운로드
                success = await self.download_file_with_browser(attachment, file_path)
                if not success:
                    logger.warning(f"첨부파일 다운로드 실패: {file_name}")
                    
            except Exception as e:
                logger.error(f"첨부파일 {i+1} 처리 중 오류: {e}")
                continue
    
    async def scrape_pages_async(self, max_pages: int = 3, output_base: str = 'output'):
        """비동기 스크래핑 메인 로직"""
        if not await self.initialize_browser():
            logger.error("브라우저 초기화 실패 - 기본 requests 방식으로 진행")
            return self.scrape_pages(max_pages, output_base)
        
        try:
            logger.info(f"비동기 스크래핑 시작: 최대 {max_pages}페이지")
            
            announcement_count = 0
            processed_count = 0
            
            for page_num in range(1, max_pages + 1):
                logger.info(f"페이지 {page_num} 처리 중")
                
                try:
                    # 목록 가져오기 및 파싱
                    announcements = await self.parse_list_page_playwright(page_num)
                    
                    if not announcements:
                        logger.warning(f"페이지 {page_num}에 공고가 없습니다")
                        if page_num == 1:
                            logger.error("첫 페이지에 공고가 없습니다")
                        break
                    
                    logger.info(f"페이지 {page_num}에서 {len(announcements)}개 공고 발견")
                    
                    # 중복 체크 적용
                    filtered_announcements, should_stop = self.filter_new_announcements(announcements)
                    
                    if should_stop:
                        logger.info(f"중복 공고 {self.duplicate_threshold}개 연속 발견으로 조기 종료")
                        break
                    
                    if not filtered_announcements:
                        logger.info(f"페이지 {page_num}에 새로운 공고가 없습니다")
                        if page_num == 1:
                            logger.warning("첫 페이지에 새로운 공고가 없습니다")
                        break
                    
                    logger.info(f"페이지 {page_num}에서 {len(filtered_announcements)}개 새로운 공고 처리")
                    
                    # 각 새로운 공고 처리
                    for ann in filtered_announcements:
                        announcement_count += 1
                        processed_count += 1
                        await self.process_announcement_async(ann, announcement_count, output_base)
                    
                    # 페이지 간 대기
                    if page_num < max_pages:
                        await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"페이지 {page_num} 처리 중 오류: {e}")
                    break
            
            logger.info(f"비동기 스크래핑 완료: 총 {processed_count}개 공고 처리")
            
            # 처리된 제목들 저장
            self.save_processed_titles()
            
            return True
            
        finally:
            await self.cleanup_browser()
    
    async def process_announcement_async(self, announcement: Dict[str, Any], index: int, output_base: str = 'output'):
        """비동기 개별 공고 처리"""
        logger.info(f"공고 처리 중 {index}: {announcement['title']}")
        
        # 폴더 생성
        folder_title = self.sanitize_filename(announcement['title'])[:100]
        folder_name = f"{index:03d}_{folder_title}"
        
        if len(folder_name) > 200:
            folder_title = folder_title[:195]
            folder_name = f"{index:03d}_{folder_title}"
        
        folder_path = os.path.join(output_base, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        
        # 상세 페이지 파싱
        try:
            detail = await self.parse_detail_page_playwright(announcement)
            logger.info(f"상세 페이지 파싱 완료 - 내용길이: {len(detail['content'])}, 첨부파일: {len(detail['attachments'])}")
        except Exception as e:
            logger.error(f"상세 페이지 파싱 실패: {e}")
            detail = {
                'content': f"파싱 오류: {str(e)}",
                'attachments': []
            }
        
        # 메타 정보 생성
        meta_info = self._create_meta_info(announcement)
        
        # 본문 저장
        content_path = os.path.join(folder_path, 'content.md')
        with open(content_path, 'w', encoding='utf-8') as f:
            f.write(meta_info + detail['content'])
        
        logger.info(f"내용 저장 완료: {content_path}")
        
        # 첨부파일 다운로드 (비동기 방식)
        await self._download_attachments_async(detail['attachments'], folder_path)
        
        # 처리된 제목으로 추가
        self.add_processed_title(announcement['title'])
        
        # 요청 간 대기
        await asyncio.sleep(1)
    
    def _create_meta_info(self, announcement: Dict[str, Any]) -> str:
        """메타 정보 생성"""
        meta_lines = [f"# {announcement['title']}", ""]
        
        # 메타 정보 추가
        if announcement.get('number'):
            meta_lines.append(f"**번호**: {announcement['number']}")
        if announcement.get('date'):
            meta_lines.append(f"**등록일**: {announcement['date']}")
        if announcement.get('has_attachment'):
            meta_lines.append(f"**첨부파일**: {'있음' if announcement['has_attachment'] else '없음'}")
        
        meta_lines.extend([
            f"**Board SNO**: {announcement.get('board_sno', '')}",
            f"**페이지**: {announcement.get('curr_page', '')}",
            f"**검색 옵션**: {announcement.get('select_search_opt', '')}",
            f"**원본 URL**: {announcement['url']}",
            "",
            "---",
            ""
        ])
        
        return "\n".join(meta_lines)


def test_agrix_scraper(pages: int = 3):
    """AGRIX 스크래퍼 테스트"""
    print(f"AGRIX 스크래퍼 테스트 시작 ({pages}페이지)")
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('agrix_scraper.log', encoding='utf-8')
        ]
    )
    
    # 출력 디렉토리 설정
    output_dir = "output/agrix"
    os.makedirs(output_dir, exist_ok=True)
    
    # 스크래퍼 실행
    scraper = EnhancedAgrixScraper()
    
    async def run_scraper():
        try:
            if scraper.use_playwright:
                success = await scraper.scrape_pages_async(max_pages=pages, output_base=output_dir)
            else:
                success = scraper.scrape_pages(max_pages=pages, output_base=output_dir)
            
            if success:
                print(f"\n=== 스크래핑 완료 ===")
                print(f"결과 저장 위치: {output_dir}")
                
                # 결과 통계
                verify_results(output_dir)
            else:
                print("스크래핑 실패")
                
        except Exception as e:
            print(f"스크래핑 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
    
    # 비동기 실행
    asyncio.run(run_scraper())


def verify_results(output_dir: str):
    """결과 검증"""
    print(f"\n=== 결과 검증 ===")
    
    try:
        # 폴더 수 확인
        if not os.path.exists(output_dir):
            print(f"출력 디렉토리가 존재하지 않습니다: {output_dir}")
            return
        
        folders = [d for d in os.listdir(output_dir) if os.path.isdir(os.path.join(output_dir, d))]
        print(f"생성된 공고 폴더 수: {len(folders)}")
        
        # 각 폴더별 통계
        total_files = 0
        total_size = 0
        attachment_counts = []
        
        for folder in folders:
            folder_path = os.path.join(output_dir, folder)
            
            # content.md 확인
            content_file = os.path.join(folder_path, 'content.md')
            if os.path.exists(content_file):
                size = os.path.getsize(content_file)
                print(f"  {folder}: content.md ({size:,} bytes)")
            else:
                print(f"  {folder}: content.md 없음")
            
            # 첨부파일 확인
            attachments_dir = os.path.join(folder_path, 'attachments')
            if os.path.exists(attachments_dir):
                files = os.listdir(attachments_dir)
                attachment_counts.append(len(files))
                for file in files:
                    file_path = os.path.join(attachments_dir, file)
                    file_size = os.path.getsize(file_path)
                    total_files += 1
                    total_size += file_size
                    print(f"    첨부파일: {file} ({file_size:,} bytes)")
            else:
                attachment_counts.append(0)
        
        # 통계 요약
        print(f"\n=== 통계 요약 ===")
        print(f"총 공고 수: {len(folders)}")
        print(f"총 첨부파일 수: {total_files}")
        print(f"총 첨부파일 크기: {total_size:,} bytes ({total_size/1024/1024:.2f} MB)")
        if attachment_counts:
            print(f"평균 첨부파일 수: {sum(attachment_counts)/len(attachment_counts):.1f}")
            print(f"최대 첨부파일 수: {max(attachment_counts)}")
        
    except Exception as e:
        print(f"결과 검증 중 오류: {e}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='AGRIX 스크래퍼')
    parser.add_argument('--pages', type=int, default=3, help='스크래핑할 페이지 수 (기본값: 3)')
    parser.add_argument('--output', type=str, default='output/agrix', help='출력 디렉토리')
    
    args = parser.parse_args()
    
    test_agrix_scraper(args.pages)