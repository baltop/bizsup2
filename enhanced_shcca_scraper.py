# -*- coding: utf-8 -*-
"""
시흥시기업인협회 공지사항 스크래퍼
Enhanced 버전 - 공지 포함 완전 수집
"""

from enhanced_base_scraper import StandardTableScraper
from bs4 import BeautifulSoup
from urllib.parse import urljoin, parse_qs
import re
import logging

logger = logging.getLogger(__name__)

class EnhancedShccaScraper(StandardTableScraper):
    """시흥시기업인협회 공지사항 스크래퍼 - Enhanced 버전"""
    
    def __init__(self):
        super().__init__()
        
        # 사이트별 설정
        self.base_url = "https://www.shcca.com"
        self.list_url = "https://www.shcca.com/notice"
        self.site_name = "시흥시기업인협회"
        
        # 기본 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1
        
        # 상공회의소 계열 특성
        self.supports_notice_image = True
        
    def get_list_url(self, page_num: int) -> str:
        """페이지별 목록 URL 생성"""
        if page_num == 1:
            return self.list_url
        return f"{self.base_url}/_NBoard/board.php?bo_table=notice&page={page_num}"
    
    def _process_notice_detection(self, cell, row_index=0):
        """공지 이미지 감지 및 번호 처리 - 모든 CCI에서 재사용 가능"""
        number = cell.get_text(strip=True)
        is_notice = False
        
        # 이미지 찾기 (BeautifulSoup)
        notice_imgs = cell.find_all('img')
        for img in notice_imgs:
            src = img.get('src', '')
            alt = img.get('alt', '')
            if '공지' in src or '공지' in alt or 'notice' in src.lower():
                is_notice = True
                break
        
        # "공지" 텍스트로도 확인
        if "공지" in number:
            is_notice = True
            
        # "text-crimson" 클래스 확인 (이 사이트 특성)
        if cell.find('span', class_='text-crimson'):
            is_notice = True
        
        # 번호 결정
        if is_notice:
            return "공지"
        elif not number:
            return f"row_{row_index}"
        else:
            return number
    
    def parse_list_page(self, html_content: str) -> list:
        """목록 페이지 파싱"""
        announcements = []
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 디버깅을 위해 HTML 저장
        with open('debug_shcca.html', 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info("HTML이 debug_shcca.html에 저장되었습니다")
        
        # list_body 내의 li 요소들 찾기
        list_body = soup.find('ul', class_='list_body')
        if not list_body:
            logger.warning("list_body를 찾을 수 없습니다")
            return announcements
        
        rows = list_body.find_all('li', class_='bl-list')
        logger.info(f"찾은 행 수: {len(rows)}")
        
        # 첫 번째 행의 HTML 구조 출력
        if rows:
            logger.info(f"첫 번째 행 HTML: {str(rows[0])[:500]}")
        
        for i, row in enumerate(rows):
            try:
                # 번호 찾기 - bl-item bl-num 클래스
                number_cell = row.find('div', class_='bl-num')
                if number_cell:
                    number = self._process_notice_detection(number_cell, i)
                else:
                    number = f"row_{i}"
                
                # 제목 찾기 - bl-subj 클래스
                title_cell = row.find('div', class_='bl-subj')
                if not title_cell:
                    logger.warning(f"행 {i}: bl-subj 셀을 찾을 수 없음")
                    continue
                
                link_elem = title_cell.find('a')
                if not link_elem:
                    logger.warning(f"행 {i}: 링크 요소를 찾을 수 없음")
                    continue
                
                title = link_elem.get_text(strip=True)
                href = link_elem.get('href', '')
                
                if not href or not title:
                    logger.warning(f"행 {i}: 제목 또는 href가 비어있음")
                    continue
                
                # URL 정리
                detail_url = urljoin(self.base_url, href)
                
                # 작성자 찾기 - bl-author 클래스 또는 모바일 정보에서
                author = ""
                author_cell = row.find('div', class_='bl-author')
                if author_cell:
                    author_span = author_cell.find('span', class_='bl-name-in')
                    if author_span:
                        author = author_span.get_text(strip=True)
                else:
                    # 모바일 정보에서 찾기
                    mobile_info = title_cell.find('div', class_='m_list_info')
                    if mobile_info:
                        author_spans = mobile_info.find_all('span', class_='text-gray')
                        if author_spans:
                            author = author_spans[0].get_text(strip=True)
                
                # 날짜와 조회수 찾기 - bl-item 클래스들에서
                date = ""
                views = ""
                bl_items = row.find_all('div', class_='bl-item')
                
                # 숨겨지지 않은 bl-item들에서 날짜와 조회수 추출
                for item in bl_items:
                    if 'hidden-xs' not in item.get('class', []):
                        continue
                    text = item.get_text(strip=True)
                    # 날짜 형식 (YYYY.MM.DD)
                    if re.match(r'\d{4}\.\d{2}\.\d{2}', text):
                        date = text
                    # 숫자만 있으면 조회수
                    elif text.replace(',', '').isdigit():
                        views = text
                
                announcement = {
                    'number': number,
                    'title': title,
                    'url': detail_url,
                    'author': author,
                    'date': date,
                    'views': views,
                    'attachments': []
                }
                
                announcements.append(announcement)
                logger.info(f"공고 추가: [{number}] {title}")
                
            except Exception as e:
                logger.error(f"행 파싱 중 오류: {e}")
                continue
        
        return announcements
    
    def parse_detail_page(self, html_content: str) -> dict:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목
        title_elem = soup.find('h4', class_='view_title')
        title = title_elem.get_text(strip=True) if title_elem else "제목 없음"
        
        # 본문 - view_content 클래스 찾기
        content_elem = soup.find('div', class_='board-view-con')
        if not content_elem:
            content_elem = soup.find('div', id='board_view_con')
        
        content_html = ""
        if content_elem:
            content_html = str(content_elem)
            
            # 이미지 URL 절대 경로로 변환
            img_tags = content_elem.find_all('img')
            for img in img_tags:
                if img.get('src'):
                    img['src'] = urljoin(self.base_url, img['src'])
        
        # HTML을 마크다운으로 변환
        content_markdown = self.h.handle(content_html) if content_html else "내용 없음"
        
        # 첨부파일 찾기
        attachments = self._extract_attachments(soup)
        
        return {
            'title': title,
            'content': content_markdown,
            'attachments': attachments
        }
    
    def _extract_attachments(self, soup: BeautifulSoup) -> list:
        """첨부파일 추출"""
        attachments = []
        
        # view_file 클래스 내의 다운로드 링크 찾기
        file_section = soup.find('div', class_='view_file')
        if not file_section:
            return attachments
        
        download_links = file_section.find_all('a', class_='view_download')
        
        for link in download_links:
            try:
                href = link.get('href', '')
                if not href:
                    continue
                
                # 파일명 추출
                filename = link.get_text(strip=True)
                # 파일 크기 제거
                if '(' in filename and ')' in filename:
                    # "파일명.hwp (96.5K) DOWNLOAD" -> "파일명.hwp"
                    filename = filename.split('(')[0].strip()
                    filename = filename.replace('DOWNLOAD', '').strip()
                
                if filename:
                    file_url = urljoin(self.base_url, href)
                    
                    attachment = {
                        'filename': filename,
                        'url': file_url,
                        'size': ''
                    }
                    
                    # 파일 크기 추출 시도
                    size_match = re.search(r'\(([^)]+)\)', link.get_text())
                    if size_match:
                        attachment['size'] = size_match.group(1)
                    
                    attachments.append(attachment)
                    logger.info(f"첨부파일 발견: {filename}")
                    
            except Exception as e:
                logger.error(f"첨부파일 추출 중 오류: {e}")
                continue
        
        return attachments

if __name__ == "__main__":
    # 테스트 실행
    import os
    import logging
    
    # 로깅 설정
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    scraper = EnhancedShccaScraper()
    output_dir = "output/shcca"
    os.makedirs(output_dir, exist_ok=True)
    
    print("시흥시기업인협회 스크래퍼 테스트 시작...")
    scraper.scrape_pages(max_pages=3, output_base=output_dir)
    print("테스트 완료!")