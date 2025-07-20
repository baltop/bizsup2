# -*- coding: utf-8 -*-
"""
한국전자기술연구원 (EKTA) 공지사항 스크래퍼
사이트: http://www.ekta.kr/?act=board&bbs_code=sub4_2
"""

import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
import logging
from typing import Dict, List, Any
from enhanced_base_scraper import EnhancedBaseScraper

logger = logging.getLogger(__name__)

class EnhancedEktaScraper(EnhancedBaseScraper):
    """한국전자기술연구원 공지사항 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "http://www.ekta.kr"
        self.list_url = "http://www.ekta.kr/?act=board&bbs_code=sub4_2"
        
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
        })
    
    def get_list_url(self, page_num: int) -> str:
        """페이지별 목록 URL 생성"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}&page={page_num}"
    
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
            # tbody가 없으면 table 직접 사용
            rows = table.find_all('tr')
        else:
            rows = tbody.find_all('tr')
        
        # 첫 번째 행이 헤더인 경우 제외
        if rows and rows[0].find('th'):
            rows = rows[1:]
        
        logger.info(f"총 {len(rows)}개의 공고 행을 발견했습니다")
        
        for row_index, row in enumerate(rows):
            try:
                cells = row.find_all('td')
                if len(cells) < 4:
                    continue
                
                # 각 셀 파싱
                number_cell = cells[0]  # 번호
                title_cell = cells[1]   # 제목
                date_cell = cells[2]    # 날짜
                views_cell = cells[3]   # 조회수
                
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
                
                # 날짜 추출
                date = date_cell.get_text(strip=True)
                
                # 조회수 추출
                views = views_cell.get_text(strip=True)
                
                # 첨부파일 여부 확인
                file_icon = title_cell.find('img', alt='FILE')
                has_attachment = file_icon is not None
                
                # 공고 시퀀스 추출 (URL에서)
                bbs_seq = ""
                if 'bbs_seq=' in href:
                    bbs_seq_match = re.search(r'bbs_seq=(\d+)', href)
                    if bbs_seq_match:
                        bbs_seq = bbs_seq_match.group(1)
                
                announcement = {
                    'title': title,
                    'url': detail_url,
                    'number': number,
                    'bbs_seq': bbs_seq,
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
            
            # 상세 페이지에서 메인 콘텐츠 찾기
            # 방법 1: 제목 다음의 내용 찾기
            title_elements = soup.find_all(['h1', 'h2', 'h3', 'generic'])
            for elem in title_elements:
                if elem.get_text(strip=True) and len(elem.get_text(strip=True)) > 10:
                    # 제목 다음의 형제 요소들에서 내용 찾기
                    next_elem = elem.find_next_sibling()
                    content_parts = []
                    while next_elem:
                        if next_elem.name in ['div', 'p', 'span', 'generic']:
                            text = next_elem.get_text(strip=True)
                            if text and len(text) > 10:
                                content_parts.append(text)
                        next_elem = next_elem.find_next_sibling()
                    
                    if content_parts:
                        content_text = '\n'.join(content_parts)
                        break
            
            # 방법 2: 메인 콘텐츠 영역 찾기
            if not content_text:
                # div나 td 등에서 긴 텍스트 찾기
                for elem in soup.find_all(['div', 'td', 'p']):
                    text = elem.get_text(strip=True)
                    if len(text) > 100:  # 100자 이상의 텍스트
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
                        not any(skip in line for skip in ['메뉴', '네비게이션', '로그인', '회원가입', '홈페이지', '이전', '다음', '목록']) and
                        not line.isdigit() and
                        not re.match(r'^\d{4}\.\d{2}\.\d{2}', line)):
                        meaningful_lines.append(line)
                
                if meaningful_lines:
                    content_text = '\n'.join(meaningful_lines[:10])  # 상위 10개 라인만
            
            if content_text:
                result['content'] = content_text
            else:
                result['content'] = "내용을 추출할 수 없습니다."
                logger.warning("상세 페이지 내용 추출 실패")
            
            # 첨부파일 추출
            # "첨부파일" 텍스트가 있는 섹션 찾기
            attachment_sections = soup.find_all(string=re.compile(r'첨부파일'))
            
            for section in attachment_sections:
                try:
                    # 첨부파일 텍스트 주변의 부모 요소에서 링크 찾기
                    parent = section.parent
                    if parent:
                        # 첨부파일 다운로드 링크 찾기
                        download_links = parent.find_all('a', href=re.compile(r'common\.download_act'))
                        if not download_links:
                            # 더 넓은 범위에서 찾기
                            container = parent.find_parent()
                            if container:
                                download_links = container.find_all('a', href=re.compile(r'common\.download_act'))
                        
                        for link in download_links:
                            href = link.get('href', '')
                            if href:
                                # 링크 텍스트에서 파일명 추출
                                filename = link.get_text(strip=True)
                                if not filename:
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
            
            # 추가적으로 모든 common.download_act 링크 찾기
            if not result['attachments']:
                all_download_links = soup.find_all('a', href=re.compile(r'common\.download_act'))
                for link in all_download_links:
                    href = link.get('href', '')
                    if href:
                        filename = link.get_text(strip=True)
                        if not filename:
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
            logger.info("EKTA 세션 초기화 중...")
            
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
            logging.FileHandler('ekta_scraper.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # 스크래퍼 실행
    scraper = EnhancedEktaScraper()
    
    # 출력 디렉토리 설정
    output_dir = "output/ekta"
    
    try:
        logger.info("=== EKTA 스크래퍼 시작 ===")
        success = scraper.scrape_pages(max_pages=3, output_base=output_dir)
        
        if success:
            logger.info("=== EKTA 스크래핑 완료 ===")
        else:
            logger.error("=== EKTA 스크래핑 실패 ===")
            
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