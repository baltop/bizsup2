#!/usr/bin/env python3
"""
Enhanced BUSANSINBO (부산신용보증재단) 스크래퍼

부산신용보증재단 공지사항 게시판에서 공고를 수집하는 스크래퍼입니다.
JavaScript 기반 네비게이션과 파일 다운로드를 완전 지원합니다.

URL: https://www.busansinbo.or.kr/portal/board/post/list.do?bcIdx=565&mid=0301010000
"""

import os
import re
import time
import logging
from typing import List, Dict, Any
from urllib.parse import urljoin, unquote
from bs4 import BeautifulSoup
from enhanced_base_scraper import StandardTableScraper
from playwright.sync_api import sync_playwright, Browser, Page

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedBusansinboScraper(StandardTableScraper):
    """BUSANSINBO 전용 Enhanced 스크래퍼 - Playwright 기반 + 파일 다운로드 지원"""
    
    def __init__(self):
        super().__init__()
        
        # BUSANSINBO 사이트 설정
        self.base_url = "https://www.busansinbo.or.kr"
        self.list_url = "https://www.busansinbo.or.kr/portal/board/post/list.do?bcIdx=565&mid=0301010000"
        self.download_url = "https://www.busansinbo.or.kr/common/file/download.do"
        
        # 사이트별 특화 설정
        self.verify_ssl = True  # BUSANSINBO SSL 인증서 정상
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 2
        
        # BUSANSINBO 특화 설정
        self.bc_idx = "565"
        self.mid = "0301010000"
        
        # Playwright 관련
        self.playwright = None
        self.browser = None
        self.page = None
        
    def _setup_playwright(self):
        """Playwright 브라우저 설정"""
        if not self.playwright:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=True)
            self.page = self.browser.new_page()
            
            # 기본 설정
            self.page.set_default_timeout(30000)
            
            logger.info("Playwright 브라우저 시작")
            
    def _cleanup_playwright(self):
        """Playwright 브라우저 정리"""
        if self.page:
            self.page.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
            
        logger.info("Playwright 브라우저 종료")
    
    def _get_page_announcements(self, page_num: int) -> list:
        """BUSANSINBO Playwright 기반 페이지 수집"""
        try:
            logger.info(f"BUSANSINBO 페이지 {page_num} 수집 시작 (Playwright)")
            
            # Playwright 설정
            self._setup_playwright()
            
            # 첫 페이지 접속
            if page_num == 1:
                logger.info(f"첫 페이지 접속: {self.list_url}")
                self.page.goto(self.list_url)
                time.sleep(2)  # 페이지 로딩 대기
            else:
                # 페이지네이션 클릭
                logger.info(f"{page_num}페이지로 이동")
                pagination_link = self.page.locator(f"a[onclick*='goPage({page_num})']")
                if pagination_link.count() > 0:
                    pagination_link.click()
                    time.sleep(2)  # 페이지 로딩 대기
                else:
                    logger.error(f"페이지 {page_num} 링크를 찾을 수 없습니다")
                    return []
            
            # 현재 페이지의 HTML 가져오기
            html_content = self.page.content()
            announcements = self.parse_list_page_playwright(html_content)
            
            return announcements
            
        except Exception as e:
            logger.error(f"페이지 {page_num} 수집 중 오류: {e}")
            return []
    
    def parse_list_page_playwright(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱 - BUSANSINBO Playwright 버전"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # BUSANSINBO 테이블 찾기 (class="board-table")
        table = soup.find('table', class_='board-table')
        if not table:
            logger.warning("BUSANSINBO board-table을 찾을 수 없습니다")
            return announcements
        
        tbody = table.find('tbody')
        if not tbody:
            logger.warning("BUSANSINBO tbody를 찾을 수 없습니다")
            return announcements
            
        rows = tbody.find_all('tr')
        logger.info(f"BUSANSINBO 테이블에서 {len(rows)}개 행 발견")
        
        for i, row in enumerate(rows):
            try:
                cells = row.find_all('td')
                if len(cells) < 5:  # num, title, file, view, date
                    continue
                
                # 컬럼 파싱: num, title, file, view, date
                number_cell = cells[0]  # td.num
                title_cell = cells[1]   # td.title
                file_cell = cells[2]    # td.file
                views_cell = cells[3]   # td.view
                date_cell = cells[4]    # td.date
                
                # 번호 처리
                number_text = number_cell.get_text(strip=True)
                is_notice = False
                if not number_text.isdigit():
                    is_notice = True
                    number = "공지" if "공지" in number_text else number_text
                else:
                    number = number_text
                
                # 제목 및 상세 페이지 정보
                title_link = title_cell.find('a')
                if not title_link:
                    continue
                
                title = title_link.get_text(strip=True)
                # data-req-get-p-idx에서 공고 ID 추출
                idx = title_link.get('data-req-get-p-idx', '')
                if not idx:
                    continue
                
                # 상세 페이지 URL 구성
                detail_url = f"{self.base_url}/portal/board/post/view.do?bcIdx={self.bc_idx}&mid={self.mid}&idx={idx}"
                
                # 조회수
                views = views_cell.get_text(strip=True)
                
                # 작성일
                date = date_cell.get_text(strip=True)
                
                # 첨부파일 여부 확인
                has_attachments = bool(file_cell.find('a', class_='file-download'))
                
                announcement = {
                    'number': number,
                    'title': title,
                    'views': views,
                    'date': date,
                    'url': detail_url,
                    'has_attachments': has_attachments,
                    'is_notice': is_notice,
                    'idx': idx  # 상세 페이지 접근용
                }
                
                announcements.append(announcement)
                logger.debug(f"공고 추가: [{number}] {title}")
                
            except Exception as e:
                logger.error(f"행 {i} 파싱 중 오류: {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
        return announcements
    
    def get_detail_page_content(self, announcement: dict) -> str:
        """상세 페이지 내용 가져오기 - Playwright 사용"""
        try:
            detail_url = announcement['url']
            logger.info(f"상세 페이지 접속: {detail_url}")
            
            # 상세 페이지로 이동
            self.page.goto(detail_url)
            time.sleep(2)
            
            # 페이지 내용 가져오기
            html_content = self.page.content()
            return html_content
            
        except Exception as e:
            logger.error(f"상세 페이지 접속 실패: {e}")
            return ""
    
    def parse_detail_page(self, html_content: str, url: str = None) -> Dict[str, Any]:
        """상세 페이지 파싱 - BUSANSINBO 구조에 최적화"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출
        title = self._extract_title(soup)
        
        # 본문 내용 추출
        content_text = self._extract_main_content(soup)
        
        # 메타 정보 추출
        meta_info = self._extract_meta_info(soup)
        
        # 첨부파일 추출 (개선된 버전)
        attachments = self._extract_attachments_enhanced(soup)
        
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
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """BUSANSINBO 상세페이지에서 제목 추출"""
        # h4 태그에서 제목 찾기
        title_elem = soup.find('h4')
        if title_elem:
            title_text = title_elem.get_text(strip=True)
            if title_text and len(title_text) > 5:
                return title_text
        
        # 백업 방법: 다른 헤더 태그들
        for tag in ['h1', 'h2', 'h3', 'h5']:
            title_elem = soup.find(tag)
            if title_elem:
                title_text = title_elem.get_text(strip=True)
                if 10 < len(title_text) < 200:
                    return title_text
        
        return "제목 없음"
    
    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """BUSANSINBO 사이트에서 본문 내용 추출 - 개선된 버전"""
        
        # 1. 불필요한 요소들 제거
        unwanted_selectors = [
            'nav', 'header', 'footer', '.nav', '.navigation',
            '.menu', '.sidebar', '.breadcrumb', '.top-banner',
            'script', 'style', '.ads', '.advertisement',
            '.btn-group', '.pagination', '.paging', '.util-menu'
        ]
        
        for selector in unwanted_selectors:
            for elem in soup.select(selector):
                elem.decompose()
        
        # 2. 제목 태그 찾기
        title_elem = soup.find('h4')
        if title_elem:
            # 제목 다음의 모든 형제 요소에서 본문 찾기
            content_parts = []
            current = title_elem.next_sibling
            
            while current:
                if hasattr(current, 'get_text'):
                    text = current.get_text(strip=True)
                    # 메타 정보 (작성자, 작성일, 조회) 건너뛰기
                    if not any(keyword in text for keyword in ['작성자', '작성일', '조회', '첨부파일']):
                        if len(text) > 20:  # 의미있는 길이의 텍스트만
                            content_parts.append(text)
                current = current.next_sibling
            
            if content_parts:
                return '\n\n'.join(content_parts)
        
        # 3. 백업 방법: 가장 긴 텍스트 블록 찾기 (개선)
        content_candidates = []
        for elem in soup.find_all(['div', 'p', 'article', 'section']):
            text = elem.get_text(strip=True)
            # 네비게이션 텍스트 제외
            if len(text) > 100 and '홈' not in text and '메뉴' not in text:
                content_candidates.append(text)
        
        if content_candidates:
            # 가장 긴 텍스트를 본문으로 선택하되, 너무 긴 것은 제외 (전체 페이지 방지)
            suitable_content = [c for c in content_candidates if 100 < len(c) < 2000]
            if suitable_content:
                return max(suitable_content, key=len)
            elif content_candidates:
                return max(content_candidates, key=len)[:2000] + "..."
        
        return "본문 내용을 찾을 수 없습니다."
    
    def _extract_meta_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """BUSANSINBO 사이트에서 메타 정보 추출"""
        meta_info = {}
        
        try:
            # span 태그로 감싸진 메타 정보 찾기
            spans = soup.find_all('span')
            current_field = None
            
            for span in spans:
                span_text = span.get_text(strip=True)
                
                if span_text in ['작성자', '작성일', '조회']:
                    current_field = span_text
                elif current_field and span.parent:
                    # 같은 p 태그 내의 텍스트에서 값 추출
                    parent_text = span.parent.get_text(strip=True)
                    if current_field == '작성자':
                        value = parent_text.replace('작성자', '').strip()
                        if value:
                            meta_info['작성자'] = value
                    elif current_field == '작성일':
                        value = parent_text.replace('작성일', '').strip()
                        if value:
                            meta_info['작성일'] = value
                    elif current_field == '조회':
                        value = parent_text.replace('조회', '').strip()
                        if value:
                            meta_info['조회수'] = value
                    current_field = None
            
        except Exception as e:
            logger.debug(f"메타 정보 추출 중 오류: {e}")
        
        return meta_info
    
    def _extract_attachments_enhanced(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """BUSANSINBO 첨부파일 정보 완전 추출 - 다운로드 지원"""
        attachments = []
        
        try:
            # 첨부파일 다운로드 버튼들 찾기
            file_buttons = soup.find_all('button', class_='file-download')
            
            for button in file_buttons:
                onclick = button.get('onclick', '')
                
                # yhLib.file.download('atchFileId', 'fileSn') 패턴에서 추출
                match = re.search(r"yhLib\.file\.download\('([^']+)','([^']+)'\)", onclick)
                if match:
                    atch_file_id, file_sn = match.groups()
                    
                    # 파일명 추출 (span.file-title에서)
                    title_span = button.find('span', class_='file-title')
                    filename = title_span.get_text(strip=True) if title_span else f"file_{file_sn}"
                    
                    # 파일 크기 추출 (span.file-size에서)
                    size_span = button.find('span', class_='file-size')
                    size_info = size_span.get_text(strip=True) if size_span else ""
                    if size_info:
                        # [Size: 102.4Kbyte] 형태에서 크기만 추출
                        size_match = re.search(r'\[Size:\s*([^\]]+)\]', size_info)
                        if size_match:
                            size_info = size_match.group(1)
                    
                    # 파일 타입 결정
                    file_type = self._determine_file_type(filename, None)
                    
                    attachment = {
                        'filename': filename,
                        'atchFileId': atch_file_id,
                        'fileSn': file_sn,
                        'type': file_type,
                        'size': size_info,
                        'download_method': 'direct',  # 이제 직접 다운로드 가능
                        'url': f"{self.download_url}?atchFileId={atch_file_id}&fileSn={file_sn}"
                    }
                    
                    attachments.append(attachment)
                    logger.debug(f"첨부파일 발견: {filename} ({size_info})")
        
        except Exception as e:
            logger.error(f"첨부파일 추출 중 오류: {e}")
        
        logger.info(f"첨부파일 {len(attachments)}개 발견")
        return attachments
    
    def _determine_file_type(self, filename: str, link_elem) -> str:
        """파일 타입 결정"""
        if not filename:
            return 'unknown'
        
        filename_lower = filename.lower()
        
        if filename_lower.endswith('.pdf'):
            return 'pdf'
        elif filename_lower.endswith(('.hwp', '.hwpx')):
            return 'hwp'
        elif filename_lower.endswith(('.doc', '.docx')):
            return 'doc'
        elif filename_lower.endswith(('.xls', '.xlsx')):
            return 'excel'
        elif filename_lower.endswith(('.jpg', '.jpeg', '.png', '.gif')):
            return 'image'
        elif filename_lower.endswith('.zip'):
            return 'zip'
        else:
            return 'unknown'
    
    def download_file(self, file_url: str, save_path: str, attachment_info: dict = None) -> bool:
        """BUSANSINBO 파일 다운로드 - 완전 구현"""
        try:
            if not attachment_info:
                logger.error("첨부파일 정보가 없습니다")
                return False
                
            atch_file_id = attachment_info.get('atchFileId')
            file_sn = attachment_info.get('fileSn')
            
            if not atch_file_id or not file_sn:
                logger.error("파일 다운로드에 필요한 파라미터가 없습니다")
                return False
            
            logger.info(f"파일 다운로드 시작: {attachment_info.get('filename', 'unknown')}")
            
            # 다운로드 URL 구성
            download_url = f"{self.download_url}?atchFileId={atch_file_id}&fileSn={file_sn}"
            
            # 다운로드 헤더 설정
            download_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
                'Connection': 'keep-alive',
                'Referer': self.list_url  # Referer 헤더 추가
            }
            
            # 다운로드 요청
            response = self.session.get(
                download_url, 
                headers=download_headers, 
                stream=True, 
                verify=self.verify_ssl, 
                timeout=self.timeout
            )
            
            logger.info(f"다운로드 응답: {response.status_code}, 크기: {len(response.content)} bytes")
            
            if response.status_code != 200:
                logger.error(f"다운로드 실패: HTTP {response.status_code}")
                return False
            
            # 파일 저장
            return self._save_file_from_response(response, save_path)
            
        except Exception as e:
            logger.error(f"파일 다운로드 중 예외 발생: {e}")
            return False
    
    def _save_file_from_response(self, response, save_path: str) -> bool:
        """응답에서 파일 저장 - 한글 파일명 처리 개선"""
        try:
            # Content-Disposition에서 파일명 추출 시도
            content_disposition = response.headers.get('Content-Disposition', '')
            if content_disposition:
                extracted_filename = self._extract_filename_from_disposition(content_disposition)
                if extracted_filename:
                    # 디렉토리는 유지하고 파일명만 변경
                    directory = os.path.dirname(save_path)
                    save_path = os.path.join(directory, self.sanitize_filename(extracted_filename))
            
            # 파일 저장
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(save_path)
            logger.info(f"파일 다운로드 완료: {os.path.basename(save_path)} ({file_size:,} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"파일 저장 실패: {e}")
            return False
    
    def _extract_filename_from_disposition(self, content_disposition: str) -> str:
        """Content-Disposition 헤더에서 파일명 추출 - BUSANSINBO 특화"""
        try:
            # filename= 파라미터 찾기
            if 'filename=' in content_disposition:
                # filename="..." 형태에서 추출
                filename_match = re.search(r'filename=(["\']?)([^"\']+)\1', content_disposition)
                if filename_match:
                    filename_encoded = filename_match.group(2)
                    
                    # URL 디코딩
                    filename = unquote(filename_encoded, encoding='utf-8')
                    
                    # + 기호를 공백으로 변환
                    filename = filename.replace('+', ' ')
                    
                    return filename.strip()
                    
        except Exception as e:
            logger.debug(f"파일명 추출 실패: {e}")
            
        return None
    
    def scrape_pages(self, max_pages: int = 3, output_base: str = "output") -> dict:
        """페이지 스크래핑 메인 메서드 - 파일 다운로드 포함"""
        try:
            logger.info(f"BUSANSINBO 스크래핑 시작: 최대 {max_pages}페이지 (파일 다운로드 포함)")
            
            total_announcements = 0
            total_files = 0
            successful_downloads = 0
            
            for page_num in range(1, max_pages + 1):
                logger.info(f"페이지 {page_num} 처리 중")
                
                # 페이지별 공고 수집
                announcements = self._get_page_announcements(page_num)
                
                if not announcements:
                    logger.warning(f"페이지 {page_num}에 공고가 없습니다")
                    continue
                
                # 각 공고 처리
                for announcement in announcements:
                    try:
                        # 상세 페이지 내용 가져오기
                        detail_html = self.get_detail_page_content(announcement)
                        if detail_html:
                            # 상세 페이지 파싱
                            detail_data = self.parse_detail_page(detail_html, announcement['url'])
                            
                            # 파일 저장
                            safe_title = self.sanitize_filename(announcement['title'])
                            number_prefix = str(announcement['number']).zfill(3)
                            announcement_dir = os.path.join(output_base, f"{number_prefix}_{safe_title}")
                            os.makedirs(announcement_dir, exist_ok=True)
                            
                            # 본문 저장
                            content_file = os.path.join(announcement_dir, "content.md")
                            with open(content_file, 'w', encoding='utf-8') as f:
                                f.write(detail_data['content'])
                                f.write(f"\n**원본 URL**: {announcement['url']}\n")
                            
                            total_announcements += 1
                            
                            # 첨부파일 다운로드
                            if detail_data['attachments']:
                                attachments_dir = os.path.join(announcement_dir, "attachments")
                                os.makedirs(attachments_dir, exist_ok=True)
                                
                                for i, attach in enumerate(detail_data['attachments']):
                                    total_files += 1
                                    
                                    # 파일명 정리
                                    filename = attach['filename']
                                    safe_filename = self.sanitize_filename(filename)
                                    file_path = os.path.join(attachments_dir, safe_filename)
                                    
                                    # 파일 다운로드 실행
                                    if self.download_file(attach['url'], file_path, attach):
                                        successful_downloads += 1
                                        logger.info(f"✅ 다운로드 성공: {filename}")
                                    else:
                                        logger.error(f"❌ 다운로드 실패: {filename}")
                        
                        time.sleep(self.delay_between_requests)
                        
                    except Exception as e:
                        logger.error(f"공고 처리 중 오류: {e}")
                        continue
            
            # Playwright 정리
            self._cleanup_playwright()
            
            # 성공률 계산
            download_success_rate = (successful_downloads / total_files * 100) if total_files > 0 else 0
            
            logger.info(f"✅ BUSANSINBO 스크래핑 완료!")
            logger.info(f"📄 수집된 공고: {total_announcements}개")
            logger.info(f"📁 전체 파일: {total_files}개")
            logger.info(f"💾 다운로드 성공: {successful_downloads}개")
            logger.info(f"📈 다운로드 성공률: {download_success_rate:.1f}%")
            
            return {
                'total_announcements': total_announcements,
                'total_files': total_files,
                'successful_downloads': successful_downloads,
                'download_success_rate': download_success_rate
            }
            
        except Exception as e:
            logger.error(f"스크래핑 실패: {e}")
            self._cleanup_playwright()
            return {'total_announcements': 0, 'total_files': 0, 'successful_downloads': 0, 'download_success_rate': 0.0}


def main():
    """테스트 실행"""
    output_dir = "output/busansinbo"
    os.makedirs(output_dir, exist_ok=True)
    
    scraper = EnhancedBusansinboScraper()
    
    try:
        result = scraper.scrape_pages(max_pages=3, output_base=output_dir)
        print(f"✅ BUSANSINBO 스크래핑 완료!")
        print(f"수집된 공고: {result.get('total_announcements', 0)}개")
        print(f"전체 파일: {result.get('total_files', 0)}개")
        print(f"다운로드 성공: {result.get('successful_downloads', 0)}개")
        print(f"다운로드 성공률: {result.get('download_success_rate', 0):.1f}%")
        
    except Exception as e:
        print(f"❌ 스크래핑 실패: {e}")
        raise


if __name__ == "__main__":
    main()