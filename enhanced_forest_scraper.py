# -*- coding: utf-8 -*-
"""
산림청 공고 스크래퍼 (Forest Service)
https://www.forest.go.kr/kfsweb/cop/bbs/selectBoardList.do?bbsId=BBSMSTR_1032&mn=NKFS_04_01_02
"""

import os
import re
import time
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup
import logging
from enhanced_base_scraper import EnhancedBaseScraper
from datetime import datetime

logger = logging.getLogger(__name__)

class ForestEnhancedScraper(EnhancedBaseScraper):
    """산림청 공고 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.forest.go.kr"
        self.list_url = "https://www.forest.go.kr/kfsweb/cop/bbs/selectBoardList.do"
        self.list_params = {
            'bbsId': 'BBSMSTR_1032',
            'mn': 'NKFS_04_01_02'
        }
        self.site_name = "forest"
        
        # 사이트별 특성 설정
        self.delay_between_requests = 1
        self.timeout = 30
        
        # 페이지네이션 설정
        self.page_size = 10  # 한 페이지당 기본 공고 수
        
        logger.info("산림청 스크래퍼 초기화 완료")
    
    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 생성"""
        params = self.list_params.copy()
        if page_num > 1:
            params['pageIndex'] = str(page_num)
        
        # URL 파라미터 구성
        param_str = '&'.join([f"{k}={v}" for k, v in params.items()])
        return f"{self.list_url}?{param_str}"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """공고 목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 공고 테이블 찾기
        table = soup.find('table', string=lambda text: text and '공고 게시판입니다' in text)
        if not table:
            # 대안: caption을 포함한 테이블 찾기
            tables = soup.find_all('table')
            for t in tables:
                caption = t.find('caption')
                if caption and '공고 게시판입니다' in caption.get_text():
                    table = t
                    break
        
        if not table:
            logger.warning("공고 테이블을 찾을 수 없습니다")
            return announcements
        
        # 테이블 본문 찾기
        tbody = table.find('tbody')
        if not tbody:
            logger.warning("테이블 본문을 찾을 수 없습니다")
            return announcements
        
        # 각 행 처리
        rows = tbody.find_all('tr')
        logger.info(f"발견된 공고 행 수: {len(rows)}")
        
        for i, row in enumerate(rows):
            try:
                cells = row.find_all('td')
                if len(cells) < 6:  # 번호, 제목, 담당부서, 작성일, 첨부, 조회
                    continue
                
                # 번호 셀 (첫 번째 셀)
                number_cell = cells[0]
                number = self.process_notice_detection(number_cell, i)
                
                # 제목 셀 (두 번째 셀)
                title_cell = cells[1]
                
                # 제목 링크 찾기
                title_link = title_cell.find('a')
                if not title_link:
                    continue
                
                # 제목 추출
                title = title_link.get_text(strip=True)
                if not title:
                    continue
                
                # URL 구성
                href = title_link.get('href', '')
                if not href:
                    continue
                
                detail_url = urljoin(self.base_url, href)
                
                # 담당부서 (세 번째 셀)
                department = cells[2].get_text(strip=True)
                
                # 작성일 (네 번째 셀)
                date = cells[3].get_text(strip=True)
                
                # 첨부파일 여부 (다섯 번째 셀)
                attachment_cell = cells[4]
                has_attachment = bool(attachment_cell.find('img') or '첨부' in attachment_cell.get_text())
                
                # 조회수 (여섯 번째 셀)
                views = cells[5].get_text(strip=True)
                
                # 기본 공고 정보
                announcement = {
                    'number': number,
                    'title': title,
                    'url': detail_url,
                    'department': department,
                    'date': date,
                    'has_attachment': has_attachment,
                    'views': views
                }
                
                # 카테고리 정보 추출 (제목에서 [기관명] 형태)
                category_match = re.match(r'\[([^\]]+)\]\s*(.+)', title)
                if category_match:
                    announcement['category'] = category_match.group(1)
                    announcement['title'] = category_match.group(2)
                
                announcements.append(announcement)
                logger.debug(f"공고 추가: {number} - {title[:50]}...")
                
            except Exception as e:
                logger.error(f"행 {i} 파싱 중 오류: {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
        return announcements
    
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """공고 상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 공고 제목 추출
        title = ""
        title_elem = soup.find('strong')
        if title_elem:
            title = title_elem.get_text(strip=True)
        
        # 공고 내용 찾기 - 다양한 방법으로 시도
        content_div = None
        
        # 방법 1: 내용이 있는 div 찾기
        content_candidates = soup.find_all('div', class_=lambda x: x and 'content' in x.lower())
        if content_candidates:
            content_div = content_candidates[0]
        
        # 방법 2: 텍스트 내용이 많은 div 찾기
        if not content_div:
            divs = soup.find_all('div')
            for div in divs:
                text = div.get_text(strip=True)
                if len(text) > 100 and '공고' in text:
                    content_div = div
                    break
        
        # 방법 3: 공고 번호나 특정 키워드가 있는 부분 찾기
        if not content_div:
            for div in soup.find_all('div'):
                text = div.get_text(strip=True)
                if any(keyword in text for keyword in ['공고', '붙임', '첨부', '년', '월', '일']):
                    if len(text) > 50:
                        content_div = div
                        break
        
        content = ""
        if content_div:
            # 내용을 마크다운으로 변환
            content = self.h.handle(str(content_div))
        else:
            # 대체 방법으로 내용 찾기
            content_sections = soup.find_all('p')
            if content_sections:
                content = "\n\n".join([p.get_text(strip=True) for p in content_sections if p.get_text(strip=True)])
        
        # 메타 정보 추출
        meta_info = {
            'title': title,
            'content': content,
            'collected_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'source': 'Forest Service 산림청'
        }
        
        # 첨부파일 찾기
        attachments = self._parse_attachments(soup)
        
        return {
            'title': title,
            'content': self._format_content(meta_info, content),
            'attachments': attachments
        }
    
    def _parse_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """첨부파일 링크 파싱"""
        attachments = []
        
        # 첨부파일 섹션 찾기
        attachment_section = soup.find('dt', string='첨부파일')
        if attachment_section:
            attachment_list = attachment_section.find_next('dd')
            if attachment_list:
                # 첨부파일 링크들 찾기
                file_links = attachment_list.find_all('a', href=True)
                
                for link in file_links:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    
                    # 다운로드 링크인지 확인
                    if 'FileDown.do' in href or 'download' in href.lower():
                        file_info = self._extract_file_info(link)
                        if file_info:
                            file_url = urljoin(self.base_url, href)
                            
                            attachment = {
                                'filename': file_info['filename'],
                                'url': file_url,
                                'size': file_info.get('size', ''),
                                'type': file_info.get('type', '')
                            }
                            
                            attachments.append(attachment)
                            logger.debug(f"첨부파일 발견: {file_info['filename']}")
        
        # 대안: 모든 파일 다운로드 링크 찾기
        if not attachments:
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link.get('href', '')
                if 'FileDown.do' in href or 'download' in href.lower():
                    file_info = self._extract_file_info(link)
                    if file_info:
                        file_url = urljoin(self.base_url, href)
                        
                        attachment = {
                            'filename': file_info['filename'],
                            'url': file_url,
                            'size': file_info.get('size', ''),
                            'type': file_info.get('type', '')
                        }
                        
                        attachments.append(attachment)
                        logger.debug(f"첨부파일 발견: {file_info['filename']}")
        
        logger.info(f"총 {len(attachments)}개 첨부파일 발견")
        return attachments
    
    def _extract_file_info(self, link_element) -> Optional[Dict[str, Any]]:
        """첨부파일 정보 추출"""
        text = link_element.get_text(strip=True)
        
        # 파일명 추출
        filename = text
        
        # 파일 크기 추출 (대괄호 안의 정보)
        size_match = re.search(r'\[([^\]]+)\]', text)
        size = size_match.group(1) if size_match else ''
        
        # 파일 확장자로 타입 추출
        type_match = re.search(r'\.([a-zA-Z0-9]+)(?:\s|$|\[)', filename)
        file_type = type_match.group(1).lower() if type_match else ''
        
        # 파일명 정리 (크기 정보 제거)
        clean_filename = re.sub(r'\s*\[[^\]]+\]', '', filename)
        clean_filename = re.sub(r'\s*자료받기.*$', '', clean_filename)
        
        if not clean_filename:
            return None
        
        return {
            'filename': clean_filename.strip(),
            'size': size.strip(),
            'type': file_type
        }
    
    def _format_content(self, meta_info: Dict[str, Any], content: str) -> str:
        """내용 포맷팅"""
        lines = [
            f"# {meta_info['title']}",
            "",
            f"**수집 시점**: {meta_info['collected_at']}",
            f"**출처**: {meta_info['source']}",
            "",
            "---",
            "",
            content
        ]
        
        return "\n".join(lines)


def main():
    """메인 실행 함수"""
    import sys
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('forest_scraper.log', encoding='utf-8')
        ]
    )
    
    # 스크래퍼 실행
    scraper = ForestEnhancedScraper()
    
    # 출력 디렉토리 생성
    output_dir = f"output/{scraper.site_name}"
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # 3페이지까지 수집
        logger.info("산림청 공고 스크래핑 시작")
        success = scraper.scrape_pages(max_pages=3, output_base=output_dir)
        
        if success:
            logger.info("스크래핑 완료")
            
            # 통계 출력
            stats = scraper.get_stats()
            logger.info(f"처리 통계: {stats}")
            
        else:
            logger.error("스크래핑 실패")
            
    except Exception as e:
        logger.error(f"스크래핑 중 오류: {e}")
        return False
    
    return True


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)