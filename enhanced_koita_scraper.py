#!/usr/bin/env python3
"""
Enhanced KOITA (한국IT서비스산업협회) Scraper
Site: https://www.koita.or.kr/board/commBoardLCRnDList.do
"""

import os
import sys
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import html2text
import re
from pathlib import Path
import logging
from datetime import datetime
import json
from requests.exceptions import RequestException, Timeout, ConnectionError

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('koita_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class KOITAScraper:
    def __init__(self, base_url="https://www.koita.or.kr", site_code="koita"):
        self.base_url = base_url
        self.site_code = site_code
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # 출력 디렉토리 설정
        self.output_dir = Path(f"output/{site_code}")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # HTML to Markdown 변환기 설정
        self.h2t = html2text.HTML2Text()
        self.h2t.ignore_links = False
        self.h2t.ignore_images = False
        self.h2t.body_width = 0
        
        self.scraped_count = 0
        self.processed_ids = set()
        self.processed_titles = []
        
        # 외부 사이트별 처리 전략
        self.external_handlers = {
            'didp.or.kr': self.handle_didp_site,
            'aica-gj.kr': self.handle_aica_site,
            'djtp.or.kr': self.handle_djtp_site,
            'gtp.or.kr': self.handle_gtp_site,
            'dtp.or.kr': self.handle_dtp_site,
            'itp.or.kr': self.handle_itp_site,
            'btp.or.kr': self.handle_btp_site,
            'default': self.handle_default_site
        }
        
    def get_page_content(self, url):
        """페이지 내용 가져오기"""
        try:
            logger.info(f"페이지 요청 중: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            response.encoding = 'utf-8'
            return response.text
        except RequestException as e:
            logger.error(f"페이지 요청 실패: {url}, 에러: {e}")
            return None
    
    def parse_post_list(self, html_content):
        """게시글 목록 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        posts = []
        
        # 테이블에서 게시글 목록 찾기
        table = soup.find('table', class_='tb tb_col tb_bd tb_st01')
        if not table:
            logger.warning("게시판 테이블을 찾을 수 없습니다.")
            return posts
            
        tbody = table.find('tbody')
        if not tbody:
            logger.warning("게시판 tbody를 찾을 수 없습니다.")
            return posts
            
        rows = tbody.find_all('tr')
        
        for row in rows:
            try:
                cells = row.find_all('td')
                if len(cells) < 5:
                    continue
                
                # 순번, 지자체, 사업명, 공고일, 신청기한
                seq_cell = cells[0]
                region_cell = cells[1]
                title_cell = cells[2]
                announce_date_cell = cells[3]
                deadline_cell = cells[4]
                
                # 사업명 링크 찾기
                title_link = title_cell.find('a')
                if not title_link:
                    continue
                    
                title = title_link.get_text(strip=True)
                href = title_link.get('href')
                
                # 다른 정보 추출
                sequence = seq_cell.get_text(strip=True)
                region = region_cell.get_text(strip=True)
                announce_date = announce_date_cell.get_text(strip=True)
                deadline = deadline_cell.get_text(strip=True)
                
                if title and href:
                    posts.append({
                        'id': sequence,
                        'sequence': sequence,
                        'title': title,
                        'region': region,
                        'announce_date': announce_date,
                        'deadline': deadline,
                        'external_url': href
                    })
                    
            except Exception as e:
                logger.error(f"게시글 파싱 중 오류: {e}")
                continue
                
        logger.info(f"총 {len(posts)}개의 게시글을 파싱했습니다.")
        return posts
    
    def handle_didp_site(self, url):
        """DIDP 사이트 처리"""
        try:
            html_content = self.get_page_content(url)
            if not html_content:
                return None, []
                
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 제목 추출
            title_element = soup.find('h3', class_='tit') or soup.find('h2') or soup.find('h1')
            
            # 본문 추출
            content_selectors = [
                '.board-detail',
                '.board-content',
                '.view-content',
                '.content',
                '.article-content'
            ]
            
            content_element = None
            for selector in content_selectors:
                content_element = soup.select_one(selector)
                if content_element:
                    break
            
            if not content_element:
                content_element = soup.find('div', class_='view')
                
            if content_element:
                content_html = str(content_element)
                content_markdown = self.h2t.handle(content_html)
            else:
                content_markdown = "내용을 찾을 수 없습니다."
                
            # 첨부파일 찾기
            attachments = []
            attachment_links = soup.find_all('a', href=True)
            for link in attachment_links:
                href = link.get('href')
                if href and ('download' in href or 'attach' in href or 'file' in href):
                    file_name = link.get_text(strip=True)
                    if href.startswith('/'):
                        file_url = urljoin(url, href)
                    else:
                        file_url = href
                    attachments.append({
                        'name': file_name,
                        'url': file_url
                    })
                    
            return content_markdown, attachments
            
        except Exception as e:
            logger.error(f"DIDP 사이트 처리 중 오류: {e}")
            return None, []
    
    def handle_aica_site(self, url):
        """AICA 사이트 처리"""
        return self.handle_default_site(url)
    
    def handle_djtp_site(self, url):
        """DJTP 사이트 처리"""
        return self.handle_default_site(url)
    
    def handle_gtp_site(self, url):
        """GTP 사이트 처리"""
        return self.handle_default_site(url)
    
    def handle_dtp_site(self, url):
        """DTP 사이트 처리"""
        return self.handle_default_site(url)
    
    def handle_itp_site(self, url):
        """ITP 사이트 처리"""
        return self.handle_default_site(url)
    
    def handle_btp_site(self, url):
        """BTP 사이트 처리"""
        return self.handle_default_site(url)
    
    def handle_default_site(self, url):
        """기본 사이트 처리"""
        try:
            html_content = self.get_page_content(url)
            if not html_content:
                return None, []
                
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 제목 추출
            title_element = soup.find('h1') or soup.find('h2') or soup.find('h3')
            
            # 본문 추출 - 다양한 선택자 시도
            content_selectors = [
                '.board-detail',
                '.board-content',
                '.view-content',
                '.content',
                '.article-content',
                '.view',
                '.post-content',
                '.notice-content',
                '#content',
                '.main-content'
            ]
            
            content_element = None
            for selector in content_selectors:
                content_element = soup.select_one(selector)
                if content_element:
                    break
            
            if content_element:
                content_html = str(content_element)
                content_markdown = self.h2t.handle(content_html)
            else:
                # 기본 내용이 없다면 제목과 기본 정보만 추출
                content_markdown = f"# 외부 사이트 연결\\n\\n원본 URL: {url}\\n\\n내용을 자동으로 추출할 수 없습니다."
                
            # 첨부파일 찾기 - 다양한 패턴 시도
            attachments = []
            attachment_selectors = [
                'a[href*="download"]',
                'a[href*="file"]',
                'a[href*="attach"]',
                '.attachment a',
                '.file-list a',
                '.download-link'
            ]
            
            for selector in attachment_selectors:
                attachment_links = soup.select(selector)
                for link in attachment_links:
                    href = link.get('href')
                    if href and not href.startswith('javascript'):
                        file_name = link.get_text(strip=True)
                        if not file_name or file_name in ['다운로드', 'download', '첨부파일']:
                            file_name = href.split('/')[-1]
                        
                        if href.startswith('/'):
                            file_url = urljoin(url, href)
                        else:
                            file_url = href
                        
                        attachments.append({
                            'name': file_name,
                            'url': file_url
                        })
            
            # 중복 제거
            unique_attachments = []
            seen_urls = set()
            for att in attachments:
                if att['url'] not in seen_urls:
                    unique_attachments.append(att)
                    seen_urls.add(att['url'])
                    
            return content_markdown, unique_attachments
            
        except Exception as e:
            logger.error(f"기본 사이트 처리 중 오류: {e}")
            return None, []
    
    def get_external_content(self, external_url):
        """외부 사이트에서 콘텐츠 가져오기"""
        try:
            domain = urlparse(external_url).netloc
            
            # 도메인별 처리기 선택
            handler = self.external_handlers.get('default')
            for domain_key, domain_handler in self.external_handlers.items():
                if domain_key != 'default' and domain_key in domain:
                    handler = domain_handler
                    break
            
            logger.info(f"외부 사이트 처리 중: {external_url}")
            return handler(external_url)
            
        except Exception as e:
            logger.error(f"외부 사이트 처리 실패: {external_url}, 에러: {e}")
            return None, []
    
    def download_attachment(self, url, filename, post_dir):
        """첨부파일 다운로드"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # HTML 응답 감지
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' in content_type:
                logger.warning(f"HTML 페이지 응답 감지: {filename}")
                return False
                
            # 파일 크기 검증
            if len(response.content) < 1024:  # 1KB 미만
                if b'<html' in response.content.lower() or b'<!doctype' in response.content.lower():
                    logger.warning(f"HTML 페이지 감지 (크기: {len(response.content)}bytes): {filename}")
                    return False
            
            # 첨부파일 디렉토리 생성
            attachments_dir = post_dir / "attachments"
            attachments_dir.mkdir(exist_ok=True)
            
            # 안전한 파일명 생성
            safe_filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
            if not safe_filename:
                safe_filename = f"attachment_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # 파일 저장
            file_path = attachments_dir / safe_filename
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"첨부파일 다운로드 완료: {safe_filename} ({len(response.content)} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"첨부파일 다운로드 실패: {filename}, 에러: {e}")
            return False
    
    def save_post_content(self, post, content, attachments):
        """게시글 내용 저장"""
        # 안전한 디렉토리 이름 생성
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', post['title'])
        safe_title = safe_title[:100]  # 길이 제한
        
        # 게시글 번호와 제목으로 폴더명 생성
        post_dir = self.output_dir / f"{post['sequence']}_{safe_title}"
        post_dir.mkdir(exist_ok=True)
        
        # 메타데이터 저장
        metadata = {
            'koita_metadata': {
                'sequence': post['sequence'],
                'title': post['title'],
                'region': post['region'],
                'announce_date': post['announce_date'],
                'deadline': post['deadline'],
                'external_url': post['external_url'],
                'scraped_at': datetime.now().isoformat()
            }
        }
        
        metadata_file = post_dir / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        # 내용 저장
        content_file = post_dir / "content.md"
        with open(content_file, 'w', encoding='utf-8') as f:
            f.write(f"# {post['title']}\\n\\n")
            f.write(f"**지역:** {post['region']}\\n")
            f.write(f"**공고일:** {post['announce_date']}\\n")
            f.write(f"**신청기한:** {post['deadline']}\\n")
            f.write(f"**외부 URL:** {post['external_url']}\\n")
            f.write(f"**수집 시간:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n\\n")
            f.write("---\\n\\n")
            if content:
                f.write(content)
            else:
                f.write("외부 사이트 내용을 가져올 수 없습니다.")
        
        # 첨부파일 다운로드
        successful_downloads = 0
        for attachment in attachments:
            if self.download_attachment(attachment['url'], attachment['name'], post_dir):
                successful_downloads += 1
        
        logger.info(f"게시글 저장 완료: {post['title']} (첨부파일 {successful_downloads}/{len(attachments)})")
        return successful_downloads
    
    def save_processed_titles(self):
        """처리된 제목 정보를 JSON 파일로 저장"""
        try:
            json_file = self.output_dir / f"processed_titles_enhanced{self.site_code}.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(self.processed_titles, f, ensure_ascii=False, indent=2)
            logger.info(f"처리된 제목 정보 저장 완료: {json_file}")
        except Exception as e:
            logger.error(f"processed_titles_enhanced{self.site_code}.json 저장 실패: {e}")
    
    def get_next_page_url(self, base_url, page_num):
        """다음 페이지 URL 생성"""
        return f"{base_url}?page={page_num}"
    
    def scrape_page(self, page_url):
        """페이지 스크래핑"""
        logger.info(f"페이지 스크래핑 시작: {page_url}")
        
        html_content = self.get_page_content(page_url)
        if not html_content:
            return 0
            
        posts = self.parse_post_list(html_content)
        processed_count = 0
        
        for post in posts:
            if post['id'] in self.processed_ids:
                continue
                
            self.processed_ids.add(post['id'])
            
            logger.info(f"게시글 처리 중: {post['title']}")
            
            # 외부 사이트에서 콘텐츠 가져오기
            content, attachments = self.get_external_content(post['external_url'])
            
            # 게시글 저장
            self.save_post_content(post, content, attachments)
            
            # 처리된 제목 정보 저장
            self.processed_titles.append({
                'id': post['id'],
                'sequence': post['sequence'],
                'title': post['title'],
                'region': post['region'],
                'announce_date': post['announce_date'],
                'deadline': post['deadline'],
                'external_url': post['external_url'],
                'scraped_at': datetime.now().isoformat()
            })
            
            processed_count += 1
            self.scraped_count += 1
            
            # 요청 간격 조절
            time.sleep(2)
            
        logger.info(f"페이지 처리 완료: {processed_count}개 게시글 처리")
        return processed_count
    
    def scrape_multiple_pages(self, start_url, max_pages=3):
        """여러 페이지 스크래핑"""
        logger.info(f"다중 페이지 스크래핑 시작: {max_pages}페이지")
        
        for page_num in range(1, max_pages + 1):
            page_url = self.get_next_page_url(start_url, page_num)
            
            logger.info(f"페이지 {page_num}/{max_pages} 처리 중...")
            
            count = self.scrape_page(page_url)
            if count == 0:
                logger.warning(f"페이지 {page_num}에서 게시글을 찾을 수 없습니다.")
                break
                
            # 페이지 간 간격
            if page_num < max_pages:
                time.sleep(3)
        
        # processed_titles.json 파일 저장
        self.save_processed_titles()
        
        logger.info(f"스크래핑 완료: 총 {self.scraped_count}개 게시글 처리")
        return self.scraped_count

def main():
    """메인 실행 함수"""
    # 시작 URL
    start_url = "https://www.koita.or.kr/board/commBoardLCRnDList.do"
    
    # 스크래퍼 인스턴스 생성
    scraper = KOITAScraper()
    
    try:
        # 3페이지까지 스크래핑
        total_count = scraper.scrape_multiple_pages(start_url, max_pages=3)
        
        print(f"\\n=== 스크래핑 완료 ===")
        print(f"총 처리된 게시글: {total_count}개")
        print(f"출력 디렉토리: {scraper.output_dir}")
        
        # 결과 요약
        if scraper.output_dir.exists():
            post_dirs = [d for d in scraper.output_dir.iterdir() if d.is_dir()]
            print(f"저장된 게시글 폴더: {len(post_dirs)}개")
            
            # 첨부파일 통계
            total_attachments = 0
            for post_dir in post_dirs:
                attachments_dir = post_dir / "attachments"
                if attachments_dir.exists():
                    total_attachments += len(list(attachments_dir.iterdir()))
            
            print(f"다운로드된 첨부파일: {total_attachments}개")
        
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단되었습니다.")
    except Exception as e:
        logger.error(f"스크래핑 중 오류 발생: {e}")
        raise

if __name__ == "__main__":
    main()