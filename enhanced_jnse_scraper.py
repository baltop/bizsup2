# -*- coding: utf-8 -*-
"""
전남사회적경제통합지원센터 센터공지 스크래퍼
URL: http://www.jn-se.kr/bbs/board.php?bo_table=nco4_1
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
        logging.FileHandler('jnse_scraper.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class EnhancedJnseScraper(EnhancedBaseScraper):
    """전남사회적경제통합지원센터 센터공지 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "http://www.jn-se.kr"
        self.list_url = "http://www.jn-se.kr/bbs/board.php?bo_table=nco4_1"
        self.site_code = "jnse"
        
        # 헤더 설정
        self.headers.update({
            'Referer': self.base_url,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        self.session.headers.update(self.headers)
        
        # 사이트별 설정
        self.verify_ssl = False
        self.timeout = 30
        self.delay_between_requests = 1
        
    def get_list_url(self, page_num):
        """페이지 번호에 따른 목록 URL 반환"""
        return f"{self.base_url}/bbs/board.php?bo_table=nco4_1&page={page_num}"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지에서 공고 목록 추출"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 게시글 목록 찾기 - ul.board_list_ul 내의 li 요소들
        board_list = soup.find('ul', class_='board_list_ul')
        if not board_list:
            logger.warning("게시글 목록을 찾을 수 없습니다")
            return announcements
        
        # 헤더 제외한 게시글 li들 찾기
        list_items = board_list.find_all('li')
        if not list_items:
            logger.warning("게시글 항목이 없습니다")
            return announcements
        
        logger.info(f"총 {len(list_items)}개의 목록 항목 발견")
        
        for i, item in enumerate(list_items):
            try:
                # 헤더 행 건너뛰기
                if item.get('class') and 'bo_head' in item.get('class'):
                    logger.debug(f"항목 {i}: 헤더 행 건너뛰기")
                    continue
                
                # 제목 링크 찾기
                title_link = item.find('a', class_='bo_subjecta')
                if not title_link:
                    logger.debug(f"항목 {i}: 제목 링크를 찾을 수 없습니다")
                    continue
                
                # 제목과 URL 추출
                title = title_link.get_text(strip=True)
                href = title_link.get('href', '')
                
                if not title or not href:
                    logger.debug(f"항목 {i}: 제목 또는 링크가 비어있습니다")
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
                    if 'wr_id' in query_params:
                        announcement['number'] = query_params['wr_id'][0]
                    
                    # 분류 정보 (있다면)
                    category_elem = item.find('div', string=lambda x: x and any(word in x for word in ['알림', '사업공고', '기타']))
                    if category_elem:
                        announcement['category'] = category_elem.get_text(strip=True)
                    
                    # 작성일과 조회수 (div 요소들에서)
                    divs = item.find_all('div')
                    for div in divs:
                        text = div.get_text(strip=True)
                        # 날짜 형식 (YYYY.MM.DD 또는 MM-DD)
                        if re.match(r'\d{4}\.\d{2}\.\d{2}|\d{2}-\d{2}', text):
                            announcement['date'] = text
                        # 조회수 (숫자만)
                        elif text.isdigit() and int(text) > 0:
                            announcement['views'] = text
                    
                except Exception as e:
                    logger.debug(f"항목 {i} 추가 정보 추출 중 오류: {e}")
                
                announcements.append(announcement)
                logger.debug(f"공고 추가: {title[:50]}...")
                
            except Exception as e:
                logger.error(f"항목 {i} 파싱 중 오류: {e}")
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
            '#bo_v_con',           # 일반적인 게시판 본문 ID
            '.bo_v_con',           # 게시판 본문 클래스
            '[id*="bo_v"]',        # bo_v로 시작하는 ID
            '.view_content',       # 뷰 컨텐츠 클래스
            '#view_content',       # 뷰 컨텐츠 ID
            'article',             # article 태그
            '.content'             # 일반적인 content 클래스
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
            # 방법 2: 긴 텍스트 영역 찾기
            all_divs = soup.find_all('div')
            max_content = ""
            for div in all_divs:
                div_text = div.get_text(strip=True)
                if len(div_text) > len(max_content) and len(div_text) > 100:
                    max_content = div_text
                    content_area = div
            
            if max_content:
                content = max_content[:2000]  # 너무 길면 자르기
        
        # 첨부파일 추출
        attachments = []
        
        # 방법 1: 일반적인 첨부파일 링크 패턴
        file_patterns = [
            'a[href*="/bbs/download.php"]',      # 다운로드 스크립트
            'a[href*="download"]',               # 다운로드 포함 링크
            'a[href*="/data/"]',                 # 데이터 폴더 링크
            'a[href*="/files/"]',                # 파일 폴더 링크
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
            attach_keywords = ['첨부', '다운로드', '파일', '자료']
            for keyword in attach_keywords:
                attach_elements = soup.find_all(string=lambda text: text and keyword in text)
                for elem in attach_elements:
                    parent = elem.parent if elem.parent else elem
                    nearby_links = parent.find_all('a', href=True) if hasattr(parent, 'find_all') else []
                    
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
    scraper = EnhancedJnseScraper()
    
    # output/jnse 디렉토리 설정
    output_dir = os.path.join('output', scraper.site_code)
    
    logger.info("="*60)
    logger.info("🏢 전남사회적경제통합지원센터 센터공지 스크래퍼 시작")
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