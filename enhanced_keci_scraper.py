# -*- coding: utf-8 -*-
"""
KECI 한국환경공단 게시판 스크래퍼
한국환경공단 공지사항 게시판 대상
"""

import re
import time
import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin, parse_qs, urlparse
from enhanced_base_scraper import EnhancedBaseScraper
import logging

logger = logging.getLogger(__name__)

class EnhancedKeciScraper(EnhancedBaseScraper):
    """KECI 한국환경공단 게시판 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.keci.or.kr"
        self.list_url = "https://www.keci.or.kr/common/bbs/selectPageListBbs.do?bbs_code=A1004"
        self.site_code = "keci"
        
        # 세션 관련 설정
        self.session_initialized = False
        
        # 중복 방지 기능 활성화
        self.enable_duplicate_check = True
        
        # 재시도 설정
        self.max_retries = 3
        self.retry_delay = 1.5
        
        # 헤더 설정
        self.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # 세션 업데이트
        self.session.headers.update(self.headers)
    
    def get_list_url(self, page_num: int) -> str:
        """페이지별 목록 URL 생성"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}&currentPage={page_num}"
    
    def initialize_session(self):
        """세션 초기화"""
        if self.session_initialized:
            return True
        
        try:
            # 메인 페이지 방문으로 세션 초기화
            main_response = self.get_page(self.base_url)
            if not main_response:
                logger.error("메인 페이지 접근 실패")
                return False
            
            # 게시판 첫 페이지 방문
            response = self.get_page(self.list_url)
            if not response:
                logger.error("게시판 접근 실패")
                return False
            
            self.session_initialized = True
            logger.info("KECI 세션 초기화 성공")
            return True
        
        except Exception as e:
            logger.error(f"세션 초기화 실패: {e}")
            return False
    
    def parse_list_page(self, html_content: str) -> list:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        logger.info(f"페이지 파싱 시작 - 현재 페이지: {self.current_page_num}")
        
        # 게시글 목록 찾기 (헤더 제외)
        posts = soup.select('.brd_list ul li:not(:first-child)')
        
        if not posts:
            logger.warning("게시글 목록을 찾을 수 없습니다")
            return announcements
        
        for post_index, post in enumerate(posts):
            try:
                # 제목 및 링크 추출
                title_link = post.select_one('p.brd_title a.link')
                if not title_link:
                    continue
                
                title = title_link.get_text(strip=True)
                if not title:
                    continue
                
                # onclick에서 bbs_seq 추출
                onclick = title_link.get('onclick', '')
                if not onclick:
                    continue
                
                # fnDetail(7759) 형태에서 숫자 추출
                match = re.search(r'fnDetail\((\d+)\)', onclick)
                if not match:
                    logger.warning(f"onclick에서 bbs_seq 추출 실패: {onclick}")
                    continue
                
                bbs_seq = match.group(1)
                detail_url = f"{self.base_url}/common/bbs/selectBbs.do?bbs_code=A1004&bbs_seq={bbs_seq}"
                
                # 게시글 번호
                num_elem = post.select_one('p.brd_num')
                number = num_elem.get_text(strip=True) if num_elem else ""
                
                # 작성자
                writer_elem = post.select_one('p.brd_wrtr')
                writer = writer_elem.get_text(strip=True) if writer_elem else ""
                
                # 등록일
                date_elem = post.select_one('p.brd_date')
                date = date_elem.get_text(strip=True) if date_elem else ""
                
                # 조회수
                views_elem = post.select_one('p.brd_cnt')
                views = views_elem.get_text(strip=True) if views_elem else ""
                
                announcement = {
                    'title': title,
                    'url': detail_url,
                    'date': date,
                    'views': views,
                    'writer': writer,
                    'number': number,
                    'bbs_seq': bbs_seq
                }
                
                announcements.append(announcement)
                logger.debug(f"공고 추가: {title} (번호: {number})")
                
            except Exception as e:
                logger.error(f"게시글 파싱 중 오류 (게시글 {post_index}): {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
        return announcements
    
    def parse_detail_page(self, html_content: str) -> dict:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출
        title = "제목 없음"
        title_elem = soup.find('h4')
        if title_elem:
            title = title_elem.get_text(strip=True)
        
        # 메타 정보 추출
        meta_info = {}
        
        # 본문 내용 추출
        content = ""
        content_div = soup.find('article', class_='pb_textarea')
        
        if content_div:
            # 이미지와 텍스트 내용 모두 추출
            content_parts = []
            
            # 모든 텍스트 요소 추출
            for element in content_div.find_all(['p', 'div', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                text = element.get_text(strip=True)
                if text and len(text) > 1:
                    content_parts.append(text)
            
            # 이미지 정보 추출
            images = content_div.find_all('img')
            for img in images:
                src = img.get('src', '')
                alt = img.get('alt', '')
                if src:
                    img_info = f"![{alt}]({src})" if alt else f"![이미지]({src})"
                    content_parts.append(img_info)
            
            if content_parts:
                content = '\n\n'.join(content_parts)
            else:
                content = content_div.get_text(separator='\n', strip=True)
        else:
            content = "내용을 찾을 수 없습니다."
        
        # 첨부파일 찾기
        attachments = []
        
        logger.info(f"첨부파일 검색 시작...")
        
        # 첨부파일 목록 찾기
        file_list = soup.find('ul', class_='file_list')
        
        if file_list:
            logger.info(f"첨부파일 목록 발견")
            
            # 각 파일 링크 찾기
            file_links = file_list.find_all('a', class_='file_btn')
            
            for link in file_links:
                file_id = link.get('data-file_id')
                file_name_elem = link.find('span', class_='file_txt')
                
                if file_id and file_name_elem:
                    file_name = file_name_elem.get_text(strip=True)
                    download_url = f"{self.base_url}/common/file/FileDown.do?file_id={file_id}"
                    
                    logger.info(f"첨부파일 발견: {file_name} (ID: {file_id})")
                    
                    attachments.append({
                        'filename': file_name,
                        'url': download_url,
                        'file_id': file_id
                    })
        else:
            logger.info("첨부파일이 없습니다.")
        
        logger.info(f"총 {len(attachments)}개 첨부파일 발견")
        
        return {
            'title': title,
            'content': content,
            'attachments': attachments,
            'meta_info': meta_info
        }
    
    def _get_page_announcements(self, page_num: int) -> list:
        """세션 확인 후 공고 목록 가져오기"""
        if not self.initialize_session():
            logger.error("세션 초기화 실패")
            return []
        
        return super()._get_page_announcements(page_num)


def main():
    """메인 실행 함수"""
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('keci_scraper.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # 스크래퍼 실행
    scraper = EnhancedKeciScraper()
    
    try:
        # 출력 디렉토리 설정
        output_dir = f'output/{scraper.site_code}'
        
        # 3페이지 수집
        logger.info("="*60)
        logger.info(f"🚀 KECI 한국환경공단 게시판 스크래핑 시작")
        logger.info(f"📂 출력 디렉토리: {output_dir}")
        logger.info(f"🔄 중복 방지 기능: {'활성화' if scraper.enable_duplicate_check else '비활성화'}")
        logger.info("="*60)
        
        success = scraper.scrape_pages(max_pages=3, output_base=output_dir)
        
        if success:
            logger.info("✅ 스크래핑 완료!")
            
            # 수집 결과 요약
            content_files = []
            for root, dirs, files in os.walk(output_dir):
                for file in files:
                    if file == 'content.md':
                        content_files.append(os.path.join(root, file))
            
            logger.info(f"📄 수집된 content.md 파일: {len(content_files)}개")
            
            # 첨부파일 확인
            attachment_files = []
            for root, dirs, files in os.walk(output_dir):
                if 'attachments' in root:
                    attachment_files.extend([os.path.join(root, f) for f in files])
            
            logger.info(f"📎 다운로드된 첨부파일: {len(attachment_files)}개")
            
        else:
            logger.error("❌ 스크래핑 실패")
            
    except KeyboardInterrupt:
        logger.info("⏹️  사용자에 의해 중단됨")
    except Exception as e:
        logger.error(f"❌ 예상치 못한 오류: {e}")
    
    return success


if __name__ == "__main__":
    main()