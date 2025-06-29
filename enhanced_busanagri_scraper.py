# -*- coding: utf-8 -*-
"""
부산농업기술센터 스크래퍼 - 향상된 버전
https://www.busan.go.kr/nongup/agricommunity11
"""

import requests
from bs4 import BeautifulSoup
import os
import time
import re
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, unquote
from enhanced_base_scraper import StandardTableScraper

logger = logging.getLogger(__name__)

class EnhancedBusanAgriScraper(StandardTableScraper):
    """부산농업기술센터 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        
        # 부산농업기술센터 기본 설정
        self.base_url = "https://www.busan.go.kr"
        self.list_url = "https://www.busan.go.kr/nongup/agricommunity11"
        
        # 사이트별 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1
        self.delay_between_pages = 2
        
        # 중복 체크 활성화
        self.enable_duplicate_check = True
        self.processed_titles_file = 'output/processed_titles_busanagri.json'
        
        # 부산농업기술센터 특화 헤더
        self.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        self.session.headers.update(self.headers)
        
        logger.info("부산농업기술센터 스크래퍼 초기화 완료")
    
    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 생성"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}?curPage={page_num}"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱 - 부산농업기술센터 테이블 구조"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 메인 테이블 찾기 (.boardList)
        table = soup.find('table', class_='boardList')
        if not table:
            logger.warning("boardList 테이블을 찾을 수 없습니다")
            return announcements
        
        # tbody 찾기
        tbody = table.find('tbody')
        if not tbody:
            logger.warning("tbody를 찾을 수 없습니다")
            return announcements
        
        # 공고 행들 파싱
        rows = tbody.find_all('tr')
        logger.info(f"총 {len(rows)}개 행 발견")
        
        for i, row in enumerate(rows):
            try:
                cells = row.find_all('td')
                if len(cells) < 6:  # 번호, 제목, 첨부파일, 부서명, 작성일, 조회수
                    logger.debug(f"행 {i+1}: 컬럼 수 부족 ({len(cells)}개)")
                    continue
                
                # 번호 (첫 번째 컬럼) - NOTICE나 숫자
                number_cell = cells[0]
                number = number_cell.get_text(strip=True)
                
                # 제목 (두 번째 컬럼)
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
                detail_url = urljoin(self.base_url, href)
                
                # 첨부파일 여부 (세 번째 컬럼)
                attachment_cell = cells[2]
                has_attachment = bool(attachment_cell.find('img') or attachment_cell.get_text(strip=True))
                
                # 부서명 (네 번째 컬럼)
                department = cells[3].get_text(strip=True)
                
                # 작성일 (다섯 번째 컬럼)
                date = cells[4].get_text(strip=True)
                
                # 조회수 (여섯 번째 컬럼)
                views = cells[5].get_text(strip=True)
                
                announcement = {
                    'title': title,
                    'url': detail_url,
                    'number': number,
                    'department': department,
                    'date': date,
                    'views': views,
                    'has_attachment': has_attachment
                }
                
                announcements.append(announcement)
                logger.debug(f"공고 파싱 완료: [{number}] {title[:50]}...")
                
            except Exception as e:
                logger.error(f"행 {i+1} 파싱 중 오류: {e}")
                continue
        
        logger.info(f"파싱 완료: {len(announcements)}개 공고")
        return announcements
    
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # boardView 영역 찾기
        board_view = soup.find('div', class_='boardView')
        if not board_view:
            logger.warning("boardView 영역을 찾을 수 없습니다")
            return {
                'content': '상세 내용을 찾을 수 없습니다.',
                'attachments': []
            }
        
        # 메타 정보 추출
        meta_info = {}
        dl_elements = board_view.find_all('dl')
        
        for dl in dl_elements:
            dt = dl.find('dt')
            dd = dl.find('dd')
            
            if dt and dd:
                key = dt.get_text(strip=True)
                value = dd.get_text(strip=True)
                
                if key and value and key != '내용':  # 내용은 따로 처리
                    meta_info[key] = value
        
        # 제목 추출 (메타 정보 또는 페이지 타이틀에서)
        title = ""
        title_elem = soup.find('h1') or soup.find('h2') or soup.find('h3')
        if title_elem:
            title = title_elem.get_text(strip=True)
        
        # 본문 내용 추출
        content_parts = []
        
        # 메타 정보 추가
        if title:
            content_parts.append(f"# {title}")
            content_parts.append("")
        
        for key, value in meta_info.items():
            content_parts.append(f"**{key}**: {value}")
        
        if meta_info:
            content_parts.append("")
            content_parts.append("---")
            content_parts.append("")
        
        # 내용 부분 찾기
        content_dl = None
        for dl in dl_elements:
            dt = dl.find('dt')
            if dt and '내용' in dt.get_text(strip=True):
                content_dl = dl
                break
        
        if content_dl:
            dd = content_dl.find('dd')
            if dd:
                # HTML을 그대로 유지하면서 텍스트 추출
                content_text = dd.get_text(separator='\n', strip=True)
                if content_text:
                    content_parts.append(content_text)
        
        # 최종 내용 조합
        content = '\n'.join(content_parts)
        
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
            # boardView 영역에서 첨부파일 찾기
            board_view = soup.find('div', class_='boardView')
            if not board_view:
                return attachments
            
            # 첨부파일 dl 요소 찾기
            dl_elements = board_view.find_all('dl')
            
            for dl in dl_elements:
                dt = dl.find('dt')
                if dt and '첨부파일' in dt.get_text(strip=True):
                    dd = dl.find('dd')
                    if dd:
                        # 다운로드 링크 찾기
                        file_links = dd.find_all('a', href=True)
                        
                        for link in file_links:
                            href = link.get('href', '')
                            
                            # 파일 다운로드 링크만 처리 (미리보기 제외)
                            if '/comm/getFile?' in href and 'javascript:' not in href:
                                filename = link.get_text(strip=True)
                                
                                if filename and href:
                                    # 절대 URL 생성
                                    file_url = urljoin(self.base_url, href)
                                    
                                    attachment = {
                                        'filename': filename,
                                        'url': file_url
                                    }
                                    
                                    attachments.append(attachment)
                                    logger.debug(f"첨부파일 발견: {filename}")
                    break
        
        except Exception as e:
            logger.error(f"첨부파일 추출 중 오류: {e}")
        
        logger.info(f"총 {len(attachments)}개 첨부파일 발견")
        return attachments
    
    def download_file(self, url: str, save_path: str, attachment_info: Dict[str, Any] = None) -> bool:
        """파일 다운로드 - RFC 5987 형식 파일명 처리"""
        try:
            logger.info(f"파일 다운로드 시작: {url}")
            
            # 디렉토리 생성
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            response = self.session.get(url, timeout=self.timeout, verify=self.verify_ssl, stream=True)
            response.raise_for_status()
            
            # RFC 5987 형식의 파일명 처리
            content_disposition = response.headers.get('Content-Disposition', '')
            actual_filename = None
            
            if content_disposition:
                # RFC 5987 형식 처리: filename*=UTF-8''encoded_filename
                rfc5987_match = re.search(r"filename\*=([^']*)'([^']*)'(.+)", content_disposition)
                if rfc5987_match:
                    encoding = rfc5987_match.group(1) or 'utf-8'
                    filename_encoded = rfc5987_match.group(3)
                    try:
                        actual_filename = unquote(filename_encoded, encoding=encoding)
                        logger.debug(f"RFC 5987 파일명 추출: {actual_filename}")
                    except Exception as e:
                        logger.warning(f"RFC 5987 파일명 디코딩 실패: {e}")
                
                # 일반 filename 파라미터 처리
                if not actual_filename:
                    filename_match = re.search(r'filename[^;=\n]*=([\'"]*)(.*?)\1', content_disposition)
                    if filename_match:
                        actual_filename = filename_match.group(2)
            
            # 실제 파일명으로 저장 경로 업데이트
            if actual_filename:
                actual_filename = self.sanitize_filename(actual_filename)
                save_dir = os.path.dirname(save_path)
                save_path = os.path.join(save_dir, actual_filename)
            
            # 파일 저장
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(save_path)
            logger.info(f"다운로드 완료: {save_path} ({file_size:,} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"파일 다운로드 실패 {url}: {e}")
            return False


def test_busanagri_scraper(pages=3):
    """부산농업기술센터 스크래퍼 테스트"""
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    scraper = EnhancedBusanAgriScraper()
    output_dir = "output/busanagri"
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"부산농업기술센터 스크래퍼 테스트 시작 - {pages}페이지")
    scraper.scrape_pages(max_pages=pages, output_base=output_dir)
    logger.info("스크래핑 완료")


if __name__ == "__main__":
    test_busanagri_scraper(3)