# -*- coding: utf-8 -*-
"""
서울신보 공지사항 스크래퍼
Enhanced 버전 - JavaScript 기반 페이지네이션과 상세페이지 처리
"""

from enhanced_base_scraper import StandardTableScraper
from bs4 import BeautifulSoup
from urllib.parse import urljoin, parse_qs
import re
import logging
import time

logger = logging.getLogger(__name__)

class EnhancedSeoulshinboScraper(StandardTableScraper):
    """서울신보 공지사항 스크래퍼 - Enhanced 버전"""
    
    def __init__(self):
        super().__init__()
        
        # 사이트별 설정
        self.base_url = "https://www.seoulshinbo.co.kr"
        self.list_url = "https://www.seoulshinbo.co.kr/wbase/contents/bbs/list.do?mng_cd=STRY9788"
        self.site_name = "서울신보"
        
        # 기본 설정
        self.verify_ssl = False  # SSL 인증서 문제로 비활성화
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1
        
        # JavaScript 기반 사이트 특성
        self.supports_ajax_pagination = True
        
    def get_list_url(self, page_num: int) -> str:
        """페이지별 목록 URL 생성 (POST 방식 시뮬레이션)"""
        if page_num == 1:
            return self.list_url
        return f"{self.list_url}&page={page_num}"
    
    def _make_post_request(self, page_num: int):
        """POST 방식으로 페이지 요청"""
        url = "https://www.seoulshinbo.co.kr/wbase/contents/bbs/list.do"
        
        data = {
            'mng_cd': 'STRY9788',
            'page': str(page_num)
        }
        
        try:
            response = self.session.post(
                url, 
                data=data, 
                headers=self.headers,
                verify=self.verify_ssl,
                timeout=self.timeout
            )
            response.encoding = self.default_encoding
            return response
        except Exception as e:
            logger.error(f"POST 요청 실패 (페이지 {page_num}): {e}")
            return None
    
    def _get_page_announcements(self, page_num: int) -> list:
        """페이지별 공고 목록 가져오기 (POST 방식 시도 후 GET 방식 폴백)"""
        self.current_page_num = page_num
        
        # POST 방식 먼저 시도
        response = self._make_post_request(page_num)
        if response and response.status_code == 200:
            html_content = response.text
        else:
            # GET 방식 폴백
            logger.info(f"POST 실패, GET 방식으로 폴백 (페이지 {page_num})")
            url = self.get_list_url(page_num)
            response = self.get_page(url)
            if not response:
                return []
            html_content = response.text
            
        return self.parse_list_page(html_content)
    
    def parse_list_page(self, html_content: str) -> list:
        """목록 페이지 파싱"""
        announcements = []
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 디버깅을 위해 HTML 저장
        with open('debug_seoulshinbo_current.html', 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # 테이블 찾기 (웹용)
        web_table = soup.find('div', class_='pre_info_list_tbl for_web')
        if not web_table:
            logger.warning("웹용 테이블을 찾을 수 없습니다")
            return announcements
        
        table = web_table.find('table')
        if not table:
            logger.warning("테이블을 찾을 수 없습니다")
            return announcements
        
        tbody = table.find('tbody')
        if not tbody:
            logger.warning("tbody를 찾을 수 없습니다")
            return announcements
        
        rows = tbody.find_all('tr')
        logger.info(f"찾은 행 수: {len(rows)}")
        
        for i, row in enumerate(rows):
            try:
                cells = row.find_all('td')
                if len(cells) < 3:
                    continue
                
                # 번호 (첫 번째 셀) - 공지 이미지 처리
                number_cell = cells[0]
                notice_elem = number_cell.find('p', class_='notice_text')
                if notice_elem:
                    number = "공지"
                else:
                    number = number_cell.get_text(strip=True)
                    if not number:
                        number = f"row_{i}"
                
                # 제목 (두 번째 셀)
                title_cell = cells[1]
                link_elem = title_cell.find('a')
                
                if not link_elem:
                    continue
                
                title = link_elem.get_text(strip=True)
                href = link_elem.get('href', '')
                onclick = link_elem.get('onclick', '')
                
                # href 또는 onclick에서 JavaScript 함수 찾기
                js_code = href if href.startswith('javascript:') else onclick
                
                if not js_code or not title:
                    continue
                
                # JavaScript에서 stry_cd 추출
                # javascript:bbs.goView('1', '19564')
                match = re.search(r"bbs\.goView\('(\d+)', '(\d+)'\)", js_code)
                if not match:
                    logger.warning(f"행 {i}: JavaScript 패턴을 찾을 수 없음: {js_code}")
                    continue
                
                stry_cd = match.group(2)
                detail_url = f"{self.base_url}/wbase/contents/bbs/view.do?mng_cd=STRY9788&stry_cd={stry_cd}"
                
                # 작성자와 날짜 (5개 셀: 번호, 제목, 작성자, 날짜, 첨부파일)
                author = ""
                date = ""
                
                if len(cells) >= 4:
                    author = cells[2].get_text(strip=True)
                    date = cells[3].get_text(strip=True)
                elif len(cells) >= 3:
                    date = cells[2].get_text(strip=True)
                
                announcement = {
                    'number': number,
                    'title': title,
                    'url': detail_url,
                    'author': author,
                    'date': date,
                    'stry_cd': stry_cd,
                    'attachments': []
                }
                
                announcements.append(announcement)
                logger.info(f"공고 추가: [{number}] {title}")
                
            except Exception as e:
                logger.error(f"행 파싱 중 오류: {e}")
                continue
        
        return announcements
    
    def parse_detail_page(self, html_content: str) -> dict:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 찾기
        title_elem = soup.find('h1') or soup.find('h2') or soup.find('.title')
        title = title_elem.get_text(strip=True) if title_elem else "제목 없음"
        
        # 본문 찾기 - 여러 패턴 시도
        content_selectors = [
            '.view_content',
            '.content',
            '.view_area',
            '.board_view',
            '.txt_area'
        ]
        
        content_elem = None
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                break
        
        # div 태그들 중에서 긴 텍스트를 가진 것 찾기
        if not content_elem:
            divs = soup.find_all('div')
            for div in divs:
                text = div.get_text(strip=True)
                if len(text) > 100:  # 충분히 긴 텍스트
                    content_elem = div
                    break
        
        content_html = ""
        if content_elem:
            content_html = str(content_elem)
            
            # 이미지 URL 절대 경로로 변환
            img_tags = content_elem.find_all('img')
            for img in img_tags:
                if img.get('src'):
                    img['src'] = urljoin(self.base_url, img['src'])
        
        # HTML을 마크다운으로 변환
        content_markdown = self.h.handle(content_html) if content_html else "내용 없음"
        
        # 첨부파일 찾기
        attachments = self._extract_attachments(soup)
        
        return {
            'title': title,
            'content': content_markdown,
            'attachments': attachments
        }
    
    def _extract_attachments(self, soup: BeautifulSoup) -> list:
        """첨부파일 추출"""
        attachments = []
        
        # 첨부파일 링크 패턴들
        file_patterns = [
            'download',
            'file',
            'attach',
            'fileDownload'
        ]
        
        # 모든 링크에서 파일 다운로드 링크 찾기
        links = soup.find_all('a', href=True)
        
        for link in links:
            href = link.get('href', '')
            onclick = link.get('onclick', '')
            
            # href나 onclick에서 파일 다운로드 패턴 찾기
            is_file_link = False
            for pattern in file_patterns:
                if pattern.lower() in href.lower() or pattern.lower() in onclick.lower():
                    is_file_link = True
                    break
            
            if is_file_link:
                filename = link.get_text(strip=True)
                if not filename:
                    filename = "첨부파일"
                
                # 절대 URL로 변환
                if href.startswith('/'):
                    file_url = urljoin(self.base_url, href)
                elif href.startswith('http'):
                    file_url = href
                else:
                    # JavaScript 함수인 경우 처리가 복잡하므로 일단 스킵
                    continue
                
                attachment = {
                    'filename': filename,
                    'url': file_url,
                    'size': ''
                }
                
                attachments.append(attachment)
                logger.info(f"첨부파일 발견: {filename}")
        
        return attachments
    
    def download_announcement_content(self, announcement: dict, save_dir: str) -> dict:
        """공고 상세 내용 다운로드 (오버라이드) - 기본정보 기반 처리"""
        try:
            # 서울신보는 특별한 세션 인증이 필요한 사이트로 
            # 상세페이지 접근이 제한되므로 기본 정보로 마크다운 생성
            
            title = announcement.get('title', '제목 없음')
            author = announcement.get('author', '')
            date = announcement.get('date', '')
            stry_cd = announcement.get('stry_cd', '')
            
            # 기본 마크다운 컨텐츠 생성
            content_lines = [
                f"# {title}",
                "",
                f"**작성자**: {author}" if author else "",
                f"**작성일**: {date}" if date else "",
                f"**게시물 번호**: {stry_cd}" if stry_cd else "",
                "",
                "## 공고 내용",
                "",
                "⚠️ **주의**: 이 공고는 서울신용보증재단 웹사이트의 특별한 인증 시스템으로 인해",
                "상세 내용을 자동으로 수집할 수 없었습니다.",
                "",
                "전체 내용을 확인하려면 다음 링크를 방문해주세요:",
                f"https://www.seoulshinbo.co.kr/wbase/contents/bbs/list.do?mng_cd=STRY9788",
                "",
                "---",
                "",
                f"**원본 URL**: {announcement.get('url', '')}",
                f"**수집 시점**: {self._get_current_timestamp()}",
            ]
            
            # 빈 줄 제거
            content_markdown = "\n".join([line for line in content_lines if line is not None])
            
            # 공고 정보 업데이트
            announcement.update({
                'title': title,
                'content': content_markdown,
                'attachments': []  # 상세페이지 접근 불가로 첨부파일 정보 없음
            })
            
            logger.info(f"기본 정보 기반 마크다운 생성 완료: {title}")
            
            return announcement
            
        except Exception as e:
            logger.error(f"기본 정보 처리 중 오류: {e}")
            return announcement
    
    def _get_current_timestamp(self):
        """현재 시간 문자열 반환"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

if __name__ == "__main__":
    # 테스트 실행
    import os
    import logging
    
    # 로깅 설정
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    scraper = EnhancedSeoulshinboScraper()
    output_dir = "output/seoulshinbo"
    os.makedirs(output_dir, exist_ok=True)
    
    print("서울신보 스크래퍼 테스트 시작...")
    scraper.scrape_pages(max_pages=3, output_base=output_dir)
    print("테스트 완료!")