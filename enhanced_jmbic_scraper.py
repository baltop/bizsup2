# -*- coding: utf-8 -*-
"""
JMBIC (전남바이오진흥원 해양바이오연구센터) 스크래퍼 - 향상된 버전
URL: http://www.jmbic.or.kr/bbs/board.php?code=open_08&bo_table=open_08
"""

from enhanced_base_scraper import StandardTableScraper
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import logging
import re

logger = logging.getLogger(__name__)

class EnhancedJmbicScraper(StandardTableScraper):
    """JMBIC 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        # 기본 설정
        self.base_url = "http://www.jmbic.or.kr"
        self.list_url = "http://www.jmbic.or.kr/bbs/board.php?code=open_08&bo_table=open_08"
        
        # 사이트별 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 2
        self.delay_between_pages = 3
        
        # User-Agent 설정 (한국 사이트 호환성)
        self.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        self.session.headers.update(self.headers)
        
    def get_list_url(self, page_num: int) -> str:
        """페이지별 URL 생성"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}&page={page_num}"
    
    def parse_list_page(self, html_content: str) -> list:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 게시판 테이블 찾기
        table = soup.find('table')
        if not table:
            logger.warning("게시판 테이블을 찾을 수 없습니다")
            return announcements
        
        tbody = table.find('tbody')
        if not tbody:
            # tbody가 없는 경우 테이블에서 직접 tr 찾기
            tbody = table
        
        rows = tbody.find_all('tr')
        logger.info(f"찾은 행 수: {len(rows)}")
        
        for i, row in enumerate(rows):
            try:
                cells = row.find_all('td')
                if len(cells) < 5:  # 번호, 제목, 글쓴이, 날짜, 조회수
                    continue
                
                # 번호 (첫 번째 셀)
                number_cell = cells[0]
                number = number_cell.get_text(strip=True)
                
                # 제목 및 링크 (두 번째 셀)
                title_cell = cells[1]
                link_elem = title_cell.find('a', href=True)
                
                if not link_elem:
                    continue
                
                title = link_elem.get_text(strip=True)
                if not title:
                    continue
                
                # URL 구성
                href = link_elem.get('href', '')
                if href.startswith('http'):
                    detail_url = href
                else:
                    detail_url = urljoin(self.base_url, href)
                
                # 작성자 (세 번째 셀)
                writer_cell = cells[2]
                writer = writer_cell.get_text(strip=True)
                
                # 날짜 (네 번째 셀)
                date_cell = cells[3]
                date = date_cell.get_text(strip=True)
                
                # 조회수 (다섯 번째 셀)
                views_cell = cells[4]
                views = views_cell.get_text(strip=True)
                
                # 첨부파일 확인
                has_attachment = title_cell.find('img', alt=re.compile(r'첨부|file', re.I)) is not None
                
                announcement = {
                    'title': title,
                    'url': detail_url,
                    'writer': writer,
                    'date': date,
                    'views': views,
                    'number': number,
                    'has_attachment': has_attachment
                }
                
                announcements.append(announcement)
                logger.debug(f"공고 추가: [{number}] {title}")
                
            except Exception as e:
                logger.error(f"행 {i} 파싱 중 오류: {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개 공고를 파싱했습니다")
        return announcements
    
    def parse_detail_page(self, html_content: str) -> dict:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 본문 내용 추출
        content_elem = soup.find('div', id='bo_v_con')
        if not content_elem:
            # 다른 선택자 시도
            content_elem = soup.find('div', class_='view_content') or soup.find('div', class_='content')
        
        content = ""
        if content_elem:
            # HTML을 마크다운으로 변환
            content = self.h.handle(str(content_elem))
            # 불필요한 공백 정리
            content = re.sub(r'\n\n+', '\n\n', content.strip())
        else:
            logger.warning("본문 내용을 찾을 수 없습니다")
            content = "본문 내용을 추출할 수 없습니다."
        
        # 첨부파일 추출
        attachments = self._extract_attachments(soup)
        
        return {
            'content': content,
            'attachments': attachments
        }
    
    def _extract_attachments(self, soup: BeautifulSoup) -> list:
        """첨부파일 추출"""
        attachments = []
        
        # 첨부파일 섹션 찾기
        file_section = soup.find('section', id='bo_v_file')
        if not file_section:
            logger.info("첨부파일 섹션을 찾을 수 없습니다")
            return attachments
        
        # 첨부파일 링크들 찾기
        file_links = file_section.find_all('a', class_='view_file_download')
        
        for i, link in enumerate(file_links):
            try:
                href = link.get('href', '')
                if not href:
                    continue
                
                # 파일 URL 구성
                if href.startswith('http'):
                    file_url = href
                else:
                    file_url = urljoin(self.base_url, href)
                
                # 파일명 추출
                filename_elem = link.find('strong')
                if filename_elem:
                    filename = filename_elem.get_text(strip=True)
                else:
                    filename = f"attachment_{i+1}.bin"
                
                # 파일 크기 추출 (선택적)
                size_text = link.get_text()
                size_match = re.search(r'\(([\d.]+[KMG]?B?)\)', size_text)
                file_size = size_match.group(1) if size_match else "Unknown"
                
                attachment = {
                    'url': file_url,
                    'filename': filename,
                    'size': file_size
                }
                
                attachments.append(attachment)
                logger.info(f"첨부파일 발견: {filename} ({file_size})")
                
            except Exception as e:
                logger.error(f"첨부파일 {i} 처리 중 오류: {e}")
                continue
        
        logger.info(f"총 {len(attachments)}개 첨부파일을 추출했습니다")
        return attachments


def test_jmbic_scraper(pages=3):
    """JMBIC 스크래퍼 테스트"""
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('jmbic_scraper.log', encoding='utf-8')
        ]
    )
    
    scraper = EnhancedJmbicScraper()
    output_dir = "output/jmbic"
    
    logger.info(f"JMBIC 스크래퍼 테스트 시작 - {pages}페이지")
    
    try:
        scraper.scrape_pages(max_pages=pages, output_base=output_dir)
        logger.info("JMBIC 스크래퍼 테스트 완료")
        return True
    except Exception as e:
        logger.error(f"스크래퍼 테스트 실패: {e}")
        return False


if __name__ == "__main__":
    test_jmbic_scraper(3)