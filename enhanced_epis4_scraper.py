# -*- coding: utf-8 -*-
"""
EPIS 교육/행사 게시판 스크래퍼
농림수산식품교육문화정보원 교육/행사 게시판 대상
"""

import re
import time
import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin, parse_qs, urlparse
from enhanced_base_scraper import EnhancedBaseScraper
import logging

logger = logging.getLogger(__name__)

class EnhancedEpis4Scraper(EnhancedBaseScraper):
    """EPIS 교육/행사 게시판 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.epis.or.kr"
        self.list_url = "https://www.epis.or.kr/home/kor/M943502192/board.do"
        self.site_code = "epis4"
        
        # 세션 관련 설정
        self.session_initialized = False
        
        # 중복 방지 기능 비활성화 (새로운 수집을 위해)
        self.enable_duplicate_check = False
        
        # 재시도 설정 강화
        self.max_retries = 5
        self.retry_delay = 3
        
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
            # 페이지 번호는 pageIndex 파라미터로 전달
            return f"{self.list_url}?pageIndex={page_num}"
    
    def initialize_session(self):
        """세션 초기화"""
        if self.session_initialized:
            return True
        
        try:
            # 먼저 메인 페이지 방문
            main_response = self.get_page(self.base_url)
            if not main_response:
                logger.error("메인 페이지 접근 실패")
                return False
            
            # 교육/행사 게시판 초기 방문
            response = self.get_page(self.list_url)
            if not response:
                logger.error("교육/행사 게시판 접근 실패")
                return False
            
            self.session_initialized = True
            logger.info("EPIS 세션 초기화 성공")
            return True
        
        except Exception as e:
            logger.error(f"세션 초기화 실패: {e}")
            return False
    
    def parse_list_page(self, html_content: str) -> list:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        logger.info(f"페이지 파싱 시작 - 현재 페이지: {self.current_page_num}")
        
        # 테이블 찾기
        table = soup.find('table')
        if not table:
            logger.warning("테이블을 찾을 수 없습니다")
            return announcements
        
        # 데이터 행들 찾기 (헤더 행 제외)
        rows = table.find_all('tr')[1:]  # 첫 번째 행은 헤더
        
        if not rows:
            logger.warning("테이블 행을 찾을 수 없습니다")
            return announcements
        
        for row_index, row in enumerate(rows):
            try:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 3:
                    continue
                
                # 번호 (No)
                number_cell = cells[0]
                number = number_cell.get_text(strip=True)
                
                # 구분 (카테고리)
                category_cell = cells[1]
                category = category_cell.get_text(strip=True)
                
                # 제목 (Title)
                title_cell = cells[2]
                title_link = title_cell.find('a')
                if not title_link:
                    continue
                
                title = title_link.get_text(strip=True)
                if not title:
                    continue
                
                # 상세 페이지 URL 추출
                href = title_link.get('href', '')
                if not href or href == 'javascript:void(0);':
                    # JavaScript 링크인 경우 onclick 이벤트에서 URL 추출
                    onclick = title_link.get('onclick', '')
                    if onclick:
                        # fn_edit 함수 호출에서 세 번째 파라미터(idx) 추출
                        match = re.search(r'fn_edit\(["\']([^"\']+)["\'][^,]*,[^,]*["\']([^"\']+)["\'][^,]*,[^,]*["\']([^"\']+)["\']', onclick)
                        if match:
                            action = match.group(1)  # 'detail'  
                            idx = match.group(2)     # 실제 idx 값
                            delete_at = match.group(3)  # 'N'
                            detail_url = f"{self.list_url}?deleteAt={delete_at}&act={action}&idx={idx}&pageIndex={self.current_page_num}"
                        else:
                            logger.warning(f"onclick에서 URL 추출 실패: {onclick}")
                            continue
                    else:
                        logger.warning(f"href와 onclick 모두 없음: {title}")
                        continue
                else:
                    detail_url = urljoin(self.base_url, href)
                
                # 등록일 (4번째 열)
                date = ""
                if len(cells) >= 4:
                    date_cell = cells[3]
                    date = date_cell.get_text(strip=True)
                
                # 조회수 (5번째 열)
                views = ""
                if len(cells) >= 5:
                    views_cell = cells[4]
                    views = views_cell.get_text(strip=True)
                
                announcement = {
                    'title': title,
                    'url': detail_url,
                    'date': date,
                    'views': views,
                    'category': category,
                    'number': number
                }
                
                announcements.append(announcement)
                logger.debug(f"공고 추가: {title} (번호: {number})")
                
            except Exception as e:
                logger.error(f"행 파싱 중 오류 (행 {row_index}): {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
        return announcements
    
    def parse_detail_page(self, html_content: str) -> dict:
        """상세 페이지 파싱 - 개선된 버전"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 찾기 - 더 정확한 방법
        title = "제목 없음"
        title_elem = soup.find('strong')
        if title_elem:
            title = title_elem.get_text(strip=True)
        
        # 메타 정보 찾기 - 더 정확한 방법
        meta_info = {}
        
        # 메타 정보가 포함된 div 찾기
        meta_divs = soup.find_all('div')
        for div in meta_divs:
            text = div.get_text(strip=True)
            if '작성자' in text and '등록일' in text:
                # 작성자, 등록일, 조회수 정보 추출
                parts = text.split('|')
                for part in parts:
                    part = part.strip()
                    if '작성자' in part and ':' in part:
                        meta_info['writer'] = part.split(':')[1].strip()
                    elif '등록일' in part and ':' in part:
                        meta_info['date'] = part.split(':')[1].strip()
                    elif '조회' in part and ':' in part:
                        meta_info['views'] = part.split(':')[1].strip()
                break
        
        # 본문 내용 찾기 - EPIS 특화 방법
        content = ""
        
        # EPIS 특화 본문 선택자
        content_div = soup.select_one('div.board_view_con div.editor_view')
        
        if content_div:
            # 본문 내용 정리
            content_parts = []
            for element in content_div.find_all(['p', 'div', 'span', 'br']):
                if element.name == 'br':
                    content_parts.append('\n')
                else:
                    element_text = element.get_text(strip=True)
                    if element_text and len(element_text) > 2:  # 의미있는 내용만
                        content_parts.append(element_text)
            
            if content_parts:
                content = '\n\n'.join(content_parts)
            else:
                content = content_div.get_text(separator='\n', strip=True)
        else:
            # 대체 방법 - 전체 페이지에서 본문 추출
            logger.warning("editor_view를 찾을 수 없음, 대체 방법 사용")
            content_div = soup.find('div', class_='board_view_con')
            if content_div:
                content = content_div.get_text(separator='\n', strip=True)
            else:
                content = "내용을 찾을 수 없습니다."
        
        # 첨부파일 찾기 - EPIS 특화 방법
        attachments = []
        
        logger.info(f"첨부파일 검색 시작...")
        
        # EPIS 특화 첨부파일 섹션 찾기
        file_section = soup.select_one('div.board_view_file div.file_box')
        
        if file_section:
            logger.info(f"첨부파일 섹션 발견")
            
            # 각 파일 링크 찾기
            file_links = file_section.select('p.file_each a')
            
            for link in file_links:
                onclick = link.get('onclick', '')
                link_text = link.get_text(strip=True)
                
                if onclick and link_text:
                    # onclick에서 고유키 추출: kssFileDownloadForKeyAct('고유키')
                    match = re.search(r'kssFileDownloadForKeyAct\(["\']([^"\']+)["\']', onclick)
                    if match:
                        unique_key = match.group(1)
                        logger.info(f"첨부파일 고유키 발견: {unique_key} ({link_text})")
                        
                        attachments.append({
                            'filename': link_text,
                            'url': '/fileDownload.do',
                            'unique_key': unique_key,
                            'method': 'POST'
                        })
                        logger.info(f"첨부파일 추가: {link_text}")
        else:
            logger.info("첨부파일 섹션이 없습니다.")
        
        logger.info(f"총 {len(attachments)}개 첨부파일 발견")
        
        return {
            'title': title,
            'content': content,
            'attachments': attachments,
            'meta_info': meta_info
        }
    
    def download_epis_file(self, unique_key: str, filename: str, save_path: str) -> bool:
        """EPIS 특화 파일 다운로드"""
        try:
            # POST 요청으로 파일 다운로드
            download_url = urljoin(self.base_url, '/fileDownload.do')
            
            data = {
                'uniqueKey': unique_key
            }
            
            headers = self.headers.copy()
            headers['Referer'] = self.list_url
            
            logger.info(f"파일 다운로드 시작: {filename} (고유키: {unique_key})")
            
            response = self.session.post(
                download_url,
                data=data,
                headers=headers,
                stream=True,
                timeout=self.timeout * 2
            )
            
            response.raise_for_status()
            
            # 파일 저장
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            total_size = 0
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        total_size += len(chunk)
            
            file_size = os.path.getsize(save_path)
            logger.info(f"다운로드 완료: {filename} ({file_size:,} bytes)")
            
            # 파일 크기 검증 (1KB 미만이면 오류 페이지일 가능성)
            if file_size < 1024:
                logger.warning(f"파일 크기가 작음: {filename} ({file_size} bytes)")
                # 파일 내용 확인
                with open(save_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(500)
                    if '<html' in content.lower() or 'error' in content.lower():
                        logger.error(f"HTML 오류 페이지 다운로드됨: {filename}")
                        os.remove(save_path)
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"파일 다운로드 실패: {filename} - {e}")
            return False
    
    def _download_attachments(self, attachments: list, folder_path: str):
        """EPIS 특화 첨부파일 다운로드"""
        if not attachments:
            logger.info("첨부파일이 없습니다")
            return
        
        logger.info(f"{len(attachments)}개 첨부파일 다운로드 시작")
        attachments_folder = os.path.join(folder_path, 'attachments')
        os.makedirs(attachments_folder, exist_ok=True)
        
        for i, attachment in enumerate(attachments):
            try:
                filename = attachment.get('filename', f"attachment_{i+1}")
                unique_key = attachment.get('unique_key')
                
                if not unique_key:
                    logger.warning(f"고유키가 없는 첨부파일: {filename}")
                    continue
                
                # 파일명 정리
                clean_filename = self.sanitize_filename(filename)
                if not clean_filename or clean_filename.isspace():
                    clean_filename = f"attachment_{i+1}"
                
                file_path = os.path.join(attachments_folder, clean_filename)
                
                # EPIS 특화 다운로드
                success = self.download_epis_file(unique_key, filename, file_path)
                if not success:
                    logger.warning(f"첨부파일 다운로드 실패: {filename}")
                
            except Exception as e:
                logger.error(f"첨부파일 처리 중 오류: {e}")
    
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
            logging.FileHandler('epis4_scraper.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    # 스크래퍼 실행
    scraper = EnhancedEpis4Scraper()
    
    try:
        # 출력 디렉토리 설정
        output_dir = f'output/{scraper.site_code}'
        
        # 중복 방지 기능 완전 비활성화
        scraper.enable_duplicate_check = False
        
        # 3페이지 수집
        logger.info("="*60)
        logger.info(f"🚀 EPIS 교육/행사 게시판 스크래핑 시작 (새로운 수집)")
        logger.info(f"📂 출력 디렉토리: {output_dir}")
        logger.info(f"🔄 중복 방지 기능: {'활성화' if scraper.enable_duplicate_check else '비활성화'}")
        logger.info("="*60)
        
        success = scraper.scrape_pages(max_pages=3, output_base=output_dir)
        
        if success:
            logger.info("✅ 스크래핑 완료!")
            
            # 수집 결과 요약
            content_files = []
            import os
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