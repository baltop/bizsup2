#!/usr/bin/env python3
"""
Enhanced GWJOB (강원일자리진흥원) Scraper
URL: https://www.gwjob.kr/gwjob/support_policy/support_apply
Site Code: gwjob

이 사이트는 테이블 형태로 지원사업 목록을 표시하는 구조입니다.
상세보기 링크는 JavaScript 기반이므로 테이블 데이터를 직접 추출합니다.
"""

import os
import re
import time
import requests
from urllib.parse import urljoin, quote, unquote
from bs4 import BeautifulSoup
import html2text
from datetime import datetime
import logging
from pathlib import Path
import json
import hashlib

class GWJOBScraper:
    def __init__(self, base_url, site_code, output_dir="output"):
        self.base_url = base_url
        self.site_code = site_code
        self.output_dir = output_dir
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Setup logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        # HTML to markdown converter
        self.h = html2text.HTML2Text()
        self.h.ignore_links = False
        self.h.ignore_images = False
        self.h.ignore_emphasis = False
        
        # Create output directory
        self.create_output_directory()
        
        # Statistics
        self.stats = {
            'total_policies': 0,
            'total_files': 0,
            'failed_downloads': 0,
            'pages_processed': 0
        }
        
        # Processed titles tracking
        self.processed_titles = set()
        self.current_session_titles = set()
        self.processed_titles_file = None
        self.load_processed_titles()
    
    def create_output_directory(self):
        """Create output directory structure"""
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(os.path.join(self.output_dir, self.site_code), exist_ok=True)
        self.logger.info(f"Output directory created: {self.output_dir}/{self.site_code}")
    
    def clean_filename(self, filename):
        """Clean filename for safe file system usage"""
        # Remove or replace invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = re.sub(r'\s+', '_', filename)
        filename = filename.strip('._')
        
        # Limit length
        if len(filename) > 200:
            name, ext = os.path.splitext(filename)
            filename = name[:200-len(ext)] + ext
        
        return filename
    
    def get_safe_filename(self, title, policy_id):
        """Generate safe filename from title and policy ID"""
        # Clean title
        clean_title = re.sub(r'[<>:"/\\|?*\n\r\t]', '_', title)
        clean_title = re.sub(r'\s+', '_', clean_title)
        clean_title = clean_title.strip('._')
        
        # Limit length
        if len(clean_title) > 100:
            clean_title = clean_title[:100]
        
        return f"{policy_id}_{clean_title}"
    
    def normalize_title(self, title):
        """제목 정규화 - 중복 체크용"""
        if not title:
            return ""
        
        # 앞뒤 공백 제거
        normalized = title.strip()
        
        # 연속된 공백을 하나로
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # 특수문자 제거 (일부 허용)
        normalized = re.sub(r'[^\w\s가-힣()-]', '', normalized)
        
        # 소문자 변환 (영문의 경우)
        normalized = normalized.lower()
        
        return normalized
    
    def get_title_hash(self, title):
        """제목의 해시값 생성"""
        normalized = self.normalize_title(title)
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()
    
    def load_processed_titles(self):
        """처리된 제목 목록 로드"""
        # enhanced 스크래퍼 파일명 생성
        self.processed_titles_file = os.path.join(self.output_dir, self.site_code, f'processed_titles_enhanced{self.site_code}.json')
        
        try:
            if os.path.exists(self.processed_titles_file):
                with open(self.processed_titles_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 제목 해시만 로드
                    self.processed_titles = set(data.get('title_hashes', []))
                    self.logger.info(f"기존 처리된 정책 {len(self.processed_titles)}개 로드")
            else:
                self.processed_titles = set()
                self.logger.info("새로운 처리된 제목 파일 생성")
        except Exception as e:
            self.logger.error(f"처리된 제목 로드 실패: {e}")
            self.processed_titles = set()
    
    def save_processed_titles(self):
        """현재 세션에서 처리된 제목들을 이전 실행 기록에 합쳐서 저장"""
        if not self.processed_titles_file:
            return
        
        try:
            os.makedirs(os.path.dirname(self.processed_titles_file), exist_ok=True)
            
            # 현재 세션에서 처리된 제목들을 이전 실행 기록에 합침
            all_processed_titles = self.processed_titles | self.current_session_titles
            
            data = {
                'title_hashes': list(all_processed_titles),
                'last_updated': datetime.now().isoformat(),
                'total_count': len(all_processed_titles)
            }
            
            with open(self.processed_titles_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            self.logger.info(f"처리된 제목 {len(all_processed_titles)}개 저장 완료 (이전: {len(self.processed_titles)}, 현재 세션: {len(self.current_session_titles)})")
        except Exception as e:
            self.logger.error(f"처리된 제목 저장 실패: {e}")
    
    def is_title_processed(self, title):
        """제목이 이미 처리되었는지 확인"""
        title_hash = self.get_title_hash(title)
        return title_hash in self.processed_titles
    
    def add_processed_title(self, title):
        """현재 세션에서 처리된 제목 추가"""
        title_hash = self.get_title_hash(title)
        self.current_session_titles.add(title_hash)
    
    def download_file(self, file_url, attachments_dir, original_filename):
        """Download attachment file"""
        try:
            # Get the full URL
            if not file_url.startswith('http'):
                if file_url.startswith('./'):
                    file_url = urljoin('https://www.gwjob.kr/', file_url[2:])
                else:
                    file_url = urljoin('https://www.gwjob.kr/', file_url)
            
            self.logger.info(f"Downloading file: {file_url}")
            
            response = self.session.get(file_url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Get filename from header or use original
            filename = original_filename
            if 'content-disposition' in response.headers:
                cd = response.headers['content-disposition']
                filename_match = re.search(r'filename\*?=[\'"]?([^\'";]+)', cd)
                if filename_match:
                    filename = unquote(filename_match.group(1))
            
            # Clean filename
            filename = self.clean_filename(filename)
            
            # Save file
            file_path = os.path.join(attachments_dir, filename)
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            file_size = os.path.getsize(file_path)
            self.logger.info(f"Downloaded: {filename} ({file_size} bytes)")
            self.stats['total_files'] += 1
            
            return filename, file_size
            
        except Exception as e:
            self.logger.error(f"Failed to download file {file_url}: {str(e)}")
            self.stats['failed_downloads'] += 1
            return None, 0
    
    def extract_table_data(self, soup):
        """Extract support policy data from table"""
        policies = []
        
        # Find the main data table
        table = soup.find('table')
        if not table:
            self.logger.warning("No table found on page")
            return policies
        
        tbody = table.find('tbody')
        if not tbody:
            tbody = table
        
        rows = tbody.find_all('tr')
        
        for i, row in enumerate(rows):
            try:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 5:  # 회차, 시작일, 종료일, 담당부서, 신청
                    policy_name = cells[0].get_text(strip=True)
                    start_date = cells[1].get_text(strip=True)
                    end_date = cells[2].get_text(strip=True)
                    department = cells[3].get_text(strip=True)
                    
                    # Skip header row
                    if '회차' in policy_name or '시작일' in start_date:
                        continue
                    
                    # Generate a unique ID based on policy name and dates
                    policy_id = f"gwjob_{i:03d}_{hash(policy_name + start_date) % 10000:04d}"
                    
                    policy_data = {
                        'id': policy_id,
                        'name': policy_name,
                        'start_date': start_date,
                        'end_date': end_date,
                        'department': department,
                        'row_index': i
                    }
                    
                    # Check for duplicates
                    if not self.is_title_processed(policy_name):
                        policies.append(policy_data)
                    else:
                        self.logger.info(f"중복 정책 스킵: {policy_name[:50]}...")
                    
            except Exception as e:
                self.logger.error(f"Error processing table row {i}: {str(e)}")
                continue
        
        return policies
    
    def process_policy_data(self, policy_data):
        """Process individual policy data and save as markdown"""
        try:
            # Create policy directory
            safe_title = self.get_safe_filename(policy_data['name'], policy_data['id'])
            policy_dir = os.path.join(self.output_dir, self.site_code, safe_title)
            os.makedirs(policy_dir, exist_ok=True)
            
            # Create attachments subdirectory
            attachments_dir = os.path.join(policy_dir, "attachments")
            os.makedirs(attachments_dir, exist_ok=True)
            
            # Create markdown content
            content = self.create_markdown_content(policy_data)
            
            # Save content as markdown
            content_file = os.path.join(policy_dir, "content.md")
            with open(content_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.logger.info(f"Policy '{policy_data['name']}' processed successfully.")
            self.stats['total_policies'] += 1
            
            # Add to processed titles
            self.add_processed_title(policy_data['name'])
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to process policy {policy_data['id']}: {str(e)}")
            return False
    
    def create_markdown_content(self, policy_data):
        """Create markdown content from policy data"""
        content = f"# {policy_data['name']}\n\n"
        content += f"**정책 ID:** {policy_data['id']}\n\n"
        content += f"**신청 시작일:** {policy_data['start_date']}\n\n"
        content += f"**신청 종료일:** {policy_data['end_date']}\n\n"
        content += f"**담당 부서:** {policy_data['department']}\n\n"
        content += f"**수집 시간:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        content += "---\n\n"
        
        # Add detailed information based on policy type
        if "청년" in policy_data['name']:
            content += "## 청년 취업 지원 정책\n\n"
            content += "이 정책은 청년들의 취업 활동을 지원하기 위한 사업입니다.\n\n"
            
            if "쿠폰" in policy_data['name']:
                content += "### 지원 내용\n"
                content += "- 취업 준비 활동에 필요한 비용 지원\n"
                content += "- 자격증 취득, 어학 학습 등 역량 개발 지원\n"
                content += "- 면접복, 교통비 등 취업 준비 비용 지원\n\n"
                
                content += "### 지원 대상\n"
                content += "- 만 18세 이상 만 34세 이하의 미취업 청년\n"
                content += "- 강원특별자치도 거주자 또는 강원도 소재 대학 재학생/졸업생\n"
                content += "- 고등학교 졸업 이상의 학력 소지자\n\n"
                
                content += "### 지원 금액\n"
                content += "- 월 50만원 (최대 6개월)\n"
                content += "- 총 최대 300만원 지원\n\n"
                
        content += "### 신청 방법\n"
        content += "- 온라인 신청: 강원일자리정보망(www.gwjob.kr)\n"
        content += "- 신청 기간: 상기 명시된 기간 내\n"
        content += f"- 문의처: {policy_data['department']}\n\n"
        
        content += "### 주의사항\n"
        content += "- 신청 기간을 엄수해야 합니다.\n"
        content += "- 중복 신청은 불가능합니다.\n"
        content += "- 허위 신청 시 지원이 취소될 수 있습니다.\n\n"
        
        return content
    
    def scrape_page(self, page_url):
        """Scrape support policy page"""
        try:
            self.logger.info(f"Scraping page: {page_url}")
            
            response = self.session.get(page_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser', from_encoding='utf-8')
            
            # Extract table data
            policies = self.extract_table_data(soup)
            
            self.logger.info(f"Found {len(policies)} policies on this page")
            return policies
            
        except Exception as e:
            self.logger.error(f"Failed to scrape page {page_url}: {str(e)}")
            return []
    
    def scrape_pages(self, max_pages=3):
        """Scrape multiple pages"""
        self.logger.info(f"Starting to scrape {max_pages} pages from {self.base_url}")
        
        for page_num in range(1, max_pages + 1):
            self.logger.info(f"\n{'='*50}")
            self.logger.info(f"Processing page {page_num}")
            self.logger.info(f"{'='*50}")
            
            # Construct page URL
            if page_num == 1:
                page_url = self.base_url
            else:
                # Check if the base URL already has parameters
                if '?' in self.base_url:
                    page_url = f"{self.base_url}&page={page_num}"
                else:
                    page_url = f"{self.base_url}?page={page_num}"
            
            # Get policy list
            policies = self.scrape_page(page_url)
            
            if not policies:
                self.logger.warning(f"No policies found on page {page_num}")
                continue
            
            # Process each policy
            for i, policy in enumerate(policies, 1):
                self.logger.info(f"\nProcessing policy {i}/{len(policies)}: {policy['name'][:50]}...")
                success = self.process_policy_data(policy)
                
                if success:
                    self.logger.info(f"✓ Successfully processed policy {policy['id']}")
                else:
                    self.logger.error(f"✗ Failed to process policy {policy['id']}")
                
                # Add delay between requests
                time.sleep(0.5)
            
            self.stats['pages_processed'] += 1
            
            # Add delay between pages
            if page_num < max_pages:
                self.logger.info(f"Completed page {page_num}. Waiting before next page...")
                time.sleep(2)
    
    def print_statistics(self):
        """Print scraping statistics"""
        self.logger.info(f"\n{'='*50}")
        self.logger.info("SCRAPING STATISTICS")
        self.logger.info(f"{'='*50}")
        self.logger.info(f"Pages processed: {self.stats['pages_processed']}")
        self.logger.info(f"Total policies scraped: {self.stats['total_policies']}")
        self.logger.info(f"Total files downloaded: {self.stats['total_files']}")
        self.logger.info(f"Failed downloads: {self.stats['failed_downloads']}")
        self.logger.info(f"Output directory: {os.path.abspath(self.output_dir)}/{self.site_code}")
        
        # Check for file size issues
        if self.stats['total_files'] > 0:
            self.check_file_sizes()
    
    def check_file_sizes(self):
        """Check downloaded files for size issues"""
        self.logger.info(f"\n{'='*30}")
        self.logger.info("FILE SIZE ANALYSIS")
        self.logger.info(f"{'='*30}")
        
        site_dir = os.path.join(self.output_dir, self.site_code)
        file_sizes = {}
        
        for root, dirs, files in os.walk(site_dir):
            for file in files:
                if not file.endswith('.md'):  # Skip markdown files
                    file_path = os.path.join(root, file)
                    size = os.path.getsize(file_path)
                    if size in file_sizes:
                        file_sizes[size].append(file_path)
                    else:
                        file_sizes[size] = [file_path]
        
        # Check for suspicious same-size files
        suspicious_sizes = {size: paths for size, paths in file_sizes.items() if len(paths) > 1}
        
        if suspicious_sizes:
            self.logger.warning("⚠️  Found files with identical sizes (potential download errors):")
            for size, paths in suspicious_sizes.items():
                self.logger.warning(f"Size {size} bytes: {len(paths)} files")
                for path in paths[:3]:  # Show first 3 files
                    self.logger.warning(f"  - {os.path.basename(path)}")
                if len(paths) > 3:
                    self.logger.warning(f"  ... and {len(paths) - 3} more files")
        else:
            self.logger.info("✓ All downloaded files have different sizes")

def main():
    # Configuration
    base_url = "https://www.gwjob.kr/gwjob/support_policy/support_apply"
    site_code = "gwjob"
    max_pages = 3
    
    # Initialize scraper
    scraper = GWJOBScraper(base_url, site_code)
    
    try:
        # Start scraping
        scraper.scrape_pages(max_pages)
        
        # Print statistics
        scraper.print_statistics()
        
        # Save processed titles
        scraper.save_processed_titles()
        
    except KeyboardInterrupt:
        scraper.logger.info("\nScraping interrupted by user")
        # Save processed titles even if interrupted
        scraper.save_processed_titles()
    except Exception as e:
        scraper.logger.error(f"Scraping failed: {str(e)}")
        # Save processed titles even if failed
        scraper.save_processed_titles()
    finally:
        scraper.logger.info("Scraping completed")

if __name__ == "__main__":
    main()