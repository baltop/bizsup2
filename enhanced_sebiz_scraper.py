# -*- coding: utf-8 -*-
"""
지역과소셜비즈 공지사항 스크래퍼
URL: https://www.sebiz.or.kr/sub/board.html?bid=k1news
"""

import os
import time
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from enhanced_base_scraper import EnhancedBaseScraper
from typing import List, Dict, Any
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('sebiz_scraper.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class EnhancedSebizScraper(EnhancedBaseScraper):
    """지역과소셜비즈 공지사항 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.sebiz.or.kr"
        self.list_url = "https://www.sebiz.or.kr/sub/board.html?bid=k1news"
        self.site_code = "sebiz"
        
        # 헤더 설정
        self.headers.update({
            'Referer': self.base_url,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        self.session.headers.update(self.headers)
        
        # 사이트별 설정
        self.verify_ssl = True
        self.timeout = 30
        self.delay_between_requests = 1
        
    def get_list_url(self, page_num):
        """페이지 번호에 따른 목록 URL 반환"""
        return f"{self.base_url}/sub/board.html?gotoPage={page_num}&bid=k1news&sflag=&sword=&syear=&bcate=&snm=296"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지에서 공고 목록 추출"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 게시판 테이블 찾기
        board_table = soup.find('table', class_='boardtable')
        if not board_table:
            logger.warning("게시판 테이블을 찾을 수 없습니다")
            return announcements
        
        # 테이블 행들 찾기 (첫 번째 행은 헤더이므로 제외)
        rows = board_table.find_all('tr')[1:]  # 첫 번째 tr은 헤더
        
        if not rows:
            logger.warning("테이블에 데이터 행이 없습니다")
            return announcements
        
        logger.info(f"총 {len(rows)}개의 행 발견")
        
        for i, row in enumerate(rows):
            try:
                cells = row.find_all('td')
                if len(cells) < 4:
                    logger.debug(f"행 {i}: 셀 수가 부족합니다 ({len(cells)}개)")
                    continue
                
                # 제목 셀에서 링크와 제목 추출
                subj_cell = None
                for cell in cells:
                    if 'subj' in cell.get('class', []):
                        subj_cell = cell
                        break
                
                if not subj_cell:
                    logger.debug(f"행 {i}: 제목 셀을 찾을 수 없습니다")
                    continue
                
                # 제목 링크 찾기
                title_link = subj_cell.find('a')
                if not title_link:
                    logger.debug(f"행 {i}: 제목 링크를 찾을 수 없습니다")
                    continue
                
                # 제목과 URL 추출
                title = title_link.get_text(strip=True)
                href = title_link.get('href', '')
                
                if not title or not href:
                    logger.debug(f"행 {i}: 제목 또는 링크가 비어있습니다")
                    continue
                
                # 상대 URL을 절대 URL로 변환
                detail_url = urljoin(self.base_url, href)
                
                # 기본 공고 정보
                announcement = {
                    'title': title.strip(),
                    'url': detail_url
                }
                
                # 추가 정보 추출 시도
                try:
                    # 게시글 번호 추출 (URL에서)
                    parsed_url = urlparse(href)
                    query_params = parse_qs(parsed_url.query)
                    if 'bno' in query_params:
                        announcement['number'] = query_params['bno'][0]
                    
                    # 분류 정보 (span.cate_code로)
                    category_span = subj_cell.find('span', class_=lambda x: x and 'cate_code' in x)
                    if category_span:
                        announcement['category'] = category_span.get_text(strip=True)
                    
                    # 기간/상태 정보
                    period_cell = None
                    for cell in cells:
                        if 'period' in cell.get('class', []):
                            period_cell = cell
                            break
                    
                    if period_cell:
                        period_text = period_cell.get_text(strip=True)
                        announcement['period'] = period_text
                        
                        # 상태 정보 추출
                        status_elem = period_cell.find('b', class_=lambda x: x and 'whether' in x)
                        if status_elem:
                            announcement['status'] = status_elem.get_text(strip=True)
                    
                    # 작성일과 조회수 추출
                    data_cells = [cell for cell in cells if 'data' in cell.get('class', [])]
                    for cell in data_cells:
                        cell_text = cell.get_text(strip=True)
                        # 날짜 형식 (YYYY-MM-DD)
                        if re.match(r'\d{4}-\d{2}-\d{2}', cell_text):
                            announcement['date'] = cell_text
                        # 조회수 (숫자만)
                        elif cell_text.isdigit():
                            announcement['views'] = cell_text
                    
                except Exception as e:
                    logger.debug(f"행 {i} 추가 정보 추출 중 오류: {e}")
                
                announcements.append(announcement)
                logger.debug(f"공고 추가: {title[:50]}...")
                
            except Exception as e:
                logger.error(f"행 {i} 파싱 중 오류: {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개 공고 추출 완료")
        return announcements
    
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지에서 내용과 첨부파일 추출"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 본문 내용 추출
        content = ""
        content_area = None
        
        # 방법 1: 게시글 본문 영역 찾기
        selectors = [
            '.view-content',       # 일반적인 뷰 컨텐츠 클래스
            '.board-content',      # 게시판 컨텐츠 클래스
            '#view_content',       # 뷰 컨텐츠 ID
            '.content',            # 일반적인 content 클래스
            '[class*="content"]',  # content가 포함된 클래스
            'article',             # article 태그
            '.view',               # view 클래스
            '.detail'              # detail 클래스
        ]
        
        for selector in selectors:
            content_area = soup.select_one(selector)
            if content_area:
                logger.debug(f"본문 영역 찾음: {selector}")
                break
        
        if content_area:
            # HTML을 마크다운으로 변환
            content = self.h.handle(str(content_area)).strip()
        else:
            # 방법 2: 테이블이나 div에서 긴 텍스트 영역 찾기
            all_divs = soup.find_all(['div', 'td'])
            max_content = ""
            for elem in all_divs:
                elem_text = elem.get_text(strip=True)
                if len(elem_text) > len(max_content) and len(elem_text) > 100:
                    max_content = elem_text
                    content_area = elem
            
            if max_content:
                content = max_content[:2000]  # 너무 길면 자르기
        
        # 첨부파일 추출
        attachments = []
        
        # 방법 1: 일반적인 첨부파일 링크 패턴
        file_patterns = [
            'a[href*="/download"]',           # 다운로드 포함 링크
            'a[href*="/file"]',               # 파일 포함 링크
            'a[href*="/attach"]',             # 첨부 포함 링크
            'a[href*="mode=down"]',           # 다운로드 모드
            'a[href*="filedown"]',            # 파일다운로드
        ]
        
        for pattern in file_patterns:
            links = soup.select(pattern)
            for link in links:
                href = link.get('href', '')
                filename = link.get_text(strip=True)
                if filename and href:
                    attachments.append({
                        'filename': filename,
                        'url': urljoin(self.base_url, href)
                    })
                    logger.debug(f"첨부파일 발견 (패턴): {filename}")
        
        # 방법 2: 파일 확장자로 끝나는 링크 찾기
        if not attachments:
            file_extensions = ['.pdf', '.hwp', '.doc', '.docx', '.xls', '.xlsx', '.zip', '.jpg', '.png', '.ppt', '.pptx']
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                # 파일 확장자 체크
                if any(ext in href.lower() for ext in file_extensions) or any(ext in text.lower() for ext in file_extensions):
                    filename = text if text else os.path.basename(href)
                    if filename:
                        attachments.append({
                            'filename': filename,
                            'url': urljoin(self.base_url, href)
                        })
                        logger.debug(f"첨부파일 발견 (확장자): {filename}")
        
        # 방법 3: "첨부" 관련 텍스트 주변에서 링크 찾기
        if not attachments:
            attach_keywords = ['첨부', '다운로드', '파일', '자료', '첨부파일']
            for keyword in attach_keywords:
                attach_elements = soup.find_all(string=lambda text: text and keyword in text)
                for elem in attach_elements:
                    parent = elem.parent if elem.parent else elem
                    if hasattr(parent, 'find_all'):
                        nearby_links = parent.find_all('a', href=True)
                        for link in nearby_links:
                            href = link.get('href', '')
                            filename = link.get_text(strip=True)
                            if filename and href and filename not in [att['filename'] for att in attachments]:
                                attachments.append({
                                    'filename': filename,
                                    'url': urljoin(self.base_url, href)
                                })
                                logger.debug(f"첨부파일 발견 (키워드): {filename}")
        
        logger.info(f"본문 길이: {len(content)}, 첨부파일: {len(attachments)}개")
        
        return {
            'content': content,
            'attachments': attachments
        }


def main():
    """메인 실행 함수"""
    scraper = EnhancedSebizScraper()
    
    # output/sebiz 디렉토리 설정
    output_dir = os.path.join('output', scraper.site_code)
    
    logger.info("="*60)
    logger.info("🏢 지역과소셜비즈 공지사항 스크래퍼 시작")
    logger.info(f"📂 저장 경로: {output_dir}")
    logger.info(f"🌐 대상 사이트: {scraper.base_url}")
    logger.info("="*60)
    
    try:
        # 3페이지까지 스크래핑 실행
        success = scraper.scrape_pages(max_pages=3, output_base=output_dir)
        
        if success:
            logger.info("✅ 스크래핑이 성공적으로 완료되었습니다!")
        else:
            logger.error("❌ 스크래핑 중 오류가 발생했습니다.")
            
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단되었습니다.")
    except Exception as e:
        logger.error(f"예상치 못한 오류: {e}")
        raise


if __name__ == "__main__":
    main()