#!/usr/bin/env python3
"""
Enhanced KNREC (한국신재생에너지센터) Scraper
Site: https://www.knrec.or.kr/biz/pds/businoti/list.do
Uses Playwright for browser automation to handle JavaScript-based file downloads
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
from playwright.sync_api import sync_playwright
import subprocess

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('knrec_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class KnrecScraper:
    def __init__(self, base_url="https://www.knrec.or.kr", site_code="knrec"):
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
        self.downloaded_files = 0
        
    def parse_post_list_with_playwright(self, list_url):
        """Playwright로 게시글 목록 파싱"""
        posts = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            try:
                page.goto(list_url, wait_until="networkidle")
                
                # 게시글 데이터 추출
                post_data = page.evaluate("""
                    () => {
                        const postData = [];
                        
                        // 게시판 테이블 찾기 (두 번째 테이블)
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
                            
                            // 헤더 행 제외하고 데이터 행 처리
                            for (let i = 1; i < rows.length; i++) {
                                const row = rows[i];
                                const cells = row.querySelectorAll('td');
                                
                                if (cells.length >= 9) {
                                    const numberCell = cells[0];
                                    const statusCell = cells[1];
                                    const categoryCell = cells[2];
                                    const titleCell = cells[3];
                                    const departmentCell = cells[4];
                                    const registerDateCell = cells[5];
                                    const deadlineDateCell = cells[6];
                                    const attachmentCell = cells[7];
                                    const viewsCell = cells[8];
                                    
                                    // 제목 셀에서 링크 찾기
                                    const titleLink = titleCell.querySelector('a');
                                    
                                    if (titleLink) {
                                        // 첨부파일 정보 추출
                                        const attachments = [];
                                        const attachmentLinks = attachmentCell.querySelectorAll('a');
                                        
                                        attachmentLinks.forEach(link => {
                                            const href = link.getAttribute('href');
                                            const onclick = link.getAttribute('onclick');
                                            const text = link.textContent.trim();
                                            
                                            if (href && href.includes('file_down') || onclick && onclick.includes('file_down')) {
                                                attachments.push({
                                                    href: href,
                                                    onclick: onclick,
                                                    text: text
                                                });
                                            }
                                        });
                                        
                                        postData.push({
                                            number: numberCell.textContent.trim(),
                                            status: statusCell.textContent.trim(),
                                            category: categoryCell.textContent.trim(),
                                            title: titleLink.textContent.trim(),
                                            href: titleLink.getAttribute('href'),
                                            department: departmentCell.textContent.trim(),
                                            registerDate: registerDateCell.textContent.trim(),
                                            deadlineDate: deadlineDateCell.textContent.trim(),
                                            views: viewsCell.textContent.trim(),
                                            attachments: attachments
                                        });
                                    }
                                }
                            }
                        }
                        
                        return postData;
                    }
                """)
                
                # 절대 URL 생성
                for post in post_data:
                    if post['href'].startswith('./'):
                        post['href'] = urljoin(list_url, post['href'])
                    elif post['href'].startswith('/'):
                        post['href'] = self.base_url + post['href']
                    elif not post['href'].startswith('http'):
                        post['href'] = urljoin(list_url, post['href'])
                        
                    # ID 생성 (URL에서 no 파라미터 추출)
                    parsed_url = urlparse(post['href'])
                    params = parse_qs(parsed_url.query)
                    no = params.get('no', [''])[0]
                    
                    posts.append({
                        'id': no if no else str(hash(post['href'])),
                        'number': post['number'],
                        'status': post['status'],
                        'category': post['category'],
                        'title': post['title'],
                        'href': post['href'],
                        'department': post['department'],
                        'registerDate': post['registerDate'],
                        'deadlineDate': post['deadlineDate'],
                        'views': post['views'],
                        'attachments': post['attachments']
                    })
                
                logger.info(f"총 {len(posts)}개의 게시글을 파싱했습니다.")
                
            except Exception as e:
                logger.error(f"게시글 목록 파싱 중 오류: {e}")
                
            finally:
                browser.close()
                
        return posts
    
    def get_post_detail_with_playwright(self, post_url):
        """Playwright로 게시글 상세 내용 가져오기"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            try:
                page.goto(post_url, wait_until="networkidle")
                
                # 게시글 상세 정보 추출
                post_detail = page.evaluate("""
                    () => {
                        // 제목 찾기
                        const titleElement = document.querySelector('.notice_view_tit');
                        const title = titleElement ? titleElement.textContent.trim() : '';
                        
                        // 게시글 상태 및 정보 추출
                        const statusElement = document.querySelector('.notice_cont');
                        const status = statusElement ? statusElement.textContent.trim() : '';
                        
                        const infoElements = document.querySelectorAll('.notice_view_info li');
                        const postInfo = {
                            department: infoElements[0] ? infoElements[0].textContent.trim() : '',
                            date: infoElements[1] ? infoElements[1].textContent.trim() : '',
                            views: infoElements[2] ? infoElements[2].textContent.trim() : ''
                        };
                        
                        // 본문 내용 찾기
                        const contentElement = document.querySelector('.notice_view_txt, #board_cont');
                        const content = contentElement ? contentElement.innerHTML : '';
                        
                        // 첨부파일 링크 찾기
                        const attachmentLinks = [];
                        const attachmentElements = document.querySelectorAll('.add_file_btn a, .notive_view_file a');
                        
                        attachmentElements.forEach(link => {
                            const href = link.getAttribute('href');
                            const onclick = link.getAttribute('onclick');
                            const text = link.textContent.trim();
                            
                            if ((href && href.includes('file_down')) || (onclick && onclick.includes('file_down'))) {
                                // 파일명 추출 (아이콘 텍스트 제거)
                                let fileName = text.replace(/pdf파일|한글파일|엑셀파일|zip파일|txt파일|워드파일/g, '').trim();
                                
                                // 추가 텍스트 정리
                                fileName = fileName.replace(/\(한글파일\)/g, '').trim();
                                
                                attachmentLinks.push({
                                    href: href || onclick,
                                    onclick: onclick || href,
                                    text: text,
                                    fileName: fileName
                                });
                            }
                        });
                        
                        return {
                            title: title,
                            status: status,
                            postInfo: postInfo,
                            content: content,
                            attachmentLinks: attachmentLinks
                        };
                    }
                """)
                
                # 내용을 마크다운으로 변환
                content_html = post_detail.get('content', '')
                content_markdown = self.h2t.handle(content_html) if content_html else "내용을 찾을 수 없습니다."
                
                # 첨부파일 정보 정리
                attachments = []
                seen_files = set()
                
                for link in post_detail.get('attachmentLinks', []):
                    file_name = link.get('fileName', link.get('text', ''))
                    onclick = link.get('onclick', link.get('href', ''))
                    
                    if file_name and onclick and file_name not in seen_files:
                        attachments.append({
                            'name': file_name,
                            'onclick': onclick,
                            'url': onclick  # JavaScript 함수 호출을 URL로 사용
                        })
                        seen_files.add(file_name)
                
                # 게시글 정보 추출
                post_info = post_detail.get('postInfo', {})
                department = post_info.get('department', '')
                date = post_info.get('date', '')
                views = post_info.get('views', '')
                
                return content_markdown, attachments, department, date, views
                
            except Exception as e:
                logger.error(f"게시글 상세 정보 파싱 중 오류: {e}")
                return None, [], "", "", ""
                
            finally:
                browser.close()
    
    def download_attachment_with_playwright(self, onclick_code, filename, post_dir):
        """Playwright로 첨부파일 다운로드"""
        try:
            # onclick 코드에서 파라미터 추출
            # 예: javascript:file_down('5763','1','notice')
            import re
            match = re.search(r"file_down\('([^']+)','([^']+)','([^']+)'\)", onclick_code)
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
                    safe_filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
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
                page.wait_for_timeout(3000)
                
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
    
    def download_attachment_requests(self, onclick_code, filename, post_dir):
        """Requests로 첨부파일 다운로드 (fallback)"""
        try:
            # onclick 코드에서 파라미터 추출
            import re
            match = re.search(r"file_down\('([^']+)','([^']+)','([^']+)'\)", onclick_code)
            if not match:
                return False
                
            no, file_seq, board_type = match.groups()
            
            # 다운로드 URL 생성 (추정)
            download_url = f"{self.base_url}/biz/pds/businoti/fileDown.do?no={no}&fileSeq={file_seq}&boardType={board_type}"
            
            response = self.session.get(download_url, timeout=30)
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
    
    def save_post_content(self, post, content, attachments, department, date, views):
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
            f.write(f"# {post['title']}\n\n")
            f.write(f"**게시글 번호:** {post['number']}\n")
            f.write(f"**게시글 ID:** {post['id']}\n")
            f.write(f"**진행상태:** {post['status']}\n")
            f.write(f"**분류:** {post['category']}\n")
            f.write(f"**담당부서:** {department or post['department']}\n")
            f.write(f"**등록일:** {date or post['registerDate']}\n")
            f.write(f"**마감일:** {post['deadlineDate']}\n")
            f.write(f"**조회수:** {views or post['views']}\n")
            f.write(f"**URL:** {post['href']}\n")
            f.write(f"**수집 시간:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")
            if content:
                f.write(content)
            else:
                f.write("내용이 없습니다. 첨부파일을 확인해주세요.")
        
        # 첨부파일 다운로드
        successful_downloads = 0
        for attachment in attachments:
            # 먼저 requests로 시도, 실패하면 playwright로 시도
            if self.download_attachment_requests(attachment['url'], attachment['name'], post_dir):
                successful_downloads += 1
                self.downloaded_files += 1
            elif self.download_attachment_with_playwright(attachment['url'], attachment['name'], post_dir):
                successful_downloads += 1
                self.downloaded_files += 1
        
        logger.info(f"게시글 저장 완료: {post['title']} (첨부파일 {successful_downloads}/{len(attachments)})")
        return successful_downloads
    
    def save_processed_titles(self):
        """처리된 제목 정보를 JSON 파일로 저장"""
        try:
            json_file = self.output_dir / f"processed_titles_enhanced_{self.site_code}.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(self.processed_titles, f, ensure_ascii=False, indent=2)
            logger.info(f"처리된 제목 정보 저장 완료: {json_file}")
        except Exception as e:
            logger.error(f"processed_titles_enhanced_{self.site_code}.json 저장 실패: {e}")
    
    def get_next_page_url(self, base_url, page_num):
        """다음 페이지 URL 생성"""
        # page 파라미터 추가/변경
        if 'page=' in base_url:
            import re
            return re.sub(r'page=\d+', f'page={page_num}', base_url)
        else:
            separator = '&' if '?' in base_url else '?'
            return f"{base_url}{separator}page={page_num}"
    
    def scrape_page(self, page_url):
        """페이지 스크래핑"""
        logger.info(f"페이지 스크래핑 시작: {page_url}")
        
        posts = self.parse_post_list_with_playwright(page_url)
        processed_count = 0
        
        for post in posts:
            if post['id'] in self.processed_ids:
                continue
                
            self.processed_ids.add(post['id'])
            
            logger.info(f"게시글 처리 중: {post['title']}")
            
            # 게시글 상세 내용 가져오기
            content, attachments, department, date, views = self.get_post_detail_with_playwright(post['href'])
            if content is None:
                # 내용이 없어도 메타데이터는 저장
                content = "내용을 가져올 수 없습니다."
                attachments = []
            
            # 게시글 저장
            self.save_post_content(post, content, attachments, department, date, views)
            
            # 처리된 제목 정보 저장
            self.processed_titles.append({
                'id': post['id'],
                'number': post['number'],
                'title': post['title'],
                'status': post['status'],
                'category': post['category'],
                'department': department or post['department'],
                'registerDate': date or post['registerDate'],
                'deadlineDate': post['deadlineDate'],
                'views': views or post['views'],
                'url': post['href'],
                'attachment_count': len(attachments),
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
                time.sleep(3)
        
        # processed_titles.json 파일 저장
        self.save_processed_titles()
        
        logger.info(f"스크래핑 완료: 총 {self.scraped_count}개 게시글 처리")
        return self.scraped_count

def main():
    """메인 실행 함수"""
    # 시작 URL
    start_url = "https://www.knrec.or.kr/biz/pds/businoti/list.do"
    
    # 스크래퍼 인스턴스 생성
    scraper = KnrecScraper()
    
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
            print(f"다운로드된 첨부파일: {scraper.downloaded_files}개")
        
        # 완료 사운드
        try:
            subprocess.run(['mpg123', './ding.mp3'], check=True)
        except:
            logger.info("완료 사운드 재생 실패")
        
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단되었습니다.")
    except Exception as e:
        logger.error(f"스크래핑 중 오류 발생: {e}")
        raise

if __name__ == "__main__":
    main()