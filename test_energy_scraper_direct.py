#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
에너지공단 스크래퍼 직접 테스트
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from enhanced_energy_scraper import EnhancedEnergyScraper
from bs4 import BeautifulSoup

def test_scraper_directly():
    """스크래퍼 직접 테스트"""
    
    # 스크래퍼 인스턴스 생성
    scraper = EnhancedEnergyScraper()
    
    # 첫 번째 공고 정보 (직접 설정)
    announcement = {
        'board_mng_no': '2',
        'board_no': '24437',
        'title': '한국에너지공단 해외사업 위탁정산기관 모집 안내'
    }
    
    print("1. 상세 페이지 HTML 가져오기...")
    html_content = scraper.get_detail_content(announcement)
    print(f"HTML 길이: {len(html_content)} bytes")
    
    if html_content:
        # HTML 파일로 저장
        with open('test_scraper_html.html', 'w', encoding='utf-8') as f:
            f.write(html_content)
        print("HTML 파일 저장: test_scraper_html.html")
        
        print("\n2. 스크래퍼 파싱 테스트...")
        result = scraper.parse_detail_page(html_content)
        print(f"파싱 결과: content={len(result['content'])}, attachments={len(result['attachments'])}")
        
        if result['content']:
            print(f"본문 내용: {result['content'][:300]}...")
        else:
            print("본문 내용이 없음")
        
        print("\n3. 직접 BeautifulSoup 파싱 테스트...")
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 선택자 테스트
        selectors = [
            '.view_inner',
            '.view_cont',
            '.board_view',
            'article .content_inner',
            'article .board_wrap',
            'article'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                print(f"✅ {selector}: {len(text)} chars")
                if len(text) > 100:
                    print(f"   내용: {text[:100]}...")
            else:
                print(f"❌ {selector}: 찾을 수 없음")
        
        print("\n4. 스크래퍼 _extract_content 직접 테스트...")
        content = scraper._extract_content(soup)
        print(f"_extract_content 결과: {len(content)} chars")
        if content:
            print(f"내용: {content[:300]}...")
        else:
            print("내용 없음")
    
    else:
        print("❌ HTML 내용을 가져올 수 없음")

if __name__ == "__main__":
    test_scraper_directly()