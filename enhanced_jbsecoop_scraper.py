#!/usr/bin/env python3
"""
전북사회적경제연대 Enhanced Scraper
URL: http://www.jbsecoop.or.kr/bbs/board.php?bo_id=notice03
"""

import os
import re
import time
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup
import requests

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from enhanced_base_scraper import EnhancedBaseScraper
except ImportError:
    logger.error("enhanced_base_scraper.py 파일을 찾을 수 없습니다. 같은 디렉토리에 있는지 확인하세요.")
    raise


class EnhancedJBSECOOPScraper(EnhancedBaseScraper):
    """전북사회적경제연대 웹사이트 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "http://www.jbsecoop.or.kr"
        self.site_code = "jbsecoop"
        # 출력 디렉토리 설정
        self.output_dir = os.path.join(os.getcwd(), 'output', 'jbsecoop')
        self.start_url = f"{self.base_url}/bbs/board.php?bo_id=notice03"
        
        # 사이트 특화 설정
        self.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        logger.info("=== JBSECOOP 스크래퍼 시작 ===")
    
    def initialize_session(self) -> bool:
        """세션 초기화"""
        try:
            logger.info("JBSECOOP 세션 초기화 중...")
            
            # 메인 페이지 접속 테스트
            response = self.session.get(self.start_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            # 인코딩 확인
            if response.encoding:
                response.encoding = 'utf-8'
            
            logger.info("세션 초기화 완료")
            return True
            
        except Exception as e:
            logger.error(f"세션 초기화 실패: {e}")
            return False
    
    def get_list_url(self, page_num: int) -> str:
        """목록 페이지 URL 생성"""
        if page_num == 1:
            return self.start_url
        else:
            return f"{self.start_url}&page={page_num}"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 게시글 목록 찾기 - 실제 구조에 맞춤
        # 구조: <ul class="list_table_cont"> 내부의 <a> 태그들
        list_container = soup.find('ul', class_='list_table_cont')
        
        if not list_container:
            logger.warning("게시글 목록 컨테이너를 찾을 수 없습니다")
            return announcements
        
        # 각 게시글 링크 찾기
        post_links = list_container.find_all('a')
        
        logger.info(f"총 {len(post_links)}개의 게시글 링크를 발견했습니다")
        
        for link in post_links:
            try:
                # 링크에서 게시글 ID 추출
                href = link.get('href', '')
                board_id = ""
                if 'wr_id=' in href:
                    wr_id_match = re.search(r'wr_id=(\d+)', href)
                    if wr_id_match:
                        board_id = wr_id_match.group(1)
                
                if not board_id:
                    logger.debug(f"게시글 ID를 찾을 수 없음: {href}")
                    continue
                
                # <li class="list"> 요소 찾기
                list_item = link.find('li', class_='list')
                if not list_item:
                    continue
                
                # 번호 추출
                number_div = list_item.find('div', class_='no')
                number_text = ""
                if number_div:
                    # 공지사항인지 확인 (이미지가 있는지)
                    img_tag = number_div.find('img')
                    if img_tag:
                        alt_text = img_tag.get('alt', '')
                        if '공지' in alt_text:
                            number_text = "공지"
                        else:
                            number_text = "공고"
                    else:
                        number_text = number_div.get_text(strip=True)
                
                # 제목 추출
                subject_div = list_item.find('div', class_='subject')
                title = ""
                if subject_div:
                    title = subject_div.get_text(strip=True)
                    # 공지 아이콘 텍스트 제거
                    title = re.sub(r'^\s*공지\s*', '', title)
                
                if not title:
                    continue
                
                # 작성자 추출
                author_div = list_item.find('div', class_='name')
                author = author_div.get_text(strip=True) if author_div else ""
                
                # 작성일 추출
                date_div = list_item.find('div', class_='date')
                date = date_div.get_text(strip=True) if date_div else ""
                
                # 조회수 추출
                hit_div = list_item.find('div', class_='hit')
                views = hit_div.get_text(strip=True) if hit_div else "0"
                
                # 첨부파일 확인 (제목 영역에 파일 아이콘이 있는지 확인)
                has_attachment = False
                if subject_div:
                    file_img = subject_div.find('img', alt='file')
                    has_attachment = file_img is not None
                
                # 상세 페이지 URL 생성
                detail_url = urljoin(self.base_url, href)
                
                announcement = {
                    'number': number_text,
                    'title': title,
                    'author': author,
                    'date': date,
                    'views': views,
                    'has_attachment': has_attachment,
                    'url': detail_url,  # base scraper에서 'url' 키를 찾음
                    'detail_url': detail_url,
                    'board_id': board_id
                }
                
                announcements.append(announcement)
                logger.debug(f"공고 파싱 완료: {title}")
                
            except Exception as e:
                logger.error(f"게시글 파싱 중 오류: {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개의 공고를 파싱했습니다")
        return announcements
    
    def parse_detail_page(self, html_content: str, detail_url: str = None) -> Dict[str, Any]:
        """공고 상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 현재 상세 페이지 URL 저장 (첨부파일 다운로드 시 Referer로 사용)
        self.current_detail_url = detail_url
        
        # 기본 반환 구조
        result = {
            'content': '',
            'attachments': []
        }
        
        # 본문 내용 추출
        content_text = ""
        
        # 방법 1: 정확한 본문 영역 찾기 (view_content 클래스)
        content_area = soup.find('div', class_='view_content')
        if content_area:
            # HTML을 텍스트로 변환하되 구조 유지
            content_text = self.h.handle(str(content_area))
            # 불필요한 공백 제거
            content_text = re.sub(r'\n{3,}', '\n\n', content_text.strip())
            logger.debug("view_content 클래스에서 내용 추출")
        
        # 방법 2: id="bbs_content" 찾기
        if not content_text:
            content_area = soup.find('div', id='bbs_content')
            if content_area:
                content_text = self.h.handle(str(content_area))
                content_text = re.sub(r'\n{3,}', '\n\n', content_text.strip())
                logger.debug("bbs_content ID에서 내용 추출")
        
        # 방법 3: 제목 다음에 있는 본문 찾기
        if not content_text:
            title_area = soup.find('div', class_='view_tit2')
            if title_area:
                # 제목 다음의 형제 요소들에서 본문 찾기
                current = title_area.find_next_sibling()
                while current:
                    if current.name == 'div' and ('view_content' in current.get('class', []) or 'bbs_content' in current.get('id', '')):
                        content_text = self.h.handle(str(current))
                        content_text = re.sub(r'\n{3,}', '\n\n', content_text.strip())
                        logger.debug("제목 다음 영역에서 내용 추출")
                        break
                    current = current.find_next_sibling()
        
        # 방법 4: 전체 페이지에서 의미있는 내용 찾기 (백업)
        if not content_text or len(content_text) < 50:
            all_text = soup.get_text(strip=True)
            lines = all_text.split('\n')
            meaningful_lines = []
            in_content = False
            
            for line in lines:
                line = line.strip()
                # 제목 이후부터 시작
                if '2025년 제2차 전북' in line or '공고' in line:
                    in_content = True
                    continue
                
                if in_content and line:
                    # 메뉴나 네비게이션 관련 텍스트 제외
                    if (len(line) > 10 and 
                        not any(skip in line for skip in ['메뉴', '네비게이션', '로그인', '회원가입', '홈', '사이트맵', '목록', '수정', '삭제', '이전', '다음', '첨부파일', 'Copyright', '전북사회적경제연대회의']) and
                        not line.isdigit() and
                        not re.match(r'^\d{2}-\d{2}-\d{2}', line) and
                        not re.match(r'^\d{4}-\d{2}-\d{2}', line)):
                        meaningful_lines.append(line)
                
                # 푸터 영역 도달시 중단
                if '개인정보처리방침' in line or 'Copyright' in line:
                    break
            
            if meaningful_lines:
                content_text = '\n'.join(meaningful_lines[:20])  # 상위 20개 라인
                logger.debug("전체 텍스트에서 의미있는 내용 추출")
        
        if content_text and len(content_text) > 10:
            result['content'] = content_text
        else:
            result['content'] = "내용을 추출할 수 없습니다."
            logger.warning("상세 페이지 내용 추출 실패")
        
        # 첨부파일 추출
        # 새로운 구조: <ul class="view_file"> 안의 파일들
        file_list = soup.find('ul', class_='view_file')
        if file_list:
            file_items = file_list.find_all('li')
            for item in file_items:
                try:
                    # onclick 속성에서 다운로드 URL 추출
                    link = item.find('a', onclick=True)
                    if link:
                        onclick = link.get('onclick', '')
                        # onclick="file_download('http://www.jbsecoop.or.kr/bbs/download.php?bo_id=notice03&wr_id=2838&no=1');"
                        url_match = re.search(r'file_download\([\'"]([^\'"]*)[\'"]', onclick)
                        if url_match:
                            download_url = url_match.group(1)
                            
                            # 파일명 추출
                            fname_span = item.find('span', class_='fname')
                            filename = fname_span.get_text(strip=True) if fname_span else 'unknown_file'
                            
                            attachment = {
                                'filename': filename,
                                'url': download_url
                            }
                            
                            result['attachments'].append(attachment)
                            logger.debug(f"첨부파일 추가: {filename}")
                
                except Exception as e:
                    logger.error(f"첨부파일 추출 중 오류: {e}")
                    continue
        
        logger.info(f"상세 페이지 파싱 완료 - 내용: {len(result['content'])}자, 첨부파일: {len(result['attachments'])}개")
        return result
    
    def run_scraper(self, max_pages: int = 3) -> Dict[str, Any]:
        """스크래퍼 실행"""
        try:
            # 세션 초기화
            if not self.initialize_session():
                return {"success": False, "error": "세션 초기화 실패"}
            
            # 부모 클래스의 scrape_pages 메서드 호출 (output_base 지정)
            self.scrape_pages(max_pages, output_base=self.output_dir)
            return {"success": True}
            
        except Exception as e:
            logger.error(f"스크래퍼 실행 중 오류: {e}")
            return {"success": False, "error": str(e)}


def main():
    """메인 함수"""
    scraper = EnhancedJBSECOOPScraper()
    
    try:
        # 3페이지까지 수집
        result = scraper.run_scraper(max_pages=3)
        
        if result.get("success", False):
            logger.info("=== JBSECOOP 스크래핑 완료 ===")
            logger.info(f"최종 통계: {scraper.get_stats()}")
        else:
            logger.error(f"스크래핑 실패: {result.get('error', '알 수 없는 오류')}")
            
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
    except Exception as e:
        logger.error(f"예상치 못한 오류: {e}")
        raise


if __name__ == "__main__":
    main()