#!/usr/bin/env python3
"""
Enhanced CBIST (Chungbuk Institute of Science & Technology) Scraper
Site: http://www.cbist.or.kr/home/sub.do?mncd=1131
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

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cbist_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CBISTScraper:
    def __init__(self, base_url="http://www.cbist.or.kr", site_code="cbist"):
        self.base_url = base_url
        self.site_code = site_code
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
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
        
    def get_page_content(self, url):
        """페이지 내용 가져오기"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            response.encoding = 'utf-8'
            return response.text
        except requests.RequestException as e:
            logger.error(f"페이지 요청 실패: {url}, 에러: {e}")
            return None
    
    def parse_post_list(self, html_content):
        """게시글 목록 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        posts = []
        
        # 테이블에서 게시글 목록 찾기
        board_table = soup.find('table', class_='board')
        if not board_table:
            logger.warning("게시판 테이블을 찾을 수 없습니다.")
            return posts
            
        tbody = board_table.find('tbody')
        if not tbody:
            logger.warning("게시판 tbody를 찾을 수 없습니다.")
            return posts
            
        rows = tbody.find_all('tr')
        
        for row in rows:
            try:
                # 제목 링크 찾기
                title_cell = row.find('td', class_='board_title')
                if not title_cell:
                    continue
                    
                title_link = title_cell.find('a', class_='title')
                if not title_link:
                    continue
                    
                title = title_link.get_text(strip=True)
                href = title_link.get('href')
                
                # 번호 추출 (URL에서)
                post_id = None
                if href and 'no=' in href:
                    post_id = href.split('no=')[1].split('&')[0]
                
                # 작성자 추출
                writer_cell = row.find('td', class_='board_write')
                writer = writer_cell.get_text(strip=True) if writer_cell else '관리자'
                
                # 등록일 추출
                date_cells = row.find_all('td', class_='board_date')
                reg_date = date_cells[0].get_text(strip=True) if date_cells else ''
                
                # 공고 기간 추출
                notice_period = ''
                if len(date_cells) > 1:
                    notice_period = date_cells[1].get_text(strip=True)
                
                # 공고 상태 추출
                status_cell = row.find('td', class_='board_status')
                status = status_cell.get_text(strip=True) if status_cell else ''
                
                # 첨부파일 여부 확인
                file_cell = row.find('td', class_='board_file')
                has_attachment = bool(file_cell and file_cell.find('a'))
                
                if title and href and post_id:
                    posts.append({
                        'id': post_id,
                        'title': title,
                        'href': href,
                        'writer': writer,
                        'reg_date': reg_date,
                        'notice_period': notice_period,
                        'status': status,
                        'has_attachment': has_attachment
                    })
                    
            except Exception as e:
                logger.error(f"게시글 파싱 중 오류: {e}")
                continue
                
        logger.info(f"총 {len(posts)}개의 게시글을 파싱했습니다.")
        return posts
    
    def get_post_detail(self, post_href):
        """게시글 상세 내용 가져오기"""
        if post_href.startswith('http'):
            full_url = post_href
        else:
            # 상대 URL을 절대 URL로 변환
            full_url = f"{self.base_url}/home/sub.do{post_href}"
        
        logger.info(f"상세 페이지 URL: {full_url}")
        html_content = self.get_page_content(full_url)
        
        if not html_content:
            return None, []
            
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 게시글 내용 추출
        content_cell = soup.find('td', class_='substance')
        if not content_cell:
            logger.warning(f"게시글 내용을 찾을 수 없습니다: {post_href}")
            return None, []
            
        # 내용을 마크다운으로 변환
        content_html = str(content_cell)
        content_markdown = self.h2t.handle(content_html)
        
        # 첨부파일 추출
        attachments = []
        file_divs = soup.find_all('div', id=re.compile(r'fileDiv\d+'))
        
        for file_div in file_divs:
            file_link = file_div.find('a')
            if file_link:
                file_href = file_link.get('href')
                file_name = file_link.get_text(strip=True)
                
                # 파일 아이콘 텍스트 제거
                if file_name.startswith('붙임'):
                    file_name = file_name
                else:
                    # 아이콘 텍스트 제거
                    file_name = re.sub(r'^[^가-힣a-zA-Z0-9]+', '', file_name)
                
                if file_href and file_name:
                    # 첨부파일 URL 수정
                    if file_href.startswith('/'):
                        file_url = f"{self.base_url}{file_href}"
                    else:
                        file_url = f"{self.base_url}/home/{file_href}"
                    
                    attachments.append({
                        'name': file_name,
                        'url': file_url
                    })
        
        return content_markdown, attachments
    
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
            
            # 파일 저장
            file_path = attachments_dir / filename
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"첨부파일 다운로드 완료: {filename} ({len(response.content)} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"첨부파일 다운로드 실패: {filename}, 에러: {e}")
            return False
    
    def save_post_content(self, post_id, title, content, attachments):
        """게시글 내용 저장"""
        # 안전한 디렉토리 이름 생성
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
        safe_title = safe_title[:100]  # 길이 제한
        
        post_dir = self.output_dir / f"{post_id}_{safe_title}"
        post_dir.mkdir(exist_ok=True)
        
        # 내용 저장
        content_file = post_dir / "content.md"
        with open(content_file, 'w', encoding='utf-8') as f:
            f.write(f"# {title}\n\n")
            f.write(f"**게시글 ID:** {post_id}\n")
            f.write(f"**수집 시간:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")
            f.write(content)
        
        # 첨부파일 다운로드
        successful_downloads = 0
        for attachment in attachments:
            if self.download_attachment(attachment['url'], attachment['name'], post_dir):
                successful_downloads += 1
        
        logger.info(f"게시글 저장 완료: {title} (첨부파일 {successful_downloads}/{len(attachments)})")
        return successful_downloads
    
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
            
            # 게시글 상세 내용 가져오기
            content, attachments = self.get_post_detail(post['href'])
            if content is None:
                continue
            
            # 게시글 저장
            self.save_post_content(post['id'], post['title'], content, attachments)
            processed_count += 1
            self.scraped_count += 1
            
            # 요청 간격 조절
            time.sleep(1)
            
        logger.info(f"페이지 처리 완료: {processed_count}개 게시글 처리")
        return processed_count
    
    def get_next_page_url(self, current_url, page_num):
        """다음 페이지 URL 생성"""
        if '?' in current_url:
            return f"{current_url}&page={page_num}"
        else:
            return f"{current_url}?page={page_num}"
    
    def scrape_multiple_pages(self, start_url, max_pages=3):
        """여러 페이지 스크래핑"""
        logger.info(f"다중 페이지 스크래핑 시작: {max_pages}페이지")
        
        for page_num in range(1, max_pages + 1):
            if page_num == 1:
                page_url = start_url
            else:
                page_url = self.get_next_page_url(start_url, page_num)
            
            logger.info(f"페이지 {page_num}/{max_pages} 처리 중...")
            
            count = self.scrape_page(page_url)
            if count == 0:
                logger.warning(f"페이지 {page_num}에서 게시글을 찾을 수 없습니다.")
                break
                
            # 페이지 간 간격
            if page_num < max_pages:
                time.sleep(2)
        
        logger.info(f"스크래핑 완료: 총 {self.scraped_count}개 게시글 처리")
        return self.scraped_count

def main():
    """메인 실행 함수"""
    # 시작 URL
    start_url = "http://www.cbist.or.kr/home/sub.do?mncd=1131"
    
    # 스크래퍼 인스턴스 생성
    scraper = CBISTScraper()
    
    try:
        # 3페이지까지 스크래핑
        total_count = scraper.scrape_multiple_pages(start_url, max_pages=3)
        
        print(f"\n=== 스크래핑 완료 ===")
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