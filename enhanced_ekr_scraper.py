#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EKR(한국농어촌공사) 공지사항 스크래퍼
URL: https://www.ekr.or.kr/planweb/board/list.krc?contentUid=402880317cc0644a017cc0c9da9f0120&boardUid=402880317cc0644a017cc5e8000f06b7&contentUid=402880317cc0644a017cc0c9da9f0120&subPath=
"""

import re
import json
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup
from enhanced_base_scraper import EnhancedBaseScraper

logger = logging.getLogger(__name__)

class EnhancedEkrScraper(EnhancedBaseScraper):
    """EKR(한국농어촌공사) 공지사항 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        
        # 사이트 기본 설정
        self.base_url = "https://www.ekr.or.kr"
        self.list_url = "https://www.ekr.or.kr/planweb/board/list.krc?contentUid=402880317cc0644a017cc0c9da9f0120&boardUid=402880317cc0644a017cc5e8000f06b7&contentUid=402880317cc0644a017cc0c9da9f0120&subPath="
        self.start_url = self.list_url
        
        # 헤더 설정
        self.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        self.session.headers.update(self.headers)
        
        # 현재 상세 페이지 URL 저장 (Referer 용)
        self.current_detail_url = None
        
        # 세션 초기화 (쿠키 설정)
        self._initialize_session()
        
    def _initialize_session(self):
        """세션 초기화 및 쿠키 설정"""
        try:
            # 메인 페이지 접근으로 세션 초기화
            logger.info("EKR 사이트 세션 초기화 중...")
            response = self.session.get(self.base_url, timeout=10)
            response.raise_for_status()
            
            # 게시판 페이지 접근으로 세션 활성화
            response = self.session.get(self.list_url, timeout=10)
            response.raise_for_status()
            
            logger.info("EKR 사이트 세션 초기화 완료")
        except Exception as e:
            logger.warning(f"세션 초기화 중 오류 (계속 진행): {e}")
        
    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 생성"""
        base_params = "contentUid=402880317cc0644a017cc0c9da9f0120&boardUid=402880317cc0644a017cc5e8000f06b7&contentUid=402880317cc0644a017cc0c9da9f0120&subPath="
        
        if page_num == 1:
            return f"{self.base_url}/planweb/board/list.krc?{base_params}"
        else:
            return f"{self.base_url}/planweb/board/list.krc?{base_params}&page={page_num}"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        logger.debug("EKR 사이트 목록 페이지 파싱 시작")
        
        # 테이블 구조 찾기 - 표준 HTML 테이블 기반 (class="bbs_table")
        table = soup.find('table', class_='bbs_table')
        if not table:
            logger.warning("bbs_table 클래스를 가진 테이블을 찾을 수 없음")
            return announcements
        
        # tr 요소들 찾기
        rows = table.find_all('tr')
        logger.debug(f"발견된 행 수: {len(rows)}")
        
        for i, row in enumerate(rows):
            try:
                # 첫 번째 행은 헤더이므로 건너뛰기
                if i == 0:
                    continue
                
                # td 요소들 찾기
                cells = row.find_all('td')
                if len(cells) < 2:  # 최소 2개 이상의 td가 있어야 함
                    continue
                
                # 첫 번째 td에서 번호 추출
                number_cell = cells[0]
                number = number_cell.get_text(strip=True)
                
                # 공지사항 이미지 확인
                is_notice = False
                notice_imgs = number_cell.find_all('img')
                for img in notice_imgs:
                    src = img.get('src', '')
                    alt = img.get('alt', '')
                    if '공지' in src or '공지' in alt or 'notice' in src.lower():
                        is_notice = True
                        break
                
                # 번호 정리
                if is_notice or '공지' in number:
                    number = "공지"
                elif not number or number.isspace():
                    number = f"row_{i}"
                
                # 제목 및 링크 추출 (두 번째 td - class="title")
                title_cell = cells[1] if len(cells) > 1 else cells[0]
                
                # 링크 찾기
                link_element = title_cell.find('a')
                if not link_element:
                    continue
                
                # 제목 추출
                title = link_element.get_text(strip=True)
                if not title:
                    continue
                
                # URL 추출
                href = link_element.get('href')
                if not href:
                    continue
                
                # 절대 URL 생성 - EKR 사이트 특성에 맞게 수정
                # 목록 URL을 기반으로 상대 URL 처리
                detail_url = urljoin(self.list_url, href)
                
                # 작성자 추출 (세 번째 td)
                writer = ''
                if len(cells) > 2:
                    writer_cell = cells[2]
                    writer = writer_cell.get_text(strip=True)
                
                # 첨부파일 여부 확인 (네 번째 td)
                has_attachment = False
                if len(cells) > 3:
                    attachment_cell = cells[3]
                    attachment_text = attachment_cell.get_text(strip=True)
                    if '첨부파일 있음' in attachment_text:
                        has_attachment = True
                
                # 날짜 추출 (다섯 번째 td)
                date = ''
                if len(cells) > 4:
                    date_cell = cells[4]
                    date = date_cell.get_text(strip=True)
                
                # 조회수 추출 (여섯 번째 td)
                views = ''
                if len(cells) > 5:
                    views_cell = cells[5]
                    views = views_cell.get_text(strip=True)
                
                # 공지사항 정보 구성
                announcement = {
                    'number': number,
                    'title': title,
                    'url': detail_url,
                    'writer': writer,
                    'has_attachment': has_attachment,
                    'date': date,
                    'views': views
                }
                
                announcements.append(announcement)
                logger.debug(f"공고 파싱 완료: {number} - {title[:50]}...")
                
            except Exception as e:
                logger.error(f"공고 {i+1} 파싱 중 오류: {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
        return announcements
    
    def parse_detail_page(self, html_content: str, detail_url: str = None) -> Dict[str, Any]:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 현재 상세 페이지 URL 저장
        if detail_url:
            self.current_detail_url = detail_url
        
        # 첨부파일 추출 (본문 추출 전에 먼저 실행)
        attachments = self._extract_attachments(soup)
        
        # 본문 내용 추출
        content = self._extract_content(soup)
        
        return {
            'content': content,
            'attachments': attachments
        }
    
    def _extract_content(self, soup: BeautifulSoup) -> str:
        """본문 내용 추출"""
        content_parts = []
        
        # 방법 1: 제목 추출
        title_element = soup.find('h1') or soup.find('h2')
        if title_element:
            title = title_element.get_text(strip=True)
            if title:
                content_parts.append(f"# {title}")
        
        # 방법 2: 테이블 구조에서 메타 정보 추출
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    
                    # 메타 정보 형태로 저장
                    if any(keyword in label for keyword in ['작성일', '조회수', '작성자', '등록일', '수정일']):
                        content_parts.append(f"**{label}**: {value}")
        
        # 방법 3: 본문 내용 추출
        content_found = False
        
        # 일반적인 본문 영역 찾기
        content_selectors = [
            'div.content',
            'div.view-content',
            'div.board-content',
            'div#content',
            'div.txt-area',
            'div.view_content',
            'div.board_view_content'
        ]
        
        for selector in content_selectors:
            content_div = soup.select_one(selector)
            if content_div:
                # 텍스트 추출
                text = content_div.get_text(strip=True)
                if text and len(text) > 20:
                    content_parts.append(text)
                    content_found = True
                    break
        
        # 방법 4: 테이블 내 긴 텍스트 찾기
        if not content_found:
            for table in tables:
                for row in table.find_all('tr'):
                    for cell in row.find_all(['td', 'th']):
                        cell_text = cell.get_text(strip=True)
                        # 충분히 긴 텍스트이고 첨부파일 관련이 아닌 경우
                        if (cell_text and len(cell_text) > 50 and 
                            not any(keyword in cell_text for keyword in ['첨부파일', '다운로드', '파일명', '파일크기'])):
                            content_parts.append(cell_text)
                            content_found = True
        
        # 방법 5: 전체 페이지에서 의미있는 텍스트 찾기 (최후 수단)
        if not content_found:
            for element in soup.find_all(['p', 'div', 'article', 'section']):
                text = element.get_text(strip=True)
                if text and len(text) > 50:
                    content_parts.append(text)
        
        # 최종 본문 구성
        if content_parts:
            return "\\n\\n".join(content_parts)
        else:
            return "본문 내용을 추출할 수 없습니다."
    
    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """첨부파일 추출"""
        attachments = []
        
        # 방법 1: 첨부파일 테이블에서 다운로드 링크 찾기
        tables = soup.find_all('table')
        for table in tables:
            for row in table.find_all('tr'):
                for cell in row.find_all(['td', 'th']):
                    cell_text = cell.get_text(strip=True)
                    
                    # 첨부파일 관련 텍스트 확인
                    if any(keyword in cell_text for keyword in ['첨부파일', '첨부', '다운로드', '파일명']):
                        # 해당 cell이나 인접한 cell에서 링크 찾기
                        links = cell.find_all('a', href=True)
                        if not links:
                            # 다음 cell에서 링크 찾기
                            next_cell = cell.find_next_sibling(['td', 'th'])
                            if next_cell:
                                links = next_cell.find_all('a', href=True)
                        
                        for link in links:
                            href = link.get('href', '')
                            filename = link.get_text(strip=True)
                            
                            # 다운로드 링크 패턴 확인
                            if 'download.krc' in href and filename:
                                # 절대 URL 생성 - EKR 사이트 특성에 맞는 URL 구성
                                if href.startswith('./'):
                                    # 상대 경로를 절대 경로로 변환
                                    download_url = urljoin(self.base_url + '/planweb/board/', href[2:])
                                elif href.startswith('/'):
                                    # 절대 경로
                                    download_url = urljoin(self.base_url, href)
                                else:
                                    # 기타 경우 현재 상세 페이지 URL 기반으로 생성
                                    if self.current_detail_url:
                                        download_url = urljoin(self.current_detail_url, href)
                                    else:
                                        download_url = urljoin(self.base_url + '/planweb/board/', href)
                                
                                # 파일 크기 정보 제거
                                filename = re.sub(r'\\s*\\([\\d.]+\\s*[KMG]?B\\)', '', filename)
                                
                                # 파일 확장자 추출
                                file_ext = filename.split('.')[-1].upper() if '.' in filename else 'UNKNOWN'
                                
                                attachments.append({
                                    'filename': filename,
                                    'url': download_url,
                                    'size': '',
                                    'type': file_ext
                                })
                                logger.debug(f"첨부파일 추출 성공: {filename} - {download_url}")
        
        # 방법 2: 일반적인 다운로드 링크 패턴 찾기
        if not attachments:
            # download.krc 패턴의 모든 링크 찾기
            download_links = soup.find_all('a', href=re.compile(r'download\.krc'))
            logger.debug(f"download.krc 패턴 링크 {len(download_links)}개 발견")
            
            for link in download_links:
                href = link.get('href', '')
                filename = link.get_text(strip=True)
                
                if href and filename:
                    # 절대 URL 생성 - EKR 사이트 특성에 맞는 URL 구성
                    if href.startswith('./'):
                        # 상대 경로를 절대 경로로 변환
                        download_url = urljoin(self.base_url + '/planweb/board/', href[2:])
                    elif href.startswith('/'):
                        # 절대 경로
                        download_url = urljoin(self.base_url, href)
                    else:
                        # 기타 경우 현재 상세 페이지 URL 기반으로 생성
                        if self.current_detail_url:
                            download_url = urljoin(self.current_detail_url, href)
                        else:
                            download_url = urljoin(self.base_url + '/planweb/board/', href)
                    
                    # 파일 크기 정보 제거
                    filename = re.sub(r'\\s*\\([\\d.]+\\s*[KMG]?B\\)', '', filename)
                    
                    # 파일 확장자 추출
                    file_ext = filename.split('.')[-1].upper() if '.' in filename else 'UNKNOWN'
                    
                    attachments.append({
                        'filename': filename,
                        'url': download_url,
                        'size': '',
                        'type': file_ext
                    })
                    logger.debug(f"다운로드 링크 추출: {filename} - {download_url}")
        
        # 방법 3: 파일 확장자가 포함된 링크 찾기
        if not attachments:
            file_extensions = ['.hwp', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.rar']
            
            for ext in file_extensions:
                ext_links = soup.find_all('a', href=re.compile(f'.*{ext}', re.IGNORECASE))
                for link in ext_links:
                    href = link.get('href', '')
                    filename = link.get_text(strip=True)
                    
                    if href and filename:
                        # 절대 URL 생성 - EKR 사이트 특성에 맞는 URL 구성
                        if href.startswith('./'):
                            # 상대 경로를 절대 경로로 변환
                            download_url = urljoin(self.base_url + '/planweb/board/', href[2:])
                        elif href.startswith('/'):
                            # 절대 경로
                            download_url = urljoin(self.base_url, href)
                        else:
                            # 기타 경우 현재 상세 페이지 URL 기반으로 생성
                            if self.current_detail_url:
                                download_url = urljoin(self.current_detail_url, href)
                            else:
                                download_url = urljoin(self.base_url + '/planweb/board/', href)
                        
                        # 파일 크기 정보 제거
                        filename = re.sub(r'\\s*\\([\\d.]+\\s*[KMG]?B\\)', '', filename)
                        
                        # 파일 확장자 추출
                        file_ext = filename.split('.')[-1].upper() if '.' in filename else 'UNKNOWN'
                        
                        attachments.append({
                            'filename': filename,
                            'url': download_url,
                            'size': '',
                            'type': file_ext
                        })
                        logger.debug(f"확장자 기반 파일 추출: {filename} - {download_url}")
        
        logger.info(f"첨부파일 {len(attachments)}개 추출")
        return attachments
    
    def download_file(self, url: str, save_path: str, attachment_info: Dict[str, Any] = None) -> bool:
        """파일 다운로드 (EKR 특성상 Referer 헤더 추가, 실제 다운로드 시도)"""
        try:
            # 다운로드 전 Referer 헤더 설정
            headers = self.session.headers.copy()
            if self.current_detail_url:
                headers['Referer'] = self.current_detail_url
            
            # 부모 클래스의 download_file 메서드 호출하되, 헤더 추가
            original_headers = self.session.headers.copy()
            self.session.headers.update(headers)
            
            try:
                result = super().download_file(url, save_path, attachment_info)
                return result
            finally:
                # 원래 헤더로 복원
                self.session.headers.clear()
                self.session.headers.update(original_headers)
                
        except Exception as e:
            logger.error(f"파일 다운로드 오류: {e}")
            return False


def main():
    """메인 실행 함수 - 3페이지 수집"""
    import sys
    import os
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('ekr_scraper.log', encoding='utf-8')
        ]
    )
    
    logger.info("="*60)
    logger.info("🚀 EKR(한국농어촌공사) 공지사항 스크래퍼 시작")
    logger.info("="*60)
    
    # 출력 디렉토리 설정
    output_dir = "output/ekr"
    
    # 기존 출력 디렉토리 정리 (파일만 삭제, 디렉토리 구조 유지)
    if os.path.exists(output_dir):
        import shutil
        logger.info(f"기존 출력 디렉토리 정리: {output_dir}")
        shutil.rmtree(output_dir)
    
    # 스크래퍼 초기화
    scraper = EnhancedEkrScraper()
    
    try:
        # 3페이지 전체 수집 실행
        success = scraper.scrape_pages(max_pages=3, output_base="output/ekr")
        
        if success:
            logger.info("✅ 스크래핑 완료!")
            
            # 통계 출력
            stats = scraper.get_stats()
            logger.info(f"📊 처리 통계: {stats}")
            
        else:
            logger.error("❌ 스크래핑 실패")
            return 1
            
    except KeyboardInterrupt:
        logger.info("⏹️  사용자에 의해 중단됨")
        return 1
    except Exception as e:
        logger.error(f"❌ 예상치 못한 오류: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())