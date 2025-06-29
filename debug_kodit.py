#!/usr/bin/env python3
"""
KODIT 사이트 디버깅 스크립트
"""

from playwright.sync_api import sync_playwright
import time

def debug_kodit():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # 헤드리스 모드 끄기
        page = browser.new_page()
        
        # 페이지 이동
        url = "https://www.kodit.co.kr/kodit/na/ntt/selectNttList.do?mi=2638&bbsId=148"
        page.goto(url)
        page.wait_for_load_state('networkidle')
        
        print("페이지 로드 완료")
        
        # 테이블 확인
        table = page.locator('table').first
        if table.is_visible():
            print("테이블 발견됨")
            
            # 첫 번째 행의 링크 확인
            first_row_link = page.locator('table tbody tr:first-child td:nth-child(2) a').first
            if first_row_link.is_visible():
                print("첫 번째 링크 발견됨")
                print(f"링크 텍스트: {first_row_link.inner_text()}")
                print(f"링크 href: {first_row_link.get_attribute('href')}")
                
                # 클릭 시도
                print("링크 클릭 시도...")
                first_row_link.click()
                page.wait_for_load_state('networkidle')
                time.sleep(2)
                
                print(f"새 URL: {page.url}")
                
                # 상세 페이지 제목 확인
                title = page.locator('h3').first
                if title.is_visible():
                    print(f"상세 페이지 제목: {title.inner_text()}")
                else:
                    print("상세 페이지 제목을 찾을 수 없음")
                
                # 본문 내용 확인
                content_divs = page.locator('div').all()
                print(f"총 div 개수: {len(content_divs)}")
                
                for i, div in enumerate(content_divs[:10]):  # 처음 10개만 확인
                    text = div.inner_text().strip()
                    if len(text) > 50:
                        print(f"div {i}: {text[:100]}...")
                
            else:
                print("첫 번째 링크를 찾을 수 없음")
                
                # 모든 링크 찾기
                all_links = page.locator('a').all()
                print(f"페이지의 모든 링크 수: {len(all_links)}")
                
                for i, link in enumerate(all_links[:10]):
                    href = link.get_attribute('href')
                    text = link.inner_text().strip()
                    if text:
                        print(f"링크 {i}: {text[:50]} -> {href}")
        else:
            print("테이블을 찾을 수 없음")
            
        print("Enter 키를 눌러 종료...")
        input()
        
        browser.close()

if __name__ == "__main__":
    debug_kodit()