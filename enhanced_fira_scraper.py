# -*- coding: utf-8 -*-
"""
FIRA (한국수산자원공단) 스크래퍼 - GET 방식 페이지네이션 지원
"""

import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
from typing import Dict, List, Any, Optional
import logging
from enhanced_base_scraper import EnhancedBaseScraper

logger = logging.getLogger(__name__)

class EnhancedFiraScraper(EnhancedBaseScraper):
    """FIRA 한국수산자원공단 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.fira.or.kr"
        self.list_url = "https://www.fira.or.kr/fira/fira_010101_1.jsp"
        self.board_no = "2"  # 공지사항 게시판 번호
        
        # 사이트별 헤더 설정
        self.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'max-age=0',
            'Upgrade-Insecure-Requests': '1'
        })
        self.session.headers.update(self.headers)
        
        # 성능 최적화
        self.delay_between_requests = 1.5
        self.delay_between_pages = 1.0
        
    def get_list_url(self, page_num: int) -> str:
        """페이지별 목록 URL 생성 (GET 방식)"""
        if page_num == 1:
            return f"{self.list_url}?mode=list&board_no={self.board_no}"
        else:
            offset = (page_num - 1) * 10  # 페이지당 10개 게시글
            return f"{self.list_url}?mode=list&board_no={self.board_no}&pager.offset={offset}"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱 - 테이블 기반"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # HTML 내용 디버깅
        logger.debug(f"HTML 길이: {len(html_content)} characters")
        
        # FIRA 사이트의 정확한 테이블 클래스로 찾기
        table = soup.find('table', class_='lmode')
        if not table:
            # 디버깅: 페이지에 있는 모든 table 태그 찾기
            all_tables = soup.find_all('table')
            logger.warning(f"table.lmode 테이블을 찾을 수 없습니다. 페이지에 있는 table 태그: {len(all_tables)}개")
            for i, t in enumerate(all_tables):
                classes = t.get('class', [])
                logger.debug(f"Table {i}: classes={classes}")
            
            # 대안: 첫 번째 table 시도
            if all_tables:
                table = all_tables[0]
                logger.info("첫 번째 table 태그 사용")
            else:
                return announcements
        
        # tbody 내의 tr 요소들 찾기
        tbody = table.find('tbody')
        if not tbody:
            logger.warning("테이블 tbody를 찾을 수 없습니다")
            # 직접 tr 찾기
            rows = table.find_all('tr')
            logger.info(f"tbody 없이 직접 tr 찾기: {len(rows)}개")
        else:
            rows = tbody.find_all('tr')
            logger.info(f"테이블에서 {len(rows)}개 행 발견")
        
        for row_index, row in enumerate(rows):
            try:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 6:  # 번호, 제목, 작성자, 작성일, 첨부파일, 조회수
                    logger.debug(f"행 {row_index}: 셀 수 부족 ({len(cells)}개)")
                    continue
                
                # 제목 셀 (두 번째 셀)
                title_cell = cells[1]
                link_elem = title_cell.find('a')
                if not link_elem:
                    logger.debug(f"행 {row_index}: 제목 링크 없음")
                    continue
                
                title = link_elem.get_text(strip=True)
                if not title:
                    logger.debug(f"행 {row_index}: 제목 텍스트 없음")
                    continue
                
                # URL 구성
                href = link_elem.get('href', '')
                if href.startswith('?'):
                    # 쿼리 스트링으로 시작하는 경우 기본 페이지 경로 추가
                    detail_url = self.list_url + href
                else:
                    detail_url = urljoin(self.base_url, href)
                
                # 기본 정보 구성
                announcement = {
                    'title': title,
                    'url': detail_url
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
                    
                    # 첨부파일 존재 여부 (다섯 번째 셀)
                    if len(cells) > 4:
                        attach_cell = cells[4]
                        if attach_cell.find('img') or '첨부' in attach_cell.get_text():
                            announcement['has_attachment'] = True
                    
                    # 조회수 (여섯 번째 셀)
                    if len(cells) > 5:
                        views = cells[5].get_text(strip=True)
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
        
        # 디버깅: 페이지에 있는 모든 table 태그 확인
        all_tables = soup.find_all('table')
        logger.debug(f"페이지에 있는 테이블 개수: {len(all_tables)}")
        for i, table in enumerate(all_tables):
            classes = table.get('class', [])
            table_id = table.get('id', '')
            logger.debug(f"Table {i}: classes={classes}, id={table_id}")
        
        # FIRA 사이트의 상세 화면 테이블 찾기 (table.vmode)
        detail_table = soup.find('table', class_='vmode')
        if not detail_table:
            # 대안 방법: 모든 table 태그 검사
            for table in all_tables:
                classes = table.get('class', [])
                if 'vmode' in classes:
                    detail_table = table
                    break
        
        if not detail_table:
            logger.warning("상세 페이지 테이블을 찾을 수 없습니다")
            # 첫 번째 테이블 사용 시도
            if all_tables:
                detail_table = all_tables[0]
                logger.info("첫 번째 테이블 사용 시도")
            else:
                return result
        
        # 본문 내용 추출
        try:
            content = self._extract_content(detail_table, soup)
            result['content'] = content
        except Exception as e:
            logger.error(f"본문 추출 중 오류: {e}")
        
        # 첨부파일 추출
        try:
            attachments = self._extract_attachments(detail_table, soup)
            result['attachments'] = attachments
        except Exception as e:
            logger.error(f"첨부파일 추출 중 오류: {e}")
        
        return result
    
    def _extract_content(self, table_soup: BeautifulSoup, full_soup: BeautifulSoup) -> str:
        """본문 내용 추출"""
        # 첫 번째 방법: div#article_text 직접 찾기 (가장 정확함)
        content_div = full_soup.find('div', id='article_text')
        if content_div:
            content_html = str(content_div)
            content_md = self.h.handle(content_html)
            content_md = re.sub(r'\n\s*\n', '\n\n', content_md)
            content_md = content_md.strip()
            logger.debug(f"div#article_text에서 본문 추출: {len(content_md)} chars")
            return content_md
        
        # 두 번째 방법: FIRA 사이트의 본문 내용 찾기 - table.vmode의 4번째 행 td
        rows = table_soup.find_all('tr')
        if len(rows) >= 4:
            # 4번째 행의 td에서 본문 추출
            content_row = rows[3]  # 0-based index
            content_cell = content_row.find('td')
            if content_cell:
                # HTML을 마크다운으로 변환
                content_html = str(content_cell)
                content_md = self.h.handle(content_html)
                
                # 불필요한 공백 정리
                content_md = re.sub(r'\n\s*\n', '\n\n', content_md)
                content_md = content_md.strip()
                
                logger.debug(f"테이블 4번째 행에서 본문 추출: {len(content_md)} chars")
                return content_md
        
        # 세 번째 방법: colspan이 큰 td 찾기
        for row in rows:
            cells = row.find_all('td')
            for cell in cells:
                if cell.get('colspan') and int(cell.get('colspan', '1')) > 1:
                    content_html = str(cell)
                    content_md = self.h.handle(content_html)
                    content_md = re.sub(r'\n\s*\n', '\n\n', content_md)
                    content_md = content_md.strip()
                    logger.debug(f"colspan 큰 td에서 본문 추출: {len(content_md)} chars")
                    return content_md
        
        logger.warning("본문 내용을 찾을 수 없습니다")
        return ""
    
    def _extract_attachments(self, table_soup: BeautifulSoup, full_soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """첨부파일 링크 추출"""
        attachments = []
        
        # 첫 번째 방법: ul.attach_list 직접 찾기
        attach_list = full_soup.find('ul', class_='attach_list')
        if attach_list:
            download_links = attach_list.find_all('a', href=re.compile(r'javascript:download\('))
        else:
            # 두 번째 방법: FIRA 사이트의 첨부파일 구조 - table.vmode의 3번째 행 내 ul.attach_list
            rows = table_soup.find_all('tr')
            if len(rows) >= 3:
                # 3번째 행에서 첨부파일 찾기
                attach_row = rows[2]  # 0-based index
                attach_list = attach_row.find('ul', class_='attach_list')
                if attach_list:
                    # ul.attach_list 내의 a 태그들 찾기
                    download_links = attach_list.find_all('a', href=re.compile(r'javascript:download\('))
                else:
                    # 전체 행에서 다운로드 링크 찾기
                    download_links = attach_row.find_all('a', href=re.compile(r'javascript:download\('))
            else:
                # 전체 테이블에서 다운로드 링크 찾기
                download_links = table_soup.find_all('a', href=re.compile(r'javascript:download\('))
        
        for link in download_links:
            try:
                href = link.get('href', '')
                filename = link.get_text(strip=True)
                
                # 파일 ID 추출
                file_id_match = re.search(r"download\('([^']+)'\)", href)
                if not file_id_match:
                    continue
                
                file_id = file_id_match.group(1)
                
                # 실제 다운로드 URL 구성 (분석 결과 반영)
                download_url = f"{self.base_url}/_custom/cms/_common/board/fira.jsp?attach_no={file_id}"
                
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
        """파일 다운로드 - FIRA 사이트 특화"""
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
            logging.FileHandler('fira_scraper.log', encoding='utf-8')
        ]
    )
    
    logger.info("FIRA 스크래퍼 시작")
    
    # 출력 디렉토리 설정
    output_dir = "output/fira"
    if os.path.exists(output_dir):
        import shutil
        shutil.rmtree(output_dir)
        logger.info(f"기존 출력 디렉토리 삭제: {output_dir}")
    
    # 스크래퍼 실행
    scraper = EnhancedFiraScraper()
    
    try:
        # 3페이지 수집
        scraper.scrape_pages(max_pages=3, output_base='output/fira')
        logger.info("FIRA 스크래퍼 완료")
        
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