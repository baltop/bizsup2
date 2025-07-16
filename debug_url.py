#!/usr/bin/env python3
"""
Debug URL construction
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
})

url = "https://www.changwon.go.kr/cwportal/10310/10429/10430.web"
base_url = "https://www.changwon.go.kr"

response = session.get(url, timeout=30)
soup = BeautifulSoup(response.content, 'html.parser')

table = soup.find('table')
if table:
    rows = table.find_all('tr')
    for row in rows[:5]:  # Check first 5 rows
        cells = row.find_all('td')
        if len(cells) >= 2:
            title_cell = cells[1]
            link = title_cell.find('a')
            if link:
                href = link.get('href')
                if href:
                    print(f"Original href: {href}")
                    full_url = urljoin(base_url, href)
                    print(f"Full URL: {full_url}")
                    print(f"Title: {link.get_text(strip=True)}")
                    print("---")