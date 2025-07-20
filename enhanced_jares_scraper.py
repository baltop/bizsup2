# -*- coding: utf-8 -*-
"""
전라남도 농업기술원 (JARES) 공지사항 스크래퍼
사이트: https://www.jares.go.kr/main/board/19
"""

import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import logging
from typing import Dict, List, Any
from enhanced_base_scraper import EnhancedBaseScraper

logger = logging.getLogger(__name__)

class EnhancedJaresScraper(EnhancedBaseScraper):
    """전라남도 농업기술원 공지사항 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.jares.go.kr"
        self.list_url = "https://www.jares.go.kr/main/board/19"
        
        # 사이트별 설정
        self.delay_between_requests = 1.5  # 1.5초 간격
        self.delay_between_pages = 2
        
        # 세션 헤더 추가
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
        })
    
    def get_list_url(self, page_num: int) -> str:
        """페이지별 목록 URL 생성"""
        if page_num == 1:
            return f"{self.list_url}/1"
        else:
            return f"{self.list_url}/{page_num}"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """공지사항 목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 공지사항 테이블 찾기
        table = soup.find('table')
        if not table:
            logger.warning("공지사항 테이블을 찾을 수 없습니다")
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
                if len(cells) < 5:
                    continue
                
                # 각 셀 파싱
                number_cell = cells[0]  # 번호
                title_cell = cells[1]   # 제목
                author_cell = cells[2]  # 작성자
                date_cell = cells[3]    # 작성일
                views_cell = cells[4]   # 조회수
                
                # 제목 링크 찾기
                title_link = title_cell.find('a')
                if not title_link:
                    continue
                
                # 제목 텍스트 추출
                title = title_link.get_text(strip=True)
                if not title:
                    continue
                
                # URL 구성
                href = title_link.get('href', '')
                if not href:
                    continue
                
                detail_url = urljoin(self.base_url, href)
                
                # 공고 번호 추출
                number = number_cell.get_text(strip=True)
                
                # 작성자 추출
                author = author_cell.get_text(strip=True)
                
                # 날짜 추출
                date = date_cell.get_text(strip=True)
                
                # 조회수 추출
                views = views_cell.get_text(strip=True)
                
                # 공고 ID 추출 (URL에서)
                post_id_match = re.search(r'/read/(\d+)', href)
                post_id = post_id_match.group(1) if post_id_match else number
                
                # 페이지 번호 추출 (URL에서)
                page_num_match = re.search(r'/board/19/(\d+)', href)
                page_num = page_num_match.group(1) if page_num_match else "1"
                
                announcement = {
                    'title': title,
                    'url': detail_url,
                    'number': number,
                    'post_id': post_id,
                    'page_num': page_num,
                    'author': author,
                    'date': date,
                    'views': views
                }
                
                announcements.append(announcement)
                logger.debug(f"공고 추가: {title}")
                
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
            # 본문 내용 추출
            content_text = ""
            
            # 방법 1: 메인 콘텐츠 영역에서 div 찾기
            # 제목 다음에 있는 div들에서 본문 찾기
            h3_title = soup.find('h3')
            if h3_title:
                # 제목 다음의 div들 탐색
                next_elem = h3_title.find_next_sibling()
                content_parts = []
                
                while next_elem:
                    if next_elem.name == 'div':
                        text = next_elem.get_text(strip=True)
                        # 작성자나 조회수가 아닌 긴 텍스트만 추출
                        if (text and len(text) > 50 and 
                            not text.startswith('작성자') and
                            not text.startswith('조회수') and
                            not text.startswith('작성일') and
                            '파일첨부' not in text):
                            content_parts.append(text)
                    next_elem = next_elem.find_next_sibling()
                
                if content_parts:
                    content_text = '\n'.join(content_parts)
            
            # 방법 2: 전체 div에서 긴 텍스트 찾기
            if not content_text:
                for div in soup.find_all('div'):
                    text = div.get_text(strip=True)
                    if (len(text) > 100 and 
                        not any(skip in text for skip in ['작성자', '조회수', '작성일', '파일첨부', '메뉴', '네비게이션', '로그인'])):
                        content_text = text
                        break
            
            # 방법 3: 전체 텍스트에서 의미있는 부분 추출
            if not content_text:
                all_text = soup.get_text(strip=True)
                lines = all_text.split('\n')
                meaningful_lines = []
                for line in lines:
                    line = line.strip()
                    if (len(line) > 20 and 
                        not any(skip in line for skip in ['메뉴', '네비게이션', '로그인', '회원가입', '홈', '사이트맵', '작성자', '조회수']) and
                        not line.isdigit() and
                        not re.match(r'^\d{4}\.\d{2}\.\d{2}', line)):
                        meaningful_lines.append(line)
                
                if meaningful_lines:
                    content_text = '\n'.join(meaningful_lines[:15])  # 상위 15개 라인만
            
            if content_text:
                result['content'] = content_text
            else:
                result['content'] = "내용을 추출할 수 없습니다."
                logger.warning("상세 페이지 내용 추출 실패")
            
            # 첨부파일 추출
            # "파일첨부" 또는 "첨부파일"이 있는 영역 찾기
            attachment_sections = soup.find_all(string=re.compile(r'파일첨부|첨부파일'))
            
            for section in attachment_sections:
                try:
                    # 파일첨부 텍스트 주변의 부모 요소에서 링크 찾기
                    parent = section.parent
                    if parent:
                        # 부모 요소에서 다운로드 링크 찾기
                        download_links = parent.find_all('a', href=re.compile(r'/download/'))
                        if not download_links:
                            # 더 넓은 범위에서 찾기
                            container = parent.find_parent()
                            if container:
                                download_links = container.find_all('a', href=re.compile(r'/download/'))
                        
                        for link in download_links:
                            href = link.get('href', '')
                            if href and '/download/' in href:
                                # 링크 텍스트에서 파일명 추출
                                filename = link.get_text(strip=True)
                                if not filename or filename == '다운로드':
                                    # 형제 요소에서 파일명 찾기
                                    prev_sibling = link.find_previous_sibling()
                                    if prev_sibling:
                                        filename = prev_sibling.get_text(strip=True)
                                        if not filename:
                                            filename = "attachment"
                                    else:
                                        filename = "attachment"
                                
                                download_url = urljoin(self.base_url, href)
                                
                                attachment = {
                                    'filename': filename,
                                    'url': download_url
                                }
                                
                                result['attachments'].append(attachment)
                                logger.debug(f"첨부파일 추가: {filename}")
                                
                except Exception as e:
                    logger.error(f"첨부파일 파싱 중 오류: {e}")
                    continue
            
            # 추가적으로 모든 /download/ 링크 찾기
            if not result['attachments']:
                all_download_links = soup.find_all('a', href=re.compile(r'/download/'))
                for link in all_download_links:
                    href = link.get('href', '')
                    if href:
                        # 파일명 추출 시도
                        filename = link.get_text(strip=True)
                        if not filename or filename == '다운로드':
                            # 주변 텍스트에서 파일명 찾기
                            parent = link.parent
                            if parent:
                                parent_text = parent.get_text(strip=True)
                                # 파일 확장자가 포함된 텍스트 찾기
                                file_match = re.search(r'([^/\s]+\.(hwp|pdf|docx?|xlsx?|pptx?|zip|rar|7z|jpg|jpeg|png|gif))', parent_text, re.IGNORECASE)
                                if file_match:
                                    filename = file_match.group(1)
                                else:
                                    filename = "attachment"
                            else:
                                filename = "attachment"
                        
                        download_url = urljoin(self.base_url, href)
                        
                        attachment = {
                            'filename': filename,
                            'url': download_url
                        }
                        
                        result['attachments'].append(attachment)
                        logger.debug(f"추가 첨부파일 발견: {filename}")
            
            logger.info(f"상세 페이지 파싱 완료 - 내용: {len(result['content'])}자, 첨부파일: {len(result['attachments'])}개")
            
        except Exception as e:
            logger.error(f"상세 페이지 파싱 중 오류: {e}")
        
        return result
    
    def initialize_session(self):
        """세션 초기화"""
        try:
            logger.info("JARES 세션 초기화 중...")
            
            # 메인 페이지 방문 - 세션 쿠키 설정
            response = self.get_page(self.base_url)
            if not response:
                logger.error("메인 페이지 접근 실패")
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
            logging.FileHandler('jares_scraper.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # 스크래퍼 실행
    scraper = EnhancedJaresScraper()
    
    # 출력 디렉토리 설정
    output_dir = "output/jares"
    
    try:
        logger.info("=== JARES 스크래퍼 시작 ===")
        success = scraper.scrape_pages(max_pages=3, output_base=output_dir)
        
        if success:
            logger.info("=== JARES 스크래핑 완료 ===")
        else:
            logger.error("=== JARES 스크래핑 실패 ===")
            
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