#!/usr/bin/env python3
"""
Enhanced CNFUND Scraper
충남 중소기업육성자금 사이트 스크래핑 도구

Site: https://www.cnfund.kr/info/list.do?menuSeq=notice
"""

import requests
from bs4 import BeautifulSoup
import os
import re
import time
import urllib.parse
from urllib.parse import urljoin, urlparse
import logging
from pathlib import Path
import json
from datetime import datetime

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cnfund_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CNFUNDScraper:
    def __init__(self, base_url="https://www.cnfund.kr/info/list.do?menuSeq=notice", 
                 output_dir="output/cnfund", max_pages=3):
        self.base_url = base_url
        self.output_dir = Path(output_dir)
        self.max_pages = max_pages
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # 출력 디렉토리 생성
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 스크래핑 통계
        self.stats = {
            'total_notices': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'total_attachments': 0,
            'pages_processed': 0
        }

    def get_page_content(self, url):
        """페이지 내용 가져오기"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            response.encoding = 'utf-8'
            return response.text
        except requests.RequestException as e:
            logger.error(f"페이지 요청 실패: {url} - {e}")
            return None

    def parse_notice_list(self, html_content):
        """공지사항 목록 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        notices = []
        
        # 테이블에서 공지사항 목록 찾기
        table = soup.find('table')
        if not table:
            logger.error("공지사항 테이블을 찾을 수 없습니다")
            return notices
        
        rows = table.find_all('tr')
        logger.info(f"테이블에서 {len(rows)}개의 행을 찾았습니다")
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 6:  # 번호, 제목, 첨부파일, 작성자, 조회수, 작성일
                try:
                    # 번호 (첫 번째 셀)
                    number_cell = cells[0].get_text(strip=True)
                    if not number_cell.isdigit():
                        continue
                    
                    # 제목 및 링크 (두 번째 셀)
                    title_cell = cells[1]
                    link_elem = title_cell.find('a')
                    if not link_elem:
                        continue
                    
                    title = title_cell.get_text(strip=True)
                    link = link_elem.get('href')
                    if link:
                        link = urljoin(self.base_url, link)
                    
                    # 첨부파일 여부 (세 번째 셀)
                    attachment_cell = cells[2]
                    has_attachment = bool(attachment_cell.find('img') or attachment_cell.get_text(strip=True))
                    
                    # 작성자 (네 번째 셀)
                    author = cells[3].get_text(strip=True)
                    
                    # 조회수 (다섯 번째 셀)
                    views = cells[4].get_text(strip=True)
                    
                    # 작성일 (여섯 번째 셀)
                    date = cells[5].get_text(strip=True)
                    
                    notice = {
                        'number': number_cell,
                        'title': title,
                        'link': link,
                        'has_attachment': has_attachment,
                        'author': author,
                        'views': views,
                        'date': date
                    }
                    notices.append(notice)
                    logger.info(f"공지사항 발견: {title}")
                    
                except Exception as e:
                    logger.error(f"공지사항 파싱 중 오류: {e}")
                    continue
        
        return notices

    def get_notice_content(self, notice_url):
        """공지사항 상세 내용 가져오기"""
        html_content = self.get_page_content(notice_url)
        if not html_content:
            return None, []
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목과 내용 추출
        title_elem = soup.find('h3') or soup.find('h2') or soup.find('h1')
        title = title_elem.get_text(strip=True) if title_elem else "제목 없음"
        
        # 공지사항 내용 영역 찾기
        content_area = None
        
        # 다양한 선택자로 내용 영역 찾기
        selectors = [
            'div.board_view_content',
            'div.content',
            'div.view_content',
            'td.td_content',
            'div[class*="content"]',
            'div[class*="view"]'
        ]
        
        for selector in selectors:
            content_area = soup.select_one(selector)
            if content_area:
                break
        
        # 내용 영역을 찾지 못한 경우 전체 페이지에서 본문 추출
        if not content_area:
            # 테이블 기반 레이아웃에서 내용 찾기
            tables = soup.find_all('table')
            for table in tables:
                cells = table.find_all('td')
                for cell in cells:
                    cell_text = cell.get_text(strip=True)
                    if len(cell_text) > 100 and ('안내' in cell_text or '공고' in cell_text):
                        content_area = cell
                        break
                if content_area:
                    break
        
        if not content_area:
            logger.warning(f"내용 영역을 찾을 수 없습니다: {notice_url}")
            content_area = soup.find('body')
        
        # 내용을 마크다운으로 변환
        content_md = self.html_to_markdown(content_area)
        
        # 첨부파일 링크 찾기
        attachment_links = []
        
        # 다양한 첨부파일 링크 패턴 검색
        download_patterns = [
            'a[href*="download"]',
            'a[href*="file"]',
            'a[href*="attach"]',
            'a[href*=".pdf"]',
            'a[href*=".hwp"]',
            'a[href*=".doc"]',
            'a[href*=".xls"]'
        ]
        
        for pattern in download_patterns:
            links = soup.select(pattern)
            for link in links:
                href = link.get('href')
                if href:
                    full_url = urljoin(notice_url, href)
                    text = link.get_text(strip=True)
                    attachment_links.append({
                        'url': full_url,
                        'text': text or '첨부파일'
                    })
        
        # 중복 제거
        unique_attachments = []
        seen_urls = set()
        for att in attachment_links:
            if att['url'] not in seen_urls:
                unique_attachments.append(att)
                seen_urls.add(att['url'])
        
        return content_md, unique_attachments

    def html_to_markdown(self, element):
        """HTML 요소를 마크다운으로 변환"""
        if not element:
            return ""
        
        # 불필요한 태그 제거
        for tag in element.find_all(['script', 'style', 'nav', 'header', 'footer']):
            tag.decompose()
        
        # 텍스트 추출 및 정리
        text = element.get_text(separator='\n', strip=True)
        
        # 마크다운 형식으로 정리
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('바로가기') and not line.startswith('메뉴'):
                cleaned_lines.append(line)
        
        # 연속된 빈 줄 제거
        result = []
        prev_empty = False
        for line in cleaned_lines:
            if line:
                result.append(line)
                prev_empty = False
            elif not prev_empty:
                result.append('')
                prev_empty = True
        
        return '\n'.join(result)

    def download_attachment(self, url, filename, folder_path):
        """첨부파일 다운로드"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Content-Type 확인
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' in content_type:
                logger.warning(f"HTML 응답 감지, 파일 다운로드 실패: {filename}")
                return False
            
            # 파일 크기 확인
            if len(response.content) < 1024:  # 1KB 미만
                # HTML 페이지인지 확인
                content_preview = response.content[:200].decode('utf-8', errors='ignore')
                if '<html' in content_preview.lower() or '<!doctype' in content_preview.lower():
                    logger.warning(f"HTML 페이지 감지, 파일 다운로드 실패: {filename}")
                    return False
            
            # 파일명 정리
            safe_filename = self.sanitize_filename(filename)
            file_path = folder_path / safe_filename
            
            # 파일 저장
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            file_size = len(response.content)
            logger.info(f"첨부파일 다운로드 완료: {safe_filename} ({file_size} bytes)")
            
            return True
            
        except Exception as e:
            logger.error(f"첨부파일 다운로드 실패: {url} - {e}")
            return False

    def sanitize_filename(self, filename):
        """파일명을 안전하게 정리"""
        # 위험한 문자 제거
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        # 파일명이 너무 긴 경우 자르기
        if len(filename) > 200:
            name, ext = os.path.splitext(filename)
            filename = name[:200-len(ext)] + ext
        
        return filename

    def save_notice_content(self, notice, content, attachments):
        """공지사항 내용 저장"""
        # 폴더명 생성 (번호_제목)
        folder_name = f"{notice['number']}_{notice['title']}"
        folder_name = self.sanitize_filename(folder_name)
        
        notice_folder = self.output_dir / folder_name
        notice_folder.mkdir(parents=True, exist_ok=True)
        
        # 내용을 마크다운 파일로 저장
        content_file = notice_folder / 'content.md'
        
        # 메타데이터 포함
        metadata = f"""# {notice['title']}

