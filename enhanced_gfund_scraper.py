#!/usr/bin/env python3
"""
Enhanced GFUND (지방금융공제조합) Scraper
URL: https://www.gfund.kr/hp/info/M04_L01.do
Site Code: gfund

공지사항 게시판 스크래퍼
"""

import os
import re
import time
import requests
from urllib.parse import urljoin, quote, unquote, urlparse, parse_qs
from bs4 import BeautifulSoup
import html2text
from datetime import datetime
import logging
from pathlib import Path
import json
import hashlib

class GFUNDScraper:
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
            'total_notices': 0,
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
                    self.logger.info(f"기존 처리된 공고 {len(self.processed_titles)}개 로드")
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

    def clean_filename(self, filename):
        """Clean filename for safe file system usage while preserving Korean characters"""
        # Remove or replace invalid characters but keep Korean characters and common punctuation
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # Replace multiple spaces with single space
        filename = re.sub(r'\s+', ' ', filename)
        filename = filename.strip()
        
        # Limit length
        if len(filename) > 200:
            name, ext = os.path.splitext(filename)
            filename = name[:200-len(ext)] + ext
        
        return filename
    
    def get_safe_filename(self, title, notice_id):
        """Generate safe filename from title and notice ID"""
        # Clean title
        clean_title = re.sub(r'[<>:"/\\|?*\n\r\t]', '_', title)
        clean_title = re.sub(r'\s+', '_', clean_title)
        clean_title = clean_title.strip('._')
        
        # Limit length
        if len(clean_title) > 100:
            clean_title = clean_title[:100]
        
        return f"{notice_id}_{clean_title}"
    
    def download_file(self, file_url, attachments_dir, original_filename):
        """Download attachment file"""
        try:
            # Get the full URL
            if not file_url.startswith('http'):
                file_url = urljoin('https://www.gfund.kr/', file_url)
            
            self.logger.info(f"Downloading file: {file_url}")
            
            response = self.session.get(file_url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Get filename from Content-Disposition header
            filename = original_filename
            if 'content-disposition' in response.headers:
                cd = response.headers['content-disposition']
                self.logger.debug(f"Content-Disposition: {cd}")
                
                # Try multiple patterns for filename extraction
                filename_match = re.search(r'filename\s*=\s*"([^"]+)"', cd)
                if filename_match:
                    raw_filename = filename_match.group(1)
                    self.logger.debug(f"Raw filename: {raw_filename}")
                    
                    # Try to decode the filename properly
                    try:
                        # First try URL decoding if it looks like URL-encoded content
                        if '%' in raw_filename:
                            filename = unquote(raw_filename)
                            self.logger.info(f"URL decoded filename: {filename}")
                        else:
                            # The filename might be UTF-8 encoded bytes represented as latin-1
                            filename = raw_filename.encode('latin-1').decode('utf-8')
                            self.logger.info(f"UTF-8 decoded filename: {filename}")
                    except (UnicodeDecodeError, UnicodeEncodeError):
                        try:
                            # Try EUC-KR encoding
                            filename = raw_filename.encode('latin-1').decode('euc-kr')
                            self.logger.info(f"EUC-KR decoded filename: {filename}")
                        except (UnicodeDecodeError, UnicodeEncodeError):
                            # If all fails, use the raw filename
                            filename = raw_filename
                            self.logger.info(f"Using raw filename: {filename}")
                else:
                    # Pattern 2: filename=파일명 (without quotes)
                    filename_match = re.search(r'filename\s*=\s*([^;]+)', cd)
                    if filename_match:
                        filename = filename_match.group(1).strip('\'"')
                    else:
                        # Pattern 3: filename*=UTF-8''encoded_filename
                        filename_match = re.search(r"filename\*\s*=\s*UTF-8''([^;]+)", cd)
                        if filename_match:
                            filename = unquote(filename_match.group(1))
                
                self.logger.info(f"Final extracted filename: {filename}")
            
            # If we still don't have a good filename, fallback to original
            if not filename or len(filename.strip()) == 0 or '.' not in filename:
                filename = original_filename
                # Try to detect file type from content-type
                content_type = response.headers.get('content-type', '').lower()
                if 'hwp' in content_type:
                    filename += '.hwp'
                elif 'pdf' in content_type:
                    filename += '.pdf'
                elif 'msword' in content_type or 'wordprocessingml' in content_type:
                    filename += '.docx' if 'wordprocessingml' in content_type else '.doc'
                elif 'excel' in content_type or 'spreadsheetml' in content_type:
                    filename += '.xlsx' if 'spreadsheetml' in content_type else '.xls'
                elif 'image' in content_type:
                    if 'jpeg' in content_type or 'jpg' in content_type:
                        filename += '.jpg'
                    elif 'png' in content_type:
                        filename += '.png'
                    elif 'gif' in content_type:
                        filename += '.gif'
                elif 'zip' in content_type or 'compressed' in content_type:
                    filename += '.zip'
            
            # Final URL decoding attempt if filename still contains encoded characters
            if '%' in filename:
                try:
                    filename = unquote(filename)
                    self.logger.info(f"Final URL decode of filename: {filename}")
                except Exception as e:
                    self.logger.warning(f"Failed final URL decode: {e}")
            
            # Clean filename for safe file system usage
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
    
    def extract_notice_list(self, soup):
        """Extract notice list from the main page"""
        notices = []
        
        # Find the notice table
        table = soup.find('table', class_='board_list')
        if not table:
            table = soup.find('table')
        
        if not table:
            self.logger.warning("No notice table found on page")
            return notices
        
        tbody = table.find('tbody')
        if not tbody:
            tbody = table
        
        notice_rows = tbody.find_all('tr')
        
        for row in notice_rows:
            try:
                cells = row.find_all('td')
                if len(cells) < 4:
                    continue
                
                # Extract notice number
                number = cells[0].get_text(strip=True)
                
                # Extract title and link
                title_cell = cells[1]
                title_link = title_cell.find('a')
                if not title_link:
                    continue
                
                title = title_link.get_text(strip=True)
                detail_url = title_link.get('href', '')
                
                # Extract notice ID from URL or use number
                notice_id = number
                if 'seq=' in detail_url:
                    id_match = re.search(r'seq=(\d+)', detail_url)
                    if id_match:
                        notice_id = id_match.group(1)
                
                # Extract author
                author = cells[2].get_text(strip=True)
                
                # Extract date
                date = cells[3].get_text(strip=True)
                
                # If detail_url is relative, make it absolute
                if detail_url and not detail_url.startswith('http'):
                    detail_url = urljoin('https://www.gfund.kr/', detail_url)
                
                notice_data = {
                    'id': notice_id,
                    'number': number,
                    'title': title,
                    'author': author,
                    'date': date,
                    'detail_url': detail_url
                }
                
                # Check for duplicates
                if not self.is_title_processed(title):
                    notices.append(notice_data)
                else:
                    self.logger.info(f"중복 공고 스킵: {title[:50]}...")
                
            except Exception as e:
                self.logger.error(f"Error processing notice row: {str(e)}")
                continue
        
        return notices
    
    def parse_js_file_data(self, js_data_string):
        """Parse JavaScript file data string into a dictionary"""
        try:
            # Remove braces and split by comma
            js_data_string = js_data_string.strip('{}').strip()
            items = js_data_string.split(', ')
            
            file_data = {}
            for item in items:
                if '=' in item:
                    key, value = item.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    file_data[key] = value
            
            return file_data
        except Exception as e:
            self.logger.error(f"Failed to parse JS file data: {e}")
            return {}
    
    def extract_files_from_onclick(self, soup):
        """Extract file information from onclick handlers"""
        files = []
        
        # Find all links with fnClickFileDown onclick handlers
        onclick_links = soup.find_all('a', onclick=re.compile(r'fnClickFileDown'))
        
        for link in onclick_links:
            try:
                onclick_value = link.get('onclick', '')
                
                # Extract the data string from fnClickFileDown('...')
                match = re.search(r"fnClickFileDown\('([^']+)'", onclick_value)
                if match:
                    js_data_string = match.group(1)
                    file_data = self.parse_js_file_data(js_data_string)
                    
                    if file_data:
                        # Extract key information
                        file_name = file_data.get('name', '')
                        file_path = file_data.get('filePath', '')
                        file_url = file_data.get('url', '')
                        file_size = file_data.get('size', '0')
                        file_ext = file_data.get('ext', '')
                        
                        # Construct full URL if not present
                        if not file_url and file_path:
                            file_url = f"https://www.gfund.kr/resources/files/{file_path}"
                        elif file_url and not file_url.startswith('http'):
                            file_url = f"https://www.gfund.kr{file_url}"
                        
                        # Clean filename - remove attachment date info
                        if file_name:
                            # Remove attachment date info like "[첨부일자 : 2024-12-30]"
                            file_name = re.sub(r'\s*\[첨부일자\s*:\s*[^\]]+\]\s*', '', file_name)
                            file_name = file_name.strip()
                        
                        files.append({
                            'name': file_name,
                            'url': file_url,
                            'size': file_size,
                            'ext': file_ext,
                            'path': file_path
                        })
                        
                        self.logger.info(f"Found file: {file_name} -> {file_url}")
                        
            except Exception as e:
                self.logger.error(f"Error extracting file from onclick: {e}")
                continue
        
        return files
    
    def scrape_notice_detail(self, notice_data):
        """Scrape individual notice detail page"""
        try:
            detail_url = notice_data['detail_url']
            
            self.logger.info(f"Scraping notice detail: {notice_data['title'][:50]}...")
            
            response = self.session.get(detail_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser', from_encoding='utf-8')
            
            # Create notice directory
            safe_title = self.get_safe_filename(notice_data['title'], notice_data['id'])
            notice_dir = os.path.join(self.output_dir, self.site_code, safe_title)
            os.makedirs(notice_dir, exist_ok=True)
            
            # Create attachments subdirectory
            attachments_dir = os.path.join(notice_dir, "attachments")
            os.makedirs(attachments_dir, exist_ok=True)
            
            # Extract content from detail page
            content_html = ""
            
            # Try different possible content containers
            content_selectors = [
                '.board.view .content',       # Main content container
                '.board.view',                # Board view container
                '.content',                   # Generic content
                '.view_content',              # View content
                '.board_content'              # Board content
            ]
            
            for selector in content_selectors:
                content_div = soup.select_one(selector)
                if content_div:
                    content_html = str(content_div)
                    break
            
            # Convert to markdown
            content_markdown = self.h.handle(content_html)
            
            # Create markdown content
            full_content = self.create_markdown_content(notice_data, content_markdown, detail_url)
            
            # Save content as markdown
            content_file = os.path.join(notice_dir, "content.md")
            with open(content_file, 'w', encoding='utf-8') as f:
                f.write(full_content)
            
            # Look for attachments using enhanced JavaScript extraction
            downloaded_files = []
            
            # Extract files from JavaScript onclick handlers (primary method)
            js_files = self.extract_files_from_onclick(soup)
            for file_info in js_files:
                if file_info['url']:
                    downloaded_file, file_size = self.download_file(
                        file_info['url'], 
                        attachments_dir, 
                        file_info['name']
                    )
                    if downloaded_file:
                        downloaded_files.append((downloaded_file, file_size))
            
            # Fallback: Try to find direct file download links
            if not downloaded_files:
                self.logger.info("No files found via JavaScript extraction, trying direct links...")
                file_links = soup.find_all('a', href=re.compile(r'resources/files/'))
                for link in file_links:
                    file_url = link.get('href', '')
                    if file_url:
                        filename = link.get_text(strip=True)
                        if not filename:
                            # Try to extract filename from URL
                            filename = os.path.basename(file_url)
                        
                        downloaded_file, file_size = self.download_file(file_url, attachments_dir, filename)
                        if downloaded_file:
                            downloaded_files.append((downloaded_file, file_size))
            
            # Additional fallback: Look for URLs in script tags
            if not downloaded_files:
                self.logger.info("No files found via direct links, scanning script tags...")
                script_tags = soup.find_all('script')
                for script in script_tags:
                    script_text = script.get_text()
                    if 'resources/files/' in script_text:
                        # Extract file URLs from JavaScript
                        file_urls = re.findall(r'https://www\.gfund\.kr/resources/files/[^"\'\'\s]+', script_text)
                        for file_url in file_urls:
                            filename = os.path.basename(file_url)
                            downloaded_file, file_size = self.download_file(file_url, attachments_dir, filename)
                            if downloaded_file:
                                downloaded_files.append((downloaded_file, file_size))
            
            self.logger.info(f"Notice '{notice_data['title']}' processed successfully. Downloaded {len(downloaded_files)} files.")
            self.stats['total_notices'] += 1
            
            # Add to processed titles
            self.add_processed_title(notice_data['title'])
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to scrape notice {notice_data['id']}: {str(e)}")
            return False
    
    def create_markdown_content(self, notice_data, content_markdown, detail_url):
        """Create markdown content from notice data"""
        content = f"# {notice_data['title']}\n\n"
        content += f"**공고 ID:** {notice_data['id']}\n\n"
        content += f"**번호:** {notice_data['number']}\n\n"
        content += f"**작성자:** {notice_data['author']}\n\n"
        content += f"**등록일:** {notice_data['date']}\n\n"
        content += f"**URL:** {detail_url}\n\n"
        content += f"**수집 시간:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        content += "---\n\n"
        
        # Add main content
        if content_markdown.strip():
            content += content_markdown
        else:
            content += "내용이 없습니다.\n"
        
        return content
    
    def scrape_page(self, page_url):
        """Scrape notice page"""
        try:
            self.logger.info(f"Scraping page: {page_url}")
            
            response = self.session.get(page_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser', from_encoding='utf-8')
            
            # Extract notice list
            notices = self.extract_notice_list(soup)
            
            self.logger.info(f"Found {len(notices)} notices on this page")
            return notices
            
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
                # For POST-based pagination, we might need to handle it differently
                # For now, try GET parameter approach
                separator = '&' if '?' in self.base_url else '?'
                page_url = f"{self.base_url}{separator}pageNum={page_num}"
            
            # Get notice list
            notices = self.scrape_page(page_url)
            
            if not notices:
                self.logger.warning(f"No notices found on page {page_num}")
                # If no notices on page 1, break
                if page_num == 1:
                    break
                continue
            
            # Process each notice
            for i, notice in enumerate(notices, 1):
                self.logger.info(f"\nProcessing notice {i}/{len(notices)}: {notice['title'][:50]}...")
                success = self.scrape_notice_detail(notice)
                
                if success:
                    self.logger.info(f"✓ Successfully processed notice {notice['id']}")
                else:
                    self.logger.error(f"✗ Failed to process notice {notice['id']}")
                
                # Add delay between requests
                time.sleep(1)
            
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
        self.logger.info(f"Total notices scraped: {self.stats['total_notices']}")
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
    base_url = "https://www.gfund.kr/hp/info/M04_L01.do"
    site_code = "gfund"
    max_pages = 3
    
    # Initialize scraper
    scraper = GFUNDScraper(base_url, site_code)
    
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