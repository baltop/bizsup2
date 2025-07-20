# -*- coding: utf-8 -*-
"""
GAFI (경기도농수산진흥원) 스크래퍼 - POST 방식 페이지네이션 지원
"""

import re
import json
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
from typing import Dict, List, Any, Optional
import logging
from enhanced_base_scraper import EnhancedBaseScraper

logger = logging.getLogger(__name__)

class EnhancedGafiScraper(EnhancedBaseScraper):
    """GAFI 경기도농수산진흥원 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.gafi.or.kr"
        self.list_url = "https://www.gafi.or.kr/web/board/boardContentsListPage.do"
        self.board_id = "42"  # 입찰/공모 게시판 ID
        self.menu_id = "9d7a4fa3cd784b2ea1ab192315847444"  # 메뉴 ID
        
        # 사이트별 헤더 설정
        self.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'max-age=0',
            'Upgrade-Insecure-Requests': '1',
            'Content-Type': 'application/x-www-form-urlencoded'
        })
        self.session.headers.update(self.headers)
        
        # 성능 최적화
        self.delay_between_requests = 2.0
        self.delay_between_pages = 1.5
        
        # 세션 초기화
        self._initialize_session()
        
    def _initialize_session(self):
        """세션 초기화 - 첫 페이지 방문으로 세션 생성"""
        try:
            initial_url = f"{self.list_url}?board_id={self.board_id}&menu_id={self.menu_id}"
            response = self.session.get(initial_url, timeout=self.timeout)
            
            if response.status_code == 200:
                # JSESSIONID 추출
                if 'jsessionid' in response.url:
                    self.session_id = response.url.split('jsessionid=')[1].split('&')[0] if '&' in response.url.split('jsessionid=')[1] else response.url.split('jsessionid=')[1]
                    logger.info(f"세션 초기화 완료: {self.session_id[:10]}...")
                else:
                    logger.warning("JSESSIONID를 찾을 수 없습니다")
                    
            else:
                logger.error(f"세션 초기화 실패: HTTP {response.status_code}")
                
        except Exception as e:
            logger.error(f"세션 초기화 중 오류: {e}")
    
    def get_list_url(self, page_num: int) -> str:
        """페이지별 목록 URL 생성 - POST 방식이므로 기본 URL 반환"""
        return f"{self.base_url}/web/board/boardContentsList.do"
    
    def _get_page_announcements(self, page_num: int) -> List[Dict[str, Any]]:
        """페이지별 공고 목록 가져오기 - Playwright 사용"""
        try:
            from playwright.sync_api import sync_playwright
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # 첫 페이지 방문
                init_url = f"{self.list_url}?board_id={self.board_id}&menu_id={self.menu_id}"
                page.goto(init_url)
                
                # 페이지 로딩 대기
                page.wait_for_timeout(3000)
                
                if page_num > 1:
                    # 페이지 이동 JavaScript 실행
                    page.evaluate(f"go_Page({page_num})")
                    page.wait_for_timeout(2000)
                
                # HTML 가져오기
                html_content = page.content()
                browser.close()
                
                logger.info(f"페이지 {page_num} Playwright로 가져오기 성공")
                return self.parse_list_page(html_content)
                
        except ImportError:
            logger.error("Playwright가 설치되지 않았습니다. pip install playwright 실행 후 playwright install 실행하세요.")
            return []
        except Exception as e:
            logger.error(f"페이지 {page_num} Playwright 가져오기 중 오류: {e}")
            return []
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱 - 테이블 기반"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # HTML 내용 디버깅
        logger.debug(f"HTML 길이: {len(html_content)} characters")
        
        # GAFI 사이트의 목록 테이블 찾기 (class: tstyle_list)
        table = soup.find('table', class_='tstyle_list')
        if not table:
            # 대안: 다른 클래스나 속성으로 찾기
            table = soup.find('table', attrs={'summary': '목록 화면'})
            if not table:
                # 모든 테이블에서 찾기
                tables = soup.find_all('table')
                for t in tables:
                    caption = t.find('caption')
                    if caption and '목록' in caption.get_text():
                        table = t
                        break
        
        if not table:
            logger.warning("목록 테이블을 찾을 수 없습니다")
            # 디버깅: 모든 테이블 확인
            all_tables = soup.find_all('table')
            logger.debug(f"페이지에 있는 테이블 개수: {len(all_tables)}")
            for i, t in enumerate(all_tables):
                summary = t.get('summary', '')
                caption = t.find('caption')
                caption_text = caption.get_text() if caption else ''
                classes = t.get('class', [])
                logger.debug(f"Table {i}: summary='{summary}', caption='{caption_text}', classes={classes}")
                
            if all_tables:
                table = all_tables[0]
                logger.info("첫 번째 테이블 사용")
            else:
                return announcements
        
        # tbody 내의 tr 요소들 찾기
        tbody = table.find('tbody')
        if not tbody:
            logger.warning("테이블 tbody를 찾을 수 없습니다")
            rows = table.find_all('tr')
            logger.info(f"tbody 없이 직접 tr 찾기: {len(rows)}개")
        else:
            rows = tbody.find_all('tr')
            logger.info(f"테이블에서 {len(rows)}개 행 발견")
        
        for row_index, row in enumerate(rows):
            try:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 5:  # 번호, 제목, 작성자, 작성일, 조회수
                    logger.debug(f"행 {row_index}: 셀 수 부족 ({len(cells)}개)")
                    continue
                
                # 제목 셀 (두 번째 셀)
                title_cell = cells[1]
                link_elem = title_cell.find('a')
                if not link_elem:
                    logger.debug(f"행 {row_index}: 제목 링크 없음")
                    continue
                
                # JavaScript 링크에서 contents_id 추출
                href = link_elem.get('href', '')
                if 'contentsView' not in href:
                    logger.debug(f"행 {row_index}: contentsView 링크 아님")
                    continue
                
                # contents_id 추출
                contents_id_match = re.search(r"contentsView\('([^']+)'\)", href)
                if not contents_id_match:
                    logger.debug(f"행 {row_index}: contents_id 추출 실패")
                    continue
                
                contents_id = contents_id_match.group(1)
                title = link_elem.get_text(strip=True)
                
                if not title:
                    logger.debug(f"행 {row_index}: 제목 텍스트 없음")
                    continue
                
                # 상세 페이지 URL 구성
                detail_url = f"{self.base_url}/web/board/boardContentsView.do?contents_id={contents_id}&board_id={self.board_id}&menu_id={self.menu_id}"
                
                # 기본 정보 구성
                announcement = {
                    'title': title,
                    'url': detail_url,
                    'contents_id': contents_id
                }
                
                # 추가 메타데이터 추출
                try:
                    # 번호 (첫 번째 셀)
                    number_cell = cells[0]
                    number = self.process_notice_detection(number_cell, row_index)
                    if number:
                        announcement['number'] = number
                    
                    # 작성자 (세 번째 셀)
                    if len(cells) > 2:
                        writer = cells[2].get_text(strip=True)
                        if writer:
                            announcement['writer'] = writer
                    
                    # 작성일 (네 번째 셀)
                    if len(cells) > 3:
                        date = cells[3].get_text(strip=True)
                        if date:
                            announcement['date'] = date
                    
                    # 조회수 (다섯 번째 셀)
                    if len(cells) > 4:
                        views = cells[4].get_text(strip=True)
                        if views and views.isdigit():
                            announcement['views'] = views
                
                except Exception as e:
                    logger.debug(f"메타데이터 추출 중 오류: {e}")
                
                announcements.append(announcement)
                logger.debug(f"공고 추가: {title[:50]}...")
                
            except Exception as e:
                logger.error(f"행 파싱 중 오류: {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
        return announcements
    
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 기본 반환값
        result = {
            'content': '',
            'attachments': []
        }
        
        # 상세 페이지 테이블 찾기
        table = soup.find('table', attrs={'summary': '상세보기'})
        if not table:
            # 대안: caption이 있는 테이블 찾기
            tables = soup.find_all('table')
            for t in tables:
                caption = t.find('caption')
                if caption and ('상세' in caption.get_text() or '보기' in caption.get_text()):
                    table = t
                    break
                    
        if not table:
            logger.warning("상세 페이지 테이블을 찾을 수 없습니다")
            # 첫 번째 테이블 사용
            tables = soup.find_all('table')
            if tables:
                table = tables[0]
                logger.info("첫 번째 테이블 사용")
            else:
                return result
        
        # 본문 내용 추출
        try:
            content = self._extract_content(table, soup)
            result['content'] = content
        except Exception as e:
            logger.error(f"본문 추출 중 오류: {e}")
        
        # 첨부파일 추출
        try:
            attachments = self._extract_attachments(table, soup)
            result['attachments'] = attachments
        except Exception as e:
            logger.error(f"첨부파일 추출 중 오류: {e}")
        
        return result
    
    def _extract_content(self, table_soup: BeautifulSoup, full_soup: BeautifulSoup) -> str:
        """본문 내용 추출"""
        # 여러 방법으로 본문 추출 시도
        
        # 첫 번째 방법: 테이블 행들을 순회하면서 본문 내용 찾기
        rows = table_soup.find_all('tr')
        for i, row in enumerate(rows):
            cells = row.find_all(['td', 'th'])
            
            # 제목 행 건너뛰기
            if i == 0:
                continue
                
            # 작성자/작성일 행 건너뛰기
            if len(cells) >= 4 and any(keyword in str(row) for keyword in ['작성자', '작성일', '글쓴이']):
                continue
                
            # 첨부파일 행 건너뛰기
            if any(keyword in str(row) for keyword in ['첨부', 'attach', 'file']):
                continue
                
            # 본문 내용으로 보이는 행 찾기
            for cell in cells:
                # colspan이 큰 셀이나 내용이 많은 셀 찾기
                if cell.get('colspan') or len(cell.get_text(strip=True)) > 50:
                    content_html = str(cell)
                    content_md = self.h.handle(content_html)
                    content_md = re.sub(r'\n\s*\n', '\n\n', content_md)
                    content_md = content_md.strip()
                    
                    if len(content_md) > 20:  # 충분한 내용이 있는 경우
                        logger.debug(f"테이블 행 {i}에서 본문 추출: {len(content_md)} chars")
                        return content_md
        
        # 두 번째 방법: 전체 테이블을 본문으로 변환
        content_html = str(table_soup)
        content_md = self.h.handle(content_html)
        content_md = re.sub(r'\n\s*\n', '\n\n', content_md)
        content_md = content_md.strip()
        
        logger.debug(f"전체 테이블에서 본문 추출: {len(content_md)} chars")
        return content_md
    
    def _extract_attachments(self, table_soup: BeautifulSoup, full_soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """첨부파일 링크 추출"""
        attachments = []
        
        # 첨부파일 다운로드 링크 찾기
        download_links = full_soup.find_all('a', href=re.compile(r'fileidDownLoad\.do'))
        
        for link in download_links:
            try:
                href = link.get('href', '')
                filename = link.get_text(strip=True)
                
                # 파일 ID 추출
                file_id_match = re.search(r'file_id=([^&]+)', href)
                if not file_id_match:
                    continue
                
                file_id = file_id_match.group(1)
                
                # 절대 URL 구성
                if href.startswith('/'):
                    download_url = self.base_url + href
                else:
                    download_url = urljoin(self.base_url, href)
                
                attachment = {
                    'filename': filename,
                    'url': download_url,
                    'file_id': file_id
                }
                
                attachments.append(attachment)
                logger.debug(f"첨부파일 발견: {filename}")
                
            except Exception as e:
                logger.error(f"첨부파일 링크 파싱 중 오류: {e}")
                continue
        
        logger.info(f"총 {len(attachments)}개 첨부파일 추출")
        return attachments
    
    def download_file(self, url: str, save_path: str, attachment_info: Dict[str, Any] = None) -> bool:
        """파일 다운로드 - GAFI 사이트 특화"""
        try:
            # Referer 헤더 설정
            download_headers = self.headers.copy()
            download_headers['Referer'] = self.base_url
            
            # 파일 다운로드 요청
            response = self.session.get(url, headers=download_headers, stream=True, timeout=self.timeout)
            
            # 응답 상태 확인
            if response.status_code != 200:
                logger.error(f"파일 다운로드 실패 (HTTP {response.status_code}): {url}")
                return False
            
            # Content-Type 확인 (HTML 응답 감지)
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' in content_type:
                logger.warning(f"HTML 응답 감지 - 파일 다운로드 실패: {url}")
                return False
            
            # 파일 저장
            import os
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # 파일 크기 확인
            file_size = os.path.getsize(save_path)
            if file_size < 1024:  # 1KB 미만이면 오류 파일일 가능성
                with open(save_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if '<html>' in content.lower() or '<!doctype' in content.lower():
                        logger.warning(f"HTML 내용 감지 - 오류 파일 삭제: {save_path}")
                        os.remove(save_path)
                        return False
            
            logger.info(f"파일 다운로드 완료: {save_path} ({file_size:,} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"파일 다운로드 중 오류: {e}")
            return False


def main():
    """메인 실행 함수"""
    import os
    import sys
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('gafi_scraper.log', encoding='utf-8')
        ]
    )
    
    logger.info("GAFI 스크래퍼 시작")
    
    # 출력 디렉토리 설정
    output_dir = "output/gafi"
    if os.path.exists(output_dir):
        import shutil
        shutil.rmtree(output_dir)
        logger.info(f"기존 출력 디렉토리 삭제: {output_dir}")
    
    # 스크래퍼 실행
    scraper = EnhancedGafiScraper()
    
    try:
        # 3페이지 수집
        scraper.scrape_pages(max_pages=3, output_base='output/gafi')
        logger.info("GAFI 스크래퍼 완료")
        
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
    except Exception as e:
        logger.error(f"스크래퍼 실행 중 오류: {e}")
        raise
    
    # 통계 출력
    stats = scraper.get_stats()
    logger.info(f"수집 완료 - 처리 시간: {stats.get('duration_seconds', 0):.1f}초")


if __name__ == "__main__":
    main()