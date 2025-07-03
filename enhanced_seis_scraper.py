# -*- coding: utf-8 -*-
"""
서울특별시교육청지원청(SEIS) 공고 스크래퍼 - Enhanced 버전
URL: https://www.seis.or.kr/home/sub.do?menukey=7187
"""

import requests
from bs4 import BeautifulSoup
import os
import time
import re
from urllib.parse import urljoin, urlparse, unquote
import logging
from enhanced_base_scraper import EnhancedBaseScraper
from playwright.sync_api import sync_playwright
import json

logger = logging.getLogger(__name__)

class EnhancedSeisScraper(EnhancedBaseScraper):
    """서울특별시교육청지원청 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        # 기본 설정
        self.base_url = "https://www.seis.or.kr"
        self.list_url = "https://www.seis.or.kr/home/sub.do?menukey=7187"
        
        # 사이트별 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 60
        self.delay_between_requests = 2  # 사이트 부하 방지
        
        # SEIS 특화 설정 - Playwright 사용 (동적 콘텐츠)
        self.use_playwright = True
        self.playwright = None
        self.browser = None
        self.page = None
        
    def _init_playwright(self):
        """Playwright 초기화"""
        if self.playwright is None:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=True,
                args=['--disable-web-security', '--disable-features=VizDisplayCompositor']
            )
            self.page = self.browser.new_page()
            
            # 타임아웃 설정
            self.page.set_default_timeout(60000)  # 60초
            
    def _close_playwright(self):
        """Playwright 정리"""
        if self.page:
            self.page.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
    
    def get_list_url(self, page_num: int) -> str:
        """페이지별 목록 URL 생성"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}&page={page_num}"
    
    def get_page_content(self, url: str) -> str:
        """Playwright를 사용한 페이지 콘텐츠 가져오기"""
        try:
            self._init_playwright()
            logger.info(f"Playwright로 페이지 로딩: {url}")
            
            self.page.goto(url, wait_until='networkidle')
            time.sleep(3)  # 추가 로딩 대기
            
            html_content = self.page.content()
            return html_content
            
        except Exception as e:
            logger.error(f"Playwright 페이지 로딩 실패: {e}")
            # 폴백: requests 사용
            return self._get_fallback_content(url)
    
    def _get_fallback_content(self, url: str) -> str:
        """requests를 사용한 폴백 콘텐츠 가져오기"""
        try:
            response = self.session.get(url, timeout=self.timeout, verify=self.verify_ssl)
            response.raise_for_status()
            response.encoding = 'utf-8'
            return response.text
        except Exception as e:
            logger.error(f"폴백 페이지 로딩 실패: {e}")
            return ""
    
    def parse_list_page(self, html_content: str) -> list:
        """목록 페이지 파싱 - div 기반 구조"""
        announcements = []
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # SEIS는 div 기반 구조, menukey=7187&mode=view&seq_no= 패턴의 링크들 찾기
        detail_links = soup.find_all('a', href=re.compile(r'menukey=7187.*mode=view.*seq_no=\d+'))
        
        logger.info(f"상세 링크 {len(detail_links)}개 발견")
        
        for i, link in enumerate(detail_links):
            try:
                # URL에서 seq_no 추출
                href = link.get('href', '')
                seq_match = re.search(r'seq_no=(\d+)', href)
                if not seq_match:
                    continue
                    
                seq_no = seq_match.group(1)
                # URL 구조 수정 - /home/ 포함해야 함
                if href.startswith('/'):
                    detail_url = f"{self.base_url}{href}"
                else:
                    detail_url = urljoin(self.base_url, href)
                
                # /home/이 없으면 추가
                if '/sub.do' in detail_url and '/home/sub.do' not in detail_url:
                    detail_url = detail_url.replace('/sub.do', '/home/sub.do')
                
                # 링크 텍스트에서 정보 추출
                link_text = link.get_text(strip=True)
                
                # 카테고리와 제목 분리 (예: "사업공고 제목★(...) 2025년..." 형태)
                category = "공지"
                title = link_text
                
                # 카테고리 추출 시도
                if link_text.startswith(('사업공고', '선정결과', '안내')):
                    parts = link_text.split('\n', 1)
                    if len(parts) >= 2:
                        category = parts[0].strip()
                        remaining = parts[1].strip()
                        
                        # 제목 추출 (제목★... 형태에서 제목 부분)
                        title_match = re.search(r'제목(.+?)(?:등록일|$)', remaining, re.DOTALL)
                        if title_match:
                            title = title_match.group(1).strip()
                            title = re.sub(r'^[★☆]', '', title).strip()  # 별표 제거
                        else:
                            title = remaining
                
                # 제목 정리
                title = re.sub(r'\s+', ' ', title).strip()
                title = title.replace('\n', ' ').replace('\t', ' ')
                
                if not title:
                    title = f"공고_{seq_no}"
                
                announcement = {
                    'number': seq_no,
                    'category': category,
                    'title': title,
                    'url': detail_url,
                    'date': '',  # 목록에서 날짜 추출 가능하면 추후 개선
                    'attachment_count': 0  # 상세페이지에서 확인
                }
                
                announcements.append(announcement)
                logger.info(f"공고 추가: [{seq_no}] {category} - {title[:50]}...")
                
            except Exception as e:
                logger.error(f"공고 파싱 중 오류 (링크 {i}): {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
        return announcements
    
    def parse_detail_page(self, html_content: str) -> dict:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출 - 실제 공고 제목 찾기
        title = ""
        
        # URL에서 제목 추출 시도 (메타데이터에서)
        page_title = soup.find('title')
        if page_title:
            title_text = page_title.get_text().strip()
            if '공지사항' not in title_text and len(title_text) > 10:
                title = title_text
        
        # 본문에서 제목 추출 시도
        if not title:
            # .ck-content 내용에서 첫 번째 줄을 제목으로 사용
            ck_content = soup.select_one('.ck-content')
            if ck_content:
                content_text = ck_content.get_text(strip=True)
                lines = content_text.split('\n')
                for line in lines:
                    line = line.strip()
                    if len(line) > 10 and ('공고' in line or '모집' in line or '안내' in line):
                        title = line
                        break
        
        if not title:
            title = "제목 없음"
        
        # 본문 내용 추출 - .ck-content 우선
        content = ""
        ck_content = soup.select_one('.ck-content')
        if ck_content:
            content = self.h.handle(str(ck_content))
        
        # .ck-content가 너무 짧으면 .contentBody 사용
        if len(content.strip()) < 100:
            content_body = soup.select_one('.contentBody')
            if content_body:
                content = self.h.handle(str(content_body))
        
        # 여전히 짧으면 가장 긴 텍스트 영역 찾기
        if len(content.strip()) < 100:
            all_divs = soup.find_all('div')
            max_text = ""
            for div in all_divs:
                div_text = div.get_text(strip=True)
                if len(div_text) > len(max_text) and len(div_text) > 200:
                    # 하위 div가 없는 순수 텍스트 영역만
                    if not div.find('div'):
                        max_text = div_text
            
            if max_text:
                content = max_text
        
        # 메타 정보 추출
        date = ""
        author = ""
        
        # 등록일 추출 시도
        date_text = soup.get_text()
        date_match = re.search(r'등록일(\d{4}-\d{2}-\d{2})', date_text)
        if date_match:
            date = date_match.group(1)
        
        # 첨부파일 추출
        attachments = self._extract_attachments(soup)
        
        return {
            'title': title,
            'content': content,
            'date': date,
            'author': author,
            'attachments': attachments
        }
    
    def _extract_attachments(self, soup: BeautifulSoup) -> list:
        """첨부파일 링크 추출"""
        attachments = []
        
        # atchFileDownload.do 패턴의 다운로드 링크 찾기
        download_links = soup.find_all('a', href=re.compile(r'atchFileDownload\.do'))
        
        logger.info(f"atchFileDownload 링크 {len(download_links)}개 발견")
        
        # 중복 제거를 위한 set
        processed_urls = set()
        
        for link in download_links:
            try:
                href = link.get('href', '')
                if href in processed_urls:
                    continue
                processed_urls.add(href)
                
                # 절대 URL 생성
                if href.startswith('http'):
                    file_url = href
                else:
                    # socialenterprise.or.kr 도메인 사용
                    if 'socialenterprise.or.kr' in href:
                        file_url = href if href.startswith('http') else f"https://{href.lstrip('/')}"
                    else:
                        file_url = f"https://www.socialenterprise.or.kr/{href.lstrip('/')}"
                
                # 파일명 추출 - 여러 방법 시도
                filename = ""
                
                # 1. 링크 텍스트에서 파일명 추출
                link_text = link.get_text(strip=True)
                if link_text and link_text not in ['다운로드', 'Download', '미리보기']:
                    # .hwp, .pdf 등 확장자가 있는 경우
                    if '.' in link_text and any(ext in link_text.lower() for ext in ['.hwp', '.pdf', '.doc', '.xls', '.ppt']):
                        filename = link_text
                
                # 2. 부모 요소에서 파일명 찾기
                if not filename:
                    parent = link.parent
                    while parent and not filename:
                        parent_text = parent.get_text()
                        # 파일 확장자가 포함된 텍스트 찾기
                        file_match = re.search(r'([^/\\:*?"<>|\n\t]+\.(?:hwp|pdf|doc|docx|xls|xlsx|ppt|pptx|zip|rar))', parent_text, re.IGNORECASE)
                        if file_match:
                            filename = file_match.group(1).strip()
                            break
                        parent = parent.parent
                        if parent and parent.name in ['body', 'html']:
                            break
                
                # 3. 형제 요소에서 파일명 찾기
                if not filename:
                    siblings = link.find_next_siblings() + link.find_previous_siblings()
                    for sibling in siblings:
                        if hasattr(sibling, 'get_text'):
                            sibling_text = sibling.get_text(strip=True)
                            file_match = re.search(r'([^/\\:*?"<>|\n\t]+\.(?:hwp|pdf|doc|docx|xls|xlsx|ppt|pptx|zip|rar))', sibling_text, re.IGNORECASE)
                            if file_match:
                                filename = file_match.group(1).strip()
                                break
                
                # 4. URL에서 파일 정보 추출
                if not filename:
                    url_match = re.search(r'fileSeqNo=(\d+)', href)
                    if url_match:
                        filename = f"첨부파일_{url_match.group(1)}.hwp"
                    else:
                        filename = f"첨부파일_{len(attachments)+1}.file"
                
                # 파일명 정리
                if filename:
                    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
                    filename = re.sub(r'\s+', ' ', filename)
                    filename = filename.replace('\n', '').replace('\t', '').strip()
                    
                    # 파일명이 너무 길면 자르기
                    if len(filename) > 100:
                        name, ext = os.path.splitext(filename)
                        filename = name[:90] + ext
                
                attachment = {
                    'filename': filename,
                    'url': file_url
                }
                
                attachments.append(attachment)
                logger.info(f"첨부파일 발견: {filename} - {file_url}")
                
            except Exception as e:
                logger.error(f"첨부파일 추출 중 오류: {e}")
                continue
        
        logger.info(f"총 {len(attachments)}개 첨부파일 추출 완료")
        return attachments
    
    def download_file(self, file_url: str, save_path: str) -> bool:
        """파일 다운로드"""
        try:
            response = self.session.get(file_url, timeout=self.timeout, verify=self.verify_ssl, stream=True)
            response.raise_for_status()
            
            # 파일명 처리
            actual_filename = self._extract_filename_from_response(response, save_path)
            
            # 파일 저장
            with open(actual_filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(actual_filename)
            logger.info(f"파일 다운로드 완료: {actual_filename} ({file_size} bytes)")
            
            return True
            
        except Exception as e:
            logger.error(f"파일 다운로드 실패 {file_url}: {e}")
            return False
    
    def _extract_filename_from_response(self, response, default_path):
        """응답 헤더에서 파일명 추출 및 한글 처리"""
        save_dir = os.path.dirname(default_path)
        
        content_disposition = response.headers.get('Content-Disposition', '')
        
        if content_disposition:
            # RFC 5987 형식 우선 처리
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
                
                # 다양한 인코딩 시도
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
                html_content = self.get_page_content(list_url)
                
                if not html_content:
                    logger.error(f"페이지 {page_num} 콘텐츠 로딩 실패")
                    break
                
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
                        detail_html = self.get_page_content(announcement['url'])
                        if not detail_html:
                            continue
                        
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
                            f.write(f"- 원본 URL: {announcement['url']}\n\n")
                            f.write("## 본문\n\n")
                            f.write(detail_info['content'])
                        
                        # 첨부파일 다운로드
                        for attachment in detail_info['attachments']:
                            file_path = os.path.join(announcement_dir, attachment['filename'])
                            
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
        
        finally:
            # Playwright 정리
            self._close_playwright()
        
        return results

def test_seis_scraper(pages=3):
    """SEIS 스크래퍼 테스트"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    scraper = EnhancedSeisScraper()
    output_dir = "output/seis"
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"SEIS 스크래퍼 테스트 시작 - {pages}페이지")
    results = scraper.scrape_pages(max_pages=pages, output_base=output_dir)
    
    logger.info(f"\n{'='*50}")
    logger.info("테스트 결과 요약")
    logger.info(f"{'='*50}")
    logger.info(f"처리된 페이지: {results['pages_processed']}")
    logger.info(f"총 공고 수: {results['total_announcements']}")
    logger.info(f"총 파일 수: {results['total_files']}")
    logger.info(f"다운로드 성공: {results['successful_downloads']}")
    logger.info(f"다운로드 실패: {results['failed_downloads']}")
    
    if results['total_files'] > 0:
        success_rate = (results['successful_downloads'] / results['total_files']) * 100
        logger.info(f"성공률: {success_rate:.1f}%")

if __name__ == "__main__":
    test_seis_scraper(3)