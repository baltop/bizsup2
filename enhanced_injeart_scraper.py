# -*- coding: utf-8 -*-
"""
인제군문화재단 공지사항 스크래퍼
URL: http://www.injeart.or.kr/?p=19&page=1
"""

import os
import time
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from enhanced_base_scraper import EnhancedBaseScraper
from typing import List, Dict, Any
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('injeart_scraper.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class EnhancedInjeartScraper(EnhancedBaseScraper):
    """인제군문화재단 공지사항 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "http://www.injeart.or.kr"
        self.list_url = "http://www.injeart.or.kr/?p=19&page=1"
        self.site_code = "injeart"
        
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
        return f"{self.base_url}/?p=19&page={page_num}"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지에서 공고 목록 추출"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 공고 목록이 담긴 테이블 찾기 - injeart 사이트 구조에 맞게 수정
        table = soup.find('table')  # 첫 번째 테이블이 목록 테이블
        if not table:
            # 다른 방법으로 테이블 찾기
            tables = soup.find_all('table')
            for t in tables:
                if t.find('th', string=lambda text: text and '제목' in text):
                    table = t
                    break
        
        if not table:
            logger.warning("공고 목록 테이블을 찾을 수 없습니다")
            return announcements
        
        # 테이블의 행들 찾기 (헤더 제외)
        rows = table.select('tbody tr') or table.select('tr')[1:]
        
        if not rows:
            logger.warning("테이블에 데이터 행이 없습니다")
            return announcements
        
        logger.info(f"총 {len(rows)}개의 행 발견")
        
        for i, row in enumerate(rows):
            try:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 3:
                    logger.debug(f"행 {i}: 셀 수가 부족합니다 ({len(cells)}개)")
                    continue
                
                # 제목과 링크 찾기 - 여러 방법 시도
                title_link = None
                title = ""
                
                # 방법 1: a 태그가 있는 셀 찾기
                for cell in cells:
                    link = cell.find('a', href=True)
                    if link and link.get_text(strip=True):
                        title_link = link
                        title = link.get_text(strip=True)
                        break
                
                if not title_link:
                    logger.debug(f"행 {i}: 제목 링크를 찾을 수 없습니다")
                    continue
                
                # URL 구성
                href = title_link.get('href', '')
                if not href or href.startswith('#'):
                    logger.debug(f"행 {i}: 유효하지 않은 href ({href})")
                    continue
                
                detail_url = urljoin(self.base_url, href)
                
                # 기본 공고 정보
                announcement = {
                    'title': title.strip(),
                    'url': detail_url
                }
                
                # 추가 정보 추출 (번호, 분류, 작성일, 조회수)
                try:
                    # 번호 (첫번째 셀)
                    if cells[0]:
                        number = cells[0].get_text(strip=True)
                        if number and not number.lower() in ['번호', 'no']:
                            announcement['number'] = number
                    
                    # 분류 (두번째 셀, 있다면)
                    if len(cells) >= 4 and cells[1]:
                        category = cells[1].get_text(strip=True)
                        if category and not category.lower() in ['분류', 'category']:
                            announcement['category'] = category
                    
                    # 작성일 (끝에서 두번째 셀)
                    if len(cells) >= 4:
                        date_text = cells[-2].get_text(strip=True)
                        if date_text and not date_text.lower() in ['등록일', '작성일', 'date']:
                            announcement['date'] = date_text
                    
                    # 조회수 (마지막 셀)
                    views_text = cells[-1].get_text(strip=True)
                    if views_text and views_text.isdigit():
                        announcement['views'] = views_text
                        
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
        
        # 방법 1: 공지사항 상세보기 테이블에서 내용 찾기
        detail_table = soup.find('table', string=lambda text: text and '공지사항 상세보기' in text)
        if not detail_table:
            detail_table = soup.select_one('table[summary*="상세보기"]')
        
        if detail_table:
            # 본문이 담긴 셀 찾기 (가장 긴 텍스트가 있는 셀)
            cells = detail_table.find_all('td')
            max_content = ""
            for cell in cells:
                cell_text = cell.get_text(strip=True)
                if len(cell_text) > len(max_content) and len(cell_text) > 50:
                    max_content = cell_text
                    content_area = cell
        
        if not content_area:
            # 방법 2: 일반적인 본문 영역 찾기
            selectors = [
                '.content', '.board_view', '.view_content',
                '#content', '#board_content', '#view_content'
            ]
            
            for selector in selectors:
                content_area = soup.select_one(selector)
                if content_area:
                    break
        
        if content_area:
            # HTML을 마크다운으로 변환
            content = self.h.handle(str(content_area)).strip()
        else:
            # 방법 3: 제목 다음의 긴 텍스트 찾기
            all_text = soup.get_text()
            if len(all_text) > 100:
                content = all_text[:1000] + "..."
                
        # 첨부파일 추출
        attachments = []
        
        # 방법 1: "첨부파일" 라벨이 있는 행에서 찾기 - 인제 사이트 특화
        attach_cells = soup.find_all(['th', 'td'], string=lambda text: text and '첨부파일' in text)
        for cell in attach_cells:
            parent_row = cell.find_parent('tr')
            if parent_row:
                file_links = parent_row.find_all('a')
                for link in file_links:
                    onclick = link.get('onclick', '')
                    filename = link.get_text(strip=True)
                    
                    # chkDownAuth('id') 패턴 파싱
                    if onclick and 'chkDownAuth(' in onclick:
                        import re
                        match = re.search(r"chkDownAuth\('([^']+)'\)", onclick)
                        if match and filename:
                            file_id = match.group(1)
                            download_url = f"{self.base_url}/inc/down.php?fileidx={file_id}"
                            attachments.append({
                                'filename': filename,
                                'url': download_url
                            })
                            logger.debug(f"첨부파일 발견: {filename} -> {download_url}")
        
        # 방법 2: 다운로드 링크 패턴으로 찾기
        if not attachments:
            download_links = soup.find_all('a', href=lambda href: href and ('download' in href.lower() or 'file' in href.lower()))
            for link in download_links:
                href = link.get('href', '')
                filename = link.get_text(strip=True)
                if filename and href:
                    attachments.append({
                        'filename': filename,
                        'url': urljoin(self.base_url, href)
                    })
        
        # 방법 3: PDF, HWP, DOC 등 파일 확장자로 끝나는 링크 찾기
        if not attachments:
            file_extensions = ['.pdf', '.hwp', '.doc', '.docx', '.xls', '.xlsx', '.zip', '.jpg', '.png']
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                if any(ext in href.lower() for ext in file_extensions) or any(ext in text.lower() for ext in file_extensions):
                    filename = text if text else os.path.basename(href)
                    if filename:
                        attachments.append({
                            'filename': filename,
                            'url': urljoin(self.base_url, href)
                        })
        
        logger.info(f"본문 길이: {len(content)}, 첨부파일: {len(attachments)}개")
        
        return {
            'content': content,
            'attachments': attachments
        }
    
    def download_file(self, url: str, save_path: str, attachment_info: Dict[str, Any] = None) -> bool:
        """파일 다운로드 - 인제 사이트 특화"""
        # 특수 URL 패턴 처리
        if '#url' in url:
            logger.warning(f"잘못된 다운로드 URL: {url}")
            return False
        
        # 기본 다운로드 메서드 호출
        success = super().download_file(url, save_path, attachment_info)
        
        if success:
            # 파일 크기 검증 (HTML 페이지가 다운로드된 경우 감지)
            if os.path.exists(save_path):
                file_size = os.path.getsize(save_path)
                if file_size < 1024:  # 1KB 미만
                    # 파일 내용이 HTML인지 확인
                    with open(save_path, 'rb') as f:
                        content = f.read(500).decode('utf-8', errors='ignore')
                        if '<html' in content.lower() or '<!doctype' in content.lower():
                            logger.warning(f"HTML 페이지가 다운로드됨. 파일 삭제: {save_path}")
                            os.remove(save_path)
                            return False
        
        return success
    

def main():
    """메인 실행 함수"""
    scraper = EnhancedInjeartScraper()
    
    # output/injeart 디렉토리 설정
    output_dir = os.path.join('output', scraper.site_code)
    
    logger.info("="*60)
    logger.info("🏛️ 인제군문화재단 공지사항 스크래퍼 시작")
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