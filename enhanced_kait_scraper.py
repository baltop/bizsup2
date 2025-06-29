#!/usr/bin/env python3
"""
Enhanced KAIT (Korea Association for Information Technology) 스크래퍼

KAIT 공고 게시판에서 공고를 수집하는 스크래퍼입니다.
표준 HTML 테이블 구조를 사용하지만 POST 기반 페이지네이션을 사용합니다.

URL: https://www.kait.or.kr/user/MainBoardList.do?cateSeq=13&bId=101
"""

import os
import re
import time
import logging
from typing import List, Dict, Any
from urllib.parse import urljoin, unquote, parse_qs, urlparse
from bs4 import BeautifulSoup
from enhanced_base_scraper import StandardTableScraper

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedKaitScraper(StandardTableScraper):
    """KAIT 전용 Enhanced 스크래퍼 - StandardTableScraper 기반"""
    
    def __init__(self):
        super().__init__()
        
        # KAIT 사이트 설정
        self.base_url = "https://www.kait.or.kr"
        self.list_url = "https://www.kait.or.kr/user/MainBoardList.do"
        
        # 사이트별 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 2
        
        # KAIT 특화 파라미터
        self.cate_seq = "13"
        self.board_id = "101"
        
    def get_list_url(self, page_num: int) -> str:
        """페이지별 URL 생성 - KAIT는 GET 파라미터 기반 페이지네이션"""
        if page_num == 1:
            return f"{self.list_url}?cateSeq={self.cate_seq}&bId={self.board_id}"
        else:
            return f"{self.list_url}?cateSeq={self.cate_seq}&bId={self.board_id}&pageIndex={page_num}"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱 - KAIT 테이블 구조"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # KAIT 테이블 찾기 - 클래스명 없는 단순 table 태그
        table = soup.find('table')
        if not table:
            logger.warning("KAIT 테이블을 찾을 수 없습니다")
            return announcements
        
        tbody = table.find('tbody')
        if not tbody:
            logger.warning("테이블 tbody를 찾을 수 없습니다")
            return announcements
        
        rows = tbody.find_all('tr')
        logger.info(f"KAIT 테이블에서 {len(rows)}개 행 발견")
        
        for i, row in enumerate(rows):
            try:
                # onclick 속성에서 goDetail 파라미터 추출
                onclick = row.get('onclick', '')
                if not onclick:
                    continue
                
                # goDetail(bSeq, bId) 패턴에서 파라미터 추출
                detail_params = self._extract_detail_params(onclick)
                if not detail_params:
                    continue
                
                bSeq, bId = detail_params
                
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
                
                # 제목 - title_cell의 a 태그에서 추출
                title_link = title_cell.find('a')
                if title_link:
                    title = title_link.get_text(strip=True)
                    # 'NEW' 아이콘 제거
                    title = re.sub(r'\s*\[?NEW\]?\s*', '', title)
                else:
                    title = title_cell.get_text(strip=True)
                
                # 파일 정보 확인 - file_btn.gif 이미지가 있으면 첨부파일 존재
                has_attachments = False
                file_imgs = file_cell.find_all('img')
                for img in file_imgs:
                    src = img.get('src', '')
                    if 'file_btn.gif' in src:
                        has_attachments = True
                        break
                
                # 날짜
                date = date_cell.get_text(strip=True)
                
                # 조회수
                views = views_cell.get_text(strip=True)
                
                # 상세 페이지 URL (POST 방식이므로 더미 URL)
                detail_url = f"{self.base_url}/user/boardDetail.do?bSeq={bSeq}&bId={bId}"
                
                announcement = {
                    'number': number,
                    'title': title,
                    'author': 'KAIT',
                    'date': date,
                    'views': views,
                    'url': detail_url,
                    'bSeq': bSeq,
                    'bId': bId,
                    'has_attachments': has_attachments
                }
                
                announcements.append(announcement)
                logger.debug(f"공고 추가: [{number}] {title}")
                
            except Exception as e:
                logger.error(f"행 {i} 파싱 중 오류: {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
        return announcements
    
    def _extract_detail_params(self, onclick: str) -> tuple:
        """JavaScript onclick에서 상세페이지 파라미터 추출"""
        try:
            # goDetail(bSeq, bId) 패턴 매칭
            match = re.search(r'goDetail\((\d+),\s*(\d+)\)', onclick)
            if match:
                bSeq = match.group(1)
                bId = match.group(2)
                return (bSeq, bId)
        except Exception as e:
            logger.debug(f"상세페이지 파라미터 추출 실패: {e}")
        
        return None
    
    def get_detail_page(self, announcement: Dict[str, Any]) -> str:
        """상세 페이지 HTML 가져오기 - POST 방식"""
        try:
            detail_url = f"{self.base_url}/user/boardDetail.do"
            
            # POST 데이터 구성 (폼 파라미터와 동일하게)
            data = {
                'bSeq': announcement['bSeq'],
                'bId': announcement['bId'],
                'cateSeq': self.cate_seq
            }
            
            # POST 요청 헤더 설정
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': f"{self.base_url}/user/MainBoardList.do?cateSeq={self.cate_seq}&bId={self.board_id}"
            }
            
            response = self.session.post(detail_url, data=data, headers=headers, timeout=self.timeout)
            if response.status_code == 200:
                logger.debug(f"상세 페이지 접근 성공: bSeq={announcement['bSeq']}")
                return response.text
            else:
                logger.error(f"상세 페이지 접근 실패: bSeq={announcement['bSeq']}, 상태코드: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"상세 페이지 가져오기 실패: {e}")
            return None
    
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱 - KAIT 구조에 최적화"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출
        title_selectors = [
            '.board_view_title',
            '.title',
            'h1',
            'h2'
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
        """KAIT 사이트에서 본문 내용 추출"""
        
        # 1. 불필요한 요소들 제거
        unwanted_selectors = [
            'nav', 'header', 'footer', '.nav', '.navigation',
            '.menu', '.sidebar', '.breadcrumb',
            'script', 'style', '.ads', '.advertisement'
        ]
        
        for selector in unwanted_selectors:
            for elem in soup.select(selector):
                elem.decompose()
        
        # 2. KAIT 특화 콘텐츠 선택자
        content_selectors = [
            '.board_view_content',    # 게시글 본문
            '.view_content',          # 뷰 콘텐츠
            '.content_area',          # 콘텐츠 영역
            '.board_content',         # 게시판 콘텐츠
            '.detail_content',        # 상세 콘텐츠
            'main',                   # main 태그
            '[role="main"]'           # main 역할
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
    
    def simple_html_to_text(self, element) -> str:
        """HTML 요소를 간단한 텍스트로 변환"""
        text = element.get_text(separator='\n\n', strip=True)
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text
    
    def _extract_meta_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """KAIT 사이트에서 메타 정보 추출"""
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
        
        # 작성자 정보 (KAIT 기본값)
        meta_info['작성자'] = 'KAIT'
        
        return meta_info
    
    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """KAIT 구조에서 첨부파일 정보 추출"""
        attachments = []
        
        # KAIT 파일 다운로드 링크 패턴: /user/FileDownload1.do?bSeq=...&bId=...
        download_links = soup.find_all('a', href=lambda x: x and '/user/FileDownload' in x)
        
        for link in download_links:
            try:
                href = link.get('href', '')
                if '/user/FileDownload' not in href:
                    continue
                
                # 파일명 추출 (링크 텍스트에서)
                filename = link.get_text(strip=True)
                if not filename or filename == '':
                    # href에서 파일 번호 추출하여 기본 파일명 생성
                    download_match = re.search(r'FileDownload(\d+)\.do', href)
                    if download_match:
                        file_num = download_match.group(1)
                        filename = f"attachment_{file_num}"
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
        """파일 다운로드 - KAIT 특화 처리"""
        try:
            logger.info(f"파일 다운로드 시작: {file_url}")
            
            # KAIT 사이트는 세션 유지가 필요할 수 있음
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
    output_dir = "output/kait"
    os.makedirs(output_dir, exist_ok=True)
    
    scraper = EnhancedKaitScraper()
    
    try:
        result = scraper.scrape_pages(max_pages=3, output_base=output_dir)
        print(f"✅ KAIT 스크래핑 완료!")
        
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