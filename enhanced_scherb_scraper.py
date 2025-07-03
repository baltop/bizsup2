# -*- coding: utf-8 -*-
"""
산청한방약초축제(SCHERB) 공고 스크래퍼 - Enhanced 버전
URL: http://www.scherb.or.kr/bbs/board.php?bo_table=sub7_1&page=1
"""

import requests
import requests.adapters
from bs4 import BeautifulSoup
import os
import time
import re
from urllib.parse import urljoin, urlparse, unquote
import logging
from enhanced_base_scraper import EnhancedBaseScraper

logger = logging.getLogger(__name__)

class EnhancedScherbScraper(EnhancedBaseScraper):
    """산청한방약초축제 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        # 기본 설정
        self.base_url = "http://www.scherb.or.kr"
        self.list_url = "http://www.scherb.or.kr/bbs/board.php?bo_table=sub7_1&page=1"
        
        # 사이트별 특화 설정
        self.verify_ssl = False  # HTTP 사이트
        self.default_encoding = 'utf-8'
        self.timeout = 45  # 타임아웃 증가
        self.delay_between_requests = 1.5  # 요청 간 지연 단축
        self.delay_between_pages = 2  # 페이지 간 대기 시간 단축
        
        # 다운로드 성능 설정
        self.max_download_retries = 3
        self.download_timeout_multiplier = 2
        
        # SCHERB 특화 설정 - 일반적인 PHP 게시판
        self.use_playwright = False
        
        # 세션 초기화 - SCHERB 사이트에 맞는 헤더 설정
        self._initialize_session()
    
    def _initialize_session(self):
        """SCHERB 사이트용 세션 초기화 - 개선된 버전"""
        # 최신 Chrome 브라우저 헤더로 업데이트
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        })
        
        # Keep-Alive 연결 설정
        adapter = requests.adapters.HTTPAdapter(
            max_retries=3,
            pool_connections=10,
            pool_maxsize=20
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        try:
            # 다단계 세션 초기화
            logger.info("SCHERB 사이트 세션 초기화 중...")
            
            # 1. 홈페이지 방문
            response = self.session.get(self.base_url, verify=self.verify_ssl, timeout=self.timeout)
            if response.status_code == 200:
                logger.info(f"홈페이지 접속 성공 (쿠키 {len(self.session.cookies)}개 설정)")
            else:
                logger.warning(f"홈페이지 접속 경고: HTTP {response.status_code}")
            
            time.sleep(1)
            
            # 2. 게시판 목록 페이지 방문 (세션 컨텍스트 설정)
            board_response = self.session.get(self.list_url, verify=self.verify_ssl, timeout=self.timeout)
            if board_response.status_code == 200:
                logger.info(f"게시판 접속 성공 (총 쿠키 {len(self.session.cookies)}개)")
            else:
                logger.warning(f"게시판 접속 경고: HTTP {board_response.status_code}")
                
            logger.info("세션 초기화 완료")
            
        except Exception as e:
            logger.warning(f"세션 초기화 실패: {e}")
            logger.info("기본 세션으로 계속 진행합니다.")
    
    def get_list_url(self, page_num: int) -> str:
        """페이지별 목록 URL 생성"""
        return f"http://www.scherb.or.kr/bbs/board.php?bo_table=sub7_1&page={page_num}"
    
    def parse_list_page(self, html_content: str) -> list:
        """목록 페이지 파싱 - PHP 게시판 테이블 기반 구조"""
        announcements = []
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 게시글 링크 찾기 - board.php?bo_table=sub7_1&wr_id= 패턴
        detail_links = soup.find_all('a', href=re.compile(r'board\.php\?bo_table=sub7_1.*wr_id=\d+'))
        
        logger.info(f"공고 링크 {len(detail_links)}개 발견")
        
        for i, link in enumerate(detail_links):
            try:
                href = link.get('href', '')
                
                # 절대 URL 생성
                if href.startswith('http'):
                    detail_url = href
                else:
                    detail_url = urljoin(self.base_url, href)
                
                # wr_id 추출
                wr_id_match = re.search(r'wr_id=(\d+)', href)
                if not wr_id_match:
                    continue
                    
                wr_id = wr_id_match.group(1)
                
                # 링크 텍스트에서 제목 추출
                title = link.get_text(strip=True)
                
                # 제목이 너무 짧으면 부모 요소에서 찾기
                if len(title) < 5:
                    parent = link.parent
                    while parent and len(title) < 5:
                        parent_text = parent.get_text(strip=True)
                        if len(parent_text) > len(title) and len(parent_text) < 200:
                            title = parent_text
                            break
                        parent = parent.parent
                
                # 테이블 구조에서 추가 정보 추출
                table_row = link.find_parent('tr')
                category = "공지"
                date = ""
                
                if table_row:
                    cells = table_row.find_all(['td', 'th'])
                    if len(cells) >= 4:
                        # 일반적인 게시판 구조: 번호, 제목, 작성자, 날짜
                        for cell in cells:
                            cell_text = cell.get_text(strip=True)
                            # 날짜 패턴 찾기
                            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', cell_text)
                            if date_match:
                                date = date_match.group(1)
                                break
                
                # 제목 정리
                if not title or title.strip() == "":
                    title = f"공고_{wr_id}"
                
                # 제목에서 불필요한 부분 제거
                title = re.sub(r'\s+', ' ', title).strip()
                title = title.replace('\n', ' ').replace('\t', ' ')
                
                announcement = {
                    'number': wr_id,
                    'category': category,
                    'title': title,
                    'url': detail_url,
                    'date': date,
                    'attachment_count': 0  # 상세페이지에서 확인
                }
                
                announcements.append(announcement)
                logger.info(f"공고 추가: [{wr_id}] {title[:50]}...")
                
            except Exception as e:
                logger.error(f"공고 파싱 중 오류 (링크 {i}): {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
        return announcements
    
    def parse_detail_page(self, html_content: str) -> dict:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출
        title = ""
        
        # 게시글 제목 영역 찾기
        title_selectors = [
            '.bo_v_title',
            '.view_title', 
            '.board_title',
            'h1',
            'h2'
        ]
        
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                title = title_elem.get_text(strip=True)
                if len(title) > 5:
                    break
        
        # 타이틀 태그에서 추출
        if not title:
            page_title = soup.find('title')
            if page_title:
                title_text = page_title.get_text().strip()
                # 사이트명 제거
                if ' | ' in title_text:
                    title = title_text.split(' | ')[0].strip()
                else:
                    title = title_text
        
        if not title:
            title = "제목 없음"
        
        # 본문 내용 추출
        content = ""
        
        # 게시글 본문 영역 찾기
        content_selectors = [
            '.bo_v_con',
            '.view_content',
            '.board_content', 
            '.content',
            '#bo_v_con'
        ]
        
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem and len(content_elem.get_text(strip=True)) > 50:
                content = self.h.handle(str(content_elem))
                break
        
        # 본문이 없으면 가장 긴 텍스트 영역 찾기
        if len(content.strip()) < 50:
            all_divs = soup.find_all('div')
            max_text = ""
            for div in all_divs:
                div_text = div.get_text(strip=True)
                if len(div_text) > len(max_text) and len(div_text) > 100:
                    # 하위 div가 많지 않은 영역
                    sub_divs = div.find_all('div')
                    if len(sub_divs) < 5:
                        max_text = div_text
            
            if max_text:
                content = max_text
        
        # 날짜 추출
        date = ""
        date_patterns = [
            r'(\d{4}-\d{2}-\d{2})',
            r'(\d{4}\.\d{2}\.\d{2})',
            r'(\d{2}-\d{2}-\d{2})'
        ]
        
        page_text = soup.get_text()
        for pattern in date_patterns:
            date_match = re.search(pattern, page_text)
            if date_match:
                date = date_match.group(1)
                break
        
        # 첨부파일 추출
        attachments = self._extract_attachments(soup)
        
        return {
            'title': title,
            'content': content,
            'date': date,
            'author': "",
            'attachments': attachments
        }
    
    def _extract_attachments(self, soup: BeautifulSoup) -> list:
        """첨부파일 링크 추출 - 중복 제거 개선"""
        attachments = []
        seen_urls = set()  # 중복 URL 제거용
        
        # PHP 게시판 첨부파일 패턴들 (SCHERB 특화)
        attachment_patterns = [
            'a[href*="download.php"]',
            'a[href*="file_download.php"]'
        ]
        
        for pattern in attachment_patterns:
            download_links = soup.select(pattern)
            
            for link in download_links:
                try:
                    href = link.get('href', '')
                    if not href:
                        continue
                    
                    # download.php 링크만 처리
                    if 'download.php' not in href:
                        continue
                    
                    # 절대 URL 생성
                    if href.startswith('http'):
                        file_url = href
                    else:
                        file_url = urljoin(self.base_url, href)
                    
                    # 중복 URL 체크
                    if file_url in seen_urls:
                        continue
                    seen_urls.add(file_url)
                    
                    # 파일명 추출 (다단계 방식)
                    filename = self._extract_filename_from_link(link, href)
                    
                    # 파일 크기 정보 추출 (가능한 경우)
                    file_size_info = self._extract_file_size_info(link)
                    
                    attachment = {
                        'filename': filename,
                        'url': file_url,
                        'size_info': file_size_info
                    }
                    
                    attachments.append(attachment)
                    size_display = f"({file_size_info})" if file_size_info else ""
                    logger.info(f"첨부파일 발견: {filename}{size_display} - {file_url}")
                    
                except Exception as e:
                    logger.error(f"첨부파일 추출 중 오류: {e}")
                    continue
        
        logger.info(f"총 {len(attachments)}개 첨부파일 추출 완료")
        return attachments
    
    def _extract_filename_from_link(self, link, href: str) -> str:
        """링크에서 파일명 추출 (한글 디코딩 개선)"""
        filename = ""
        
        # 1. 링크 텍스트에서 파일명 추출 (우선순위 1)
        link_text = link.get_text(strip=True)
        if link_text and any(ext in link_text.lower() for ext in ['.pdf', '.hwp', '.doc', '.xls', '.ppt', '.zip']):
            # URL 인코딩된 텍스트 디코딩 시도
            try:
                if '%' in link_text:
                    decoded_text = unquote(link_text, encoding='utf-8')
                    filename = decoded_text
                else:
                    filename = link_text
            except:
                filename = link_text
        
        # 2. title 속성에서 파일명 추출
        if not filename:
            title = link.get('title', '').strip()
            if title and any(ext in title.lower() for ext in ['.pdf', '.hwp', '.doc', '.xls', '.ppt', '.zip']):
                try:
                    if '%' in title:
                        decoded_title = unquote(title, encoding='utf-8')
                        filename = decoded_title
                    else:
                        filename = title
                except:
                    filename = title
        
        # 3. href에서 파일명 추출
        if not filename:
            # URL 파라미터에서 파일명 찾기
            filename_match = re.search(r'file[_=]([^&\s]+)', href)
            if filename_match:
                try:
                    raw_filename = filename_match.group(1)
                    filename = unquote(raw_filename, encoding='utf-8')
                except:
                    filename = filename_match.group(1)
        
        # 4. 부모/형제 요소에서 파일명 찾기
        if not filename:
            # 부모 요소 검색
            parent = link.parent
            if parent:
                parent_text = parent.get_text()
                file_match = re.search(r'([^/\\:*?"<>|\n\t]+\.(?:pdf|hwp|doc|docx|xls|xlsx|ppt|pptx|zip|rar))', parent_text, re.IGNORECASE)
                if file_match:
                    candidate_filename = file_match.group(1).strip()
                    # URL 인코딩된 파일명 디코딩 시도
                    try:
                        if '%' in candidate_filename:
                            filename = unquote(candidate_filename, encoding='utf-8')
                        else:
                            filename = candidate_filename
                    except:
                        filename = candidate_filename
            
            # 형제 요소 검색
            if not filename:
                next_sibling = link.next_sibling
                if next_sibling and hasattr(next_sibling, 'get_text'):
                    sibling_text = next_sibling.get_text(strip=True)
                    if sibling_text and any(ext in sibling_text.lower() for ext in ['.pdf', '.hwp', '.doc', '.xls', '.ppt', '.zip']):
                        filename = sibling_text
        
        # 5. 기본 파일명 생성
        if not filename:
            # wr_id에서 파일명 생성
            wr_id_match = re.search(r'wr_id=(\d+)', href)
            no_match = re.search(r'no=(\d+)', href)
            wr_id = wr_id_match.group(1) if wr_id_match else "unknown"
            no = no_match.group(1) if no_match else "0"
            filename = f"첨부파일_{wr_id}_{no}.file"
        
        # 파일명 정리
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = re.sub(r'\s+', ' ', filename).strip()
        
        # 파일명이 너무 길면 자르기
        if len(filename) > 100:
            name, ext = os.path.splitext(filename)
            filename = name[:90] + ext
        
        return filename
    
    def _extract_file_size_info(self, link) -> str:
        """링크 주변에서 파일 크기 정보 추출"""
        try:
            # 링크 텍스트에서 크기 정보 찾기
            link_text = link.get_text()
            size_patterns = [
                r'(\d+(?:\.\d+)?\s*[KMGT]?B)',
                r'\((\d+(?:\.\d+)?\s*[KMGT]?B)\)',
                r'(\d+\.\d+[KMGT]?B)',
                r'(\d+[KMGT]?B)'
            ]
            
            for pattern in size_patterns:
                match = re.search(pattern, link_text, re.IGNORECASE)
                if match:
                    return match.group(1)
            
            # 부모 요소에서 크기 정보 찾기
            parent = link.parent
            if parent:
                parent_text = parent.get_text()
                for pattern in size_patterns:
                    match = re.search(pattern, parent_text, re.IGNORECASE)
                    if match:
                        return match.group(1)
            
        except Exception:
            pass
        
        return ""
    
    def download_file(self, file_url: str, save_path: str) -> bool:
        """파일 다운로드 - SCHERB 특화 버전 (개선된 세션 관리)"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                logger.info(f"파일 다운로드 시도 {attempt + 1}/{max_retries}: {file_url}")
                
                # 1. 세션 갱신을 위한 다단계 접근
                wr_id_match = re.search(r'wr_id=(\d+)', file_url)
                page_match = re.search(r'page=(\d+)', file_url)
                
                if wr_id_match:
                    wr_id = wr_id_match.group(1)
                    page_num = page_match.group(1) if page_match else "1"
                    
                    # A. 먼저 목록 페이지 방문 (세션 컨텍스트 설정)
                    list_url = f"{self.base_url}/bbs/board.php?bo_table=sub7_1&page={page_num}"
                    logger.debug(f"목록 페이지 방문: {list_url}")
                    list_response = self.session.get(list_url, verify=self.verify_ssl, timeout=self.timeout)
                    time.sleep(0.5)
                    
                    # B. 그 다음 상세페이지 방문 (게시글 읽기 권한 확보)
                    detail_url = f"{self.base_url}/bbs/board.php?bo_table=sub7_1&wr_id={wr_id}&page={page_num}"
                    logger.debug(f"상세페이지 방문: {detail_url}")
                    detail_response = self.session.get(detail_url, verify=self.verify_ssl, timeout=self.timeout)
                    time.sleep(0.5)
                    
                    # C. 세션 쿠키 확인
                    session_cookies = self.session.cookies
                    logger.debug(f"현재 쿠키 수: {len(session_cookies)}")
                
                # 2. 다운로드 시 완전한 브라우저 헤더 모방
                download_headers = {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Accept-Encoding': 'gzip, deflate',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'same-origin',
                    'Sec-Fetch-User': '?1',
                    'Upgrade-Insecure-Requests': '1',
                    'Referer': detail_url if wr_id_match else f"{self.base_url}/bbs/board.php?bo_table=sub7_1"
                }
                
                # 기존 헤더 백업 및 적용
                original_headers = self.session.headers.copy()
                self.session.headers.update(download_headers)
                
                # 3. 다운로드 실행
                response = self.session.get(file_url, timeout=self.timeout * 2, verify=self.verify_ssl, stream=True)
                
                # 헤더 복원
                self.session.headers = original_headers
                
                # 4. 응답 상태 확인
                response.raise_for_status()
                
                # 5. Content-Type 1차 검증
                content_type = response.headers.get('Content-Type', '').lower()
                content_length = response.headers.get('Content-Length')
                content_disposition = response.headers.get('Content-Disposition', '')
                
                logger.debug(f"Content-Type: {content_type}")
                logger.debug(f"Content-Length: {content_length}")
                logger.debug(f"Content-Disposition: {content_disposition}")
                
                # 6. HTML 에러페이지 감지 (다중 검증)
                first_chunk = next(response.iter_content(chunk_size=2048), b'')
                
                # A. Content-Type이 text/html인 경우
                if 'text/html' in content_type:
                    # B. HTML 문서 시작 태그 확인
                    html_indicators = [b'<!doctype html', b'<html', b'<HTML', b'<!DOCTYPE html']
                    is_html = any(indicator in first_chunk.lower() for indicator in html_indicators)
                    
                    if is_html:
                        # C. 한국어 에러 메시지 확인
                        try:
                            text_content = first_chunk.decode('utf-8', errors='ignore')
                            error_keywords = [
                                '잘못된 접근', '권한이 없습니다', '파일을 찾을 수 없습니다', 
                                'access denied', 'permission denied', 'file not found',
                                '오류안내 페이지', 'error page', '<title>오류안내 페이지',  # SCHERB 특화 에러 키워드
                                '산청한방약초축제</title>', 'scherb.or.kr'  # 사이트 메인페이지로 리다이렉트된 경우
                            ]
                            is_error = any(keyword in text_content for keyword in error_keywords)
                            
                            if is_error:
                                logger.warning(f"HTML 에러페이지 감지: {file_url}")
                                logger.debug(f"에러 내용 미리보기: {text_content[:300]}")
                                
                                # 재시도 전 대기
                                if attempt < max_retries - 1:
                                    wait_time = (attempt + 1) * 2
                                    logger.info(f"{wait_time}초 후 재시도...")
                                    time.sleep(wait_time)
                                    continue
                                else:
                                    logger.error(f"다운로드 실패 - 최대 재시도 횟수 초과: {file_url}")
                                    return False
                        except:
                            pass
                
                # 7. 파일 크기 검증 (알려진 에러 페이지 크기 체크)
                known_error_sizes = [4527, 4500, 4600, 2048]  # 알려진 에러 페이지 크기들 (2048 추가)
                if content_length and int(content_length) in known_error_sizes:
                    logger.warning(f"의심스러운 파일 크기 감지: {content_length} bytes")
                    if attempt < max_retries - 1:
                        time.sleep((attempt + 1) * 2)
                        continue
                
                # 8. 파일명 추출 및 경로 설정
                actual_filename = self._extract_filename_from_response(response, save_path)
                
                # 디렉토리 생성 확보
                os.makedirs(os.path.dirname(actual_filename), exist_ok=True)
                
                # 9. 스트리밍 다운로드 (첫 번째 청크 포함)
                total_size = 0
                with open(actual_filename, 'wb') as f:
                    # 첫 번째 청크 쓰기
                    if first_chunk:
                        f.write(first_chunk)
                        total_size += len(first_chunk)
                    
                    # 나머지 청크들 쓰기
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            total_size += len(chunk)
                
                # 10. 다운로드 후 검증
                actual_file_size = os.path.getsize(actual_filename)
                
                # A. 크기 이상 여부 체크 (확장)
                known_error_sizes = [4527, 4500, 4600, 2048]  # 알려진 에러 페이지 크기들
                if actual_file_size in known_error_sizes:
                    logger.error(f"다운로드된 파일이 알려진 에러 페이지 크기: {actual_file_size} bytes")
                    os.remove(actual_filename)  # 잘못된 파일 삭제
                    if attempt < max_retries - 1:
                        time.sleep((attempt + 1) * 2)
                        continue
                    return False
                
                # B. SCHERB 특화 HTML 에러페이지 상세 검증
                if actual_file_size < 5000:  # 5KB 미만 파일들은 모두 검증
                    with open(actual_filename, 'rb') as f:
                        content_sample = f.read(500)  # 더 많은 내용 읽기
                        
                        # HTML 문서인지 확인
                        if b'<html' in content_sample.lower() or b'<!doctype' in content_sample.lower():
                            content_text = content_sample.decode('utf-8', errors='ignore')
                            
                            # SCHERB 특화 에러페이지 키워드 체크
                            scherb_error_indicators = [
                                '오류안내 페이지',
                                '산청한방약초축제</title>',
                                'scherb.or.kr',
                                'og:title" content="산청한방약초축제"',
                                'meta property="og:site_name" content="산청한방약초축제"'
                            ]
                            
                            if any(indicator in content_text for indicator in scherb_error_indicators):
                                logger.error(f"SCHERB 에러페이지 감지: {actual_filename}")
                                logger.debug(f"에러 내용: {content_text[:200]}")
                                os.remove(actual_filename)
                                if attempt < max_retries - 1:
                                    time.sleep((attempt + 1) * 2)
                                    continue
                                return False
                
                # C. 성공
                logger.info(f"파일 다운로드 완료: {actual_filename} ({actual_file_size:,} bytes)")
                return True
                
            except requests.exceptions.RequestException as e:
                logger.error(f"다운로드 요청 오류 {attempt + 1}/{max_retries}: {e}")
                if attempt < max_retries - 1:
                    time.sleep((attempt + 1) * 3)
                    continue
            except Exception as e:
                logger.error(f"다운로드 예외 오류 {attempt + 1}/{max_retries}: {e}")
                if attempt < max_retries - 1:
                    time.sleep((attempt + 1) * 3)
                    continue
        
        logger.error(f"파일 다운로드 최종 실패: {file_url}")
        return False
    
    def _extract_filename_from_response(self, response, default_path):
        """응답 헤더에서 파일명 추출 및 한글 처리 (개선된 버전)"""
        save_dir = os.path.dirname(default_path)
        original_filename = os.path.basename(default_path)
        
        content_disposition = response.headers.get('Content-Disposition', '')
        
        if content_disposition:
            # RFC 5987 형식 우선 처리 (filename*=UTF-8''encoded_name)
            rfc5987_match = re.search(r"filename\*=([^']*)'([^']*)'(.+)", content_disposition)
            if rfc5987_match:
                encoding, lang, encoded_filename = rfc5987_match.groups()
                try:
                    # URL 디코딩 후 지정된 인코딩으로 디코딩
                    decoded_filename = unquote(encoded_filename, encoding=encoding or 'utf-8')
                    clean_filename = self.sanitize_filename(decoded_filename)
                    return os.path.join(save_dir, clean_filename)
                except Exception as e:
                    logger.debug(f"RFC 5987 디코딩 실패: {e}")
            
            # 일반 filename 파라미터 처리
            filename_match = re.search(r'filename[^;=\n]*=([\'"]*)(.*?)\1', content_disposition)
            if filename_match:
                raw_filename = filename_match.group(2)
                
                # 한글 파일명 다단계 디코딩 시도
                decodings_to_try = [
                    # URL 인코딩된 경우
                    lambda x: unquote(x, encoding='utf-8'),
                    lambda x: unquote(x, encoding='euc-kr'),
                    lambda x: unquote(x, encoding='cp949'),
                    # Latin-1 → 실제 인코딩
                    lambda x: x.encode('latin-1').decode('utf-8'),
                    lambda x: x.encode('latin-1').decode('euc-kr'),
                    lambda x: x.encode('latin-1').decode('cp949'),
                    # 원본 그대로
                    lambda x: x
                ]
                
                for decode_func in decodings_to_try:
                    try:
                        decoded = decode_func(raw_filename)
                        if decoded and not decoded.isspace() and len(decoded) > 0:
                            # 한글이 포함되어 있거나 확장자가 있으면 유효한 파일명으로 간주
                            if any(ord(char) > 127 for char in decoded) or '.' in decoded:
                                clean_filename = self.sanitize_filename(decoded.replace('+', ' '))
                                logger.debug(f"파일명 디코딩 성공: {raw_filename} → {clean_filename}")
                                return os.path.join(save_dir, clean_filename)
                    except Exception as e:
                        logger.debug(f"디코딩 시도 실패: {e}")
                        continue
        
        # Content-Disposition에서 추출 실패한 경우, 기존 파일명을 URL 디코딩 시도
        if original_filename and '%' in original_filename:
            try:
                decoded_original = unquote(original_filename, encoding='utf-8')
                clean_filename = self.sanitize_filename(decoded_original)
                logger.debug(f"기존 파일명 디코딩: {original_filename} → {clean_filename}")
                return os.path.join(save_dir, clean_filename)
            except Exception as e:
                logger.debug(f"기존 파일명 디코딩 실패: {e}")
        
        return default_path
    
    def _rebuild_response_with_first_chunk(self, response, first_chunk):
        """첫 번째 청크를 이미 읽은 응답을 재구성하는 헬퍼 메서드"""
        class ChunkedResponse:
            def __init__(self, original_response, first_chunk):
                self.original_response = original_response
                self.first_chunk = first_chunk
                self.first_chunk_sent = False
                
            def iter_content(self, chunk_size=8192):
                if not self.first_chunk_sent:
                    self.first_chunk_sent = True
                    yield self.first_chunk
                
                for chunk in self.original_response.iter_content(chunk_size=chunk_size):
                    yield chunk
                    
            def __getattr__(self, name):
                return getattr(self.original_response, name)
        
        return ChunkedResponse(response, first_chunk)
    
    def sanitize_filename(self, filename: str) -> str:
        """파일명 정리"""
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = filename.replace('\n', '').replace('\t', '').strip()
        return filename[:200]  # 파일명 길이 제한
    
    def scrape_pages(self, max_pages: int = 3, output_base: str = "output") -> dict:
        """페이지 스크래핑 실행"""
        results = {
            'total_announcements': 0,
            'total_files': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'pages_processed': 0
        }
        
        try:
            for page_num in range(1, max_pages + 1):
                logger.info(f"\n{'='*50}")
                logger.info(f"페이지 {page_num} 처리 시작")
                logger.info(f"{'='*50}")
                
                # 목록 페이지 가져오기
                list_url = self.get_list_url(page_num)
                response = self.get_page(list_url)
                
                if not response:
                    logger.error(f"페이지 {page_num} 콘텐츠 로딩 실패")
                    break
                
                html_content = response.text
                
                # 공고 목록 파싱
                announcements = self.parse_list_page(html_content)
                
                if not announcements:
                    logger.warning(f"페이지 {page_num}에서 공고를 찾을 수 없음")
                    break
                
                results['total_announcements'] += len(announcements)
                
                # 각 공고 처리
                for announcement in announcements:
                    try:
                        # 상세 페이지 가져오기
                        detail_response = self.get_page(announcement['url'])
                        if not detail_response:
                            continue
                        
                        detail_html = detail_response.text
                        
                        # 상세 정보 파싱
                        detail_info = self.parse_detail_page(detail_html)
                        
                        # 출력 디렉토리 생성
                        announcement_dir = os.path.join(output_base, f"{announcement['number']}_{self.sanitize_filename(announcement['title'][:50])}")
                        os.makedirs(announcement_dir, exist_ok=True)
                        
                        # 본문 저장
                        content_file = os.path.join(announcement_dir, "content.md")
                        with open(content_file, 'w', encoding='utf-8') as f:
                            f.write(f"# {detail_info['title']}\n\n")
                            f.write(f"- 카테고리: {announcement['category']}\n")
                            f.write(f"- 번호: {announcement['number']}\n")
                            f.write(f"- 날짜: {detail_info['date']}\n")
                            f.write(f"- 원본 URL: {announcement['url']}\n\n")
                            f.write("## 본문\n\n")
                            f.write(detail_info['content'])
                        
                        # 첨부파일 다운로드
                        if detail_info['attachments']:
                            # attachments 디렉토리 생성
                            attachments_dir = os.path.join(announcement_dir, "attachments")
                            os.makedirs(attachments_dir, exist_ok=True)
                            
                            for attachment in detail_info['attachments']:
                                file_path = os.path.join(attachments_dir, attachment['filename'])
                                
                                results['total_files'] += 1
                                if self.download_file(attachment['url'], file_path):
                                    results['successful_downloads'] += 1
                                else:
                                    results['failed_downloads'] += 1
                        
                        logger.info(f"공고 처리 완료: {announcement['title'][:50]}...")
                        
                    except Exception as e:
                        logger.error(f"공고 처리 중 오류: {e}")
                        continue
                
                results['pages_processed'] += 1
                
                # 페이지 간 대기
                if page_num < max_pages:
                    time.sleep(self.delay_between_pages)
            
        except Exception as e:
            logger.error(f"스크래핑 중 오류: {e}")
        
        return results

