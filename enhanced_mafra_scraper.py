# -*- coding: utf-8 -*-
"""
농림축산식품부 공지·공고 스크래퍼 (MAFRA)
https://www.mafra.go.kr/home/5108/subview.do
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

class MafraEnhancedScraper(EnhancedBaseScraper):
    """농림축산식품부 공지·공고 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.mafra.go.kr"
        self.list_url = "https://www.mafra.go.kr/home/5108/subview.do"
        self.site_name = "mafra"
        
        # 사이트별 특성 설정
        self.delay_between_requests = 1
        self.timeout = 30
        
        # 페이지네이션 설정
        self.page_size = 10  # 한 페이지당 기본 공고 수
        
        logger.info("농림축산식품부 스크래퍼 초기화 완료")
    
    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 생성"""
        if page_num == 1:
            return self.list_url
        
        # MAFRA는 JavaScript page_link() 함수를 사용하여 페이지 이동
        # 실제로는 POST 요청으로 페이지 데이터를 가져옴
        return self.list_url
    
    def get_page(self, url: str, **kwargs) -> Optional:
        """페이지 요청 - POST 방식 페이지네이션 지원"""
        if 'page_num' in kwargs:
            page_num = kwargs.pop('page_num')
            return self._get_page_with_pagination(page_num, **kwargs)
        else:
            return super().get_page(url, **kwargs)
    
    def _get_page_with_pagination(self, page_num: int, **kwargs) -> Optional:
        """페이지네이션을 위한 POST 요청"""
        if page_num == 1:
            # 첫 페이지는 일반 GET 요청
            return super().get_page(self.list_url, **kwargs)
        
        # 2페이지 이상은 POST 요청으로 처리
        # MAFRA의 페이지네이션은 JavaScript 기반이므로 
        # 여기서는 간단히 GET 요청에 파라미터 추가로 처리
        params = {
            'page': str(page_num),
            'row': '10'
        }
        
        return super().get_page(self.list_url, params=params, **kwargs)
    
    def _get_page_announcements(self, page_num: int) -> List[Dict[str, Any]]:
        """페이지별 공고 목록 가져오기"""
        logger.info(f"페이지 {page_num} 공고 목록 요청")
        
        # 페이지네이션이 있는 경우 POST 요청
        if page_num > 1:
            response = self.get_page(self.list_url, page_num=page_num)
        else:
            response = self.get_page(self.list_url)
        
        if not response:
            logger.warning(f"페이지 {page_num} 응답을 가져올 수 없습니다")
            return []
        
        # 현재 페이지 번호 저장
        self.current_page_num = page_num
        announcements = self.parse_list_page(response.text)
        
        return announcements
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """공고 목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 공고 테이블 찾기 - MAFRA는 클래스명 없는 일반 테이블 사용
        # caption에 "공지·공고 게시판"이 포함된 테이블 찾기
        table = None
        tables = soup.find_all('table')
        for t in tables:
            caption = t.find('caption')
            if caption and '공지·공고 게시판' in caption.get_text():
                table = t
                break
        
        if not table:
            logger.warning("공고 테이블을 찾을 수 없습니다")
            logger.debug(f"발견된 테이블 수: {len(tables)}")
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
                if len(cells) < 2:
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
                
                # 기본 공고 정보
                announcement = {
                    'number': number,
                    'title': title,
                    'url': detail_url
                }
                
                # 추가 정보 추출 (작성일, 담당부서 등) - MAFRA 실제 구조에 맞게 수정
                try:
                    # dl 태그에서 추가 정보 추출
                    dl_elements = title_cell.find_all('dl')
                    for dl in dl_elements:
                        dd_elements = dl.find_all('dd')
                        
                        for dd in dd_elements:
                            text = dd.get_text(strip=True)
                            class_name = dd.get('class', [])
                            
                            # 날짜 정보 (class="date")
                            if 'date' in class_name and re.match(r'\d{4}\.\d{2}\.\d{2}', text):
                                announcement['date'] = text
                            # 부서 정보 (class="name")
                            elif 'name' in class_name:
                                announcement['department'] = text
                            # 첨부파일 정보 (class="file")
                            elif 'file' in class_name and '첨부파일' in text:
                                announcement['has_attachment'] = True
                    
                    # 첨부파일 여부 확인 (대체 방법)
                    if 'has_attachment' not in announcement:
                        announcement['has_attachment'] = False
                        
                except Exception as e:
                    logger.debug(f"추가 정보 추출 중 오류: {e}")
                
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
        
        # 공고 제목
        title = ""
        title_elem = soup.find('dt', string=lambda text: text and text.strip())
        if title_elem:
            title = title_elem.get_text(strip=True)
        
        # 공고 내용 찾기
        content_div = soup.find('div', class_='artclCont')
        if not content_div:
            content_div = soup.find('div', class_='artclInfo')
        
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
            'source': 'MAFRA 농림축산식품부'
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
        
        # 첨부파일 링크 찾기
        attachment_links = soup.find_all('a', href=True)
        
        for link in attachment_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # 다운로드 링크 패턴 확인
            if 'download.do' in href or 'file' in href.lower():
                # 파일 정보 추출
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
        
        # 파일 크기 추출 (괄호 안의 정보)
        size_match = re.search(r'\(파일\s*용량\s*:\s*([^)]+)\)', text)
        size = size_match.group(1) if size_match else ''
        
        # 파일 확장자로 타입 추출
        type_match = re.search(r'\.([a-zA-Z0-9]+)(?:\s*\(|$)', filename)
        file_type = type_match.group(1).lower() if type_match else ''
        
        # 파일명 정리 (크기 정보 제거)
        clean_filename = re.sub(r'\s*\(파일\s*용량\s*:[^)]+\)', '', filename)
        
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
            logging.FileHandler('mafra_scraper.log', encoding='utf-8')
        ]
    )
    
    # 스크래퍼 실행
    scraper = MafraEnhancedScraper()
    
    # 출력 디렉토리 생성
    output_dir = f"output/{scraper.site_name}"
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # 3페이지까지 수집
        logger.info("MAFRA 공지·공고 스크래핑 시작")
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