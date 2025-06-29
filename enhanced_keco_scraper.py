#!/usr/bin/env python3
"""
Enhanced KECO (한국환경공단) 스크래퍼

KECO 사업공고 게시판에서 공고를 수집하는 스크래퍼입니다.
표준 HTML 테이블 구조와 JavaScript 기반 네비게이션을 처리합니다.

URL: https://www.keco.or.kr/web/lay1/bbs/S1T10C108/A/18/list.do
"""

import os
import re
import time
import logging
from typing import List, Dict, Any
from urllib.parse import urljoin, unquote
from bs4 import BeautifulSoup
from enhanced_base_scraper import StandardTableScraper

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedKecoScraper(StandardTableScraper):
    """KECO 전용 Enhanced 스크래퍼 - StandardTableScraper 기반"""
    
    def __init__(self):
        super().__init__()
        
        # KECO 사이트 설정
        self.base_url = "https://www.keco.or.kr"
        self.list_url = "https://www.keco.or.kr/web/lay1/bbs/S1T10C108/A/18/list.do"
        
        # 사이트별 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 2
        
    def get_list_url(self, page_num: int) -> str:
        """페이지별 URL 생성 - KECO는 GET 파라미터 사용"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}?rows=10&cpage={page_num}"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱 - KECO 테이블 구조"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # KECO 테이블 찾기
        table = soup.find('table')
        if not table:
            logger.warning("KECO 테이블을 찾을 수 없습니다")
            return announcements
        
        tbody = table.find('tbody')
        if not tbody:
            logger.warning("테이블 tbody를 찾을 수 없습니다")
            return announcements
        
        rows = tbody.find_all('tr')
        logger.info(f"KECO 테이블에서 {len(rows)}개 행 발견")
        
        for i, row in enumerate(rows):
            try:
                cells = row.find_all('td')
                if len(cells) < 5:  # 번호, 제목, 작성자, 파일, 작성일
                    continue
                
                # 컬럼 파싱: 번호, 제목, 작성자, 파일, 작성일
                number_cell = cells[0]
                title_cell = cells[1]
                author_cell = cells[2]
                file_cell = cells[3]
                date_cell = cells[4]
                
                # 번호 처리 (공지 vs 번호)
                number, is_notice = self._process_notice_number(number_cell)
                
                # 제목 및 상세 페이지 링크
                title_link = title_cell.find('a')
                if not title_link:
                    continue
                
                title = title_link.get_text(strip=True)
                onclick = title_link.get('onclick', '')
                
                # JavaScript에서 상세 페이지 URL 추출
                detail_url = self._extract_detail_url(onclick)
                if not detail_url:
                    continue
                
                # 작성자
                author = author_cell.get_text(strip=True)
                
                # 첨부파일 정보 확인
                has_attachments = self._check_attachments(file_cell)
                
                # 작성일
                date = date_cell.get_text(strip=True)
                
                announcement = {
                    'number': number,
                    'title': title,
                    'author': author,
                    'date': date,
                    'url': detail_url,
                    'has_attachments': has_attachments,
                    'is_notice': is_notice
                }
                
                announcements.append(announcement)
                logger.debug(f"공고 추가: [{number}] {title}")
                
            except Exception as e:
                logger.error(f"행 {i} 파싱 중 오류: {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
        return announcements
    
    def _process_notice_number(self, number_cell) -> tuple:
        """번호 셀에서 공지 여부 및 번호 추출"""
        # 공지 이미지 확인
        notice_img = number_cell.find('img', alt='공지')
        if notice_img:
            return ("공지", True)
        
        # 일반 번호
        number_text = number_cell.get_text(strip=True)
        if number_text:
            return (number_text, False)
        
        return ("", False)
    
    def _extract_detail_url(self, onclick: str) -> str:
        """JavaScript onclick에서 상세 페이지 URL 추출"""
        try:
            # location.href='./view.do?...' 패턴 매칭
            pattern = r"location\.href='([^']+)'"
            match = re.search(pattern, onclick)
            if match:
                relative_url = match.group(1)
                # 상대 경로를 절대 경로로 변환
                if relative_url.startswith('./'):
                    relative_url = relative_url[2:]  # './' 제거
                    return f"{self.base_url}/web/lay1/bbs/S1T10C108/A/18/{relative_url}"
                else:
                    return urljoin(self.base_url, relative_url)
        except Exception as e:
            logger.debug(f"상세 페이지 URL 추출 실패: {e}")
        
        return None
    
    def _check_attachments(self, file_cell) -> bool:
        """첨부파일 존재 여부 확인"""
        # file_box 클래스가 있으면 첨부파일 존재
        file_box = file_cell.find('div', class_='file_box')
        if file_box:
            return True
        
        # 첨부파일 이미지가 있으면 첨부파일 존재
        file_img = file_cell.find('img', alt='첨부파일')
        if file_img:
            return True
        
        return False
    
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱 - KECO 구조에 최적화"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출
        title_selectors = [
            '.view_top h3',
            '.board_view_title',
            '.view_title',
            'h1',
            'h2',
            'h3'
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
        """KECO 사이트에서 본문 내용 추출"""
        
        # 1. 불필요한 요소들 제거
        unwanted_selectors = [
            'nav', 'header', 'footer', '.nav', '.navigation',
            '.menu', '.sidebar', '.breadcrumb',
            'script', 'style', '.ads', '.advertisement',
            '.view_top', '.view_info', '.board_btn'
        ]
        
        for selector in unwanted_selectors:
            for elem in soup.select(selector):
                elem.decompose()
        
        # 2. KECO 특화 콘텐츠 선택자
        content_selectors = [
            '.view_con',           # 뷰 콘텐츠
            '.board_view_content', # 게시글 본문
            '.view_content',       # 뷰 콘텐츠
            '.content_area',       # 콘텐츠 영역
            '.board_content',      # 게시판 콘텐츠
            '.detail_content',     # 상세 콘텐츠
            'main',                # main 태그
            '[role="main"]'        # main 역할
        ]
        
        content_elem = None
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                logger.debug(f"콘텐츠 선택자 사용: {selector}")
                break
        
        if content_elem:
            # 추가 불필요한 요소 제거
            for unwanted in content_elem.select('.btn, .button, .pagination, .paging, .file_list'):
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
    
    def simple_html_to_text(self, element) -> str:
        """HTML 요소를 간단한 텍스트로 변환"""
        text = element.get_text(separator='\n\n', strip=True)
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text
    
    def _extract_meta_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """KECO 사이트에서 메타 정보 추출"""
        meta_info = {}
        
        try:
            # KECO 상세 페이지의 메타 정보는 view_info 영역에 있음
            view_info = soup.find('div', class_='view_info')
            if view_info:
                info_items = view_info.find_all(['dt', 'dd', 'span', 'strong'])
                
                for item in info_items:
                    text = item.get_text(strip=True)
                    
                    # 작성자 정보
                    if '작성자' in text or '등록자' in text:
                        meta_info['작성자'] = text.replace('작성자', '').replace('등록자', '').strip()
                    
                    # 등록일 정보
                    elif '등록일' in text or '작성일' in text:
                        date_text = text.replace('등록일', '').replace('작성일', '').strip()
                        meta_info['등록일'] = date_text
                    
                    # 조회수 정보
                    elif '조회수' in text or '조회' in text:
                        views_text = text.replace('조회수', '').replace('조회', '').strip()
                        meta_info['조회수'] = views_text
            
            # 백업 방법: 페이지 텍스트에서 패턴 찾기
            if not meta_info:
                page_text = soup.get_text()
                
                # 날짜 패턴 찾기
                date_match = re.search(r'(\d{4}[-./]\d{2}[-./]\d{2})', page_text)
                if date_match:
                    meta_info['작성일'] = date_match.group(1)
                
                # 조회수 패턴 찾기
                views_match = re.search(r'조회수?\s*:?\s*(\d+)', page_text)
                if views_match:
                    meta_info['조회수'] = views_match.group(1)
                
                # 작성자 정보 (KECO 기본값)
                meta_info['작성자'] = 'KECO'
        
        except Exception as e:
            logger.debug(f"메타 정보 추출 중 오류: {e}")
        
        return meta_info
    
    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """KECO 구조에서 첨부파일 정보 추출"""
        attachments = []
        
        # KECO 파일 다운로드 링크 패턴: /download.do?uuid=...
        download_links = soup.find_all('a', href=lambda x: x and '/download.do?uuid=' in x)
        
        for link in download_links:
            try:
                href = link.get('href', '')
                if '/download.do?uuid=' not in href:
                    continue
                
                # 파일명 추출 (링크 텍스트에서)
                filename = link.get_text(strip=True)
                if not filename:
                    # href에서 UUID 추출하여 기본 파일명 생성
                    uuid_match = re.search(r'uuid=([^&]+)', href)
                    if uuid_match:
                        uuid = uuid_match.group(1)
                        filename = f"attachment_{uuid}"
                    else:
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
    
    def _determine_file_type(self, filename: str, link_elem) -> str:
        """파일 타입 결정"""
        if not filename:
            return 'unknown'
        
        filename_lower = filename.lower()
        
        if filename_lower.endswith('.pdf'):
            return 'pdf'
        elif filename_lower.endswith(('.hwp', '.hwpx')):
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
        """파일 다운로드 - KECO 특화 처리"""
        try:
            logger.info(f"파일 다운로드 시작: {file_url}")
            
            # KECO 사이트는 세션 유지가 필요할 수 있음
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
            logger.info(f"파일 다운로드 완료: {os.path.basename(save_path)} ({file_size:,} bytes)")
            
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
    output_dir = "output/keco"
    os.makedirs(output_dir, exist_ok=True)
    
    scraper = EnhancedKecoScraper()
    
    try:
        result = scraper.scrape_pages(max_pages=3, output_base=output_dir)
        print(f"✅ KECO 스크래핑 완료!")
        
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