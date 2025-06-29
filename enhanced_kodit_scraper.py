#!/usr/bin/env python3
"""
Enhanced KODIT (신용보증기금) 스크래퍼

KODIT 공지사항 게시판에서 공고를 수집하는 스크래퍼입니다.
JavaScript 기반 동적 사이트이므로 Playwright를 사용합니다.

URL: https://www.kodit.co.kr/kodit/na/ntt/selectNttList.do?mi=2638&bbsId=148
"""

import os
import re
import time
import json
import logging
from typing import List, Dict, Any
from urllib.parse import urljoin, unquote
from playwright.sync_api import sync_playwright, Page, Browser
from bs4 import BeautifulSoup
import requests
from enhanced_base_scraper import EnhancedBaseScraper

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedKoditScraper(EnhancedBaseScraper):
    """KODIT 전용 Enhanced 스크래퍼 - Playwright 기반"""
    
    def __init__(self):
        super().__init__()
        
        # KODIT 사이트 설정
        self.base_url = "https://www.kodit.co.kr"
        self.list_url = "https://www.kodit.co.kr/kodit/na/ntt/selectNttList.do?mi=2638&bbsId=148"
        
        # 사이트별 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 2
        
        # Playwright 관련 설정
        self.playwright = None
        self.browser = None
        self.page = None
        self.csrf_token = None
        
        # 기본 파라미터
        self.base_params = {
            'mi': '2638',
            'bbsId': '148'
        }
        
    def start_browser(self):
        """Playwright 브라우저 시작"""
        if self.playwright is None:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            self.page = self.browser.new_page()
            
            # User-Agent 설정
            self.page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            
            logger.info("Playwright 브라우저 시작됨")
            
    def stop_browser(self):
        """Playwright 브라우저 종료"""
        if self.page:
            self.page.close()
            self.page = None
        if self.browser:
            self.browser.close()
            self.browser = None
        if self.playwright:
            self.playwright.stop()
            self.playwright = None
        logger.info("Playwright 브라우저 종료됨")
            
    def get_list_url(self, page_num: int) -> str:
        """페이지별 URL 생성 (POST 방식이므로 기본 URL 반환)"""
        return self.list_url
        
    def navigate_to_page(self, page_num: int):
        """특정 페이지로 이동 (POST 요청)"""
        if page_num == 1:
            # 첫 페이지는 직접 접속
            self.page.goto(self.list_url)
            self.page.wait_for_load_state('networkidle')
            
            # CSRF 토큰 추출
            self.extract_csrf_token()
        else:
            # 2페이지 이상은 JavaScript 함수를 통해 이동
            try:
                # 페이지네이션 링크 클릭
                page_link = self.page.locator(f'a[href="javascript:goPaging({page_num})"]').first
                if page_link.is_visible():
                    page_link.click()
                else:
                    # 직접 JavaScript 실행
                    self.page.evaluate(f'goPaging({page_num})')
                
                self.page.wait_for_load_state('networkidle')
                time.sleep(self.delay_between_requests)
                
            except Exception as e:
                logger.error(f"페이지 {page_num} 이동 실패: {e}")
                raise
    
    def extract_csrf_token(self):
        """CSRF 토큰 추출"""
        try:
            # 페이지에서 CSRF 토큰 찾기
            csrf_input = self.page.locator('input[name="_csrf"]').first
            if csrf_input.is_visible():
                self.csrf_token = csrf_input.get_attribute('value')
                logger.info(f"CSRF 토큰 추출: {self.csrf_token[:20]}...")
            else:
                logger.warning("CSRF 토큰을 찾을 수 없음")
        except Exception as e:
            logger.error(f"CSRF 토큰 추출 실패: {e}")
    
    def _get_page_announcements(self, page_num: int) -> List[Dict[str, Any]]:
        """페이지별 공고 목록 가져오기 (Playwright 기반)"""
        logger.info(f"페이지 {page_num} 공고 목록 수집 중...")
        
        # 브라우저가 시작되지 않았으면 시작
        if self.page is None:
            self.start_browser()
        
        # 페이지 이동
        self.navigate_to_page(page_num)
        
        # 페이지 내용 가져오기
        html_content = self.page.content()
        
        # BeautifulSoup으로 파싱
        return self.parse_list_page(html_content)
        
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 게시판 테이블 찾기 (클래스명이 없으므로 caption으로 찾기)
        table = soup.find('table')
        if not table:
            logger.error("게시판 테이블을 찾을 수 없습니다")
            return announcements
            
        tbody = table.find('tbody')
        if not tbody:
            logger.error("테이블 본문을 찾을 수 없습니다")
            return announcements
            
        rows = tbody.find_all('tr')
        logger.info(f"발견된 행 수: {len(rows)}")
        
        for i, row in enumerate(rows):
            try:
                cells = row.find_all('td')
                if len(cells) < 4:
                    continue
                    
                # 번호 (첫 번째 셀)
                number_cell = cells[0]
                number = number_cell.get_text(strip=True)
                
                # 제목 (두 번째 셀)
                title_cell = cells[1]
                title_link = title_cell.find('a')
                if not title_link:
                    continue
                    
                title = title_link.get_text(strip=True)
                
                # 등록일 (세 번째 셀)
                date_cell = cells[2]
                date = date_cell.get_text(strip=True)
                
                # 조회수 (네 번째 셀)
                views_cell = cells[3]
                views = views_cell.get_text(strip=True)
                
                # 공고 일련번호 추출을 위해 onclick 속성이나 다른 방법 필요
                # JavaScript 링크이므로 나중에 상세 페이지 접근 시 처리
                
                announcement = {
                    'number': number,
                    'title': title,
                    'date': date,
                    'views': views,
                    'url': 'javascript:',  # JavaScript 링크
                    'row_index': i  # 행 인덱스 저장
                }
                
                announcements.append(announcement)
                logger.info(f"공고 추가: [{number}] {title}")
                
            except Exception as e:
                logger.error(f"행 {i} 파싱 실패: {e}")
                continue
                
        logger.info(f"총 {len(announcements)}개 공고 수집완료")
        return announcements
        
    def get_detail_content(self, announcement: Dict[str, Any]) -> Dict[str, Any]:
        """상세 페이지 내용 가져오기 (API 기반 개선)"""
        try:
            # 상세 페이지로 이동 (JavaScript 기반)
            row_index = announcement.get('row_index', 0)
            
            # 더 정확한 선택자로 제목 링크 찾기
            title_link = self.page.locator(f'table tbody tr:nth-child({row_index + 1}) td:nth-child(2) a').first
            
            # 다른 방법으로도 시도
            if not title_link.is_visible():
                title_link = self.page.locator(f'tr:nth-child({row_index + 1}) a').first
            
            # 게시글 번호 추출 (data-id 또는 다른 방법)
            ntt_sn = None
            try:
                if title_link.is_visible():
                    ntt_sn = title_link.get_attribute('data-id')
                    if not ntt_sn:
                        # onclick에서 추출 시도
                        onclick = title_link.get_attribute('onclick') or ''
                        match = re.search(r"'(\d+)'", onclick)
                        if match:
                            ntt_sn = match.group(1)
            except Exception as e:
                logger.debug(f"게시글 번호 추출 실패: {e}")
            
            if title_link.is_visible():
                # JavaScript 링크 클릭
                title_link.click()
                
                # 페이지 내용 변화 대기 (AJAX 처리 시간)
                self.page.wait_for_timeout(3000)  # 3초 대기
                time.sleep(self.delay_between_requests)
            else:
                logger.error(f"제목 링크를 찾을 수 없음: {announcement['title']}")
                # 링크를 찾지 못하면 최소한의 정보라도 저장
                return {
                    'content': f"# {announcement['title']}\n\n**번호**: {announcement.get('number', '')}\n**등록일**: {announcement.get('date', '')}\n**조회수**: {announcement.get('views', '')}\n\n상세 내용을 가져올 수 없습니다.",
                    'attachments': []
                }
            
            # 현재 URL 저장
            current_url = self.page.url
            announcement['url'] = current_url
            
            # 상세 페이지 내용 파싱
            html_content = self.page.content()
            detail_info = self.parse_detail_page(html_content)
            
            # 첨부파일 정보를 API로 가져오기 (ntt_sn이 있는 경우)
            if ntt_sn:
                try:
                    api_attachments = self.get_attachments_via_api(ntt_sn)
                    if api_attachments:
                        detail_info['attachments'] = api_attachments
                        logger.info(f"API를 통해 첨부파일 {len(api_attachments)}개 발견")
                except Exception as e:
                    logger.warning(f"API 첨부파일 가져오기 실패: {e}")
            
            # 목록 페이지로 돌아가기
            self.page.go_back()
            self.page.wait_for_load_state('networkidle')
            time.sleep(self.delay_between_requests)
            
            return detail_info
            
        except Exception as e:
            logger.error(f"상세 내용 가져오기 실패 - {announcement['title']}: {e}")
            return {
                'content': f"# {announcement['title']}\n\n상세 내용을 가져올 수 없습니다.",
                'attachments': []
            }
            
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출
        title_elem = soup.find('h3') or soup.find('h2') or soup.find('h1')
        title = title_elem.get_text(strip=True) if title_elem else "제목 없음"
        
        # 본문 내용 추출 (div 태그에서 본문 찾기)
        content_elem = None
        
        # 여러 div 중에서 본문이 있는 div 찾기
        all_divs = soup.find_all('div')
        for div in all_divs:
            div_text = div.get_text(strip=True)
            if len(div_text) > 100:  # 충분한 길이의 텍스트가 있는 div
                content_elem = div
                break
        
        if not content_elem:
            # 다른 선택자 시도
            content_elem = soup.find('div', id='content') or soup.find('div', class_='view-content')
        
        if content_elem:
            # HTML을 텍스트로 변환 (간단한 변환)
            content_text = self.simple_html_to_text(content_elem)
        else:
            content_text = "본문 내용을 찾을 수 없습니다."
            
        # 메타 정보 추출
        meta_info = self.extract_meta_info(soup)
        
        # 현재 URL 추가
        current_url = getattr(self.page, 'url', '') if self.page else ''
        
        # 첨부파일 추출
        attachments = self._extract_attachments(soup)
        
        # 마크다운 형식으로 조합
        markdown_content = f"# {title}\n\n"
        
        if meta_info:
            for key, value in meta_info.items():
                markdown_content += f"**{key}**: {value}\n"
            markdown_content += f"**원본 URL**: {current_url}\n\n"
        
        markdown_content += "---\n\n"
        markdown_content += content_text
        
        return {
            'content': markdown_content,
            'attachments': attachments
        }
        
    def extract_meta_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """메타 정보 추출"""
        meta_info = {}
        
        # ul 태그에서 작성자, 등록일 정보 추출
        info_list = soup.find('ul')
        if info_list:
            items = info_list.find_all('li')
            for item in items:
                item_text = item.get_text(strip=True)
                if '작성자' in item_text:
                    meta_info['작성자'] = item_text.replace('작성자', '').strip()
                elif '등록일' in item_text:
                    meta_info['등록일'] = item_text.replace('등록일', '').strip()
        
        return meta_info
        
    def simple_html_to_text(self, element) -> str:
        """HTML 요소를 간단한 텍스트로 변환"""
        # 단락 분리
        text = element.get_text(separator='\n\n', strip=True)
        
        # 과도한 공백 제거
        import re
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        
        return text
        
    def get_attachments_via_api(self, ntt_sn: str) -> List[Dict[str, Any]]:
        """API를 통한 첨부파일 정보 가져오기"""
        try:
            # Playwright에서 쿠키 가져오기
            cookies = {}
            for cookie in self.page.context.cookies():
                cookies[cookie['name']] = cookie['value']
            
            # 1. 권한 체크 API 호출
            check_url = f"{self.base_url}/kodit/na/ntt/checkCI.do"
            check_data = {'bi': '148', 'ns': ntt_sn}
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': self.page.url
            }
            
            check_response = requests.post(check_url, data=check_data, 
                                         cookies=cookies, headers=headers, 
                                         verify=self.verify_ssl, timeout=30)
            
            if check_response.status_code != 200:
                logger.warning(f"권한 체크 실패: {check_response.status_code}")
                return []
            
            try:
                check_result = check_response.json()
            except:
                logger.warning("권한 체크 응답이 JSON이 아님")
                return []
            
            if check_result.get('ca') != 'Y':
                logger.info(f"게시글 {ntt_sn}에 대한 접근 권한 없음")
                return []
            
            # 2. 첨부파일 목록 API 호출
            file_check_url = f"{self.base_url}/kodit/na/ntt/fileDownChk.do"
            file_params = {
                'mi': '2638',
                'bbsId': '148',
                'nttSn': ntt_sn
            }
            
            file_response = requests.get(file_check_url, params=file_params,
                                       cookies=cookies, headers=headers,
                                       verify=self.verify_ssl, timeout=30)
            
            if file_response.status_code != 200:
                logger.warning(f"첨부파일 체크 실패: {file_response.status_code}")
                return []
            
            try:
                file_data = file_response.json()
            except:
                logger.warning("첨부파일 응답이 JSON이 아님")
                return []
            
            # 3. 첨부파일 정보 처리
            attachments = []
            ntt_file_list = file_data.get('nttFileList', [])
            
            if not ntt_file_list:
                logger.debug(f"게시글 {ntt_sn}에 첨부파일 없음")
                return []
            
            for file_info in ntt_file_list:
                file_name = file_info.get('fileNm', 'unknown_file')
                dwld_url = file_info.get('dwldUrl', '')
                
                if dwld_url:
                    attachment = {
                        'filename': file_name,
                        'url': f"{self.base_url}/common/nttFileDownload.do",
                        'params': {'fileKey': dwld_url},
                        'type': 'api',
                        'cookies': cookies,
                        'headers': headers
                    }
                    attachments.append(attachment)
                    logger.debug(f"첨부파일 발견: {file_name}")
            
            return attachments
            
        except Exception as e:
            logger.error(f"API 첨부파일 가져오기 실패: {e}")
            return []
        
    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """첨부파일 정보 추출"""
        attachments = []
        
        # 첨부파일 영역 찾기
        attach_section = soup.find('div', class_='attach') or soup.find('div', class_='file-list')
        if not attach_section:
            # 다른 선택자 시도
            attach_section = soup.find('ul', class_='file-list') or soup.find('div', id='fileList')
        
        if attach_section:
            # 파일 링크 찾기
            file_links = attach_section.find_all('a', href=True)
            
            for link in file_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                if href and text:
                    # JavaScript 다운로드 함수 확인
                    if 'mfn_fileDownload' in href:
                        # fileKey 추출
                        match = re.search(r"mfn_fileDownload\('([^']+)'\)", href)
                        if match:
                            file_key = match.group(1)
                            file_url = f"/common/fileDownload.do?fileKey={file_key}"
                            full_url = urljoin(self.base_url, file_url)
                            
                            attachments.append({
                                'filename': text,
                                'url': full_url,
                                'type': 'javascript'
                            })
                    else:
                        # 직접 링크
                        full_url = urljoin(self.base_url, href)
                        attachments.append({
                            'filename': text,
                            'url': full_url,
                            'type': 'direct'
                        })
        
        logger.info(f"첨부파일 {len(attachments)}개 발견")
        return attachments
        
    def download_file(self, attachment: Dict[str, Any], save_dir: str, 
                     announcement: Dict[str, Any] = None, 
                     attachment_info: Dict[str, Any] = None) -> bool:
        """파일 다운로드 (API 첨부파일 지원)"""
        try:
            url = attachment['url']
            filename = attachment.get('filename', 'unknown_file')
            attachment_type = attachment.get('type', 'direct')
            
            # 파일명 정리
            clean_filename = self.sanitize_filename(filename)
            file_path = os.path.join(save_dir, clean_filename)
            
            # API 첨부파일 처리
            if attachment_type == 'api':
                # API에서 전달받은 쿠키와 헤더 사용
                cookies = attachment.get('cookies', {})
                headers = attachment.get('headers', {})
                params = attachment.get('params', {})
                
                response = requests.get(url, params=params, cookies=cookies, 
                                      headers=headers, stream=True, timeout=30, 
                                      verify=self.verify_ssl)
            else:
                # 기존 방식 (Playwright 쿠키 사용)
                cookies = {}
                for cookie in self.page.context.cookies():
                    cookies[cookie['name']] = cookie['value']
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Referer': self.page.url
                }
                
                response = requests.get(url, cookies=cookies, headers=headers, 
                                      stream=True, timeout=30, verify=self.verify_ssl)
            
            response.raise_for_status()
            
            # Content-Disposition에서 파일명 추출 시도
            content_disposition = response.headers.get('Content-Disposition', '')
            if content_disposition:
                extracted_filename = self.extract_filename_from_disposition(content_disposition)
                if extracted_filename:
                    clean_filename = self.sanitize_filename(extracted_filename)
                    file_path = os.path.join(save_dir, clean_filename)
            
            # 파일 저장
            os.makedirs(save_dir, exist_ok=True)
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(file_path)
            logger.info(f"파일 다운로드 완료: {clean_filename} ({file_size} bytes)")
            
            return True
            
        except Exception as e:
            logger.error(f"파일 다운로드 실패 - {filename}: {e}")
            return False
            
    def extract_filename_from_disposition(self, content_disposition: str) -> str:
        """Content-Disposition 헤더에서 파일명 추출"""
        try:
            # RFC 5987 형식 우선 처리
            rfc5987_match = re.search(r"filename\*=([^']*)'([^']*)'(.+)", content_disposition)
            if rfc5987_match:
                encoding, lang, filename = rfc5987_match.groups()
                try:
                    from urllib.parse import unquote
                    filename = unquote(filename, encoding=encoding or 'utf-8')
                    return filename
                except:
                    pass
            
            # 일반 filename 파라미터 처리
            filename_match = re.search(r'filename[^;=\n]*=([\'"]*)(.*?)\1', content_disposition)
            if filename_match:
                filename = filename_match.group(2)
                
                # 다양한 인코딩 시도
                for encoding in ['utf-8', 'euc-kr', 'cp949']:
                    try:
                        if encoding == 'utf-8':
                            decoded = filename.encode('latin-1').decode('utf-8')
                        else:
                            decoded = filename.encode('latin-1').decode(encoding)
                        
                        if decoded and not decoded.isspace():
                            return decoded.replace('+', ' ')
                    except:
                        continue
                        
                return filename.replace('+', ' ')
                
        except Exception as e:
            logger.debug(f"파일명 추출 실패: {e}")
            
        return None
            
    def process_announcement(self, announcement: Dict[str, Any], index: int, output_base: str = 'output') -> bool:
        """개별 공고 처리 - Playwright 전용"""
        try:
            # 파일명 안전화
            safe_title = self.sanitize_filename(announcement['title'])
            number = announcement.get('number', '0')
            # 번호가 숫자가 아닐 수 있으므로 처리
            try:
                num_int = int(number)
                folder_name = f"{num_int:0>3d}_{safe_title}"
            except (ValueError, TypeError):
                folder_name = f"{number}_{safe_title}"
            
            announcement_dir = os.path.join(output_base, folder_name)
            os.makedirs(announcement_dir, exist_ok=True)
            
            # 상세 내용 가져오기 (Playwright 방식)
            detail_info = self.get_detail_content(announcement)
            
            # 본문 저장
            content_file = os.path.join(announcement_dir, 'content.md')
            with open(content_file, 'w', encoding='utf-8') as f:
                f.write(detail_info['content'])
            
            # 첨부파일 처리
            attachments = detail_info.get('attachments', [])
            if attachments:
                attachments_dir = os.path.join(announcement_dir, 'attachments')
                os.makedirs(attachments_dir, exist_ok=True)
                
                for attachment in attachments:
                    success = self.download_file(attachment, attachments_dir, announcement)
                    if success:
                        # 파일 카운트는 base scraper에서 처리됨
                        pass
            
            logger.info(f"공고 처리 완료: {announcement['title']}")
            return True
            
        except Exception as e:
            logger.error(f"공고 처리 실패: {announcement['title']} - {e}")
            return False
    
    def scrape_pages(self, max_pages: int = 3, output_base: str = "output") -> Dict[str, Any]:
        """페이지 스크래핑 실행"""
        try:
            self.start_browser()
            result = super().scrape_pages(max_pages, output_base)
            return result
        finally:
            self.stop_browser()
            
    def __del__(self):
        """소멸자 - 브라우저 정리"""
        self.stop_browser()


def main():
    """메인 실행 함수"""
    scraper = EnhancedKoditScraper()
    
    try:
        # 3페이지까지 수집
        output_dir = "output/kodit"
        os.makedirs(output_dir, exist_ok=True)
        
        result = scraper.scrape_pages(max_pages=3, output_base=output_dir)
        
        print(f"\n✅ KODIT 스크래핑 완료!")
        print(f"수집된 공고: {result['total_announcements']}개")
        print(f"다운로드된 파일: {result['total_files']}개")
        print(f"성공률: {result['success_rate']:.1f}%")
        
    except Exception as e:
        print(f"❌ 스크래핑 실패: {e}")
    finally:
        scraper.stop_browser()


if __name__ == "__main__":
    main()