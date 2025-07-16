#!/usr/bin/env python3
"""
KNREC 첨부파일 다운로드 테스트
"""
from enhanced_knrec_scraper import KnrecScraper
from pathlib import Path

def test_download():
    scraper = KnrecScraper()
    
    # 테스트 디렉토리 생성
    test_dir = Path("test_download")
    test_dir.mkdir(exist_ok=True)
    
    # 첫 번째 게시글의 첫 번째 첨부파일 다운로드 테스트
    onclick_code = "javascript:file_down('5763','1','notice')"
    filename = "2025년도 신재생에너지 금융지원사업 지원 변경 공고_최종.pdf"
    
    print(f"첨부파일 다운로드 테스트:")
    print(f"  파일명: {filename}")
    print(f"  Onclick: {onclick_code}")
    
    # Playwright로 다운로드
    result = scraper.download_attachment_with_playwright(onclick_code, filename, test_dir)
    
    print(f"다운로드 결과: {'성공' if result else '실패'}")
    
    # 다운로드된 파일 확인
    attachments_dir = test_dir / "attachments"
    if attachments_dir.exists():
        files = list(attachments_dir.iterdir())
        print(f"다운로드된 파일: {len(files)}개")
        for file in files:
            print(f"  - {file.name} ({file.stat().st_size} bytes)")

if __name__ == "__main__":
    test_download()