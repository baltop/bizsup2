# -*- coding: utf-8 -*-
"""
중소기업수출지원센터 스크래퍼 - 향상된 아키텍처 사용
"""

from enhanced_base_scraper import StandardTableScraper
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import logging
from typing import List, Dict, Any
import requests
import os
import time
import re
import json
import hashlib
from datetime import datetime

logger = logging.getLogger(__name__)

class EnhancedSmesgoScraper(StandardTableScraper):
    """중소기업수출지원센터 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        # 하드코딩된 설정들
        self.base_url = "https://www.smes.go.kr"
        self.list_url = "https://www.smes.go.kr/exportcenter/information/notice/list.do"
        
        # SMESGO 특화 설정
        self.timeout = 120
        self.delay_between_requests = 1
        self.delay_between_pages = 2
        
        # CSRF 토큰 관리
        self.csrf_token = None
        
        # 처리된 제목 관리
        self.processed_titles = set()
        self.current_session_titles = set()
        
    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 반환"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}?pageNumber={page_num}"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # CSRF 토큰 추출
        if not self.csrf_token:
            csrf_meta = soup.find('meta', attrs={'name': '_csrf'})
            if csrf_meta:
                self.csrf_token = csrf_meta.get('content')
        
        # 테이블에서 공고 정보 추출
        table = soup.find('table', class_='table-type-list')
        if not table:
            logger.warning("목록 테이블을 찾을 수 없습니다")
            return announcements
        
        tbody = table.find('tbody')
        if not tbody:
            logger.warning("테이블 본문을 찾을 수 없습니다")
            return announcements
        
        rows = tbody.find_all('tr')
        logger.info(f"{len(rows)}개 행 발견")
        
        for row in rows:
            try:
                cols = row.find_all('td')
                if len(cols) < 5:
                    continue
                
                # 번호, 제목, 첨부파일, 작성일, 조회수
                number = cols[0].get_text(strip=True)
                title_cell = cols[1]
                title_link = title_cell.find('a')
                
                if not title_link:
                    continue
                
                title = title_link.get_text(strip=True)
                detail_url = urljoin(self.base_url, title_link.get('href'))
                
                has_attachment = '첨부파일 있음' in cols[2].get_text(strip=True)
                date_str = cols[3].get_text(strip=True)
                views = cols[4].get_text(strip=True)
                
                announcement = {
                    'number': number,
                    'title': title,
                    'url': detail_url,
                    'has_attachment': has_attachment,
                    'date': date_str,
                    'views': views
                }
                
                announcements.append(announcement)
                
            except Exception as e:
                logger.error(f"행 파싱 중 오류: {e}")
                continue
        
        return announcements
    
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목
        title_elem = soup.find('div', class_='post-title')
        title = title_elem.get_text(strip=True) if title_elem else ""
        
        # 본문 내용
        content_elem = soup.find('div', class_='post-content')
        content = ""
        if content_elem:
            # 이미지 태그 처리
            for img in content_elem.find_all('img'):
                src = img.get('src')
                if src:
                    # 상대 경로를 절대 경로로 변경
                    abs_src = urljoin(self.base_url, src)
                    img['src'] = abs_src
            
            content = str(content_elem)
        
        # 첨부파일 정보
        attachments = []
        file_list = soup.find('ul', class_='post-file-list')
        if file_list:
            for file_item in file_list.find_all('li'):
                file_link = file_item.find('a')
                if file_link:
                    file_url = urljoin(self.base_url, file_link.get('href'))
                    file_name = file_link.get_text(strip=True)
                    attachments.append({
                        'name': file_name,
                        'url': file_url
                    })
        
        return {
            'title': title,
            'content': content,
            'attachments': attachments
        }
    
    def load_processed_titles(self, output_base: str = 'output'):
        """처리된 제목 목록 로드"""
        site_name = self.__class__.__name__.replace('Scraper', '').lower()
        if site_name.startswith('enhanced'):
            site_name = site_name[8:]  # 'enhanced' 제거
        
        self.processed_titles_file = os.path.join(output_base, f'processed_titles_enhanced{site_name}.json')
        
        if os.path.exists(self.processed_titles_file):
            try:
                with open(self.processed_titles_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                if isinstance(data, dict) and 'title_hashes' in data:
                    # 해시 기반 형태
                    self.processed_titles = set(data['title_hashes'])
                elif isinstance(data, list):
                    # 배열 형태 - 각 항목에서 제목 해시 추출
                    for item in data:
                        if isinstance(item, dict) and 'title' in item:
                            title_hash = self.get_title_hash(item['title'])
                            self.processed_titles.add(title_hash)
                        elif isinstance(item, str):
                            # 이미 해시 형태인 경우
                            self.processed_titles.add(item)
                            
                logger.info(f"이전 처리된 제목 {len(self.processed_titles)}개 로드")
                    
            except Exception as e:
                logger.error(f"처리된 제목 로드 실패: {e}")
                self.processed_titles = set()
        else:
            self.processed_titles = set()
    
    def save_processed_titles(self):
        """현재 세션에서 처리된 제목들을 저장"""
        if not self.processed_titles_file:
            return
        
        try:
            # 다른 사이트와 동일한 형태로 저장 (배열 형태)
            data = []
            
            # 현재 세션에서 처리된 제목들로 배열 생성
            for title_hash in self.current_session_titles:
                data.append({
                    "id": title_hash,
                    "scraped_at": datetime.now().isoformat()
                })
            
            os.makedirs(os.path.dirname(self.processed_titles_file), exist_ok=True)
            
            with open(self.processed_titles_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"처리된 제목 {len(data)}개 저장")
            
        except Exception as e:
            logger.error(f"처리된 제목 저장 실패: {e}")
    
    def get_title_hash(self, title: str) -> str:
        """제목의 해시값 생성"""
        # 제목 정규화
        normalized = title.strip()
        normalized = re.sub(r'\s+', ' ', normalized)  # 연속 공백 제거
        normalized = re.sub(r'[^\w\s가-힣()-]', '', normalized)  # 특수문자 제거
        normalized = normalized.lower()
        
        # MD5 해시 생성
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()
    
    def is_title_processed(self, title: str) -> bool:
        """제목이 이미 처리되었는지 확인"""
        title_hash = self.get_title_hash(title)
        return title_hash in self.processed_titles
    
    def add_processed_title(self, title: str):
        """현재 세션에서 처리된 제목 추가"""
        title_hash = self.get_title_hash(title)
        self.current_session_titles.add(title_hash)
    
    def clean_filename(self, filename: str) -> str:
        """파일명에서 특수문자 제거"""
        # 윈도우에서 사용할 수 없는 문자 제거
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # 연속된 점 제거
        filename = re.sub(r'\.{2,}', '.', filename)
        # 앞뒤 공백 및 점 제거
        filename = filename.strip('. ')
        return filename
    
    def download_attachment(self, attachment: Dict[str, Any], save_dir: str) -> bool:
        """첨부파일 다운로드"""
        try:
            response = self.session.get(attachment['url'], timeout=60)
            response.raise_for_status()
            
            # HTML 응답 체크
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' in content_type:
                logger.warning(f"HTML 응답 감지: {attachment['name']}")
                return False
            
            # 파일 크기 체크
            if len(response.content) < 1024:  # 1KB 미만
                # HTML 페이지일 가능성 체크
                if b'<html' in response.content.lower() or b'<!doctype' in response.content.lower():
                    logger.warning(f"작은 파일 크기 및 HTML 감지: {attachment['name']}")
                    return False
            
            # 파일명 정리
            clean_name = self.clean_filename(attachment['name'])
            file_path = os.path.join(save_dir, clean_name)
            
            # 파일 저장
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            # 파일 크기 로그
            file_size = len(response.content)
            logger.info(f"첨부파일 다운로드 완료: {clean_name} ({file_size} bytes)")
            
            return True
            
        except Exception as e:
            logger.error(f"첨부파일 다운로드 오류 ({attachment['name']}): {e}")
            return False
    
    def save_notice_content(self, notice_info: Dict[str, Any], detail_info: Dict[str, Any], save_dir: str) -> bool:
        """공고 내용을 markdown 파일로 저장"""
        try:
            # content.md 파일 생성
            content_file = os.path.join(save_dir, 'content.md')
            
            with open(content_file, 'w', encoding='utf-8') as f:
                f.write(f"# {detail_info['title']}\n\n")
                f.write(f"- **작성일**: {notice_info['date']}\n")
                f.write(f"- **조회수**: {notice_info['views']}\n")
                f.write(f"- **원본 URL**: {notice_info['url']}\n\n")
                f.write("---\n\n")
                
                # HTML 내용을 간단한 마크다운으로 변환
                if detail_info['content']:
                    # BeautifulSoup로 HTML 파싱
                    soup = BeautifulSoup(detail_info['content'], 'html.parser')
                    
                    # 텍스트 추출 및 기본 마크다운 변환
                    text = soup.get_text(separator='\n', strip=True)
                    f.write(text)
                    f.write("\n\n")
                    
                    # 이미지 링크 추가
                    images = soup.find_all('img')
                    if images:
                        f.write("## 이미지\n\n")
                        for img in images:
                            src = img.get('src')
                            if src:
                                f.write(f"![이미지]({src})\n\n")
            
            return True
            
        except Exception as e:
            logger.error(f"내용 저장 오류: {e}")
            return False
    
    def process_notice(self, notice_info: Dict[str, Any], output_dir: str) -> bool:
        """개별 공고 처리"""
        try:
            # 중복 체크
            if self.is_title_processed(notice_info['title']):
                logger.info(f"이미 처리된 공고 건너뛰기: {notice_info['title']}")
                return False
            
            # 상세 정보 추출
            detail_response = self.get_page(notice_info['url'])
            if not detail_response:
                return False
            
            detail_info = self.parse_detail_page(detail_response.text)
            if not detail_info:
                return False
            
            # 저장 디렉토리 생성
            clean_title = self.clean_filename(f"{notice_info['number']}_{detail_info['title']}")
            notice_dir = os.path.join(output_dir, clean_title)
            os.makedirs(notice_dir, exist_ok=True)
            
            # 첨부파일 디렉토리 생성
            if detail_info['attachments']:
                attachments_dir = os.path.join(notice_dir, 'attachments')
                os.makedirs(attachments_dir, exist_ok=True)
            
            # 내용 저장
            self.save_notice_content(notice_info, detail_info, notice_dir)
            
            # 첨부파일 다운로드
            downloaded_count = 0
            for attachment in detail_info['attachments']:
                if self.download_attachment(attachment, attachments_dir):
                    downloaded_count += 1
                time.sleep(self.delay_between_requests)
            
            # 처리된 제목 추가
            self.add_processed_title(notice_info['title'])
            
            logger.info(f"공고 처리 완료: {notice_info['number']} - {detail_info['title']} (첨부파일 {downloaded_count}개)")
            
            return True
            
        except Exception as e:
            logger.error(f"공고 처리 오류 ({notice_info['number']}): {e}")
            return False
    
    def scrape(self, max_pages: int = 3, output_dir: str = None) -> int:
        """메인 스크래핑 실행"""
        if output_dir is None:
            site_name = self.__class__.__name__.replace('Scraper', '').lower()
            if site_name.startswith('enhanced'):
                site_name = site_name[8:]  # 'enhanced' 제거
            output_dir = os.path.join('output', site_name)
        
        os.makedirs(output_dir, exist_ok=True)
        
        # 처리된 제목 로드
        self.load_processed_titles()
        
        logger.info(f"중소기업수출지원센터 스크래핑 시작 (최대 {max_pages}페이지)")
        
        total_processed = 0
        
        for page in range(1, max_pages + 1):
            logger.info(f"페이지 {page} 처리 중...")
            
            # 목록 페이지 가져오기
            list_url = self.get_list_url(page)
            response = self.get_page(list_url)
            if not response:
                logger.error(f"페이지 {page} 가져오기 실패")
                continue
            
            # 공고 목록 파싱
            announcements = self.parse_list_page(response.text)
            if not announcements:
                logger.warning(f"페이지 {page}에서 공고를 찾을 수 없습니다.")
                continue
            
            # 각 공고 처리
            page_processed = 0
            for announcement in announcements:
                if self.process_notice(announcement, output_dir):
                    page_processed += 1
                    total_processed += 1
                time.sleep(self.delay_between_requests)
            
            logger.info(f"페이지 {page} 완료 ({page_processed}/{len(announcements)}개 처리)")
            
            # 페이지 간 대기
            if page < max_pages:
                time.sleep(self.delay_between_pages)
        
        # 처리된 제목 저장
        self.save_processed_titles()
        
        logger.info(f"스크래핑 완료: 총 {total_processed}개 공고 처리")
        
        return total_processed


def main():
    """메인 함수"""
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('/tmp/smesgo_scraper.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    scraper = EnhancedSmesgoScraper()
    processed_count = scraper.scrape(max_pages=3)
    
    print(f"\n=== 스크래핑 완료 ===")
    print(f"처리된 공고 수: {processed_count}")
    print(f"출력 디렉토리: output/smesgo")
    
    return processed_count


if __name__ == "__main__":
    main()