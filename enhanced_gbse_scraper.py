# -*- coding: utf-8 -*-
"""
GBSE (경상북도사회적경제지원센터) 스크래퍼 - GET 방식 Base64 인코딩 파라미터 지원
"""

import re
import base64
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote, unquote
from typing import Dict, List, Any, Optional
import logging
from enhanced_base_scraper import EnhancedBaseScraper

logger = logging.getLogger(__name__)

class EnhancedGbseScraper(EnhancedBaseScraper):
    """GBSE 경상북도사회적경제지원센터 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "http://www.gbse.or.kr"
        self.list_url = "http://www.gbse.or.kr/HOME/gbse/sub.htm"
        self.nav_code = "gbs1566979318"
        self.table_code = "ex_bbs_data_gbse"
        self.code = "N2JuNsnaMxmm"
        
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
        self.delay_between_requests = 1.0
        self.delay_between_pages = 1.0
        
    def _encode_mv_data(self, page_num: int) -> str:
        """mv_data 파라미터를 Base64로 인코딩"""
        start_page = (page_num - 1) * 10
        mv_data = f"startPage={start_page}&code={self.code}&nav_code={self.nav_code}&table={self.table_code}"
        
        # Base64 인코딩
        encoded_data = base64.b64encode(mv_data.encode('utf-8')).decode('utf-8')
        return encoded_data
    
    def _decode_mv_data(self, encoded_data: str) -> Dict[str, str]:
        """Base64로 인코딩된 mv_data를 디코딩"""
        try:
            decoded_data = base64.b64decode(encoded_data).decode('utf-8')
            params = {}
            for param in decoded_data.split('&'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    params[key] = value
            return params
        except Exception as e:
            logger.error(f"mv_data 디코딩 중 오류: {e}")
            return {}
    
    def get_list_url(self, page_num: int) -> str:
        """페이지별 목록 URL 생성"""
        if page_num == 1:
            return f"{self.list_url}?nav_code={self.nav_code}"
        else:
            mv_data = self._encode_mv_data(page_num)
            return f"{self.list_url}?mv_data={mv_data}"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱 - 테이블 기반"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # HTML 내용 디버깅
        logger.debug(f"HTML 길이: {len(html_content)} characters")
        
        # GBSE 사이트의 목록 테이블 찾기
        table = soup.find('table', attrs={'summary': lambda x: x and '게시물 목록' in x})
        if not table:
            # 대안 방법: 모든 테이블 확인
            all_tables = soup.find_all('table')
            logger.debug(f"페이지에 있는 테이블 개수: {len(all_tables)}")
            
            for i, t in enumerate(all_tables):
                summary = t.get('summary', '')
                if summary and ('게시물' in summary or '목록' in summary):
                    table = t
                    logger.info(f"테이블 {i} 사용 (summary: {summary})")
                    break
                    
        if not table:
            logger.warning("목록 테이블을 찾을 수 없습니다")
            # 마지막 대안: 첫 번째 테이블 사용
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
                if len(cells) < 5:  # 번호, 제목, 첨부, 작성자, 등록일, 조회수
                    logger.debug(f"행 {row_index}: 셀 수 부족 ({len(cells)}개)")
                    continue
                
                # 제목 셀 찾기 (보통 두 번째 셀)
                title_cell = None
                title_link = None
                
                for cell in cells:
                    link = cell.find('a')
                    if link and link.get('href') and 'mode=view' in link.get('href', ''):
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
                
                # 카테고리 태그 제거
                category_tag = title_cell.find('span', class_='category')
                if category_tag:
                    category = category_tag.get_text(strip=True)
                    title = title.replace(category, '').strip()
                
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
                    for cell in cells:
                        if cell.find('img', src=lambda x: x and 'file' in x.lower()):
                            announcement['has_attachment'] = True
                            break
                    
                    # 작성자 (작성자 셀 찾기)
                    writer_cell = None
                    for cell in cells:
                        cell_text = cell.get_text(strip=True)
                        if '경북' in cell_text or '센터' in cell_text:
                            writer_cell = cell
                            break
                    
                    if writer_cell:
                        announcement['writer'] = writer_cell.get_text(strip=True)
                    
                    # 등록일 (날짜 형식 셀 찾기)
                    date_cell = None
                    for cell in cells:
                        cell_text = cell.get_text(strip=True)
                        if re.match(r'\d{4}-\d{2}-\d{2}', cell_text):
                            date_cell = cell
                            break
                    
                    if date_cell:
                        announcement['date'] = date_cell.get_text(strip=True)
                    
                    # 조회수 (숫자만 있는 셀 찾기)
                    for cell in cells:
                        cell_text = cell.get_text(strip=True)
                        if cell_text.isdigit():
                            announcement['views'] = cell_text
                            break
                
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
        content_area = soup.find('div', class_='board_view')
        if not content_area:
            # 대안: 본문이 있을 만한 div 찾기
            content_divs = soup.find_all('div')
            for div in content_divs:
                if len(div.get_text(strip=True)) > 100:  # 충분한 텍스트가 있는 div
                    content_area = div
                    break
        
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
            
            logger.debug(f"본문 추출 완료: {len(content_md)} chars")
            return content_md
        
        # 두 번째 방법: 페이지 전체에서 본문 찾기
        paragraphs = soup.find_all('p')
        if paragraphs:
            content_parts = []
            for p in paragraphs:
                text = p.get_text(strip=True)
                if text and len(text) > 10:  # 의미있는 텍스트만
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
        
        # 첨부파일 다운로드 링크 찾기
        # 패턴 1: bbs_download.php 링크
        download_links = soup.find_all('a', href=re.compile(r'bbs_download\.php'))
        
        for link in download_links:
            try:
                href = link.get('href', '')
                filename = link.get_text(strip=True)
                
                # 절대 URL 구성
                if href.startswith('/'):
                    download_url = self.base_url + href
                elif href.startswith('../'):
                    download_url = self.base_url + href[2:]
                else:
                    download_url = urljoin(self.base_url, href)
                
                # 파일 정보 추출
                if 'mv_data=' in href:
                    mv_data_match = re.search(r'mv_data=([^&]+)', href)
                    if mv_data_match:
                        mv_data = mv_data_match.group(1)
                        attachment = {
                            'filename': filename,
                            'url': download_url,
                            'mv_data': mv_data
                        }
                        attachments.append(attachment)
                        logger.debug(f"첨부파일 발견: {filename}")
                
            except Exception as e:
                logger.error(f"첨부파일 링크 파싱 중 오류: {e}")
                continue
        
        # 패턴 2: JavaScript 팝업 방식
        popup_links = soup.find_all('a', href=re.compile(r'javascript:pdsWinOpen'))
        
        for link in popup_links:
            try:
                href = link.get('href', '')
                filename = link.get_text(strip=True)
                
                # JavaScript에서 mv_data 추출
                mv_data_match = re.search(r"pdsWinOpen\('([^']+)'\)", href)
                if mv_data_match:
                    mv_data = mv_data_match.group(1)
                    
                    # 다운로드 URL 구성
                    download_url = f"{self.base_url}/HOME/gbse/bbs/bbs_download.php?mv_data={mv_data}&download=h"
                    
                    attachment = {
                        'filename': filename,
                        'url': download_url,
                        'mv_data': mv_data
                    }
                    attachments.append(attachment)
                    logger.debug(f"첨부파일 발견 (팝업): {filename}")
                
            except Exception as e:
                logger.error(f"팝업 첨부파일 파싱 중 오류: {e}")
                continue
        
        logger.info(f"총 {len(attachments)}개 첨부파일 추출")
        return attachments
    
    def download_file(self, url: str, save_path: str, attachment_info: Dict[str, Any] = None) -> bool:
        """파일 다운로드 - GBSE 사이트 특화"""
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
            logging.FileHandler('gbse_scraper.log', encoding='utf-8')
        ]
    )
    
    logger.info("GBSE 스크래퍼 시작")
    
    # 출력 디렉토리 설정
    output_dir = "output/gbse"
    if os.path.exists(output_dir):
        import shutil
        shutil.rmtree(output_dir)
        logger.info(f"기존 출력 디렉토리 삭제: {output_dir}")
    
    # 스크래퍼 실행
    scraper = EnhancedGbseScraper()
    
    try:
        # 3페이지 수집
        scraper.scrape_pages(max_pages=3, output_base='output/gbse')
        logger.info("GBSE 스크래퍼 완료")
        
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