#!/usr/bin/env python3
"""
Test script to extract proper GTC announcement content using Playwright
"""

import asyncio
import os
import requests
from playwright.async_api import async_playwright

async def test_content_extraction():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        # 목록 페이지로 이동
        await page.goto("https://www.gtc.co.kr/page/10059/10007.tc")
        await page.wait_for_timeout(3000)
        
        # 첫 번째 공지사항 클릭
        first_link = await page.query_selector('tbody tr:first-child td:nth-child(2) a')
        if first_link:
            await first_link.click()
            await page.wait_for_timeout(3000)
            
            # 제목 추출
            title_elem = await page.query_selector('p')
            if title_elem:
                title = await title_elem.text_content()
                print(f"제목: {title}")
            
            # 본문 내용 추출 (더 정확한 셀렉터 사용)
            content_divs = await page.query_selector_all('div')
            print("\\n=== 본문 내용 후보들 ===")
            for i, div in enumerate(content_divs):
                text = await div.text_content()
                if text and '■' in text and len(text) > 50:
                    print(f"[{i}] {text[:200]}...")
                    
            # 첨부파일 링크 확인
            attachment_links = await page.query_selector_all('a[href*="/file/readFile.tc"]')
            print(f"\\n=== 첨부파일 {len(attachment_links)}개 ===")
            for link in attachment_links:
                href = await link.get_attribute('href')
                text = await link.text_content()
                print(f"파일: {text}")
                print(f"URL: {href}")
                
                # 첨부파일 다운로드 테스트
                if href:
                    full_url = f"https://www.gtc.co.kr{href}"
                    print(f"다운로드 URL: {full_url}")
                    
                    # 요청 헤더 설정
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
                        'Referer': 'https://www.gtc.co.kr/page/10059/10007.tc'
                    }
                    
                    try:
                        response = requests.get(full_url, headers=headers, timeout=30)
                        print(f"응답 상태: {response.status_code}")
                        print(f"Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
                        print(f"파일 크기: {len(response.content)} bytes")
                        
                        if response.status_code == 200:
                            # 파일명 정리
                            filename = text.strip()
                            filename = filename.replace('[96KB]', '').strip()
                            
                            # 테스트 다운로드
                            test_dir = "test_downloads"
                            os.makedirs(test_dir, exist_ok=True)
                            
                            file_path = os.path.join(test_dir, filename)
                            with open(file_path, 'wb') as f:
                                f.write(response.content)
                            
                            print(f"다운로드 완료: {file_path}")
                            
                    except Exception as e:
                        print(f"다운로드 실패: {e}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_content_extraction())