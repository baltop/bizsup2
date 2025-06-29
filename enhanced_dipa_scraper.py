#!/usr/bin/env python3
"""
DIPA (용인시산업진흥원) 스크래퍼 - 향상된 버전

사이트: http://dipa.or.kr/information/businessnotice/
특징: HTTP 사이트, WordPress + KBoard, 표준 HTML 테이블, GET 파라미터 페이지네이션
"""

import re
import logging
from typing import List, Dict, Any
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from enhanced_base_scraper import StandardTableScraper

logger = logging.getLogger(__name__)

class EnhancedDIPAScraper(StandardTableScraper):
    """DIPA 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        # 기본 설정
        self.base_url = "http://dipa.or.kr"
        self.list_url = "http://dipa.or.kr/information/businessnotice/"
        
        # 사이트별 특화 설정
        self.verify_ssl = False  # HTTP 사이트이므로 SSL 검증 불필요
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1
        
        # DIPA 특화 설정
        self.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        logger.info("DIPA 스크래퍼 초기화 완료")
    
    def get_list_url(self, page_num: int) -> str:
        """페이지별 URL 생성"""
        # 설정이 있으면 부모 클래스의 표준 구현 사용
        if self.config and self.config.pagination:
            return super().get_list_url(page_num)
        
        # Fallback: DIPA 특화 로직
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}?pageid={page_num}&mod=list"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱"""
        # 설정 기반 파싱이 가능하면 사용
        if self.config and self.config.selectors:
            return super().parse_list_page(html_content)
        
        # Fallback: DIPA 특화 로직
        return self._parse_list_fallback(html_content)
    
    def _parse_list_fallback(self, html_content: str) -> List[Dict[str, Any]]:
        """DIPA 표준 HTML 테이블 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        try:
            # 표준 HTML 테이블 구조에서 공고 목록 파싱
            table = soup.find('table')
            if not table:
                logger.warning("테이블을 찾을 수 없습니다")
                return announcements
            
            tbody = table.find('tbody')
            if not tbody:
                tbody = table  # tbody가 없는 경우 table 직접 사용
            
            rows = tbody.find_all('tr')
            logger.info(f"테이블에서 {len(rows)}개 행 발견")
            
            for i, row in enumerate(rows):
                try:
                    cells = row.find_all('td')
                    if len(cells) < 4:  # 최소 4개 컬럼 필요 (번호, 제목, 작성자, 작성일)
                        logger.debug(f"행 {i+1}: 컬럼 수 부족 ({len(cells)}개)")
                        continue
                    
                    # 번호 셀 (첫 번째)
                    number_cell = cells[0]
                    number_text = number_cell.get_text(strip=True)
                    
                    # 공지사항 스킵 (번호가 숫자가 아닌 경우)
                    if not number_text.isdigit():
                        logger.debug(f"행 {i+1}: 공지사항 스킵 ({number_text})")
                        continue
                    
                    # 제목 셀 (두 번째)
                    title_cell = cells[1]
                    link_elem = title_cell.find('a')
                    
                    if not link_elem:
                        logger.debug(f"행 {i+1}: 제목 링크를 찾을 수 없음")
                        continue
                    
                    title = link_elem.get_text(strip=True)
                    if not title:
                        logger.debug(f"행 {i+1}: 제목이 비어있음")
                        continue
                    
                    href = link_elem.get('href', '')
                    if not href:
                        logger.debug(f"행 {i+1}: href가 비어있음")
                        continue
                    
                    # 절대 URL로 변환
                    if href.startswith('/'):
                        detail_url = urljoin(self.base_url, href)
                    elif href.startswith('?'):
                        detail_url = urljoin(self.list_url, href)
                    else:
                        detail_url = href
                    
                    # 작성자 (세 번째)
                    author = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                    
                    # 작성일 (네 번째)
                    date = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                    
                    announcement = {
                        'title': title,
                        'url': detail_url,
                        'number': number_text,
                        'author': author,
                        'date': date
                    }
                    
                    announcements.append(announcement)
                    logger.debug(f"공고 파싱 완료: {title[:50]}...")
                    
                except Exception as e:
                    logger.warning(f"행 {i+1} 파싱 중 오류: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"목록 페이지 파싱 중 오류: {e}")
        
        logger.info(f"{len(announcements)}개 공고 파싱 완료")
        return announcements
    
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱"""
        # 설정 기반 파싱이 가능하면 사용
        if self.config and self.config.selectors:
            return super().parse_detail_page(html_content)
        
        # Fallback: DIPA 특화 로직
        return self._parse_detail_fallback(html_content)
    
    def _parse_detail_fallback(self, html_content: str) -> Dict[str, Any]:
        """DIPA 상세 페이지 특화 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 본문 추출을 위한 다양한 선택자 시도
        content_selectors = [
            '.content-body',
            '.kboard-content',
            '.post-content',
            '.entry-content',
            '.content-area',
            '.board-content',
            '.article-content'
        ]
        
        content = ""
        content_elem = None
        
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                logger.debug(f"본문을 {selector} 선택자로 찾음")
                break
        
        if content_elem:
            # HTML을 텍스트로 변환
            content = content_elem.get_text(separator='\n', strip=True)
        else:
            # 대체 방법: 본문이 있을 만한 영역에서 텍스트 추출
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_=re.compile(r'content|post|article'))
            if main_content:
                content = main_content.get_text(separator='\n', strip=True)
                logger.warning("본문 영역을 추정하여 텍스트 추출")
            else:
                # 마지막 수단: 전체 body에서 텍스트 추출
                body = soup.find('body')
                if body:
                    content = body.get_text(separator='\n', strip=True)
                    logger.warning("본문 영역을 찾지 못해 전체 페이지 텍스트 사용")
        
        # 첨부파일 추출
        attachments = self._extract_attachments(soup)
        
        return {
            'content': content,
            'attachments': attachments
        }
    
    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """첨부파일 링크 추출"""
        attachments = []
        
        try:
            # WordPress KBoard 플러그인의 첨부파일 패턴들
            attachment_patterns = [
                # 1. 버튼 형태의 첨부파일
                ('button', lambda elem: elem.get_text(strip=True)),
                # 2. 링크 형태의 첨부파일 (일반적인 패턴)
                ('a[href*="download"]', lambda elem: elem.get_text(strip=True)),
                ('a[href*="file"]', lambda elem: elem.get_text(strip=True)),
                ('a[href*="attach"]', lambda elem: elem.get_text(strip=True)),
                # 3. 파일 확장자가 포함된 링크
                ('a[href*=".hwp"]', lambda elem: elem.get_text(strip=True)),
                ('a[href*=".pdf"]', lambda elem: elem.get_text(strip=True)),
                ('a[href*=".doc"]', lambda elem: elem.get_text(strip=True)),
                ('a[href*=".xls"]', lambda elem: elem.get_text(strip=True)),
                ('a[href*=".zip"]', lambda elem: elem.get_text(strip=True))
            ]
            
            for selector, filename_extractor in attachment_patterns:
                elements = soup.select(selector)
                
                for elem in elements:
                    # 파일명 추출
                    filename = filename_extractor(elem)
                    
                    # 파일명이 유효한지 확인
                    if not filename or len(filename) < 3:
                        continue
                    
                    # 다운로드 관련 텍스트인지 확인
                    if any(keyword in filename.lower() for keyword in ['다운로드', 'download', '첨부']):
                        # 실제 파일명이 아닌 버튼 텍스트인 경우, 다른 방법으로 파일명 추출
                        # title 속성이나 data 속성에서 파일명 찾기
                        actual_filename = elem.get('title') or elem.get('data-filename')
                        if actual_filename:
                            filename = actual_filename
                        else:
                            # 근처에서 파일명 찾기
                            parent = elem.parent
                            if parent:
                                text_content = parent.get_text()
                                # 파일 확장자가 포함된 텍스트 찾기
                                file_pattern = re.search(r'[\w\s가-힣]+\.(hwp|pdf|doc|docx|xls|xlsx|zip|ppt|pptx)', text_content)
                                if file_pattern:
                                    filename = file_pattern.group(0)
                    
                    # 파일 확장자가 있는지 확인
                    if not re.search(r'\.(hwp|pdf|doc|docx|xls|xlsx|zip|ppt|pptx)$', filename.lower()):
                        continue
                    
                    # URL 구성
                    if elem.name == 'button':
                        # 버튼의 경우 onclick 이벤트나 data 속성에서 URL 추출
                        onclick = elem.get('onclick', '')
                        data_url = elem.get('data-url', '')
                        
                        if onclick:
                            # JavaScript 함수에서 URL 추출
                            url_match = re.search(r'["\']([^"\']*(?:download|file)[^"\']*)["\']', onclick)
                            if url_match:
                                file_url = url_match.group(1)
                            else:
                                continue
                        elif data_url:
                            file_url = data_url
                        else:
                            # 버튼 주변에서 다운로드 링크 찾기
                            parent = elem.parent
                            if parent:
                                nearby_link = parent.find('a', href=True)
                                if nearby_link:
                                    file_url = nearby_link.get('href')
                                else:
                                    continue
                            else:
                                continue
                    else:
                        # 링크의 경우 href 속성 사용
                        file_url = elem.get('href', '')
                        if not file_url:
                            continue
                    
                    # 절대 URL로 변환
                    if file_url.startswith('/'):
                        file_url = urljoin(self.base_url, file_url)
                    elif not file_url.startswith('http'):
                        file_url = urljoin(self.list_url, file_url)
                    
                    attachment = {
                        'name': filename,
                        'url': file_url
                    }
                    
                    # 중복 제거
                    if attachment not in attachments:
                        attachments.append(attachment)
                        logger.debug(f"첨부파일 발견: {filename}")
                
                # 첫 번째 패턴에서 파일을 찾았으면 다른 패턴은 시도하지 않음
                if attachments:
                    break
            
        except Exception as e:
            logger.error(f"첨부파일 추출 중 오류: {e}")
        
        logger.info(f"{len(attachments)}개 첨부파일 발견")
        return attachments

# 하위 호환성을 위한 별칭
DIPAScraper = EnhancedDIPAScraper

if __name__ == "__main__":
    # 간단한 테스트
    scraper = EnhancedDIPAScraper()
    print(f"DIPA 스크래퍼 초기화 완료")
    print(f"기본 URL: {scraper.list_url}")
    print(f"1페이지 URL: {scraper.get_list_url(1)}")
    print(f"2페이지 URL: {scraper.get_list_url(2)}")
    print(f"SSL 검증: {scraper.verify_ssl}")  # False여야 함 (HTTP 사이트)