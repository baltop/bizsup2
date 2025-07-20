# -*- coding: utf-8 -*-
"""
GuroArtsValley.or.kr(구로문화재단) 재단소식 스크래퍼
URL: https://guroartsvalley.or.kr/user/board/mn011801.do
"""

import re
import json
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup
from enhanced_base_scraper import EnhancedBaseScraper

logger = logging.getLogger(__name__)

class EnhancedGuroArtsValleyScraper(EnhancedBaseScraper):
    """구로문화재단 재단소식 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        
        # 사이트 기본 설정
        self.base_url = "https://guroartsvalley.or.kr"
        self.list_url = "https://guroartsvalley.or.kr/user/board/mn011801.do"
        self.start_url = self.list_url
        
        # 헤더 설정
        self.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        self.session.headers.update(self.headers)
        
        # 현재 상세 페이지 URL 저장 (Referer 용)
        self.current_detail_url = None
        
        # 메뉴코드 (고정값)
        self.menu_code = "mn011801"
        
    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 생성"""
        return f"{self.list_url}?page={page_num}&pageSC=&pageSO=&pageST=&pageSV="
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 테이블 찾기
        table = soup.find('table', class_='bbs-list')
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
                
                # 컬럼 구조: 번호, 구분, 제목, 등록일, 조회수
                number_cell = cells[0]
                category_cell = cells[1]
                title_cell = cells[2]
                date_cell = cells[3]
                views_cell = cells[4]
                
                # 번호 처리 (공지사항인 경우 "공지"로 표시)
                number = number_cell.get_text(strip=True)
                if not number or number == "공지":
                    number = "공지"
                
                # 구분 처리
                category = category_cell.get_text(strip=True)
                
                # 제목 및 JavaScript 링크 추출
                title_link = title_cell.find('a')
                if not title_link:
                    continue
                
                title = title_link.get_text(strip=True)
                if not title:
                    continue
                
                # JavaScript 링크에서 boardId 추출
                href = title_link.get('href', '')
                if not href or 'goView' not in href:
                    continue
                
                # goView('12745',0) 형태에서 boardId 추출
                match = re.search(r"goView\('(\d+)',(\d+)\)", href)
                if not match:
                    continue
                
                board_id = match.group(1)
                index = match.group(2)
                
                # 상세 페이지 URL 구성
                detail_url = (f"{self.base_url}/user/board/boardDefaultView.do"
                            f"?page=1&pageST=&pageSV=&itemCd1=&itemCd2=&menuCode={self.menu_code}"
                            f"&boardId={board_id}&index={index}")
                
                # 공고 정보 구성
                announcement = {
                    'number': number,
                    'category': category,
                    'title': title,
                    'url': detail_url,
                    'board_id': board_id,
                    'index': index,
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
        
        # 첨부파일 추출 (본문 추출 전에 먼저 실행)
        attachments = self._extract_attachments(soup)
        
        # 본문 내용 추출
        content = self._extract_content(soup)
        
        return {
            'content': content,
            'attachments': attachments
        }
    
    def _extract_content(self, soup: BeautifulSoup) -> str:
        """본문 내용 추출"""
        content_parts = []
        
        # 방법 1: 메인 콘텐츠 영역 찾기
        content_div = soup.find('div', class_='cont_w')
        if content_div:
            # 첨부파일 링크 제외하고 본문만 추출
            # 첨부파일 span 제거
            for attachment_span in content_div.find_all('span', class_='file_attach'):
                attachment_span.decompose()
            
            # 본문 텍스트 추출
            text = content_div.get_text(strip=True)
            if text and len(text) > 20:
                content_parts.append(text)
        
        # 방법 2: article 태그 내부 찾기
        if not content_parts:
            article = soup.find('article')
            if article:
                content_div = article.find('div', class_='cont_w')
                if content_div:
                    # 첨부파일 링크 제외
                    for attachment_span in content_div.find_all('span', class_='file_attach'):
                        attachment_span.decompose()
                    
                    text = content_div.get_text(strip=True)
                    if text and len(text) > 20:
                        content_parts.append(text)
        
        # 방법 3: 단락별 추출
        if not content_parts:
            paragraphs = soup.find_all('p')
            for p in paragraphs:
                text = p.get_text(strip=True)
                if text and len(text) > 20:
                    content_parts.append(text)
        
        # 방법 4: 마지막 수단 - 제목 추출
        if not content_parts:
            title_div = soup.find('div', class_='t')
            if title_div:
                title_text = title_div.get_text(strip=True)
                if title_text:
                    content_parts.append(f"제목: {title_text}")
        
        # 최종 본문 구성
        if content_parts:
            return "\n\n".join(content_parts)
        else:
            return "본문 내용을 추출할 수 없습니다."
    
    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """첨부파일 추출"""
        attachments = []
        
        # 방법 1: 첨부파일 섹션에서 추출
        attachment_spans = soup.find_all('span', class_='file_attach')
        logger.debug(f"방법 1: span.file_attach 찾음 - {len(attachment_spans)}개")
        for span in attachment_spans:
            links = span.find_all('a')
            logger.debug(f"span 내부 링크 {len(links)}개 발견")
            for link in links:
                href = link.get('href', '')
                filename = link.get_text(strip=True)
                
                if href and filename and '/download.do' in href:
                    # 절대 URL 생성
                    download_url = urljoin(self.base_url, href)
                    
                    # 파일 확장자 추출
                    file_ext = filename.split('.')[-1].upper() if '.' in filename else 'UNKNOWN'
                    
                    attachments.append({
                        'filename': filename,
                        'url': download_url,
                        'size': '',
                        'type': file_ext
                    })
                    logger.debug(f"첨부파일 추출 성공: {filename} - {download_url}")
        
        # 방법 2: 다운로드 링크 직접 찾기
        if not attachments:
            download_links = soup.find_all('a', href=re.compile(r'/download\.do'))
            logger.debug(f"방법 2: /download.do 링크 {len(download_links)}개 발견")
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
                    logger.debug(f"첨부파일 추출 성공: {filename} - {download_url}")
        
        # 방법 3: attachId 패턴 찾기
        if not attachments:
            attach_links = soup.find_all('a', href=re.compile(r'attachId=\d+'))
            logger.debug(f"방법 3: attachId 패턴 {len(attach_links)}개 발견")
            for link in attach_links:
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
                    logger.debug(f"첨부파일 추출 성공: {filename} - {download_url}")
        
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
            logging.FileHandler('guroartsvalley_scraper.log', encoding='utf-8')
        ]
    )
    
    logger.info("="*60)
    logger.info("🚀 GuroArtsValley.or.kr(구로문화재단) 재단소식 스크래퍼 시작")
    logger.info("="*60)
    
    # 출력 디렉토리 설정
    output_dir = "output/guroartsvalley"
    
    # 기존 출력 디렉토리 정리 (파일만 삭제, 디렉토리 구조 유지)
    if os.path.exists(output_dir):
        import shutil
        logger.info(f"기존 출력 디렉토리 정리: {output_dir}")
        shutil.rmtree(output_dir)
    
    # 스크래퍼 초기화
    scraper = EnhancedGuroArtsValleyScraper()
    
    try:
        # 3페이지 수집 실행
        success = scraper.scrape_pages(max_pages=3, output_base="output/guroartsvalley")
        
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