# -*- coding: utf-8 -*-
"""
GEEA (경북동부경영자협회) 스크래퍼 - GET 방식 페이지네이션 지원
"""

import re
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote, parse_qs, urlparse
from typing import Dict, List, Any, Optional
import logging
from enhanced_base_scraper import EnhancedBaseScraper

logger = logging.getLogger(__name__)

class EnhancedGeeaScraper(EnhancedBaseScraper):
    """GEEA 경북동부경영자협회 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "http://www.geea.or.kr"
        self.list_url = "http://www.geea.or.kr/bbs_shop/list.htm"
        self.board_code = "notice"
        
        # 사이트별 헤더 설정
        self.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Cache-Control': 'max-age=0',
            'Upgrade-Insecure-Requests': '1'
        })
        self.session.headers.update(self.headers)
        
        # 성능 최적화
        self.delay_between_requests = 1.2
        self.delay_between_pages = 1.0
        
    def get_list_url(self, page_num: int) -> str:
        """페이지별 목록 URL 생성"""
        base_params = {
            'page': str(page_num),
            'me_popup': '',
            'auto_frame': '',
            'cate_sub_idx': '0',
            'search_first_subject': '',
            'list_mode': 'board',
            'board_code': self.board_code,
            'keyfield': '',
            'key': '',
            'y': '',
            'm': ''
        }
        
        param_str = '&'.join([f"{k}={v}" for k, v in base_params.items()])
        return f"{self.list_url}?{param_str}"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱 - 테이블 기반"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # HTML 내용 디버깅
        logger.debug(f"HTML 길이: {len(html_content)} characters")
        
        # GEEA 사이트의 목록 테이블 찾기
        table = soup.find('table', attrs={'summary': '게시판 게시물 리스트'})
        if not table:
            # 대안: 클래스로 찾기
            table = soup.find('table', class_='게시판 게시물 리스트')
            if not table:
                # 모든 테이블 확인
                all_tables = soup.find_all('table')
                logger.debug(f"페이지에 있는 테이블 개수: {len(all_tables)}")
                
                for i, t in enumerate(all_tables):
                    summary = t.get('summary', '')
                    classes = t.get('class', [])
                    if summary and ('게시판' in summary or '게시물' in summary):
                        table = t
                        logger.info(f"테이블 {i} 사용 (summary: {summary})")
                        break
                    elif classes and any('게시판' in str(cls) for cls in classes):
                        table = t
                        logger.info(f"테이블 {i} 사용 (classes: {classes})")
                        break
        
        if not table:
            logger.warning("목록 테이블을 찾을 수 없습니다")
            # 마지막 대안: 첫 번째 테이블 사용
            all_tables = soup.find_all('table')
            if all_tables:
                table = all_tables[0]
                logger.info("첫 번째 테이블 사용")
            else:
                return announcements
        
        # tbody 또는 직접 tr 찾기
        tbody = table.find('tbody')
        if tbody:
            rows = tbody.find_all('tr')
            logger.info(f"tbody에서 {len(rows)}개 행 발견")
        else:
            rows = table.find_all('tr')
            # 헤더 행 제외
            if rows and (rows[0].find('th') or '번호' in rows[0].get_text()):
                rows = rows[1:]
            logger.info(f"table에서 {len(rows)}개 행 발견 (헤더 제외)")
        
        for row_index, row in enumerate(rows):
            try:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 4:  # 번호, 제목, 이름, 날짜, 조회수
                    logger.debug(f"행 {row_index}: 셀 수 부족 ({len(cells)}개)")
                    continue
                
                # 제목 셀에서 링크 찾기
                title_cell = None
                title_link = None
                
                for cell in cells:
                    link = cell.find('a')
                    if link and link.get('href'):
                        href = link.get('href')
                        if 'read.htm' in href or 'bbs/notice' in href:
                            title_cell = cell
                            title_link = link
                            break
                
                if not title_link:
                    logger.debug(f"행 {row_index}: 제목 링크 없음")
                    continue
                
                # 제목 추출
                title = title_link.get_text(strip=True)
                if not title:
                    logger.debug(f"행 {row_index}: 제목 텍스트 없음")
                    continue
                
                # 댓글 수 제거 (예: [3])
                title = re.sub(r'\[\d+\]$', '', title).strip()
                
                # URL 구성
                href = title_link.get('href')
                if href.startswith('/'):
                    detail_url = self.base_url + href
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
                    
                    # 첨부파일 존재 여부 확인
                    if title_cell:
                        # 이미지 아이콘 확인
                        img_tags = title_cell.find_all('img')
                        for img in img_tags:
                            src = img.get('src', '')
                            alt = img.get('alt', '')
                            if 'file' in src.lower() or 'attach' in src.lower() or 'file' in alt.lower():
                                announcement['has_attachment'] = True
                                break
                    
                    # 작성자 (이름 셀)
                    if len(cells) > 2:
                        writer_cell = cells[2]
                        writer = writer_cell.get_text(strip=True)
                        if writer:
                            announcement['writer'] = writer
                    
                    # 작성일 (날짜 셀)
                    if len(cells) > 3:
                        date_cell = cells[3]
                        date = date_cell.get_text(strip=True)
                        if date and re.match(r'\d{4}-\d{2}-\d{2}', date):
                            announcement['date'] = date
                    
                    # 조회수 (마지막 셀)
                    if len(cells) > 4:
                        views_cell = cells[4]
                        views = views_cell.get_text(strip=True)
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
        
        # 본문 내용 추출
        try:
            content = self._extract_content(soup)
            result['content'] = content
        except Exception as e:
            logger.error(f"본문 추출 중 오류: {e}")
        
        # 첨부파일 추출
        try:
            attachments = self._extract_attachments(soup)
            result['attachments'] = attachments
        except Exception as e:
            logger.error(f"첨부파일 추출 중 오류: {e}")
        
        return result
    
    def _extract_content(self, soup: BeautifulSoup) -> str:
        """본문 내용 추출"""
        # 여러 방법으로 본문 추출 시도
        
        # 첫 번째 방법: 게시글 내용 영역 찾기
        content_areas = [
            soup.find('div', class_='board_content'),
            soup.find('div', class_='content'),
            soup.find('div', id='content'),
            soup.find('td', class_='content')
        ]
        
        for content_area in content_areas:
            if content_area:
                # 불필요한 요소 제거
                for unwanted in content_area.find_all(['script', 'style', 'nav', 'header', 'footer']):
                    unwanted.decompose()
                
                # HTML을 마크다운으로 변환
                content_html = str(content_area)
                content_md = self.h.handle(content_html)
                
                # 불필요한 공백 정리
                content_md = re.sub(r'\n\s*\n', '\n\n', content_md)
                content_md = content_md.strip()
                
                if len(content_md) > 50:  # 충분한 내용이 있는 경우
                    logger.debug(f"본문 추출 완료: {len(content_md)} chars")
                    return content_md
        
        # 두 번째 방법: 테이블 기반 본문 찾기
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                for cell in cells:
                    if len(cell.get_text(strip=True)) > 100:  # 충분한 텍스트가 있는 셀
                        content_html = str(cell)
                        content_md = self.h.handle(content_html)
                        content_md = re.sub(r'\n\s*\n', '\n\n', content_md)
                        content_md = content_md.strip()
                        
                        if len(content_md) > 50:
                            logger.debug(f"테이블에서 본문 추출: {len(content_md)} chars")
                            return content_md
        
        # 세 번째 방법: 전체 페이지에서 본문 찾기
        paragraphs = soup.find_all('p')
        if paragraphs:
            content_parts = []
            for p in paragraphs:
                text = p.get_text(strip=True)
                if text and len(text) > 10:
                    content_parts.append(text)
            
            if content_parts:
                content = '\n\n'.join(content_parts)
                logger.debug(f"단락에서 본문 추출: {len(content)} chars")
                return content
        
        logger.warning("본문 내용을 찾을 수 없습니다")
        return ""
    
    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """첨부파일 링크 추출"""
        attachments = []
        
        # JavaScript 함수 호출 패턴으로 첨부파일 찾기
        # 패턴: javascript:file_download(숫자)
        js_links = soup.find_all('a', href=re.compile(r'javascript:file_download\(\d+\)'))
        
        for link in js_links:
            try:
                href = link.get('href', '')
                filename = link.get_text(strip=True)
                
                # JavaScript에서 파일 번호 추출
                file_no_match = re.search(r'file_download\((\d+)\)', href)
                if not file_no_match:
                    continue
                
                file_no = file_no_match.group(1)
                
                # 파일명에서 크기 정보 제거
                # 예: "[붙임1]파일명.pdf [File size:234KB]" -> "파일명.pdf"
                filename_cleaned = re.sub(r'^\[.*?\]', '', filename)  # 앞의 [붙임1] 제거
                filename_cleaned = re.sub(r'\s*\[File size:.*?\]$', '', filename_cleaned)  # 뒤의 크기 정보 제거
                filename_cleaned = filename_cleaned.strip()
                
                if not filename_cleaned:
                    filename_cleaned = f"attachment_{file_no}"
                
                # 현재 페이지 URL에서 board_idx 추출
                current_url = soup.find('meta', attrs={'property': 'og:url'})
                board_idx = None
                
                if current_url:
                    url_content = current_url.get('content', '')
                    if 'bbs/notice/' in url_content:
                        board_idx = url_content.split('bbs/notice/')[-1]
                
                # 대안: 페이지 내에서 board_idx 찾기
                if not board_idx:
                    scripts = soup.find_all('script')
                    for script in scripts:
                        script_text = script.get_text()
                        if 'board_idx' in script_text:
                            idx_match = re.search(r'board_idx[\'"]?\s*[:=]\s*[\'"]?(\d+)', script_text)
                            if idx_match:
                                board_idx = idx_match.group(1)
                                break
                
                if board_idx:
                    # 실제 다운로드 URL 구성
                    download_url = f"{self.base_url}/bbs_shop/file_download.php?board_code={self.board_code}&board_idx={board_idx}&sel_no={file_no}"
                    
                    attachment = {
                        'filename': filename_cleaned,
                        'url': download_url,
                        'file_no': file_no,
                        'board_idx': board_idx
                    }
                    
                    attachments.append(attachment)
                    logger.debug(f"첨부파일 발견: {filename_cleaned}")
                
            except Exception as e:
                logger.error(f"첨부파일 링크 파싱 중 오류: {e}")
                continue
        
        # 추가 패턴: 직접 다운로드 링크
        direct_links = soup.find_all('a', href=re.compile(r'file_download\.php'))
        
        for link in direct_links:
            try:
                href = link.get('href', '')
                filename = link.get_text(strip=True)
                
                # 파일명 정리
                filename_cleaned = re.sub(r'^\[.*?\]', '', filename)
                filename_cleaned = re.sub(r'\s*\[File size:.*?\]$', '', filename_cleaned)
                filename_cleaned = filename_cleaned.strip()
                
                if not filename_cleaned:
                    continue
                
                # 절대 URL 구성
                if href.startswith('/'):
                    download_url = self.base_url + href
                else:
                    download_url = urljoin(self.base_url, href)
                
                # 파라미터 추출
                parsed_url = urlparse(download_url)
                params = parse_qs(parsed_url.query)
                
                attachment = {
                    'filename': filename_cleaned,
                    'url': download_url,
                    'file_no': params.get('sel_no', ['0'])[0],
                    'board_idx': params.get('board_idx', [''])[0]
                }
                
                attachments.append(attachment)
                logger.debug(f"직접 링크 첨부파일 발견: {filename_cleaned}")
                
            except Exception as e:
                logger.error(f"직접 링크 파싱 중 오류: {e}")
                continue
        
        logger.info(f"총 {len(attachments)}개 첨부파일 추출")
        return attachments
    
    def download_file(self, url: str, save_path: str, attachment_info: Dict[str, Any] = None) -> bool:
        """파일 다운로드 - GEEA 사이트 특화"""
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
            logging.FileHandler('geea_scraper.log', encoding='utf-8')
        ]
    )
    
    logger.info("GEEA 스크래퍼 시작")
    
    # 출력 디렉토리 설정
    output_dir = "output/geea"
    if os.path.exists(output_dir):
        import shutil
        shutil.rmtree(output_dir)
        logger.info(f"기존 출력 디렉토리 삭제: {output_dir}")
    
    # 스크래퍼 실행
    scraper = EnhancedGeeaScraper()
    
    try:
        # 3페이지 수집
        scraper.scrape_pages(max_pages=3, output_base='output/geea')
        logger.info("GEEA 스크래퍼 완료")
        
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