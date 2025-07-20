# -*- coding: utf-8 -*-
"""
충청남도농업기술원 (CNNONGUP) 공지사항 스크래퍼
사이트: https://cnnongup.chungnam.go.kr/board/B0013.cs?m=315
"""

import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
import logging
from typing import Dict, List, Any
from enhanced_base_scraper import EnhancedBaseScraper

logger = logging.getLogger(__name__)

class EnhancedCnnongupScraper(EnhancedBaseScraper):
    """충청남도농업기술원 공지사항 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://cnnongup.chungnam.go.kr"
        self.list_url = "https://cnnongup.chungnam.go.kr/board/B0013.cs?m=315"
        
        # 사이트별 설정
        self.delay_between_requests = 1.5  # 1.5초 간격
        self.delay_between_pages = 2
        
        # 세션 헤더 추가
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
        })
    
    def get_list_url(self, page_num: int) -> str:
        """페이지별 목록 URL 생성"""
        return f"{self.list_url}&pageIndex={page_num}&pageUnit=10"
    
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
            # tbody가 없으면 table에서 직접 tr 찾기
            rows = table.find_all('tr')
            # 첫 번째 행이 헤더인 경우 제외
            if rows and rows[0].find('th'):
                rows = rows[1:]
        else:
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
                
                # 상대 URL을 절대 URL로 변환
                if href.startswith('?'):
                    detail_url = f"{self.base_url}/board/B0013.cs{href}"
                else:
                    detail_url = urljoin(self.base_url, href)
                
                # 공고 번호 추출
                number = number_cell.get_text(strip=True)
                
                # 작성자 추출
                author = author_cell.get_text(strip=True)
                
                # 날짜 추출
                date = date_cell.get_text(strip=True)
                
                # 조회수 추출
                views = views_cell.get_text(strip=True)
                
                # 첨부파일 여부 확인
                attachment_icon = title_cell.find('img', alt='첨부파일')
                has_attachment = attachment_icon is not None
                
                # 공고 ID 추출 (URL에서)
                article_id = ""
                if 'articleId=' in href:
                    article_id_match = re.search(r'articleId=(\d+)', href)
                    if article_id_match:
                        article_id = article_id_match.group(1)
                
                announcement = {
                    'title': title,
                    'url': detail_url,
                    'number': number,
                    'article_id': article_id,
                    'author': author,
                    'date': date,
                    'views': views,
                    'has_attachment': has_attachment
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
            
            # 방법 1: post-content 클래스 찾기
            post_content = soup.find('div', class_='post-content')
            if post_content:
                content_text = post_content.get_text(strip=True)
                logger.debug("post-content div에서 내용 추출")
            
            # 방법 2: content-area 내부에서 본문 찾기
            if not content_text:
                content_area = soup.find('div', class_='content-area')
                if content_area:
                    # 헤더 정보 다음의 div들에서 본문 찾기
                    divs = content_area.find_all('div')
                    for div in divs:
                        if div.get('class') and 'post-content' in div.get('class', []):
                            content_text = div.get_text(strip=True)
                            break
                        elif not div.get('class'):  # 클래스가 없는 div
                            text = div.get_text(strip=True)
                            if len(text) > 100:  # 충분히 긴 텍스트
                                content_text = text
                                break
                
                logger.debug("content-area에서 내용 추출")
            
            # 방법 3: 전체 페이지에서 의미있는 내용 찾기
            if not content_text:
                # 제목 정보가 있는 dl 태그 다음의 내용 찾기
                post_header = soup.find('dl', class_='post-header')
                if post_header:
                    next_elem = post_header.find_next_sibling()
                    while next_elem:
                        if next_elem.name == 'div':
                            text = next_elem.get_text(strip=True)
                            if len(text) > 50 and '첨부파일' not in text:
                                content_text = text
                                break
                        next_elem = next_elem.find_next_sibling()
                
                logger.debug("post-header 다음에서 내용 추출")
            
            # 방법 4: 전체 텍스트에서 의미있는 부분 추출
            if not content_text:
                all_text = soup.get_text(strip=True)
                lines = all_text.split('\n')
                meaningful_lines = []
                for line in lines:
                    line = line.strip()
                    if (len(line) > 20 and 
                        not any(skip in line for skip in ['메뉴', '네비게이션', '로그인', '회원가입', '홈', '사이트맵', '첨부파일', '미리보기']) and
                        not line.isdigit() and
                        not re.match(r'^\d{4}-\d{2}-\d{2}', line)):
                        meaningful_lines.append(line)
                
                if meaningful_lines:
                    content_text = '\n'.join(meaningful_lines[:15])  # 상위 15개 라인만
                
                logger.debug("전체 텍스트에서 의미있는 내용 추출")
            
            if content_text:
                result['content'] = content_text
            else:
                result['content'] = "내용을 추출할 수 없습니다."
                logger.warning("상세 페이지 내용 추출 실패")
            
            # 첨부파일 추출
            # attachments 클래스 영역에서 다운로드 링크 찾기
            attachments_div = soup.find('div', class_='attachments')
            if attachments_div:
                download_links = attachments_div.find_all('a', href=re.compile(r'act=download'))
                for link in download_links:
                    href = link.get('href', '')
                    if href:
                        # 링크 텍스트에서 파일명 추출
                        link_text = link.get_text(strip=True)
                        if link_text and '(' in link_text:
                            # "파일명.hwp (92KByte)" 형태에서 파일명만 추출
                            filename = link_text.split('(')[0].strip()
                        else:
                            filename = link_text if link_text else "attachment"
                        
                        # 상대 URL을 절대 URL로 변환
                        if href.startswith('?'):
                            download_url = f"{self.base_url}/board/B0013.cs{href}"
                        else:
                            download_url = urljoin(self.base_url, href)
                        
                        attachment = {
                            'filename': filename,
                            'url': download_url
                        }
                        
                        result['attachments'].append(attachment)
                        logger.debug(f"첨부파일 추가: {filename}")
            
            # 추가적으로 모든 download 링크 찾기
            if not result['attachments']:
                all_download_links = soup.find_all('a', href=re.compile(r'act=download'))
                for link in all_download_links:
                    href = link.get('href', '')
                    if href:
                        link_text = link.get_text(strip=True)
                        if link_text and '(' in link_text:
                            filename = link_text.split('(')[0].strip()
                        else:
                            filename = link_text if link_text else "attachment"
                        
                        if href.startswith('?'):
                            download_url = f"{self.base_url}/board/B0013.cs{href}"
                        else:
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
            logger.info("CNNONGUP 세션 초기화 중...")
            
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
            logging.FileHandler('cnnongup_scraper.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # 스크래퍼 실행
    scraper = EnhancedCnnongupScraper()
    
    # 출력 디렉토리 설정
    output_dir = "output/cnnongup"
    
    try:
        logger.info("=== CNNONGUP 스크래퍼 시작 ===")
        success = scraper.scrape_pages(max_pages=3, output_base=output_dir)
        
        if success:
            logger.info("=== CNNONGUP 스크래핑 완료 ===")
        else:
            logger.error("=== CNNONGUP 스크래핑 실패 ===")
            
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