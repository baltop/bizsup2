# -*- coding: utf-8 -*-
"""
축산환경관리원(LEMI) 공지사항 스크래퍼 - Enhanced 버전
URL: https://www.lemi.or.kr/board.do?boardno=24&menuno=71
"""

import os
import re
import time
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, unquote
from bs4 import BeautifulSoup

try:
    from enhanced_base_scraper import StandardTableScraper
except ImportError:
    from enhanced_base_scraper import EnhancedBaseScraper as StandardTableScraper

logger = logging.getLogger(__name__)

class EnhancedLemiScraper(StandardTableScraper):
    """축산환경관리원(LEMI) 전용 스크래퍼 - Enhanced 버전"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.lemi.or.kr"
        self.list_url = "https://www.lemi.or.kr/board.do?boardno=24&menuno=71"
        
        # LEMI 사이트 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1.5
        
        # 공지사항 포함 수집 설정
        self.include_notices = True
        
        logger.info("Enhanced LEMI 스크래퍼 초기화 완료")

    def get_list_url(self, page_num: int) -> str:
        """페이지별 목록 URL 생성"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}&page_now={page_num}"

    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱 - 공지사항 포함"""
        announcements = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 게시판 테이블 찾기
            table = soup.find('table', class_='list_tbl')
            if not table:
                logger.warning("목록 테이블을 찾을 수 없습니다")
                return announcements
            
            tbody = table.find('tbody')
            if not tbody:
                logger.warning("tbody를 찾을 수 없습니다")
                return announcements
            
            rows = tbody.find_all('tr')
            logger.info(f"총 {len(rows)}개의 행을 발견했습니다")
            
            for i, row in enumerate(rows):
                cells = row.find_all('td')
                if len(cells) < 4:
                    continue
                
                try:
                    # 번호 처리 (공지 포함)
                    number_cell = cells[0]
                    number = number_cell.get_text(strip=True)
                    
                    # 공지사항 처리
                    is_notice = False
                    if 'tr_notice' in row.get('class', []) or '공지' in number:
                        is_notice = True
                        number = "공지"
                    elif not number or not number.replace('공지', '').strip():
                        number = f"row_{i+1}"
                    
                    # 제목 및 링크
                    title_cell = cells[1]
                    link_elem = title_cell.find('a')
                    if not link_elem:
                        continue
                    
                    title = link_elem.get_text(strip=True)
                    href = link_elem.get('href', '')
                    
                    if not href:
                        continue
                    
                    detail_url = urljoin(self.base_url, href)
                    
                    # 작성자
                    author = cells[2].get_text(strip=True)
                    
                    # 작성일
                    date = cells[3].get_text(strip=True)
                    # "작성일" 텍스트 제거
                    date = re.sub(r'^작성일', '', date).strip()
                    
                    announcement = {
                        'number': number,
                        'title': title,
                        'url': detail_url,
                        'author': author,
                        'date': date,
                        'is_notice': is_notice
                    }
                    
                    announcements.append(announcement)
                    logger.info(f"공고 추가: [{number}] {title}")
                    
                except Exception as e:
                    logger.warning(f"행 {i+1} 파싱 중 오류: {e}")
                    continue
            
            logger.info(f"총 {len(announcements)}개의 공고를 파싱했습니다")
            
        except Exception as e:
            logger.error(f"목록 페이지 파싱 중 오류 발생: {e}")
        
        return announcements

    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 제목 추출
            title_elem = soup.find('h5', class_='sbj')
            title = title_elem.get_text(strip=True) if title_elem else "제목 없음"
            
            # 메타 정보 추출
            author = "관리자"  # 기본값
            date = ""
            views = ""
            
            info_list = soup.find('ul', class_='info')
            if info_list:
                info_items = info_list.find_all('li')
                for item in info_items:
                    text = item.get_text(strip=True)
                    if '작성일' in text:
                        date = re.sub(r'^작성일', '', text).strip()
                    elif '조회' in text:
                        views = re.sub(r'^조회', '', text).strip()
            
            # 본문 내용 추출
            content_div = soup.find('div', class_='memoWrap')
            content = ""
            
            if content_div:
                # 이미지의 alt 텍스트 우선 사용
                images = content_div.find_all('img')
                for img in images:
                    alt_text = img.get('alt', '')
                    if alt_text and len(alt_text) > 50:  # 충분한 길이의 alt 텍스트가 있으면 사용
                        content = alt_text
                        break
                
                # alt 텍스트가 없으면 일반 텍스트 추출
                if not content:
                    content = content_div.get_text(separator='\n', strip=True)
                
                # HTML을 마크다운으로 변환
                if content:
                    content = self.h.handle(str(content_div))
            
            # 첨부파일 추출
            attachments = self._extract_attachments(soup)
            
            return {
                'title': title,
                'author': author,
                'date': date,
                'views': views,
                'content': content,
                'attachments': attachments
            }
            
        except Exception as e:
            logger.error(f"상세 페이지 파싱 중 오류: {e}")
            return {
                'title': "파싱 오류",
                'author': "",
                'date': "",
                'views': "",
                'content': f"상세 페이지 파싱 중 오류가 발생했습니다: {e}",
                'attachments': []
            }

    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """첨부파일 정보 추출"""
        attachments = []
        
        try:
            # 첨부파일 영역 찾기
            file_ul = soup.find('ul', class_='file')
            if not file_ul:
                return attachments
            
            file_links = file_ul.find_all('a', href=True)
            
            for link in file_links:
                href = link.get('href', '')
                onclick = link.get('onclick', '')
                
                # JavaScript 다운로드 함수 파싱 - href와 onclick 모두 확인
                download_pattern = None
                if 'download(' in href:
                    download_pattern = href
                elif 'download(' in onclick:
                    download_pattern = onclick
                
                if download_pattern:
                    # download(3242) 형태에서 파일번호 추출
                    file_id_match = re.search(r'download\((\d+)\)', download_pattern)
                    if file_id_match:
                        file_id = file_id_match.group(1)
                        
                        # 파일명 추출 (링크 텍스트에서, filename 클래스가 있는 링크만)
                        filename = link.get_text(strip=True)
                        
                        # 빈 텍스트이거나 filename 클래스가 없으면 스킵 (아이콘 링크)
                        if not filename or 'filename' not in link.get('class', []):
                            continue
                        
                        # 파일 다운로드 URL 구성
                        download_url = f"{self.base_url}/common/imgload.do?fileno={file_id}"
                        
                        # 파일 크기 정보 추출 (주변 텍스트에서)
                        parent = link.parent
                        if parent:
                            parent_text = parent.get_text()
                            size_match = re.search(r'용량\s*:\s*([^/]+)', parent_text)
                            file_size = size_match.group(1).strip() if size_match else "unknown"
                        else:
                            file_size = "unknown"
                        
                        attachment = {
                            'filename': filename,
                            'url': download_url,
                            'size': file_size,
                            'file_id': file_id
                        }
                        
                        attachments.append(attachment)
                        logger.info(f"첨부파일 발견: {filename} ({file_size})")
            
        except Exception as e:
            logger.error(f"첨부파일 추출 중 오류: {e}")
        
        return attachments

    def download_file(self, file_url: str, save_path: str, attachment_info: Dict[str, Any] = None) -> bool:
        """파일 다운로드 - LEMI 특화"""
        try:
            logger.info(f"파일 다운로드 시작: {file_url}")
            
            # Referer 헤더 추가
            headers = self.headers.copy()
            headers['Referer'] = self.base_url
            
            response = self.session.get(
                file_url, 
                headers=headers,
                timeout=self.timeout,
                verify=self.verify_ssl,
                stream=True
            )
            
            if response.status_code == 200:
                # Enhanced Base Scraper가 이미 올바른 파일명으로 save_path를 설정했으므로 그대로 사용
                filename = save_path
                
                # 파일 저장
                os.makedirs(os.path.dirname(filename), exist_ok=True)
                
                with open(filename, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                file_size = os.path.getsize(filename)
                logger.info(f"파일 다운로드 완료: {filename} ({file_size} bytes)")
                
                return True
            else:
                logger.error(f"파일 다운로드 실패: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"파일 다운로드 중 오류: {e}")
            return False

    def _extract_filename_from_response(self, response, default_path):
        """응답 헤더에서 파일명 추출 - 한글 파일명 처리"""
        save_dir = os.path.dirname(default_path)
        
        content_disposition = response.headers.get('Content-Disposition', '')
        
        if content_disposition:
            # RFC 5987 형식 먼저 시도
            rfc5987_match = re.search(r"filename\*=([^']*)'([^']*)'(.+)", content_disposition)
            if rfc5987_match:
                encoding, lang, filename = rfc5987_match.groups()
                try:
                    filename = unquote(filename, encoding=encoding or 'utf-8')
                    return os.path.join(save_dir, self.sanitize_filename(filename))
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
                            clean_filename = self.sanitize_filename(decoded.replace('+', ' '))
                            return os.path.join(save_dir, clean_filename)
                    except:
                        continue
        
        # 기본 파일명 사용
        return default_path

    def sanitize_filename(self, filename: str) -> str:
        """파일명 정리"""
        # Windows 호환을 위한 특수문자 제거
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = filename.strip('. ')
        
        return filename if filename else "unnamed_file"


def main():
    """테스트용 메인 함수"""
    scraper = EnhancedLemiScraper()
    output_dir = "output/lemi"
    
    try:
        os.makedirs(output_dir, exist_ok=True)
        scraper.scrape_pages(max_pages=3, output_base=output_dir)
        print("✅ LEMI 스크래핑 완료")
        
    except KeyboardInterrupt:
        print("\n❌ 사용자에 의해 중단되었습니다")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()