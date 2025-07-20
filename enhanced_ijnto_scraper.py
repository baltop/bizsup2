# -*- coding: utf-8 -*-
"""
(재)인천국제관광공사 (IJNTO) 공지사항 스크래퍼
사이트: https://ijnto.or.kr/plaza/notice/lists/
"""

import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import logging
from typing import Dict, List, Any
from enhanced_base_scraper import EnhancedBaseScraper

logger = logging.getLogger(__name__)

class EnhancedIjntoScraper(EnhancedBaseScraper):
    """(재)인천국제관광공사 공지사항 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://ijnto.or.kr"
        self.list_url = "https://ijnto.or.kr/plaza/notice/lists/"
        
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
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        })
    
    def get_list_url(self, page_num: int) -> str:
        """페이지별 목록 URL 생성"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}{page_num}"
    
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
                if len(cells) < 6:
                    continue
                
                # 각 셀 파싱
                number_cell = cells[0]  # 번호
                title_cell = cells[1]   # 제목
                category_cell = cells[2]  # 분류
                author_cell = cells[3]   # 작성자
                date_cell = cells[4]     # 등록일
                views_cell = cells[5]    # 조회수
                
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
                
                # 분류 추출
                category = category_cell.get_text(strip=True)
                
                # 작성자 추출
                author = author_cell.get_text(strip=True)
                
                # 날짜 추출
                date = date_cell.get_text(strip=True)
                
                # 조회수 추출
                views = views_cell.get_text(strip=True)
                
                # 공고 ID 추출 (URL에서)
                notice_id_match = re.search(r'/read/(\d+)', href)
                notice_id = notice_id_match.group(1) if notice_id_match else number
                
                announcement = {
                    'title': title,
                    'url': detail_url,
                    'number': number,
                    'notice_id': notice_id,
                    'category': category,
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
            # 본문 내용 추출 - iframe 내부 내용 또는 메인 콘텐츠
            content_text = ""
            
            # 1. iframe 내부 내용 시도
            iframe = soup.find('iframe')
            if iframe:
                # iframe src가 있으면 별도 요청이 필요하지만, 
                # 보통 innerHTML로 직접 내용이 포함되어 있음
                iframe_content = iframe.get_text(strip=True)
                if iframe_content:
                    content_text = iframe_content
                    logger.debug("iframe에서 내용 추출")
                else:
                    # iframe src로 추가 요청
                    iframe_src = iframe.get('src')
                    if iframe_src:
                        iframe_url = urljoin(self.base_url, iframe_src)
                        iframe_response = self.get_page(iframe_url)
                        if iframe_response:
                            iframe_soup = BeautifulSoup(iframe_response.text, 'html.parser')
                            content_text = iframe_soup.get_text(strip=True)
                            logger.debug("iframe src에서 내용 추출")
            
            # 2. 메인 콘텐츠 영역에서 직접 추출
            if not content_text:
                # 공지사항 내용이 포함된 div 찾기
                content_divs = soup.find_all('div', class_=lambda x: x and 'content' in x.lower())
                if content_divs:
                    content_text = content_divs[0].get_text(strip=True)
                    logger.debug("content div에서 내용 추출")
                else:
                    # 전체 텍스트에서 의미있는 내용 추출
                    all_text = soup.get_text(strip=True)
                    # 네비게이션, 메뉴 등 불필요한 내용 제거
                    lines = all_text.split('\n')
                    meaningful_lines = []
                    for line in lines:
                        line = line.strip()
                        if len(line) > 10 and not any(skip in line for skip in ['메뉴', '네비게이션', '로그인', '회원가입', '홈', '사이트맵']):
                            meaningful_lines.append(line)
                    content_text = '\n'.join(meaningful_lines)
                    logger.debug("전체 텍스트에서 내용 추출")
            
            # HTML을 마크다운으로 변환
            if content_text:
                result['content'] = content_text
            else:
                result['content'] = "내용을 추출할 수 없습니다."
                logger.warning("상세 페이지 내용 추출 실패")
            
            # 첨부파일 추출
            # "파일첨부" 텍스트가 있는 섹션 찾기
            attachment_sections = soup.find_all(string=re.compile(r'파일첨부'))
            
            for section in attachment_sections:
                try:
                    # 파일첨부 텍스트 주변의 부모 요소에서 링크 찾기
                    parent = section.parent
                    if parent:
                        # 부모 요소와 형제 요소들에서 파일 링크 찾기
                        file_links = parent.find_all('a', href=re.compile(r'/upload/editor/'))
                        if not file_links:
                            # 더 넓은 범위에서 찾기
                            container = parent.find_parent()
                            if container:
                                file_links = container.find_all('a', href=re.compile(r'/upload/editor/'))
                        
                        for link in file_links:
                            href = link.get('href', '')
                            if href:
                                filename = link.get_text(strip=True)
                                if not filename:
                                    # URL에서 파일명 추출
                                    filename = href.split('/')[-1]
                                
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
            
            # 추가적으로 모든 /upload/editor/ 링크 찾기
            if not result['attachments']:
                all_upload_links = soup.find_all('a', href=re.compile(r'/upload/editor/'))
                for link in all_upload_links:
                    href = link.get('href', '')
                    if href:
                        filename = link.get_text(strip=True)
                        if not filename:
                            filename = href.split('/')[-1]
                        
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
            logger.info("IJNTO 세션 초기화 중...")
            
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
            logging.FileHandler('ijnto_scraper.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # 스크래퍼 실행
    scraper = EnhancedIjntoScraper()
    
    # 출력 디렉토리 설정
    output_dir = "output/ijnto"
    
    try:
        logger.info("=== IJNTO 스크래퍼 시작 ===")
        success = scraper.scrape_pages(max_pages=3, output_base=output_dir)
        
        if success:
            logger.info("=== IJNTO 스크래핑 완료 ===")
        else:
            logger.error("=== IJNTO 스크래핑 실패 ===")
            
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