#!/usr/bin/env python3
"""
Quick KNREC Scraper - 빠른 처리를 위한 단순화된 버전
"""

import json
import time
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright
import requests
import re
import html2text
from urllib.parse import urljoin, urlparse, parse_qs
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class QuickKnrecScraper:
    def __init__(self):
        self.base_url = "https://www.knrec.or.kr"
        self.output_dir = Path("output/knrec")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # HTML to Markdown 변환기
        self.h2t = html2text.HTML2Text()
        self.h2t.ignore_links = False
        self.h2t.ignore_images = False
        self.h2t.body_width = 0
        
        self.processed_titles = []
        self.processed_ids = set()
        
        # 기존 processed titles 로드
        json_file = self.output_dir / "processed_titles_enhanced_knrec.json"
        if json_file.exists():
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                    for item in existing_data:
                        self.processed_ids.add(item['id'])
                        self.processed_titles.append(item)
                logger.info(f"기존 처리된 게시글 {len(existing_data)}개 로드됨")
            except Exception as e:
                logger.error(f"기존 데이터 로드 실패: {e}")
    
    def get_posts_from_page(self, page_url):
        """페이지에서 게시글 목록 가져오기"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            try:
                page.goto(page_url, wait_until="networkidle")
                
                # 게시글 데이터 추출
                post_data = page.evaluate("""
                    () => {
                        const postData = [];
                        const tables = document.querySelectorAll('table');
                        let boardTable = null;
                        
                        for (let i = 0; i < tables.length; i++) {
                            const table = tables[i];
                            const rows = table.querySelectorAll('tr');
                            if (rows.length > 5) {
                                const headerCells = rows[0].querySelectorAll('th');
                                if (headerCells.length > 5) {
                                    boardTable = table;
                                    break;
                                }
                            }
                        }
                        
                        if (boardTable) {
                            const rows = boardTable.querySelectorAll('tr');
                            
                            for (let i = 1; i < rows.length; i++) {
                                const row = rows[i];
                                const cells = row.querySelectorAll('td');
                                
                                if (cells.length >= 9) {
                                    const titleCell = cells[3];
                                    const titleLink = titleCell.querySelector('a');
                                    
                                    if (titleLink) {
                                        postData.push({
                                            number: cells[0].textContent.trim(),
                                            status: cells[1].textContent.trim(),
                                            category: cells[2].textContent.trim(),
                                            title: titleLink.textContent.trim(),
                                            href: titleLink.getAttribute('href'),
                                            department: cells[4].textContent.trim(),
                                            registerDate: cells[5].textContent.trim(),
                                            deadlineDate: cells[6].textContent.trim(),
                                            views: cells[8].textContent.trim()
                                        });
                                    }
                                }
                            }
                        }
                        
                        return postData;
                    }
                """)
                
                # 절대 URL 생성 및 ID 추출
                posts = []
                for post in post_data:
                    if post['href'].startswith('./'):
                        post['href'] = urljoin(page_url, post['href'])
                    elif post['href'].startswith('/'):
                        post['href'] = self.base_url + post['href']
                    elif not post['href'].startswith('http'):
                        post['href'] = urljoin(page_url, post['href'])
                        
                    # ID 추출
                    parsed_url = urlparse(post['href'])
                    params = parse_qs(parsed_url.query)
                    no = params.get('no', [''])[0]
                    
                    post['id'] = no if no else str(hash(post['href']))
                    posts.append(post)
                
                return posts
                
            except Exception as e:
                logger.error(f"게시글 목록 파싱 중 오류: {e}")
                return []
            finally:
                browser.close()
    
    def process_post_simple(self, post):
        """게시글 간단 처리 (첨부파일 제외)"""
        if post['id'] in self.processed_ids:
            return False
            
        # 디렉토리 생성
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', post['title'])[:100]
        post_dir = self.output_dir / f"{post['number']}_{safe_title}"
        post_dir.mkdir(exist_ok=True)
        
        # 내용 파일 생성
        content_file = post_dir / "content.md"
        with open(content_file, 'w', encoding='utf-8') as f:
            f.write(f"# {post['title']}\\n\\n")
            f.write(f"**게시글 번호:** {post['number']}\\n")
            f.write(f"**게시글 ID:** {post['id']}\\n")
            f.write(f"**진행상태:** {post['status']}\\n")
            f.write(f"**분류:** {post['category']}\\n")
            f.write(f"**담당부서:** {post['department']}\\n")
            f.write(f"**등록일:** {post['registerDate']}\\n")
            f.write(f"**마감일:** {post['deadlineDate']}\\n")
            f.write(f"**조회수:** {post['views']}\\n")
            f.write(f"**URL:** {post['href']}\\n")
            f.write(f"**수집 시간:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n\\n")
            f.write("---\\n\\n")
            f.write("내용 상세는 URL을 통해 확인하세요.")
        
        # processed_titles에 추가
        self.processed_titles.append({
            'id': post['id'],
            'number': post['number'],
            'title': post['title'],
            'status': post['status'],
            'category': post['category'],
            'department': post['department'],
            'registerDate': post['registerDate'],
            'deadlineDate': post['deadlineDate'],
            'views': post['views'],
            'url': post['href'],
            'attachment_count': 0,
            'scraped_at': datetime.now().isoformat()
        })
        
        self.processed_ids.add(post['id'])
        return True
    
    def scrape_pages(self, start_url, max_pages=3):
        """여러 페이지 스크래핑"""
        total_processed = 0
        
        for page_num in range(1, max_pages + 1):
            if page_num == 1:
                page_url = start_url
            else:
                if 'page=' in start_url:
                    page_url = re.sub(r'page=\\d+', f'page={page_num}', start_url)
                else:
                    separator = '&' if '?' in start_url else '?'
                    page_url = f"{start_url}{separator}page={page_num}"
            
            logger.info(f"페이지 {page_num}/{max_pages} 처리 중: {page_url}")
            
            posts = self.get_posts_from_page(page_url)
            page_processed = 0
            
            for post in posts:
                if self.process_post_simple(post):
                    page_processed += 1
                    total_processed += 1
                    logger.info(f"처리 완료: {post['title']}")
            
            logger.info(f"페이지 {page_num} 완료: {page_processed}개 새로 처리")
            time.sleep(1)  # 페이지 간 대기
        
        # JSON 파일 저장
        json_file = self.output_dir / "processed_titles_enhanced_knrec.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(self.processed_titles, f, ensure_ascii=False, indent=2)
        
        logger.info(f"전체 처리 완료: {total_processed}개 새로 처리, 총 {len(self.processed_titles)}개")
        return total_processed

def main():
    scraper = QuickKnrecScraper()
    start_url = "https://www.knrec.or.kr/biz/pds/businoti/list.do"
    
    try:
        total_count = scraper.scrape_pages(start_url, max_pages=3)
        print(f"처리 완료: {total_count}개 새로 처리됨")
        print(f"총 게시글: {len(scraper.processed_titles)}개")
        
    except Exception as e:
        logger.error(f"스크래핑 중 오류: {e}")

if __name__ == "__main__":
    main()