# -*- coding: utf-8 -*-
"""
광주시립중앙도서관 스크래퍼 - Enhanced 버전
사이트: https://lib.gjcity.go.kr/lay1/bbs/S1T82C3521/H/1/list.do
"""

import requests
from bs4 import BeautifulSoup
import os
import re
import logging
import time
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Any, Optional
from enhanced_base_scraper import StandardTableScraper

logger = logging.getLogger(__name__)

class EnhancedGjcitylibScraper(StandardTableScraper):
    """광주시립중앙도서관 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        
        # 기본 설정
        self.base_url = "https://lib.gjcity.go.kr"
        self.list_url = "https://lib.gjcity.go.kr/lay1/bbs/S1T82C3521/H/1/list.do"
        
        # 사이트별 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 2  # 더 긴 지연시간
        self.delay_between_pages = 5     # 페이지 간 더 긴 대기
        
        # 테스트를 위해 중복 체크 비활성화
        self.enable_duplicate_check = False
        
        # 웹 방화벽 우회용 자연스러운 헤더 설정
        self.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        })
        self.session.headers.update(self.headers)
        
        logger.info("광주시립중앙도서관 스크래퍼 초기화 완료")
    
    def initialize_session(self):
        """세션 초기화 - 웹 방화벽 우회용"""
        try:
            logger.info("세션 초기화 중...")
            
            # 먼저 메인 페이지에 방문해서 세션 쿠키 획득
            main_response = self.session.get(
                self.base_url,
                headers=self.headers,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            
            if main_response.status_code == 200:
                logger.info("메인 페이지 방문 성공")
                time.sleep(2)  # 자연스러운 대기
                
                # 목록 페이지 방문
                list_response = self.session.get(
                    self.list_url,
                    headers=self.headers,
                    timeout=self.timeout,
                    verify=self.verify_ssl
                )
                
                if list_response.status_code == 200:
                    logger.info("목록 페이지 접근 성공 - 세션 초기화 완료")
                    return True
                else:
                    logger.warning(f"목록 페이지 접근 실패: {list_response.status_code}")
            else:
                logger.warning(f"메인 페이지 접근 실패: {main_response.status_code}")
                
        except Exception as e:
            logger.error(f"세션 초기화 실패: {e}")
        
        return False
    
    def get_page_with_retry(self, url: str, max_retries: int = 3) -> Optional[requests.Response]:
        """재시도 로직이 있는 페이지 가져오기"""
        for attempt in range(max_retries):
            try:
                # Referer 헤더 설정
                headers = self.headers.copy()
                if url != self.list_url:
                    headers['Referer'] = self.list_url
                
                response = self.session.get(
                    url,
                    headers=headers,
                    timeout=self.timeout,
                    verify=self.verify_ssl
                )
                
                # 웹 방화벽 차단 확인
                if "Web firewall" in response.text or "blocked" in response.text.lower():
                    logger.warning(f"시도 {attempt + 1}: 웹 방화벽 차단 감지")
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 3
                        logger.info(f"{wait_time}초 대기 후 재시도...")
                        time.sleep(wait_time)
                        continue
                
                if response.status_code == 200:
                    return response
                else:
                    logger.warning(f"시도 {attempt + 1}: HTTP {response.status_code}")
                    
            except Exception as e:
                logger.error(f"시도 {attempt + 1} 실패: {e}")
            
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 지수적 백오프
        
        return None
    
    def get_list_url(self, page_num: int) -> str:
        """페이지 번호별 목록 URL 생성"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}?rows=10&cpage={page_num}&q="
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        try:
            # 테이블 찾기
            table = soup.find('table')
            if not table:
                logger.warning("목록 테이블을 찾을 수 없습니다")
                return announcements
            
            # tbody 찾기
            tbody = table.find('tbody')
            if not tbody:
                tbody = table
            
            # 각 행 처리
            rows = tbody.find_all('tr')
            logger.info(f"테이블에서 {len(rows)}개 행 발견")
            
            for row in rows:
                # th와 td를 모두 포함하여 셀 추출 (번호 컬럼이 th이므로)
                cells = row.find_all(['th', 'td'])
                if len(cells) < 7:  # 7개 컬럼 (번호, 구분, 제목, 첨부, 작성자, 작성일, 조회수)
                    continue
                
                try:
                    # 제목 및 링크 추출 (3번째 컬럼)
                    title_cell = cells[2]
                    link_elem = title_cell.find('a')
                    
                    if not link_elem:
                        continue
                    
                    title = link_elem.get_text(strip=True)
                    if not title:
                        continue
                    
                    # 상세 페이지 URL 구성
                    href = link_elem.get('href', '')
                    detail_url = urljoin(self.base_url, href)
                    
                    # 기본 공고 정보
                    announcement = {
                        'title': title,
                        'url': detail_url
                    }
                    
                    # 추가 메타데이터 추출
                    try:
                        # 번호 (1번째 컬럼)
                        number_text = cells[0].get_text(strip=True)
                        if number_text and number_text.isdigit():
                            announcement['number'] = number_text
                        
                        # 구분 (2번째 컬럼)
                        category = cells[1].get_text(strip=True)
                        if category:
                            announcement['category'] = category
                        
                        # 첨부파일 여부 (4번째 컬럼)
                        attachment_cell = cells[3]
                        has_attachment = attachment_cell.find('img') is not None
                        announcement['has_attachment'] = has_attachment
                        
                        # 작성자 (5번째 컬럼)
                        writer = cells[4].get_text(strip=True)
                        if writer:
                            announcement['writer'] = writer
                        
                        # 작성일 (6번째 컬럼)
                        date = cells[5].get_text(strip=True)
                        if date:
                            announcement['date'] = date
                        
                        # 조회수 (7번째 컬럼)
                        views = cells[6].get_text(strip=True)
                        if views and views.isdigit():
                            announcement['views'] = int(views)
                        
                    except Exception as e:
                        logger.warning(f"메타데이터 추출 중 오류: {e}")
                    
                    announcements.append(announcement)
                    logger.debug(f"공고 추가: {title}")
                    
                except Exception as e:
                    logger.error(f"행 파싱 중 오류: {e}")
                    continue
            
            logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
            return announcements
            
        except Exception as e:
            logger.error(f"목록 페이지 파싱 실패: {e}")
            return announcements
    
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = {
            'content': '',
            'attachments': []
        }
        
        # 웹 방화벽 차단 확인
        if "Web firewall security policies" in html_content or "blocked" in html_content.lower():
            logger.warning("웹 방화벽에 의해 페이지가 차단되었습니다")
            result['content'] = "웹 방화벽으로 인해 내용을 가져올 수 없습니다."
            return result
        
        try:
            # 제목 추출
            title_elem = soup.find('h4')
            title = title_elem.get_text(strip=True) if title_elem else ""
            
            # 메타 정보 추출
            meta_info = []
            if title:
                meta_info.append(f"# {title}")
                meta_info.append("")
            
            # dl 태그에서 메타 정보 추출 (작성자, 조회수, 작성일 등)
            dl_elem = soup.find('dl')
            if dl_elem:
                dts = dl_elem.find_all('dt')
                dds = dl_elem.find_all('dd')
                
                for dt, dd in zip(dts, dds):
                    dt_text = dt.get_text(strip=True)
                    dd_text = dd.get_text(strip=True)
                    
                    if dt_text and dd_text and dt_text != "첨부파일":
                        meta_info.append(f"**{dt_text}**: {dd_text}")
            
            if meta_info:
                meta_info.append("")
                meta_info.append("---")
                meta_info.append("")
            
            # 본문 내용 추출
            content_parts = []
            
            # 본문 영역 찾기 - 다양한 방법 시도
            content_elem = None
            
            # 방법 1: 일반적인 본문 div 찾기
            content_elem = soup.find('div', class_=re.compile(r'content|board|view'))
            
            # 방법 2: 테이블 이후의 div 찾기
            if not content_elem:
                tables = soup.find_all('table')
                for table in tables:
                    next_div = table.find_next_sibling('div')
                    if next_div and next_div.get_text(strip=True):
                        content_elem = next_div
                        break
            
            # 방법 3: 첨부파일 dl 이후의 내용 찾기
            if not content_elem:
                if dl_elem:
                    next_elem = dl_elem.find_next_sibling()
                    while next_elem:
                        if next_elem.name in ['div', 'p'] and next_elem.get_text(strip=True):
                            content_elem = next_elem
                            break
                        next_elem = next_elem.find_next_sibling()
            
            # 방법 4: 페이지 전체에서 가장 긴 텍스트 블록 찾기
            if not content_elem:
                text_blocks = soup.find_all(['div', 'p', 'td'])
                max_length = 0
                for block in text_blocks:
                    text = block.get_text(strip=True)
                    if len(text) > max_length and len(text) > 50:  # 최소 50자 이상
                        max_length = len(text)
                        content_elem = block
            
            # 본문 내용 변환
            if content_elem:
                # HTML을 마크다운으로 변환
                content_html = str(content_elem)
                content_markdown = self.h.handle(content_html)
                content_parts.append(content_markdown.strip())
            else:
                # 본문을 찾지 못한 경우 전체 페이지에서 추출
                logger.warning("본문 영역을 찾을 수 없어 전체 텍스트에서 추출합니다")
                all_text = soup.get_text()
                # 불필요한 부분 제거
                cleaned_text = re.sub(r'\s+', ' ', all_text).strip()
                if len(cleaned_text) > 200:
                    content_parts.append(cleaned_text[:1000] + "...")
                else:
                    content_parts.append(cleaned_text)
            
            # 첨부파일 추출
            attachments = self._extract_attachments(soup)
            
            # 결과 조합
            final_content = "\n".join(meta_info + content_parts)
            
            result = {
                'content': final_content,
                'attachments': attachments
            }
            
            logger.info(f"상세 페이지 파싱 완료 - 내용: {len(final_content)}자, 첨부파일: {len(attachments)}개")
            return result
            
        except Exception as e:
            logger.error(f"상세 페이지 파싱 실패: {e}")
            return result
    
    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """첨부파일 추출"""
        attachments = []
        
        try:
            # 첨부파일 링크 찾기 - /download.do?uuid= 패턴
            download_links = soup.find_all('a', href=re.compile(r'/download\.do\?uuid='))
            
            for link in download_links:
                try:
                    href = link.get('href', '')
                    if not href:
                        continue
                    
                    # 파일 URL 구성
                    file_url = urljoin(self.base_url, href)
                    
                    # 파일명 추출
                    filename = link.get_text(strip=True)
                    if not filename:
                        # URL에서 파일명 추출 시도
                        if '.' in href:
                            filename = href.split('/')[-1]
                        else:
                            filename = f"attachment_{len(attachments) + 1}"
                    
                    attachment = {
                        'filename': filename,
                        'url': file_url
                    }
                    
                    attachments.append(attachment)
                    logger.debug(f"첨부파일 발견: {filename} - {file_url}")
                    
                except Exception as e:
                    logger.error(f"첨부파일 추출 중 오류: {e}")
                    continue
            
            logger.info(f"총 {len(attachments)}개 첨부파일 추출")
            return attachments
            
        except Exception as e:
            logger.error(f"첨부파일 추출 실패: {e}")
            return attachments
    
    def download_file(self, url: str, save_path: str, attachment_info: Dict[str, Any] = None) -> bool:
        """파일 다운로드 - 광주시립중앙도서관 특화"""
        try:
            logger.info(f"파일 다운로드 시작: {url}")
            
            # 다운로드 헤더 설정
            download_headers = self.headers.copy()
            download_headers['Referer'] = self.base_url
            
            response = self.session.get(
                url,
                headers=download_headers,
                stream=True,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            
            # 실제 파일명 추출
            actual_filename = self._extract_filename(response, save_path)
            if actual_filename != save_path:
                save_path = actual_filename
            
            # 파일 저장
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(save_path)
            logger.info(f"다운로드 완료: {save_path} ({file_size:,} bytes)")
            
            # 파일 크기 검증
            if file_size == 0:
                logger.warning(f"다운로드된 파일 크기가 0입니다: {save_path}")
                return False
            elif file_size < 100:
                logger.warning(f"다운로드된 파일 크기가 너무 작습니다: {save_path} ({file_size} bytes)")
                # 파일 내용 확인
                with open(save_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(200)
                    if 'error' in content.lower() or 'not found' in content.lower():
                        logger.error(f"다운로드 실패 - 에러 응답: {content}")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"파일 다운로드 실패 {url}: {e}")
            return False
    
    def process_announcement(self, announcement: Dict[str, Any], index: int, output_base: str = 'output'):
        """개별 공고 처리 - 웹 방화벽 우회 강화 버전"""
        logger.info(f"공고 처리 중 {index}: {announcement['title']}")
        
        # 폴더 생성
        folder_title = self.sanitize_filename(announcement['title'])[:100]
        folder_name = f"{index:03d}_{folder_title}"
        
        if len(folder_name) > 200:
            folder_title = folder_title[:195]
            folder_name = f"{index:03d}_{folder_title}"
        
        folder_path = os.path.join(output_base, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        
        # 상세 페이지 가져오기 (개선된 재시도 로직 사용)
        response = self.get_page_with_retry(announcement['url'])
        if not response:
            logger.error(f"상세 페이지 가져오기 실패 (모든 재시도 소진): {announcement['title']}")
            # 실패해도 기본 메타 정보는 저장
            meta_info = self._create_meta_info(announcement)
            content_path = os.path.join(folder_path, 'content.md')
            with open(content_path, 'w', encoding='utf-8') as f:
                f.write(meta_info + "\n웹 방화벽으로 인해 상세 내용을 가져올 수 없습니다.")
            return
        
        # 상세 내용 파싱
        try:
            detail = self.parse_detail_page(response.text)
            logger.info(f"상세 페이지 파싱 완료 - 내용길이: {len(detail['content'])}, 첨부파일: {len(detail['attachments'])}")
        except Exception as e:
            logger.error(f"상세 페이지 파싱 실패: {e}")
            detail = {
                'content': f"파싱 오류: {str(e)}",
                'attachments': []
            }
        
        # 메타 정보 생성
        meta_info = self._create_meta_info(announcement)
        
        # 본문 저장
        content_path = os.path.join(folder_path, 'content.md')
        with open(content_path, 'w', encoding='utf-8') as f:
            f.write(meta_info + detail['content'])
        
        logger.info(f"내용 저장 완료: {content_path}")
        
        # 첨부파일 다운로드
        self._download_attachments(detail['attachments'], folder_path)
        
        # 처리된 제목으로 추가
        self.add_processed_title(announcement['title'])
        
        # 요청 간 대기 (웹 방화벽 우회용 긴 대기)
        if self.delay_between_requests > 0:
            time.sleep(self.delay_between_requests)
    
    def _create_meta_info(self, announcement: Dict[str, Any]) -> str:
        """메타 정보 생성"""
        meta_lines = [f"# {announcement['title']}", ""]
        
        # 메타 정보 추가
        if announcement.get('writer'):
            meta_lines.append(f"**작성자**: {announcement['writer']}")
        if announcement.get('date'):
            meta_lines.append(f"**작성일**: {announcement['date']}")
        if announcement.get('views'):
            meta_lines.append(f"**조회수**: {announcement['views']}")
        if announcement.get('category'):
            meta_lines.append(f"**구분**: {announcement['category']}")
        
        meta_lines.extend([
            f"**원본 URL**: {announcement['url']}",
            "",
            "---",
            ""
        ])
        
        return "\n".join(meta_lines)
    
    def scrape_pages(self, max_pages: int = 4, output_base: str = 'output'):
        """웹 방화벽 우회를 위한 세션 초기화 포함"""
        logger.info(f"스크래핑 시작: 최대 {max_pages}페이지")
        
        # 세션 초기화
        if not self.initialize_session():
            logger.error("세션 초기화 실패 - 스크래핑을 계속 시도합니다")
        
        # 부모 클래스의 스크래핑 로직 실행
        return super().scrape_pages(max_pages, output_base)


def test_gjcitylib_scraper(pages: int = 3):
    """광주시립중앙도서관 스크래퍼 테스트"""
    print(f"광주시립중앙도서관 스크래퍼 테스트 시작 ({pages}페이지)")
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('gjcitylib_scraper.log', encoding='utf-8')
        ]
    )
    
    # 출력 디렉토리 설정
    output_dir = "output/gjcitylib"
    os.makedirs(output_dir, exist_ok=True)
    
    # 스크래퍼 실행
    scraper = EnhancedGjcitylibScraper()
    
    try:
        success = scraper.scrape_pages(max_pages=pages, output_base=output_dir)
        
        if success:
            print(f"\n=== 스크래핑 완료 ===")
            print(f"결과 저장 위치: {output_dir}")
            
            # 결과 통계
            verify_results(output_dir)
        else:
            print("스크래핑 실패")
            
    except Exception as e:
        print(f"스크래핑 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()


def verify_results(output_dir: str):
    """결과 검증"""
    print(f"\n=== 결과 검증 ===")
    
    try:
        # 폴더 수 확인
        if not os.path.exists(output_dir):
            print(f"출력 디렉토리가 존재하지 않습니다: {output_dir}")
            return
        
        folders = [d for d in os.listdir(output_dir) if os.path.isdir(os.path.join(output_dir, d))]
        print(f"생성된 공고 폴더 수: {len(folders)}")
        
        # 각 폴더별 통계
        total_files = 0
        total_size = 0
        attachment_counts = []
        
        for folder in folders:
            folder_path = os.path.join(output_dir, folder)
            
            # content.md 확인
            content_file = os.path.join(folder_path, 'content.md')
            if os.path.exists(content_file):
                size = os.path.getsize(content_file)
                print(f"  {folder}: content.md ({size:,} bytes)")
            else:
                print(f"  {folder}: content.md 없음")
            
            # 첨부파일 확인
            attachments_dir = os.path.join(folder_path, 'attachments')
            if os.path.exists(attachments_dir):
                files = os.listdir(attachments_dir)
                attachment_counts.append(len(files))
                for file in files:
                    file_path = os.path.join(attachments_dir, file)
                    file_size = os.path.getsize(file_path)
                    total_files += 1
                    total_size += file_size
                    print(f"    첨부파일: {file} ({file_size:,} bytes)")
            else:
                attachment_counts.append(0)
        
        # 통계 요약
        print(f"\n=== 통계 요약 ===")
        print(f"총 공고 수: {len(folders)}")
        print(f"총 첨부파일 수: {total_files}")
        print(f"총 첨부파일 크기: {total_size:,} bytes ({total_size/1024/1024:.2f} MB)")
        if attachment_counts:
            print(f"평균 첨부파일 수: {sum(attachment_counts)/len(attachment_counts):.1f}")
            print(f"최대 첨부파일 수: {max(attachment_counts)}")
        
    except Exception as e:
        print(f"결과 검증 중 오류: {e}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='광주시립중앙도서관 스크래퍼')
    parser.add_argument('--pages', type=int, default=3, help='스크래핑할 페이지 수 (기본값: 3)')
    parser.add_argument('--output', type=str, default='output/gjcitylib', help='출력 디렉토리')
    
    args = parser.parse_args()
    
    test_gjcitylib_scraper(args.pages)