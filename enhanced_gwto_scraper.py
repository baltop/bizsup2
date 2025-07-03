#!/usr/bin/env python3
"""
Enhanced GWTO (강원관광재단) Scraper
URL: https://www.gwto.or.kr/www/selectBbsNttList.do?bbsNo=3&key=23
Site Code: gwto
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

class GWTOScraper:
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
    
    def download_file(self, file_url, notice_dir, original_filename):
        """Download attachment file"""
        try:
            # Get the full URL
            if not file_url.startswith('http'):
                if file_url.startswith('./'):
                    file_url = urljoin('https://www.gwto.or.kr/www/', file_url[2:])
                else:
                    file_url = urljoin('https://www.gwto.or.kr/www/', file_url)
            
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
            file_path = os.path.join(notice_dir, filename)
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
    
    def extract_notice_content(self, detail_soup):
        """Extract main content from notice detail page"""
        # Find the content area
        content_cell = detail_soup.find('td')
        if not content_cell:
            return "내용을 찾을 수 없습니다."
        
        # Find the content specifically in the row with "내용" header
        content_row = None
        for tr in detail_soup.find_all('tr'):
            th = tr.find('th')
            if th and '내용' in th.get_text():
                content_row = tr
                break
        
        if content_row:
            content_td = content_row.find('td')
            if content_td:
                # Convert to markdown
                content_html = str(content_td)
                return self.h.handle(content_html).strip()
        
        return "내용을 찾을 수 없습니다."
    
    def extract_attachments(self, detail_soup):
        """Extract attachment information from detail page"""
        attachments = []
        
        # Find attachment section
        file_row = None
        for tr in detail_soup.find_all('tr'):
            th = tr.find('th')
            if th and '파일' in th.get_text():
                file_row = tr
                break
        
        if file_row:
            file_td = file_row.find('td')
            if file_td:
                # Find all attachment links
                for link in file_td.find_all('a', href=True):
                    href = link['href']
                    filename = link.get_text().strip()
                    
                    # Clean filename from link text
                    filename = re.sub(r'^.*?(\w+\.\w+)$', r'\1', filename)
                    if not filename or '.' not in filename:
                        filename = f"attachment_{len(attachments)+1}.bin"
                    
                    attachments.append({
                        'url': href,
                        'filename': filename
                    })
        
        return attachments
    
    def scrape_notice_detail(self, notice_url, notice_title, notice_id):
        """Scrape individual notice detail page"""
        try:
            # Get full URL
            if not notice_url.startswith('http'):
                # Handle relative URLs that start with ./
                if notice_url.startswith('./'):
                    detail_url = urljoin('https://www.gwto.or.kr/www/', notice_url[2:])
                else:
                    detail_url = urljoin('https://www.gwto.or.kr/www/', notice_url)
            else:
                detail_url = notice_url
            
            self.logger.info(f"Scraping notice detail: {detail_url}")
            
            response = self.session.get(detail_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser', from_encoding='utf-8')
            
            # Create notice directory
            safe_title = self.get_safe_filename(notice_title, notice_id)
            notice_dir = os.path.join(self.output_dir, self.site_code, safe_title)
            os.makedirs(notice_dir, exist_ok=True)
            
            # Extract main content
            content = self.extract_notice_content(soup)
            
            # Save content as markdown
            content_file = os.path.join(notice_dir, f"{safe_title}.md")
            with open(content_file, 'w', encoding='utf-8') as f:
                f.write(f"# {notice_title}\n\n")
                f.write(f"**공고 ID:** {notice_id}\n\n")
                f.write(f"**URL:** {detail_url}\n\n")
                f.write(f"**수집 시간:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write("---\n\n")
                f.write(content)
            
            # Extract and download attachments
            attachments = self.extract_attachments(soup)
            downloaded_files = []
            
            for attachment in attachments:
                filename, file_size = self.download_file(
                    attachment['url'], 
                    notice_dir, 
                    attachment['filename']
                )
                if filename:
                    downloaded_files.append({
                        'filename': filename,
                        'size': file_size
                    })
            
            self.logger.info(f"Notice '{notice_title}' processed successfully. Content saved, {len(downloaded_files)} files downloaded.")
            self.stats['total_notices'] += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to scrape notice detail {notice_url}: {str(e)}")
            return False
    
    def scrape_notice_list(self, page_url):
        """Scrape notice list page"""
        try:
            self.logger.info(f"Scraping page: {page_url}")
            
            response = self.session.get(page_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser', from_encoding='utf-8')
            
            # Find notice table
            notice_table = soup.find('table', class_='p-table')
            if not notice_table:
                self.logger.warning("No notice table found")
                return []
            
            notices = []
            tbody = notice_table.find('tbody')
            if tbody:
                for row in tbody.find_all('tr'):
                    # Extract notice information
                    cells = row.find_all('td')
                    if len(cells) >= 4:
                        # Find title link
                        title_cell = cells[1]  # Second column is title
                        title_link = title_cell.find('a', href=True)
                        
                        if title_link:
                            title = title_link.get_text().strip()
                            title = re.sub(r'\s+', ' ', title)  # Clean whitespace
                            notice_url = title_link['href']
                            
                            # Extract notice ID from URL
                            notice_id_match = re.search(r'nttNo=(\d+)', notice_url)
                            notice_id = notice_id_match.group(1) if notice_id_match else 'unknown'
                            
                            notices.append({
                                'title': title,
                                'url': notice_url,
                                'id': notice_id
                            })
            
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
                page_url = f"{self.base_url}&pageIndex={page_num}"
            
            # Get notice list
            notices = self.scrape_notice_list(page_url)
            
            if not notices:
                self.logger.warning(f"No notices found on page {page_num}")
                continue
            
            # Process each notice
            for i, notice in enumerate(notices, 1):
                self.logger.info(f"\nProcessing notice {i}/{len(notices)}: {notice['title'][:50]}...")
                success = self.scrape_notice_detail(notice['url'], notice['title'], notice['id'])
                
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
    base_url = "https://www.gwto.or.kr/www/selectBbsNttList.do?bbsNo=3&key=23"
    site_code = "gwto"
    max_pages = 3
    
    # Initialize scraper
    scraper = GWTOScraper(base_url, site_code)
    
    try:
        # Start scraping
        scraper.scrape_pages(max_pages)
        
        # Print statistics
        scraper.print_statistics()
        
    except KeyboardInterrupt:
        scraper.logger.info("\nScraping interrupted by user")
    except Exception as e:
        scraper.logger.error(f"Scraping failed: {str(e)}")
    finally:
        scraper.logger.info("Scraping completed")

if __name__ == "__main__":
    main()