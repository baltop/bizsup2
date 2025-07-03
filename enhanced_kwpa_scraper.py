# -*- coding: utf-8 -*-
"""
한국원목생산업협회(KWPA) 공지사항 스크래퍼 - Enhanced 버전
URL: http://www.kwpa.co.kr/html/s0401.php
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

class EnhancedKwpaScraper(StandardTableScraper):
    """한국원목생산업협회(KWPA) 전용 스크래퍼 - Enhanced 버전"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "http://www.kwpa.co.kr"
        self.list_url = "http://www.kwpa.co.kr/html/s0401.php"
        
        # KWPA 사이트 특화 설정
        self.verify_ssl = False  # HTTP 사이트
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1.5
        
        # 공지사항 포함 수집 설정
        self.include_notices = True
        
        logger.info("Enhanced KWPA 스크래퍼 초기화 완료")

    def get_list_url(self, page_num: int) -> str:
        """페이지별 목록 URL 생성"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}?page={page_num}"

    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱 - 공지사항 포함"""
        announcements = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 게시판 테이블 찾기
            table = soup.find('table', class_='table-list')
            if not table:
                logger.warning("목록 테이블을 찾을 수 없습니다")
                return announcements
            
            tbody = table.find('tbody')
            if not tbody:
                logger.warning("tbody를 찾을 수 없습니다")
                return announcements
            
            rows = tbody.find_all('tr', class_='tr-body')
            logger.info(f"총 {len(rows)}개의 행을 발견했습니다")
            
            for i, row in enumerate(rows):
                cells = row.find_all('td')
                if len(cells) < 5:
                    continue
                
                try:
                    # 번호 처리 (공지 포함)
                    number_cell = cells[0]
                    number = number_cell.get_text(strip=True)
                    
                    # 공지사항 처리
                    is_notice = False
                    if '공지' in number:
                        is_notice = True
                        number = "공지"
                    elif not number or not number.isdigit():
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
                    
                    # 첨부파일 여부 확인
                    has_attachment = bool(title_cell.find('img', src=re.compile(r'icon_file')))
                    
                    # 작성자
                    author = cells[2].get_text(strip=True)
                    
                    # 작성일
                    date = cells[3].get_text(strip=True)
                    
                    # 조회수
                    views = cells[4].get_text(strip=True)
                    
                    announcement = {
                        'number': number,
                        'title': title,
                        'url': detail_url,
                        'author': author,
                        'date': date,
                        'views': views,
                        'has_attachment': has_attachment,
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
            title_elem = soup.find('h4', class_='title')
            title = title_elem.get_text(strip=True) if title_elem else "제목 없음"
            
            # 메타 정보 추출
            author = ""
            date = ""
            views = ""
            
            info_div = soup.find('div', class_='float-right info')
            if info_div:
                info_spans = info_div.find_all('span', class_='read-member-info')
                if len(info_spans) >= 3:
                    author = info_spans[0].get_text(strip=True)
                    date = info_spans[1].get_text(strip=True)
                    views = info_spans[2].get_text(strip=True)
            
            # 본문 내용 추출
            content_div = soup.find('div', class_='bbs-read-body')
            content = ""
            
            if content_div:
                # HTML을 마크다운으로 변환
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
            # 첨부파일 영역 찾기 - tr-download 클래스를 가진 행
            download_row = soup.find('tr', class_='tr-download')
            if not download_row:
                return attachments
            
            # 파일 링크 찾기
            file_links = download_row.find_all('a', href=True)
            
            for link in file_links:
                href = link.get('href', '')
                
                # KWPA 다운로드 링크 패턴: /bbslib/download.php?tbl=b401&seq=140&fid=192
                if 'download.php' in href:
                    # 파일명 추출 (링크 텍스트에서)
                    filename = link.get_text(strip=True)
                    
                    # 아이콘 제거 (fa fa-link 등)
                    filename = re.sub(r'^\s*[\uf000-\uf8ff]?\s*', '', filename)  # 유니코드 아이콘 제거
                    filename = filename.strip()
                    
                    if not filename:
                        continue
                    
                    # 절대 URL 생성
                    download_url = urljoin(self.base_url, href)
                    
                    attachment = {
                        'filename': filename,
                        'url': download_url,
                        'size': "unknown"
                    }
                    
                    attachments.append(attachment)
                    logger.info(f"첨부파일 발견: {filename}")
            
        except Exception as e:
            logger.error(f"첨부파일 추출 중 오류: {e}")
        
        return attachments

    def download_file(self, file_url: str, save_path: str, attachment_info: Dict[str, Any] = None) -> bool:
        """파일 다운로드 - KWPA 특화"""
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
    scraper = EnhancedKwpaScraper()
    output_dir = "output/kwpa"
    
    try:
        os.makedirs(output_dir, exist_ok=True)
        scraper.scrape_pages(max_pages=3, output_base=output_dir)
        print("✅ KWPA 스크래핑 완료")
        
    except KeyboardInterrupt:
        print("\n❌ 사용자에 의해 중단되었습니다")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()