# -*- coding: utf-8 -*-
"""
Jscci(전주상공회의소) 스크래퍼 - Enhanced 버전
"""

import re
import os
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from enhanced_base_scraper import StandardTableScraper
import logging

logger = logging.getLogger(__name__)

class EnhancedJscciScraper(StandardTableScraper):
    """전주상공회의소 공지사항 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://jscci.korcham.net"
        self.list_url = "https://jscci.korcham.net/front/board/boardContentsListPage.do?boardId=10673&menuId=1402"
        
        # Jscci 특화 설정 - 타임아웃 대기시간 증가
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 60  # 60초로 증가
        self.delay_between_requests = 3  # 3초로 증가
        
        # JavaScript 기반 상세 페이지 접근을 위한 기본 URL
        self.detail_base_url = "https://jscci.korcham.net/front/board/boardContentsView.do"
        
    def get_list_url(self, page_num: int) -> str:
        """페이지별 URL 생성 (JavaScript 기반 페이지네이션)"""
        if page_num == 1:
            return self.list_url
        else:
            # JavaScript go_Page() 함수 기반 페이지네이션 처리
            return f"{self.list_url}&page={page_num}"
    
    def parse_list_page(self, html_content: str) -> list:
        """목록 페이지 파싱 - JavaScript 렌더링된 내용도 고려"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 먼저 기본적인 테이블 구조 찾기
        table = soup.find('table')
        tbody = None
        
        if table:
            tbody = table.find('tbody')
            if tbody:
                rows = tbody.find_all('tr')
                logger.info(f"tbody에서 {len(rows)}개 행 발견")
            else:
                # tbody가 없으면 table에서 직접 tr 찾기
                rows = table.find_all('tr')
                logger.info(f"table에서 직접 {len(rows)}개 행 발견")
        else:
            # 테이블이 없으면 전체 문서에서 tr 찾기
            rows = soup.find_all('tr')
            logger.info(f"전체 문서에서 {len(rows)}개 행 발견")
        
        if not rows:
            logger.warning("행을 찾을 수 없습니다. JavaScript 렌더링이 필요할 수 있습니다.")
            # JavaScript 렌더링 필요 - Playwright 사용 필요
            return self._parse_with_playwright()
        
        # 헤더 행 제외하고 데이터 행만 처리
        data_rows = []
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:  # 번호, 제목 컬럼
                # th가 있는 헤더 행은 제외
                if not row.find('th'):
                    data_rows.append(row)
        
        logger.info(f"데이터 행 {len(data_rows)}개 처리")
        
        for row in data_rows:
            try:
                cells = row.find_all('td')
                if len(cells) < 2:
                    continue
                
                # 번호 (첫 번째 셀) - "공지" 이미지가 있을 수 있음
                number = cells[0].get_text(strip=True)
                
                # 제목 셀 (두 번째 셀)
                title_cell = cells[1]
                link_elem = title_cell.find('a')
                
                if not link_elem:
                    continue
                
                title = link_elem.get_text(strip=True)
                if not title:
                    continue
                
                # JavaScript onclick에서 contentsView ID 추출
                onclick = link_elem.get('onclick', '')
                content_id = None
                if onclick:
                    # javascript:contentsView('XXXXX') 형태에서 ID 추출
                    match = re.search(r"contentsView\('(\d+)'\)", onclick)
                    if match:
                        content_id = match.group(1)
                
                if not content_id:
                    logger.warning(f"컨텐츠 ID를 찾을 수 없습니다: {title}")
                    continue
                
                # 상세 페이지 URL 구성
                detail_url = f"{self.detail_base_url}?contentsId={content_id}"
                
                # 작성일은 전주CCI에서는 목록에 없을 수 있음 (상세페이지에서 확인)
                date = ""
                if len(cells) > 2:
                    date = cells[2].get_text(strip=True)
                
                announcement = {
                    'title': title,
                    'url': detail_url,
                    'date': date,
                    'number': number,
                    'content_id': content_id
                }
                
                announcements.append(announcement)
                logger.debug(f"공고 추가: {title}")
                
            except Exception as e:
                logger.error(f"행 파싱 중 오류: {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
        return announcements
    
    def _parse_with_playwright(self):
        """Playwright를 사용한 JavaScript 렌더링 후 파싱 - 타임아웃 증가"""
        try:
            from playwright.sync_api import sync_playwright
            
            announcements = []
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # 타임아웃 설정 증가
                page.set_default_timeout(60000)  # 60초
                
                # 페이지 로드
                page.goto(self.list_url, timeout=60000)
                page.wait_for_load_state('networkidle', timeout=60000)
                
                # 추가 대기시간
                page.wait_for_timeout(3000)
                
                # 테이블 요소들 추출 - 다양한 선택자 시도
                rows = []
                
                # 여러 방법으로 행 찾기
                selectors = ['tbody tr', 'table tr', 'tr']
                for selector in selectors:
                    temp_rows = page.locator(selector).all()
                    if temp_rows:
                        rows = temp_rows
                        logger.info(f"Playwright로 '{selector}' 선택자로 {len(rows)}개 행 발견")
                        break
                
                if not rows:
                    logger.warning("Playwright로도 행을 찾을 수 없습니다.")
                    return []
                
                for i, row in enumerate(rows):
                    try:
                        # 셀 찾기
                        cells = row.locator('td').all()
                        if len(cells) < 2:
                            # 헤더 행일 수 있으므로 건너뛰기
                            logger.debug(f"행 {i}: 셀 수 부족 ({len(cells)}개)")
                            continue
                        
                        # 번호
                        number = cells[0].inner_text().strip()
                        if not number or (number.isdigit() == False and number != "공지"):
                            logger.debug(f"행 {i}: 번호가 유효하지 않음 ({number})")
                            continue
                        
                        # 제목과 링크
                        title_cell = cells[1]
                        links = title_cell.locator('a').all()
                        if not links:
                            logger.debug(f"행 {i}: 링크를 찾을 수 없음")
                            continue
                        
                        link = links[0]  # 첫 번째 링크 사용
                        title = link.inner_text().strip()
                        if not title:
                            logger.debug(f"행 {i}: 제목이 비어있음")
                            continue
                        
                        # href와 onclick 둘 다 확인
                        onclick = link.get_attribute('onclick') or ''
                        href = link.get_attribute('href') or ''
                        
                        # contentsView ID 추출
                        content_id = None
                        
                        # href에서 먼저 시도
                        if href and 'contentsView' in href:
                            match = re.search(r"contentsView\('(\d+)'\)", href)
                            if match:
                                content_id = match.group(1)
                        
                        # onclick에서 시도
                        if not content_id and onclick:
                            match = re.search(r"contentsView\('(\d+)'\)", onclick)
                            if match:
                                content_id = match.group(1)
                        
                        if not content_id:
                            logger.debug(f"행 {i}: 컨텐츠 ID를 찾을 수 없음 (href: {href[:50]}, onclick: {onclick[:50]})")
                            continue
                        
                        # 날짜 (있는 경우)
                        date = ""
                        if len(cells) > 2:
                            date = cells[2].inner_text().strip()
                        
                        detail_url = f"{self.detail_base_url}?contentsId={content_id}"
                        
                        announcement = {
                            'title': title,
                            'url': detail_url,
                            'date': date,
                            'number': number,
                            'content_id': content_id
                        }
                        
                        announcements.append(announcement)
                        logger.info(f"공고 추가: {title}")
                        
                    except Exception as e:
                        logger.error(f"Playwright 행 {i} 파싱 중 오류: {e}")
                        continue
                
                browser.close()
            
            logger.info(f"Playwright로 {len(announcements)}개 공고 파싱 완료")
            return announcements
            
        except ImportError:
            logger.error("Playwright가 설치되지 않았습니다. pip install playwright 후 playwright install 실행하세요.")
            return []
        except Exception as e:
            logger.error(f"Playwright 파싱 중 오류: {e}")
            return []
    
    def get_detail_page_with_playwright(self, content_id: str) -> str:
        """Playwright를 사용해서 상세 페이지 가져오기 - 타임아웃 증가"""
        try:
            from playwright.sync_api import sync_playwright
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # 타임아웃 설정 증가
                page.set_default_timeout(60000)  # 60초
                
                # 목록 페이지로 이동
                page.goto(self.list_url, timeout=60000)
                page.wait_for_load_state('networkidle', timeout=60000)
                
                # JavaScript 함수로 상세 페이지 클릭
                try:
                    # contentsView JavaScript 함수 실행
                    page.evaluate(f"contentsView('{content_id}')")
                    
                    # 페이지 전환 대기 - URL 변경을 기다림
                    page.wait_for_url("**/boardContentsView.do**", timeout=30000)
                    page.wait_for_load_state('networkidle', timeout=30000)
                    
                    # 추가 대기시간 증가
                    page.wait_for_timeout(5000)
                    
                except Exception as e:
                    logger.warning(f"JavaScript 함수 실행 또는 페이지 전환 실패: {e}")
                    # 직접 URL로 접근 시도
                    direct_url = f"{self.detail_base_url}?contentsId={content_id}"
                    page.goto(direct_url, timeout=60000)
                    page.wait_for_load_state('networkidle', timeout=30000)
                    page.wait_for_timeout(3000)
                
                # 페이지 내용 가져오기
                html_content = page.content()
                browser.close()
                
                logger.info(f"상세 페이지 HTML 길이: {len(html_content)}")
                return html_content
                
        except Exception as e:
            logger.error(f"Playwright 상세 페이지 가져오기 실패: {e}")
            return ""
    
    def parse_detail_page(self, html_content: str) -> dict:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 본문 내용 찾기
        content = ""
        title = ""
        date = ""
        
        # 상세보기 테이블에서 내용 추출
        detail_table = soup.find('table')
        if detail_table:
            rows = detail_table.find_all('tr')
            for row in rows:
                cells = row.find_all(['th', 'td'])
                
                # 제목 추출
                if len(cells) == 2:
                    th = cells[0].get_text(strip=True)
                    if th == "제목":
                        title = cells[1].get_text(strip=True)
                    elif th == "작성일":
                        date = cells[1].get_text(strip=True)
                
                # 본문 내용 추출 (셀이 1개이고 이미지나 텍스트가 있는 경우)
                if len(cells) == 1:
                    content_cell = cells[0]
                    
                    # 이미지가 있는지 확인
                    images = content_cell.find_all('img')
                    if images:
                        # 이미지 기반 공고의 경우
                        content = "## 공고 내용\n\n이 공고는 이미지 형태로 제공됩니다. 첨부파일을 다운로드하여 확인하세요.\n\n"
                        for img in images:
                            src = img.get('src', '')
                            if src:
                                content += f"![공고 이미지]({src})\n\n"
                    else:
                        # 텍스트 기반 공고의 경우
                        cell_text = content_cell.get_text(strip=True)
                        if len(cell_text) > 50:  # 어느 정도 길이가 있는 텍스트만 본문으로 간주
                            # HTML을 마크다운으로 변환
                            paragraphs = content_cell.find_all('p')
                            if paragraphs:
                                content_parts = []
                                for p in paragraphs:
                                    p_text = p.get_text(strip=True)
                                    if p_text:
                                        content_parts.append(p_text)
                                content = '\n\n'.join(content_parts)
                            else:
                                # p 태그가 없는 경우 전체 텍스트 사용
                                content = cell_text
                            
                            # 불필요한 공백 정리
                            content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
                            break
        
        # 첨부파일 찾기
        attachments = []
        
        if detail_table:
            rows = detail_table.find_all('tr')
            for row in rows:
                cells = row.find_all(['th', 'td'])
                
                # 첨부파일 행 찾기
                if len(cells) >= 2:
                    th = cells[0]
                    if th and '첨부파일' in th.get_text():
                        td = cells[1]
                        if td:
                            # 첨부파일 링크들 찾기
                            file_links = td.find_all('a')
                            for link in file_links:
                                filename = link.get_text(strip=True)
                                href = link.get('href', '')
                                
                                if href and filename:
                                    # 절대 URL로 변환
                                    if href.startswith('/'):
                                        file_url = self.base_url + href
                                    else:
                                        file_url = urljoin(self.base_url, href)
                                    
                                    attachment = {
                                        'filename': filename,
                                        'url': file_url
                                    }
                                    attachments.append(attachment)
                                    logger.info(f"첨부파일 발견: {filename}")
        
        # 본문이 비어있으면 기본 텍스트 추가
        if not content.strip():
            content = "## 공고 내용\n\n공고 내용을 확인하려면 첨부파일을 다운로드하여 확인하세요.\n\n"
        else:
            # 마크다운 형태로 정리
            content = f"## 공고 내용\n\n{content}\n\n"
        
        result = {
            'title': title,
            'content': content,
            'attachments': attachments,
            'date': date
        }
        
        logger.info(f"상세 페이지 파싱 완료 - 제목: {title}, 날짜: {date}, 내용: {len(content)}자, 첨부파일: {len(attachments)}개")
        return result
    
    def process_announcement(self, announcement: dict, index: int, output_base: str = 'output'):
        """개별 공고 처리 - Playwright 사용, 대기시간 증가"""
        logger.info(f"공고 처리 중 {index}: {announcement['title']}")
        
        # 폴더 생성
        folder_title = self.sanitize_filename(announcement['title'])[:100]
        folder_name = f"{index:03d}_{folder_title}"
        
        if len(folder_name) > 200:
            folder_title = folder_title[:195]
            folder_name = f"{index:03d}_{folder_title}"
        
        folder_path = os.path.join(output_base, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        
        # Playwright로 상세 페이지 가져오기
        content_id = announcement.get('content_id')
        if content_id:
            html_content = self.get_detail_page_with_playwright(content_id)
            if not html_content:
                logger.error(f"상세 페이지 가져오기 실패: {announcement['title']}")
                return
        else:
            # 일반적인 방법으로 시도
            response = self.get_page(announcement['url'])
            if not response:
                logger.error(f"상세 페이지 가져오기 실패: {announcement['title']}")
                return
            html_content = response.text
        
        # 상세 내용 파싱
        try:
            detail = self.parse_detail_page(html_content)
            logger.info(f"상세 페이지 파싱 완료 - 내용길이: {len(detail['content'])}, 첨부파일: {len(detail['attachments'])}")
            
            # 목록에서 가져온 정보에 상세페이지 정보 업데이트
            if detail.get('date') and not announcement.get('date'):
                announcement['date'] = detail['date']
            
            # HTML 길이 검증
            if len(html_content) < 1000:
                logger.warning(f"HTML 내용이 너무 짧습니다: {len(html_content)}자")
                
            # 파싱 결과 검증
            if not detail.get('content') or len(detail['content']) < 50:
                logger.warning(f"파싱된 내용이 부족합니다: {len(detail.get('content', ''))}자")
                
        except Exception as e:
            logger.error(f"상세 페이지 파싱 실패: {e}")
            # 기본 콘텐츠로라도 저장
            detail = {
                'title': announcement.get('title', ''),
                'content': "## 공고 내용\n\n상세 내용을 가져올 수 없습니다. 원본 페이지를 확인해주세요.\n\n",
                'attachments': [],
                'date': ''
            }
        
        # 메타 정보 생성
        meta_info = self._create_meta_info(announcement)
        
        # 본문 저장
        content_path = os.path.join(folder_path, 'content.md')
        with open(content_path, 'w', encoding='utf-8') as f:
            f.write(meta_info + detail['content'])
        
        logger.info(f"내용 저장 완료: {content_path}")
        
        # 첨부파일 다운로드
        self._download_attachments(detail['attachments'], folder_path)
        
        # 처리된 제목으로 추가
        self.add_processed_title(announcement['title'])
        
        # 요청 간 대기 시간 증가
        if self.delay_between_requests > 0:
            time.sleep(self.delay_between_requests)

# 테스트용 함수
def test_jscci_scraper(pages=3):
    """Jscci 스크래퍼 테스트"""
    import os
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    scraper = EnhancedJscciScraper()
    output_dir = "output/jscci"
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"Jscci 스크래퍼 테스트 시작 - {pages}페이지")
    scraper.scrape_pages(max_pages=pages, output_base=output_dir)
    logger.info("Jscci 스크래퍼 테스트 완료")

if __name__ == "__main__":
    test_jscci_scraper(3)