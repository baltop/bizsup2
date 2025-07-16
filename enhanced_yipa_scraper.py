#!/usr/bin/env python3
"""
Enhanced YIPA (영월산업진흥원) Scraper
Site: https://mybiz.yipa.or.kr/yipa/bbs_list.do?code=sub01b&keyvalue=sub01
"""

import os
import sys
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
import html2text
import re
from pathlib import Path
import logging
from datetime import datetime
import json
from requests.exceptions import RequestException
import uuid

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('yipa_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class YIPAScraper:
    def __init__(self, base_url="https://mybiz.yipa.or.kr", site_code="yipa"):
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
        
        # 게시글 링크 찾기
        post_links = soup.find_all('a', href=lambda x: x and 'bbs_view' in x)
        
        for link in post_links:
            try:
                href = link.get('href')
                title = link.get_text(strip=True)
                
                if not href or not title:
                    continue
                
                # URL 끝의 ||는 제거
                if href.endswith('||'):
                    href = href[:-2]
                
                # 절대 URL 생성
                if href.startswith('/'):
                    full_url = self.base_url + href
                else:
                    full_url = urljoin(self.base_url, href)
                
                # URL에서 파라미터 추출하여 ID 생성
                parsed_url = urlparse(full_url)
                params = parse_qs(parsed_url.query)
                bbs_data = params.get('bbs_data', [''])[0]
                
                # ID는 bbs_data를 사용하거나 링크의 해시값 사용
                post_id = bbs_data if bbs_data else str(hash(full_url))
                
                # 게시글 번호 추출 (링크 텍스트에서 숫자 추출 시도)
                post_number = re.search(r'^\d+', title)
                if post_number:
                    post_number = post_number.group()
                else:
                    post_number = str(len(posts) + 1)
                
                posts.append({
                    'id': post_id,
                    'number': post_number,
                    'title': title,
                    'href': full_url,
                    'bbs_data': bbs_data
                })
                
            except Exception as e:
                logger.error(f"게시글 링크 파싱 중 오류: {e}")
                continue
        
        logger.info(f"총 {len(posts)}개의 게시글을 파싱했습니다.")
        return posts
    
    def get_post_detail(self, post_url):
        """게시글 상세 내용 가져오기"""
        html_content = self.get_page_content(post_url)
        
        if not html_content:
            return None, [], None, None
            
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 첫 번째 테이블에서 정보 추출
        main_table = soup.find('table')
        if not main_table:
            logger.warning("메인 테이블을 찾을 수 없습니다.")
            return None, [], None, None
        
        rows = main_table.find_all('tr')
        
        # 기본값 설정
        title = ""
        author = ""
        date = ""
        content = ""
        
        try:
            # 첫 번째 행: 제목
            if len(rows) > 0:
                title_cell = rows[0].find('td')
                if title_cell:
                    title = title_cell.get_text(strip=True)
            
            # 두 번째 행: 작성자 및 날짜
            if len(rows) > 1:
                author_cell = rows[1].find('td')
                if author_cell:
                    author_text = author_cell.get_text(strip=True)
                    # 작성자와 날짜 분리
                    if '작성일' in author_text:
                        parts = author_text.split('작성일')
                        if len(parts) == 2:
                            author = parts[0].strip()
                            date = parts[1].strip()
                    else:
                        author = author_text
            
            # 마지막 행: 본문 내용
            if len(rows) > 3:
                content_cell = rows[3].find('td')
                if content_cell:
                    content_html = str(content_cell)
                    content = self.h2t.handle(content_html)
            
        except Exception as e:
            logger.error(f"게시글 상세 정보 파싱 중 오류: {e}")
        
        # 첨부파일 링크 찾기
        attachments = []
        attachment_links = soup.find_all('a', href=lambda x: x and 'download' in x)
        
        for link in attachment_links:
            try:
                href = link.get('href')
                if not href:
                    continue
                
                # 파일명 추출
                file_name = link.get_text(strip=True)
                if not file_name:
                    # URL에서 파일명 추출 시도
                    file_name = href.split('=')[-1] if '=' in href else 'attachment'
                
                # 절대 URL 생성
                if href.startswith('/'):
                    file_url = self.base_url + href
                else:
                    file_url = urljoin(self.base_url, href)
                
                attachments.append({
                    'name': file_name,
                    'url': file_url
                })
                
            except Exception as e:
                logger.error(f"첨부파일 링크 파싱 중 오류: {e}")
                continue
        
        return content, attachments, author, date
    
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
                safe_filename = f"attachment_{uuid.uuid4().hex[:8]}"
            
            # 파일명이 너무 길면 자르기
            if len(safe_filename) > 200:
                name_part = safe_filename[:180]
                ext_part = safe_filename[-20:] if '.' in safe_filename[-20:] else ''
                safe_filename = name_part + ext_part
            
            # 파일 저장
            file_path = attachments_dir / safe_filename
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"첨부파일 다운로드 완료: {safe_filename} ({len(response.content)} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"첨부파일 다운로드 실패: {filename}, 에러: {e}")
            return False
    
    def save_post_content(self, post, content, attachments, author, date):
        """게시글 내용 저장"""
        # 안전한 디렉토리 이름 생성
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', post['title'])
        safe_title = safe_title[:100]  # 길이 제한
        
        # 게시글 번호와 제목으로 폴더명 생성
        post_dir = self.output_dir / f"{post['number']}_{safe_title}"
        post_dir.mkdir(exist_ok=True)
        
        # 내용 저장
        content_file = post_dir / "content.md"
        with open(content_file, 'w', encoding='utf-8') as f:
            f.write(f"# {post['title']}\\n\\n")
            f.write(f"**게시글 번호:** {post['number']}\\n")
            f.write(f"**게시글 ID:** {post['id']}\\n")
            if author:
                f.write(f"**작성자:** {author}\\n")
            if date:
                f.write(f"**작성일:** {date}\\n")
            f.write(f"**URL:** {post['href']}\\n")
            f.write(f"**수집 시간:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n\\n")
            f.write("---\\n\\n")
            if content:
                f.write(content)
            else:
                f.write("내용이 없습니다. 첨부파일을 확인해주세요.")
        
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
        # 현재 URL에서 파라미터 유지하면서 페이지 번호 추가/변경
        if 'page=' in base_url:
            # 이미 page 파라미터가 있으면 교체
            import re
            return re.sub(r'page=\d+', f'page={page_num}', base_url)
        else:
            # page 파라미터가 없으면 추가
            separator = '&' if '?' in base_url else '?'
            return f"{base_url}{separator}page={page_num}"
    
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
            content, attachments, author, date = self.get_post_detail(post['href'])
            if content is None:
                # 내용이 없어도 메타데이터는 저장
                content = "내용을 가져올 수 없습니다."
                attachments = []
            
            # 게시글 저장
            self.save_post_content(post, content, attachments, author, date)
            
            # 처리된 제목 정보 저장
            self.processed_titles.append({
                'id': post['id'],
                'number': post['number'],
                'title': post['title'],
                'author': author or '',
                'date': date or '',
                'url': post['href'],
                'attachment_count': len(attachments),
                'scraped_at': datetime.now().isoformat()
            })
            
            processed_count += 1
            self.scraped_count += 1
            
            # 요청 간격 조절
            time.sleep(1)
            
        logger.info(f"페이지 처리 완료: {processed_count}개 게시글 처리")
        return processed_count
    
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
        
        # processed_titles.json 파일 저장
        self.save_processed_titles()
        
        logger.info(f"스크래핑 완료: 총 {self.scraped_count}개 게시글 처리")
        return self.scraped_count

def main():
    """메인 실행 함수"""
    # 시작 URL
    start_url = "https://mybiz.yipa.or.kr/yipa/bbs_list.do?code=sub01b&keyvalue=sub01"
    
    # 스크래퍼 인스턴스 생성
    scraper = YIPAScraper()
    
    try:
        # 3페이지까지 스크래핑 (현재는 1페이지만 있음)
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