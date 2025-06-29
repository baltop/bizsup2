# -*- coding: utf-8 -*-
"""
바로정보 지원사업 신청 스크래퍼 - 향상된 버전
https://www.baroinfo.com/front/M000000742/applybusiness/list.do
"""

import requests
from bs4 import BeautifulSoup
import os
import time
import html2text
from urllib.parse import urljoin, urlparse, parse_qs
import re
import json
import logging
from typing import Dict, List, Any, Optional
from enhanced_base_scraper import StandardTableScraper

logger = logging.getLogger(__name__)

class EnhancedBaroInfoScraper(StandardTableScraper):
    """바로정보 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        
        # 바로정보 기본 설정
        self.base_url = "https://www.baroinfo.com"
        self.list_url = "https://www.baroinfo.com/front/M000000742/applybusiness/list.do"
        
        # 사이트별 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1
        self.delay_between_pages = 2
        
        # 바로정보 특화 헤더
        self.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        self.session.headers.update(self.headers)
    
    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 생성 - JavaScript 기반 페이지네이션"""
        if page_num == 1:
            return self.list_url
        else:
            # JavaScript fnLinkPage 함수 패턴 분석 결과
            # 실제로는 POST 요청이나 다른 방식일 수 있으므로 기본 파라미터 방식으로 시도
            return f"{self.list_url}?page={page_num}"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱 - 바로정보 테이블 구조"""
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
            # tbody가 없으면 table 직접 사용
            tbody = table
        
        # 공고 행들 파싱
        rows = tbody.find_all('tr')
        logger.info(f"총 {len(rows)}개 행 발견")
        
        for row in rows:
            try:
                cells = row.find_all('td')
                if len(cells) < 5:  # 번호, 제목, 상태, 신청기간, 첨부파일
                    continue
                
                # 제목 셀 (두 번째 컬럼)
                title_cell = cells[1]
                title_elem = title_cell.find('p') or title_cell
                title = title_elem.get_text(strip=True)
                
                if not title or title in ['제목', '']:
                    continue
                
                # 클릭 이벤트에서 URL 추출 (행 전체가 클릭 가능)
                onclick = row.get('onclick', '')
                detail_url = None
                
                if onclick:
                    # onclick="return fn_articleView('AC00006572', '', 'ETC')" 패턴
                    match = re.search(r"fn_articleView\s*\(\s*['\"]([^'\"]+)['\"]", onclick)
                    if match:
                        article_id = match.group(1)
                        detail_url = f"{self.base_url}/front/M000000742/applybusiness/view.do?articleId={article_id}"
                
                if not detail_url:
                    logger.warning(f"상세 URL을 찾을 수 없습니다: {title}")
                    continue
                
                # 상태 (세 번째 컬럼)
                status_cell = cells[2]
                status_elem = status_cell.find('div') or status_cell
                status = status_elem.get_text(strip=True)
                
                # 신청기간 (네 번째 컬럼)
                period_cell = cells[3]
                period = period_cell.get_text(strip=True)
                
                # 첨부파일 (다섯 번째 컬럼)
                file_cell = cells[4]
                has_attachment = bool(file_cell.find('a'))
                
                announcement = {
                    'title': title,
                    'url': detail_url,
                    'status': status,
                    'period': period,
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
        title_elem = soup.find('div', class_='') or soup.select_one('h3, h2, h1')
        title = ""
        if title_elem:
            title = title_elem.get_text(strip=True)
        
        # 메타 정보 테이블 찾기
        meta_info = {}
        info_table = soup.find('table')
        if info_table:
            rows = info_table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    if key and value:
                        meta_info[key] = value
        
        # 본문 내용 추출 - 테이블 이후의 내용
        content_sections = []
        
        # 본문이 포함된 요소들 찾기
        content_elements = soup.find_all('p')
        for elem in content_elements:
            text = elem.get_text(strip=True)
            if text and len(text) > 10:  # 의미있는 텍스트만
                content_sections.append(text)
        
        # HTML을 마크다운으로 변환
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        
        # 전체 내용이 없으면 특정 영역만 추출
        if not content_sections:
            # 메인 컨테이너에서 내용 추출
            main_content = soup.find('main') or soup.find('div', {'id': 'container'})
            if main_content:
                # 테이블과 네비게이션 제외하고 텍스트 추출
                for unwanted in main_content.find_all(['table', 'nav', 'header', 'footer']):
                    unwanted.decompose()
                content = h.handle(str(main_content))
            else:
                content = h.handle(html_content)
        else:
            content = '\n\n'.join(content_sections)
        
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
        
        # 첨부파일 섹션 찾기
        attachment_section = soup.find('div', string=re.compile('첨부파일'))
        if attachment_section:
            # 첨부파일 링크들 찾기
            attachment_links = attachment_section.find_next('ul')
            if attachment_links:
                links = attachment_links.find_all('a', href=True)
                for link in links:
                    href = link.get('href')
                    filename = link.get_text(strip=True)
                    
                    if href and filename:
                        # 절대 URL 생성
                        file_url = urljoin(self.base_url, href)
                        
                        attachments.append({
                            'filename': filename,
                            'url': file_url
                        })
                        logger.debug(f"첨부파일 발견: {filename}")
        
        # 추가: 테이블에서 직접 첨부파일 링크 찾기 (목록 페이지의 첨부파일)
        if not attachments:
            file_links = soup.find_all('a', href=re.compile(r'/front/fileDown\.do'))
            for link in file_links:
                href = link.get('href')
                filename = link.get_text(strip=True) or "첨부파일"
                
                if href:
                    file_url = urljoin(self.base_url, href)
                    
                    # 파일 확장자 추출
                    if not '.' in filename:
                        # 링크에서 파일 타입 추출 시도
                        img = link.find('img')
                        if img and img.get('src'):
                            src = img.get('src')
                            if 'pdf' in src.lower():
                                filename += '.pdf'
                            elif 'hwp' in src.lower():
                                filename += '.hwp'
                            elif 'doc' in src.lower():
                                filename += '.doc'
                            elif 'xls' in src.lower():
                                filename += '.xls'
                            elif 'png' in src.lower():
                                filename += '.png'
                            elif 'jpg' in src.lower() or 'jpeg' in src.lower():
                                filename += '.jpg'
                    
                    attachments.append({
                        'filename': filename,
                        'url': file_url
                    })
                    logger.debug(f"첨부파일 발견: {filename}")
        
        logger.info(f"총 {len(attachments)}개 첨부파일 발견")
        return attachments
    
    def _get_page_announcements(self, page_num: int) -> List[Dict[str, Any]]:
        """페이지별 공고 목록 가져오기 - JavaScript 페이지네이션 대응"""
        if page_num == 1:
            # 첫 페이지는 기본 URL 사용
            page_url = self.list_url
        else:
            # JavaScript fnLinkPage 함수 시뮬레이션
            # 실제로는 POST 요청일 수 있으므로 여러 방법 시도
            
            # 방법 1: 쿼리 파라미터
            page_url = f"{self.list_url}?page={page_num}"
            
            # 방법 2: POST 데이터로 시도해볼 수도 있음
            # 하지만 일단 GET 방식으로 시도
        
        logger.info(f"페이지 {page_num} URL: {page_url}")
        
        response = self.get_page(page_url)
        if not response:
            logger.warning(f"페이지 {page_num} 응답을 가져올 수 없습니다")
            return []
        
        # JavaScript 페이지네이션이 작동하지 않을 경우를 위한 POST 요청 시도
        if page_num > 1 and response.status_code != 200:
            logger.info(f"GET 요청 실패, POST 요청 시도: 페이지 {page_num}")
            
            # POST 데이터 구성 (실제 사이트 분석 결과에 따라 조정 필요)
            post_data = {
                'page': str(page_num),
                'pageSize': '10'
            }
            
            response = self.post_page(self.list_url, data=post_data)
            if not response:
                return []
        
        announcements = self.parse_list_page(response.text)
        
        # 마지막 페이지 감지 - 공고가 없거나 페이지 번호가 범위를 벗어남
        if not announcements and page_num > 1:
            logger.info(f"페이지 {page_num}에 공고가 없어 마지막 페이지로 판단됩니다")
        
        return announcements


def test_baroinfo_scraper(pages=3):
    """바로정보 스크래퍼 테스트"""
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    scraper = EnhancedBaroInfoScraper()
    output_dir = "output/baroinfo"
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"바로정보 스크래퍼 테스트 시작 - {pages}페이지")
    scraper.scrape_pages(max_pages=pages, output_base=output_dir)
    logger.info("스크래핑 완료")


if __name__ == "__main__":
    test_baroinfo_scraper(3)