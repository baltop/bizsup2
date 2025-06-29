# -*- coding: utf-8 -*-
"""
Enhanced MIRE 스크래퍼 - 세션 기반 스크래퍼
환동해산업연구원(MIRE) 전용 스크래퍼 (Enhanced 아키텍처)
mire_scraper.py 기반 리팩토링
"""

from enhanced_base_scraper import SessionBasedScraper
from bs4 import BeautifulSoup
from urllib.parse import urljoin, parse_qs, urlparse, unquote
import re
import os
import time
import requests
import logging

logger = logging.getLogger(__name__)

class EnhancedMIREScraper(SessionBasedScraper):
    """환동해산업연구원(MIRE) 전용 스크래퍼 - Enhanced 버전"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "http://mire.re.kr"
        self.list_url = "http://mire.re.kr/sub4_4.php"
        self.session_id = None
        self.default_encoding = 'euc-kr'  # MIRE는 EUC-KR 인코딩 사용
        
    def initialize_session(self):
        """세션 초기화 - MIRE PHP 세션 ID 획득"""
        if self.session_initialized and self.session_id:
            return True
            
        try:
            logger.info("MIRE 세션 ID 획득 중...")
            # 초기 페이지 접속하여 세션 ID 획득
            response = self.session.get(self.list_url, headers=self.headers, verify=self.verify_ssl)
            
            # 쿠키에서 PHPSESSID 추출
            if 'PHPSESSID' in response.cookies:
                self.session_id = response.cookies['PHPSESSID']
                logger.info(f"새로운 세션 ID 획득: {self.session_id}")
                self.session_initialized = True
                self.session_data['session_id'] = self.session_id
                return True
            else:
                # URL에서 PHPSESSID 추출 시도
                final_url = response.url
                parsed_url = urlparse(final_url)
                params = parse_qs(parsed_url.query)
                if 'PHPSESSID' in params:
                    self.session_id = params['PHPSESSID'][0]
                    logger.info(f"URL에서 세션 ID 획득: {self.session_id}")
                    self.session_initialized = True
                    self.session_data['session_id'] = self.session_id
                    return True
                else:
                    # 기본값 사용
                    self.session_id = "default_session_id"
                    logger.warning("세션 ID를 찾을 수 없어 기본값 사용")
                    self.session_initialized = True
                    return True
                    
        except Exception as e:
            logger.error(f"세션 ID 획득 실패: {e}")
            self.session_id = "default_session_id"
            self.session_initialized = True
            return False
    
    def get_page(self, url: str, **kwargs) -> requests.Response:
        """페이지 가져오기 - EUC-KR 인코딩 처리"""
        try:
            response = self.session.get(url, headers=self.headers, verify=self.verify_ssl, **kwargs)
            response.encoding = 'euc-kr'  # MIRE 사이트는 EUC-KR 사용
            return response
        except Exception as e:
            logger.error(f"페이지 가져오기 실패 {url}: {e}")
            return None
    
    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 반환"""
        if not self.initialize_session():
            logger.error("세션 초기화 실패")
            return self.list_url
            
        if page_num == 1:
            return f"{self.list_url}?PHPSESSID={self.session_id}"
        else:
            return f"{self.list_url}?PHPSESSID={self.session_id}&page={page_num}"
            
    def parse_list_page(self, html_content: str) -> list:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 모든 상세페이지 링크 찾기 (type=read 패턴)
        detail_links = soup.find_all('a', href=re.compile(r'type=read.*id=\d+'))
        
        for link in detail_links:
            try:
                # 제목
                title = link.get_text(strip=True)
                if not title or len(title) < 5:  # 너무 짧은 텍스트는 제외
                    continue
                    
                # 공지사항 제외 (선택적)
                if title == '공지':
                    continue
                
                # URL
                href = link.get('href', '')
                if not href:
                    continue
                    
                # PHP 세션 ID 포함
                if 'PHPSESSID' not in href:
                    if '?' in href:
                        href += f"&PHPSESSID={self.session_id}"
                    else:
                        href += f"?PHPSESSID={self.session_id}"
                detail_url = urljoin(self.base_url, href)
                
                # 부모 행에서 추가 정보 추출
                parent_tr = link.find_parent('tr')
                num = ''
                date = ''
                views = ''
                
                if parent_tr:
                    tds = parent_tr.find_all('td')
                    # TD 구조: 번호, 공백, 제목(링크), 공백, 작성자, 공백, 날짜, 공백, 조회수
                    for i, td in enumerate(tds):
                        text = td.get_text(strip=True)
                        # 번호 (숫자만)
                        if text.isdigit() and not num:
                            num = text
                        # 날짜 (YY.MM.DD 패턴)
                        elif len(text) == 8 and text[2] == '.' and text[5] == '.':
                            date = text
                        # 조회수 (마지막 숫자)
                        elif text.isdigit() and i > len(tds) - 3:
                            views = text
                
                # 중복 제거를 위해 URL 기반으로 체크
                if not any(a['url'] == detail_url for a in announcements):
                    announcements.append({
                        'num': num,
                        'title': title,
                        'url': detail_url,
                        'date': date,
                        'views': views
                    })
                    
            except Exception as e:
                logger.debug(f"링크 파싱 중 오류 (스킵): {e}")
                continue
        
        # 정렬 (번호 역순으로)
        announcements.sort(key=lambda x: int(x['num']) if x['num'].isdigit() else 0, reverse=True)
        
        logger.info(f"목록 페이지에서 {len(announcements)}개 공고 발견")
        return announcements
        
    def parse_detail_page(self, html_content: str) -> dict:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 본문 내용 찾기
        content_area = self._find_content_area(soup)
        
        # 첨부파일 찾기 - type=download 패턴을 사용
        attachments = self._find_attachments(soup)
        
        # 본문을 마크다운으로 변환
        content_md = ""
        if content_area:
            content_md = self.h.handle(str(content_area))
        else:
            # content_area가 없으면 전체 테이블을 마크다운으로 변환
            content_table = soup.find('table', class_='tb2')
            if content_table:
                content_md = self.h.handle(str(content_table))
        
        return {
            'content': content_md,
            'attachments': attachments
        }
    
    def _find_content_area(self, soup):
        """본문 영역 찾기"""
        # 테이블 구조에서 본문 찾기
        content_table = soup.find('table', class_='tb2')
        if content_table:
            # 본문이 있는 TD 찾기 - 크게 한 개의 TD에 전체 내용이 들어있는 경우
            rows = content_table.find_all('tr')
            for row in rows:
                tds = row.find_all('td')
                if len(tds) == 1:  # TD가 하나만 있는 행
                    td = tds[0]
                    # 자식 요소가 많거나 텍스트가 긴 경우
                    if len(td.find_all()) > 5 or len(td.get_text(strip=True)) > 200:
                        logger.debug("테이블 구조에서 본문 영역 발견")
                        return td
        
        # 다른 가능한 본문 영역들
        content_selectors = [
            'div.view_cont',
            'div.board_view',
            'div.view_content',
            'div.content',
            'td.content'
        ]
        
        for selector in content_selectors:
            content_area = soup.select_one(selector)
            if content_area:
                logger.debug(f"본문 영역 발견: {selector}")
                return content_area
        
        return None
    
    def _find_attachments(self, soup):
        """첨부파일 찾기"""
        attachments = []
        
        # type=download 패턴으로 파일 링크 찾기
        file_links = soup.find_all('a', href=re.compile(r'type=download'))
        for link in file_links:
            file_name = link.get_text(strip=True)
            file_url = link.get('href', '')
            
            if file_url and file_name:
                # 세션 ID 추가
                if 'PHPSESSID' not in file_url:
                    if '?' in file_url:
                        file_url += f"&PHPSESSID={self.session_id}"
                    else:
                        file_url += f"?PHPSESSID={self.session_id}"
                        
                file_url = urljoin(self.base_url, file_url)
                
                attachments.append({
                    'name': file_name,
                    'url': file_url
                })
        
        logger.info(f"첨부파일 {len(attachments)}개 발견")
        return attachments
    
    def download_file(self, url: str, save_path: str, attachment_info: dict = None) -> bool:
        """파일 다운로드 - MIRE 맞춤형 (EUC-KR 파일명 처리)"""
        try:
            logger.info(f"파일 다운로드 시작: {url}")
            
            # Referer 헤더 추가
            headers = self.headers.copy()
            headers['Referer'] = self.base_url
            
            response = self.session.get(url, headers=headers, stream=True, verify=self.verify_ssl)
            response.raise_for_status()
            
            # 실제 파일명 추출 - MIRE 특화 EUC-KR 처리
            actual_filename = self._extract_mire_filename(response, save_path)
            if actual_filename != save_path:
                save_path = actual_filename
            
            # 파일 저장
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        
            file_size = os.path.getsize(save_path)
            logger.info(f"다운로드 완료: {save_path} ({file_size:,} bytes)")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"네트워크 오류 - 파일 다운로드 실패 {url}: {e}")
            return False
        except Exception as e:
            logger.error(f"파일 다운로드 실패 {url}: {e}")
            return False
    
    def _extract_mire_filename(self, response: requests.Response, default_path: str) -> str:
        """MIRE 사이트 전용 파일명 추출 - EUC-KR 인코딩 처리"""
        content_disposition = response.headers.get('Content-Disposition', '')
        
        if not content_disposition:
            return default_path
        
        # 파일명 추출
        filename_match = re.search(r'filename[^;=\n]*=(([\'"]).*?\2|[^;\n]*)', content_disposition)
        if filename_match:
            filename = filename_match.group(1).strip('"\'')
            
            # EUC-KR 인코딩 처리 - 다단계 폴백
            for encoding in ['euc-kr', 'utf-8', 'cp949']:
                try:
                    if encoding == 'euc-kr':
                        # EUC-KR로 잘못 해석된 경우 복구 시도
                        decoded = filename.encode('latin-1').decode('euc-kr')
                    elif encoding == 'utf-8':
                        # UTF-8로 잘못 해석된 경우 복구 시도
                        decoded = filename.encode('latin-1').decode('utf-8')
                    else:
                        # CP949 시도
                        decoded = filename.encode('latin-1').decode('cp949')
                    
                    if decoded and not decoded.isspace():
                        save_dir = os.path.dirname(default_path)
                        # + 기호를 공백으로 변경 및 URL 디코딩
                        clean_filename = decoded.replace('+', ' ')
                        try:
                            clean_filename = unquote(clean_filename)
                        except:
                            pass
                        
                        final_filename = self.sanitize_filename(clean_filename)
                        return os.path.join(save_dir, final_filename)
                        
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    logger.debug(f"파일명 디코딩 시도 실패 ({encoding}): {e}")
                    continue
        
        return default_path