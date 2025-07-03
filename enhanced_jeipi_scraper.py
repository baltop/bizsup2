#!/usr/bin/env python3
"""
JEIPI (전라남도환경산업진흥원) Enhanced Scraper
- URL: https://www.jeipi.or.kr/rainboard/rain.php?rBoard=notice
- Site Code: jeipi
- 개발일: 2025-07-03
"""

import os
import re
import time
import hashlib
import requests
from urllib.parse import urljoin, quote, unquote, parse_qs, urlparse
from bs4 import BeautifulSoup
from typing import Dict, List, Any, Optional
import logging

# Enhanced Base Scraper Import
from enhanced_base_scraper import StandardTableScraper

# 로거 설정
logger = logging.getLogger(__name__)

class EnhancedJeipiScraper(StandardTableScraper):
    """JEIPI 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        # 기본 설정
        self.base_url = "https://www.jeipi.or.kr"
        self.list_url = "https://www.jeipi.or.kr/rainboard/rain.php?rBoard=notice"
        
        # JEIPI 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 2
        
        # 세션 설정 (robots.txt 무시)
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def get_list_url(self, page_num: int) -> str:
        """페이지별 목록 URL 생성"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}&page={page_num}"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # JEIPI 테이블 구조: table with thead/tbody
        table = soup.find('table')
        if not table:
            logger.warning("목록 테이블을 찾을 수 없습니다")
            return announcements
        
        tbody = table.find('tbody')
        if not tbody:
            logger.warning("테이블 tbody를 찾을 수 없습니다")
            return announcements
        
        for i, row in enumerate(tbody.find_all('tr'), 1):
            try:
                cells = row.find_all('td')
                if len(cells) < 5:  # 번호, 제목, 글쓴이, 날짜, 조회
                    continue
                
                # 1. 번호 (첫 번째 셀) - 공지 여부 확인
                number_cell = cells[0]
                number = number_cell.get_text(strip=True)
                is_notice = 'bo_notice' in row.get('class', [])
                
                if is_notice:
                    number = "공지"
                elif not number:
                    number = f"row_{i}"
                
                # 2. 제목 (두 번째 셀) - 링크 정보 추출
                title_cell = cells[1]
                title_link = title_cell.find('a')
                
                if not title_link:
                    continue
                
                title = title_link.get_text(strip=True)
                href = title_link.get('href', '')
                
                # URL에서 wr_id 추출
                parsed_url = urlparse(href)
                query_params = parse_qs(parsed_url.query)
                wr_id = query_params.get('wr_id', [''])[0]
                
                if not wr_id:
                    logger.warning(f"wr_id를 찾을 수 없습니다: {href}")
                    continue
                
                detail_url = href if href.startswith('http') else urljoin(self.base_url, href)
                
                # 첨부파일 여부 확인
                has_attachment = title_cell.find('img', alt='첨부파일') is not None
                
                # 3. 글쓴이 (세 번째 셀)
                writer_cell = cells[2]
                writer = writer_cell.get_text(strip=True)
                
                # 4. 날짜 (네 번째 셀)
                date_cell = cells[3]
                date = date_cell.get_text(strip=True)
                
                # 5. 조회수 (다섯 번째 셀)
                views_cell = cells[4]
                views = views_cell.get_text(strip=True)
                
                # 공고 정보 구성
                announcement = {
                    'number': number,
                    'title': title,
                    'url': detail_url,
                    'writer': writer,
                    'date': date,
                    'views': views,
                    'wr_id': wr_id,
                    'has_attachment': has_attachment,
                    'is_notice': is_notice,
                    'attachments': []  # 상세 페이지에서 처리
                }
                
                # 공고 추가
                announcements.append(announcement)
                logger.info(f"공고 추가: [{number}] {title}")
                
            except Exception as e:
                logger.error(f"공고 파싱 중 오류 (행 {i}): {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개 공고를 파싱했습니다")
        return announcements
    
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        try:
            # 본문 내용 추출 - 본문 영역 찾기
            content_sections = []
            
            # 본문 내용이 들어있을 수 있는 영역들 시도
            content_areas = [
                soup.find('div', class_='view_content'),
                soup.find('div', class_='bo_content'),
                soup.find('div', id='bo_v_con'),
                soup.find('td', class_='td_content'),
            ]
            
            content = ""
            for area in content_areas:
                if area:
                    content = area.get_text(strip=True)
                    if content and len(content) > 50:  # 의미있는 내용이 있으면
                        break
            
            if not content:
                # 대체 방법: 페이지에서 긴 텍스트 찾기
                all_text = soup.get_text()
                lines = [line.strip() for line in all_text.split('\n') if line.strip()]
                content_lines = [line for line in lines if len(line) > 30]
                content = '\n\n'.join(content_lines[:10]) if content_lines else "본문 내용을 추출할 수 없습니다."
            
            # 첨부파일 정보 추출
            attachments = self._extract_attachments(soup)
            
            return {
                'content': content,
                'attachments': attachments
            }
            
        except Exception as e:
            logger.error(f"상세 페이지 파싱 중 오류: {e}")
            return {
                'content': "파싱 오류로 인해 내용을 추출할 수 없습니다.",
                'attachments': []
            }
    
    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """첨부파일 정보 추출"""
        attachments = []
        
        try:
            # download.php 링크를 찾는 다양한 방법 시도
            download_links = soup.find_all('a', href=re.compile(r'download\.php'))
            
            for i, link in enumerate(download_links):
                try:
                    href = link.get('href', '')
                    if not href:
                        continue
                    
                    # 파일 다운로드 URL 구성
                    download_url = href if href.startswith('http') else urljoin(self.base_url, href)
                    
                    # 파일명 추출 - 링크 텍스트에서
                    file_text = link.get_text(strip=True)
                    
                    # 파일명과 크기 분리
                    size_match = re.search(r'\(([^)]+)\)$', file_text)
                    if size_match:
                        file_size = size_match.group(1)
                        filename = file_text.replace(size_match.group(0), '').strip()
                    else:
                        file_size = "Unknown"
                        filename = file_text
                    
                    if not filename:
                        filename = f"attachment_{i+1}.bin"
                    
                    attachment = {
                        'url': download_url,
                        'filename': filename,
                        'size': file_size
                    }
                    
                    attachments.append(attachment)
                    logger.info(f"첨부파일 발견: {filename} ({file_size})")
                    
                except Exception as e:
                    logger.error(f"첨부파일 {i} 처리 중 오류: {e}")
                    continue
            
            if not attachments:
                logger.debug("첨부파일이 없습니다")
            else:
                logger.info(f"총 {len(attachments)}개 첨부파일 발견")
            
        except Exception as e:
            logger.error(f"첨부파일 추출 중 오류: {e}")
        
        return attachments
    
    def download_file(self, url: str, save_path: str, attachment_info: Dict[str, Any] = None) -> bool:
        """JEIPI 파일 다운로드"""
        try:
            logger.debug(f"파일 다운로드 시도: {save_path}")
            
            # 파일 다운로드 GET 요청
            response = self.session.get(
                url,
                timeout=self.timeout,
                verify=self.verify_ssl,
                stream=True
            )
            
            if response.status_code == 200:
                # 파일 저장
                with open(save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                file_size = os.path.getsize(save_path)
                logger.info(f"파일 다운로드 완료: {os.path.basename(save_path)} ({file_size:,} bytes)")
                return True
            else:
                logger.error(f"파일 다운로드 실패: {os.path.basename(save_path)} (Status: {response.status_code})")
                return False
                
        except Exception as e:
            logger.error(f"파일 다운로드 중 오류: {e}")
            return False
    
    def _extract_fallback_content(self, soup: BeautifulSoup) -> str:
        """대체 본문 추출 방법"""
        try:
            # 전체 텍스트에서 의미있는 부분 추출
            text_lines = []
            for element in soup.find_all(['p', 'div', 'span']):
                text = element.get_text(strip=True)
                if text and len(text) > 20 and text not in text_lines:
                    text_lines.append(text)
            
            if text_lines:
                return '\n\n'.join(text_lines[:5])
            
            return "본문 내용을 추출할 수 없습니다."
            
        except Exception as e:
            logger.error(f"대체 본문 추출 중 오류: {e}")
            return "본문 추출 중 오류가 발생했습니다."

def test_jeipi_scraper(pages: int = 3):
    """JEIPI 스크래퍼 테스트"""
    print("=== JEIPI 스크래퍼 테스트 시작 ===")
    
    scraper = EnhancedJeipiScraper()
    output_dir = "output/jeipi"
    
    # 출력 디렉토리 생성
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # 스크래핑 실행
        scraper.scrape_pages(max_pages=pages, output_base=output_dir)
        
        print(f"\n=== JEIPI 스크래퍼 테스트 완료 ===")
        print(f"결과 확인: {output_dir} 디렉토리")
        
    except Exception as e:
        print(f"테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_jeipi_scraper(3)