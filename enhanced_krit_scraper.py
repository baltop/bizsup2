# -*- coding: utf-8 -*-
"""
국방기술진흥연구소(KRIT) 공지사항 스크래퍼 - Enhanced 버전
URL: https://krit.re.kr/krit/bbs/notice_list.do?gotoMenuNo=05010000
"""

import os
import re
import time
import logging
import requests
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, unquote, parse_qs, urlparse
from bs4 import BeautifulSoup

try:
    from enhanced_base_scraper import StandardTableScraper
except ImportError:
    from enhanced_base_scraper import EnhancedBaseScraper as StandardTableScraper

logger = logging.getLogger(__name__)

class EnhancedKritScraper(StandardTableScraper):
    """국방기술진흥연구소(KRIT) 전용 스크래퍼 - Enhanced 버전"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://krit.re.kr"
        self.list_url = "https://krit.re.kr/krit/bbs/notice_list.do?gotoMenuNo=05010000"
        
        # KRIT 사이트 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 2.0  # JavaScript 기반 사이트이므로 조금 더 여유
        
        # 공지사항 포함 수집 설정
        self.include_notices = True
        
        # 세션 설정 (보안 관련)
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        logger.info("Enhanced KRIT 스크래퍼 초기화 완료")

    def get_list_url(self, page_num: int) -> str:
        """페이지별 목록 URL 생성 - POST 방식"""
        return self.list_url

    def _get_page_announcements(self, page_num: int) -> List[Dict[str, Any]]:
        """페이지별 공고 목록 가져오기 - POST 방식으로 오버라이드"""
        try:
            # 먼저 목록 페이지를 GET으로 방문 (세션 설정을 위해)
            if page_num == 1:
                logger.info("첫 페이지 - 목록 페이지 GET 요청으로 세션 초기화")
                get_response = self.session.get(
                    self.list_url,
                    timeout=self.timeout,
                    verify=self.verify_ssl
                )
                if get_response.status_code != 200:
                    logger.warning(f"목록 페이지 GET 요청 실패: {get_response.status_code}")
            
            # KRIT는 POST 방식으로 페이지네이션 처리
            post_data = {
                'page': str(page_num),
                'bbsId': 'notice',
                'gotoMenuNo': '05010000',
                'searchCnd': '',
                'searchWrd': '',
                'startd': '',
                'endd': ''
            }
            
            logger.info(f"페이지 {page_num} POST 요청 중...")
            
            response = self.session.post(
                self.list_url,
                data=post_data,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            
            if response.status_code != 200:
                logger.error(f"HTTP 요청 실패: {response.status_code}")
                return []
            
            response.encoding = 'utf-8'
            return self.parse_list_page(response.text)
            
        except Exception as e:
            logger.error(f"페이지 {page_num} 요청 중 오류 발생: {e}")
            return []

    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱 - 리스트 기반"""
        announcements = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # KRIT 사이트는 직접 li 태그들을 찾아야 함
            # onclick="fnView('notice',...)" 패턴을 가진 링크가 있는 li 요소들 찾기
            items = soup.find_all('li')
            
            # fnView 함수가 있는 li 요소만 필터링
            valid_items = []
            for item in items:
                link = item.find('a')
                if link and link.get('onclick') and 'fnView' in link.get('onclick'):
                    valid_items.append(item)
            
            if not valid_items:
                logger.warning("공지사항 항목을 찾을 수 없습니다")
                return announcements
            
            logger.info(f"총 {len(valid_items)}개의 공고 항목을 발견했습니다")
            
            for i, item in enumerate(valid_items):
                try:
                    # 링크 요소 찾기
                    link_elem = item.find('a')
                    if not link_elem:
                        continue
                    
                    # JavaScript 함수에서 파라미터 추출
                    onclick = link_elem.get('onclick', '')
                    if 'fnView' not in onclick:
                        continue
                    
                    # fnView('notice','','5947','1','','') 형태에서 파라미터 추출
                    match = re.search(r"fnView\('([^']*)',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)'\)", onclick)
                    if not match:
                        continue
                    
                    bbs_id, _, ntt_id, page, _, _ = match.groups()
                    
                    # 제목 추출
                    title_text = link_elem.get_text(strip=True)
                    
                    # 공지사항 여부 및 번호 처리
                    is_notice = False
                    number = ""
                    
                    # 공지사항 체크
                    if item.get('class') and 'notice' in item.get('class'):
                        is_notice = True
                        # <span>공지</span> 부분과 실제 제목 분리
                        span_elem = link_elem.find('span')
                        if span_elem and '공지' in span_elem.get_text():
                            number = "공지"
                            # span 태그 제거하고 실제 제목만 추출
                            span_elem.decompose()
                            title = link_elem.get_text(strip=True)
                        else:
                            number = "공지"
                            title = title_text
                    else:
                        # 일반 공고 - 숫자 추출
                        span_elem = link_elem.find('span')
                        if span_elem:
                            number = span_elem.get_text(strip=True)
                            # span 태그 제거하고 실제 제목만 추출
                            span_elem.decompose()
                            title = link_elem.get_text(strip=True)
                        else:
                            number = f"item_{i+1}"
                            title = title_text
                    
                    # 상세 페이지 URL 구성
                    detail_url = f"{self.base_url}/krit/bbs/notice_view.do?bbsId={bbs_id}&nttId={ntt_id}&gotoMenuNo=05010000"
                    
                    # 작성자, 날짜, 조회수 추출
                    writer_ul = item.find('ul', class_='writer')
                    date = ""
                    views = ""
                    
                    if writer_ul:
                        writer_items = writer_ul.find_all('li')
                        if len(writer_items) >= 2:
                            date = writer_items[0].get_text(strip=True).replace('date', '').strip()
                            views = writer_items[1].get_text(strip=True).replace('hits', '').strip()
                    
                    # 첨부파일 여부 확인
                    has_attachment = bool(item.find('span', class_='file'))
                    
                    announcement = {
                        'number': number,
                        'title': title,
                        'url': detail_url,
                        'author': "관리자",  # KRIT는 작성자 정보가 없음
                        'date': date,
                        'views': views,
                        'has_attachment': has_attachment,
                        'is_notice': is_notice,
                        'ntt_id': ntt_id,
                        'bbs_id': bbs_id
                    }
                    
                    announcements.append(announcement)
                    logger.info(f"공고 추가: [{number}] {title}")
                    
                except Exception as e:
                    logger.warning(f"리스트 항목 {i+1} 파싱 중 오류: {e}")
                    continue
            
            logger.info(f"총 {len(announcements)}개의 공고를 파싱했습니다")
            
        except Exception as e:
            logger.error(f"목록 페이지 파싱 중 오류 발생: {e}")
        
        return announcements
    
    def get_page(self, url: str, **kwargs) -> Optional[requests.Response]:
        """상세 페이지 가져오기 - Referer 헤더 추가 (KRIT 보안 제한 우회)"""
        try:
            # Referer 헤더 추가 (보안 제한 우회)
            headers = kwargs.get('headers', {})
            if not headers:
                headers = self.session.headers.copy()
            headers['Referer'] = self.list_url
            kwargs['headers'] = headers
            
            # 부모 클래스의 get_page 메서드 호출
            return super().get_page(url, **kwargs)
                
        except Exception as e:
            logger.error(f"상세 페이지 요청 중 오류: {e} - {url}")
            return None

    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 보안 제한 체크
            if "정상적인 경로를 통해 다시 접근해 주세요" in html_content:
                logger.warning("보안 제한으로 인한 접근 거부")
                return {
                    'title': "접근 제한",
                    'author': "관리자",
                    'date': "",
                    'views': "",
                    'content': "이 공고는 보안상의 이유로 상세 내용을 수집할 수 없습니다.",
                    'attachments': []
                }
            
            # 제목 추출 (다양한 방법 시도)
            title = "제목 없음"
            title_selectors = [
                'h1.title', 'h2.title', 'h3.title', 'h4.title', 'h5.title',
                '.viewTitle', '.bbsTitle', '.subject', '.title'
            ]
            
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    break
            
            # 메타 정보 추출
            author = "관리자"
            date = ""
            views = ""
            
            # 다양한 메타 정보 위치 시도
            meta_selectors = [
                '.viewInfo', '.bbsInfo', '.postInfo', '.articleInfo'
            ]
            
            for selector in meta_selectors:
                meta_elem = soup.select_one(selector)
                if meta_elem:
                    meta_text = meta_elem.get_text()
                    # 날짜 패턴 추출
                    date_match = re.search(r'(\d{4}[-./]\d{1,2}[-./]\d{1,2})', meta_text)
                    if date_match:
                        date = date_match.group(1)
                    # 조회수 패턴 추출
                    views_match = re.search(r'조회\s*:?\s*(\d+)', meta_text)
                    if views_match:
                        views = views_match.group(1)
                    break
            
            # 본문 내용 추출
            content = ""
            content_selectors = [
                '.viewContent', '.bbsContent', '.postContent', 
                '.articleContent', '.content', '#content'
            ]
            
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    content = self.h.handle(str(content_elem))
                    break
            
            if not content:
                # 일반적인 div나 p 태그에서 내용 추출
                content_div = soup.find('div', class_=re.compile(r'content|view|article|post'))
                if content_div:
                    content = self.h.handle(str(content_div))
            
            # 첨부파일 추출
            attachments = self._extract_attachments(soup)
            
            return {
                'title': title,
                'author': author,
                'date': date,
                'views': views,
                'content': content,
                'attachments': attachments
            }
            
        except Exception as e:
            logger.error(f"상세 페이지 파싱 중 오류: {e}")
            return {
                'title': "파싱 오류",
                'author': "",
                'date': "",
                'views': "",
                'content': f"상세 페이지 파싱 중 오류가 발생했습니다: {e}",
                'attachments': []
            }

    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """첨부파일 정보 추출"""
        attachments = []
        
        try:
            # KRIT 사이트의 첨부파일 패턴 찾기
            attachment_selectors = [
                'a[href*="fileDownload"]',
                'a[href*="download"]',
                'a[onclick*="download"]',
                '.fileList a',
                '.attachFile a',
                '.attach a'
            ]
            
            for selector in attachment_selectors:
                file_links = soup.select(selector)
                
                for link in file_links:
                    href = link.get('href', '')
                    onclick = link.get('onclick', '')
                    
                    # 다운로드 URL 추출
                    download_url = None
                    filename = link.get_text(strip=True)
                    
                    if href and 'download' in href:
                        download_url = urljoin(self.base_url, href)
                    elif onclick and 'download' in onclick:
                        # JavaScript 함수에서 URL 추출 시도
                        url_match = re.search(r"['\"]([^'\"]*download[^'\"]*)['\"]", onclick)
                        if url_match:
                            download_url = urljoin(self.base_url, url_match.group(1))
                    
                    if download_url and filename:
                        attachment = {
                            'filename': filename,
                            'url': download_url,
                            'size': "unknown"
                        }
                        
                        attachments.append(attachment)
                        logger.info(f"첨부파일 발견: {filename}")
                
                if attachments:  # 첨부파일을 찾았으면 다른 선택자는 시도하지 않음
                    break
            
        except Exception as e:
            logger.error(f"첨부파일 추출 중 오류: {e}")
        
        return attachments

    def download_file(self, file_url: str, save_path: str, attachment_info: Dict[str, Any] = None) -> bool:
        """파일 다운로드 - KRIT 특화"""
        try:
            logger.info(f"파일 다운로드 시작: {file_url}")
            
            # Referer 헤더 추가 (보안상 중요)
            headers = self.session.headers.copy()
            headers['Referer'] = self.list_url
            
            response = self.session.get(
                file_url, 
                headers=headers,
                timeout=self.timeout,
                verify=self.verify_ssl,
                stream=True
            )
            
            if response.status_code == 200:
                # Enhanced Base Scraper가 이미 올바른 파일명으로 save_path를 설정했으므로 그대로 사용
                filename = save_path
                
                # 파일 저장
                os.makedirs(os.path.dirname(filename), exist_ok=True)
                
                with open(filename, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                file_size = os.path.getsize(filename)
                logger.info(f"파일 다운로드 완료: {filename} ({file_size} bytes)")
                
                return True
            else:
                logger.error(f"파일 다운로드 실패: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"파일 다운로드 중 오류: {e}")
            return False

    def sanitize_filename(self, filename: str) -> str:
        """파일명 정리"""
        # Windows 호환을 위한 특수문자 제거
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = filename.strip('. ')
        
        return filename if filename else "unnamed_file"


def main():
    """테스트용 메인 함수"""
    scraper = EnhancedKritScraper()
    output_dir = "output/krit"
    
    try:
        os.makedirs(output_dir, exist_ok=True)
        scraper.scrape_pages(max_pages=3, output_base=output_dir)
        print("✅ KRIT 스크래핑 완료")
        
    except KeyboardInterrupt:
        print("\n❌ 사용자에 의해 중단되었습니다")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()