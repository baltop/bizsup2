#!/usr/bin/env python3
"""
Enhanced KMA (대한의사협회) 스크래퍼

KMA 교육 및 연수 공지사항 게시판에서 공고를 수집하는 스크래퍼입니다.
AJAX 기반 동적 사이트이므로 Playwright를 사용하며, API 직접 호출도 지원합니다.

URL: https://www.kma.or.kr/kr/usrs/eduRegMgnt/eduRegMgntForm.do?mkey=24&cateNm=abtNews
"""

import os
import re
import time
import json
import logging
from typing import List, Dict, Any
from urllib.parse import urljoin, unquote
from playwright.sync_api import sync_playwright, Page, Browser
from bs4 import BeautifulSoup
import requests
from enhanced_base_scraper import EnhancedBaseScraper

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedKmaScraper(EnhancedBaseScraper):
    """KMA 전용 Enhanced 스크래퍼 - AJAX API 기반"""
    
    def __init__(self):
        super().__init__()
        
        # KMA 사이트 설정
        self.base_url = "https://www.kma.or.kr"
        self.list_url = "https://www.kma.or.kr/kr/usrs/eduRegMgnt/eduRegMgntForm.do?mkey=24&cateNm=abtNews"
        
        # 사이트별 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 2
        
        # Playwright 관련 설정
        self.playwright = None
        self.browser = None
        self.page = None
        
        # API 엔드포인트
        self.api_url = "https://www.kma.or.kr/kr/usrs/eduRegMgnt/selectInsightSubList.do"
        self.download_url = "https://www.kma.or.kr/kr/common/file/FileDown.do"
        
        # 고정 파라미터
        self.base_params = {
            'sidx': 'BRD_SEQ',
            'sord': 'DESC',
            'rows': '8',
            'p_menu_id': '24',
            'mkey': '24',
            'cateNm': 'abtNews',
            'p_assct_cdclsf_id': '3'
        }
        
        # 캐시된 데이터 저장
        self.cached_announcements = {}
        
    def start_browser(self):
        """Playwright 브라우저 시작"""
        if self.playwright is None:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            self.page = self.browser.new_page()
            
            # User-Agent 설정
            self.page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            
            logger.info("Playwright 브라우저 시작됨")
            
    def stop_browser(self):
        """Playwright 브라우저 종료"""
        if self.page:
            self.page.close()
            self.page = None
        if self.browser:
            self.browser.close()
            self.browser = None
        if self.playwright:
            self.playwright.stop()
            self.playwright = None
        logger.info("Playwright 브라우저 종료됨")
            
    def get_list_url(self, page_num: int) -> str:
        """페이지별 URL 생성 (API 방식이므로 기본 URL 반환)"""
        return self.list_url
        
    def fetch_announcements_api(self, page_num: int) -> Dict[str, Any]:
        """AJAX API를 통한 공고 목록 가져오기"""
        try:
            # API 요청 파라미터 준비
            params = self.base_params.copy()
            params.update({
                'page': str(page_num),
                'totalCnt': '',
                'moreCnt': ''
            })
            
            # 헤더 설정
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Referer': self.list_url
            }
            
            # Playwright에서 쿠키 가져오기 (가능한 경우)
            cookies = {}
            if self.page:
                for cookie in self.page.context.cookies():
                    cookies[cookie['name']] = cookie['value']
            
            # POST 요청
            response = requests.post(
                self.api_url,
                data=params,
                headers=headers,
                cookies=cookies,
                verify=self.verify_ssl,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            
            # JSON 응답 파싱
            api_data = response.json()
            logger.info(f"API 응답: 페이지 {page_num}, 총 {api_data.get('records', 0)}개 게시글, {len(api_data.get('rows', []))}개 반환")
            
            return api_data
            
        except Exception as e:
            logger.error(f"API 요청 실패 (페이지 {page_num}): {e}")
            return {}
    
    def _get_page_announcements(self, page_num: int) -> List[Dict[str, Any]]:
        """페이지별 공고 목록 가져오기 (API 기반)"""
        logger.info(f"페이지 {page_num} 공고 목록 수집 중...")
        
        # API를 통해 데이터 가져오기
        api_data = self.fetch_announcements_api(page_num)
        if not api_data:
            return []
        
        # 데이터 변환
        announcements = []
        rows = api_data.get('rows', [])
        
        for row in rows:
            try:
                brd_seq = row.get('BRD_SEQ')
                title = row.get('TTL', '제목 없음')
                date = row.get('VIEW_REG_DATE', '')
                view_cnt = row.get('VIEW_CNT', 0)
                fileadd = row.get('FILEADD', 'N')
                
                # 상세페이지 URL 생성
                detail_url = (
                    f"{self.base_url}/kr/usrs/eduRegMgnt/eduRegMgntForm.do"
                    f"?p_brd_seq={brd_seq}&p_menu_id=24&mkey=24&cateNm=abtNewsDtl"
                    f"&p_hmpgcd=30&p_assct_cdclsf_id=3"
                )
                
                announcement = {
                    'number': str(brd_seq),
                    'title': title,
                    'date': date,
                    'views': str(view_cnt),
                    'url': detail_url,
                    'brd_seq': brd_seq,
                    'has_files': fileadd == 'Y'
                }
                
                # 캐시에 저장 (상세 정보에서 사용)
                self.cached_announcements[brd_seq] = row
                
                announcements.append(announcement)
                logger.info(f"공고 추가: [{brd_seq}] {title}")
                
            except Exception as e:
                logger.error(f"데이터 변환 실패: {e}")
                continue
                
        logger.info(f"총 {len(announcements)}개 공고 수집완료")
        return announcements
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱 (API 기반이므로 빈 구현)"""
        # 이 메서드는 _get_page_announcements에서 API를 직접 호출하므로 사용되지 않음
        return []
        
    def get_detail_content(self, announcement: Dict[str, Any]) -> Dict[str, Any]:
        """상세 페이지 내용 가져오기 (Playwright 기반)"""
        try:
            # 브라우저가 시작되지 않았으면 시작
            if self.page is None:
                self.start_browser()
            
            detail_url = announcement['url']
            logger.info(f"상세 페이지 접속: {detail_url}")
            
            # 상세 페이지 접속
            self.page.goto(detail_url)
            self.page.wait_for_load_state('networkidle')
            time.sleep(self.delay_between_requests)
            
            # 페이지 내용 파싱
            html_content = self.page.content()
            detail_info = self.parse_detail_page_with_announcement(html_content, announcement)
            
            return detail_info
            
        except Exception as e:
            logger.error(f"상세 내용 가져오기 실패 - {announcement['title']}: {e}")
            return {
                'content': f"# {announcement['title']}\n\n상세 내용을 가져올 수 없습니다.",
                'attachments': []
            }
            
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱 (기본 구현)"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출
        title_elem = soup.find('h2', class_='title') or soup.find('h1') or soup.find('h2')
        title = title_elem.get_text(strip=True) if title_elem else "제목 없음"
        
        # 본문 내용 추출
        content_elem = soup.find('div', class_='detail-cont') or soup.find('div', class_='view-content')
        if not content_elem:
            content_elem = soup.find('div', id='content') or soup.find('article')
        
        if content_elem:
            content_text = self.simple_html_to_text(content_elem)
        else:
            content_text = "본문 내용을 찾을 수 없습니다."
        
        # 첨부파일 추출
        attachments = self._extract_attachments(soup)
        
        return {
            'content': f"# {title}\n\n---\n\n{content_text}",
            'attachments': attachments
        }
    
    def parse_detail_page_with_announcement(self, html_content: str, announcement: Dict[str, Any]) -> Dict[str, Any]:
        """상세 페이지 파싱 (announcement 정보 포함)"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출
        title_elem = soup.find('h2', class_='title') or soup.find('h1') or soup.find('h2')
        title = title_elem.get_text(strip=True) if title_elem else announcement.get('title', '제목 없음')
        
        # 본문 내용 추출
        content_elem = soup.find('div', class_='detail-cont') or soup.find('div', class_='view-content')
        if not content_elem:
            # 다른 선택자 시도
            content_elem = soup.find('div', id='content') or soup.find('article')
        
        if content_elem:
            # HTML을 텍스트로 변환
            content_text = self.simple_html_to_text(content_elem)
        else:
            content_text = "본문 내용을 찾을 수 없습니다."
            
        # 메타 정보 추출
        meta_info = self.extract_meta_info(soup, announcement)
        
        # 첨부파일 추출
        attachments = self._extract_attachments(soup)
        
        # 마크다운 형식으로 조합
        markdown_content = f"# {title}\n\n"
        
        if meta_info:
            for key, value in meta_info.items():
                markdown_content += f"**{key}**: {value}\n"
            markdown_content += f"**원본 URL**: {announcement.get('url', '')}\n\n"
        
        markdown_content += "---\n\n"
        markdown_content += content_text
        
        return {
            'content': markdown_content,
            'attachments': attachments
        }
        
    def extract_meta_info(self, soup: BeautifulSoup, announcement: Dict[str, Any]) -> Dict[str, str]:
        """메타 정보 추출"""
        meta_info = {}
        
        # 기본 정보 추가
        meta_info['번호'] = announcement.get('number', '')
        meta_info['등록일'] = announcement.get('date', '')
        meta_info['조회수'] = announcement.get('views', '')
        
        # 추가 메타 정보 추출 시도
        info_area = soup.find('div', class_='info-area') or soup.find('ul', class_='board-info')
        if info_area:
            items = info_area.find_all(['li', 'span', 'div'])
            for item in items:
                item_text = item.get_text(strip=True)
                if '작성자' in item_text:
                    meta_info['작성자'] = item_text.replace('작성자', '').strip()
                elif '등록일' in item_text and not meta_info.get('등록일'):
                    meta_info['등록일'] = item_text.replace('등록일', '').strip()
        
        return meta_info
        
    def simple_html_to_text(self, element) -> str:
        """HTML 요소를 간단한 텍스트로 변환"""
        # 단락 분리
        text = element.get_text(separator='\n\n', strip=True)
        
        # 과도한 공백 제거
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        
        return text
        
    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """첨부파일 정보 추출"""
        attachments = []
        
        # 첨부파일 영역 찾기
        file_section = soup.find('div', class_='form-set filedown')
        if not file_section:
            file_section = soup.find('div', class_='file-list') or soup.find('ul', class_='attach-file')
        
        if file_section:
            # 파일 링크 찾기
            file_links = file_section.find_all('a', href=True)
            
            for link in file_links:
                href = link.get('href', '')
                filename = link.get_text(strip=True)
                
                # JavaScript 다운로드 함수 확인
                onclick = link.get('onclick', '')
                if 'fn_fileDown' in onclick:
                    # 파라미터 추출: fn_fileDown('filegrp_id', 'file_id')
                    match = re.search(r"fn_fileDown\('([^']+)',\s*'([^']+)'\)", onclick)
                    if match:
                        filegrp_id = match.group(1)
                        file_id = match.group(2)
                        
                        # 파일명에서 다운로드 아이콘 텍스트 제거
                        clean_filename = re.sub(r'다운로드$', '', filename).strip()
                        
                        attachment = {
                            'filename': clean_filename,
                            'url': self.download_url,
                            'type': 'form_post',
                            'params': {
                                'p_filegrp_id': filegrp_id,
                                'p_file_id': file_id
                            }
                        }
                        attachments.append(attachment)
                        logger.debug(f"첨부파일 발견: {clean_filename}")
                elif href and not href.startswith('javascript:'):
                    # 직접 링크
                    full_url = urljoin(self.base_url, href)
                    attachments.append({
                        'filename': filename,
                        'url': full_url,
                        'type': 'direct'
                    })
        
        logger.info(f"첨부파일 {len(attachments)}개 발견")
        return attachments
        
    def download_file(self, attachment: Dict[str, Any], save_dir: str, 
                     announcement: Dict[str, Any] = None, 
                     attachment_info: Dict[str, Any] = None) -> bool:
        """파일 다운로드 (form POST 지원)"""
        try:
            url = attachment['url']
            filename = attachment.get('filename', 'unknown_file')
            attachment_type = attachment.get('type', 'direct')
            
            # 파일명 정리
            clean_filename = self.sanitize_filename(filename)
            file_path = os.path.join(save_dir, clean_filename)
            
            # Playwright에서 쿠키 가져오기
            cookies = {}
            if self.page:
                for cookie in self.page.context.cookies():
                    cookies[cookie['name']] = cookie['value']
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': self.page.url if self.page else self.list_url
            }
            
            if attachment_type == 'form_post':
                # POST 방식으로 파일 다운로드
                params = attachment.get('params', {})
                response = requests.post(url, data=params, cookies=cookies, 
                                       headers=headers, stream=True, timeout=30, 
                                       verify=self.verify_ssl)
            else:
                # GET 방식 (직접 링크)
                response = requests.get(url, cookies=cookies, headers=headers, 
                                      stream=True, timeout=30, verify=self.verify_ssl)
            
            response.raise_for_status()
            
            # Content-Disposition에서 파일명 추출 시도
            content_disposition = response.headers.get('Content-Disposition', '')
            if content_disposition:
                extracted_filename = self.extract_filename_from_disposition(content_disposition)
                if extracted_filename:
                    clean_filename = self.sanitize_filename(extracted_filename)
                    file_path = os.path.join(save_dir, clean_filename)
            
            # 파일 저장
            os.makedirs(save_dir, exist_ok=True)
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(file_path)
            logger.info(f"파일 다운로드 완료: {clean_filename} ({file_size} bytes)")
            
            return True
            
        except Exception as e:
            logger.error(f"파일 다운로드 실패 - {filename}: {e}")
            return False
            
    def extract_filename_from_disposition(self, content_disposition: str) -> str:
        """Content-Disposition 헤더에서 파일명 추출"""
        try:
            # RFC 5987 형식 우선 처리
            rfc5987_match = re.search(r"filename\*=([^']*)'([^']*)'(.+)", content_disposition)
            if rfc5987_match:
                encoding, lang, filename = rfc5987_match.groups()
                try:
                    filename = unquote(filename, encoding=encoding or 'utf-8')
                    return filename
                except:
                    pass
            
            # 일반 filename 파라미터 처리
            filename_match = re.search(r'filename[^;=\n]*=([\'"]*)(.*?)\1', content_disposition)
            if filename_match:
                filename = filename_match.group(2)
                
                # UTF-8 디코딩 시도
                try:
                    if filename.encode('latin-1'):
                        decoded = filename.encode('latin-1').decode('utf-8')
                        return decoded.replace('+', ' ')
                except:
                    pass
                        
                return filename.replace('+', ' ')
                
        except Exception as e:
            logger.debug(f"파일명 추출 실패: {e}")
            
        return None
    
    def process_announcement(self, announcement: Dict[str, Any], index: int, output_base: str = 'output') -> bool:
        """개별 공고 처리 - KMA 전용"""
        try:
            # 파일명 안전화
            safe_title = self.sanitize_filename(announcement['title'])
            number = announcement.get('number', '0')
            folder_name = f"{number}_{safe_title}"
            
            announcement_dir = os.path.join(output_base, folder_name)
            os.makedirs(announcement_dir, exist_ok=True)
            
            # 상세 내용 가져오기
            detail_info = self.get_detail_content(announcement)
            
            # 본문 저장
            content_file = os.path.join(announcement_dir, 'content.md')
            with open(content_file, 'w', encoding='utf-8') as f:
                f.write(detail_info['content'])
            
            # 첨부파일 처리
            attachments = detail_info.get('attachments', [])
            if attachments:
                attachments_dir = os.path.join(announcement_dir, 'attachments')
                os.makedirs(attachments_dir, exist_ok=True)
                
                for attachment in attachments:
                    success = self.download_file(attachment, attachments_dir, announcement)
                    if success:
                        # 파일 카운트는 base scraper에서 처리됨
                        pass
            
            logger.info(f"공고 처리 완료: {announcement['title']}")
            return True
            
        except Exception as e:
            logger.error(f"공고 처리 실패: {announcement['title']} - {e}")
            return False
    
    def scrape_pages(self, max_pages: int = 3, output_base: str = "output") -> Dict[str, Any]:
        """페이지 스크래핑 실행"""
        try:
            self.start_browser()
            
            # 첫 페이지 접속하여 세션 설정
            self.page.goto(self.list_url)
            self.page.wait_for_load_state('networkidle')
            time.sleep(2)
            
            result = super().scrape_pages(max_pages, output_base)
            return result
        finally:
            self.stop_browser()
            
    def __del__(self):
        """소멸자 - 브라우저 정리"""
        self.stop_browser()


def main():
    """메인 실행 함수"""
    scraper = EnhancedKmaScraper()
    
    try:
        # 3페이지까지 수집
        output_dir = "output/kma"
        os.makedirs(output_dir, exist_ok=True)
        
        result = scraper.scrape_pages(max_pages=3, output_base=output_dir)
        
        print(f"\n✅ KMA 스크래핑 완료!")
        print(f"수집된 공고: {result['total_announcements']}개")
        print(f"다운로드된 파일: {result['total_files']}개")
        print(f"성공률: {result['success_rate']:.1f}%")
        
    except Exception as e:
        print(f"❌ 스크래핑 실패: {e}")
    finally:
        scraper.stop_browser()


if __name__ == "__main__":
    main()