def test_scherb_scraper(pages=1):
    """SCHERB 스크래퍼 테스트 - 개선된 버전"""
    # 로그 레벨 설정 (DEBUG로 설정하여 더 자세한 정보 확인)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    scraper = EnhancedScherbScraper()
    output_dir = "output/scherb_improved"
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"개선된 SCHERB 스크래퍼 테스트 시작 - {pages}페이지")
    results = scraper.scrape_pages(max_pages=pages, output_base=output_dir)
    
    logger.info(f"\n{'='*60}")
    logger.info("📊 테스트 결과 요약")
    logger.info(f"{'='*60}")
    logger.info(f"📄 처리된 페이지: {results['pages_processed']}")
    logger.info(f"📋 총 공고 수: {results['total_announcements']}")
    logger.info(f"📎 발견된 파일 수: {results['total_files']}")
    logger.info(f"✅ 다운로드 성공: {results['successful_downloads']}")
    logger.info(f"❌ 다운로드 실패: {results['failed_downloads']}")
    
    if results['total_files'] > 0:
        success_rate = (results['successful_downloads'] / results['total_files']) * 100
        logger.info(f"🎯 성공률: {success_rate:.1f}%")
        
        if success_rate < 50:
            logger.warning("⚠️  성공률이 50% 미만입니다. 추가 개선이 필요합니다.")
        elif success_rate < 80:
            logger.info("⚡ 성공률이 양호합니다. 추가 최적화 가능합니다.")
        else:
            logger.info("🎉 성공률이 우수합니다!")
    
    # 실제 다운로드된 파일 확인
    logger.info(f"\n📁 실제 다운로드된 파일 현황:")
    try:
        total_files_downloaded = 0
        for root, dirs, files in os.walk(output_dir):
            if 'attachments' in root and files:
                actual_files = [f for f in files if not f.startswith('.')]
                if actual_files:
                    rel_path = os.path.relpath(root, output_dir)
                    logger.info(f"   {rel_path}: {len(actual_files)}개 파일")
                    total_files_downloaded += len(actual_files)
        
        logger.info(f"💾 실제 저장된 파일 총 개수: {total_files_downloaded}개")
        
        if total_files_downloaded != results['successful_downloads']:
            logger.warning(f"⚠️  보고된 성공 수({results['successful_downloads']})와 실제 파일 수({total_files_downloaded})가 다릅니다.")
            
    except Exception as e:
        logger.error(f"파일 현황 확인 중 오류: {e}")
    
    logger.info(f"{'='*60}")
    return results

if __name__ == "__main__":
    test_scherb_scraper(1)  # 1페이지만 테스트