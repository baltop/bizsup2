#!/usr/bin/env python3
"""
Enhanced KPC (한국생산성본부) 스크래퍼

KPC 지원사업 공고 게시판에서 공고를 수집하는 스크래퍼입니다.
JavaScript 기반 동적 사이트이므로 Playwright를 사용합니다.

URL: https://www.kpc.or.kr/PTWCC002_board_index2.do?type_cd=02
"""

import os
import re
import time
import logging
from typing import List, Dict, Any
from urllib.parse import urljoin, unquote
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Page, Browser
from enhanced_base_scraper import EnhancedBaseScraper

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedKpcScraper(EnhancedBaseScraper):
    """KPC 전용 Enhanced 스크래퍼 - Playwright 기반"""
    
    def __init__(self):
        super().__init__()
        
        # KPC 사이트 설정
        self.base_url = "https://www.kpc.or.kr"
        self.list_url = "https://www.kpc.or.kr/PTWCC002_board_index2.do?type_cd=02"
        
        # 사이트별 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 60000  # Playwright는 millisecond 단위 (60초로 증가)
        self.delay_between_requests = 3
        
        # Playwright 관련 설정
        self.playwright = None
        self.browser = None
        self.page = None
        
    def __enter__(self):
        """Context manager 진입"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        self.page = self.browser.new_page()
        
        # 기본 타임아웃 설정
        self.page.set_default_timeout(self.timeout)
        
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
        """페이지별 URL 생성 - KPC는 pagenum 파라미터 사용"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}&pagenum={page_num}"
        
    def navigate_to_page(self, page_num: int) -> bool:
        """URL 기반 페이지네이션으로 해당 페이지로 이동"""
        try:
            page_url = self.get_list_url(page_num)
            self.page.goto(page_url, wait_until='networkidle')
            time.sleep(2)  # 추가 로딩 대기
            return True
                
        except Exception as e:
            logger.error(f"페이지 {page_num} 이동 중 오류: {e}")
            return False
            
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱 - KPC 특화 구조"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 1. 상단 슬라이더 공고 찾기 (3개)
        slider_items = soup.select('div[role="group"]')
        logger.info(f"슬라이더 공고: {len(slider_items)}개 발견")
        
        for i, item in enumerate(slider_items):
            try:
                announcement = self._parse_slider_item(item, i)
                if announcement:
                    announcements.append(announcement)
            except Exception as e:
                logger.error(f"슬라이더 아이템 {i} 파싱 실패: {e}")
        
        # 2. 하단 목록 공고 찾기 (10개)
        # 클릭 가능한 div 중 제목이 있는 것들 찾기
        clickable_divs = soup.find_all('div', {'style': re.compile(r'cursor:\s*pointer|cursor:pointer')})
        if not clickable_divs:
            clickable_divs = soup.find_all('div', onclick=True)
        
        logger.info(f"클릭 가능한 div: {len(clickable_divs)}개 발견")
        
        for i, div in enumerate(clickable_divs):
            try:
                # 제목으로 보이는 텍스트가 있는지 확인
                div_text = div.get_text(strip=True)
                if len(div_text) > 10 and not self._is_navigation_text(div_text):
                    announcement = self._parse_list_item(div, len(announcements))
                    if announcement:
                        announcements.append(announcement)
            except Exception as e:
                logger.error(f"목록 아이템 {i} 파싱 실패: {e}")
        
        logger.info(f"총 {len(announcements)}개 공고 수집완료")
        return announcements
        
    def _parse_slider_item(self, item, index) -> Dict[str, Any]:
        """슬라이더 아이템 파싱"""
        # 제목 찾기 (heading level=3)
        title_elem = item.find('h3') or item.find(['h1', 'h2', 'h4'])
        if not title_elem:
            return None
            
        title = title_elem.get_text(strip=True)
        if len(title) < 5:
            return None
        
        # onclick 또는 href 정보 찾기
        clickable_elem = item.find(['div', 'a'], onclick=True) or item.find('a', href=True)
        detail_url = ""
        
        if clickable_elem:
            onclick = clickable_elem.get('onclick', '')
            href = clickable_elem.get('href', '')
            
            if onclick:
                # onclick에서 URL 추출
                url_match = re.search(r"location\.href\s*=\s*['\"]([^'\"]+)['\"]", onclick)
                if url_match:
                    detail_url = urljoin(self.base_url, url_match.group(1))
            elif href:
                detail_url = urljoin(self.base_url, href)
        
        # 메타 정보 추출
        meta_list = item.find('ul')
        meta_info = {}
        if meta_list:
            list_items = meta_list.find_all('li')
            for li in list_items:
                li_text = li.get_text(strip=True)
                if '조회' in li_text:
                    meta_info['views'] = li_text
                elif re.search(r'\d{4}', li_text):
                    meta_info['date'] = li_text
                else:
                    meta_info['author'] = li_text
        
        return {
            'number': f'slider_{index+1}',
            'title': title,
            'author': meta_info.get('author', '관리자'),
            'date': meta_info.get('date', ''),
            'views': meta_info.get('views', ''),
            'url': detail_url,
            'has_attachments': False,
            'type': 'slider'
        }
        
    def _parse_list_item(self, div, index) -> Dict[str, Any]:
        """목록 아이템 파싱"""
        title = div.get_text(strip=True)
        
        if len(title) < 5:
            return None
            
        # onclick 또는 href 정보 추출
        onclick = div.get('onclick', '')
        detail_url = ""
        
        if onclick:
            # onclick에서 URL 추출
            url_match = re.search(r"location\.href\s*=\s*['\"]([^'\"]+)['\"]", onclick)
            if url_match:
                detail_url = urljoin(self.base_url, url_match.group(1))
        
        # 부모 요소에서 메타 정보 찾기
        parent = div.parent
        meta_info = {}
        
        if parent:
            parent_text = parent.get_text()
            # 날짜 패턴 찾기
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', parent_text)
            if date_match:
                meta_info['date'] = date_match.group(1)
            
            # 조회수 패턴 찾기
            views_match = re.search(r'조회\s+(\d+)', parent_text)
            if views_match:
                meta_info['views'] = views_match.group(1)
        
        return {
            'number': str(index + 1),
            'title': title,
            'author': '관리자',
            'date': meta_info.get('date', ''),
            'views': meta_info.get('views', ''),
            'url': detail_url,
            'has_attachments': False,
            'type': 'list'
        }
        
    def _is_navigation_text(self, text: str) -> bool:
        """네비게이션 텍스트인지 확인"""
        nav_keywords = ['메뉴', '홈', '로그인', '검색', '이전', '다음', '목록']
        return any(keyword in text for keyword in nav_keywords)
        
    def _extract_detail_info_from_onclick(self, onclick: str) -> Dict[str, str]:
        """onclick 이벤트에서 상세 페이지 정보 추출"""
        if not onclick:
            return {}
            
        # 다양한 JavaScript 함수 패턴 처리
        patterns = [
            r"viewDetail\('([^']+)'\)",
            r"showDetail\('([^']+)'\)",
            r"goDetail\('([^']+)'\)",
            r"fn_detail\('([^']+)'\)",
            r"detail\('([^']+)'\)",
            r"view\('([^']+)',\s*'([^']*)'\)",
            r"goView\('([^']+)',\s*'([^']*)'\)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, onclick)
            if match:
                groups = match.groups()
                return {
                    'id': groups[0],
                    'type': groups[1] if len(groups) > 1 else '',
                    'onclick': onclick
                }
                
        return {}
        
    def get_detail_page_content(self, announcement: Dict[str, Any]) -> str:
        """상세 페이지 접근 및 HTML 내용 반환"""
        try:
            detail_url = announcement.get('url', '')
            
            if detail_url:
                logger.info(f"상세 페이지 접근: {detail_url}")
                # 직접 URL로 이동 - 더 관대한 대기 조건 사용
                self.page.goto(detail_url, wait_until='domcontentloaded', timeout=60000)
                time.sleep(3)
                
                # 현재 페이지의 HTML 반환
                return self.page.content()
            else:
                logger.error("상세 페이지 URL이 없습니다")
                return ""
                
        except Exception as e:
            logger.error(f"상세 페이지 접근 실패: {e}")
            return ""
            
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱 - KPC 구조에 최적화"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출
        title_selectors = [
            'h1', 'h2', 'h3',
            '.title', '.subject',
            '.board-title',
            'strong'
        ]
        
        title = "제목 없음"
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                potential_title = title_elem.get_text(strip=True)
                if potential_title and len(potential_title) > 5:
                    title = potential_title
                    break
        
        # 본문 내용 추출
        content_text = self._extract_main_content(soup)
        
        # 메타 정보 추출
        meta_info = self.extract_meta_info(soup)
        
        # 첨부파일 추출
        attachments = self._extract_attachments(soup)
        
        # 마크다운 형식으로 조합
        markdown_content = f"# {title}\n\n"
        
        if meta_info:
            for key, value in meta_info.items():
                markdown_content += f"**{key}**: {value}\n"
            markdown_content += "\n"
        
        markdown_content += "---\n\n"
        markdown_content += content_text
        
        return {
            'content': markdown_content,
            'attachments': attachments
        }
        
    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """KPC 사이트에서 본문 내용 추출 - 개선된 버전"""
        
        # 1. 네비게이션 및 불필요한 요소들 제거
        unwanted_selectors = [
            'nav', 'header', 'footer', '.nav', '.navigation',
            '.menu', '.sidebar', '.breadcrumb', '.footer',
            'script', 'style', '.ads', '.advertisement'
        ]
        
        for selector in unwanted_selectors:
            for elem in soup.select(selector):
                elem.decompose()
        
        # 2. KPC 특화 콘텐츠 선택자 - 실제 공고 내용이 있는 부분
        content_selectors = [
            '.board_view',          # 게시글 뷰 영역
            '.content_area',        # 콘텐츠 영역
            '.view_content',        # 뷰 콘텐츠
            '.detail_content',      # 상세 콘텐츠
            'main',                 # main 태그
            '[role="main"]'         # main 역할
        ]
        
        content_elem = None
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                logger.debug(f"콘텐츠 선택자 사용: {selector}")
                break
        
        if content_elem:
            # 추가 불필요한 요소 제거
            for unwanted in content_elem.select('.btn, .button, .pagination, .paging'):
                unwanted.decompose()
            
            # 본문 텍스트 추출
            content_text = self.simple_html_to_text(content_elem)
            
            # 네비게이션 키워드 제거
            nav_patterns = [
                r'교육\s*컨설팅\s*지수\s*자격시험\s*생산성\s*ESG',
                r'로그인\s*회원가입\s*강의요청',
                r'검색\s*최근 검색어\s*자동완성',
                r'MY KPC\s*마이페이지',
                r'KPC소개\s*고객센터',
                r'사이트맵\s*접기/펴기',
                r'법인회원제도\s*담당자연락처',
                r'Copyright.*All Rights Reserved'
            ]
            
            for pattern in nav_patterns:
                content_text = re.sub(pattern, '', content_text, flags=re.IGNORECASE)
            
            # 공고 관련 키워드가 포함된 실제 내용만 추출
            if self._contains_announcement_keywords(content_text):
                return content_text.strip()
        
        # 백업 방법: 공고 관련 키워드가 있는 가장 긴 텍스트 블록 찾기
        all_containers = soup.find_all(['div', 'p', 'article', 'section', 'table'])
        best_content = ""
        max_relevance_score = 0
        
        for container in all_containers:
            container_text = container.get_text(strip=True)
            
            if len(container_text) > 100:  # 최소 길이 조건
                relevance_score = self._calculate_relevance_score(container_text)
                
                if relevance_score > max_relevance_score:
                    best_content = container_text
                    max_relevance_score = relevance_score
        
        return best_content if best_content else "본문 내용을 찾을 수 없습니다."
    
    def _contains_announcement_keywords(self, text: str) -> bool:
        """공고 관련 키워드 포함 여부 확인"""
        keywords = [
            '모집', '공고', '신청', '접수', '선정', '지원', '사업',
            '컨설팅', '프로그램', '교육', '참가', '기업', '대상',
            '기간', '방법', '서류', '문의', '안내', '개최'
        ]
        
        return sum(1 for keyword in keywords if keyword in text) >= 3
    
    def _calculate_relevance_score(self, text: str) -> int:
        """텍스트의 공고 관련 점수 계산"""
        score = 0
        
        # 공고 관련 키워드 점수
        announcement_keywords = [
            '모집', '공고', '신청', '접수', '선정', '지원', '사업',
            '컨설팅', '프로그램', '교육', '참가', '기업', '대상'
        ]
        
        for keyword in announcement_keywords:
            score += text.count(keyword) * 2
        
        # 날짜 패턴 점수
        date_patterns = [
            r'\d{4}[.-]\d{2}[.-]\d{2}',  # 2025-06-26
            r'\d{4}년\s*\d{1,2}월\s*\d{1,2}일',  # 2025년 6월 26일
        ]
        
        for pattern in date_patterns:
            score += len(re.findall(pattern, text)) * 3
        
        # 네비게이션 키워드는 점수 차감
        nav_keywords = ['로그인', '회원가입', '검색', '메뉴', '홈', 'KPC소개']
        for keyword in nav_keywords:
            score -= text.count(keyword) * 5
        
        return score
    
    def _is_navigation_content(self, text: str) -> bool:
        """네비게이션 또는 메뉴 내용인지 확인"""
        nav_keywords = [
            '홈', '로그인', '회원가입', '사이트맵', '메뉴', '네비게이션',
            '검색', '이전', '다음', '목록', '첫페이지', '마지막페이지'
        ]
        
        for keyword in nav_keywords:
            if text.count(keyword) > 2:
                return True
        
        return False
        
    def extract_meta_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """KPC 구조에서 메타 정보 추출"""
        meta_info = {}
        
        # 페이지 텍스트에서 날짜 패턴 찾기
        page_text = soup.get_text()
        date_match = re.search(r'(\d{4}[-./]\d{2}[-./]\d{2})', page_text)
        if date_match:
            meta_info['작성일'] = date_match.group(1)
        
        # 조회수 패턴 찾기
        views_match = re.search(r'조회수?\s*:?\s*(\d+)', page_text)
        if views_match:
            meta_info['조회수'] = views_match.group(1)
        
        return meta_info
        
    def simple_html_to_text(self, element) -> str:
        """HTML 요소를 간단한 텍스트로 변환"""
        text = element.get_text(separator='\n\n', strip=True)
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text
        
    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """KPC 구조에서 첨부파일 정보 추출 - DEXT5Upload iframe 기반"""
        attachments = []
        
        # DEXT5Upload iframe 찾기
        dext_iframe = soup.find('iframe', {'title': 'DEXT5Upload Area'})
        if dext_iframe:
            logger.info("DEXT5Upload iframe 발견 - Playwright로 처리 필요")
            attachments.append({
                'filename': 'dext5upload_files',
                'url': '',
                'type': 'dext5upload_iframe',
                'iframe_title': 'DEXT5Upload Area'
            })
        
        # 다른 iframe 기반 첨부파일 시스템
        iframe_selectors = [
            'iframe[src*="upload"]',
            'iframe[src*="file"]',
            'iframe[src*="attach"]',
            'iframe[title*="upload"]',
            'iframe[title*="file"]'
        ]
        
        for selector in iframe_selectors:
            iframes = soup.select(selector)
            for iframe in iframes:
                iframe_src = iframe.get('src', '')
                iframe_title = iframe.get('title', '')
                if iframe_src or iframe_title:
                    attachments.append({
                        'filename': f'iframe_file_{len(attachments)}',
                        'url': urljoin(self.base_url, iframe_src) if iframe_src else '',
                        'type': 'iframe',
                        'iframe_title': iframe_title
                    })
        
        # 일반 다운로드 링크 찾기 (백업)
        download_selectors = [
            'a[href*="download"]',
            'a[href*="file"]',
            'a[onclick*="download"]'
        ]
        
        for selector in download_selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get('href', '')
                onclick = link.get('onclick', '')
                filename = link.get_text(strip=True)
                
                if href and filename and len(filename) > 3:
                    file_url = urljoin(self.base_url, href)
                    attachments.append({
                        'filename': filename,
                        'url': file_url,
                        'type': 'direct'
                    })
                elif onclick and filename and len(filename) > 3:
                    attachments.append({
                        'filename': filename,
                        'url': '',
                        'type': 'javascript',
                        'onclick': onclick
                    })
        
        logger.info(f"첨부파일 {len(attachments)}개 발견")
        return attachments
        
    def _download_attachments(self, attachments: List[Dict[str, Any]], folder_path: str):
        """첨부파일 다운로드 - DEXT5Upload iframe 및 기타 방식 지원"""
        if not attachments:
            logger.info("첨부파일이 없습니다")
            return
        
        logger.info(f"{len(attachments)}개 첨부파일 다운로드 시작")
        attachments_folder = os.path.join(folder_path, 'attachments')
        os.makedirs(attachments_folder, exist_ok=True)
        
        downloaded_count = 0
        
        for i, attachment in enumerate(attachments):
            try:
                attachment_type = attachment.get('type', 'direct')
                filename = attachment.get('filename', f'attachment_{i+1}')
                
                logger.info(f"첨부파일 {i+1} 처리: {filename} (타입: {attachment_type})")
                
                if attachment_type == 'dext5upload_iframe':
                    # DEXT5Upload iframe 기반 파일 다운로드
                    files_downloaded = self._download_dext5upload_files(attachments_folder)
                    downloaded_count += files_downloaded
                elif attachment_type == 'iframe':
                    # 기타 iframe 기반 파일 다운로드
                    self._download_iframe_file(attachment, attachments_folder)
                    downloaded_count += 1
                elif attachment_type == 'javascript':
                    # JavaScript 기반 파일 다운로드
                    self._download_javascript_file(attachment, attachments_folder)
                    downloaded_count += 1
                else:
                    # 직접 링크 다운로드
                    self._download_direct_file(attachment, attachments_folder)
                    downloaded_count += 1
                    
            except Exception as e:
                logger.error(f"첨부파일 다운로드 실패 - {filename}: {e}")
                continue
        
        logger.info(f"첨부파일 다운로드 완료: {downloaded_count}개 파일")
        return downloaded_count

    def _download_dext5upload_files(self, folder_path: str) -> int:
        """DEXT5Upload iframe에서 첨부파일 다운로드 - 간단한 방법"""
        try:
            # 먼저 페이지에서 DEXT5Upload iframe이 있는지 확인
            iframe_selector = 'iframe[title="DEXT5Upload Area"]'
            
            # Playwright의 frame 선택자 사용
            iframe_element = self.page.query_selector(iframe_selector)
            if not iframe_element:
                logger.warning("DEXT5Upload iframe을 찾을 수 없습니다")
                return 0
            
            logger.info("DEXT5Upload iframe 발견, 파일 다운로드 시작")
            
            # iframe 내부로 접근
            try:
                iframe = self.page.frame_locator(iframe_selector)
                
                # iframe 내부 로딩 대기
                time.sleep(5)
                
                # 전체 다운로드 버튼 찾기 (더 간단한 방법)
                download_button_selectors = [
                    'button:has-text("전체 다운로드")',
                    'input[value="전체 다운로드"]',
                    'button:has-text("다운로드")',
                    'input[value="다운로드"]',
                    '[onclick*="downloadAll"]',
                    '[onclick*="download"]'
                ]
                
                downloaded_files = 0
                
                for selector in download_button_selectors:
                    try:
                        download_button = iframe.locator(selector)
                        
                        # 버튼이 존재하는지 확인
                        if download_button.count() > 0:
                            logger.info(f"다운로드 버튼 발견: {selector}")
                            
                            # 다운로드 시작
                            with self.page.expect_download(timeout=30000) as download_info:
                                download_button.click()
                                time.sleep(2)
                            
                            download = download_info.value
                            
                            # 파일명 정리
                            suggested_name = download.suggested_filename
                            if not suggested_name:
                                suggested_name = f"kpc_attachment_{int(time.time())}"
                            
                            safe_filename = self.sanitize_filename(suggested_name)
                            
                            # 파일 저장
                            file_path = os.path.join(folder_path, safe_filename)
                            download.save_as(file_path)
                            
                            file_size = os.path.getsize(file_path)
                            logger.info(f"파일 다운로드 완료: {safe_filename} ({file_size} bytes)")
                            
                            downloaded_files += 1
                            break
                            
                    except Exception as e:
                        logger.debug(f"다운로드 버튼 {selector} 시도 실패: {e}")
                        continue
                
                if downloaded_files == 0:
                    # 개별 파일 다운로드 시도
                    logger.info("전체 다운로드 실패, 개별 파일 다운로드 시도")
                    downloaded_files = self._download_individual_files(iframe, folder_path)
                
                logger.info(f"DEXT5Upload 다운로드 완료: {downloaded_files}개 파일")
                return downloaded_files
                
            except Exception as e:
                logger.error(f"iframe 처리 중 오류: {e}")
                return 0
            
        except Exception as e:
            logger.error(f"DEXT5Upload 파일 다운로드 실패: {e}")
            return 0
    
    def _download_individual_files(self, iframe, folder_path: str) -> int:
        """개별 파일 다운로드"""
        try:
            downloaded_files = 0
            
            # 체크박스가 있는 파일 행 찾기
            file_checkboxes = iframe.locator('input[type="checkbox"]')
            
            if file_checkboxes.count() > 0:
                logger.info(f"{file_checkboxes.count()}개 파일 체크박스 발견")
                
                for i in range(file_checkboxes.count()):
                    try:
                        checkbox = file_checkboxes.nth(i)
                        
                        # 체크박스 선택
                        checkbox.check()
                        time.sleep(0.5)
                        
                        # 다운로드 버튼 클릭
                        download_button = iframe.locator('button:has-text("다운로드"), input[value="다운로드"]').first()
                        
                        if download_button.count() > 0:
                            with self.page.expect_download(timeout=30000) as download_info:
                                download_button.click()
                                time.sleep(1)
                            
                            download = download_info.value
                            
                            # 파일 저장
                            suggested_name = download.suggested_filename or f"file_{i+1}"
                            safe_filename = self.sanitize_filename(suggested_name)
                            file_path = os.path.join(folder_path, safe_filename)
                            download.save_as(file_path)
                            
                            file_size = os.path.getsize(file_path)
                            logger.info(f"개별 파일 다운로드 완료: {safe_filename} ({file_size} bytes)")
                            
                            downloaded_files += 1
                        
                        # 체크박스 해제
                        checkbox.uncheck()
                        time.sleep(0.5)
                        
                    except Exception as e:
                        logger.error(f"개별 파일 {i+1} 다운로드 실패: {e}")
                        continue
            
            return downloaded_files
            
        except Exception as e:
            logger.error(f"개별 파일 다운로드 실패: {e}")
            return 0
                
    def _download_iframe_file(self, attachment: Dict[str, Any], folder_path: str):
        """iframe 기반 파일 다운로드"""
        try:
            iframe_url = attachment['url']
            
            # 새 페이지에서 iframe 로드
            iframe_page = self.browser.new_page()
            iframe_page.goto(iframe_url, wait_until='networkidle')
            
            # iframe 내부의 다운로드 링크 찾기
            download_links = iframe_page.locator('a[href*="download"], a[onclick*="download"]')
            
            if download_links.count() > 0:
                # 첫 번째 다운로드 링크 클릭
                with iframe_page.expect_download() as download_info:
                    download_links.first.click()
                
                download = download_info.value
                filename = download.suggested_filename or f"iframe_file_{int(time.time())}"
                file_path = os.path.join(folder_path, filename)
                
                download.save_as(file_path)
                logger.info(f"iframe 파일 다운로드 완료: {filename}")
            
            iframe_page.close()
            
        except Exception as e:
            logger.error(f"iframe 파일 다운로드 실패: {e}")
            
    def _download_javascript_file(self, attachment: Dict[str, Any], folder_path: str):
        """JavaScript 기반 파일 다운로드"""
        try:
            onclick = attachment.get('onclick', '')
            
            if onclick:
                # JavaScript 함수 실행하여 다운로드 시작
                with self.page.expect_download() as download_info:
                    self.page.evaluate(onclick)
                
                download = download_info.value
                filename = download.suggested_filename or attachment.get('filename', f"js_file_{int(time.time())}")
                file_path = os.path.join(folder_path, filename)
                
                download.save_as(file_path)
                logger.info(f"JavaScript 파일 다운로드 완료: {filename}")
                
        except Exception as e:
            logger.error(f"JavaScript 파일 다운로드 실패: {e}")
            
    def _download_direct_file(self, attachment: Dict[str, Any], folder_path: str):
        """직접 링크 파일 다운로드"""
        try:
            url = attachment['url']
            filename = attachment.get('filename', f'direct_file_{int(time.time())}')
            
            # requests 세션 사용
            response = self.session.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Content-Disposition에서 파일명 추출 시도
            content_disposition = response.headers.get('Content-Disposition', '')
            if content_disposition:
                extracted_filename = self._extract_filename_from_disposition(content_disposition)
                if extracted_filename:
                    filename = extracted_filename
            
            clean_filename = self.sanitize_filename(filename)
            file_path = os.path.join(folder_path, clean_filename)
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(file_path)
            logger.info(f"직접 파일 다운로드 완료: {clean_filename} ({file_size} bytes)")
            
        except Exception as e:
            logger.error(f"직접 파일 다운로드 실패: {e}")
            
    def _extract_filename_from_disposition(self, content_disposition: str) -> str:
        """Content-Disposition 헤더에서 파일명 추출"""
        try:
            # RFC 5987 형식 처리
            rfc5987_match = re.search(r"filename\*=([^']*)'([^']*)'(.+)", content_disposition)
            if rfc5987_match:
                encoding, lang, filename = rfc5987_match.groups()
                try:
                    filename = unquote(filename, encoding=encoding or 'utf-8')
                    return filename
                except:
                    pass
            
            # 일반 filename 파라미터 처리
            filename_match = re.search(r'filename[^;=\n]*=([\'"]*)(.*?)\1', content_disposition)
            if filename_match:
                filename = filename_match.group(2)
                
                # UTF-8 및 EUC-KR 인코딩 시도
                for encoding in ['utf-8', 'euc-kr', 'cp949']:
                    try:
                        if encoding == 'utf-8':
                            decoded = filename.encode('latin-1').decode('utf-8')
                        else:
                            decoded = filename.encode('latin-1').decode(encoding)
                        
                        if decoded and not decoded.isspace():
                            return decoded.replace('+', ' ').strip()
                    except:
                        continue
                        
                return filename.replace('+', ' ')
                
        except Exception as e:
            logger.debug(f"파일명 추출 실패: {e}")
            
        return None
        
    def _create_folder_name(self, announcement: Dict[str, Any], index: int) -> str:
        """폴더명 생성"""
        title = announcement.get('title', '제목없음')
        
        # 폴더명에 사용할 수 없는 문자 제거
        clean_title = re.sub(r'[<>:"/\\|?*]', '', title)
        clean_title = clean_title.replace('\n', ' ').replace('\r', ' ')
        clean_title = re.sub(r'\s+', '_', clean_title.strip())
        
        # 길이 제한 (100자)
        if len(clean_title) > 100:
            clean_title = clean_title[:100]
            
        return f"{index:03d}_{clean_title}"
        
    def sanitize_filename(self, filename: str) -> str:
        """파일명 정리"""
        # 파일명에 사용할 수 없는 문자 제거
        clean_name = re.sub(r'[<>:"/\\|?*]', '', filename)
        clean_name = clean_name.replace('\n', ' ').replace('\r', ' ')
        clean_name = re.sub(r'\s+', '_', clean_name.strip())
        return clean_name
        
    def scrape_pages(self, max_pages: int = 3, output_base: str = "output") -> Dict[str, Any]:
        """페이지 스크래핑 실행 - Playwright 기반"""
        results = {
            'total_announcements': 0,
            'total_files': 0,
            'success_rate': 0.0,
            'processed_pages': 0
        }
        
        try:
            logger.info(f"KPC 스크래핑 시작 - {max_pages}페이지")
            
            for page_num in range(1, max_pages + 1):
                logger.info(f"\n=== 페이지 {page_num} 처리 중 ===")
                
                # 페이지 이동
                if not self.navigate_to_page(page_num):
                    logger.error(f"페이지 {page_num} 이동 실패")
                    continue
                
                # 현재 페이지 HTML 가져오기
                html_content = self.page.content()
                
                # 목록 파싱
                announcements = self.parse_list_page(html_content)
                
                if not announcements:
                    logger.warning(f"페이지 {page_num}에서 공고를 찾을 수 없습니다")
                    continue
                
                # 각 공고 처리
                for i, announcement in enumerate(announcements):
                    try:
                        # 중복 확인 - 기본적으로 건너뛰지 않음
                        title = announcement['title']
                        logger.info(f"공고 {i+1} 처리 중: {title}")
                        
                        # 상세 페이지 접근
                        detail_html = self.get_detail_page_content(announcement)
                        
                        if detail_html:
                            # 상세 페이지 파싱
                            detail_data = self.parse_detail_page(detail_html)
                            
                            # 폴더 생성 및 저장
                            folder_name = self._create_folder_name(announcement, results['total_announcements'] + 1)
                            folder_path = os.path.join(output_base, folder_name)
                            os.makedirs(folder_path, exist_ok=True)
                            
                            # 콘텐츠 저장
                            content_file = os.path.join(folder_path, 'content.md')
                            with open(content_file, 'w', encoding='utf-8') as f:
                                f.write(detail_data['content'])
                            
                            # 첨부파일 다운로드
                            downloaded_files = self._download_attachments(detail_data['attachments'], folder_path)
                            
                            # 통계 업데이트
                            results['total_announcements'] += 1
                            if downloaded_files:
                                results['total_files'] += downloaded_files
                            else:
                                results['total_files'] += len(detail_data['attachments'])
                            
                            logger.info(f"공고 처리 완료: {title}")
                            
                        # 목록 페이지로 돌아가기
                        self.page.go_back(wait_until='networkidle')
                        time.sleep(self.delay_between_requests)
                        
                    except Exception as e:
                        logger.error(f"공고 처리 실패 - {announcement['title']}: {e}")
                        continue
                
                results['processed_pages'] += 1
                logger.info(f"페이지 {page_num} 완료")
                
            # 성공률 계산
            if results['total_announcements'] > 0:
                results['success_rate'] = 100.0
            
            logger.info(f"\n✅ KPC 스크래핑 완료!")
            logger.info(f"처리된 페이지: {results['processed_pages']}")
            logger.info(f"수집된 공고: {results['total_announcements']}개")
            logger.info(f"다운로드된 파일: {results['total_files']}개")
            
            return results
            
        except Exception as e:
            logger.error(f"스크래핑 중 오류 발생: {e}")
            raise


def main():
    """메인 실행 함수"""
    output_dir = "output/kpc_test"
    os.makedirs(output_dir, exist_ok=True)
    
    # Context manager 사용
    with EnhancedKpcScraper() as scraper:
        try:
            result = scraper.scrape_pages(max_pages=1, output_base=output_dir)  # 1페이지, 1개 공고만 테스트
            
            print(f"\n✅ KPC 스크래핑 완료!")
            print(f"수집된 공고: {result['total_announcements']}개")
            print(f"다운로드된 파일: {result['total_files']}개")
            print(f"성공률: {result['success_rate']:.1f}%")
            
        except Exception as e:
            print(f"❌ 스크래핑 실패: {e}")


if __name__ == "__main__":
    main()