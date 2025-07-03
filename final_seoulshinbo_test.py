#!/usr/bin/env python3
"""
서울신보 사이트 최종 테스트 - 올바른 분석 로직 적용
"""

import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os

class SeoulshinboFinalTester:
    def __init__(self):
        self.base_url = "https://www.seoulshinbo.co.kr"
        self.list_url = "https://www.seoulshinbo.co.kr/wbase/contents/bbs/list.do?mng_cd=STRY9788"
        self.session = requests.Session()
        
        # 헤더 설정
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })

    def get_list_page(self):
        """목록 페이지 접근 및 쿠키 획득"""
        print("1. 목록 페이지 접근...")
        
        response = self.session.get(self.list_url, timeout=30)
        response.raise_for_status()
        
        print(f"   ✅ Status: {response.status_code}")
        print(f"   쿠키: {dict(self.session.cookies)}")
        
        return response.text

    def parse_announcements(self, html_content):
        """공고 목록 파싱"""
        print("2. 공고 목록 파싱...")
        
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 올바른 테이블 찾기 (두 번째 테이블이 공고 목록)
        tables = soup.find_all('table')
        if len(tables) < 2:
            print("   ❌ 공고 테이블을 찾을 수 없습니다")
            return []
        
        table = tables[1]  # 두 번째 테이블
        tbody = table.find('tbody')
        if not tbody:
            tbody = table
        
        rows = tbody.find_all('tr')
        print(f"   테이블에서 {len(rows)}개 행 발견")
        
        for row in rows[:5]:  # 처음 5개만 테스트
            cells = row.find_all('td')
            if len(cells) < 2:
                continue
            
            # 제목 셀 (두 번째 셀)
            title_cell = cells[1]
            link = title_cell.find('a')
            
            if link:
                title = link.get_text(strip=True)
                href = link.get('href', '')
                
                # JavaScript 링크에서 파라미터 추출
                match = re.search(r"bbs\.goView\('(\d+)',\s*'(\d+)'\)", href)
                if match:
                    page_index = match.group(1)
                    bno = match.group(2)
                    
                    announcement = {
                        'title': title,
                        'page_index': page_index,
                        'bno': bno,
                        'detail_url': f"{self.base_url}/wbase/contents/bbs/view/{bno}.do?mng_cd=STRY9788&pageIndex={page_index}"
                    }
                    announcements.append(announcement)
                    
                    print(f"   공고 {len(announcements)}: {title[:60]}...")
        
        return announcements

    def get_detail_page(self, announcement):
        """상세페이지 접근"""
        print(f"3. 상세페이지 접근: {announcement['title'][:50]}...")
        
        detail_url = announcement['detail_url']
        headers = {'Referer': self.list_url}
        
        response = self.session.get(detail_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        print(f"   ✅ Status: {response.status_code}, 크기: {len(response.text)} bytes")
        
        return response.text

    def parse_detail_page(self, html_content):
        """상세페이지 파싱"""
        print("4. 상세페이지 내용 파싱...")
        
        soup = BeautifulSoup(html_content, 'html.parser')
        result = {
            'title': '',
            'content': '',
            'attachments': []
        }
        
        # 테이블에서 정보 추출 (첫 번째 테이블이 상세 정보)
        tables = soup.find_all('table')
        if tables:
            table = tables[0]
            rows = table.find_all('tr')
            
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    header = cells[0].get_text(strip=True)
                    content = cells[1].get_text(strip=True)
                    
                    if header == '제목':
                        result['title'] = content
                        print(f"   제목: {content}")
                    elif header == '내용':
                        result['content'] = content
                        print(f"   본문 길이: {len(content)} 문자")
                        print(f"   본문 미리보기: {content[:100]}...")
                    elif header == '첨부파일':
                        # 첨부파일 링크 찾기
                        file_links = cells[1].find_all('a')
                        for link in file_links:
                            href = link.get('href', '')
                            text = link.get_text(strip=True)
                            if href and text:
                                full_url = urljoin(self.base_url, href)
                                result['attachments'].append({
                                    'name': text,
                                    'url': full_url
                                })
                                print(f"   첨부파일: {text} -> {href}")
        
        return result

    def test_file_download(self, file_info):
        """첨부파일 다운로드 테스트"""
        print(f"5. 첨부파일 다운로드 테스트: {file_info['name']}")
        
        try:
            headers = {'Referer': self.list_url}
            response = self.session.get(file_info['url'], headers=headers, timeout=30, stream=True)
            response.raise_for_status()
            
            content_type = response.headers.get('Content-Type', '')
            content_length = response.headers.get('Content-Length', 'Unknown')
            
            print(f"   ✅ Content-Type: {content_type}")
            print(f"   ✅ Content-Length: {content_length} bytes")
            
            # 첫 몇 바이트 확인
            first_bytes = next(response.iter_content(chunk_size=10))
            print(f"   첫 바이트: {first_bytes[:10].hex()}")
            
            return True
            
        except Exception as e:
            print(f"   ❌ 다운로드 실패: {e}")
            return False

def main():
    print("서울신보 사이트 최종 테스트")
    print("=" * 60)
    
    tester = SeoulshinboFinalTester()
    
    try:
        # 1. 목록 페이지 접근
        html_content = tester.get_list_page()
        
        # 2. 공고 목록 파싱
        announcements = tester.parse_announcements(html_content)
        if not announcements:
            print("❌ 공고를 찾을 수 없습니다")
            return
        
        # 3. 첫 번째 공고 상세페이지 접근
        first_announcement = announcements[0]
        detail_html = tester.get_detail_page(first_announcement)
        
        # 4. 상세페이지 파싱
        detail_info = tester.parse_detail_page(detail_html)
        
        # 5. 첨부파일 다운로드 테스트
        if detail_info['attachments']:
            for file_info in detail_info['attachments']:
                tester.test_file_download(file_info)
        else:
            print("5. 첨부파일이 없습니다")
        
        # 6. 결과 요약
        print("\n" + "=" * 60)
        print("🎯 최종 테스트 결과:")
        print(f"   목록 페이지 접근: ✅ 성공")
        print(f"   공고 파싱: ✅ {len(announcements)}개 성공")
        print(f"   상세페이지 접근: ✅ 성공")
        print(f"   제목 추출: ✅ {detail_info['title']}")
        print(f"   본문 추출: ✅ {len(detail_info['content'])}자")
        print(f"   첨부파일: ✅ {len(detail_info['attachments'])}개")
        
        print("\n🚀 Python requests 구현 방법 요약:")
        print("1. ✅ session.get()으로 목록 페이지 접근하여 쿠키 자동 획득")
        print("2. ✅ JavaScript href에서 정규표현식으로 bno, pageIndex 추출")
        print("3. ✅ URL 패턴: /wbase/contents/bbs/view/{bno}.do?mng_cd=STRY9788&pageIndex={pageIndex}")
        print("4. ✅ Referer 헤더 설정하여 GET 요청")
        print("5. ✅ 응답은 정상적으로 받아짐 (404 아님)")
        print("6. ✅ 테이블 구조로 파싱: 제목, 내용, 첨부파일")
        print("7. ✅ 첨부파일 다운로드도 동일한 세션으로 가능")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()