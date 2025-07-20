#!/usr/bin/env python3
"""
Enhanced OFSI (전라남도 해양수산과학원) 공지사항 스크래퍼
URL: https://ofsi.jeonnam.go.kr/ofsi/177/subview.do
"""

import os
import re
import json
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from enhanced_base_scraper import EnhancedBaseScraper

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnhancedOfsiScraper(EnhancedBaseScraper):
    """전라남도 해양수산과학원 공지사항 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        
        # 사이트 기본 정보
        self.base_url = "https://ofsi.jeonnam.go.kr"
        self.list_url = "https://ofsi.jeonnam.go.kr/ofsi/177/subview.do"
        self.site_code = "ofsi"
        
        # 출력 디렉토리 설정
        self.output_base = f"output/{self.site_code}"
        os.makedirs(self.output_base, exist_ok=True)
        
        # 페이지네이션 관련 설정
        self.pagination_form_url = "/bbs/ofsi/38/artclList.do"
        self.pagination_form_data = {
            'layout': 'YfvSWvlsyMjnrjh0KwMsxg%3D%3D',
            'menuNo': '37',
            'upperMenuNo': '37',
            'searchType': '',
            'searchWord': '',
            'page': '1'
        }
        
        # 헤더 설정
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
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
        """페이지 번호에 따른 목록 URL 반환 (POST 방식이므로 항상 같은 URL)"""
        return urljoin(self.base_url, self.pagination_form_url)
    
    def _get_page_announcements(self, page_num: int) -> List[Dict[str, Any]]:
        """페이지별 공고 목록 가져오기 - POST 방식 구현"""
        try:
            # POST 데이터 준비
            form_data = self.pagination_form_data.copy()
            form_data['page'] = str(page_num)
            
            # POST 요청
            response = self.post_page(self.get_list_url(page_num), data=form_data)
            
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
            # 공지사항 테이블 찾기
            table = soup.select_one('table.artclTable')
            if not table:
                logger.warning("공지사항 테이블을 찾을 수 없습니다")
                return announcements
            
            # tbody 내의 모든 tr 찾기
            rows = table.select('tbody tr')
            
            for row_index, row in enumerate(rows):
                try:
                    # 모든 td 셀 가져오기
                    cells = row.select('td')
                    if len(cells) < 6:  # 번호, 제목, 작성자, 작성일, 첨부파일, 조회수
                        continue
                    
                    # 번호 처리 (일반공지인지 확인)
                    number_cell = cells[0]
                    number_text = number_cell.get_text(strip=True)
                    
                    # 제목 및 링크 추출
                    title_cell = cells[1]
                    title_link = title_cell.select_one('a')
                    
                    if not title_link:
                        continue
                    
                    title = title_link.get_text(strip=True)
                    href = title_link.get('href', '')
                    
                    if not title or not href:
                        continue
                    
                    # 절대 URL 생성
                    detail_url = urljoin(self.base_url, href)
                    
                    # 작성자
                    author = cells[2].get_text(strip=True)
                    
                    # 작성일
                    date = cells[3].get_text(strip=True)
                    
                    # 첨부파일 여부 확인
                    attachment_cell = cells[4]
                    has_attachment = bool(attachment_cell.select('a'))
                    
                    # 조회수
                    views = cells[5].get_text(strip=True)
                    
                    # 공지사항 여부 확인
                    is_notice = "일반공지" in number_text
                    
                    announcement = {
                        'title': title,
                        'url': detail_url,
                        'author': author,
                        'date': date,
                        'views': views,
                        'number': number_text,
                        'is_notice': is_notice,
                        'has_attachment': has_attachment
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
            content_div = soup.select_one('div.content')
            if content_div:
                # HTML을 마크다운으로 변환
                content_text = self.h.handle(str(content_div))
                result['content'] = content_text.strip()
            else:
                # 대안 방법: article 태그 내용 전체 추출
                article = soup.select_one('article')
                if article:
                    # 제목과 메타정보 제외하고 본문만 추출
                    content_parts = []
                    for element in article.find_all(['p', 'div', 'span'], recursive=True):
                        text = element.get_text(strip=True)
                        if text and len(text) > 10:  # 의미있는 내용만
                            content_parts.append(text)
                    
                    if content_parts:
                        result['content'] = '\n\n'.join(content_parts)
                else:
                    result['content'] = "본문 내용을 찾을 수 없습니다."
            
            # 첨부파일 추출
            attachments = []
            
            # 첨부파일 섹션 찾기
            attachment_section = soup.select_one('dt:contains("첨부파일")')
            if attachment_section:
                # 다음 dd 태그에서 첨부파일 링크들 찾기
                dd_element = attachment_section.find_next_sibling('dd')
                if dd_element:
                    attachment_links = dd_element.select('a')
                    
                    for link in attachment_links:
                        href = link.get('href', '')
                        filename = link.get_text(strip=True)
                        
                        if href and filename:
                            # 절대 URL 생성
                            file_url = urljoin(self.base_url, href)
                            
                            attachments.append({
                                'filename': filename,
                                'url': file_url,
                                'name': filename  # 'name' 키도 추가 (base_scraper 호환)
                            })
            
            # 다른 방법으로 첨부파일 찾기 (위 방법이 실패한 경우)
            if not attachments:
                download_links = soup.select('a[href*="/download.do"]')
                for link in download_links:
                    href = link.get('href', '')
                    filename = link.get_text(strip=True)
                    
                    if href and filename:
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
        """첨부파일 다운로드 - OFSI 사이트 특화"""
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
    logger.info("=== OFSI 공지사항 스크래퍼 시작 ===")
    
    try:
        # 스크래퍼 인스턴스 생성
        scraper = EnhancedOfsiScraper()
        
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