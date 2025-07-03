# -*- coding: utf-8 -*-
"""
KBIZ (중소기업중앙회) 사이트 스크래퍼 - Enhanced 버전
사이트: https://www.kbiz.or.kr/ko/contents/bbs/list.do?mnSeq=211&schFld=whle&schTxt=%EC%82%AC%EC%97%85%EA%B3%B5%EA%B3%A0
"""

from enhanced_base_scraper import StandardTableScraper
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote
import re
import os
import logging

logger = logging.getLogger(__name__)

class EnhancedKbizScraper(StandardTableScraper):
    """KBIZ 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.kbiz.or.kr"
        self.list_url = "https://www.kbiz.or.kr/ko/contents/bbs/list.do?mnSeq=211&schFld=whle&schTxt=%EC%82%AC%EC%97%85%EA%B3%B5%EA%B3%A0"
        
        # KBIZ 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1
    
    def get_list_url(self, page_num: int) -> str:
        """페이지별 목록 URL 생성"""
        if page_num == 1:
            return self.list_url
        else:
            return f"https://www.kbiz.or.kr/ko/contents/bbs/list.do?pg={page_num}&pgSz=10&mnSeq=211&schFld=whle&schTxt=%EC%82%AC%EC%97%85%EA%B3%B5%EA%B3%A0"
    
    def parse_list_page(self, html_content: str) -> list:
        """목록 페이지 파싱"""
        announcements = []
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 테이블 찾기
        table = soup.find('table')
        if not table:
            logger.warning("테이블을 찾을 수 없습니다")
            return announcements
        
        # 행들 가져오기 (헤더 제외)
        rows = table.find_all('tr')
        for i, row in enumerate(rows):
            cells = row.find_all('td')
            if len(cells) < 4:  # 번호, 제목, 첨부파일, 등록일
                continue
            
            try:
                # 번호 (첫 번째 셀) - "공지" 이미지 처리
                number_cell = cells[0]
                number = number_cell.get_text(strip=True)
                
                # 공지 이미지 확인
                notice_img = number_cell.find('img', {'alt': '공지'})
                if notice_img or '공지' in number_cell.get_text():
                    number = "공지"
                elif not number:
                    number = f"row_{i}"
                
                # 제목 (두 번째 셀) - onclick 처리
                title_cell = cells[1]
                title = title_cell.get_text(strip=True)
                
                # goView 함수에서 상세 URL 추출
                onclick_span = title_cell.find('span', onclick=True)
                if onclick_span:
                    onclick = onclick_span.get('onclick', '')
                    # goView(159352, 'Y') 패턴에서 ID와 플래그 추출
                    match = re.search(r"goView\((\d+),\s*'([YN])'\)", onclick)
                    if match:
                        seq_id, top_fix = match.groups()
                        detail_url = f"{self.base_url}/ko/contents/bbs/view.do?seq={seq_id}&topFixYn={top_fix}&mnSeq=211&schFld=whle&schTxt=%EC%82%AC%EC%97%85%EA%B3%B5%EA%B3%A0"
                    else:
                        continue
                else:
                    continue
                
                # 첨부파일 여부 (세 번째 셀)
                file_cell = cells[2]
                has_attachment = bool(file_cell.find('img', {'alt': '파일'}))
                
                # 등록일 (네 번째 셀)
                date = cells[3].get_text(strip=True)
                
                announcement = {
                    'number': number,
                    'title': title,
                    'url': detail_url,
                    'date': date,
                    'has_attachment': has_attachment
                }
                
                announcements.append(announcement)
                logger.info(f"공고 추가: [{number}] {title}")
                
            except Exception as e:
                logger.error(f"공고 파싱 오류 (행 {i}): {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
        return announcements
    
    def parse_detail_page(self, html_content: str) -> dict:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출 - 여러 선택자 시도
        title = "제목 없음"
        title_selectors = ['h1', 'h2', '.title', '.board-title', '.subject']
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem and title_elem.get_text(strip=True):
                title = title_elem.get_text(strip=True)
                break
        
        # 메타 정보 - 테이블에서 추출
        meta_info = {}
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    if key and value:
                        meta_info[key] = value
        
        # 본문 추출 - 전체 페이지에서 본문 영역 찾기
        content = ""
        
        # 1. 특정 본문 영역 선택자 시도
        content_selectors = [
            '.content', '.board-content', '.view-content', 
            '.detail-content', '.txt-area', '.view-wrap'
        ]
        
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                content = self.h.handle(str(content_elem))
                break
        
        # 2. 본문을 찾지 못한 경우, 테이블 정보를 본문으로 사용
        if not content.strip() and meta_info:
            content_parts = []
            for key, value in meta_info.items():
                content_parts.append(f"**{key}**: {value}")
            content = "\n\n".join(content_parts)
        
        # 3. 여전히 본문이 없으면 페이지 전체에서 추출
        if not content.strip():
            # 스크립트, 스타일 등 제거
            for script in soup(["script", "style", "nav", "header", "footer"]):
                script.decompose()
            
            # 주요 내용이 있을 만한 부분 찾기
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
            if main_content:
                content = self.h.handle(str(main_content))
            else:
                # 최후의 수단: body의 텍스트 내용
                content = soup.get_text(separator='\n', strip=True)
        
        # 첨부파일 추출
        attachments = self._extract_attachments(soup)
        
        return {
            'title': title,
            'content': content,
            'attachments': attachments,
            'meta_info': meta_info
        }
    
    def _extract_attachments(self, soup: BeautifulSoup) -> list:
        """첨부파일 추출"""
        attachments = []
        
        # 다운로드 링크 찾기
        download_links = soup.find_all('a', href=re.compile(r'download\.do'))
        
        for link in download_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            if href:
                # 상대 URL을 절대 URL로 변환
                file_url = urljoin(self.base_url, href)
                
                # URL에서 원본 파일명 추출 시도
                filename = self._extract_filename_from_url(file_url)
                
                attachment = {
                    'url': file_url,
                    'filename': filename or text or 'attachment',
                    'text': text
                }
                attachments.append(attachment)
                logger.info(f"첨부파일 발견: {filename} - {file_url}")
        
        return attachments
    
    def _extract_filename_from_url(self, url: str) -> str:
        """URL에서 파일명 추출 - KBIZ는 특수한 인코딩 사용"""
        try:
            # KBIZ의 경우 orgalFle 파라미터가 16진수 인코딩된 한글일 수 있음
            if 'orgalFle=' in url:
                import urllib.parse
                parsed = urllib.parse.urlparse(url)
                params = urllib.parse.parse_qs(parsed.query)
                
                if 'orgalFle' in params:
                    encoded_filename = params['orgalFle'][0]
                    
                    # 1. 일반 URL 디코딩 시도
                    try:
                        decoded_filename = urllib.parse.unquote(encoded_filename, encoding='utf-8')
                        if decoded_filename != encoded_filename and len(decoded_filename) > 0:
                            return decoded_filename
                    except:
                        pass
                    
                    # 2. 16진수 디코딩 시도 (KBIZ의 특수한 방식)
                    try:
                        # 16진수를 바이트로 변환 후 UTF-8 디코딩
                        if len(encoded_filename) % 2 == 0:  # 16진수는 짝수 길이여야 함
                            bytes_data = bytes.fromhex(encoded_filename)
                            decoded_filename = bytes_data.decode('utf-8')
                            return decoded_filename
                    except:
                        pass
                    
                    # 3. 그대로 반환 (마지막 수단)
                    return encoded_filename
            
            return None
        except Exception as e:
            logger.warning(f"파일명 추출 실패: {e}")
            return None
    
    def _guess_extension_from_content_type(self, response) -> str:
        """Content-Type으로부터 확장자 추측"""
        content_type = response.headers.get('Content-Type', '').lower()
        
        if 'excel' in content_type or 'sheet' in content_type or 'spreadsheet' in content_type:
            return '.xlsx'
        elif 'word' in content_type or 'msword' in content_type:
            return '.docx'
        elif 'pdf' in content_type:
            return '.pdf'
        elif 'hwp' in content_type:
            return '.hwp'
        elif 'zip' in content_type:
            return '.zip'
        elif 'text' in content_type:
            return '.txt'
        elif 'image' in content_type:
            if 'jpeg' in content_type or 'jpg' in content_type:
                return '.jpg'
            elif 'png' in content_type:
                return '.png'
            elif 'gif' in content_type:
                return '.gif'
            else:
                return '.img'
        else:
            return '.bin'
    
    def download_file(self, file_url: str, file_path_or_dir: str, attachment_or_filename = None) -> str:
        """파일 다운로드 with 한글 파일명 처리 - Enhanced Base Scraper 호환"""
        try:
            logger.info(f"파일 다운로드 시작: {file_url}")
            
            response = self.session.get(file_url, timeout=self.timeout, verify=self.verify_ssl)
            response.raise_for_status()
            
            # file_path_or_dir가 파일 경로인지 디렉토리인지 판단
            if file_path_or_dir.endswith(('.pdf', '.docx', '.xlsx', '.hwp', '.zip', '.bin', '.txt')) or os.path.basename(file_path_or_dir) != os.path.dirname(file_path_or_dir):
                # 이미 파일 경로인 경우 (base scraper가 전체 경로를 넘긴 경우)
                file_path = file_path_or_dir
                save_dir = os.path.dirname(file_path)
                filename = os.path.basename(file_path)
            else:
                # 디렉토리인 경우 (기존 방식)
                save_dir = file_path_or_dir
                filename = attachment_or_filename
                
                # 파일명 결정 - attachment dict가 넘어온 경우 처리
                if isinstance(filename, dict):
                    filename = filename.get('filename', filename.get('text', 'attachment'))
                
                # 파일명이 여전히 없으면 URL에서 추출 (KBIZ 16진수 디코딩)
                if not filename:
                    filename = self._extract_filename_from_url(file_url)
                
                # 파일명이 여전히 없으면 응답 헤더에서 추출
                if not filename:
                    filename = self._extract_filename_from_response(response, save_dir)
                
                # 파일명이 여전히 없거나 확장자가 없는 경우
                if not filename or not filename.strip():
                    # saveFle 파라미터에서 확장자 추출 시도
                    try:
                        import urllib.parse
                        parsed = urllib.parse.urlparse(file_url)
                        params = urllib.parse.parse_qs(parsed.query)
                        if 'saveFle' in params:
                            save_file = params['saveFle'][0]
                            # 확장자 추출
                            if '.' in save_file:
                                ext = '.' + save_file.split('.')[-1]
                            else:
                                ext = self._guess_extension_from_content_type(response)
                        else:
                            ext = self._guess_extension_from_content_type(response)
                    except:
                        ext = self._guess_extension_from_content_type(response)
                    
                    filename = f"attachment_{hash(file_url) % 100000}{ext}"
                
                # 확장자가 없는 경우 추가
                elif '.' not in filename:
                    # saveFle 파라미터에서 확장자 추출
                    try:
                        import urllib.parse
                        parsed = urllib.parse.urlparse(file_url)
                        params = urllib.parse.parse_qs(parsed.query)
                        if 'saveFle' in params:
                            save_file = params['saveFle'][0]
                            if '.' in save_file:
                                ext = '.' + save_file.split('.')[-1]
                                filename += ext
                    except:
                        pass
                
                # 안전한 파일명으로 변환
                safe_filename = self.sanitize_filename(str(filename))
                file_path = os.path.join(save_dir, safe_filename)
            
            # 디렉토리 생성
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 파일 저장
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            file_size = len(response.content)
            safe_filename = os.path.basename(file_path)
            logger.info(f"파일 다운로드 완료: {safe_filename} ({file_size:,} bytes)")
            
            return file_path
            
        except Exception as e:
            logger.error(f"파일 다운로드 실패 {file_url}: {e}")
            return None
    
    def _extract_filename_from_response(self, response, save_dir: str) -> str:
        """응답 헤더에서 파일명 추출"""
        content_disposition = response.headers.get('Content-Disposition', '')
        
        if content_disposition:
            # RFC 5987 형식 처리
            rfc5987_match = re.search(r"filename\*=([^']*)'([^']*)'(.+)", content_disposition)
            if rfc5987_match:
                encoding, lang, filename = rfc5987_match.groups()
                try:
                    filename = unquote(filename, encoding=encoding or 'utf-8')
                    return self.sanitize_filename(filename)
                except:
                    pass
            
            # 일반 filename 파라미터 처리
            filename_match = re.search(r'filename[^;=\n]*=([\'"]*)(.*?)\1', content_disposition)
            if filename_match:
                filename = filename_match.group(2)
                
                # 한글 파일명 인코딩 처리
                for encoding in ['utf-8', 'euc-kr', 'cp949']:
                    try:
                        if encoding == 'utf-8':
                            decoded = filename.encode('latin-1').decode('utf-8')
                        else:
                            decoded = filename.encode('latin-1').decode(encoding)
                        
                        if decoded and not decoded.isspace():
                            return self.sanitize_filename(decoded.replace('+', ' '))
                    except:
                        continue
        
        return None

def test_kbiz_scraper(pages=3):
    """KBIZ 스크래퍼 테스트"""
    scraper = EnhancedKbizScraper()
    output_dir = "output/kbiz"
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        scraper.scrape_pages(max_pages=pages, output_base=output_dir)
        print(f"✅ KBIZ 스크래퍼 테스트 완료 - {pages}페이지 수집")
    except Exception as e:
        print(f"❌ KBIZ 스크래퍼 테스트 실패: {e}")

if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    test_kbiz_scraper(3)