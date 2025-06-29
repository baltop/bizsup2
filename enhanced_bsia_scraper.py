# -*- coding: utf-8 -*-
"""
BSIA (부산경남봉제산업협동조합) 스크래퍼 - 향상된 버전
https://www.bsia.kr/notice
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

class EnhancedBSIAScraper(StandardTableScraper):
    """BSIA 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        
        # BSIA 기본 설정
        self.base_url = "https://www.bsia.kr"
        self.list_url = "https://www.bsia.kr/notice"
        
        # 사이트별 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1
        self.delay_between_pages = 2
        
        # BSIA 특화 헤더
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
            # URL 패턴: ?command=&id=&page_no=2&category2=&search_key=subject&category=&search_keyword=
            return f"{self.list_url}?command=&id=&page_no={page_num}&category2=&search_key=subject&category=&search_keyword="
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱 - BSIA 테이블 구조"""
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
                if len(cells) < 4:  # NO, 분류, 제목, 등록일
                    continue
                
                # 첫 번째 셀이 th인 경우 (헤더 행) 스킵
                if cells[0].name == 'th' and cells[0].get_text(strip=True) in ['NO', '공지']:
                    continue
                
                # 번호 (첫 번째 컬럼)
                no_cell = cells[0]
                no = no_cell.get_text(strip=True)
                
                # 분류 (두 번째 컬럼)
                category_cell = cells[1]
                category = category_cell.get_text(strip=True)
                
                # 제목 (세 번째 컬럼)
                title_cell = cells[2]
                link_elem = title_cell.find('a')
                
                if not link_elem:
                    continue
                
                title_text = link_elem.find('span') or link_elem
                title = title_text.get_text(strip=True)
                
                if not title or title in ['제목', '']:
                    continue
                
                # 첨부파일 여부 확인
                has_attachment = bool(title_cell.find(string=re.compile('첨부파일 있음')))
                
                # 등록일 (네 번째 컬럼)
                date_cell = cells[3]
                date = date_cell.get_text(strip=True)
                
                # onclick에서 공고 ID 추출
                onclick = link_elem.get('onclick', '')
                detail_url = None
                
                if onclick:
                    # onclick="javascript:viewDetail(this, 203, '/notice');" 패턴
                    match = re.search(r'viewDetail\s*\(\s*[^,]+,\s*(\d+),\s*[^)]+\)', onclick)
                    if match:
                        notice_id = match.group(1)
                        detail_url = f"{self.base_url}/notice?command=view&id={notice_id}&page_no=1&category2=&search_key=subject&category=&search_keyword="
                
                if not detail_url:
                    logger.warning(f"상세 URL을 찾을 수 없습니다: {title}")
                    continue
                
                announcement = {
                    'title': title,
                    'url': detail_url,
                    'category': category,
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
    
    def _extract_notice_id_from_table(self, soup: BeautifulSoup, target_title: str) -> Optional[str]:
        """테이블에서 특정 제목의 공고 ID 추출 (대체 방법)"""
        try:
            # 모든 테이블 행을 확인하여 제목으로 ID 추정
            table = soup.find('table')
            if not table:
                return None
            
            rows = table.find_all('tr')
            for i, row in enumerate(rows):
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 3:
                    title_cell = cells[2]
                    if title_cell.find(string=re.compile(re.escape(target_title))):
                        # 행 순서 기반으로 ID 추정 (실제 사이트 분석 필요)
                        # 이는 임시 방법이며, 실제로는 JavaScript 분석이나 다른 방법 필요
                        return str(200 + i)  # 추정값
            
            return None
        except Exception as e:
            logger.error(f"공고 ID 추출 실패: {e}")
            return None
    
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출
        title_elem = soup.find('h3') or soup.find('h2') or soup.find('h1')
        title = ""
        if title_elem:
            title = title_elem.get_text(strip=True)
        
        # 메타 정보 추출 (관리자, 등록일, 조회수)
        meta_info = {}
        
        # 관리자, 날짜, 조회수가 있는 영역 찾기
        meta_container = soup.find('div', class_=['post-meta', 'article-meta']) or soup.find('div', string=re.compile('관리자|등록일|조회'))
        if meta_container:
            meta_text = meta_container.get_text()
            # 정규식으로 메타 정보 추출
            admin_match = re.search(r'관리자', meta_text)
            date_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', meta_text)
            views_match = re.search(r'(\d+)', meta_text)
            
            if admin_match:
                meta_info['writer'] = '관리자'
            if date_match:
                meta_info['date'] = date_match.group(1)
            if views_match:
                meta_info['views'] = views_match.group(1)
        
        # 본문 내용 추출 - 상세 페이지 구조에 따라 조정
        content_sections = []
        
        # 본문이 포함된 요소들 찾기 (실제 사이트 구조에 따라 조정)
        content_elements = soup.find_all(['p', 'div'], class_=['content', 'article-content', 'post-content'])
        if not content_elements:
            # 특정 클래스가 없는 경우 모든 p 태그에서 내용 추출
            content_elements = soup.find_all('p')
        
        for elem in content_elements:
            text = elem.get_text(strip=True)
            if text and len(text) > 10:  # 의미있는 텍스트만
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
        
        # 첨부파일 섹션 찾기
        attachment_section = soup.find('h5', string=re.compile('첨부파일'))
        if attachment_section:
            # 첨부파일 링크들 찾기 (h5 다음의 ul 또는 인접 요소)
            attachment_container = attachment_section.find_next_sibling(['ul', 'div', 'p'])
            if attachment_container:
                links = attachment_container.find_all('a', href=True)
                for link in links:
                    href = link.get('href')
                    filename_elem = link.find('span') or link
                    filename = filename_elem.get_text(strip=True)
                    
                    if href and filename and not filename.startswith('다운로드'):
                        # 절대 URL 생성
                        file_url = urljoin(self.base_url, href)
                        
                        # 파일명 정리 (다운로드 텍스트 제거)
                        filename = re.sub(r'^다운로드\s*', '', filename).strip()
                        
                        attachments.append({
                            'filename': filename,
                            'url': file_url
                        })
                        logger.debug(f"첨부파일 발견: {filename}")
        
        # 추가: 다른 패턴의 첨부파일 링크 찾기
        if not attachments:
            # download 링크 패턴 찾기
            download_links = soup.find_all('a', href=re.compile(r'/download/'))
            for link in download_links:
                href = link.get('href')
                filename = link.get_text(strip=True)
                
                if href and filename:
                    file_url = urljoin(self.base_url, href)
                    
                    # 파일명 정리
                    filename = re.sub(r'^다운로드\s*', '', filename).strip()
                    if not filename:
                        filename = "첨부파일"
                    
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


def test_bsia_scraper(pages=3):
    """BSIA 스크래퍼 테스트"""
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    scraper = EnhancedBSIAScraper()
    output_dir = "output/bsia"
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"BSIA 스크래퍼 테스트 시작 - {pages}페이지")
    scraper.scrape_pages(max_pages=pages, output_base=output_dir)
    logger.info("스크래핑 완료")


if __name__ == "__main__":
    test_bsia_scraper(3)