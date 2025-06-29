#!/usr/bin/env python3
"""
CBSINBO 디버그 스크립트 - Referer 설정 확인
"""

import requests
from enhanced_cbsinbo_scraper import EnhancedCbsinboScraper

def debug_cbsinbo_referer():
    """CBSINBO Referer 설정 디버그"""
    
    scraper = EnhancedCbsinboScraper()
    
    # 1. 목록 페이지에서 첫 번째 첨부파일 공고 찾기
    print("1단계: 목록 페이지 파싱")
    list_response = scraper.session.get(scraper.list_url, verify=False)
    announcements = scraper.parse_list_page(list_response.text)
    
    # 첨부파일이 있는 공고 찾기
    target_announcement = None
    for announcement in announcements:
        if announcement.get('has_attachments'):
            target_announcement = announcement
            break
    
    if not target_announcement:
        print("❌ 첨부파일이 있는 공고를 찾을 수 없습니다.")
        return
    
    print(f"대상 공고: {target_announcement['title']}")
    print(f"상세 URL: {target_announcement['url']}")
    
    # 2. current_detail_url 설정 테스트
    print("\n2단계: current_detail_url 설정 테스트")
    scraper.current_detail_url = target_announcement['url']
    print(f"설정된 current_detail_url: {scraper.current_detail_url}")
    
    # 3. 상세 페이지 파싱
    print("\n3단계: 상세 페이지 파싱")
    detail_response = scraper.session.get(target_announcement['url'], verify=False)
    detail_data = scraper.parse_detail_page(detail_response.text)
    
    if not detail_data['attachments']:
        print("❌ 상세 페이지에서 첨부파일을 찾을 수 없습니다.")
        return
    
    attachment = detail_data['attachments'][0]
    print(f"첨부파일: {attachment['filename']}")
    print(f"다운로드 URL: {attachment['url']}")
    
    # 4. 직접 다운로드 테스트 (수동 Referer 설정)
    print("\n4단계: 수동 Referer 다운로드 테스트")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': target_announcement['url'],  # 직접 설정
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }
    
    print(f"Referer 헤더: {headers['Referer']}")
    
    response = requests.get(attachment['url'], headers=headers, verify=False)
    print(f"응답 상태: {response.status_code}")
    print(f"파일 크기: {len(response.content)} bytes")
    
    if len(response.content) == 33:
        content_text = response.content.decode('utf-8', errors='ignore')
        print(f"오류 내용: {content_text}")
    else:
        print("✅ 정상 다운로드!")
        return True
    
    # 5. 스크래퍼 download_file 메서드 테스트
    print("\n5단계: 스크래퍼 download_file 메서드 테스트")
    
    # current_detail_url이 설정되었는지 확인
    print(f"scraper.current_detail_url: {scraper.current_detail_url}")
    
    test_save_path = "/tmp/test_cbsinbo_download.hwp"
    success = scraper.download_file(attachment['url'], test_save_path, attachment)
    
    if success:
        print("✅ 스크래퍼 다운로드 성공!")
        return True
    else:
        print("❌ 스크래퍼 다운로드 실패!")
        return False

if __name__ == "__main__":
    debug_cbsinbo_referer()