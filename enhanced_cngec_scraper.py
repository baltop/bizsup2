#!/usr/bin/env python3
"""
Enhanced CNGEC Scraper
충남녹색환경지원센터 (CNGEC) 공고 수집 스크래퍼
"""

import requests
from bs4 import BeautifulSoup
import os
import time
import urllib.parse
import re
from urllib.parse import urljoin
import html2text
import hashlib
from pathlib import Path
import json

class CNGECScraper:
    def __init__(self, base_url, site_code, output_dir="output"):
        self.base_url = base_url
        self.site_code = site_code
        self.output_dir = os.path.join(output_dir, site_code)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # 출력 디렉토리 생성
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        
        # HTML to markdown 변환기
        self.h2t = html2text.HTML2Text()
        self.h2t.ignore_links = False
        self.h2t.ignore_images = False
        self.h2t.body_width = 0
        
        # 다운로드 통계
        self.stats = {
            'total_posts': 0,
            'attachments_downloaded': 0,
            'pages_processed': 0,
            'errors': []
        }
    
    def clean_filename(self, filename):
        """파일명을 안전하게 정리"""
        # 특수문자 제거 및 길이 제한
        cleaned = re.sub(r'[<>:"/\\|?*]', '_', filename)
        cleaned = cleaned.strip()
        
        # 파일명이 너무 길면 줄임
        if len(cleaned) > 200:
            name, ext = os.path.splitext(cleaned)
            cleaned = name[:200-len(ext)] + ext
        
        return cleaned
    
    def download_file(self, url, filepath):
        """파일 다운로드"""
        try:
            response = self.session.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Content-Type 확인
            content_type = response.headers.get('content-type', '').lower()
            
            # HTML 응답인 경우 (오류 페이지) 감지
            if 'text/html' in content_type:
                print(f"    경고: HTML 응답 감지 - {url}")
                return 0
            
            total_size = 0
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        total_size += len(chunk)
            
            file_size = os.path.getsize(filepath)
            
            # 파일이 너무 작은 경우 (오류 페이지일 가능성)
            if file_size < 1024:
                print(f"    경고: 파일 크기 너무 작음 ({file_size} bytes) - {url}")
                # 파일 내용 확인
                with open(filepath, 'rb') as f:
                    content = f.read(512)
                    if b'<html' in content.lower() or b'<!doctype' in content.lower():
                        print(f"    오류: HTML 페이지 다운로드됨")
                        os.remove(filepath)
                        return 0
            
            return file_size
        except Exception as e:
            self.stats['errors'].append(f"파일 다운로드 실패 {url}: {str(e)}")
            return 0
    
    def extract_content(self, soup):
        """본문 내용 추출"""
        content_div = soup.find('div', {'id': 'bo_v_con'})
        if not content_div:
            return ""
        
        # 불필요한 요소 제거
        for element in content_div.find_all(['script', 'style']):
            element.decompose()
        
        return str(content_div)
    
    def extract_attachments(self, soup):
        """첨부파일 정보 추출"""
        attachments = []
        
        file_section = soup.find('section', {'id': 'bo_v_file'})
        if file_section:
            for link in file_section.find_all('a', class_='view_file_download'):
                href = link.get('href')
                if href:
                    strong_elem = link.find('strong')
                    if strong_elem:
                        filename = strong_elem.text.strip()
                        # 파일 크기 추출
                        parent_li = link.parent
                        if parent_li:
                            size_match = re.search(r'\(([^)]+)\)', parent_li.text)
                            size = size_match.group(1) if size_match else "Unknown"
                        else:
                            size = "Unknown"
                        
                        attachments.append({
                            'url': urljoin(self.base_url, href),
                            'filename': filename,
                            'size': size
                        })
        
        return attachments
    
    def scrape_post_detail(self, post_url, post_id):
        """게시글 상세 페이지 스크래핑"""
        try:
            print(f"  상세 페이지 접속: {post_url}")
            response = self.session.get(post_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 제목 추출
            title_elem = soup.find('span', class_='bo_v_tit')
            title = "제목 없음"
            if title_elem:
                title = title_elem.text.strip()
            
            # 메타 정보 추출
            meta_info = {}
            info_section = soup.find('section', {'id': 'bo_v_info'})
            if info_section:
                date_elem = info_section.find('strong', class_='if_date')
                if date_elem:
                    date_text = date_elem.text.strip()
                    # 날짜 형식에서 실제 날짜 추출
                    date_match = re.search(r'(\d{2}-\d{2}-\d{2} \d{2}:\d{2})', date_text)
                    if date_match:
                        meta_info['date'] = date_match.group(1)
                
                # 작성자는 항상 "최고관리자"로 보임
                meta_info['author'] = "최고관리자"
            
            # 본문 내용 추출
            content_html = self.extract_content(soup)
            content_md = self.h2t.handle(content_html)
            
            # 첨부파일 정보 추출
            attachments = self.extract_attachments(soup)
            
            # 게시글별 디렉토리 생성
            safe_title = self.clean_filename(title)
            post_dir = os.path.join(self.output_dir, f"{post_id}_{safe_title}")
            os.makedirs(post_dir, exist_ok=True)
            
            # 첨부파일 디렉토리 생성
            attachments_dir = os.path.join(post_dir, "attachments")
            if attachments:
                os.makedirs(attachments_dir, exist_ok=True)
            
            # 본문을 content.md 파일로 저장
            md_filepath = os.path.join(post_dir, "content.md")
            
            with open(md_filepath, 'w', encoding='utf-8') as f:
                f.write(f"# {title}\n\n")
                f.write(f"**작성자:** {meta_info.get('author', 'N/A')}\n")
                f.write(f"**등록일:** {meta_info.get('date', 'N/A')}\n")
                f.write(f"**URL:** {post_url}\n\n")
                f.write("## 본문\n\n")
                f.write(content_md)
                
                if attachments:
                    f.write("\n## 첨부파일\n\n")
                    for att in attachments:
                        f.write(f"- {att['filename']} ({att['size']})\n")
            
            print(f"  본문 저장: {md_filepath}")
            
            # 첨부파일 다운로드
            for i, attachment in enumerate(attachments):
                try:
                    filename = self.clean_filename(attachment['filename'])
                    file_path = os.path.join(attachments_dir, filename)
                    
                    print(f"  첨부파일 다운로드: {filename}")
                    file_size = self.download_file(attachment['url'], file_path)
                    
                    if file_size > 0:
                        self.stats['attachments_downloaded'] += 1
                        print(f"    완료: {filename} ({file_size} bytes)")
                    else:
                        print(f"    실패: {filename}")
                        
                except Exception as e:
                    self.stats['errors'].append(f"첨부파일 다운로드 실패 {attachment['filename']}: {str(e)}")
                    print(f"    오류: {str(e)}")
            
            return {
                'title': title,
                'author': meta_info.get('author', 'N/A'),
                'date': meta_info.get('date', 'N/A'),
                'attachments': len(attachments),
                'post_dir': post_dir
            }
            
        except Exception as e:
            self.stats['errors'].append(f"게시글 상세 스크래핑 실패 {post_url}: {str(e)}")
            print(f"    오류: {str(e)}")
            return None
    
    def scrape_page(self, page_num):
        """페이지별 게시글 목록 스크래핑"""
        try:
            if page_num == 1:
                url = self.base_url
            else:
                url = f"{self.base_url}&page={page_num}"
                
            print(f"\n페이지 {page_num} 스크래핑 시작: {url}")
            
            response = self.session.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 게시글 목록 추출
            posts = []
            tbody = soup.find('tbody')
            if tbody:
                for tr in tbody.find_all('tr'):
                    # 공지사항 스킵 (bo_notice 클래스)
                    if 'bo_notice' in tr.get('class', []):
                        continue
                    
                    # 제목 링크 찾기
                    title_td = tr.find('td', class_='td_subject')
                    if title_td:
                        title_link = title_td.find('a', href=True)
                        if title_link and 'wr_id=' in title_link['href']:
                            post_url = urljoin(self.base_url, title_link['href'])
                            post_id = re.search(r'wr_id=(\d+)', title_link['href']).group(1)
                            title = title_link.text.strip()
                            
                            posts.append({
                                'id': post_id,
                                'title': title,
                                'url': post_url
                            })
            
            print(f"페이지 {page_num}에서 {len(posts)}개 게시글 발견")
            
            # 각 게시글 상세 스크래핑
            for post in posts:
                print(f"\n[{post['id']}] {post['title']}")
                result = self.scrape_post_detail(post['url'], post['id'])
                if result:
                    self.stats['total_posts'] += 1
                
                # 요청 간격 조절
                time.sleep(1)
            
            self.stats['pages_processed'] += 1
            return len(posts)
            
        except Exception as e:
            self.stats['errors'].append(f"페이지 {page_num} 스크래핑 실패: {str(e)}")
            print(f"페이지 {page_num} 스크래핑 오류: {str(e)}")
            return 0
    
    def run(self, max_pages=3):
        """스크래핑 실행"""
        print(f"CNGEC 스크래핑 시작 - 최대 {max_pages}페이지")
        print(f"출력 디렉토리: {self.output_dir}")
        print(f"사이트 코드: {self.site_code}")
        
        start_time = time.time()
        
        for page in range(1, max_pages + 1):
            posts_count = self.scrape_page(page)
            
            if posts_count == 0:
                print(f"페이지 {page}에서 게시글을 찾을 수 없습니다. 종료합니다.")
                break
            
            print(f"페이지 {page} 완료 - {posts_count}개 게시글 처리")
            
            # 페이지 간 간격
            if page < max_pages:
                time.sleep(2)
        
        end_time = time.time()
        
        # 통계 출력
        print(f"\n{'='*50}")
        print("스크래핑 완료!")
        print(f"{'='*50}")
        print(f"처리된 페이지: {self.stats['pages_processed']}")
        print(f"수집된 게시글: {self.stats['total_posts']}")
        print(f"다운로드된 첨부파일: {self.stats['attachments_downloaded']}")
        print(f"소요 시간: {end_time - start_time:.2f}초")
        
        if self.stats['errors']:
            print(f"\n오류 {len(self.stats['errors'])}개:")
            for error in self.stats['errors']:
                print(f"  - {error}")
        
        # 통계를 JSON 파일로 저장
        stats_file = os.path.join(self.output_dir, f"{self.site_code}_stats.json")
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, ensure_ascii=False, indent=2)
        
        return self.stats

