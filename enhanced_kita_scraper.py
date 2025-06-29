# -*- coding: utf-8 -*-
"""
한국무역협회(KITA) Enhanced 스크래퍼 - JavaScript 기반 동적 사이트
"""

import requests
from bs4 import BeautifulSoup
import re
import logging
from urllib.parse import urljoin
from enhanced_base_scraper import StandardTableScraper
import time
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class EnhancedKitaScraper(StandardTableScraper):
    """한국무역협회(KITA) 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        # 하드코딩된 설정들 (설정 파일로 관리되지만 fallback용)
        self.base_url = "https://www.kita.net"
        self.list_url = "https://www.kita.net/asocBiz/asocBiz/asocBizOngoingList.do"
        self.detail_url = "https://www.kita.net/asocBiz/asocBiz/asocBizOngoingDetail.do"
        
        # 사이트 특화 설정
        self.verify_ssl = True  # HTTPS 정상 인증서
        self.default_encoding = 'utf-8'
        
        # 세션 관리
        self.session_initialized = False
        
    def initialize_session(self):
        """세션 초기화"""
        if self.session_initialized:
            return True
        
        try:
            # 첫 페이지 방문으로 세션 초기화
            response = self.get_page(self.list_url)
            if response and response.status_code == 200:
                self.session_initialized = True
                logger.info("KITA 세션 초기화 완료")
                return True
        except Exception as e:
            logger.error(f"KITA 세션 초기화 실패: {e}")
        
        return False
    
    def get_list_url(self, page_num: int) -> str:
        """페이지별 URL 생성 - JavaScript POST 요청 기반"""
        # KITA는 동일한 URL로 페이지 번호를 POST로 전송
        return self.list_url
    
    def get_page_data(self, page_num: int) -> requests.Response:
        """페이지별 데이터 가져오기 - POST 요청"""
        if not self.initialize_session():
            logger.error("세션 초기화 실패")
            return None
        
        # POST 데이터 구성 (JavaScript goPage() 함수 분석 결과)
        form_data = {
            'pageIndex': str(page_num),
            'searchBizGbn': '',
            'searchAreaCd': '',
            'searchBizTitle': '',
            'searchContinent': '',
            'searchCountry': '',
            'searchCateGbn': '',
            'searchItemDetail': '',
            'searchDateGbn': '',
            'searchStartDate': '',
            'searchEndDate': '',
            'searchOrderGbn': '1'  # 마감임박 순
        }
        
        try:
            response = self.session.post(
                self.list_url,
                data=form_data,
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Referer': self.list_url
                },
                verify=self.verify_ssl,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                response.encoding = 'utf-8'
                return response
            else:
                logger.warning(f"페이지 {page_num} HTTP 상태: {response.status_code}")
                
        except Exception as e:
            logger.error(f"페이지 {page_num} 요청 실패: {e}")
        
        return None
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱 - KITA 사이트 특화"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # KITA 사이트 리스트 구조 분석
        # <ul class="board-list-biz theme-board3"> 형태
        list_container = soup.find('ul', class_='board-list-biz')
        
        if not list_container:
            logger.warning("KITA 리스트 컨테이너를 찾을 수 없습니다")
            return announcements
        
        # 각 프로젝트 항목 찾기
        project_items = list_container.find_all('li')
        
        logger.info(f"KITA 목록에서 {len(project_items)}개 항목 발견")
        
        for item in project_items:
            try:
                # JavaScript 링크에서 bizAltkey 추출
                # onclick="goDetailPage('202505030');"
                link_elem = item.find('a', onclick=re.compile(r'goDetailPage'))
                if not link_elem:
                    continue
                
                onclick_attr = link_elem.get('onclick', '')
                bizaltkey_match = re.search(r"goDetailPage\('([^']+)'\)", onclick_attr)
                
                if not bizaltkey_match:
                    logger.debug(f"bizAltkey를 찾을 수 없는 항목 스킵: {onclick_attr}")
                    continue
                
                bizaltkey = bizaltkey_match.group(1)
                title = link_elem.get('title') or link_elem.get_text(strip=True)
                
                if not title:
                    logger.debug(f"제목이 없는 항목 스킵: {bizaltkey}")
                    continue
                
                # 상세 페이지 URL 구성 (POST 방식이므로 파라미터 포함)
                detail_url = f"{self.detail_url}?bizAltkey={bizaltkey}"
                
                announcement = {
                    'title': title,
                    'url': detail_url,
                    'bizaltkey': bizaltkey
                }
                
                # 추가 메타 정보 추출
                self._extract_meta_info(item, announcement)
                
                announcements.append(announcement)
                logger.debug(f"공고 파싱: {title[:50]}...")
                
            except Exception as e:
                logger.error(f"항목 파싱 중 오류: {e}")
                continue
        
        logger.info(f"{len(announcements)}개 KITA 공고 파싱 완료")
        return announcements
    
    def _extract_meta_info(self, item_elem: BeautifulSoup, announcement: Dict[str, Any]):
        """추가 메타 정보 추출"""
        try:
            # 사업기간 정보
            date_div = item_elem.find('div', class_='date')
            if date_div:
                date_paragraphs = date_div.find_all('p')
                for p in date_paragraphs:
                    text = p.get_text(strip=True)
                    if '사업기간' in text:
                        announcement['period'] = text.replace('사업기간 :', '').strip()
                    elif '모집기간' in text:
                        announcement['recruitment'] = text.replace('모집기간 :', '').strip()
            
            # 사업 유형 및 지역 정보
            info_div = item_elem.find('div', class_='info')
            if info_div:
                li_elements = info_div.find_all('li')
                for li in li_elements:
                    text = li.get_text(strip=True)
                    if text.startswith('사업 :'):
                        announcement['business_type'] = text.replace('사업 :', '').strip()
                    elif text.startswith('지역 :'):
                        announcement['region'] = text.replace('지역 :', '').strip()
            
            # D-day 정보
            dday_elem = item_elem.find('strong')
            if dday_elem and dday_elem.get_text(strip=True).startswith('D-'):
                announcement['dday'] = dday_elem.get_text(strip=True)
                
        except Exception as e:
            logger.debug(f"메타 정보 추출 중 오류: {e}")
    
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = {
            'content': '',
            'attachments': []
        }
        
        try:
            # 페이지 제목
            page_title = soup.find('title')
            title_text = page_title.get_text() if page_title else ''
            
            # 본문 내용 추출
            content_text = self._extract_content(soup, title_text)
            result['content'] = content_text
            
            # 첨부파일 추출
            attachments = self._extract_attachments(soup)
            result['attachments'] = attachments
            
            logger.info(f"KITA 상세 페이지 파싱 완료 - 내용: {len(content_text)}자, 첨부파일: {len(attachments)}개")
            
        except Exception as e:
            logger.error(f"KITA 상세 페이지 파싱 실패: {e}")
        
        return result
    
    def _extract_content(self, soup: BeautifulSoup, title_text: str) -> str:
        """본문 내용 추출"""
        content_parts = []
        
        # 제목 추가
        if title_text:
            content_parts.append(f"# {title_text}\n")
        
        # 메인 컨텐츠 영역 찾기 - KITA 사이트 특화
        content_selectors = [
            '.board-detail.theme-board3',
            '.detail-head',
            '.board-detail',
            '.detail-content',
            '.view-content'
        ]
        
        main_content = None
        for selector in content_selectors:
            main_content = soup.select_one(selector)
            if main_content:
                logger.debug(f"본문을 {selector} 선택자로 찾음")
                break
        
        if main_content:
            # HTML을 마크다운으로 변환
            content_html = str(main_content)
            markdown_content = self.h.handle(content_html)
            content_parts.append(markdown_content)
        else:
            # 폴백: 제목과 기본 정보만 추출
            logger.warning("메인 컨텐츠 영역을 찾을 수 없음 - 기본 정보만 추출")
            
            # 기본 정보 추출 시도
            basic_info = []
            
            # 사업기간, 모집기간 등 메타 정보
            for dl in soup.find_all('dl'):
                dt = dl.find('dt')
                dd = dl.find('dd')
                if dt and dd:
                    key = dt.get_text(strip=True)
                    value = dd.get_text(strip=True)
                    if key and value and any(keyword in key for keyword in ['사업기간', '모집기간', '참가신청', '대상', '내용']):
                        basic_info.append(f"**{key}**: {value}")
            
            if basic_info:
                content_parts.extend(basic_info)
            else:
                content_parts.append("상세 내용은 원본 사이트를 확인해주세요.")
        
        return '\n'.join(content_parts)
    
    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """첨부파일 추출"""
        attachments = []
        
        # KITA 사이트 첨부파일 패턴 분석
        attachment_selectors = [
            'a[href*="download"]',
            'a[href*="file"]',
            'a[onclick*="download"]',
            '.attach a',
            '.file-list a',
            '.download a'
        ]
        
        for selector in attachment_selectors:
            links = soup.select(selector)
            for link in links:
                try:
                    href = link.get('href', '')
                    onclick = link.get('onclick', '')
                    
                    # 파일명 추출
                    file_name = link.get_text(strip=True)
                    if not file_name:
                        file_name = link.get('title', '')
                    
                    # 다운로드 URL 구성
                    file_url = None
                    
                    if href and ('download' in href or 'file' in href):
                        file_url = urljoin(self.base_url, href)
                    elif onclick and 'download' in onclick:
                        # JavaScript 다운로드 함수에서 URL 추출
                        # 예: downloadFile('file_id') 패턴
                        url_match = re.search(r"['\"]([^'\"]*download[^'\"]*)['\"]", onclick)
                        if url_match:
                            file_url = urljoin(self.base_url, url_match.group(1))
                    
                    if file_url and file_name:
                        # 파일 확장자 확인
                        file_patterns = [
                            r'\.pdf$', r'\.hwp$', r'\.doc$', r'\.docx$',
                            r'\.xls$', r'\.xlsx$', r'\.ppt$', r'\.pptx$',
                            r'\.zip$', r'\.txt$', r'\.hwpx$', r'\.jpg$', r'\.png$'
                        ]
                        
                        is_file = any(re.search(pattern, file_name.lower()) for pattern in file_patterns)
                        
                        if is_file:
                            attachment = {
                                'name': file_name,
                                'url': file_url
                            }
                            attachments.append(attachment)
                            logger.debug(f"첨부파일 발견: {file_name}")
                
                except Exception as e:
                    logger.debug(f"첨부파일 링크 처리 중 오류: {e}")
                    continue
        
        logger.info(f"{len(attachments)}개 첨부파일 발견")
        return attachments
    
    def get_page(self, url: str, **kwargs) -> requests.Response:
        """페이지 가져오기 - POST 요청 지원"""
        # bizAltkey가 포함된 URL인 경우 POST 요청으로 처리
        if 'bizAltkey=' in url:
            bizaltkey = url.split('bizAltkey=')[1].split('&')[0]
            
            # POST 데이터로 상세 페이지 요청
            form_data = {
                'bizAltkey': bizaltkey
            }
            
            try:
                response = self.session.post(
                    self.detail_url,
                    data=form_data,
                    headers={
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'Referer': self.list_url
                    },
                    verify=self.verify_ssl,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    response.encoding = 'utf-8'
                    return response
                    
            except Exception as e:
                logger.error(f"KITA 상세 페이지 요청 실패: {e}")
                return None
        
        # 일반적인 GET 요청
        return super().get_page(url, **kwargs)
    
    def _get_page_announcements(self, page_num: int) -> List[Dict[str, Any]]:
        """페이지별 공고 목록 가져오기"""
        response = self.get_page_data(page_num)
        
        if not response:
            logger.warning(f"페이지 {page_num} 데이터를 가져올 수 없습니다")
            return []
        
        announcements = self.parse_list_page(response.text)
        
        # 마지막 페이지 감지
        if not announcements and page_num > 1:
            logger.info(f"페이지 {page_num}에 공고가 없어 마지막 페이지로 판단됩니다")
        
        return announcements


# 하위 호환성을 위한 별칭
KitaScraper = EnhancedKitaScraper