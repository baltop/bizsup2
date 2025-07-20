#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BACF(부안군문화재단) 공지사항 스크래퍼
URL: https://www.bacf.or.kr/base/board/list?boardManagementNo=2&menuLevel=2&menuNo=18
"""

import re
import json
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup
from enhanced_base_scraper import EnhancedBaseScraper

logger = logging.getLogger(__name__)

class EnhancedBacfScraper(EnhancedBaseScraper):
    """BACF(부안군문화재단) 공지사항 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        
        # 사이트 기본 설정
        self.base_url = "https://www.bacf.or.kr"
        self.list_url = "https://www.bacf.or.kr/base/board/list"
        self.start_url = self.list_url
        
        # URL 파라미터 (고정값)
        self.base_params = {
            'boardManagementNo': '2',
            'menuLevel': '2',
            'menuNo': '18',
            'searchCategory': '',
            'searchType': '',
            'searchWord': ''
        }
        
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
        
        # SSL 인증서 검증 비활성화
        self.verify_ssl = False
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # 현재 상세 페이지 URL 저장 (Referer 용)
        self.current_detail_url = None
        
    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 생성"""
        params = self.base_params.copy()
        params['page'] = str(page_num)
        
        # URL 파라미터 문자열 생성
        param_str = '&'.join([f"{k}={v}" for k, v in params.items()])
        return f"{self.list_url}?{param_str}"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 공지사항 테이블 찾기
        table = soup.find('table')
        if not table:
            logger.warning("공지사항 테이블을 찾을 수 없습니다")
            return announcements
        
        # tbody 찾기
        tbody = table.find('tbody')
        if not tbody:
            logger.warning("테이블 tbody를 찾을 수 없습니다")
            return announcements
        
        # 각 행 처리
        rows = tbody.find_all('tr')
        logger.info(f"총 {len(rows)}개의 공고 행 발견")
        
        for i, row in enumerate(rows):
            try:
                # 셀 찾기
                cells = row.find_all(['td', 'th'])
                if len(cells) < 4:  # 최소 4개 셀 확인 (번호, 제목, 등록일, 조회)
                    continue
                
                # 컬럼 구조: 번호, 제목, 등록일, 조회
                number_cell = cells[0]
                title_cell = cells[1] 
                date_cell = cells[2]
                views_cell = cells[3]
                
                # 번호 처리
                number = number_cell.get_text(strip=True)
                if not number:
                    continue
                
                # 제목 및 링크 추출
                title_link = title_cell.find('a')
                if not title_link:
                    continue
                
                title = title_link.get_text(strip=True)
                if not title:
                    continue
                
                # 상세 페이지 URL 추출
                detail_url = title_link.get('href')
                if not detail_url:
                    continue
                
                # 절대 URL 생성
                detail_url = urljoin(self.base_url, detail_url)
                
                # 날짜 및 조회수 처리
                date = date_cell.get_text(strip=True) if date_cell else ''
                views = views_cell.get_text(strip=True) if views_cell else ''
                
                # 공고 정보 구성
                announcement = {
                    'number': number,
                    'title': title,
                    'url': detail_url,
                    'date': date,
                    'views': views,
                    'has_attachment': False  # 상세 페이지에서 확인
                }
                
                announcements.append(announcement)
                logger.debug(f"공고 파싱 완료: {title[:50]}...")
                
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
        title_element = soup.find('h3')
        if title_element:
            title_text = title_element.get_text(strip=True)
            if title_text:
                content_parts.append(f"# {title_text}")
        
        # 방법 2: 메타 정보 추출 (작성일, 조회수 등)
        meta_list = soup.find('ul')
        if meta_list:
            meta_items = meta_list.find_all('li')
            for item in meta_items:
                meta_text = item.get_text(strip=True)
                if meta_text and ('작성일' in meta_text or '조회' in meta_text):
                    content_parts.append(f"**{meta_text}**")
        
        # 방법 3: 본문 내용 추출 - 여러 방법 시도
        content_containers = [
            soup.find('div', class_='content'),
            soup.find('div', class_='board-content'),
            soup.find('div', class_='view-content'),
            soup.find('div', id='content'),
            soup.find('article'),
            soup.find('section')
        ]
        
        for container in content_containers:
            if container:
                # 첨부파일 섹션 제거
                for attachment_section in container.find_all(['div', 'section'], class_=lambda x: x and 'attach' in x.lower()):
                    attachment_section.decompose()
                
                # 본문 텍스트 추출
                paragraphs = container.find_all('p')
                if paragraphs:
                    for p in paragraphs:
                        text = p.get_text(strip=True)
                        if text and len(text) > 10:
                            content_parts.append(text)
                else:
                    # p 태그가 없으면 전체 텍스트 추출
                    text = container.get_text(strip=True)
                    if text and len(text) > 20:
                        content_parts.append(text)
                break
        
        # 방법 4: 전체 본문 영역에서 추출 (마지막 수단)
        if not content_parts or len(content_parts) <= 2:
            # 첨부파일 관련 요소 제거
            for unwanted in soup.find_all(['div', 'section'], class_=lambda x: x and ('attach' in x.lower() or 'file' in x.lower())):
                unwanted.decompose()
            
            # main 태그나 content 영역 찾기
            main_content = soup.find('main') or soup.find('div', id='main')
            if main_content:
                paragraphs = main_content.find_all('p')
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if text and len(text) > 20:
                        content_parts.append(text)
        
        # 최종 본문 구성
        if content_parts:
            return "\\n\\n".join(content_parts)
        else:
            return "본문 내용을 추출할 수 없습니다."
    
    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """첨부파일 추출"""
        attachments = []
        
        # 방법 1: 첨부파일 섹션 찾기
        attachment_sections = [
            soup.find('div', class_=lambda x: x and 'attach' in x.lower()),
            soup.find('div', class_=lambda x: x and 'file' in x.lower()),
            soup.find('section', class_=lambda x: x and 'attach' in x.lower()),
            soup.find('ul', class_=lambda x: x and 'attach' in x.lower())
        ]
        
        for section in attachment_sections:
            if section:
                file_links = section.find_all('a')
                logger.debug(f"첨부파일 섹션에서 {len(file_links)}개 링크 발견")
                
                for link in file_links:
                    href = link.get('href', '')
                    filename = link.get_text(strip=True)
                    
                    if href and filename:
                        # 절대 URL 생성
                        download_url = urljoin(self.base_url, href)
                        
                        # 파일 확장자 추출
                        file_ext = filename.split('.')[-1].upper() if '.' in filename else 'UNKNOWN'
                        
                        attachments.append({
                            'filename': filename,
                            'url': download_url,
                            'size': '',
                            'type': file_ext
                        })
                        logger.debug(f"첨부파일 추출 성공: {filename} - {download_url}")
                break
        
        # 방법 2: 일반적인 파일 다운로드 링크 찾기
        if not attachments:
            file_links = soup.find_all('a', href=re.compile(r'(download|file|attach)', re.I))
            logger.debug(f"일반 파일 링크 {len(file_links)}개 발견")
            
            for link in file_links:
                href = link.get('href', '')
                filename = link.get_text(strip=True)
                
                if href and filename:
                    # 절대 URL 생성
                    download_url = urljoin(self.base_url, href)
                    
                    # 파일 확장자 추출
                    file_ext = filename.split('.')[-1].upper() if '.' in filename else 'UNKNOWN'
                    
                    attachments.append({
                        'filename': filename,
                        'url': download_url,
                        'size': '',
                        'type': file_ext
                    })
                    logger.debug(f"일반 파일 링크 추출: {filename} - {download_url}")
        
        # 방법 3: 특정 파일 확장자 링크 찾기
        if not attachments:
            file_extensions = ['pdf', 'hwp', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'jpg', 'jpeg', 'png', 'gif', 'zip', 'rar']
            for ext in file_extensions:
                file_links = soup.find_all('a', href=re.compile(rf'\.{ext}', re.I))
                for link in file_links:
                    href = link.get('href', '')
                    filename = link.get_text(strip=True) or f"attachment.{ext}"
                    
                    if href:
                        # 절대 URL 생성
                        download_url = urljoin(self.base_url, href)
                        
                        attachments.append({
                            'filename': filename,
                            'url': download_url,
                            'size': '',
                            'type': ext.upper()
                        })
                        logger.debug(f"확장자 기반 파일 추출: {filename} - {download_url}")
        
        logger.info(f"첨부파일 {len(attachments)}개 추출")
        return attachments


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
            logging.FileHandler('bacf_scraper.log', encoding='utf-8')
        ]
    )
    
    logger.info("="*60)
    logger.info("🚀 BACF(부안군문화재단) 공지사항 스크래퍼 시작")
    logger.info("="*60)
    
    # 출력 디렉토리 설정
    output_dir = "output/bacf"
    
    # 기존 출력 디렉토리 정리 (파일만 삭제, 디렉토리 구조 유지)
    if os.path.exists(output_dir):
        import shutil
        logger.info(f"기존 출력 디렉토리 정리: {output_dir}")
        shutil.rmtree(output_dir)
    
    # 스크래퍼 초기화
    scraper = EnhancedBacfScraper()
    
    try:
        # 3페이지 수집 실행
        success = scraper.scrape_pages(max_pages=3, output_base="output/bacf")
        
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