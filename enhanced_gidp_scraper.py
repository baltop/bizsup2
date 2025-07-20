# -*- coding: utf-8 -*-
"""
GIDP (강원디자인진흥원) 스크래퍼 - GET 방식 페이지네이션 지원
"""

import re
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote, parse_qs, urlparse
from typing import Dict, List, Any, Optional
import logging
from enhanced_base_scraper import EnhancedBaseScraper

logger = logging.getLogger(__name__)

class EnhancedGidpScraper(EnhancedBaseScraper):
    """GIDP 강원디자인진흥원 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.gidp.kr"
        self.list_url = "https://www.gidp.kr/gidp/notice/notification"
        
        # SSL 인증서 검증 비활성화 - 완전한 방법
        import urllib3
        import ssl
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # 세션 설정에서 SSL 검증 완전 비활성화
        self.verify_ssl = False
        
        # 어댑터 설정으로 SSL 완전 비활성화
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        class SSLAdapter(HTTPAdapter):
            def init_poolmanager(self, *args, **kwargs):
                kwargs['ssl_context'] = ssl.create_default_context()
                kwargs['ssl_context'].check_hostname = False
                kwargs['ssl_context'].verify_mode = ssl.CERT_NONE
                return super().init_poolmanager(*args, **kwargs)
        
        self.session.mount('https://', SSLAdapter())
        
        # 사이트별 헤더 설정
        self.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'max-age=0',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        self.session.headers.update(self.headers)
        
        # 성능 최적화
        self.delay_between_requests = 1.0
        self.delay_between_pages = 1.0
        
    def get_list_url(self, page_num: int) -> str:
        """페이지별 목록 URL 생성"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}?pageIndex={page_num}"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱 - 테이블 기반"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # HTML 내용 디버깅
        logger.debug(f"HTML 길이: {len(html_content)} characters")
        
        # GIDP 사이트의 목록 테이블 찾기
        table = soup.find('table', attrs={'caption': '게시판 제목'})
        if not table:
            # 대안: 클래스로 찾기
            table = soup.find('table', class_='게시판 제목')
            if not table:
                # 모든 테이블 확인
                all_tables = soup.find_all('table')
                logger.debug(f"페이지에 있는 테이블 개수: {len(all_tables)}")
                
                for i, t in enumerate(all_tables):
                    caption = t.find('caption')
                    if caption and ('게시판' in caption.get_text() or '제목' in caption.get_text()):
                        table = t
                        logger.info(f"테이블 {i} 사용 (caption: {caption.get_text()})")
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
            if rows and (rows[0].find('th') or any(keyword in rows[0].get_text() for keyword in ['번호', '제목', '구분'])):
                rows = rows[1:]
            logger.info(f"table에서 {len(rows)}개 행 발견 (헤더 제외)")
        
        for row_index, row in enumerate(rows):
            try:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 6:  # 번호, 구분, 제목, 상태, 작성자, 등록일, 조회수
                    logger.debug(f"행 {row_index}: 셀 수 부족 ({len(cells)}개)")
                    continue
                
                # 제목 셀에서 링크 찾기 (보통 3번째 셀)
                title_cell = None
                title_link = None
                
                for i, cell in enumerate(cells):
                    link = cell.find('a')
                    if link and link.get('href'):
                        href = link.get('href')
                        if 'articleSeq=' in href:
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
                    if len(cells) > 0:
                        number_cell = cells[0]
                        number = self.process_notice_detection(number_cell, row_index)
                        if number:
                            announcement['number'] = number
                    
                    # 구분 (두 번째 셀)
                    if len(cells) > 1:
                        category_cell = cells[1]
                        category = category_cell.get_text(strip=True)
                        if category:
                            announcement['category'] = category
                    
                    # 상태 (네 번째 셀)
                    if len(cells) > 3:
                        status_cell = cells[3]
                        status = status_cell.get_text(strip=True)
                        if status:
                            announcement['status'] = status
                    
                    # 작성자 (다섯 번째 셀)
                    if len(cells) > 4:
                        writer_cell = cells[4]
                        writer = writer_cell.get_text(strip=True)
                        if writer:
                            announcement['writer'] = writer
                    
                    # 등록일 (여섯 번째 셀)
                    if len(cells) > 5:
                        date_cell = cells[5]
                        date = date_cell.get_text(strip=True)
                        if date and re.match(r'\d{4}-\d{2}-\d{2}', date):
                            announcement['date'] = date
                    
                    # 조회수 (일곱 번째 셀)
                    if len(cells) > 6:
                        views_cell = cells[6]
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
        
        # 첫 번째 방법: 첨부파일 영역 이후의 내용 찾기
        content_parts = []
        
        # 첨부파일 영역 찾기
        attachment_found = False
        for element in soup.find_all(['div', 'p', 'span']):
            text = element.get_text(strip=True)
            if '첨부파일' in text:
                attachment_found = True
                continue
            
            # 첨부파일 영역 이후의 내용 수집
            if attachment_found and element.name == 'p':
                # 이미지가 포함된 경우
                if element.find('img'):
                    imgs = element.find_all('img')
                    for img in imgs:
                        src = img.get('src', '')
                        if src:
                            if src.startswith('/'):
                                img_url = self.base_url + src
                            else:
                                img_url = urljoin(self.base_url, src)
                            content_parts.append(f"![공고문]({img_url})")
                
                # 텍스트가 포함된 경우
                if text and len(text) > 10:
                    content_parts.append(text)
        
        if content_parts:
            content = '\n\n'.join(content_parts)
            logger.debug(f"첨부파일 이후 본문 추출: {len(content)} chars")
            return content
        
        # 두 번째 방법: 전체 페이지에서 본문 찾기
        # 메타데이터 영역 이후의 내용 찾기
        all_paragraphs = soup.find_all('p')
        for p in all_paragraphs:
            if len(p.get_text(strip=True)) > 20:
                # 이미지 포함 확인
                if p.find('img'):
                    imgs = p.find_all('img')
                    for img in imgs:
                        src = img.get('src', '')
                        if src:
                            if src.startswith('/'):
                                img_url = self.base_url + src
                            else:
                                img_url = urljoin(self.base_url, src)
                            content_parts.append(f"![공고문]({img_url})")
                
                # 텍스트 추가
                text = p.get_text(strip=True)
                if text and len(text) > 10:
                    content_parts.append(text)
        
        if content_parts:
            content = '\n\n'.join(content_parts)
            logger.debug(f"전체 페이지에서 본문 추출: {len(content)} chars")
            return content
        
        # 세 번째 방법: 전체 본문 영역 찾기
        main_content = soup.find('div', class_='content')
        if not main_content:
            main_content = soup.find('div', id='content')
        
        if main_content:
            # 불필요한 요소 제거
            for unwanted in main_content.find_all(['script', 'style', 'nav', 'header', 'footer']):
                unwanted.decompose()
            
            # HTML을 마크다운으로 변환
            content_html = str(main_content)
            content_md = self.h.handle(content_html)
            
            # 불필요한 공백 정리
            content_md = re.sub(r'\n\s*\n', '\n\n', content_md)
            content_md = content_md.strip()
            
            if len(content_md) > 50:
                logger.debug(f"메인 컨텐츠 영역에서 본문 추출: {len(content_md)} chars")
                return content_md
        
        logger.warning("본문 내용을 찾을 수 없습니다")
        return ""
    
    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """첨부파일 링크 추출"""
        attachments = []
        
        # 첨부파일 다운로드 링크 찾기
        # 패턴: /egf/ext/notify/article/download?fileSeq=N
        download_links = soup.find_all('a', href=re.compile(r'/egf/ext/notify/article/download'))
        
        for link in download_links:
            try:
                href = link.get('href', '')
                filename = link.get_text(strip=True)
                
                # 파일명이 비어있으면 건너뛰기
                if not filename:
                    continue
                
                # 파일 시퀀스 번호 추출
                parsed_url = urlparse(href)
                params = parse_qs(parsed_url.query)
                file_seq = params.get('fileSeq', [''])[0]
                
                if not file_seq:
                    continue
                
                # 절대 URL 구성
                if href.startswith('/'):
                    download_url = self.base_url + href
                else:
                    download_url = urljoin(self.base_url, href)
                
                attachment = {
                    'filename': filename,
                    'url': download_url,
                    'file_seq': file_seq
                }
                
                attachments.append(attachment)
                logger.debug(f"첨부파일 발견: {filename}")
                
            except Exception as e:
                logger.error(f"첨부파일 링크 파싱 중 오류: {e}")
                continue
        
        logger.info(f"총 {len(attachments)}개 첨부파일 추출")
        return attachments
    
    def download_file(self, url: str, save_path: str, attachment_info: Dict[str, Any] = None) -> bool:
        """파일 다운로드 - GIDP 사이트 특화"""
        try:
            # Referer 헤더 설정
            download_headers = self.headers.copy()
            download_headers['Referer'] = self.base_url
            
            # 파일 다운로드 요청
            response = self.session.get(url, headers=download_headers, stream=True, timeout=self.timeout, verify=False)
            
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
            logging.FileHandler('gidp_scraper.log', encoding='utf-8')
        ]
    )
    
    logger.info("GIDP 스크래퍼 시작")
    
    # 출력 디렉토리 설정
    output_dir = "output/gidp"
    if os.path.exists(output_dir):
        import shutil
        shutil.rmtree(output_dir)
        logger.info(f"기존 출력 디렉토리 삭제: {output_dir}")
    
    # 스크래퍼 실행
    scraper = EnhancedGidpScraper()
    
    try:
        # 3페이지 수집
        scraper.scrape_pages(max_pages=3, output_base='output/gidp')
        logger.info("GIDP 스크래퍼 완료")
        
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