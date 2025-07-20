# -*- coding: utf-8 -*-
"""
GITC 사업공고 스크래퍼 (경북IT융합산업기술원)
https://www.gitc.or.kr/main/page?x=53
"""

import os
import re
import time
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup
import logging
from enhanced_base_scraper import EnhancedBaseScraper
from datetime import datetime

logger = logging.getLogger(__name__)

class GitcEnhancedScraper(EnhancedBaseScraper):
    """GITC 사업공고 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.gitc.or.kr"
        self.list_url = "https://www.gitc.or.kr/main/page"
        self.list_params = {
            'x': '53'
        }
        self.site_name = "gitc"
        
        # 사이트별 특성 설정
        self.delay_between_requests = 1
        self.timeout = 30
        
        # 페이지네이션 설정
        self.page_size = 25  # 한 페이지당 기본 공고 수
        
        logger.info("GITC 스크래퍼 초기화 완료")
    
    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 생성"""
        params = self.list_params.copy()
        if page_num > 1:
            params['page'] = str(page_num)
        params['search'] = ''
        
        # URL 파라미터 구성
        param_str = '&'.join([f"{k}={v}" for k, v in params.items()])
        return f"{self.list_url}?{param_str}"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """사업공고 목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 공고 테이블 찾기 (class="humCon")
        table = soup.find('table', class_='humCon')
        if not table:
            logger.warning("사업공고 테이블을 찾을 수 없습니다")
            return announcements
        
        # 모든 행 찾기 (헤더 제외)
        rows = table.find_all('tr')
        logger.info(f"전체 행 수: {len(rows)}")
        
        # 헤더 행 제외하고 데이터 행만 처리
        data_rows = []
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 6:  # 데이터 행
                data_rows.append(row)
        
        logger.info(f"발견된 공고 행 수: {len(data_rows)}")
        
        for i, row in enumerate(data_rows):
            try:
                cells = row.find_all('td')
                if len(cells) < 6:  # 진행상태, 번호, 제목, 작성자, 등록일, 조회
                    continue
                
                # 진행상태 (첫 번째 셀)
                status_cell = cells[0]
                status_span = status_cell.find('span')
                status = status_span.get_text(strip=True) if status_span else status_cell.get_text(strip=True)
                
                # 번호 (두 번째 셀)
                number_cell = cells[1]
                number = self.process_notice_detection(number_cell, i)
                
                # 제목 (세 번째 셀)
                title_cell = cells[2]
                
                # 제목 링크 찾기
                title_link = title_cell.find('a')
                if not title_link:
                    continue
                
                # 제목 추출 (아이콘 제거)
                title = title_link.get_text(strip=True)
                if not title:
                    continue
                
                # URL 구성
                href = title_link.get('href', '')
                if not href:
                    continue
                
                detail_url = urljoin(self.base_url, href)
                
                # 작성자 (네 번째 셀)
                author = cells[3].get_text(strip=True)
                
                # 등록일 (다섯 번째 셀)
                date = cells[4].get_text(strip=True)
                
                # 조회수 (여섯 번째 셀)
                views = cells[5].get_text(strip=True)
                
                # 기본 공고 정보
                announcement = {
                    'number': number,
                    'title': title,
                    'url': detail_url,
                    'author': author,
                    'date': date,
                    'views': views,
                    'status': status
                }
                
                # 공지사항 구분 처리
                if '[공지]' in title:
                    announcement['category'] = '공지'
                    announcement['title'] = title.replace('[공지]', '').strip()
                
                announcements.append(announcement)
                logger.debug(f"사업공고 추가: {number} - {title[:50]}...")
                
            except Exception as e:
                logger.error(f"행 {i} 파싱 중 오류: {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개 사업공고 파싱 완료")
        return announcements
    
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """사업공고 상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 공고 정보 추출
        title = ""
        author = ""
        date = ""
        views = ""
        
        # 상세 정보 테이블 찾기
        detail_table = soup.find('table')
        if detail_table:
            rows = detail_table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 4:
                    # 첫 번째 행: 제목, 작성일
                    if '제목' in cells[0].get_text():
                        title = cells[1].get_text(strip=True)
                        date = cells[3].get_text(strip=True)
                    # 두 번째 행: 작성자, 조회
                    elif '작성자' in cells[0].get_text():
                        author = cells[1].get_text(strip=True)
                        views = cells[3].get_text(strip=True)
        
        # 공고 내용 찾기
        content = ""
        content_rows = detail_table.find_all('tr') if detail_table else []
        for row in content_rows:
            cells = row.find_all('td')
            if len(cells) == 1:  # 내용이 있는 행
                content_cell = cells[0]
                if content_cell.get_text(strip=True) and '첨부파일' not in content_cell.get_text():
                    content = self.h.handle(str(content_cell))
                    break
        
        # 내용이 비어있는 경우 대체 방법
        if not content:
            content = "내용이 없습니다."
        
        # 메타 정보 추출
        meta_info = {
            'title': title,
            'author': author,
            'date': date,
            'views': views,
            'content': content,
            'collected_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'source': 'GITC 경북IT융합산업기술원'
        }
        
        # 첨부파일 찾기
        attachments = self._parse_attachments(soup)
        
        return {
            'title': title,
            'content': self._format_content(meta_info, content),
            'attachments': attachments
        }
    
    def _parse_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """첨부파일 링크 파싱"""
        attachments = []
        
        # 첨부파일 섹션 찾기 (더 정확한 방법)
        attachment_rows = soup.find_all('tr')
        for row in attachment_rows:
            cells = row.find_all(['td', 'th'])  # td와 th 모두 검색
            if len(cells) >= 2 and '첨부파일' in cells[0].get_text():
                # 첨부파일이 있는 셀 (두 번째 셀 또는 colspan이 적용된 셀)
                attachment_cell = cells[1] if len(cells) > 1 else cells[0]
                
                # file-down 클래스를 가진 링크 찾기
                file_links = attachment_cell.find_all('a', class_='file-down', href=True)
                
                for link in file_links:
                    href = link.get('href', '')
                    download_attr = link.get('download', '')
                    text = link.get_text(strip=True)
                    
                    # 다운로드 링크인지 확인
                    if href and ('/uploads/' in href or '/upload' in href):
                        file_url = urljoin(self.base_url, href)
                        
                        # 파일명은 download 속성 우선, 없으면 텍스트 사용
                        filename = download_attr if download_attr else text
                        if not filename:
                            filename = href.split('/')[-1]
                        
                        # 파일 정보 추출
                        file_info = self._extract_file_info(filename, href)
                        
                        attachment = {
                            'filename': file_info['filename'],
                            'url': file_url,
                            'size': file_info.get('size', ''),
                            'type': file_info.get('type', '')
                        }
                        
                        attachments.append(attachment)
                        logger.debug(f"첨부파일 발견: {file_info['filename']}")
                
                break
        
        logger.info(f"총 {len(attachments)}개 첨부파일 발견")
        return attachments
    
    def _extract_file_info(self, text: str, href: str) -> Dict[str, Any]:
        """첨부파일 정보 추출"""
        # 기본 파일명은 텍스트 사용
        filename = text.strip()
        
        # URL에서 파일 확장자 추출
        parsed_url = urlparse(href)
        path = parsed_url.path
        
        # 파일 확장자 추출
        file_type = ""
        if '.' in path:
            file_type = path.split('.')[-1].lower()
        
        # 파일명에서 확장자가 없으면 URL에서 추출한 확장자 추가
        if not filename.endswith(f'.{file_type}') and file_type:
            if not '.' in filename:
                filename = f"{filename}.{file_type}"
        
        return {
            'filename': filename,
            'size': '',  # 크기 정보 없음
            'type': file_type
        }
    
    def _format_content(self, meta_info: Dict[str, Any], content: str) -> str:
        """내용 포맷팅"""
        lines = [
            f"# {meta_info['title']}",
            "",
            f"**작성자**: {meta_info['author']}",
            f"**작성일**: {meta_info['date']}",
            f"**조회수**: {meta_info['views']}",
            f"**수집 시점**: {meta_info['collected_at']}",
            f"**출처**: {meta_info['source']}",
            "",
            "---",
            "",
            content
        ]
        
        return "\n".join(lines)


def main():
    """메인 실행 함수"""
    import sys
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('gitc_scraper.log', encoding='utf-8')
        ]
    )
    
    # 스크래퍼 실행
    scraper = GitcEnhancedScraper()
    
    # 출력 디렉토리 생성
    output_dir = f"output/{scraper.site_name}"
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # 3페이지까지 수집
        logger.info("GITC 사업공고 스크래핑 시작")
        success = scraper.scrape_pages(max_pages=3, output_base=output_dir)
        
        if success:
            logger.info("스크래핑 완료")
            
            # 통계 출력
            stats = scraper.get_stats()
            logger.info(f"처리 통계: {stats}")
            
        else:
            logger.error("스크래핑 실패")
            
    except Exception as e:
        logger.error(f"스크래핑 중 오류: {e}")
        return False
    
    return True


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)