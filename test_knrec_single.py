#!/usr/bin/env python3
"""
KNREC 단일 게시글 테스트
"""
from enhanced_knrec_scraper import KnrecScraper

def test_single_post():
    scraper = KnrecScraper()
    
    # 첫 번째 게시글 URL
    post_url = "https://www.knrec.or.kr/biz/pds/businoti/view.do?no=5763"
    
    print(f"게시글 상세 정보 테스트: {post_url}")
    
    # 게시글 상세 정보 가져오기
    content, attachments, department, date, views = scraper.get_post_detail_with_playwright(post_url)
    
    print(f"Content length: {len(content) if content else 0}")
    print(f"Attachments: {len(attachments)}")
    print(f"Department: {department}")
    print(f"Date: {date}")
    print(f"Views: {views}")
    
    for i, attachment in enumerate(attachments):
        print(f"Attachment {i+1}:")
        print(f"  Name: {attachment['name']}")
        print(f"  URL: {attachment['url']}")
        print(f"  Onclick: {attachment['onclick']}")

if __name__ == "__main__":
    test_single_post()