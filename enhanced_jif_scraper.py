# -*- coding: utf-8 -*-
"""
전북바이오융합산업진흥원(JIF) Enhanced 스크래퍼 - 표준 테이블 + JavaScript 네비게이션
"""

import requests
from bs4 import BeautifulSoup
import re
import logging
import os
from urllib.parse import urljoin, parse_qs, urlparse, unquote
from enhanced_base_scraper import StandardTableScraper
import time
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class EnhancedJIFScraper(StandardTableScraper):
    """전북바이오융합산업진흥원(JIF) 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        
        # 향상된 헤더 설정 (차단 방지)
        self.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'DNT': '1',
        })
        self.session.headers.update(self.headers)
        
        # 하드코딩된 설정들 (설정 파일로 관리되지만 fallback용)
        self.base_url = "https://www.jif.re.kr"
        self.list_url = "https://www.jif.re.kr/board/list.do?boardUUID=53473d307cb77a53017cb7e09b8e0003&menuUUID=53473d307cb7118c017cb71940970029"
        
        # 사이트 특화 설정
        self.verify_ssl = True  # HTTPS 사이트, SSL 인증서 정상
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1
        
        # UUID 파라미터 추출
        self.board_uuid = "53473d307cb77a53017cb7e09b8e0003"
        self.menu_uuid = "53473d307cb7118c017cb71940970029"
    
    def get_list_url(self, page_num: int) -> str:
        """페이지별 URL 생성 - Spring Framework 페이지네이션"""
        # 설정이 있으면 부모 클래스의 표준 구현 사용
        if self.config and self.config.pagination:
            return super().get_list_url(page_num)
        
        # Fallback: JIF는 page 파라미터와 rowCount 사용
        if page_num == 1:
            return f"{self.list_url}&page=1&rowCount=10"
        else:
            return f"{self.list_url}&page={page_num}&rowCount=10"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱 - 설정 주입과 Fallback 패턴"""
        # 설정 기반 파싱이 가능하면 사용
        if self.config and self.config.selectors:
            return super().parse_list_page(html_content)
        
        # Fallback: 사이트 특화 로직
        return self._parse_list_fallback(html_content)
    
    def _parse_list_fallback(self, html_content: str) -> List[Dict[str, Any]]:
        """JIF 특화된 목록 파싱 로직"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 테이블 찾기 - 캡션이 "일반공고 리스트"인 테이블
        table = None
        for table_elem in soup.find_all('table'):
            caption = table_elem.find('caption')
            if caption and '공고' in caption.get_text():
                table = table_elem
                logger.debug("일반공고 리스트 테이블 찾음")
                break
        
        if not table:
            # 백업: 일반적인 테이블 찾기
            table = soup.find('table')
            if table:
                logger.debug("일반 테이블로 fallback")
        
        if not table:
            logger.warning("공고 목록 테이블을 찾을 수 없습니다")
            return announcements
        
        # tbody에서 행 찾기
        tbody = table.find('tbody')
        if not tbody:
            logger.warning("테이블 tbody를 찾을 수 없습니다")
            return announcements
        
        rows = tbody.find_all('tr')
        if not rows:
            logger.warning("테이블 행을 찾을 수 없습니다")
            return announcements
        
        logger.info(f"테이블에서 {len(rows)}개 행 발견")
        
        for i, row in enumerate(rows):
            try:
                cells = row.find_all('td')
                if len(cells) < 7:  # 번호, 상태, 제목, 공고기간, 첨부파일, 작성자, 작성일, 조회 (8개)
                    logger.debug(f"행 {i}: 셀 수 부족 ({len(cells)}개)")
                    continue
                
                # 제목 셀에서 링크 찾기 (세 번째 셀)
                title_cell = cells[2] if len(cells) > 2 else cells[1]
                link_elem = title_cell.find('a')
                
                if not link_elem:
                    logger.debug(f"행 {i}: 링크를 찾을 수 없음")
                    continue
                
                # 제목과 UUID 추출
                title = link_elem.get_text(strip=True)
                onclick = link_elem.get('onclick', '')
                
                if not title or len(title) < 3:
                    logger.debug(f"행 {i}: 제목이 너무 짧음: '{title}'")
                    continue
                
                # JavaScript onclick에서 UUID 추출
                # 예: fn_view('53473d307cb77a53017cb7e12345')
                article_uuid = ""
                uuid_match = re.search(r"fn_view\(['\"]([^'\"]+)['\"]", onclick)
                if uuid_match:
                    article_uuid = uuid_match.group(1)
                    logger.debug(f"UUID 추출: {article_uuid}")
                else:
                    logger.debug(f"행 {i}: UUID 추출 실패 - onclick: {onclick}")
                    continue
                
                # 상세 페이지 URL 생성
                detail_url = (f"{self.base_url}/board/view.do?"
                            f"boardUUID={self.board_uuid}"
                            f"&menuUUID={self.menu_uuid}"
                            f"&boardArticleUUID={article_uuid}"
                            f"&categoryGroup=0&page=1&rowCount=10")
                
                # 공고 번호 추출 (첫 번째 셀)
                number = ""
                number_cell = cells[0]
                if number_cell:
                    number_text = number_cell.get_text(strip=True)
                    if number_text and number_text != "번호":
                        number = number_text
                
                # 상태 추출 (두 번째 셀)
                status = ""
                if len(cells) > 1:
                    status_cell = cells[1]
                    status = status_cell.get_text(strip=True)
                
                # 공고기간 추출 (네 번째 셀)
                period = ""
                if len(cells) > 3:
                    period_cell = cells[3]
                    period = period_cell.get_text(strip=True)
                
                # 첨부파일 여부 확인 (다섯 번째 셀)
                has_attachment = False
                if len(cells) > 4:
                    attach_cell = cells[4]
                    attach_img = attach_cell.find('img')
                    if attach_img:
                        img_src = attach_img.get('src', '')
                        if '첨부' in img_src or 'attach' in img_src.lower():
                            has_attachment = True
                
                # 작성자 추출 (여섯 번째 셀)
                author = ""
                if len(cells) > 5:
                    author_cell = cells[5]
                    author = author_cell.get_text(strip=True)
                
                # 작성일 추출 (일곱 번째 셀)
                date = ""
                if len(cells) > 6:
                    date_cell = cells[6]
                    date_text = date_cell.get_text(strip=True)
                    # 날짜 패턴 매칭 (YYYY-MM-DD)
                    date_match = re.search(r'(\d{4}-\d{1,2}-\d{1,2})', date_text)
                    if date_match:
                        date = date_match.group(1)
                
                # 조회수 추출 (여덟 번째 셀)
                views = ""
                if len(cells) > 7:
                    views_cell = cells[7]
                    views = views_cell.get_text(strip=True)
                
                logger.debug(f"행 {i}: 공고 발견 - {title[:30]}... (날짜: {date})")
                
                # 공고 정보 구성
                announcement = {
                    'title': title,
                    'url': detail_url,
                    'number': number,
                    'status': status,
                    'period': period,
                    'has_attachment': has_attachment,
                    'author': author,
                    'date': date,
                    'views': views,
                    'article_uuid': article_uuid,
                    'summary': ""
                }
                
                announcements.append(announcement)
                
            except Exception as e:
                logger.error(f"행 {i} 파싱 중 오류: {e}")
                continue
        
        logger.info(f"{len(announcements)}개 공고 파싱 완료")
        return announcements
    
    def parse_detail_page(self, html_content: str, announcement_url: str = None) -> Dict[str, Any]:
        """상세 페이지 파싱 - JIF 실제 HTML 구조 기반"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출
        title = ""
        # 제목 후보들 검색 (h1, h2, h3 순서로)
        for tag in ['h1', 'h2', 'h3', 'h4']:
            title_elem = soup.find(tag)
            if title_elem:
                title_text = title_elem.get_text(strip=True)
                if title_text and len(title_text) > 5:  # 유효한 제목
                    title = title_text
                    logger.debug(f"제목을 {tag} 태그에서 찾음: {title[:50]}...")
                    break
        
        # 백업: 강하게 스타일된 텍스트나 큰 텍스트에서 제목 찾기
        if not title:
            for elem in soup.find_all(['div', 'p', 'span']):
                text = elem.get_text(strip=True)
                if len(text) > 10 and len(text) < 200:  # 제목 같은 길이
                    parent_style = elem.get('style', '')
                    if 'font-weight' in parent_style or 'font-size' in parent_style:
                        title = text
                        break
        
        # 본문 내용 추출
        content = ""
        
        # 방법 1: 본문이 있는 div나 section에서 찾기
        content_candidates = []
        for elem in soup.find_all(['div', 'section', 'article']):
            elem_text = elem.get_text(strip=True)
            if len(elem_text) > 100:  # 충분히 긴 텍스트
                # 메뉴나 네비게이션이 아닌 본문 같은 내용 필터링
                if not any(nav_word in elem_text for nav_word in ['목록', '이전', '다음', '메뉴', '로그인']):
                    content_candidates.append((len(elem_text), elem_text))
        
        # 가장 긴 텍스트를 본문으로 선택
        if content_candidates:
            content_candidates.sort(key=lambda x: x[0], reverse=True)
            content = content_candidates[0][1]
            logger.debug(f"본문 추출: {len(content)}자")
        
        # 방법 2: 백업 - 전체 텍스트에서 본문 부분 추출
        if not content or len(content) < 50:
            all_text = soup.get_text()
            # 본문 시작점 찾기
            content_start_markers = ['공고', '모집', '안내', '신청', '지원', '사업', '접수']
            for marker in content_start_markers:
                if marker in all_text:
                    start_idx = all_text.find(marker)
                    content = all_text[start_idx:start_idx+3000]  # 적당한 길이로 제한
                    break
        
        if not content or len(content) < 30:
            logger.warning("본문 영역을 찾을 수 없거나 내용이 부족합니다")
            content = "본문 내용을 추출할 수 없습니다."
        else:
            logger.info(f"본문 추출 성공: {len(content)}자")
        
        # 첨부파일 추출
        attachments = self._extract_attachments(soup, announcement_url)
        
        return {
            'title': title,
            'content': content,
            'attachments': attachments
        }
    
    def _extract_attachments(self, soup: BeautifulSoup, page_url: str = None) -> List[Dict[str, Any]]:
        """첨부파일 추출 - JIF downloadFile.do 기반 다운로드"""
        attachments = []
        
        # downloadFile.do 패턴 링크 찾기
        for link in soup.find_all('a'):
            href = link.get('href', '')
            
            # 파일 다운로드 링크 확인
            if 'downloadFile.do' in href:
                # 파일명 추출 (링크 텍스트에서)
                filename = link.get_text(strip=True)
                
                # 절대 URL로 변환
                if href.startswith('/'):
                    download_url = f"{self.base_url}{href}"
                else:
                    download_url = href
                
                if filename and download_url:
                    attachments.append({
                        'name': filename,
                        'url': download_url
                    })
                    
                    logger.debug(f"downloadFile.do 첨부파일 발견: {filename}")
        
        # 이미지 태그와 함께 있는 다운로드 링크도 확인
        for img in soup.find_all('img'):
            img_src = img.get('src', '')
            if '첨부' in img_src or 'attach' in img_src.lower() or 'download' in img_src.lower():
                # 이미지 근처의 링크 찾기
                parent = img.parent
                if parent:
                    nearby_link = parent.find('a')
                    if nearby_link:
                        href = nearby_link.get('href', '')
                        if 'downloadFile.do' in href:
                            filename = nearby_link.get_text(strip=True)
                            download_url = f"{self.base_url}{href}" if href.startswith('/') else href
                            
                            if filename and download_url:
                                attachments.append({
                                    'name': filename,
                                    'url': download_url
                                })
                                
                                logger.debug(f"이미지 근처 첨부파일 발견: {filename}")
        
        # 첨부파일 섹션에서 ul/li 구조로 된 파일 목록 찾기
        for ul in soup.find_all('ul'):
            for li in ul.find_all('li'):
                download_link = li.find('a', href=re.compile(r'downloadFile\.do'))
                if download_link:
                    href = download_link.get('href', '')
                    filename = download_link.get_text(strip=True)
                    
                    # "다운로드" 텍스트만 있는 경우 파일명을 다른 곳에서 찾기
                    if filename == "다운로드" or len(filename) < 3:
                        # 같은 li 내의 다른 텍스트나 이미지 alt에서 파일명 찾기
                        img_in_li = li.find('img')
                        if img_in_li:
                            alt_text = img_in_li.get('alt', '')
                            if alt_text and len(alt_text) > 3:
                                filename = alt_text
                        
                        # 여전히 파일명이 없으면 li의 전체 텍스트에서 추출
                        if not filename or filename == "다운로드":
                            li_text = li.get_text(strip=True)
                            # "다운로드" 제거하고 남은 텍스트 사용
                            filename = li_text.replace("다운로드", "").strip()
                    
                    download_url = f"{self.base_url}{href}" if href.startswith('/') else href
                    
                    if filename and download_url and filename != "다운로드":
                        attachments.append({
                            'name': filename,
                            'url': download_url
                        })
                        
                        logger.debug(f"ul/li 구조 첨부파일 발견: {filename}")
        
        logger.info(f"총 {len(attachments)}개 첨부파일 발견")
        return attachments
    
    def download_file(self, url: str, save_path: str, filename: str = None) -> bool:
        """파일 다운로드 - JIF downloadFile.do 처리"""
        try:
            logger.info(f"파일 다운로드 시도: {url}")
            
            # 강화된 헤더로 다운로드 시도
            download_headers = self.headers.copy()
            download_headers.update({
                'Referer': self.base_url,
                'Accept': '*/*',
            })
            
            response = self.session.get(
                url, 
                headers=download_headers,
                verify=self.verify_ssl,
                stream=True,
                timeout=120
            )
            
            # 응답 상태 확인
            if response.status_code != 200:
                logger.error(f"파일 다운로드 실패 {url}: HTTP {response.status_code}")
                return False
            
            # Content-Type 확인
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' in content_type:
                logger.warning(f"HTML 응답 수신 (파일이 없을 수 있음): {url}")
                # 실제로 HTML 에러 페이지인지 확인
                content_preview = response.content[:500].decode('utf-8', errors='ignore')
                if '<html' in content_preview.lower():
                    logger.error(f"HTML 에러 페이지 수신: {url}")
                    return False
            
            # 파일 저장
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # 파일 크기 확인
            file_size = os.path.getsize(save_path)
            if file_size == 0:
                logger.error(f"다운로드된 파일이 비어있음: {save_path}")
                os.remove(save_path)
                return False
            
            logger.info(f"파일 다운로드 완료: {save_path} ({file_size:,} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"파일 다운로드 중 오류 {url}: {e}")
            return False
    
    def _create_meta_info(self, announcement: Dict[str, Any]) -> str:
        """JIF 메타 정보 생성"""
        meta_lines = [f"# {announcement['title']}", ""]
        
        # JIF 특화 메타 정보
        if 'number' in announcement and announcement['number']:
            meta_lines.append(f"**공고번호**: {announcement['number']}")
        if 'status' in announcement and announcement['status']:
            meta_lines.append(f"**상태**: {announcement['status']}")
        if 'period' in announcement and announcement['period']:
            meta_lines.append(f"**공고기간**: {announcement['period']}")
        if 'author' in announcement and announcement['author']:
            meta_lines.append(f"**작성자**: {announcement['author']}")
        if 'date' in announcement and announcement['date']:
            meta_lines.append(f"**작성일**: {announcement['date']}")
        if 'views' in announcement and announcement['views']:
            meta_lines.append(f"**조회수**: {announcement['views']}")
        if 'has_attachment' in announcement and announcement['has_attachment']:
            meta_lines.append(f"**첨부파일**: 있음")
        if 'summary' in announcement and announcement['summary']:
            meta_lines.append(f"**요약**: {announcement['summary']}")
        
        meta_lines.extend([
            f"**원본 URL**: {announcement['url']}",
            "",
            "---",
            ""
        ])
        
        return "\n".join(meta_lines)

# 하위 호환성을 위한 별칭
JIFScraper = EnhancedJIFScraper