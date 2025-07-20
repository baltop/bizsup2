#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KEPCO(한국전력공사) 공지사항 스크래퍼
URL: https://home.kepco.co.kr/kepco/CY/K/ntcob/list.do?boardSeq=21069447&parnScrpSeq=21069447&depth=0&boardNo=0&boardCd=BRD_000039&replyRole=&pageIndex=1&searchKeyword=&searchCondition=&menuCd=FN02070501
"""

import re
import json
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup
from enhanced_base_scraper import EnhancedBaseScraper

logger = logging.getLogger(__name__)

class EnhancedKepcoScraper(EnhancedBaseScraper):
    """KEPCO(한국전력공사) 공지사항 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        
        # 사이트 기본 설정
        self.base_url = "https://home.kepco.co.kr"
        self.list_url = "https://home.kepco.co.kr/kepco/CY/K/ntcob/list.do"
        self.start_url = self.list_url
        
        # URL 파라미터 (고정값)
        self.base_params = {
            'boardSeq': '21069447',
            'parnScrpSeq': '21069447',
            'depth': '0',
            'boardNo': '0',
            'boardCd': 'BRD_000039',
            'replyRole': '',
            'searchKeyword': '',
            'searchCondition': 'total',
            'menuCd': 'FN02070501'
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
        
        # 현재 상세 페이지 URL 저장 (Referer 용)
        self.current_detail_url = None
        
    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 생성"""
        params = self.base_params.copy()
        params['pageIndex'] = str(page_num)
        
        # URL 파라미터 문자열 생성
        param_str = '&'.join([f"{k}={v}" for k, v in params.items()])
        return f"{self.list_url}?{param_str}"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 공지사항 테이블 찾기 (table.list)
        table = soup.find('table', class_='list')
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
                # 번호 셀 (th)
                number_cell = row.find('th')
                if not number_cell:
                    continue
                
                # 나머지 셀들 (td)
                cells = row.find_all('td')
                if len(cells) < 4:  # 최소 4개 td 확인
                    continue
                
                # 컬럼 구조: 번호(th), 제목(td.tit), 첨부(td.down), 작성일(td), 조회수(td)
                title_cell = cells[0]  # td.tit
                attachment_cell = cells[1]  # td.down
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
                
                # JavaScript 링크에서 boardSeq 추출
                onclick = title_link.get('onclick', '')
                if not onclick or 'fncGoView' not in onclick:
                    continue
                
                # fncGoView('21069731') 형태에서 boardSeq 추출
                match = re.search(r"fncGoView\('(\d+)'\)", onclick)
                if not match:
                    continue
                
                board_seq = match.group(1)
                
                # 상세 페이지 URL 구성
                detail_params = self.base_params.copy()
                detail_params['pageIndex'] = '1'
                detail_params['boardSeq'] = board_seq
                
                param_str = '&'.join([f"{k}={v}" for k, v in detail_params.items()])
                detail_url = f"{self.base_url}/kepco/CY/K/ntcob/ntcobView.do?{param_str}"
                
                # 첨부파일 여부 확인
                has_attachment = bool(attachment_cell.find('a'))
                
                # 공고 정보 구성
                announcement = {
                    'number': number,
                    'title': title,
                    'url': detail_url,
                    'board_seq': board_seq,
                    'date': date_cell.get_text(strip=True) if date_cell else '',
                    'views': views_cell.get_text(strip=True) if views_cell else '',
                    'has_attachment': has_attachment
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
        
        # 방법 1: 게시글 제목 추출 (dt 태그, 두 번째 dt 요소)
        dt_elements = soup.find_all('dt')
        if len(dt_elements) >= 2:
            title_elem = dt_elements[1]
            title_text = title_elem.get_text(strip=True)
            if title_text:
                content_parts.append(f"# {title_text}")
        
        # 방법 2: 메타데이터 테이블 추출
        meta_table = soup.find('table', attrs={'caption': lambda x: x and '게시판' in x})
        if meta_table:
            rows = meta_table.find_all('tr')
            for row in rows:
                cells = row.find_all(['th', 'td'])
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)
                    if key and value:
                        content_parts.append(f"**{key}**: {value}")
        
        # 방법 3: 본문 내용 추출 (dd.view_cont div.cont)
        content_container = soup.find('dd', class_='view_cont')
        if content_container:
            content_div = content_container.find('div', class_='cont')
            if content_div:
                # 첨부파일 링크 제거
                for file_link in content_div.find_all('a', href=re.compile(r'FileDownSecure\.do')):
                    file_link.decompose()
                
                # 본문 텍스트 추출
                paragraphs = content_div.find_all('p')
                if paragraphs:
                    for p in paragraphs:
                        text = p.get_text(strip=True)
                        if text and len(text) > 10:
                            content_parts.append(text)
                else:
                    # p 태그가 없으면 전체 텍스트 추출
                    text = content_div.get_text(strip=True)
                    if text and len(text) > 10:
                        content_parts.append(text)
        
        # 방법 4: dd.view_cont 전체에서 추출
        if not content_parts or len(content_parts) <= 2:
            view_cont = soup.find('dd', class_='view_cont')
            if view_cont:
                # 첨부파일 섹션 제거
                for file_section in view_cont.find_all('dd', class_='file'):
                    file_section.decompose()
                
                text = view_cont.get_text(strip=True)
                if text and len(text) > 20:
                    content_parts.append(text)
        
        # 방법 5: 단락별 추출 (마지막 수단)
        if not content_parts or len(content_parts) <= 2:
            paragraphs = soup.find_all('p')
            for p in paragraphs:
                text = p.get_text(strip=True)
                if text and len(text) > 20:
                    content_parts.append(text)
        
        # 최종 본문 구성
        if content_parts:
            return "\n\n".join(content_parts)
        else:
            return "본문 내용을 추출할 수 없습니다."
    
    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """첨부파일 추출"""
        attachments = []
        
        # 방법 1: dd.file 섹션에서 첨부파일 찾기
        file_section = soup.find('dd', class_='file')
        if file_section:
            file_links = file_section.find_all('a', href=re.compile(r'FileDownSecure\.do'))
            logger.debug(f"dd.file 섹션에서 {len(file_links)}개 링크 발견")
            
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
        
        # 방법 2: 전체 페이지에서 FileDownSecure.do 링크 찾기
        if not attachments:
            file_links = soup.find_all('a', href=re.compile(r'FileDownSecure\.do'))
            logger.debug(f"전체 페이지에서 FileDownSecure.do 링크 {len(file_links)}개 발견")
            
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
        
        # 방법 3: JavaScript onclick 패턴 찾기
        if not attachments:
            onclick_links = soup.find_all('a', onclick=re.compile(r'FileDownSecure\.do'))
            logger.debug(f"JavaScript onclick 링크 {len(onclick_links)}개 발견")
            
            for link in onclick_links:
                onclick = link.get('onclick', '')
                filename = link.get_text(strip=True)
                
                # location.href='/kepco/cmmn/fms/FileDownSecure.do?...' 패턴 추출
                match = re.search(r"location\.href='([^']*FileDownSecure\.do[^']*)'", onclick)
                if match:
                    download_url = urljoin(self.base_url, match.group(1))
                    
                    # 파일명이 없으면 기본 이름 사용
                    if not filename:
                        filename = f"attachment_{len(attachments) + 1}.file"
                    
                    # 파일 확장자 추출
                    file_ext = filename.split('.')[-1].upper() if '.' in filename else 'UNKNOWN'
                    
                    attachments.append({
                        'filename': filename,
                        'url': download_url,
                        'size': '',
                        'type': file_ext
                    })
                    logger.debug(f"JavaScript 첨부파일 추출: {filename} - {download_url}")
        
        logger.info(f"첨부파일 {len(attachments)}개 추출")
        return attachments
    
    # KEPCO 스크래퍼는 base scraper의 download_file을 사용합니다
    # 필요시 current_detail_url이 Referer로 자동 설정됩니다


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
            logging.FileHandler('kepco_scraper.log', encoding='utf-8')
        ]
    )
    
    logger.info("="*60)
    logger.info("🚀 KEPCO(한국전력공사) 공지사항 스크래퍼 시작")
    logger.info("="*60)
    
    # 출력 디렉토리 설정
    output_dir = "output/kepco"
    
    # 기존 출력 디렉토리 정리 (파일만 삭제, 디렉토리 구조 유지)
    if os.path.exists(output_dir):
        import shutil
        logger.info(f"기존 출력 디렉토리 정리: {output_dir}")
        shutil.rmtree(output_dir)
    
    # 스크래퍼 초기화
    scraper = EnhancedKepcoScraper()
    
    try:
        # 3페이지 수집 실행
        success = scraper.scrape_pages(max_pages=3, output_base="output/kepco")
        
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