**번호:** {notice['number']}
**작성자:** {notice['author']}
**작성일:** {notice['date']}
**조회수:** {notice['views']}
**링크:** {notice['link']}

---

{content}
"""
        
        with open(content_file, 'w', encoding='utf-8') as f:
            f.write(metadata)
        
        # 첨부파일 다운로드
        attachments_folder = notice_folder / 'attachments'
        if attachments:
            attachments_folder.mkdir(parents=True, exist_ok=True)
            
            for i, attachment in enumerate(attachments):
                filename = attachment['text'] or f'attachment_{i+1}'
                
                # 파일 확장자 추가
                if not os.path.splitext(filename)[1]:
                    # URL에서 확장자 추출
                    parsed_url = urlparse(attachment['url'])
                    url_ext = os.path.splitext(parsed_url.path)[1]
                    if url_ext:
                        filename += url_ext
                    else:
                        filename += '.unknown'
                
                success = self.download_attachment(
                    attachment['url'], 
                    filename, 
                    attachments_folder
                )
                
                if success:
                    self.stats['successful_downloads'] += 1
                else:
                    self.stats['failed_downloads'] += 1
                
                self.stats['total_attachments'] += 1
                
                # 다운로드 간격
                time.sleep(1)
        
        logger.info(f"공지사항 저장 완료: {folder_name}")
        return True

    def get_next_page_url(self, current_page):
        """다음 페이지 URL 생성"""
        if current_page >= self.max_pages:
            return None
        
        next_page = current_page + 1
        if '?' in self.base_url:
            return f"{self.base_url}&page={next_page}"
        else:
            return f"{self.base_url}?page={next_page}"

    def scrape_page(self, page_url, page_num):
        """단일 페이지 스크래핑"""
        logger.info(f"페이지 {page_num} 스크래핑 시작: {page_url}")
        
        html_content = self.get_page_content(page_url)
        if not html_content:
            logger.error(f"페이지 {page_num} 내용을 가져올 수 없습니다")
            return False
        
        notices = self.parse_notice_list(html_content)
        if not notices:
            logger.warning(f"페이지 {page_num}에서 공지사항을 찾을 수 없습니다")
            return False
        
        logger.info(f"페이지 {page_num}에서 {len(notices)}개의 공지사항을 발견했습니다")
        
        # 각 공지사항 처리
        for notice in notices:
            try:
                logger.info(f"공지사항 처리 중: {notice['title']}")
                
                # 상세 내용 가져오기
                content, attachments = self.get_notice_content(notice['link'])
                if content is None:
                    logger.error(f"공지사항 내용을 가져올 수 없습니다: {notice['title']}")
                    continue
                
                # 내용 저장
                self.save_notice_content(notice, content, attachments)
                self.stats['total_notices'] += 1
                
                # 요청 간격
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"공지사항 처리 중 오류: {notice['title']} - {e}")
                continue
        
        self.stats['pages_processed'] += 1
        return True

    def run(self):
        """스크래핑 실행"""
        logger.info("CNFUND 스크래핑 시작")
        logger.info(f"대상 URL: {self.base_url}")
        logger.info(f"출력 디렉토리: {self.output_dir}")
        logger.info(f"최대 페이지 수: {self.max_pages}")
        
        start_time = datetime.now()
        
        # 첫 페이지부터 시작
        current_page = 1
        page_url = self.base_url
        
        while current_page <= self.max_pages:
            try:
                success = self.scrape_page(page_url, current_page)
                if not success:
                    logger.warning(f"페이지 {current_page} 스크래핑 실패")
                
                # 다음 페이지 URL 생성
                if current_page < self.max_pages:
                    page_url = self.get_next_page_url(current_page)
                    if not page_url:
                        logger.info("더 이상 페이지가 없습니다")
                        break
                
                current_page += 1
                
                # 페이지 간 간격
                time.sleep(3)
                
            except Exception as e:
                logger.error(f"페이지 {current_page} 처리 중 오류: {e}")
                break
        
        # 통계 출력
        end_time = datetime.now()
        duration = end_time - start_time
        
        logger.info("=" * 50)
        logger.info("스크래핑 완료!")
        logger.info(f"실행 시간: {duration}")
        logger.info(f"처리된 페이지: {self.stats['pages_processed']}")
        logger.info(f"총 공지사항: {self.stats['total_notices']}")
        logger.info(f"총 첨부파일: {self.stats['total_attachments']}")
        logger.info(f"다운로드 성공: {self.stats['successful_downloads']}")
        logger.info(f"다운로드 실패: {self.stats['failed_downloads']}")
        logger.info(f"출력 디렉토리: {self.output_dir}")
        
        # 통계를 JSON 파일로 저장
        stats_file = self.output_dir / 'scraping_stats.json'
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump({
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'duration_seconds': duration.total_seconds(),
                'stats': self.stats
            }, f, ensure_ascii=False, indent=2)

def main():
    """메인 함수"""
    try:
        scraper = CNFUNDScraper(
            base_url="https://www.cnfund.kr/info/list.do?menuSeq=notice",
            output_dir="output/cnfund",
            max_pages=3
        )
        scraper.run()
        
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단되었습니다")
    except Exception as e:
        logger.error(f"스크래핑 중 오류 발생: {e}")

if __name__ == "__main__":
    main()