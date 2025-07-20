#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test attachment URL extraction specifically
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

# Get the detail page
url = "http://www.injeart.or.kr/?p=19&page=1&viewMode=view&reqIdx=202507181020209469"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

response = requests.get(url, headers=headers, verify=False)
soup = BeautifulSoup(response.text, 'html.parser')

print("=== 첨부파일 추출 테스트 ===")

# 방법 1: "첨부파일" 라벨이 있는 행에서 찾기 - 인제 사이트 특화
attachments = []
base_url = "http://www.injeart.or.kr"

attach_cells = soup.find_all(['th', 'td'], string=lambda text: text and '첨부파일' in text)
print(f"첨부파일 셀 발견: {len(attach_cells)}개")

for cell in attach_cells:
    parent_row = cell.find_parent('tr')
    if parent_row:
        file_links = parent_row.find_all('a')
        print(f"링크 발견: {len(file_links)}개")
        
        for i, link in enumerate(file_links):
            onclick = link.get('onclick', '')
            filename = link.get_text(strip=True)
            href = link.get('href', '')
            
            print(f"\n링크 {i+1}:")
            print(f"  파일명: {filename}")
            print(f"  href: {href}")
            print(f"  onclick: {onclick}")
            
            # chkDownAuth('id') 패턴 파싱
            if onclick and 'chkDownAuth(' in onclick:
                match = re.search(r"chkDownAuth\('([^']+)'\)", onclick)
                if match and filename:
                    file_id = match.group(1)
                    download_url = f"{base_url}/inc/down.php?fileidx={file_id}"
                    attachments.append({
                        'filename': filename,
                        'url': download_url
                    })
                    print(f"  → 다운로드 URL: {download_url}")

print(f"\n=== 최종 첨부파일 목록 ({len(attachments)}개) ===")
for i, att in enumerate(attachments):
    print(f"{i+1}. {att['filename']} -> {att['url']}")