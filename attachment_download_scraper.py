#!/usr/bin/env python3
"""
KNREC 첨부파일 다운로드 전용 스크래퍼
"""

import json
import time
import re
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright
import requests
import uuid
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AttachmentDownloader:
    def __init__(self):
        self.base_url = "https://www.knrec.or.kr"
        self.output_dir = Path("output/knrec")
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
    def get_post_attachments(self, post_url):
        """게시글에서 첨부파일 정보 가져오기"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            try:
                page.goto(post_url, wait_until="networkidle")
                
                # 첨부파일 정보 추출
                attachment_info = page.evaluate("""
                    () => {
                        const attachmentLinks = [];
                        
                        // 여러 선택자로 첨부파일 링크 찾기
                        const selectors = [
                            '.add_file_btn a',
                            '.notive_view_file a',
                            '.attach_file a',
                            '.file_list a',
                            'a[href*="file_down"]',
                            'a[onclick*="file_down"]'
                        ];
                        
                        selectors.forEach(selector => {
                            const elements = document.querySelectorAll(selector);
                            elements.forEach(link => {
                                const href = link.getAttribute('href');
                                const onclick = link.getAttribute('onclick');
                                const text = link.textContent.trim();
                                
                                if ((href && href.includes('file_down')) || 
                                    (onclick && onclick.includes('file_down'))) {
                                    
                                    // 파일명 정리
                                    let fileName = text.replace(/pdf파일|한글파일|엑셀파일|zip파일|txt파일|워드파일/g, '').trim();
                                    fileName = fileName.replace(/\\(한글파일\\)/g, '').trim();
                                    fileName = fileName.replace(/\\s+/g, ' ').trim();
                                    
                                    if (fileName) {
                                        attachmentLinks.push({
                                            href: href || onclick,
                                            onclick: onclick || href,
                                            text: text,
                                            fileName: fileName
                                        });
                                    }
                                }
                            });
                        });
                        
                        return attachmentLinks;
                    }
                """)
                
                return attachment_info
                
            except Exception as e:
                logger.error(f"첨부파일 정보 추출 중 오류: {e}")
                return []
            finally:
                browser.close()
    
    def download_attachment_with_playwright(self, onclick_code, filename, post_dir):
        """Playwright로 첨부파일 다운로드"""
        try:
            # onclick 코드에서 파라미터 추출
            match = re.search(r"file_down\\('([^']+)','([^']+)','([^']+)'\\)", onclick_code)
            if not match:
                logger.warning(f"JavaScript 함수 파싱 실패: {onclick_code}")
                return False
                
            no, file_seq, board_type = match.groups()
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # 다운로드 이벤트 처리
                download_path = None
                
                def handle_download(download):
                    nonlocal download_path
                    # 첨부파일 디렉토리 생성
                    attachments_dir = post_dir / "attachments"
                    attachments_dir.mkdir(exist_ok=True)
                    
                    # 안전한 파일명 생성
                    safe_filename = re.sub(r'[<>:"/\\\\|?*]', '_', filename)
                    if not safe_filename:
                        safe_filename = f"attachment_{uuid.uuid4().hex[:8]}"
                    
                    # 파일명이 너무 길면 자르기
                    if len(safe_filename) > 200:
                        name_part = safe_filename[:180]
                        ext_part = safe_filename[-20:] if '.' in safe_filename[-20:] else ''
                        safe_filename = name_part + ext_part
                    
                    download_path = attachments_dir / safe_filename
                    download.save_as(str(download_path))
                
                page.on("download", handle_download)
                
                # 원본 페이지로 이동
                original_url = f"https://www.knrec.or.kr/biz/pds/businoti/view.do?no={no}"
                page.goto(original_url, wait_until="networkidle")
                
                # JavaScript 함수 실행
                page.evaluate(f"file_down('{no}', '{file_seq}', '{board_type}')")
                
                # 다운로드 완료 대기
                page.wait_for_timeout(5000)
                
                browser.close()
                
                if download_path and download_path.exists():
                    file_size = download_path.stat().st_size
                    logger.info(f"첨부파일 다운로드 완료: {filename} ({file_size} bytes)")
                    return True
                else:
                    logger.warning(f"첨부파일 다운로드 실패: {filename}")
                    return False
                    
        except Exception as e:
            logger.error(f"첨부파일 다운로드 실패: {filename}, 에러: {e}")
            return False
    
    def process_attachments_from_json(self):
        """JSON 파일에서 게시글 정보를 읽어서 첨부파일 다운로드"""
        json_file = self.output_dir / "processed_titles_enhanced_knrec.json"
        
        if not json_file.exists():
            logger.error("processed_titles_enhanced_knrec.json 파일이 없습니다.")
            return
        
        with open(json_file, 'r', encoding='utf-8') as f:
            posts = json.load(f)
        
        # 상위 10개 게시글만 처리 (테스트)
        for post in posts[:10]:
            post_url = post['url']
            post_title = post['title']
            post_id = post['id']
            
            logger.info(f"게시글 처리 중: {post_title}")
            
            # 첨부파일 정보 가져오기
            attachments = self.get_post_attachments(post_url)
            
            if not attachments:
                logger.info(f"첨부파일 없음: {post_title}")
                continue
            
            logger.info(f"첨부파일 {len(attachments)}개 발견: {post_title}")
            
            # 게시글 디렉토리 찾기
            post_dirs = [d for d in self.output_dir.iterdir() 
                        if d.is_dir() and post_id in d.name]
            
            if not post_dirs:
                logger.warning(f"게시글 디렉토리를 찾을 수 없음: {post_title}")
                continue
            
            post_dir = post_dirs[0]
            
            # 첨부파일 다운로드
            successful_downloads = 0
            for attachment in attachments:
                if self.download_attachment_with_playwright(
                    attachment['onclick'], 
                    attachment['fileName'], 
                    post_dir
                ):
                    successful_downloads += 1
                time.sleep(2)  # 다운로드 간 대기
            
            logger.info(f"첨부파일 다운로드 완료: {successful_downloads}/{len(attachments)} - {post_title}")
            time.sleep(3)  # 게시글 간 대기

def main():
    downloader = AttachmentDownloader()
    downloader.process_attachments_from_json()

if __name__ == "__main__":
    main()