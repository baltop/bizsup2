# -*- coding: utf-8 -*-
"""
PAJUCCI (파주상공회의소) 스크래퍼 - 향상된 버전
http://pajucci.korcham.net/notice
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

class EnhancedPAJUCCIScraper(StandardTableScraper):
    """PAJUCCI 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        
        # PAJUCCI 기본 설정
        self.base_url = "http://pajucci.korcham.net"
        self.list_url = "http://pajucci.korcham.net/notice"
        
        # 사이트별 특화 설정
        self.verify_ssl = False  # HTTP 사이트
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1
        self.delay_between_pages = 2
        
        # PAJUCCI 특화 헤더
        self.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        self.session.headers.update(self.headers)
    
    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 생성"""
        if page_num == 1:
            return self.list_url
        else:
            # URL 패턴: ?page=2
            return f"{self.list_url}?page={page_num}"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱 - PAJUCCI 테이블 구조"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 메인 테이블 찾기 - caption이 "공지사항 목록"인 테이블
        table = None
        for t in soup.find_all('table'):
            caption = t.find('caption')
            if caption and '공지사항 목록' in caption.get_text():
                table = t
                logger.debug(f"공지사항 목록 테이블 발견")
                break
        
        if not table:
            logger.warning("목록 테이블을 찾을 수 없습니다")
            # 디버깅을 위해 모든 테이블 로그
            tables = soup.find_all('table')
            logger.info(f"총 {len(tables)}개 테이블 발견")
            for i, t in enumerate(tables):
                caption = t.find('caption')
                caption_text = caption.get_text() if caption else "None"
                logger.info(f"테이블 {i+1} caption: {caption_text}")
                rows = t.find_all('tr')
                logger.info(f"테이블 {i+1} 행 수: {len(rows)}")
            return announcements
        
        # tbody 또는 전체 행에서 데이터 추출
        tbody = table.find('tbody')
        if tbody:
            rows = tbody.find_all('tr')
        else:
            # tbody가 없으면 모든 row에서 헤더 제외
            all_rows = table.find_all('tr')
            # 첫 번째 행이 헤더인지 확인
            if all_rows and (all_rows[0].find('th') or '번호' in all_rows[0].get_text()):
                rows = all_rows[1:]  # 헤더 제외
            else:
                rows = all_rows
        
        logger.info(f"총 {len(rows)}개 행 발견")
        
        for row in rows:
            try:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 5:  # 번호, 제목, 글쓴이, 첨부, 날짜
                    continue
                
                # 첫 번째 셀이 th인 경우 (헤더 행) 스킵
                if cells[0].name == 'th':
                    continue
                
                # 번호 (첫 번째 컬럼) - "공지" 표시가 있을 수 있음
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
                
                # URL 추출 - 절대 URL이 이미 포함되어 있음
                href = link_elem.get('href', '')
                if href and href != '#':
                    # 이미 절대 URL인 경우 그대로 사용, 아니면 urljoin 적용
                    if href.startswith('http'):
                        detail_url = href
                    else:
                        detail_url = urljoin(self.base_url, href)
                else:
                    logger.warning(f"상세 URL을 찾을 수 없습니다: {title}")
                    continue
                
                # 글쓴이 (세 번째 컬럼)
                author_cell = cells[2]
                author = author_cell.get_text(strip=True)
                
                # 첨부 (네 번째 컬럼) - 빈 셀이면 첨부파일 없음
                attachment_cell = cells[3]
                attachment_text = attachment_cell.get_text(strip=True)
                has_attachment = bool(attachment_text)
                
                # 날짜 (다섯 번째 컬럼)
                date_cell = cells[4]
                date = date_cell.get_text(strip=True)
                
                announcement = {
                    'title': title,
                    'url': detail_url,
                    'author': author,
                    'date': date,
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
        
        # 제목 추출 - article > h2 구조
        title = ""
        title_elem = soup.find('article').find('h2') if soup.find('article') else None
        if title_elem:
            title = title_elem.get_text(strip=True)
        
        if not title:
            # 대체 방법: 페이지 타이틀에서 찾기
            page_title = soup.find('title')
            if page_title:
                title_text = page_title.get_text()
                # "제목 > 공지사항 | 파주상공회의소" 형태에서 제목 부분만 추출
                if ' > ' in title_text:
                    title = title_text.split(' > ')[0].strip()
                else:
                    title = title_text.strip()
        
        # 메타 정보 추출 (날짜, 조회수 등)
        meta_info = {}
        
        # 페이지 정보 영역에서 메타데이터 추출
        page_info = soup.find('div', class_='page-info') or soup.find(text=re.compile(r'\d{2}-\d{2}-\d{2}'))
        if page_info:
            # 날짜 패턴 찾기
            date_pattern = r'(\d{2})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})'
            date_match = re.search(date_pattern, str(page_info))
            if date_match:
                meta_info['date'] = date_match.group(0)
        
        # 본문 내용 추출
        content_sections = []
        
        # 본문이 포함된 영역 찾기 (PAJUCCI 특화)
        # article 태그 내의 본문 영역
        article = soup.find('article')
        if article:
            # 본문 컨테이너 찾기
            content_div = article.find('div', class_='content') or article.find('div')
            
            if content_div:
                # 불필요한 요소 제거
                for unwanted in content_div.find_all(['script', 'style', 'nav', 'header', 'footer']):
                    unwanted.decompose()
                
                # 이미지와 텍스트 추출
                for elem in content_div.find_all(['p', 'div', 'span']):
                    text = elem.get_text(strip=True)
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
        
        # 첨부파일 목록 찾기 - PAJUCCI는 list 형태로 첨부파일 제공
        attachment_list = soup.find('ul') or soup.find('ol')
        if attachment_list:
            for item in attachment_list.find_all('li'):
                link = item.find('a')
                if link:
                    href = link.get('href', '')
                    filename_text = link.get_text(strip=True)
                    
                    # 다운로드 URL 패턴 확인
                    if 'download.php' in href:
                        # 절대 URL 생성
                        file_url = urljoin(self.base_url, href)
                        
                        # 파일명과 크기 정보 분리
                        # 예: "파일명.hwp (11.8M)" 형태
                        size_match = re.search(r'\(([^)]+)\)$', filename_text)
                        if size_match:
                            file_size = size_match.group(1)
                            filename = filename_text.replace(size_match.group(0), '').strip()
                        else:
                            filename = filename_text
                            file_size = ""
                        
                        attachments.append({
                            'filename': filename,
                            'url': file_url,
                            'size': file_size
                        })
                        logger.debug(f"첨부파일 발견: {filename} ({file_size})")
        
        # 추가: 다른 패턴의 첨부파일 링크 찾기
        if not attachments:
            # download.php를 포함한 모든 링크 찾기
            download_links = soup.find_all('a', href=re.compile(r'download\.php'))
            for link in download_links:
                href = link.get('href')
                filename = link.get_text(strip=True)
                
                if href:
                    file_url = urljoin(self.base_url, href)
                    
                    # 파일명이 의미없는 경우 URL 파라미터에서 추출
                    if not filename or filename in ['다운로드', '파일']:
                        parsed_url = urlparse(href)
                        query_params = parse_qs(parsed_url.query)
                        if 'filename' in query_params:
                            filename = query_params['filename'][0]
                        else:
                            filename = "첨부파일"
                    
                    attachments.append({
                        'filename': filename,
                        'url': file_url,
                        'size': ""
                    })
                    logger.debug(f"첨부파일 발견: {filename}")
            
            # 일반 파일 확장자 패턴도 확인
            if not attachments:
                file_links = soup.find_all('a', href=re.compile(r'\.(hwp|pdf|doc|docx|xls|xlsx|ppt|pptx|zip|rar|jpg|png)$', re.I))
                for link in file_links:
                    href = link.get('href')
                    filename = link.get_text(strip=True) or os.path.basename(href)
                    
                    if href:
                        file_url = urljoin(self.base_url, href)
                        
                        attachments.append({
                            'filename': filename,
                            'url': file_url,
                            'size': ""
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


def test_pajucci_scraper(pages=3):
    """PAJUCCI 스크래퍼 테스트"""
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    scraper = EnhancedPAJUCCIScraper()
    output_dir = "output/pajucci"
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"PAJUCCI 스크래퍼 테스트 시작 - {pages}페이지")
    scraper.scrape_pages(max_pages=pages, output_base=output_dir)
    logger.info("스크래핑 완료")


if __name__ == "__main__":
    test_pajucci_scraper(3)