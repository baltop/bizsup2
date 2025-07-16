#!/usr/bin/env python3
"""
Enhanced Changwon Support Business Notice Scraper
Site: https://www.changwon.go.kr/cwportal/10310/10429/10430.web
Code: changwon
"""

import os
import sys
import time
import requests
from bs4 import BeautifulSoup
import re
import html2text
from urllib.parse import urljoin, urlparse
from pathlib import Path
import hashlib

class ChangwonScraper:
    def __init__(self, site_code="changwon"):
        self.site_code = site_code
        self.base_url = "https://www.changwon.go.kr"
        self.list_url = "https://www.changwon.go.kr/cwportal/10310/10429/10430.web"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Create output directory
        self.output_dir = Path(f"output/{site_code}")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # HTML to Markdown converter
        self.h2m = html2text.HTML2Text()
        self.h2m.ignore_links = False
        self.h2m.ignore_images = False
        self.h2m.body_width = 0
        
        print(f"Changwon scraper initialized - Output directory: {self.output_dir}")

    def get_article_list(self, page_num=1):
        """Get article list from the given page"""
        print(f"Fetching page {page_num}...")
        
        # Build URL with page parameter
        if page_num == 1:
            url = self.list_url
        else:
            url = f"{self.list_url}?gcode=1009&cpage={page_num}"
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find article table
            articles = []
            table = soup.find('table')
            if table:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        # Check if there's a link in the title cell (usually 2nd column)
                        title_cell = cells[1]
                        link = title_cell.find('a')
                        if link:
                            href = link.get('href')
                            if href:
                                # Build full URL
                                full_url = urljoin(self.base_url, href)
                                
                                # Extract title (remove "새 글" text)
                                title = link.get_text(strip=True)
                                title = re.sub(r'\s*새\s*글\s*$', '', title)
                                
                                # Extract article number from URL
                                idx_match = re.search(r'idx=(\d+)', href)
                                if idx_match:
                                    article_num = idx_match.group(1)
                                    
                                    # Get department info (usually 3rd column)
                                    department = ""
                                    if len(cells) >= 3:
                                        department = cells[2].get_text(strip=True)
                                    
                                    articles.append({
                                        'title': title,
                                        'url': full_url,
                                        'article_num': article_num,
                                        'department': department
                                    })
            
            print(f"Found {len(articles)} articles on page {page_num}")
            return articles
            
        except Exception as e:
            print(f"Error fetching page {page_num}: {str(e)}")
            return []

    def get_article_content(self, article_url):
        """Get article content and attachments"""
        try:
            response = self.session.get(article_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract title from the page more precisely
            title = "No Title"
            text_content = soup.get_text()
            lines = text_content.split('\n')
            
            # Look for title patterns
            for line in lines:
                line = line.strip()
                if line and any(keyword in line for keyword in ['안내', '공고', '신청', '모집', '개최', '결과', '특강']):
                    if not any(skip in line for skip in ['새소식', '등록일', '담당부서', '조회수', '문의전화']):
                        title = line
                        break
            
            # Extract main content more precisely
            content_lines = []
            found_title = False
            found_content = False
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Find the title line
                if not found_title and line == title:
                    found_title = True
                    content_lines.append(f"# {line}")
                    continue
                
                # Start collecting content after metadata
                if found_title and not found_content:
                    if '○' in line or '◦' in line or '•' in line or '▷' in line or '1.' in line or '2.' in line:
                        found_content = True
                        content_lines.append(f"\n{line}")
                    elif any(keyword in line for keyword in ['드립니다', '안내', '바랍니다', '참여', '신청', '접수', '모집']):
                        found_content = True
                        content_lines.append(f"\n{line}")
                    continue
                
                # Collect content lines
                if found_content:
                    # Stop at footer content
                    if any(keyword in line for keyword in ['문의전화', '담당부서', '다음 글', '목록', '만족도', '공공누리']):
                        break
                    
                    # Skip metadata lines
                    if any(skip in line for skip in ['등록일', '담당부서', '조회수', 'KB)', 'MB)', '바로보기']):
                        continue
                    
                    content_lines.append(line)
            
            content = '\n'.join(content_lines)
            
            # If still no content, try a different approach
            if not content or len(content) < 100:
                # Look for content in the body text
                body_text = soup.get_text()
                # Find content between title and footer
                title_pos = body_text.find(title)
                if title_pos != -1:
                    content_start = title_pos + len(title)
                    content_end = body_text.find('문의전화', content_start)
                    if content_end == -1:
                        content_end = body_text.find('담당부서', content_start)
                    if content_end == -1:
                        content_end = content_start + 1000  # Limit to first 1000 chars
                    
                    content = body_text[content_start:content_end].strip()
                    # Clean up the content
                    content = re.sub(r'\s+', ' ', content)
                    content = content.replace('등록일 :', '\n등록일 :')
                    content = content.replace('○', '\n○')
                    content = f"# {title}\n\n{content}"
            
            # Find attachments with broader search
            attachments = []
            # Look for various attachment patterns
            attachment_links = soup.find_all('a', href=re.compile(r'download\.do|cmsfile|fileDownload|\.pdf|\.hwp|\.doc|\.xlsx|\.zip'))
            
            for link in attachment_links:
                href = link.get('href')
                if href:
                    # Build full URL (handle both relative and absolute URLs)
                    if href.startswith('http'):
                        full_url = href
                    else:
                        full_url = urljoin(self.base_url, href)
                    
                    # Extract filename from link text
                    filename = link.get_text(strip=True)
                    # Remove size information in parentheses
                    filename = re.sub(r'\([^)]*\)', '', filename).strip()
                    
                    # If no filename in link text, try to extract from href or generate one
                    if not filename or filename == "바로보기" or len(filename) < 3:
                        # Try to extract filename from URL or generate one
                        filename = f"attachment_{len(attachments) + 1}"
                        if '.pdf' in href or '.pdf' in filename:
                            filename += '.pdf'
                        elif '.hwp' in href or '.hwp' in filename:
                            filename += '.hwp'
                        elif '.doc' in href or '.doc' in filename:
                            filename += '.doc'
                        elif '.xlsx' in href or '.xlsx' in filename:
                            filename += '.xlsx'
                        elif '.zip' in href or '.zip' in filename:
                            filename += '.zip'
                        else:
                            filename += '.file'
                    
                    # Clean filename
                    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
                    
                    attachments.append({
                        'filename': filename,
                        'url': full_url
                    })
                    
                    print(f"Found attachment: {filename} -> {full_url}")
            
            # Remove duplicates
            unique_attachments = []
            seen_urls = set()
            for attachment in attachments:
                if attachment['url'] not in seen_urls:
                    seen_urls.add(attachment['url'])
                    unique_attachments.append(attachment)
            
            attachments = unique_attachments
            
            return {
                'title': title,
                'content': content,
                'attachments': attachments
            }
            
        except Exception as e:
            print(f"Error fetching article content: {str(e)}")
            return {
                'title': "Error",
                'content': f"Error fetching content: {str(e)}",
                'attachments': []
            }

    def download_attachment(self, attachment_url, filename, download_dir):
        """Download attachment file"""
        try:
            # Create attachment directory
            attachment_dir = download_dir / "attachments"
            attachment_dir.mkdir(exist_ok=True)
            
            # Download file
            response = self.session.get(attachment_url, timeout=60)
            response.raise_for_status()
            
            # Check if response is HTML (error page)
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' in content_type or len(response.content) < 1024:
                # Check if content looks like HTML
                if response.content.startswith(b'<!DOCTYPE') or response.content.startswith(b'<html'):
                    print(f"Skipping HTML response for {filename}")
                    return False
            
            # Save file
            file_path = attachment_dir / filename
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            # Verify file size
            file_size = file_path.stat().st_size
            if file_size > 0:
                print(f"Downloaded: {filename} ({file_size} bytes)")
                return True
            else:
                print(f"Empty file, removing: {filename}")
                file_path.unlink()
                return False
                
        except Exception as e:
            print(f"Error downloading {filename}: {str(e)}")
            return False

    def save_article(self, article_data, article_num, title):
        """Save article content and attachments"""
        # Clean title for directory name
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
        safe_title = safe_title.replace('\n', ' ').replace('\r', ' ')
        safe_title = re.sub(r'\s+', ' ', safe_title).strip()
        
        # Limit title length
        if len(safe_title) > 100:
            safe_title = safe_title[:100]
        
        # Create article directory
        article_dir = self.output_dir / f"{article_num}_{safe_title}"
        article_dir.mkdir(exist_ok=True)
        
        # Save content
        content_file = article_dir / "content.md"
        with open(content_file, 'w', encoding='utf-8') as f:
            f.write(f"# {article_data['title']}\n\n")
            f.write(article_data['content'])
        
        # Download attachments
        downloaded_count = 0
        for attachment in article_data['attachments']:
            if self.download_attachment(attachment['url'], attachment['filename'], article_dir):
                downloaded_count += 1
        
        print(f"Saved: {article_num}_{safe_title} ({downloaded_count} attachments)")
        return downloaded_count

    def scrape_pages(self, max_pages=3):
        """Scrape specified number of pages"""
        print(f"Starting scrape of {max_pages} pages...")
        
        total_articles = 0
        total_attachments = 0
        
        for page_num in range(1, max_pages + 1):
            print(f"\n--- Page {page_num} ---")
            
            # Get article list
            articles = self.get_article_list(page_num)
            
            if not articles:
                print(f"No articles found on page {page_num}")
                continue
            
            # Process each article
            for i, article in enumerate(articles, 1):
                print(f"\nProcessing article {i}/{len(articles)}: {article['title']}")
                
                # Get article content
                article_data = self.get_article_content(article['url'])
                
                # Save article
                attachment_count = self.save_article(article_data, article['article_num'], article['title'])
                
                total_articles += 1
                total_attachments += attachment_count
                
                # Delay between requests
                time.sleep(1)
            
            # Delay between pages
            time.sleep(2)
        
        print(f"\nScraping completed!")
        print(f"Total articles: {total_articles}")
        print(f"Total attachments: {total_attachments}")
        
        return total_articles, total_attachments

    def check_file_sizes(self):
        """Check for duplicate file sizes (potential errors)"""
        print("\nChecking file sizes...")
        
        file_sizes = {}
        total_files = 0
        
        for article_dir in self.output_dir.iterdir():
            if article_dir.is_dir():
                attachment_dir = article_dir / "attachments"
                if attachment_dir.exists():
                    for file_path in attachment_dir.iterdir():
                        if file_path.is_file():
                            size = file_path.stat().st_size
                            if size not in file_sizes:
                                file_sizes[size] = []
                            file_sizes[size].append(str(file_path))
                            total_files += 1
        
        # Check for suspicious duplicate sizes
        suspicious_sizes = {size: files for size, files in file_sizes.items() if len(files) > 3}
        
        if suspicious_sizes:
            print("Warning: Found potentially duplicate file sizes:")
            for size, files in suspicious_sizes.items():
                print(f"  Size {size} bytes: {len(files)} files")
                for file in files[:5]:  # Show first 5 files
                    print(f"    {file}")
                if len(files) > 5:
                    print(f"    ... and {len(files) - 5} more files")
        else:
            print("No suspicious duplicate file sizes found.")
        
        print(f"Total files checked: {total_files}")
        return suspicious_sizes

if __name__ == "__main__":
    scraper = ChangwonScraper()
    
    # Scrape 3 pages
    articles, attachments = scraper.scrape_pages(max_pages=3)
    
    # Check file sizes
    scraper.check_file_sizes()
    
    print(f"\nFinal results:")
    print(f"- Articles scraped: {articles}")
    print(f"- Attachments downloaded: {attachments}")
    print(f"- Output directory: {scraper.output_dir}")