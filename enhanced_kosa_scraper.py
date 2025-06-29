#!/usr/bin/env python3
"""
Enhanced KOSA (한국철강협회) 스크래퍼

KOSA 뉴스 게시판에서 공고를 수집하는 스크래퍼입니다.
표준 HTML 테이블 구조를 사용하므로 StandardTableScraper를 기반으로 합니다.

URL: https://www.kosa.or.kr/news/sIssue_list_2013.jsp?page=&category=&keyword=
"""

import os
import re
import time
import logging
from typing import List, Dict, Any
from urllib.parse import urljoin, unquote, quote
from bs4 import BeautifulSoup
from enhanced_base_scraper import StandardTableScraper

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedKosaScraper(StandardTableScraper):
    """KOSA 전용 Enhanced 스크래퍼 - StandardTableScraper 기반"""
    
    def __init__(self):
        super().__init__()
        
        # KOSA 사이트 설정
        self.base_url = "https://www.kosa.or.kr"
        self.list_url = "https://www.kosa.or.kr/news/sIssue_list_2013.jsp"
        
        # 사이트별 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 2
        
    def get_list_url(self, page_num: int) -> str:
        """페이지별 URL 생성 - KOSA는 page 파라미터 사용"""
        if page_num == 1:
            return f"{self.list_url}?page=&category=&keyword="
        else:
            return f"{self.list_url}?page={page_num}&category=&keyword="
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱 - KOSA 테이블 구조"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # KOSA 테이블 찾기 - class="listTypeA mb"
        table = soup.find('table', class_='listTypeA')
        if not table:
            logger.warning("KOSA 테이블을 찾을 수 없습니다")
            return announcements
        
        tbody = table.find('tbody')
        if not tbody:
            logger.warning("테이블 tbody를 찾을 수 없습니다")
            return announcements
        
        rows = tbody.find_all('tr')
        logger.info(f"KOSA 테이블에서 {len(rows)}개 행 발견")
        
        for i, row in enumerate(rows):
            try:
                cells = row.find_all('td')
                if len(cells) < 5:  # 번호, 제목, 파일, 날짜, 조회
                    continue
                
                # 컬럼 파싱: 번호, 제목, 파일, 날짜, 조회
                number_cell = cells[0]
                title_cell = cells[1]
                file_cell = cells[2]
                date_cell = cells[3]
                views_cell = cells[4]
                
                # 번호
                number = number_cell.get_text(strip=True)
                
                # 제목 및 상세 페이지 링크
                title_link = title_cell.find('a')
                if not title_link:
                    continue
                
                title = title_link.get_text(strip=True)
                href = title_link.get('href', '')
                
                if href:
                    # KOSA 상세 페이지는 /news/ 경로 필요
                    if href.startswith('sIssue_view_2013.jsp'):
                        detail_url = f"{self.base_url}/news/{href}"
                    else:
                        detail_url = urljoin(self.base_url, href)
                else:
                    continue
                
                # 파일 정보 확인
                has_attachments = False
                file_imgs = file_cell.find_all('img')
                if file_imgs:
                    for img in file_imgs:
                        alt_text = img.get('alt', '').lower()
                        if any(keyword in alt_text for keyword in ['파일', 'pdf', '한글', '이미지']):
                            has_attachments = True
                            break
                
                # 날짜
                date = date_cell.get_text(strip=True)
                
                # 조회수
                views = views_cell.get_text(strip=True)
                
                announcement = {
                    'number': number,
                    'title': title,
                    'author': 'KOSA',
                    'date': date,
                    'views': views,
                    'url': detail_url,
                    'has_attachments': has_attachments
                }
                
                announcements.append(announcement)
                logger.debug(f"공고 추가: [{number}] {title}")
                
            except Exception as e:
                logger.error(f"행 {i} 파싱 중 오류: {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
        return announcements
    
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱 - KOSA 구조에 최적화"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출
        title_selectors = [
            'h2',  # 주요 제목
            '.viewTitle h2',
            '.board-title',
            'h1'
        ]
        
        title = "제목 없음"
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                potential_title = title_elem.get_text(strip=True)
                if potential_title and len(potential_title) > 5:
                    title = potential_title
                    break
        
        # 본문 내용 추출
        content_text = self._extract_main_content(soup)
        
        # 메타 정보 추출
        meta_info = self._extract_meta_info(soup)
        
        # 첨부파일 추출
        attachments = self._extract_attachments(soup)
        
        # 마크다운 형식으로 조합
        markdown_content = f"# {title}\n\n"
        
        if meta_info:
            for key, value in meta_info.items():
                markdown_content += f"**{key}**: {value}\n"
            markdown_content += "\n"
        
        markdown_content += "---\n\n"
        markdown_content += content_text
        
        return {
            'content': markdown_content,
            'attachments': attachments
        }
    
    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """KOSA 사이트에서 본문 내용 추출"""
        
        # 1. 불필요한 요소들 제거
        unwanted_selectors = [
            'nav', 'header', 'footer', '.nav', '.navigation',
            '.menu', '.sidebar', '.breadcrumb',
            'script', 'style', '.ads', '.advertisement'
        ]
        
        for selector in unwanted_selectors:
            for elem in soup.select(selector):
                elem.decompose()
        
        # 2. KOSA 특화 콘텐츠 선택자
        content_selectors = [
            '.viewContent',      # 뷰 콘텐츠 영역
            '.board_view',       # 게시글 뷰 영역
            '.content_area',     # 콘텐츠 영역
            '.view_content',     # 뷰 콘텐츠
            '.detail_content',   # 상세 콘텐츠
            'main',              # main 태그
            '[role="main"]'      # main 역할
        ]
        
        content_elem = None
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                logger.debug(f"콘텐츠 선택자 사용: {selector}")
                break
        
        if content_elem:
            # 추가 불필요한 요소 제거
            for unwanted in content_elem.select('.btn, .button, .pagination, .paging'):
                unwanted.decompose()
            
            # 본문 텍스트 추출
            content_text = self.simple_html_to_text(content_elem)
        else:
            # 백업 방법: div나 p 태그에서 가장 긴 텍스트 찾기
            content_candidates = []
            
            for elem in soup.find_all(['div', 'p', 'article', 'section']):
                text = elem.get_text(strip=True)
                if len(text) > 100:  # 최소 길이 조건
                    content_candidates.append(text)
            
            # 가장 긴 텍스트를 본문으로 선택
            if content_candidates:
                content_text = max(content_candidates, key=len)
            else:
                content_text = "본문 내용을 찾을 수 없습니다."
        
        return content_text.strip()
    
    def _extract_meta_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """KOSA 사이트에서 메타 정보 추출"""
        meta_info = {}
        
        try:
            # KOSA 상세 페이지의 메타 정보는 리스트 형태로 표시됨
            meta_lists = soup.find_all('ul')
            
            for ul in meta_lists:
                items = ul.find_all('li')
                for item in items:
                    text = item.get_text(strip=True)
                    
                    # 작성자 정보
                    if '작성자' in text:
                        meta_info['작성자'] = text.replace('작성자', '').strip()
                    
                    # 등록일 정보
                    elif '등록일' in text or '작성일' in text:
                        date_text = text.replace('등록일', '').replace('작성일', '').strip()
                        meta_info['등록일'] = date_text
                    
                    # 조회수 정보
                    elif '조회수' in text or '조회' in text:
                        views_text = text.replace('조회수', '').replace('조회', '').strip()
                        meta_info['조회수'] = views_text
            
        except Exception as e:
            logger.debug(f"메타 정보 추출 중 오류: {e}")
        
        return meta_info
    
    def simple_html_to_text(self, element) -> str:
        """HTML 요소를 간단한 텍스트로 변환"""
        text = element.get_text(separator='\n\n', strip=True)
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text
    
    def _extract_meta_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """KOSA 사이트에서 메타 정보 추출"""
        meta_info = {}
        
        # 페이지 텍스트에서 날짜 패턴 찾기
        page_text = soup.get_text()
        date_match = re.search(r'(\d{4}[-./]\d{2}[-./]\d{2})', page_text)
        if date_match:
            meta_info['작성일'] = date_match.group(1)
        
        # 조회수 패턴 찾기
        views_match = re.search(r'조회수?\s*:?\s*(\d+)', page_text)
        if views_match:
            meta_info['조회수'] = views_match.group(1)
        
        # 작성자 정보 (KOSA 기본값)
        meta_info['작성자'] = 'KOSA'
        
        return meta_info
    
    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """KOSA 구조에서 첨부파일 정보 추출"""
        attachments = []
        
        # KOSA 파일 다운로드 링크 패턴: /FileDownload?name=...&dir=DIR_BOARD
        download_links = soup.find_all('a', href=lambda x: x and '/FileDownload' in x)
        
        for link in download_links:
            try:
                href = link.get('href', '')
                if '/FileDownload' not in href:
                    continue
                
                # 파일명 추출 (URL에서 name 파라미터)
                filename = self._extract_filename_from_url(href)
                if not filename:
                    filename = f"attachment_{len(attachments)+1}"
                
                # 전체 URL 구성
                file_url = urljoin(self.base_url, href)
                
                # 파일 타입 확인
                file_type = self._determine_file_type(filename, link)
                
                attachment = {
                    'filename': filename,
                    'url': file_url,
                    'type': file_type,
                    'download_method': 'direct'
                }
                
                attachments.append(attachment)
                logger.debug(f"첨부파일 발견: {filename}")
                
            except Exception as e:
                logger.error(f"첨부파일 처리 중 오류: {e}")
                continue
        
        logger.info(f"첨부파일 {len(attachments)}개 발견")
        return attachments
    
    def _extract_filename_from_url(self, url: str) -> str:
        """URL에서 파일명 추출 및 디코딩"""
        try:
            # name 파라미터 추출
            import re
            from urllib.parse import parse_qs, urlparse
            
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            
            if 'name' in params:
                encoded_name = params['name'][0]
                
                # URL 디코딩 시도
                try:
                    # UTF-8 디코딩 시도
                    decoded_name = unquote(encoded_name, encoding='utf-8')
                    return decoded_name
                except:
                    try:
                        # EUC-KR 디코딩 시도
                        decoded_name = unquote(encoded_name, encoding='euc-kr')
                        return decoded_name
                    except:
                        # 디코딩 실패 시 원본 반환
                        return encoded_name
            
        except Exception as e:
            logger.debug(f"파일명 추출 실패: {e}")
        
        return None
    
    def _determine_file_type(self, filename: str, link_elem) -> str:
        """파일 타입 결정"""
        if not filename:
            return 'unknown'
        
        filename_lower = filename.lower()
        
        if filename_lower.endswith('.pdf'):
            return 'pdf'
        elif filename_lower.endswith('.hwp'):
            return 'hwp'
        elif filename_lower.endswith(('.doc', '.docx')):
            return 'doc'
        elif filename_lower.endswith(('.xls', '.xlsx')):
            return 'excel'
        elif filename_lower.endswith(('.jpg', '.jpeg', '.png', '.gif')):
            return 'image'
        elif filename_lower.endswith('.zip'):
            return 'zip'
        else:
            return 'unknown'
    
    def download_file(self, file_url: str, save_path: str, attachment_info: dict = None) -> bool:
        """파일 다운로드 - KOSA 특화 처리"""
        try:
            logger.info(f"파일 다운로드 시작: {file_url}")
            
            # KOSA 사이트는 세션 유지가 필요할 수 있음
            response = self.session.get(file_url, stream=True, timeout=self.timeout)
            response.raise_for_status()
            
            # Content-Disposition에서 파일명 추출 시도
            content_disposition = response.headers.get('Content-Disposition', '')
            if content_disposition:
                extracted_filename = self._extract_filename_from_disposition(content_disposition)
                if extracted_filename:
                    # 디렉토리는 유지하고 파일명만 변경
                    directory = os.path.dirname(save_path)
                    save_path = os.path.join(directory, self.sanitize_filename(extracted_filename))
            
            # 파일 저장
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(save_path)
            logger.info(f"파일 다운로드 완료: {os.path.basename(save_path)} ({file_size} bytes)")
            
            return True
            
        except Exception as e:
            logger.error(f"파일 다운로드 실패: {e}")
            return False
    
    def _extract_filename_from_disposition(self, content_disposition: str) -> str:
        """Content-Disposition 헤더에서 파일명 추출"""
        try:
            # RFC 5987 형식 처리 (filename*=UTF-8''filename)
            rfc5987_match = re.search(r"filename\*=([^']*)'([^']*)'(.+)", content_disposition)
            if rfc5987_match:
                encoding, lang, filename = rfc5987_match.groups()
                try:
                    filename = unquote(filename, encoding=encoding or 'utf-8')
                    return filename
                except:
                    pass
            
            # 일반 filename 파라미터 처리
            filename_match = re.search(r'filename[^;=\n]*=([\'"]*)(.*?)\1', content_disposition)
            if filename_match:
                filename = filename_match.group(2)
                
                # 다양한 인코딩 시도
                for encoding in ['utf-8', 'euc-kr', 'cp949']:
                    try:
                        if encoding == 'utf-8':
                            decoded = filename.encode('latin-1').decode('utf-8')
                        else:
                            decoded = filename.encode('latin-1').decode(encoding)
                        
                        if decoded and not decoded.isspace():
                            return decoded.replace('+', ' ').strip()
                    except:
                        continue
                        
                return filename.replace('+', ' ')
                
        except Exception as e:
            logger.debug(f"파일명 추출 실패: {e}")
            
        return None


def main():
    """테스트 실행"""
    output_dir = "output/kosa"
    os.makedirs(output_dir, exist_ok=True)
    
    scraper = EnhancedKosaScraper()
    
    try:
        result = scraper.scrape_pages(max_pages=3, output_base=output_dir)
        print(f"✅ KOSA 스크래핑 완료!")
        
        # scrape_pages 메서드가 dict를 반환하는지 확인
        if isinstance(result, dict):
            print(f"수집된 공고: {result.get('total_announcements', 0)}개")
            print(f"다운로드된 파일: {result.get('total_files', 0)}개")
            print(f"성공률: {result.get('success_rate', 0):.1f}%")
        else:
            print(f"스크래핑 결과: {result}")
        
    except Exception as e:
        print(f"❌ 스크래핑 실패: {e}")
        raise


if __name__ == "__main__":
    main()