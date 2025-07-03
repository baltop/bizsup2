# -*- coding: utf-8 -*-
"""
JIUC (전북산학융합원) 스크래퍼 - 향상된 버전
URL: http://www.jiuc.or.kr/main/menu?gc=605XOAS&sca=
"""

from enhanced_base_scraper import StandardTableScraper
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
import logging
import re

logger = logging.getLogger(__name__)

class EnhancedJiucScraper(StandardTableScraper):
    """JIUC 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        # 기본 설정
        self.base_url = "http://www.jiuc.or.kr"
        self.list_url = "http://www.jiuc.or.kr/main/menu?gc=605XOAS&sca="
        
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
        """페이지별 URL 생성 - JIUC 특화"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}&do=list&page={page_num}"
    
    def parse_list_page(self, html_content: str) -> list:
        """목록 페이지 파싱 - JIUC 커스텀 구조"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # JIUC 게시판 테이블 찾기
        table = soup.find('table', class_='gtable board_list')
        if not table:
            logger.warning("게시판 테이블을 찾을 수 없습니다")
            return announcements
        
        tbody = table.find('tbody')
        if not tbody:
            logger.warning("tbody를 찾을 수 없습니다")
            return announcements
        
        rows = tbody.find_all('tr')
        logger.info(f"찾은 행 수: {len(rows)}")
        
        for i, row in enumerate(rows):
            try:
                cells = row.find_all('td')
                if len(cells) < 7:  # 번호, 분류, 제목, 첨부, 작성자, 작성일, 조회
                    continue
                
                # 번호 (첫 번째 셀) - 공지 처리
                number_cell = cells[0]
                is_notice = 'notice' in row.get('class', [])
                
                if is_notice:
                    # 공지 아이콘 확인
                    notice_icon = number_cell.find('span', class_='icon_notice')
                    number = "공지" if notice_icon else f"notice_{i}"
                else:
                    number = number_cell.get_text(strip=True)
                
                # 분류 (두 번째 셀)
                category_cell = cells[1]
                category = category_cell.get_text(strip=True)
                
                # 제목 및 링크 (세 번째 셀)
                title_cell = cells[2]
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
                
                # 첨부파일 여부 (네 번째 셀)
                attachment_cell = cells[3]
                has_attachment = attachment_cell.find('i', class_='fas fa-paperclip') is not None
                
                # 작성자 (다섯 번째 셀)
                writer_cell = cells[4]
                writer = writer_cell.get_text(strip=True)
                
                # 작성일 (여섯 번째 셀)
                date_cell = cells[5]
                date = date_cell.get_text(strip=True)
                
                # 조회수 (일곱 번째 셀)
                views_cell = cells[6]
                views = views_cell.get_text(strip=True)
                
                announcement = {
                    'title': title,
                    'url': detail_url,
                    'category': category,
                    'writer': writer,
                    'date': date,
                    'views': views,
                    'number': number,
                    'has_attachment': has_attachment,
                    'is_notice': is_notice
                }
                
                announcements.append(announcement)
                logger.debug(f"공고 추가: [{number}] {category} - {title}")
                
            except Exception as e:
                logger.error(f"행 {i} 파싱 중 오류: {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개 공고를 파싱했습니다")
        return announcements
    
    def parse_detail_page(self, html_content: str) -> dict:
        """상세 페이지 파싱 - JIUC 특화"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 본문 내용 추출 - JIUC 구조
        content_elem = soup.find('div', class_='content_wrap')
        if not content_elem:
            logger.warning("본문 내용을 찾을 수 없습니다")
            content = "본문 내용을 추출할 수 없습니다."
        else:
            # HTML을 마크다운으로 변환
            content = self.h.handle(str(content_elem))
            # 불필요한 공백 정리
            content = re.sub(r'\n\n+', '\n\n', content.strip())
        
        # 첨부파일 추출
        attachments = self._extract_attachments(soup)
        
        return {
            'content': content,
            'attachments': attachments
        }
    
    def _extract_attachments(self, soup: BeautifulSoup) -> list:
        """첨부파일 추출 - JIUC 특화 구조"""
        attachments = []
        
        # JIUC 첨부파일 섹션 찾기
        file_section = soup.find('div', class_='file_wrap')
        if not file_section:
            logger.info("첨부파일 섹션을 찾을 수 없습니다")
            return attachments
        
        # 첨부파일 링크들 찾기 - JIUC 특화 구조
        file_links = file_section.find_all('div', class_='ahref_btns cursor')
        
        for i, link_div in enumerate(file_links):
            try:
                # data-href 속성에서 다운로드 URL 추출
                download_url = link_div.get('data-href', '')
                if not download_url:
                    continue
                
                # 파일 URL 구성
                if download_url.startswith('http'):
                    file_url = download_url
                else:
                    file_url = urljoin(self.base_url, download_url)
                
                # 파일명 추출
                filename_elem = link_div.find('span', class_='fname')
                if filename_elem:
                    filename = filename_elem.get_text(strip=True)
                else:
                    filename = f"attachment_{i+1}.bin"
                
                # 파일 크기 추출
                size_elem = link_div.find('span', class_='fsize')
                if size_elem:
                    size_text = size_elem.get_text(strip=True)
                    # 괄호와 KB 단위 제거하여 크기만 추출
                    size_match = re.search(r'\(([\d.]+)\s*([KMGT]?B?)\)', size_text)
                    file_size = size_match.group(0) if size_match else "Unknown"
                else:
                    file_size = "Unknown"
                
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


def test_jiuc_scraper(pages=3):
    """JIUC 스크래퍼 테스트"""
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('jiuc_scraper.log', encoding='utf-8')
        ]
    )
    
    scraper = EnhancedJiucScraper()
    output_dir = "output/jiuc"
    
    logger.info(f"JIUC 스크래퍼 테스트 시작 - {pages}페이지")
    
    try:
        scraper.scrape_pages(max_pages=pages, output_base=output_dir)
        logger.info("JIUC 스크래퍼 테스트 완료")
        return True
    except Exception as e:
        logger.error(f"스크래퍼 테스트 실패: {e}")
        return False


if __name__ == "__main__":
    test_jiuc_scraper(3)