def main():
    """메인 함수"""
    base_url = "http://www.cngec.or.kr/bbs/board.php?bo_table=notice"
    site_code = "cngec"
    
    scraper = CNGECScraper(base_url, site_code)
    stats = scraper.run(max_pages=3)
    
    # 파일 크기 검증
    print(f"\n{'='*50}")
    print("파일 크기 검증")
    print(f"{'='*50}")
    
    attachment_sizes = {}
    for root, dirs, files in os.walk(scraper.output_dir):
        for file in files:
            if not file.endswith('.md') and not file.endswith('.json'):
                filepath = os.path.join(root, file)
                size = os.path.getsize(filepath)
                
                if size in attachment_sizes:
                    attachment_sizes[size].append(filepath)
                else:
                    attachment_sizes[size] = [filepath]
    
    # 같은 크기의 파일들 찾기
    duplicate_sizes = {size: files for size, files in attachment_sizes.items() if len(files) > 1}
    
    if duplicate_sizes:
        print("⚠️  같은 크기의 파일들이 발견되었습니다 (오류 가능성):")
        for size, files in duplicate_sizes.items():
            print(f"  크기 {size} bytes:")
            for file in files:
                print(f"    - {file}")
    else:
        print("✅ 모든 첨부파일이 서로 다른 크기를 가지고 있습니다.")
    
    # 한글 파일명 검증
    print(f"\n{'='*50}")
    print("한글 파일명 검증")
    print(f"{'='*50}")
    
    korean_files = []
    for root, dirs, files in os.walk(scraper.output_dir):
        for file in files:
            if re.search(r'[가-힣]', file):
                korean_files.append(os.path.join(root, file))
    
    if korean_files:
        print(f"✅ 한글 파일명 {len(korean_files)}개가 정상적으로 처리되었습니다:")
        for file in korean_files[:5]:  # 처음 5개만 표시
            print(f"  - {os.path.basename(file)}")
        if len(korean_files) > 5:
            print(f"  ... 총 {len(korean_files)}개")
    else:
        print("한글 파일명이 없습니다.")
    
    # 완료 사운드 재생
    try:
        import subprocess
        subprocess.run(["mpg123", "./ding.mp3"], capture_output=True)
        print("\n🔔 완료 사운드 재생")
    except Exception as e:
        print(f"\n⚠️  완료 사운드 재생 실패: {str(e)}")

if __name__ == "__main__":
    main()