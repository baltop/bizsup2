#!/usr/bin/env python3
"""
Test GWCF file download with proper filename handling
"""

import os
import re
import requests
from urllib.parse import unquote
import logging

def test_download():
    # Setup logging
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    
    # Test file URL
    file_url = "https://www.gwcf.or.kr/.attach/FILE_000000000009765?fileSn=0&download=true"
    
    logger.info(f"Testing download: {file_url}")
    
    response = session.get(file_url, stream=True, timeout=30)
    response.raise_for_status()
    
    logger.info(f"Response headers: {dict(response.headers)}")
    
    # Get filename from Content-Disposition header
    filename = "default_filename"
    if 'content-disposition' in response.headers:
        cd = response.headers['content-disposition']
        logger.info(f"Content-Disposition raw: {cd}")
        
        # Try multiple patterns for filename extraction
        # Pattern 1: filename="한글파일명.확장자"
        filename_match = re.search(r'filename\s*=\s*"([^"]+)"', cd)
        if filename_match:
            raw_filename = filename_match.group(1)
            logger.info(f"Raw filename: {raw_filename}")
            
            # Try to decode the filename properly
            try:
                # The filename might be UTF-8 encoded bytes represented as latin-1
                filename = raw_filename.encode('latin-1').decode('utf-8')
                logger.info(f"UTF-8 decoded filename: {filename}")
            except (UnicodeDecodeError, UnicodeEncodeError):
                try:
                    # Try EUC-KR encoding
                    filename = raw_filename.encode('latin-1').decode('euc-kr')
                    logger.info(f"EUC-KR decoded filename: {filename}")
                except (UnicodeDecodeError, UnicodeEncodeError):
                    # If all fails, use the raw filename
                    filename = raw_filename
                    logger.info(f"Using raw filename: {filename}")
        else:
            # Pattern 2: filename=파일명 (without quotes)
            filename_match = re.search(r'filename\s*=\s*([^;]+)', cd)
            if filename_match:
                filename = filename_match.group(1).strip('\'"')
                logger.info(f"Pattern 2 match: {filename}")
    
    # Create test directory
    os.makedirs('test_downloads', exist_ok=True)
    
    # Save file
    file_path = os.path.join('test_downloads', filename)
    with open(file_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    
    file_size = os.path.getsize(file_path)
    logger.info(f"Downloaded: {filename} ({file_size} bytes)")
    
    return filename, file_size

if __name__ == "__main__":
    test_download()