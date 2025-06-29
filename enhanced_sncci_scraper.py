# -*- coding: utf-8 -*-
"""
SNCCI (성남상공회의소) 스크래퍼 - 향상된 버전
https://www.sncci.net/new/sub01/sub0101.php
"""

import requests
from bs4 import BeautifulSoup
import os
import time
import html2text
from urllib.parse import urljoin, urlparse, parse_qs, unquote
import re
import json
import logging
from typing import Dict, List, Any, Optional
from enhanced_base_scraper import StandardTableScraper

logger = logging.getLogger(__name__)

class EnhancedSNCCIScraper(StandardTableScraper):
    """SNCCI 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        
        # SNCCI 기본 설정
        self.base_url = "https://www.sncci.net"
        self.list_url = "https://www.sncci.net/new/sub01/sub0101.php"
        
        # 사이트별 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1
        self.delay_between_pages = 2
        
        # SNCCI 특화 헤더
        self.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        self.session.headers.update(self.headers)
    
    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 생성"""
        if page_num == 1:
            return self.list_url
        else:
            # URL 패턴: ?no=&p=2&prog=&cate1=&h=&m=&z=&type=
            return f"{self.list_url}?no=&p={page_num}&prog=&cate1=&h=&m=&z=&type="
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱 - SNCCI 테이블 구조"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 메인 테이블 찾기
        table = soup.find('table')
        if not table:
            logger.warning("목록 테이블을 찾을 수 없습니다")
            return announcements
        
        # tbody 찾기 (헤더 제외)
        tbody = table.find('tbody')
        if not tbody:
            # tbody가 없으면 table 직접 사용하되 첫 번째 행 제외
            rows = table.find_all('tr')[1:]  # 헤더 제외
        else:
            rows = tbody.find_all('tr')
        
        logger.info(f"총 {len(rows)}개 행 발견")
        
        for row in rows:
            try:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 5:  # 번호, 제목, 기간, 구분, 조회수
                    continue
                
                # 첫 번째 셀이 th인 경우 (헤더 행) 스킵
                if cells[0].name == 'th':
                    continue
                
                # 번호 (첫 번째 컬럼)
                no_cell = cells[0]
                no = no_cell.get_text(strip=True)
                
                # 제목 (두 번째 컬럼)
                title_cell = cells[1]
                link_elem = title_cell.find('a')
                
                if not link_elem:
                    continue
                
                title = link_elem.get_text(strip=True)
                
                if not title or title in ['제목', '']:
                    continue
                
                # URL 추출 - 상대 경로 처리
                href = link_elem.get('href', '')
                if href and href != '#':
                    # 상대 경로를 절대 경로로 변환
                    detail_url = urljoin(self.list_url, href)
                else:
                    logger.warning(f"상세 URL을 찾을 수 없습니다: {title}")
                    continue
                
                # 기간 (세 번째 컬럼)
                period_cell = cells[2]
                period = period_cell.get_text(strip=True)
                
                # 구분 (네 번째 컬럼)
                category_cell = cells[3]
                category = category_cell.get_text(strip=True)
                
                # 조회수 (다섯 번째 컬럼)
                views_cell = cells[4]
                views = views_cell.get_text(strip=True)
                
                # 첨부파일 여부 확인 (새글 이미지 등)
                has_attachment = bool(title_cell.find('img'))
                
                announcement = {
                    'title': title,
                    'url': detail_url,
                    'period': period,
                    'category': category,
                    'views': views,
                    'no': no,
                    'has_attachment': has_attachment
                }
                
                announcements.append(announcement)
                logger.debug(f"공고 추가: {title}")
                
            except Exception as e:
                logger.error(f"행 파싱 중 오류: {e}")
                continue
        
        logger.info(f"파싱 완료: {len(announcements)}개 공고")
        return announcements
    
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출
        title_elem = soup.find('h2') or soup.find('h1') or soup.find('h3')
        title = ""
        if title_elem:
            title = title_elem.get_text(strip=True)
        
        # 메타 정보 추출 (날짜 등)
        meta_info = {}
        
        # 날짜 정보가 있는 paragraph 찾기
        date_para = soup.find('p', string=re.compile(r'\d{4}-\d{2}-\d{2}'))
        if date_para:
            date_text = date_para.get_text(strip=True)
            meta_info['date'] = date_text
        
        # 본문 내용 추출
        content_sections = []
        
        # 본문이 포함된 div 찾기 (SNCCI 특화)
        content_div = soup.find('div', class_=['content', 'board_content'])
        if not content_div:
            # 특정 클래스가 없는 경우 generic div에서 찾기
            content_divs = soup.find_all('div')
            for div in content_divs:
                # 텍스트가 많이 포함된 div 찾기
                text_content = div.get_text(strip=True)
                if len(text_content) > 100:  # 충분한 텍스트가 있는 경우
                    content_div = div
                    break
        
        if content_div:
            # 불필요한 요소 제거
            for unwanted in content_div.find_all(['script', 'style', 'nav', 'header', 'footer']):
                unwanted.decompose()
            
            # 텍스트 추출
            paragraphs = content_div.find_all(['p', 'div'])
            for para in paragraphs:
                text = para.get_text(strip=True)
                if text and len(text) > 5:  # 의미있는 텍스트만
                    content_sections.append(text)
        
        # HTML을 마크다운으로 변환
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        
        if content_sections:
            content = '\n\n'.join(content_sections)
        else:
            # 전체 본문에서 불필요한 요소 제거 후 변환
            for unwanted in soup.find_all(['nav', 'header', 'footer', 'script', 'style']):
                unwanted.decompose()
            content = h.handle(html_content)
        
        # 첨부파일 추출
        attachments = self._extract_attachments(soup)
        
        return {
            'title': title,
            'content': content,
            'meta_info': meta_info,
            'attachments': attachments
        }
    
    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """첨부파일 링크 추출"""
        attachments = []
        
        # 첨부파일 다운로드 링크 찾기 - SNCCI 특화 패턴
        # download.php 링크 패턴 찾기
        download_links = soup.find_all('a', href=re.compile(r'download\.php'))
        for link in download_links:
            href = link.get('href')
            filename = link.get_text(strip=True)
            
            if href and filename:
                # 절대 URL 생성
                file_url = urljoin(self.base_url, href)
                
                # 파일명 정리
                if not filename or filename in ['다운로드', '파일']:
                    # URL에서 파일명 추출 시도
                    parsed_url = urlparse(href)
                    query_params = parse_qs(parsed_url.query)
                    if 'filename' in query_params:
                        filename = query_params['filename'][0]
                    else:
                        filename = "첨부파일"
                
                attachments.append({
                    'filename': filename,
                    'url': file_url
                })
                logger.debug(f"첨부파일 발견: {filename}")
        
        # 추가: 다른 패턴의 첨부파일 링크 찾기
        if not attachments:
            # .hwp, .pdf 등의 확장자를 가진 링크 찾기
            file_links = soup.find_all('a', href=re.compile(r'\.(hwp|pdf|doc|docx|xls|xlsx|ppt|pptx|zip|rar)$', re.I))
            for link in file_links:
                href = link.get('href')
                filename = link.get_text(strip=True) or os.path.basename(href)
                
                if href:
                    file_url = urljoin(self.base_url, href)
                    
                    attachments.append({
                        'filename': filename,
                        'url': file_url
                    })
                    logger.debug(f"첨부파일 발견: {filename}")
        
        logger.info(f"총 {len(attachments)}개 첨부파일 발견")
        return attachments
    
    def _get_page_announcements(self, page_num: int) -> List[Dict[str, Any]]:
        """페이지별 공고 목록 가져오기"""
        page_url = self.get_list_url(page_num)
        logger.info(f"페이지 {page_num} URL: {page_url}")
        
        response = self.get_page(page_url)
        if not response:
            logger.warning(f"페이지 {page_num} 응답을 가져올 수 없습니다")
            return []
        
        # 페이지가 에러 상태거나 잘못된 경우 감지
        if response.status_code >= 400:
            logger.warning(f"페이지 {page_num} HTTP 에러: {response.status_code}")
            return []
        
        announcements = self.parse_list_page(response.text)
        
        # 마지막 페이지 감지
        if not announcements and page_num > 1:
            logger.info(f"페이지 {page_num}에 공고가 없어 마지막 페이지로 판단됩니다")
        
        return announcements


def test_sncci_scraper(pages=3):
    """SNCCI 스크래퍼 테스트"""
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    scraper = EnhancedSNCCIScraper()
    output_dir = "output/sncci"
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"SNCCI 스크래퍼 테스트 시작 - {pages}페이지")
    scraper.scrape_pages(max_pages=pages, output_base=output_dir)
    logger.info("스크래핑 완료")


if __name__ == "__main__":
    test_sncci_scraper(3)