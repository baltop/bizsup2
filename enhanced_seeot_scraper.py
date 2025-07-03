# -*- coding: utf-8 -*-
"""
서울동부고용노동지청지원단(SEEOT) 공고 스크래퍼 - Enhanced 버전
URL: https://seeot.or.kr/alarm/notice/
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

class EnhancedSeeotScraper(EnhancedBaseScraper):
    """서울동부고용노동지청지원단 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        # 기본 설정
        self.base_url = "https://seeot.or.kr"
        self.list_url = "https://seeot.or.kr/alarm/notice/"
        
        # 사이트별 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 60
        self.delay_between_requests = 2  # 사이트 부하 방지
        self.delay_between_pages = 3  # 페이지 간 대기 시간
        
        # SEEOT 특화 설정 - Playwright 사용 (WordPress 기반)
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
            return f"{self.list_url}page/{page_num}/"
    
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
        """목록 페이지 파싱 - WordPress Breakdance 기반 구조"""
        announcements = []
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # SEEOT 공고 링크 패턴 찾기 - bde-container-link 클래스의 breakdance-link
        notice_links = soup.find_all('a', class_='breakdance-link')
        
        # 공고 링크만 필터링 (Korean URL 인코딩된 것들)
        filtered_links = []
        for link in notice_links:
            href = link.get('href', '')
            if (href.startswith('https://seeot.or.kr/') and 
                href != 'https://seeot.or.kr/alarm/notice/' and
                'wp-content' not in href and
                'wp-admin' not in href and
                'wp-json' not in href and
                'xmlrpc' not in href and
                '%' in href):  # Korean URL 인코딩이 있는 것들
                filtered_links.append(link)
        
        logger.info(f"공고 링크 {len(filtered_links)}개 발견")
        
        for i, link in enumerate(filtered_links):
            try:
                href = link.get('href', '')
                detail_url = href
                
                # 링크의 내부 구조에서 정보 추출
                # 각 링크는 컨테이너 안에 카테고리, 제목, 날짜가 구조화되어 있음
                
                # 카테고리 찾기 (bde-text 클래스)
                category_elem = link.find(class_=re.compile(r'bde-text.*10289-102'))
                category = category_elem.get_text(strip=True) if category_elem else "공지"
                
                # 제목 찾기 (bde-heading 클래스)
                title_elem = link.find(class_=re.compile(r'bde-heading.*10289-101'))
                title = title_elem.get_text(strip=True) if title_elem else ""
                
                # 날짜 찾기 (bde-text 클래스 중 날짜 패턴)
                date_elem = link.find(class_=re.compile(r'bde-text.*10289-103'))
                date = date_elem.get_text(strip=True) if date_elem else ""
                
                # 제목이 없으면 URL에서 추출
                if not title:
                    try:
                        decoded_url = unquote(href, encoding='utf-8')
                        url_parts = [part for part in decoded_url.split('/') if part]
                        if url_parts:
                            last_part = url_parts[-1]
                            # 한국어 제목에서 키워드 추출
                            keywords = re.findall(r'[가-힣]+', last_part)
                            if keywords:
                                title = ' '.join(keywords[:5])  # 처음 5개 단어
                            else:
                                title = last_part.replace('-', ' ')[:50]
                    except:
                        title = f"공고_{i+1}"
                
                # URL에서 고유 ID 추출
                number = str(i + 1)  # 기본값
                try:
                    decoded_url = unquote(href, encoding='utf-8')
                    url_parts = [part for part in decoded_url.split('/') if part]
                    if url_parts:
                        last_part = url_parts[-1]
                        # 한국어 제목에서 첫 번째 키워드 추출
                        keywords = re.findall(r'[가-힣]+', last_part)
                        if keywords:
                            number = keywords[0][:8]  # 첫 8글자만
                        else:
                            # 영문이나 숫자가 있으면 사용
                            clean_part = re.sub(r'[^a-zA-Z0-9가-힣]', '', last_part)
                            number = clean_part[:10] if clean_part else str(i + 1)
                except:
                    pass
                
                announcement = {
                    'number': number,
                    'category': category,
                    'title': title,
                    'url': detail_url,
                    'date': date,
                    'attachment_count': 0  # 상세페이지에서 확인
                }
                
                announcements.append(announcement)
                logger.info(f"공고 추가: [{number}] {category} - {title[:50]}...")
                
            except Exception as e:
                logger.error(f"공고 파싱 중 오류 (링크 {i}): {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
        return announcements
    
    def parse_detail_page(self, html_content: str) -> dict:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출 - WordPress 기본 구조
        title = ""
        
        # 페이지 타이틀에서 추출
        page_title = soup.find('title')
        if page_title:
            title_text = page_title.get_text().strip()
            # 사이트 명 제거
            title_parts = title_text.split(' - ')
            if len(title_parts) > 1:
                title = title_parts[0].strip()
            else:
                title = title_text
        
        # h1, h2 태그에서 제목 찾기
        if not title or len(title) < 10:
            for tag in ['h1', 'h2', 'h3']:
                title_elem = soup.find(tag)
                if title_elem:
                    candidate = title_elem.get_text(strip=True)
                    if len(candidate) > len(title):
                        title = candidate
                        break
        
        if not title:
            title = "제목 없음"
        
        # 본문 내용 추출 - WordPress 구조에 맞게
        content = ""
        
        # WordPress 일반적인 본문 클래스들
        content_selectors = [
            '.post-content',
            '.entry-content',
            '.content',
            '.article-content',
            '.post-body',
            '.single-content',
            'article .content',
            'main .content'
        ]
        
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem and len(content_elem.get_text(strip=True)) > 100:
                content = self.h.handle(str(content_elem))
                break
        
        # 본문이 없으면 가장 긴 텍스트 영역 찾기
        if len(content.strip()) < 50:
            all_divs = soup.find_all('div')
            max_text = ""
            for div in all_divs:
                div_text = div.get_text(strip=True)
                if (len(div_text) > len(max_text) and 
                    len(div_text) > 200 and
                    not div.find('div')):  # 하위 div가 없는 순수 텍스트 영역
                    max_text = div_text
            
            if max_text:
                content = max_text
        
        # 날짜 추출
        date = ""
        date_selectors = [
            '.date',
            '.post-date',
            '.entry-date',
            '[class*="date"]',
            'time'
        ]
        
        for selector in date_selectors:
            date_elem = soup.select_one(selector)
            if date_elem:
                date_text = date_elem.get_text(strip=True)
                # 날짜 패턴 추출
                date_match = re.search(r'(\d{4}[-년]\d{1,2}[-월]\d{1,2})', date_text)
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
        """첨부파일 링크 추출"""
        attachments = []
        
        # WordPress 첨부파일 패턴들
        attachment_patterns = [
            'a[href*="wp-content/uploads"]',  # WordPress 업로드 파일
            'a[href*="download"]',
            'a[href*="attach"]',
            'a[href*="file"]'
        ]
        
        for pattern in attachment_patterns:
            download_links = soup.select(pattern)
            
            for link in download_links:
                try:
                    href = link.get('href', '')
                    if not href:
                        continue
                    
                    # 절대 URL 생성
                    if href.startswith('http'):
                        file_url = href
                    else:
                        file_url = urljoin(self.base_url, href)
                    
                    # 파일명 추출
                    filename = ""
                    
                    # 1. 링크 텍스트에서 파일명 추출
                    link_text = link.get_text(strip=True)
                    if link_text and any(ext in link_text.lower() for ext in ['.pdf', '.hwp', '.doc', '.xls', '.ppt']):
                        filename = link_text
                    
                    # 2. URL에서 파일명 추출
                    if not filename:
                        url_path = urlparse(file_url).path
                        if '/' in url_path:
                            potential_filename = url_path.split('/')[-1]
                            if '.' in potential_filename:
                                filename = unquote(potential_filename)
                    
                    # 3. 부모 요소에서 파일명 찾기
                    if not filename:
                        parent = link.parent
                        if parent:
                            parent_text = parent.get_text()
                            file_match = re.search(r'([^/\\:*?"<>|\n\t]+\.(?:pdf|hwp|doc|docx|xls|xlsx|ppt|pptx|zip|rar))', parent_text, re.IGNORECASE)
                            if file_match:
                                filename = file_match.group(1).strip()
                    
                    # 4. 기본 파일명 생성
                    if not filename:
                        filename = f"첨부파일_{len(attachments)+1}.file"
                    
                    # 파일명 정리
                    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
                    filename = re.sub(r'\s+', ' ', filename).strip()
                    
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
        
        finally:
            # Playwright 정리
            self._close_playwright()
        
        return results

def test_seeot_scraper(pages=3):
    """SEEOT 스크래퍼 테스트"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    scraper = EnhancedSeeotScraper()
    output_dir = "output/seeot"
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"SEEOT 스크래퍼 테스트 시작 - {pages}페이지")
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
    test_seeot_scraper(3)