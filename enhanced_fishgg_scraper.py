# -*- coding: utf-8 -*-
"""
Fish.gg.go.kr(경기도 해양수산자원연구소) 공고 스크래퍼
URL: https://fish.gg.go.kr/noti/27
"""

import re
import json
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup
from enhanced_base_scraper import EnhancedBaseScraper

logger = logging.getLogger(__name__)

class EnhancedFishggScraper(EnhancedBaseScraper):
    """경기도 해양수산자원연구소 공고 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        
        # 사이트 기본 설정
        self.base_url = "https://fish.gg.go.kr"
        self.list_url = "https://fish.gg.go.kr/noti/27"
        self.start_url = self.list_url
        
        # 헤더 설정
        self.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        self.session.headers.update(self.headers)
        
        # 현재 상세 페이지 URL 저장 (Referer 용)
        self.current_detail_url = None
        
    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 생성"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}?c_paged={page_num}"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 테이블 찾기
        table = soup.find('table', class_='board')
        if not table:
            logger.warning("공고 테이블을 찾을 수 없습니다")
            return announcements
        
        # tbody 찾기
        tbody = table.find('tbody')
        if not tbody:
            logger.warning("테이블 tbody를 찾을 수 없습니다")
            return announcements
        
        # 각 행 처리
        rows = tbody.find_all('tr')
        logger.info(f"총 {len(rows)}개의 공고 행 발견")
        
        for i, row in enumerate(rows):
            try:
                cells = row.find_all('td')
                if len(cells) < 5:  # 최소 5개 컬럼 확인
                    continue
                
                # 컬럼 구조: 번호, 제목, 글쓴이, 작성일, 조회수
                number_cell = cells[0]
                title_cell = cells[1]
                author_cell = cells[2]
                date_cell = cells[3]
                views_cell = cells[4]
                
                # 번호 처리
                number = number_cell.get_text(strip=True)
                
                # 제목 및 링크 추출
                title_link = title_cell.find('a')
                if not title_link:
                    continue
                
                title = title_link.get_text(strip=True)
                if not title:
                    continue
                
                # 상세 페이지 URL 추출
                href = title_link.get('href', '')
                if not href:
                    continue
                
                # 상대 URL을 절대 URL로 변환
                detail_url = urljoin(self.base_url, href)
                
                # 공고 정보 구성
                announcement = {
                    'number': number,
                    'title': title,
                    'url': detail_url,
                    'author': author_cell.get_text(strip=True) if author_cell else '',
                    'date': date_cell.get_text(strip=True) if date_cell else '',
                    'views': views_cell.get_text(strip=True) if views_cell else ''
                }
                
                announcements.append(announcement)
                logger.debug(f"공고 파싱 완료: {title[:50]}...")
                
            except Exception as e:
                logger.error(f"공고 {i+1} 파싱 중 오류: {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
        return announcements
    
    def parse_detail_page(self, html_content: str, detail_url: str = None) -> Dict[str, Any]:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 현재 상세 페이지 URL 저장
        if detail_url:
            self.current_detail_url = detail_url
        
        # 본문 내용 추출
        content = self._extract_content(soup)
        
        # 첨부파일 추출
        attachments = self._extract_attachments(soup)
        
        return {
            'content': content,
            'attachments': attachments
        }
    
    def _extract_content(self, soup: BeautifulSoup) -> str:
        """본문 내용 추출"""
        content_parts = []
        
        # 방법 1: 본문 영역 직접 찾기
        content_td = soup.find('td', class_='post-content')
        if content_td:
            # 텍스트 추출 및 정리
            text = content_td.get_text(strip=True)
            if text and len(text) > 50:
                content_parts.append(text)
        
        # 방법 2: 테이블 내 본문 찾기
        if not content_parts:
            tables = soup.find_all('table')
            for table in tables:
                if 'single' in table.get('class', []):
                    tbody = table.find('tbody')
                    if tbody:
                        content_td = tbody.find('td')
                        if content_td:
                            text = content_td.get_text(strip=True)
                            if text and len(text) > 50:
                                content_parts.append(text)
                                break
        
        # 방법 3: 전체 본문 영역 찾기
        if not content_parts:
            post_content = soup.find('div', class_='post-content')
            if post_content:
                content_parts.append(post_content.get_text(strip=True))
        
        # 방법 4: 마지막 수단 - 페이지 전체에서 의미있는 텍스트 추출
        if not content_parts:
            # 제목 추출
            title_th = soup.find('th', class_='title')
            if title_th:
                title_text = title_th.get_text(strip=True)
                # 조회수 부분 제거
                title_text = re.sub(r'조회수\s*\|\s*\d+', '', title_text).strip()
                if title_text:
                    content_parts.append(f"제목: {title_text}")
            
            # 본문 단락들 찾기
            paragraphs = soup.find_all('p')
            for p in paragraphs:
                text = p.get_text(strip=True)
                if text and len(text) > 20:
                    content_parts.append(text)
        
        # 최종 본문 구성
        if content_parts:
            return "\n\n".join(content_parts)
        else:
            return "본문 내용을 추출할 수 없습니다."
    
    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """첨부파일 추출"""
        attachments = []
        
        # 방법 1: 첨부파일 섹션에서 추출
        attachment_section = soup.find('div', class_='post-attachment')
        if attachment_section:
            attachment_list = attachment_section.find('div', class_='attachment-list')
            if attachment_list:
                links = attachment_list.find_all('a')
                for link in links:
                    href = link.get('href', '')
                    filename = link.get_text(strip=True)
                    
                    if href and filename:
                        # 파일명에서 아이콘 정보 제거
                        filename = re.sub(r'extension_icon\s*', '', filename).strip()
                        
                        # 상대 URL을 절대 URL로 변환
                        download_url = urljoin(self.base_url, href)
                        
                        # 파일 확장자 추출
                        file_ext = filename.split('.')[-1].upper() if '.' in filename else 'UNKNOWN'
                        
                        attachments.append({
                            'filename': filename,
                            'url': download_url,
                            'size': '',
                            'type': file_ext
                        })
        
        # 방법 2: 직접 다운로드 링크 찾기
        if not attachments:
            # wp-content/uploads 패턴의 링크 찾기
            all_links = soup.find_all('a', href=re.compile(r'wp-content/uploads'))
            for link in all_links:
                href = link.get('href', '')
                filename = link.get_text(strip=True)
                
                if href and filename:
                    download_url = urljoin(self.base_url, href)
                    file_ext = filename.split('.')[-1].upper() if '.' in filename else 'UNKNOWN'
                    
                    attachments.append({
                        'filename': filename,
                        'url': download_url,
                        'size': '',
                        'type': file_ext
                    })
        
        # 방법 3: download 속성이 있는 링크 찾기
        if not attachments:
            download_links = soup.find_all('a', download=True)
            for link in download_links:
                href = link.get('href', '')
                filename = link.get_text(strip=True)
                
                if href and filename:
                    download_url = urljoin(self.base_url, href)
                    file_ext = filename.split('.')[-1].upper() if '.' in filename else 'UNKNOWN'
                    
                    attachments.append({
                        'filename': filename,
                        'url': download_url,
                        'size': '',
                        'type': file_ext
                    })
        
        logger.info(f"첨부파일 {len(attachments)}개 추출")
        return attachments


def main():
    """메인 실행 함수 - 3페이지 수집"""
    import sys
    import os
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('fishgg_scraper.log', encoding='utf-8')
        ]
    )
    
    logger.info("="*60)
    logger.info("🚀 Fish.gg.go.kr(경기도 해양수산자원연구소) 공고 스크래퍼 시작")
    logger.info("="*60)
    
    # 출력 디렉토리 설정
    output_dir = "output/fishgg"
    
    # 기존 출력 디렉토리 정리 (파일만 삭제, 디렉토리 구조 유지)
    if os.path.exists(output_dir):
        import shutil
        logger.info(f"기존 출력 디렉토리 정리: {output_dir}")
        shutil.rmtree(output_dir)
    
    # 스크래퍼 초기화
    scraper = EnhancedFishggScraper()
    
    try:
        # 3페이지 수집 실행
        success = scraper.scrape_pages(max_pages=3, output_base="output/fishgg")
        
        if success:
            logger.info("✅ 스크래핑 완료!")
            
            # 통계 출력
            stats = scraper.get_stats()
            logger.info(f"📊 처리 통계: {stats}")
            
        else:
            logger.error("❌ 스크래핑 실패")
            return 1
            
    except KeyboardInterrupt:
        logger.info("⏹️  사용자에 의해 중단됨")
        return 1
    except Exception as e:
        logger.error(f"❌ 예상치 못한 오류: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())