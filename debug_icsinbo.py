#!/usr/bin/env python3
"""
ICSINBO HTML 구조 디버깅
"""

import requests
from bs4 import BeautifulSoup
import re

def debug_icsinbo_structure():
    """ICSINBO 사이트 구조 디버깅"""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
    })
    
    list_url = "https://www.icsinbo.or.kr/home/board/brdList.do?menu_cd=000096"
    
    try:
        response = session.get(list_url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        print("=== ICSINBO HTML 구조 분석 ===")
        print(f"페이지 제목: {soup.title.text if soup.title else 'N/A'}")
        
        # 1. 모든 링크 찾기
        all_links = soup.find_all('a')
        print(f"\n전체 링크 수: {len(all_links)}")
        
        # onclick이 있는 링크들
        onclick_links = [link for link in all_links if link.get('onclick')]
        print(f"onclick이 있는 링크: {len(onclick_links)}")
        
        for i, link in enumerate(onclick_links[:5]):  # 처음 5개만
            print(f"  {i+1}. onclick: {link.get('onclick')}")
            print(f"     text: {link.get_text(strip=True)[:50]}...")
        
        # 2. JavaScript 함수 패턴 찾기
        js_patterns = [
            r'pageviewform\(',
            r'viewDetail\(',
            r'linkPage\(',
            r'javascript:',
            r'pageview\('
        ]
        
        for pattern in js_patterns:
            matches = re.findall(pattern, response.text, re.IGNORECASE)
            if matches:
                print(f"\n패턴 '{pattern}' 발견: {len(matches)}개")
                
                # 실제 함수 호출 찾기
                full_matches = re.findall(pattern + r'[^)]*\)', response.text, re.IGNORECASE)
                for match in full_matches[:3]:  # 처음 3개만
                    print(f"  {match}")
        
        # 3. 테이블 구조 찾기
        tables = soup.find_all('table')
        print(f"\n테이블 수: {len(tables)}")
        
        for i, table in enumerate(tables):
            rows = table.find_all('tr')
            if len(rows) > 3:  # 의미있는 테이블만
                print(f"  테이블 {i+1}: {len(rows)}개 행")
                if rows:
                    first_row = rows[0]
                    cells = first_row.find_all(['td', 'th'])
                    print(f"    첫 행 셀 수: {len(cells)}")
                    if cells:
                        print(f"    첫 셀 내용: {cells[0].get_text(strip=True)[:30]}...")
        
        # 4. 리스트 구조 찾기
        uls = soup.find_all('ul')
        meaningful_uls = [ul for ul in uls if len(ul.find_all('li')) > 3]
        print(f"\n의미있는 ul 리스트: {len(meaningful_uls)}")
        
        for i, ul in enumerate(meaningful_uls[:2]):  # 처음 2개만
            lis = ul.find_all('li')
            print(f"  리스트 {i+1}: {len(lis)}개 항목")
            if lis:
                first_li = lis[0]
                print(f"    첫 항목 내용: {first_li.get_text(strip=True)[:50]}...")
                
                # 링크 확인
                links_in_li = first_li.find_all('a')
                if links_in_li:
                    print(f"    첫 항목 링크 onclick: {links_in_li[0].get('onclick', 'N/A')}")
        
        # 5. 특정 클래스나 ID 찾기
        interesting_elements = soup.find_all(['div', 'section'], class_=re.compile(r'(list|board|content|notice)', re.I))
        print(f"\n관심있는 요소 (list/board/content/notice): {len(interesting_elements)}")
        
        for elem in interesting_elements[:3]:
            print(f"  태그: {elem.name}, 클래스: {elem.get('class')}")
            if elem.get_text(strip=True):
                print(f"    내용: {elem.get_text(strip=True)[:50]}...")
        
        # 6. AJAX 요청 패턴 찾기
        ajax_patterns = [
            r'\.ajax\(',
            r'XMLHttpRequest',
            r'fetch\(',
            r'$.post',
            r'$.get'
        ]
        
        for pattern in ajax_patterns:
            if re.search(pattern, response.text, re.IGNORECASE):
                print(f"\nAJAX 패턴 '{pattern}' 발견됨")
        
        # 7. 스크립트 태그 내용 확인
        scripts = soup.find_all('script')
        print(f"\n스크립트 태그 수: {len(scripts)}")
        
        for script in scripts:
            if script.string and len(script.string) > 100:
                script_content = script.string[:200]
                if 'pageviewform' in script_content or 'linkPage' in script_content:
                    print(f"  관련 스크립트 발견:")
                    print(f"    {script_content}...")
                    
    except Exception as e:
        print(f"오류: {e}")

if __name__ == "__main__":
    debug_icsinbo_structure()