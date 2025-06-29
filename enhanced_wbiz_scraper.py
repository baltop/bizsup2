#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
여성기업종합지원센터 Enhanced Scraper
Site: https://wbiz.or.kr/notice/biz.do
Type: JavaScript 기반 리스트 구조 (UL/LI)
Features: Playwright 기반, 한글 파일명 지원, JavaScript 함수 호출 처리
"""

import os
import sys
import re
import time
import logging
from urllib.parse import urljoin, unquote
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# 프로젝트 루트를 Python 경로에 추가
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from enhanced_base_scraper import StandardTableScraper

class EnhancedWbizScraper(StandardTableScraper):
    """여성기업종합지원센터 전용 스크래퍼 - Playwright 기반"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://wbiz.or.kr"
        self.list_url = "https://wbiz.or.kr/notice/biz.do"
        self.detail_url_template = "https://wbiz.or.kr/notice/bizDetail.do"
        
        # 사이트별 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1
        
        # Playwright 관련
        self.playwright = None
        self.browser = None
        self.page = None
        
        # 고정 파라미터
        self.bbs_id = "BBS_0002"
        
        # 로거 설정
        self.logger = logging.getLogger(self.__class__.__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
    def __enter__(self):
        """Context manager 진입"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        self.page = self.browser.new_page()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager 종료"""
        if self.page:
            self.page.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
    
    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 생성"""
        if page_num == 1:
            return f"{self.list_url}?bbsId={self.bbs_id}"
        else:
            return f"{self.list_url}?bbsId={self.bbs_id}&pageIndex={page_num}"
    
    def _get_page_announcements(self, page_num: int) -> List[Dict[str, Any]]:
        """Playwright를 사용한 페이지 공고 목록 가져오기"""
        list_url = self.get_list_url(page_num)
        
        try:
            self.logger.info(f"페이지 {page_num} 접속: {list_url}")
            
            # 페이지 접속
            self.page.goto(list_url, timeout=30000)
            self.page.wait_for_load_state("networkidle", timeout=30000)
            
            # HTML 가져오기
            html_content = self.page.content()
            
            # BeautifulSoup으로 파싱
            return self.parse_list_page(html_content)
            
        except PlaywrightTimeoutError:
            self.logger.error(f"페이지 {page_num} 타임아웃")
            return []
        except Exception as e:
            self.logger.error(f"페이지 {page_num} 처리 중 오류: {e}")
            return []
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """리스트 기반 HTML 파싱 (UL/LI 구조)"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # UL/LI 구조에서 공고 목록 찾기
        # 실제 구조에 맞게 선택자 조정
        notice_lists = soup.find_all('ul')
        
        for ul in notice_lists:
            items = ul.find_all('li')
            
            # 5개 항목 (번호, 구분, 제목, 첨부파일, 등록일)이 있는 ul 찾기
            if len(items) == 5:
                try:
                    # 번호 (첫 번째 li)
                    number_item = items[0]
                    number = number_item.get_text(strip=True)
                    
                    # "공지" 이미지나 텍스트 확인
                    if "공지" in number or number.lower() == "notice":
                        number = "공지"
                    elif not number or not number.replace(" ", ""):
                        continue  # 빈 번호는 건너뛰기
                    
                    # 구분 (두 번째 li)
                    category = items[1].get_text(strip=True)
                    
                    # 제목 (세 번째 li)
                    title_item = items[2]
                    title_link = title_item.find('a')
                    
                    if not title_link:
                        continue
                    
                    title = title_link.get_text(strip=True)
                    if not title:
                        continue
                    
                    # JavaScript 링크에서 nttId 추출 시도
                    onclick = title_link.get('onclick', '')
                    href = title_link.get('href', '')
                    
                    # nttId 추출 (WBIZ 전용 패턴)
                    ntt_id = None
                    for pattern in [
                        r"fnViewArticle\s*\(\s*['\"](\d+)['\"]",  # fnViewArticle('521', 'BBS_0002')
                        r"fnViewArticle\s*\(\s*(\d+)\s*,",        # fnViewArticle(521, 'BBS_0002')
                        r"nttId['\"]?\s*[:=]\s*['\"]?(\d+)",      # 일반적인 nttId 패턴
                        r"bizDetail\.do\?[^'\"]*nttId=(\d+)"      # URL에서 직접 추출
                    ]:
                        match = re.search(pattern, onclick + href)
                        if match:
                            ntt_id = match.group(1)
                            break
                    
                    if not ntt_id:
                        # nttId를 찾을 수 없으면 디버깅 정보 출력
                        self.logger.warning(f"nttId를 찾을 수 없음: {title}")
                        self.logger.debug(f"onclick: {onclick}")
                        self.logger.debug(f"href: {href}")
                        continue
                    
                    # 상세 페이지 URL 구성
                    detail_url = f"{self.detail_url_template}?bbsId={self.bbs_id}&nttId={ntt_id}"
                    
                    # 첨부파일 (네 번째 li)
                    attachment_item = items[3]
                    has_attachment = bool(attachment_item.find('a'))
                    
                    # 등록일 (다섯 번째 li)
                    date = items[4].get_text(strip=True)
                    
                    announcement = {
                        'number': number,
                        'title': title,
                        'category': category,
                        'date': date,
                        'url': detail_url,
                        'ntt_id': ntt_id,
                        'has_attachment': has_attachment
                    }
                    
                    announcements.append(announcement)
                    self.logger.info(f"공고 추가: [{number}] {title}")
                    
                except Exception as e:
                    self.logger.error(f"공고 파싱 중 오류: {e}")
                    continue
        
        self.logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
        return announcements
    
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 본문 내용 추출 (다양한 선택자 시도)
        content_selectors = [
            '.article-content',
            '.board-content',
            '.content',
            '[class*="content"]',
            '.view-content',
            '.detail-content'
        ]
        
        content = ""
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                content = content_elem.get_text(strip=True)
                break
        
        if not content:
            # 전체 본문에서 내용이 많은 div 찾기
            divs = soup.find_all('div')
            max_length = 0
            for div in divs:
                text = div.get_text(strip=True)
                if len(text) > max_length and len(text) > 100:
                    content = text
                    max_length = len(text)
        
        # 첨부파일 추출
        attachments = self._extract_attachments(soup)
        
        return {
            'content': content,
            'attachments': attachments
        }
    
    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """첨부파일 정보 추출 (JavaScript 함수 파라미터 분석)"""
        attachments = []
        
        # fnCommonDownFile 함수 호출 링크 찾기
        for link in soup.find_all('a'):
            onclick = link.get('onclick', '')
            href = link.get('href', '')
            
            # 상세 페이지에서는 4개 파라미터 사용: fnCommonDownFile(atchFileId, fileSn, bbsId, nttId)
            # 먼저 4개 파라미터 패턴 시도
            pattern_4 = r"fnCommonDownFile\s*\(\s*['\"]([^'\"]+)['\"],\s*['\"]([^'\"]+)['\"],\s*['\"]([^'\"]+)['\"],\s*['\"]([^'\"]+)['\"]\s*\)"
            match = re.search(pattern_4, onclick + href)
            
            if match:
                atch_file_id, file_sn, bbs_id, ntt_id = match.groups()
                filename = link.get_text(strip=True)
                
                attachment = {
                    'filename': filename,
                    'atch_file_id': atch_file_id,
                    'file_sn': file_sn,
                    'bbs_id': bbs_id,
                    'ntt_id': ntt_id,
                    'download_url': f"/front/fms/FileDown.do"
                }
                
                attachments.append(attachment)
                self.logger.info(f"첨부파일 발견: {filename} (atchFileId: {atch_file_id}, fileSn: {file_sn})")
                continue
            
            # 2개 파라미터 패턴도 시도 (목록 페이지용)
            pattern_2 = r"fnCommonDownFile\s*\(\s*['\"]([^'\"]+)['\"],\s*['\"]([^'\"]+)['\"]\s*\)"
            match = re.search(pattern_2, onclick + href)
            
            if match:
                atch_file_id, file_sn = match.groups()
                filename = link.get_text(strip=True)
                
                attachment = {
                    'filename': filename,
                    'atch_file_id': atch_file_id,
                    'file_sn': file_sn,
                    'download_url': f"/front/fms/FileDown.do"
                }
                
                attachments.append(attachment)
                self.logger.info(f"첨부파일 발견: {filename} (atchFileId: {atch_file_id}, fileSn: {file_sn})")
        
        return attachments
    
    def download_file(self, file_url: str, save_path: str, attachment_info: dict = None) -> bool:
        """첨부파일 다운로드 - WBIZ 전용 POST 요청 방식"""
        if not attachment_info:
            return super().download_file(file_url, save_path)
        
        try:
            # 1. CSRF 토큰 획득
            self.logger.debug("CSRF 토큰 획득 시작")
            csrf_name, csrf_token = self._get_csrf_token()
            self.logger.debug(f"획득한 CSRF: {csrf_name}={csrf_token}")
            if not csrf_name or not csrf_token:
                self.logger.error("CSRF 토큰을 획득할 수 없습니다.")
                return False
            
            # 2. Playwright 쿠키를 requests 세션에 복사
            self._sync_cookies_with_session()
            
            # 3. POST 요청 데이터 구성
            atch_file_id = attachment_info.get('atch_file_id')
            file_sn = attachment_info.get('file_sn')
            download_url = f"{self.base_url}/front/fms/FileDown.do"
            
            # POST 데이터 (JavaScript 함수와 동일하게 구성)
            post_data = {
                csrf_name: csrf_token,  # 동적 CSRF 이름 사용
                'atchFileId': atch_file_id,
                'fileSn': file_sn
            }
            
            # 추가 파라미터가 있으면 포함 (상세 페이지 다운로드의 경우)
            bbs_id = attachment_info.get('bbs_id')
            ntt_id = attachment_info.get('ntt_id')
            if bbs_id and ntt_id:
                post_data.update({
                    'bbsId': bbs_id,
                    'bIdx': ntt_id,  # JavaScript에서 bIdx로 전달됨
                    'fileCn': attachment_info.get('filename', '')  # 파일명
                })
            
            self.logger.info(f"파일 다운로드 시작: {download_url}")
            self.logger.info(f"POST 데이터: {post_data}")
            
            # 4. POST 요청으로 파일 다운로드
            response = self.session.post(
                download_url, 
                data=post_data,
                headers={
                    'Referer': self.page.url if self.page else self.base_url,
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': '*/*',
                    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                timeout=60, 
                stream=True
            )
            
            # 응답 확인
            if response.status_code != 200:
                self.logger.error(f"다운로드 실패: HTTP {response.status_code}")
                self.logger.error(f"응답 내용: {response.text[:500]}")
                return False
            
            # Content-Type 확인
            content_type = response.headers.get('content-type', '')
            if 'text/html' in content_type:
                self.logger.warning("HTML 응답 받음 - 인증 또는 권한 문제일 수 있음")
                self.logger.debug(f"응답 내용: {response.text[:1000]}")
                return False
            
            # 4. 디렉토리 생성
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # 5. 파일명 처리 (Content-Disposition에서 추출)
            final_save_path = self._extract_filename_from_response(response, save_path)
            
            # 6. 파일 저장
            with open(final_save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(final_save_path)
            self.logger.info(f"파일 다운로드 완료: {os.path.basename(final_save_path)} ({file_size:,} bytes)")
            
            return True
            
        except Exception as e:
            self.logger.error(f"파일 다운로드 실패: {e}")
            return False
    
    def _get_csrf_token(self) -> tuple:
        """현재 페이지에서 CSRF 토큰 이름과 값 획득"""
        try:
            # Playwright 페이지에서 CSRF 토큰 추출
            if self.page:
                self.logger.debug("Playwright 페이지에서 CSRF 토큰 추출 시도")
                # JavaScript로 토큰 이름과 값 가져오기
                csrf_data = self.page.evaluate("""() => {
                    const nameElem = document.getElementById('hdCsrfNm');
                    const tokenElem = document.getElementById('hdCsrfTk');
                    return {
                        name: nameElem ? nameElem.value : null,
                        token: tokenElem ? tokenElem.value : null
                    };
                }""")
                
                csrf_name = csrf_data.get('name')
                csrf_token = csrf_data.get('token')
                
                if csrf_name and csrf_token:
                    self.logger.debug(f"Playwright에서 CSRF 획득: {csrf_name}={csrf_token}")
                    return csrf_name, csrf_token
                else:
                    self.logger.debug("Playwright에서 CSRF 토큰을 찾을 수 없음")
            
            # 대안: requests로 페이지 재접속해서 토큰 획득  
            self.logger.debug("requests로 CSRF 토큰 획득 시도")
            response = self.session.get(
                f"{self.base_url}/notice/biz.do?bbsId={self.bbs_id}",
                verify=self.verify_ssl,
                timeout=30
            )
            
            self.logger.debug(f"CSRF 토큰 획득 요청 응답: {response.status_code}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                csrf_nm_input = soup.find('input', {'id': 'hdCsrfNm'})
                csrf_tk_input = soup.find('input', {'id': 'hdCsrfTk'})
                
                if csrf_nm_input and csrf_tk_input:
                    csrf_name = csrf_nm_input.get('value')
                    csrf_token = csrf_tk_input.get('value')
                    self.logger.debug(f"requests에서 CSRF 획득: {csrf_name}={csrf_token}")
                    return csrf_name, csrf_token
                
                self.logger.debug("requests로 CSRF 토큰을 찾을 수 없음")
            
            return None, None
            
        except Exception as e:
            self.logger.error(f"CSRF 토큰 획득 실패: {e}")
            return None, None
    
    def _sync_cookies_with_session(self):
        """Playwright 페이지의 쿠키를 requests 세션에 동기화"""
        try:
            if self.page:
                self.logger.debug("Playwright 쿠키를 requests 세션에 동기화 시작")
                cookies = self.page.context.cookies()
                
                for cookie in cookies:
                    if cookie.get('domain') in ['wbiz.or.kr', '.wbiz.or.kr']:
                        self.session.cookies.set(
                            name=cookie['name'],
                            value=cookie['value'],
                            domain=cookie.get('domain'),
                            path=cookie.get('path', '/'),
                            secure=cookie.get('secure', False)
                        )
                        self.logger.debug(f"쿠키 동기화: {cookie['name']}={cookie['value'][:20]}...")
                
                self.logger.debug(f"총 {len(cookies)}개 쿠키 동기화 완료")
        except Exception as e:
            self.logger.warning(f"쿠키 동기화 실패: {e}")  # 경고 레벨로 처리
    
    def _extract_filename_from_response(self, response, default_path):
        """응답 헤더에서 한글 파일명 추출"""
        content_disposition = response.headers.get('Content-Disposition', '')
        save_dir = os.path.dirname(default_path)
        
        if content_disposition:
            # RFC 5987 형식 처리
            rfc5987_match = re.search(r"filename\*=([^']*)'([^']*)'(.+)", content_disposition)
            if rfc5987_match:
                encoding, lang, filename = rfc5987_match.groups()
                try:
                    filename = unquote(filename, encoding=encoding or 'utf-8')
                    return os.path.join(save_dir, self.sanitize_filename(filename))
                except:
                    pass
            
            # 일반 filename 파라미터 처리
            filename_match = re.search(r'filename[^;=\n]*=([\'"]*)(.*?)\1', content_disposition)
            if filename_match:
                filename = filename_match.group(2)
                
                # 한글 파일명 디코딩 시도
                for encoding in ['utf-8', 'euc-kr', 'cp949']:
                    try:
                        if encoding == 'utf-8':
                            decoded = filename.encode('latin-1').decode('utf-8')
                        else:
                            decoded = filename.encode('latin-1').decode(encoding)
                        
                        if decoded and not decoded.isspace():
                            clean_filename = self.sanitize_filename(decoded.replace('+', ' '))
                            return os.path.join(save_dir, clean_filename)
                    except:
                        continue
        
        return default_path
    
    def save_announcement(self, announcement: dict, content: str, attachments: list, output_base: str):
        """공고 정보를 파일로 저장"""
        # 폴더명 생성 (번호_제목)
        folder_name = f"{announcement['number']}_{self.sanitize_filename(announcement['title'])}"
        folder_path = os.path.join(output_base, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        
        # 본문 내용을 markdown으로 저장
        content_path = os.path.join(folder_path, 'content.md')
        with open(content_path, 'w', encoding='utf-8') as f:
            f.write(f"# {announcement['title']}\n\n")
            f.write(f"**번호**: {announcement['number']}\n")
            f.write(f"**구분**: {announcement['category']}\n")
            f.write(f"**등록일**: {announcement['date']}\n")
            f.write(f"**첨부파일**: {'있음' if announcement['has_attachment'] else '없음'}\n\n")
            f.write("---\n\n")
            f.write(content)
            f.write(f"\n\n**원본 URL**: {announcement['url']}\n")
        
        self.logger.info(f"공고 저장 완료: {folder_name}")
    
    def _get_attachment_path(self, announcement: dict, attachment: dict, output_base: str) -> str:
        """첨부파일 저장 경로 생성"""
        folder_name = f"{announcement['number']}_{self.sanitize_filename(announcement['title'])}"
        attachment_dir = os.path.join(output_base, folder_name, "attachments")
        os.makedirs(attachment_dir, exist_ok=True)
        
        filename = self.sanitize_filename(attachment['filename'])
        return os.path.join(attachment_dir, filename)
    
    def sanitize_filename(self, filename: str) -> str:
        """파일명에서 유효하지 않은 문자 제거"""
        # Windows 및 Linux에서 사용할 수 없는 문자들 제거
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # 파일명 길이 제한 (200자)
        if len(filename) > 200:
            name, ext = os.path.splitext(filename)
            filename = name[:200-len(ext)] + ext
        
        return filename.strip()
    
    def _create_meta_info(self, announcement: Dict[str, Any]) -> str:
        """공고 메타 정보 생성"""
        meta_info = f"""# {announcement['title']}

## 공고 정보
- **번호**: {announcement.get('number', 'N/A')}
- **카테고리**: {announcement.get('category', 'N/A')}
- **등록일**: {announcement.get('date', 'N/A')}
- **원본 URL**: {announcement['url']}
- **첨부파일**: {'있음' if announcement.get('has_attachment', False) else '없음'}

## 공고 내용

"""
        return meta_info
    
    def scrape_pages(self, max_pages: int = 3, output_base: str = "output/wbiz"):
        """메인 스크래핑 실행 - Context Manager 사용"""
        self.logger.info(f"WBIZ 스크래핑 시작 - 최대 {max_pages}페이지")
        
        with self:  # Context manager 사용
            total_announcements = 0
            total_files = 0
            downloaded_files = 0
            
            for page_num in range(1, max_pages + 1):
                self.logger.info(f"\n=== 페이지 {page_num} 처리 시작 ===")
                
                # 페이지 공고 목록 가져오기
                announcements = self._get_page_announcements(page_num)
                
                if not announcements:
                    self.logger.warning(f"페이지 {page_num}에서 공고를 찾을 수 없습니다.")
                    break
                
                # 각 공고 상세 처리
                for announcement in announcements:
                    try:
                        # 상세 페이지 접속
                        detail_url = announcement['url']
                        self.page.goto(detail_url, timeout=30000)
                        self.page.wait_for_load_state("networkidle", timeout=30000)
                        
                        # 상세 내용 파싱
                        detail_html = self.page.content()
                        detail_data = self.parse_detail_page(detail_html)
                        
                        # 메타 정보 생성 및 공고 저장
                        announcement['content'] = detail_data['content']
                        announcement['attachments'] = detail_data['attachments']
                        
                        # 폴더 생성
                        folder_title = self.sanitize_filename(announcement['title'])[:100]
                        folder_name = f"{total_announcements+1:03d}_{folder_title}"
                        folder_path = os.path.join(output_base, folder_name)
                        os.makedirs(folder_path, exist_ok=True)
                        
                        # 메타 정보 생성
                        meta_info = self._create_meta_info(announcement)
                        
                        # 본문 저장
                        content_path = os.path.join(folder_path, 'content.md')
                        with open(content_path, 'w', encoding='utf-8') as f:
                            f.write(meta_info + detail_data['content'])
                        
                        self.logger.info(f"내용 저장 완료: {content_path}")
                        
                        total_announcements += 1
                        total_files += len(detail_data['attachments'])
                        
                        # 첨부파일 다운로드
                        for i, attachment in enumerate(detail_data['attachments'], 1):
                            filename = attachment.get('filename', f'attachment_{i}')
                            safe_filename = self.sanitize_filename(filename)
                            save_path = os.path.join(folder_path, safe_filename)
                            
                            success = self.download_file(
                                file_url=attachment['download_url'],
                                save_path=save_path,
                                attachment_info=attachment
                            )
                            if success:
                                downloaded_files += 1
                        
                        time.sleep(self.delay_between_requests)
                        
                    except Exception as e:
                        self.logger.error(f"공고 처리 실패 [{announcement['title']}]: {e}")
                        continue
                
                time.sleep(self.delay_between_requests)
            
            # 결과 요약
            success_rate = (downloaded_files / total_files * 100) if total_files > 0 else 0
            
            self.logger.info(f"\n{'='*50}")
            self.logger.info(f"✅ WBIZ 스크래핑 완료!")
            self.logger.info(f"수집된 공고: {total_announcements}개")
            self.logger.info(f"전체 파일: {total_files}개")
            self.logger.info(f"다운로드 성공: {downloaded_files}개")
            self.logger.info(f"다운로드 성공률: {success_rate:.1f}%")
            self.logger.info(f"{'='*50}")

def main():
    """테스트 실행"""
    scraper = EnhancedWbizScraper()
    output_dir = "output/wbiz"
    
    try:
        scraper.scrape_pages(max_pages=3, output_base=output_dir)
    except KeyboardInterrupt:
        print("\n스크래핑이 중단되었습니다.")
    except Exception as e:
        print(f"스크래핑 중 오류 발생: {e}")

if __name__ == "__main__":
    main()