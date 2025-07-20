# -*- coding: utf-8 -*-
"""
경기도 환경에너지진흥원 (GGEEA) 공지사항 스크래퍼
사이트: https://www.ggeea.or.kr/notice
"""

import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, parse_qs
import logging
from typing import Dict, List, Any
from enhanced_base_scraper import EnhancedBaseScraper

logger = logging.getLogger(__name__)

class EnhancedGgeeaScraper(EnhancedBaseScraper):
    """경기도 환경에너지진흥원 공지사항 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.ggeea.or.kr"
        self.list_url = "https://www.ggeea.or.kr/notice"
        
        # 사이트별 설정
        self.delay_between_requests = 2  # 정부 사이트 - 2초 간격
        self.delay_between_pages = 1.5
        
        # 세션 헤더 추가
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        })
    
    def get_list_url(self, page_num: int) -> str:
        """페이지별 목록 URL 생성"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}?page={page_num}"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """공지사항 목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 공지사항 테이블 찾기 (caption 요소로 검색)
        table = None
        tables = soup.find_all('table')
        for t in tables:
            caption = t.find('caption')
            if caption and '공지사항 목록' in caption.get_text(strip=True):
                table = t
                break
        
        if not table:
            logger.warning("공지사항 목록 테이블을 찾을 수 없습니다")
            return announcements
        
        # 테이블 행들 찾기
        tbody = table.find('tbody')
        if not tbody:
            logger.warning("테이블 본문을 찾을 수 없습니다")
            return announcements
        
        rows = tbody.find_all('tr')
        logger.info(f"총 {len(rows)}개의 공고 행을 발견했습니다")
        
        for row_index, row in enumerate(rows):
            try:
                cells = row.find_all('td')
                if len(cells) < 4:
                    continue
                
                # 각 셀 파싱
                number_cell = cells[0]  # 번호
                title_cell = cells[1]   # 제목 (카테고리 + 제목)
                date_cell = cells[2]    # 날짜
                views_cell = cells[3]   # 조회수
                
                # 제목 링크 찾기
                title_link = title_cell.find('a')
                if not title_link:
                    continue
                
                # 제목 텍스트 추출 (마지막 a 태그가 실제 제목)
                title_links = title_cell.find_all('a')
                if len(title_links) >= 2:
                    # 카테고리와 제목이 분리된 경우
                    category_link = title_links[0]
                    title_link = title_links[1]
                    category = category_link.get_text(strip=True)
                    title = title_link.get_text(strip=True)
                    full_title = f"[{category}] {title}" if category else title
                else:
                    # 제목만 있는 경우
                    title = title_link.get_text(strip=True)
                    full_title = title
                
                if not full_title:
                    continue
                
                # URL 구성
                href = title_link.get('href', '')
                if not href:
                    continue
                
                detail_url = urljoin(self.base_url, href)
                
                # 공고 번호 추출
                number = number_cell.get_text(strip=True)
                
                # 날짜 추출
                date = date_cell.get_text(strip=True)
                
                # 조회수 추출
                views = views_cell.get_text(strip=True)
                
                announcement = {
                    'title': full_title,
                    'url': detail_url,
                    'number': number,
                    'date': date,
                    'views': views
                }
                
                announcements.append(announcement)
                logger.debug(f"공고 추가: {full_title}")
                
            except Exception as e:
                logger.error(f"공고 파싱 중 오류 (행 {row_index}): {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개의 공고를 파싱했습니다")
        return announcements
    
    def parse_detail_page(self, html_content: str, detail_url: str = None) -> Dict[str, Any]:
        """공고 상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 기본 반환 구조
        result = {
            'content': '',
            'attachments': []
        }
        
        try:
            # 제목 추출
            title_elem = soup.find('h2')
            if title_elem:
                title = title_elem.get_text(strip=True)
                logger.debug(f"제목 추출: {title}")
            
            # 본문 내용 추출
            content_section = soup.find('div', string=lambda text: text and '본문' in text)
            if content_section:
                # 본문 섹션 다음의 실제 내용 찾기
                content_div = content_section.find_next_sibling('div')
                if content_div:
                    # HTML을 마크다운으로 변환
                    content = self.h.handle(str(content_div))
                    result['content'] = content.strip()
                else:
                    logger.warning("본문 내용을 찾을 수 없습니다")
            else:
                # 대체 방법: article 태그 내용 추출
                article = soup.find('article')
                if article:
                    content = self.h.handle(str(article))
                    result['content'] = content.strip()
                else:
                    logger.warning("본문 내용을 찾을 수 없습니다")
            
            # 첨부파일 추출
            attachments_section = soup.find('section', {'id': 'bo_v_file'})
            if attachments_section:
                # 첨부파일 목록 찾기
                attachment_ul = attachments_section.find('ul')
                if attachment_ul:
                    attachment_items = attachment_ul.find_all('li')
                    
                    for item in attachment_items:
                        try:
                            # 다운로드 링크 찾기
                            download_link = item.find('a')
                            if not download_link:
                                continue
                            
                            # 파일명 추출
                            filename = download_link.get_text(strip=True)
                            
                            # 다운로드 URL 구성
                            href = download_link.get('href', '')
                            if not href:
                                continue
                            
                            download_url = urljoin(self.base_url, href)
                            
                            # 첨부파일 정보 저장
                            attachment = {
                                'filename': filename,
                                'url': download_url
                            }
                            
                            result['attachments'].append(attachment)
                            logger.debug(f"첨부파일 추가: {filename}")
                            
                        except Exception as e:
                            logger.error(f"첨부파일 파싱 중 오류: {e}")
                            continue
            
            logger.info(f"상세 페이지 파싱 완료 - 내용: {len(result['content'])}자, 첨부파일: {len(result['attachments'])}개")
            
        except Exception as e:
            logger.error(f"상세 페이지 파싱 중 오류: {e}")
        
        return result
    
    def initialize_session(self):
        """세션 초기화"""
        try:
            logger.info("GGEEA 세션 초기화 중...")
            
            # 메인 페이지 방문 - 세션 쿠키 설정
            response = self.get_page(self.base_url)
            if not response:
                logger.error("메인 페이지 접근 실패")
                return False
            
            # 공지사항 페이지 방문 - 세션 유지
            response = self.get_page(self.list_url)
            if not response:
                logger.error("공지사항 페이지 접근 실패")
                return False
            
            logger.info("세션 초기화 완료")
            return True
            
        except Exception as e:
            logger.error(f"세션 초기화 실패: {e}")
            return False
    
    def _get_page_announcements(self, page_num: int) -> List[Dict[str, Any]]:
        """세션 확인 후 공고 목록 가져오기"""
        # 첫 페이지에서 세션 초기화
        if page_num == 1:
            if not self.initialize_session():
                logger.error("세션 초기화 실패")
                return []
        
        return super()._get_page_announcements(page_num)


def main():
    """메인 실행 함수"""
    import logging
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('ggeea_scraper.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # 스크래퍼 실행
    scraper = EnhancedGgeeaScraper()
    
    # 출력 디렉토리 설정
    output_dir = "output/ggeea"
    
    try:
        logger.info("=== GGEEA 스크래퍼 시작 ===")
        success = scraper.scrape_pages(max_pages=3, output_base=output_dir)
        
        if success:
            logger.info("=== GGEEA 스크래핑 완료 ===")
        else:
            logger.error("=== GGEEA 스크래핑 실패 ===")
            
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
    except Exception as e:
        logger.error(f"예상치 못한 오류: {e}")
    finally:
        # 최종 통계 출력
        stats = scraper.get_stats()
        logger.info(f"최종 통계: {stats}")


if __name__ == "__main__":
    main()