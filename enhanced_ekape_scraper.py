# -*- coding: utf-8 -*-
"""
한국축산물품질평가원 (EKAPE) 공지사항 스크래퍼
사이트: https://www.ekape.or.kr/board/list.do?menuId=menu149208&nextUrl=
"""

import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
import logging
from typing import Dict, List, Any
from enhanced_base_scraper import EnhancedBaseScraper

logger = logging.getLogger(__name__)

class EnhancedEkapeScraper(EnhancedBaseScraper):
    """한국축산물품질평가원 공지사항 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.ekape.or.kr"
        self.list_url = "https://www.ekape.or.kr/board/list.do?menuId=menu149208&nextUrl="
        
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
        return f"{self.list_url}&pageIndex={page_num}&pageUnit=10&searchCondition=SUBJECT&searchKeyword="
    
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
                # data-column 속성으로 셀 찾기
                number_cell = row.find('td', attrs={'data-column': '번호'})
                title_cell = row.find('td', attrs={'data-column': '제목'})
                author_cell = row.find('td', attrs={'data-column': '등록자'})
                date_cell = row.find('td', attrs={'data-column': '등록일'})
                views_cell = row.find('td', attrs={'data-column': '조회수'})
                
                if not all([number_cell, title_cell, author_cell, date_cell, views_cell]):
                    continue
                
                # 제목 링크 찾기 (JavaScript 링크)
                title_link = title_cell.find('a')
                if not title_link:
                    continue
                
                # 제목 텍스트 추출
                title = title_link.get_text(strip=True)
                if not title:
                    continue
                
                # JavaScript에서 boardNo 추출
                href = title_link.get('href', '')
                board_no = ""
                if 'goBoardView' in href:
                    board_no_match = re.search(r"goBoardView\('(\d+)'\)", href)
                    if board_no_match:
                        board_no = board_no_match.group(1)
                
                if not board_no:
                    continue
                
                # 상세 페이지 URL 구성
                detail_url = f"{self.base_url}/board/view.do?menuId=menu149208&boardNo={board_no}&dmlType=SELECT&pageIndex=1&pageUnit=10&searchCondition=SUBJECT&searchKeyword="
                
                # 공고 번호 추출
                number = number_cell.get_text(strip=True)
                
                # 등록자 추출
                author = author_cell.get_text(strip=True)
                
                # 날짜 추출
                date = date_cell.get_text(strip=True)
                
                # 조회수 추출
                views = views_cell.get_text(strip=True)
                
                # 첨부파일 여부 확인 (아이콘이나 텍스트로)
                has_attachment = bool(title_cell.find('img', alt=re.compile(r'첨부|파일|attachment', re.I)))
                
                announcement = {
                    'title': title,
                    'url': detail_url,
                    'number': number,
                    'board_no': board_no,
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
        # 현재 상세 페이지 URL 저장 (첨부파일 다운로드 시 Referer로 사용)
        self.current_detail_url = detail_url
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
            
            # 방법 1: 메인 콘텐츠 영역 찾기
            # 여러 가지 패턴으로 본문 찾기
            content_selectors = [
                '.board-view-content',
                '.content-area',
                '.view-content',
                'div[class*="content"]',
                'div[class*="view"]'
            ]
            
            for selector in content_selectors:
                content_div = soup.select_one(selector)
                if content_div:
                    content_text = content_div.get_text(strip=True)
                    if len(content_text) > 100:
                        logger.debug(f"{selector}에서 내용 추출")
                        break
            
            # 방법 2: 테이블 구조에서 본문 찾기
            if not content_text:
                # 상세 페이지가 테이블 구조인 경우
                tables = soup.find_all('table')
                for table in tables:
                    tds = table.find_all('td')
                    for td in tds:
                        text = td.get_text(strip=True)
                        if (len(text) > 100 and 
                            not any(skip in text for skip in ['제목', '등록자', '등록일', '조회수', '첨부파일', '목록', '수정', '삭제'])):
                            content_text = text
                            logger.debug("테이블에서 내용 추출")
                            break
                    if content_text:
                        break
            
            # 방법 3: 전체 페이지에서 의미있는 내용 찾기
            if not content_text:
                # 제목 다음에 오는 긴 텍스트 찾기
                all_text = soup.get_text(strip=True)
                lines = all_text.split('\n')
                meaningful_lines = []
                for line in lines:
                    line = line.strip()
                    if (len(line) > 20 and 
                        not any(skip in line for skip in ['메뉴', '네비게이션', '로그인', '회원가입', '홈', '사이트맵', '첨부파일', '목록', '수정', '삭제', '이전', '다음']) and
                        not line.isdigit() and
                        not re.match(r'^\d{4}-\d{2}-\d{2}', line) and
                        not re.match(r'^\d{4}\.\d{2}\.\d{2}', line)):
                        meaningful_lines.append(line)
                
                if meaningful_lines:
                    content_text = '\n'.join(meaningful_lines[:15])  # 상위 15개 라인만
                    logger.debug("전체 텍스트에서 의미있는 내용 추출")
            
            if content_text:
                result['content'] = content_text
            else:
                result['content'] = "내용을 추출할 수 없습니다."
                logger.warning("상세 페이지 내용 추출 실패")
            
            # 첨부파일 추출 - JavaScript onclick 함수에서 매개변수 추출
            attachment_links = soup.find_all('a', onclick=re.compile(r'attachfileDownload'))
            
            # 현재 게시글 번호 추출
            board_no = ""
            if detail_url:
                parsed_url = urlparse(detail_url)
                query_params = parse_qs(parsed_url.query)
                board_no = query_params.get('boardNo', [''])[0]
            
            for link in attachment_links:
                onclick = link.get('onclick', '')
                filename = link.get_text(strip=True)
                
                # JavaScript 함수에서 매개변수 추출
                # attachfileDownload('/attachfile/attachfileDownload.do','0024','830','1')
                match = re.search(r"attachfileDownload\('([^']+)','([^']+)','([^']+)','([^']+)'\)", onclick)
                if match:
                    context_path = match.group(1)  # /attachfile/attachfileDownload.do
                    board_info_no = match.group(2)  # 0024
                    board_no_param = match.group(3)       # 830
                    file_id = match.group(4)        # 1, 2, 3, 4
                    
                    # 실제 다운로드 URL 구성
                    download_url = f"{self.base_url}{context_path}?boardInfoNo={board_info_no}&boardNo={board_no_param}&fileId={file_id}"
                    
                    attachment = {
                        'filename': filename,
                        'url': download_url
                    }
                    
                    result['attachments'].append(attachment)
                    logger.debug(f"첨부파일 추가: {filename} -> {download_url}")
                else:
                    logger.debug(f"첨부파일 URL 파싱 실패: {onclick}")
            
            # 기존 방식도 유지 (백업용)
            attachment_sections = soup.find_all(string=re.compile(r'첨부파일'))
            
            for section in attachment_sections:
                try:
                    # 첨부파일 텍스트 주변의 부모 요소에서 링크 찾기
                    parent = section.parent
                    if parent:
                        # 첨부파일 다운로드 링크 찾기
                        download_links = parent.find_all('a', href=re.compile(r'#attachdown|download|attach'))
                        if not download_links:
                            # 더 넓은 범위에서 찾기
                            container = parent.find_parent()
                            if container:
                                download_links = container.find_all('a', href=re.compile(r'#attachdown|download|attach'))
                        
                        for link in download_links:
                            href = link.get('href', '')
                            if href and href != '#':
                                # 이미 추가된 첨부파일인지 확인
                                filename = link.get_text(strip=True)
                                if any(att['filename'] == filename for att in result['attachments']):
                                    continue
                                
                                if not filename:
                                    filename = "attachment"
                                
                                # 다운로드 URL 처리
                                if href.startswith('#'):
                                    # JavaScript 다운로드 링크인 경우
                                    onclick = link.get('onclick', '')
                                    if onclick:
                                        # onclick에서 실제 다운로드 URL 추출 시도
                                        url_match = re.search(r"'([^']+)'", onclick)
                                        if url_match:
                                            download_url = urljoin(self.base_url, url_match.group(1))
                                        else:
                                            download_url = href
                                    else:
                                        download_url = href
                                else:
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
            
            # 추가적으로 모든 다운로드 링크 찾기
            if not result['attachments']:
                all_download_links = soup.find_all('a', href=re.compile(r'download|attach'))
                for link in all_download_links:
                    href = link.get('href', '')
                    if href and href != '#':
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
            logger.info("EKAPE 세션 초기화 중...")
            
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
            logging.FileHandler('ekape_scraper.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # 스크래퍼 실행
    scraper = EnhancedEkapeScraper()
    
    # 출력 디렉토리 설정
    output_dir = "output/ekape"
    
    try:
        logger.info("=== EKAPE 스크래퍼 시작 ===")
        success = scraper.scrape_pages(max_pages=3, output_base=output_dir)
        
        if success:
            logger.info("=== EKAPE 스크래핑 완료 ===")
        else:
            logger.error("=== EKAPE 스크래핑 실패 ===")
            
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