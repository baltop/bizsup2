# -*- coding: utf-8 -*-
"""
부산테크노파크 스크래퍼 - 향상된 아키텍처 사용 예제
기존 BTPScraper를 새로운 아키텍처로 마이그레이션한 예제
"""

from enhanced_base_scraper import StandardTableScraper
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class EnhancedBTPScraper(StandardTableScraper):
    """부산테크노파크 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        # 하드코딩된 설정들 (설정 파일로 관리되지만 fallback용)
        self.base_url = "https://www.btp.or.kr"
        self.list_url = "https://www.btp.or.kr/kor/CMS/Board/Board.do?mCode=MN013"
        
        # BTP 특화 설정 - 타임아웃 대기시간 대폭 증가, 딜레이 최소화
        self.timeout = 120  # 120초로 대폭 증가 (대용량 파일 다운로드 고려)
        self.delay_between_requests = 0.5  # 0.5초로 최소화 (빠른 처리)
    
    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 반환"""
        # 설정이 있으면 부모 클래스의 표준 구현 사용
        if self.config and self.config.pagination:
            return super().get_list_url(page_num)
        
        # Fallback: 기존 로직
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}&page={page_num}"
    
    def parse_list_page(self, html_content: str) -> list:
        """목록 페이지 파싱"""
        # 설정 기반 파싱이 가능하면 사용
        if self.config and self.config.selectors:
            return super().parse_list_page(html_content)
        
        # Fallback: 기존 로직
        return self._parse_list_fallback(html_content)
    
    def _parse_list_fallback(self, html_content: str) -> list:
        """기존 방식의 목록 파싱 (Fallback)"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        table = soup.find('table', class_='bdListTbl')
        if not table:
            logger.warning("목록 테이블을 찾을 수 없습니다")
            return announcements
        
        tbody = table.find('tbody')
        if not tbody:
            logger.warning("테이블 본문을 찾을 수 없습니다")
            return announcements
        
        rows = tbody.find_all('tr')
        logger.info(f"{len(rows)}개 행 발견")
        
        for row in rows:
            try:
                # 링크 찾기
                link_elem = row.find('a', href=True)
                if not link_elem:
                    continue
                
                # 제목
                title = link_elem.get_text(strip=True)
                if not title:
                    continue
                
                # 상세 페이지 URL 구성
                href = link_elem['href']
                if href.startswith('?'):
                    # 상대 쿼리스트링인 경우 기본 URL에 붙이기
                    detail_url = self.list_url.split('?')[0] + href
                else:
                    detail_url = urljoin(self.base_url, href)
                
                announcement = {
                    'title': title,
                    'url': detail_url
                }
                
                # 추가 정보 추출
                self._extract_additional_fields(row, announcement)
                
                announcements.append(announcement)
                
            except Exception as e:
                logger.error(f"행 파싱 중 오류: {e}")
                continue
        
        logger.info(f"{len(announcements)}개 공고 파싱 완료")
        return announcements
    
    def _get_page_announcements(self, page_num: int) -> List[Dict[str, Any]]:
        """페이지별 공고 목록 가져오기 - BTP 전용"""
        page_url = self.get_list_url(page_num)
        response = self.get_page(page_url)
        
        if not response:
            logger.warning(f"페이지 {page_num} 응답을 가져올 수 없습니다")
            return []
        
        # 페이지가 에러 상태거나 잘못된 경우 감지
        if response.status_code >= 400:
            logger.warning(f"페이지 {page_num} HTTP 에러: {response.status_code}")
            return []
        
        announcements = self.parse_list_page(response.text)
        
        # BTP 특화: 페이지에 "등록된 게시물이 없습니다" 또는 빈 테이블이 있는지 확인
        if not announcements and page_num > 1:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # "등록된 게시물이 없습니다" 메시지 확인
            no_result_elements = soup.find_all(text=lambda text: text and ('등록된 게시물이 없습니다' in text or '데이터가 없습니다' in text or '게시물이 없습니다' in text))
            
            if no_result_elements:
                logger.info(f"BTP 페이지 {page_num}: '등록된 게시물이 없습니다' 메시지 발견 - 마지막 페이지")
            else:
                logger.info(f"BTP 페이지 {page_num}: 공고가 없어 마지막 페이지로 판단됩니다")
        
        return announcements
    
    def _extract_additional_fields(self, row, announcement: dict):
        """추가 필드 추출"""
        # 상태
        status_elem = row.find('span', class_='status')
        if status_elem:
            announcement['status'] = status_elem.get_text(strip=True)
        
        # 작성자
        writer_elem = row.find('td', class_='writer')
        if writer_elem:
            announcement['writer'] = writer_elem.get_text(strip=True)
        
        # 날짜
        date_elem = row.find('td', class_='date')
        if date_elem:
            announcement['date'] = date_elem.get_text(strip=True)
        
        # 접수기간
        period_elem = row.find('td', class_='period')
        if period_elem:
            announcement['period'] = period_elem.get_text(strip=True)
    
    def parse_detail_page(self, html_content: str) -> dict:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = {
            'content': '',
            'attachments': []
        }
        
        try:
            # 본문 추출
            content = self._extract_content(soup)
            result['content'] = content
            
            # 첨부파일 추출
            attachments = self._extract_attachments(soup)
            result['attachments'] = attachments
            
            logger.debug(f"상세 페이지 파싱 완료 - 내용: {len(content)}자, 첨부파일: {len(attachments)}개")
            
        except Exception as e:
            logger.error(f"상세 페이지 파싱 중 오류: {e}")
        
        return result
    
    def _extract_content(self, soup: BeautifulSoup) -> str:
        """본문 내용 추출"""
        # 여러 가능한 본문 컨테이너 시도
        content_selectors = [
            '.board-view-content',
            '.view-content', 
            '.content',
            '#content',
            '.board-content'
        ]
        
        content_elem = None
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                break
        
        if not content_elem:
            # 대체 방법: 가장 큰 텍스트 블록 찾기
            all_divs = soup.find_all('div')
            if all_divs:
                content_elem = max(all_divs, key=lambda x: len(x.get_text()))
        
        if content_elem:
            # HTML을 마크다운으로 변환
            return self.h.handle(str(content_elem))
        else:
            logger.warning("본문 내용을 찾을 수 없습니다")
            return ""
    
    def _extract_attachments(self, soup: BeautifulSoup) -> list:
        """첨부파일 목록 추출"""
        attachments = []
        
        # 첨부파일 링크 찾기
        attachment_selectors = [
            'a[href*="download"]',
            'a[href*="file"]',
            '.attach a',
            '.attachment a',
            '.file-list a'
        ]
        
        for selector in attachment_selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get('href', '')
                if not href:
                    continue
                
                # 파일명 추출
                filename = link.get_text(strip=True)
                if not filename:
                    filename = href.split('/')[-1]
                
                # 절대 URL 생성
                if href.startswith('http'):
                    file_url = href
                else:
                    file_url = urljoin(self.base_url, href)
                
                attachments.append({
                    'name': filename,
                    'url': file_url
                })
        
        # 중복 제거
        seen = set()
        unique_attachments = []
        for att in attachments:
            key = (att['name'], att['url'])
            if key not in seen:
                seen.add(key)
                unique_attachments.append(att)
        
        return unique_attachments


# 하위 호환성을 위한 별칭
BTPScraper = EnhancedBTPScraper

# 테스트용 함수
def test_btp_scraper(pages=3):
    """BTP 스크래퍼 테스트"""
    import os
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    scraper = EnhancedBTPScraper()
    output_dir = "output/btp"
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"BTP 스크래퍼 테스트 시작 - {pages}페이지")
    scraper.scrape_pages(max_pages=pages, output_base=output_dir)
    logger.info("BTP 스크래퍼 테스트 완료")

if __name__ == "__main__":
    test_btp_scraper(3)  # 3페이지 완전 테스트