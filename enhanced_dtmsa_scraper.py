#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DTMSA(대구전통시장진흥재단) 공지사항 스크래퍼
URL: https://www.dtmsa.or.kr/announcements
"""

import re
import json
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup
from enhanced_base_scraper import EnhancedBaseScraper

logger = logging.getLogger(__name__)

class EnhancedDtmsaScraper(EnhancedBaseScraper):
    """DTMSA(대구전통시장진흥재단) 공지사항 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        
        # 사이트 기본 설정
        self.base_url = "https://www.dtmsa.or.kr"
        self.list_url = "https://www.dtmsa.or.kr/announcements"
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
        
    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 생성"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}?page={page_num}"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 실제 HTML 구조 확인을 위한 디버깅
        logger.debug(f"HTML 구조 확인: {html_content[:500]}...")
        
        # 공지사항 목록 찾기 - 실제 HTML에서는 list 태그가 아닌 다른 구조일 수 있음
        # 브라우저에서 확인한 바로는 list > listitem > link 구조
        
        # 방법 1: 직접 list 태그 찾기
        announcement_list = soup.find('list', recursive=True)
        if announcement_list:
            logger.debug("list 태그 발견")
            list_items = announcement_list.find_all('listitem')
            logger.debug(f"listitem 개수: {len(list_items)}")
            
            for i, item in enumerate(list_items):
                try:
                    # 각 항목에서 링크 찾기
                    link_element = item.find('link')
                    if not link_element:
                        continue
                    
                    # 링크 텍스트에서 정보 추출
                    link_text = link_element.get_text(strip=True)
                    if not link_text:
                        continue
                    
                    # URL 추출
                    detail_url = link_element.get('href')
                    if not detail_url:
                        continue
                    
                    # 절대 URL 생성
                    detail_url = urljoin(self.base_url, detail_url)
                    
                    # 링크 텍스트 파싱 (예: "809 공지 2025 동성로 리빙랩 프로그램 참가자 모집 (연장 공고) 2025.7.10 289")
                    # 또는 "812 [유관공고] 폐업·휴업(예정) 소상공인 재기지원 심리회복 산림치유프로그램 모집 안 2025.7.18 7"
                    
                    # 번호 추출 (첫 번째 숫자)
                    number_match = re.match(r'^(\d+)', link_text)
                    number = number_match.group(1) if number_match else str(i + 1)
                    
                    # 날짜 추출 (YYYY.M.D 형태)
                    date_match = re.search(r'(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})', link_text)
                    date = f"{date_match.group(1)}.{date_match.group(2)}.{date_match.group(3)}" if date_match else ''
                    
                    # 조회수 추출 (마지막 숫자)
                    views_match = re.search(r'(\d+)$', link_text)
                    views = views_match.group(1) if views_match else ''
                    
                    # 제목 추출 (번호 이후부터 날짜 이전까지)
                    title_start = len(number) + 1 if number_match else 0
                    title_end = date_match.start() if date_match else len(link_text)
                    title = link_text[title_start:title_end].strip()
                    
                    # 조회수 부분 제거
                    if views_match:
                        title = title.replace(views_match.group(0), '').strip()
                    
                    # 공지사항 정보 구성
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
        
        # 방법 2: 일반적인 HTML 구조로 찾기 (기본 HTML 태그 사용)
        if not announcements:
            logger.debug("list 태그에서 공고를 찾을 수 없음. 일반 HTML 구조로 시도")
            
            # 일반적인 링크 패턴으로 찾기
            all_links = soup.find_all('a', href=re.compile(r'/announcement/\d+'))
            logger.debug(f"announcement 링크 개수: {len(all_links)}")
            
            for i, link in enumerate(all_links):
                try:
                    link_text = link.get_text(strip=True)
                    if not link_text:
                        continue
                    
                    detail_url = link.get('href')
                    if not detail_url:
                        continue
                    
                    # 절대 URL 생성
                    detail_url = urljoin(self.base_url, detail_url)
                    
                    # 링크 텍스트 파싱
                    number_match = re.match(r'^(\d+)', link_text)
                    number = number_match.group(1) if number_match else str(i + 1)
                    
                    date_match = re.search(r'(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})', link_text)
                    date = f"{date_match.group(1)}.{date_match.group(2)}.{date_match.group(3)}" if date_match else ''
                    
                    views_match = re.search(r'(\d+)$', link_text)
                    views = views_match.group(1) if views_match else ''
                    
                    # 제목 추출 개선
                    title = link_text
                    if number_match:
                        title = title[len(number):].strip()
                    if date_match:
                        title = title[:title.find(date_match.group(0))].strip()
                    if views_match:
                        title = title.replace(views_match.group(0), '').strip()
                    
                    # 제목 정리
                    title = re.sub(r'\s+', ' ', title).strip()  # 여러 공백을 하나로
                    
                    announcement = {
                        'number': number,
                        'title': title,
                        'url': detail_url,
                        'date': date,
                        'views': views,
                        'has_attachment': False
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
        
        # 방법 1: 제목 추출 (table 구조에서)
        title_rows = soup.find_all('row')
        for row in title_rows:
            row_text = row.get_text(strip=True)
            if row_text and len(row_text) > 5 and not '작성일' in row_text and not '조회수' in row_text and not '첨부파일' in row_text:
                content_parts.append(f"# {row_text}")
                break
        
        # 방법 2: 메타 정보 추출 (작성일, 조회수 등)
        meta_rows = soup.find_all('row')
        for row in meta_rows:
            row_text = row.get_text(strip=True)
            if '작성일' in row_text or '조회수' in row_text:
                content_parts.append(f"**{row_text}**")
        
        # 방법 3: 본문 내용 추출 - 테이블 구조 기반
        content_found = False
        for row in soup.find_all('row'):
            cell = row.find('cell')
            if cell:
                # 첨부파일 링크가 있는 셀은 건너뛰기
                if cell.find('link') and ('첨부' in cell.get_text() or '.hwp' in cell.get_text() or '.pdf' in cell.get_text()):
                    continue
                
                # 본문 내용이 있는 셀 찾기
                cell_text = cell.get_text(strip=True)
                if cell_text and len(cell_text) > 50:  # 충분히 긴 텍스트
                    # generic 태그들 내부의 텍스트 추출
                    generics = cell.find_all('generic')
                    for generic in generics:
                        text = generic.get_text(strip=True)
                        if text and len(text) > 10:
                            content_parts.append(text)
                    content_found = True
                    break
        
        # 방법 4: 전체 본문 영역에서 추출 (마지막 수단)
        if not content_found:
            # 전체 페이지에서 의미있는 텍스트 찾기
            for element in soup.find_all(['p', 'div', 'article', 'section']):
                text = element.get_text(strip=True)
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
        
        # 방법 1: 첨부파일 링크 찾기 (테이블 구조에서)
        for row in soup.find_all('row'):
            cell = row.find('cell')
            if cell:
                # 첨부파일 링크가 있는 셀 찾기
                file_links = cell.find_all('link')
                for link in file_links:
                    link_text = link.get_text(strip=True)
                    href = link.get('href')
                    
                    # 파일 확장자나 다운로드 관련 키워드 확인
                    if href and any(ext in link_text.lower() for ext in ['.hwp', '.pdf', '.doc', '.xls', '.png', '.jpg', '.zip']):
                        # 절대 URL 생성
                        download_url = urljoin(self.base_url, href)
                        
                        # 파일명 추출
                        filename = link_text.strip()
                        if filename:
                            # 파일 크기 정보 제거 (예: "( 88KB)" 부분)
                            filename = re.sub(r'\s*\(\s*[\d.]+\s*[KMG]?B\s*\)', '', filename)
                            
                            # 파일 확장자 추출
                            file_ext = filename.split('.')[-1].upper() if '.' in filename else 'UNKNOWN'
                            
                            attachments.append({
                                'filename': filename,
                                'url': download_url,
                                'size': '',
                                'type': file_ext
                            })
                            logger.debug(f"첨부파일 추출 성공: {filename} - {download_url}")
        
        # 방법 2: 일반적인 파일 다운로드 링크 찾기
        if not attachments:
            # 일반적인 <a> 태그에서 다운로드 링크 찾기
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link.get('href', '')
                link_text = link.get_text(strip=True)
                
                # 다운로드 관련 URL 패턴 확인
                if 'download' in href.lower() or 'fileDownload' in href:
                    # 절대 URL 생성
                    download_url = urljoin(self.base_url, href)
                    
                    # 파일명 추출
                    filename = link_text.strip()
                    if filename:
                        # 파일 크기 정보 제거
                        filename = re.sub(r'\s*\(\s*[\d.]+\s*[KMG]?B\s*\)', '', filename)
                        
                        # 파일 확장자 추출
                        file_ext = filename.split('.')[-1].upper() if '.' in filename else 'UNKNOWN'
                        
                        attachments.append({
                            'filename': filename,
                            'url': download_url,
                            'size': '',
                            'type': file_ext
                        })
                        logger.debug(f"일반 파일 링크 추출: {filename} - {download_url}")
        
        # 방법 3: 브라우저 스냅샷에서 확인한 다운로드 링크 패턴
        if not attachments:
            # /common/fileDownload/ 패턴 찾기
            download_links = soup.find_all('a', href=re.compile(r'/common/fileDownload/'))
            logger.debug(f"fileDownload 패턴 링크 {len(download_links)}개 발견")
            
            for link in download_links:
                href = link.get('href', '')
                filename = link.get_text(strip=True)
                
                if href and filename:
                    # 절대 URL 생성
                    download_url = urljoin(self.base_url, href)
                    
                    # 파일 크기 정보 제거
                    filename = re.sub(r'\s*\(\s*[\d.]+\s*[KMG]?B\s*\)', '', filename)
                    
                    # 파일 확장자 추출
                    file_ext = filename.split('.')[-1].upper() if '.' in filename else 'UNKNOWN'
                    
                    attachments.append({
                        'filename': filename,
                        'url': download_url,
                        'size': '',
                        'type': file_ext
                    })
                    logger.debug(f"fileDownload 패턴 파일 추출: {filename} - {download_url}")
        
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
            logging.FileHandler('dtmsa_scraper.log', encoding='utf-8')
        ]
    )
    
    logger.info("="*60)
    logger.info("🚀 DTMSA(대구전통시장진흥재단) 공지사항 스크래퍼 시작")
    logger.info("="*60)
    
    # 출력 디렉토리 설정
    output_dir = "output/dtmsa"
    
    # 기존 출력 디렉토리 정리 (파일만 삭제, 디렉토리 구조 유지)
    if os.path.exists(output_dir):
        import shutil
        logger.info(f"기존 출력 디렉토리 정리: {output_dir}")
        shutil.rmtree(output_dir)
    
    # 스크래퍼 초기화
    scraper = EnhancedDtmsaScraper()
    
    try:
        # 3페이지 수집 실행
        success = scraper.scrape_pages(max_pages=3, output_base="output/dtmsa")
        
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