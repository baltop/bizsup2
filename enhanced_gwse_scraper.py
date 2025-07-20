#!/usr/bin/env python3
"""
Enhanced GWSE (강원지속가능경제지원센터) 공지사항 스크래퍼
URL: https://gwse.or.kr/bbs/board.php?bo_table=sub41&sca=%EC%82%AC%EC%97%85%EA%B3%B5%EA%B3%A0
"""

import os
import re
import json
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, urlparse, parse_qs, unquote
from bs4 import BeautifulSoup
from enhanced_base_scraper import EnhancedBaseScraper

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnhancedGwseScraper(EnhancedBaseScraper):
    """강원지속가능경제지원센터 공지사항 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        
        # 사이트 기본 정보
        self.base_url = "https://gwse.or.kr"
        self.list_url = "https://gwse.or.kr/bbs/board.php?bo_table=sub41&sca=%EC%82%AC%EC%97%85%EA%B3%B5%EA%B3%A0"
        self.site_code = "gwse"
        
        # 출력 디렉토리 설정
        self.output_base = f"output/{self.site_code}"
        os.makedirs(self.output_base, exist_ok=True)
        
        # 사업공고 카테고리 필터
        self.category_filter = "sca=%EC%82%AC%EC%97%85%EA%B3%B5%EA%B3%A0"
        
        # 헤더 설정
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1'
        })
        
        # 세션 초기화
        self.initialize_session()
    
    def initialize_session(self):
        """세션 초기화 - 메인 페이지 방문으로 세션 설정"""
        try:
            logger.info("세션 초기화 중...")
            response = self.get_page(self.list_url)
            if response and response.status_code == 200:
                logger.info("세션 초기화 성공")
                return True
            else:
                logger.error("세션 초기화 실패")
                return False
        except Exception as e:
            logger.error(f"세션 초기화 중 오류: {e}")
            return False
    
    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 반환"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}&page={page_num}"
    
    def _get_page_announcements(self, page_num: int) -> List[Dict[str, Any]]:
        """페이지별 공고 목록 가져오기"""
        try:
            # 페이지 URL 생성
            page_url = self.get_list_url(page_num)
            
            # 페이지 요청
            response = self.get_page(page_url)
            
            if not response:
                logger.warning(f"페이지 {page_num} 응답을 가져올 수 없습니다")
                return []
            
            # 현재 페이지 번호 저장
            self.current_page_num = page_num
            announcements = self.parse_list_page(response.text)
            
            return announcements
            
        except Exception as e:
            logger.error(f"페이지 {page_num} 처리 중 오류: {e}")
            return []
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        try:
            # 게시판 테이블 찾기
            table = soup.select_one('table')
            if not table:
                logger.warning("게시판 테이블을 찾을 수 없습니다")
                return announcements
            
            # 모든 tr 찾기 (헤더 제외)
            rows = table.select('tr')[1:]  # 첫 번째 행(헤더) 제외
            
            for row_index, row in enumerate(rows):
                try:
                    # 모든 td 셀 가져오기
                    cells = row.select('td')
                    if len(cells) < 5:  # 번호, 제목, 작성자, 날짜, 조회수
                        continue
                    
                    # 번호 처리
                    number_cell = cells[0]
                    number_text = number_cell.get_text(strip=True)
                    
                    # 제목 및 링크 추출
                    title_cell = cells[1]
                    post_links = title_cell.select('a')
                    
                    # 두 번째 링크가 게시물 링크 (첫 번째는 카테고리)
                    if len(post_links) < 2:
                        continue
                    
                    title_link = post_links[1]  # 두 번째 링크가 게시물 링크
                    title = title_link.get_text(strip=True)
                    href = title_link.get('href', '')
                    
                    if not title or not href:
                        continue
                    
                    # 절대 URL 생성
                    detail_url = urljoin(self.base_url, href)
                    
                    # 카테고리 추출 (첫 번째 링크가 카테고리)
                    category_link = post_links[0]  # 첫 번째 링크가 카테고리
                    category = category_link.get_text(strip=True) if category_link else ""
                    
                    # 작성자
                    author_cell = cells[2]
                    author = author_cell.get_text(strip=True)
                    
                    # 날짜
                    date_cell = cells[3]
                    date = date_cell.get_text(strip=True)
                    
                    # 조회수
                    views_cell = cells[4]
                    views = views_cell.get_text(strip=True)
                    
                    # 첨부파일 여부 확인
                    has_attachment = bool(title_cell.select('img[alt="첨부파일"]'))
                    
                    # 공지사항 여부 확인
                    is_notice = "공지" in number_text or "공지사항" in category
                    
                    # wr_id 추출
                    wr_id = ""
                    if href:
                        parsed_url = urlparse(href)
                        query_params = parse_qs(parsed_url.query)
                        if 'wr_id' in query_params:
                            wr_id = query_params['wr_id'][0]
                    
                    announcement = {
                        'title': title,
                        'url': detail_url,
                        'author': author,
                        'date': date,
                        'views': views,
                        'number': number_text,
                        'category': category,
                        'is_notice': is_notice,
                        'has_attachment': has_attachment,
                        'wr_id': wr_id
                    }
                    
                    announcements.append(announcement)
                    logger.debug(f"공고 추가: {title}")
                    
                except Exception as e:
                    logger.error(f"행 {row_index} 파싱 중 오류: {e}")
                    continue
            
            logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
            
        except Exception as e:
            logger.error(f"목록 페이지 파싱 실패: {e}")
        
        return announcements
    
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 기본 반환값
        result = {
            'content': '',
            'attachments': []
        }
        
        try:
            # 본문 내용 추출
            content_found = False
            
            # 방법 1: 메인 컨텐츠 영역에서 본문 찾기
            content_div = soup.select_one('div#bo_v_con div')
            if content_div:
                # HTML을 마크다운으로 변환
                content_text = self.h.handle(str(content_div))
                result['content'] = content_text.strip()
                content_found = True
            
            # 방법 2: 텍스트 기반 본문 추출 (위 방법이 실패한 경우)
            if not content_found:
                # 본문 섹션 찾기
                content_sections = []
                
                # 모든 텍스트 요소를 순회하여 본문 찾기
                for element in soup.find_all(['p', 'div', 'span', 'br'], recursive=True):
                    if element.name == 'br':
                        content_sections.append('\n')
                        continue
                    
                    text = element.get_text(strip=True)
                    if text and len(text) > 10:  # 의미있는 내용만
                        # 메타 정보 제외
                        if not any(keyword in text for keyword in ['조회', '작성자', '작성일', '첨부파일', '댓글']):
                            content_sections.append(text)
                
                if content_sections:
                    result['content'] = '\n\n'.join(content_sections)
                    content_found = True
            
            # 방법 3: 기본 내용 추출
            if not content_found:
                result['content'] = "본문 내용을 찾을 수 없습니다."
            
            # 첨부파일 추출
            attachments = []
            
            # 첨부파일 섹션 찾기 - "첨부파일" 헤딩 찾기
            attachment_heading = soup.find('h2', string='첨부파일')
            if not attachment_heading:
                # 다른 헤딩 레벨도 확인
                attachment_heading = soup.find(['h1', 'h2', 'h3', 'h4'], string='첨부파일')
            
            if attachment_heading:
                # 다음 리스트 요소 찾기
                file_list = attachment_heading.find_next('ul') or attachment_heading.find_next('ol')
                if file_list:
                    file_links = file_list.select('a[href*="download.php"]')
                    
                    for link in file_links:
                        href = link.get('href', '')
                        
                        # 파일명 추출 (strong 태그 내의 텍스트)
                        filename_elem = link.select_one('strong')
                        filename = filename_elem.get_text(strip=True) if filename_elem else ""
                        
                        # 파일명이 없으면 링크 텍스트 사용
                        if not filename:
                            filename = link.get_text(strip=True)
                        
                        if href and filename:
                            # 절대 URL 생성
                            file_url = urljoin(self.base_url, href)
                            
                            attachments.append({
                                'filename': filename,
                                'url': file_url,
                                'name': filename  # 'name' 키도 추가 (base_scraper 호환)
                            })
            
            # 대안 방법: 페이지 전체에서 다운로드 링크 찾기
            if not attachments:
                download_links = soup.select('a[href*="download.php"]')
                for link in download_links:
                    href = link.get('href', '')
                    
                    # 파일명 추출
                    filename_elem = link.select_one('strong')
                    filename = filename_elem.get_text(strip=True) if filename_elem else ""
                    
                    if not filename:
                        filename = link.get_text(strip=True)
                    
                    if href and filename and filename != "첨부파일":
                        file_url = urljoin(self.base_url, href)
                        attachments.append({
                            'filename': filename,
                            'url': file_url,
                            'name': filename
                        })
            
            result['attachments'] = attachments
            
            logger.info(f"상세 페이지 파싱 완료 - 내용: {len(result['content'])}자, 첨부파일: {len(attachments)}개")
            
        except Exception as e:
            logger.error(f"상세 페이지 파싱 실패: {e}")
            result['content'] = "상세 페이지 파싱 중 오류가 발생했습니다."
        
        return result
    
    def download_file(self, url: str, save_path: str, attachment_info: Dict[str, Any] = None) -> bool:
        """첨부파일 다운로드 - GWSE 사이트 특화"""
        try:
            logger.info(f"첨부파일 다운로드 시작: {url}")
            
            # 다운로드 헤더 설정
            download_headers = self.session.headers.copy()
            download_headers['Referer'] = self.base_url
            
            # 파일 다운로드
            response = self.session.get(url, headers=download_headers, stream=True, timeout=30)
            response.raise_for_status()
            
            # Content-Type 확인
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' in content_type.lower():
                logger.warning(f"HTML 응답 감지, 파일 다운로드 실패: {url}")
                return False
            
            # 실제 파일명 추출
            actual_filename = self._extract_filename(response, save_path)
            if actual_filename != save_path:
                save_path = actual_filename
            
            # 디렉토리 생성
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # 파일 저장
            total_size = 0
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        total_size += len(chunk)
            
            # 파일 크기 확인
            file_size = os.path.getsize(save_path)
            
            # 너무 작은 파일은 오류 페이지일 가능성 확인
            if file_size < 1024:  # 1KB 미만
                try:
                    with open(save_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if '<html' in content.lower() or '<!doctype' in content.lower():
                            logger.warning(f"HTML 파일 감지, 삭제: {save_path}")
                            os.remove(save_path)
                            return False
                except:
                    pass
            
            logger.info(f"첨부파일 다운로드 완료: {save_path} ({file_size:,} bytes)")
            
            # 통계 업데이트
            with self._lock:
                self.stats['files_downloaded'] += 1
                self.stats['total_download_size'] += file_size
            
            return True
            
        except Exception as e:
            logger.error(f"첨부파일 다운로드 실패: {url} - {e}")
            return False


def main():
    """메인 실행 함수"""
    logger.info("=== GWSE 공지사항 스크래퍼 시작 ===")
    
    try:
        # 스크래퍼 인스턴스 생성
        scraper = EnhancedGwseScraper()
        
        # 3페이지 수집 실행
        success = scraper.scrape_pages(max_pages=3, output_base=scraper.output_base)
        
        if success:
            logger.info("=== 스크래핑 완료 ===")
        else:
            logger.error("=== 스크래핑 실패 ===")
            
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단되었습니다.")
    except Exception as e:
        logger.error(f"스크래핑 중 오류 발생: {e}")


if __name__ == "__main__":
    main()