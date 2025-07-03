#!/usr/bin/env python3
"""
JEXPORT (전라남도수출지원센터) Enhanced Scraper
- URL: https://www.jexport.or.kr/user/reg_biz
- Site Code: jexport
- 개발일: 2025-07-03
"""

import os
import re
import time
import hashlib
import requests
from urllib.parse import urljoin, quote, unquote
from bs4 import BeautifulSoup
from typing import Dict, List, Any, Optional
import logging

# Enhanced Base Scraper Import
from enhanced_base_scraper import StandardTableScraper

# 로거 설정
logger = logging.getLogger(__name__)

class EnhancedJexportScraper(StandardTableScraper):
    """JEXPORT 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        # 기본 설정
        self.base_url = "https://www.jexport.or.kr"
        self.list_url = "https://www.jexport.or.kr/user/reg_biz"
        
        # JEXPORT 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 2
        
        # 세션 설정
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
            return f"{self.list_url}?page={page_num}"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # JEXPORT 테이블 구조: table.dcTBJN
        table = soup.find('table', class_='dcTBJN')
        if not table:
            logger.warning("목록 테이블을 찾을 수 없습니다")
            # 디버그: 다른 테이블들 찾아보기
            all_tables = soup.find_all('table')
            logger.debug(f"찾은 테이블 수: {len(all_tables)}")
            for i, tbl in enumerate(all_tables):
                logger.debug(f"테이블 {i}: {tbl.get('class')}")
            return announcements
        
        tbody = table.find('tbody')
        if not tbody:
            logger.warning("테이블 tbody를 찾을 수 없습니다")
            return announcements
        
        for i, row in enumerate(tbody.find_all('tr'), 1):
            try:
                cells = row.find_all('td')
                if len(cells) < 4:
                    continue
                
                # 1. 상태 (첫 번째 셀)
                status_cell = cells[0]
                status = status_cell.get_text(strip=True)
                
                # 2. 사업명 (두 번째 셀) - 링크가 있는 제목
                title_cell = cells[1]
                title_link = title_cell.find('a')
                
                if not title_link:
                    continue
                
                title = title_link.get_text(strip=True)
                
                # JavaScript 함수에서 project_no 추출 (href 속성에서)
                href = title_link.get('href', '')
                project_no_match = re.search(r"f_detail\('([^']+)'\)", href)
                if not project_no_match:
                    logger.warning(f"프로젝트 번호를 찾을 수 없습니다: {href}")
                    logger.debug(f"전체 링크: {title_link}")
                    continue
                
                project_no = project_no_match.group(1)
                detail_url = f"{self.base_url}/user/reg_biz/detail?project_no={project_no}&page=1"
                
                # 3. 공고기간 (세 번째 셀)
                notice_period = cells[2].get_text(strip=True)
                
                # 4. 접수기간 (네 번째 셀)  
                reception_period = cells[3].get_text(strip=True)
                
                # 공고 정보 구성
                announcement = {
                    'number': f"row_{i}",
                    'title': title,
                    'url': detail_url,
                    'status': status,
                    'notice_period': notice_period,
                    'reception_period': reception_period,
                    'project_no': project_no,
                    'attachments': []  # 상세 페이지에서 처리
                }
                
                # 공고 추가
                announcements.append(announcement)
                logger.info(f"공고 추가: [{announcement['number']}] {title}")
                
            except Exception as e:
                logger.error(f"공고 파싱 중 오류 (행 {i}): {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개 공고를 파싱했습니다")
        return announcements
    
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        try:
            # 본문 내용 추출 - dcRegBizDetail 영역
            content_sections = []
            detail_section = soup.find('div', class_='dcRegBizDetail')
            
            if detail_section:
                for section in detail_section.find_all('div', class_='dcRegBizCon'):
                    title_elem = section.find('h4', class_='dcH4Title')
                    content_elem = section.find('div', class_='dcDetailBox')
                    
                    if title_elem and content_elem:
                        section_title = title_elem.get_text(strip=True)
                        section_content = content_elem.get_text(strip=True)
                        content_sections.append(f"## {section_title}\n\n{section_content}\n")
            
            # 첨부파일 정보 추출
            attachments = self._extract_attachments(soup)
            
            # 본문을 마크다운으로 구성
            if content_sections:
                content = '\n'.join(content_sections)
            else:
                # 대체 본문 추출
                content = self._extract_fallback_content(soup)
            
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
            # 첨부파일 테이블에서 onclick 함수 찾기 - dcRegBizPeriod 영역
            period_table = soup.find('div', class_='dcRegBizPeriod')
            if period_table:
                # onclick 속성이 있는 모든 링크 찾기
                file_links = period_table.find_all('a', onclick=True)
                
                for link in file_links:
                    onclick = link.get('onclick', '')
                    
                    # file_download 함수에서 프로젝트 번호 추출
                    download_match = re.search(r"file_download\('([^']+)'\)", onclick)
                    if download_match:
                        project_no = download_match.group(1)
                        file_name = link.get_text(strip=True)
                        
                        # 다운로드 URL 구성
                        download_url = f"{self.base_url}/user/reg_biz/file_download"
                        
                        attachment = {
                            'url': download_url,
                            'filename': file_name,
                            'project_no': project_no
                        }
                        
                        attachments.append(attachment)
                        logger.info(f"첨부파일 발견: {file_name} (project_no: {project_no})")
            
            if not attachments:
                logger.debug("첨부파일이 없습니다")
            else:
                logger.info(f"총 {len(attachments)}개 첨부파일 발견")
            
        except Exception as e:
            logger.error(f"첨부파일 추출 중 오류: {e}")
        
        return attachments
    
    def download_file(self, url: str, save_path: str, attachment_info: Dict[str, Any] = None) -> bool:
        """JEXPORT 파일 다운로드 (POST 요청 방식)"""
        try:
            if not attachment_info:
                logger.error("첨부파일 정보가 없습니다")
                return False
                
            project_no = attachment_info.get('project_no', '')
            if not project_no:
                logger.error(f"프로젝트 번호가 없습니다: {attachment_info}")
                return False
            
            # POST 데이터 구성
            post_data = {
                'project_no': project_no
            }
            
            # 파일 다운로드 POST 요청
            logger.debug(f"파일 다운로드 시도: {save_path}")
            response = self.session.post(
                url,
                data=post_data,
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
            # 전체 컨텐츠 영역에서 텍스트 추출
            content_div = soup.find('div', id='diCon')
            if content_div:
                # 제목과 기본 정보 제외하고 본문만 추출
                texts = []
                for p in content_div.find_all(['p', 'div', 'span']):
                    text = p.get_text(strip=True)
                    if text and len(text) > 10:  # 의미있는 텍스트만
                        texts.append(text)
                
                return '\n\n'.join(texts[:5])  # 상위 5개 문단만
            
            return "본문 내용을 추출할 수 없습니다."
            
        except Exception as e:
            logger.error(f"대체 본문 추출 중 오류: {e}")
            return "본문 추출 중 오류가 발생했습니다."

def test_jexport_scraper(pages: int = 3):
    """JEXPORT 스크래퍼 테스트"""
    print("=== JEXPORT 스크래퍼 테스트 시작 ===")
    
    scraper = EnhancedJexportScraper()
    output_dir = "output/jexport"
    
    # 출력 디렉토리 생성
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # 스크래핑 실행
        scraper.scrape_pages(max_pages=pages, output_base=output_dir)
        
        print(f"\n=== JEXPORT 스크래퍼 테스트 완료 ===")
        print(f"결과 확인: {output_dir} 디렉토리")
        
    except Exception as e:
        print(f"테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_jexport_scraper(3)  # 3페이지 테스트