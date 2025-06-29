#!/usr/bin/env python3
"""
Enhanced KEA (한국에너지공단) 스크래퍼

KEA 공지사항 게시판에서 공고를 수집하는 스크래퍼입니다.
표준 HTML 테이블 기반 사이트이므로 BeautifulSoup으로 파싱합니다.

URL: https://www.kea.kr/sub_news/notice.php
"""

import os
import re
import time
import logging
from typing import List, Dict, Any
from urllib.parse import urljoin, unquote
from bs4 import BeautifulSoup
from enhanced_base_scraper import StandardTableScraper

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedKeaScraper(StandardTableScraper):
    """KEA 전용 Enhanced 스크래퍼 - 표준 테이블 기반"""
    
    def __init__(self):
        super().__init__()
        
        # KEA 사이트 설정
        self.base_url = "https://www.kea.kr"
        self.list_url = "https://www.kea.kr/sub_news/notice.php"
        
        # 사이트별 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1
        
        # KEA 특화 파라미터
        self.board_name = "notice"
        
    def get_list_url(self, page_num: int) -> str:
        """페이지별 URL 생성"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}?page={page_num}&b_name={self.board_name}"
        
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 게시판 테이블 찾기
        table = soup.find('table')
        if not table:
            logger.error("게시판 테이블을 찾을 수 없습니다")
            return announcements
            
        tbody = table.find('tbody')
        if not tbody:
            # tbody가 없는 경우 table에서 직접 tr 찾기
            tbody = table
            
        rows = tbody.find_all('tr')
        logger.info(f"발견된 행 수: {len(rows)}")
        
        for i, row in enumerate(rows):
            try:
                cells = row.find_all('td')
                if len(cells) < 5:
                    continue
                    
                # 번호 (첫 번째 셀) - "공지" 또는 숫자
                number_cell = cells[0]
                number = number_cell.get_text(strip=True)
                
                # 제목 (두 번째 셀)
                title_cell = cells[1]
                title_link = title_cell.find('a')
                if not title_link:
                    continue
                    
                title = title_link.get_text(strip=True)
                href = title_link.get('href', '')
                
                # 상대 URL을 절대 URL로 변환
                if href.startswith('/'):
                    detail_url = self.base_url + href
                else:
                    detail_url = urljoin(self.base_url, href)
                
                # 작성자 (세 번째 셀)
                author_cell = cells[2]
                author = author_cell.get_text(strip=True)
                
                # 등록일 (네 번째 셀)
                date_cell = cells[3]
                date = date_cell.get_text(strip=True)
                
                # 조회수 (다섯 번째 셀)
                views_cell = cells[4]
                views = views_cell.get_text(strip=True)
                
                # 첨부파일 여부 확인 (제목에서 "첨부파일" 텍스트 확인)
                has_attachments = "첨부파일" in title or "첨부" in title
                
                announcement = {
                    'number': number,
                    'title': title,
                    'author': author,
                    'date': date,
                    'views': views,
                    'url': detail_url,
                    'has_attachments': has_attachments
                }
                
                announcements.append(announcement)
                logger.info(f"공고 추가: [{number}] {title}")
                
            except Exception as e:
                logger.error(f"행 {i} 파싱 실패: {e}")
                continue
                
        logger.info(f"총 {len(announcements)}개 공고 수집완료")
        return announcements
        
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱 - KEA 구조에 최적화"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # KEA 상세 페이지에서 제목 추출
        # 다양한 선택자 시도
        title_selectors = [
            'h1',
            'h2', 
            'h3',
            '.title',
            'strong',
            'paragraph'  # KEA는 paragraph 태그를 사용할 수 있음
        ]
        
        title = "제목 없음"
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                potential_title = title_elem.get_text(strip=True)
                if potential_title and len(potential_title) > 5:  # 의미있는 제목인지 확인
                    title = potential_title
                    break
        
        # 본문 내용 추출
        content_text = self._extract_main_content(soup)
        
        # 메타 정보 추출
        meta_info = self.extract_meta_info(soup)
        
        # 첨부파일 추출
        attachments = self._extract_attachments(soup)
        
        # 마크다운 형식으로 조합
        markdown_content = f"# {title}\n\n"
        
        if meta_info:
            for key, value in meta_info.items():
                markdown_content += f"**{key}**: {value}\n"
            markdown_content += "\n"
        
        markdown_content += "---\n\n"
        markdown_content += content_text
        
        return {
            'content': markdown_content,
            'attachments': attachments
        }
        
    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """KEA 사이트에서 본문 내용 추출 - 정확한 선택자 사용"""
        
        # KEA 특화 콘텐츠 선택자 (정확한 구조 기반)
        content_selectors = [
            '.board_viewM .note-editable',  # 주요 선택자
            'div.board_viewM div.note-editable',  # 더 구체적
            '.note-editable',  # 대안
            '.board_viewM'  # 백업
        ]
        
        content_elem = None
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                logger.debug(f"콘텐츠 선택자 사용: {selector}")
                break
        
        if content_elem:
            # UI 메시지 요소들 제거
            ui_message_selectors = [
                '#error_msg',
                '.ment_del',
                '.ment_id', 
                '.ment_comment',
                '.ment_max',
                '.ment_copy',
                '.ment_auth'
            ]
            
            for ui_selector in ui_message_selectors:
                for ui_elem in content_elem.select(ui_selector):
                    ui_elem.decompose()
            
            # 본문 텍스트 추출
            content_text = self.simple_html_to_text(content_elem)
            
            # UI 메시지 텍스트 필터링 (혹시 놓친 것들)
            ui_messages = [
                "삭제하시겠습니까?",
                "로그인이 필요합니다.",
                "댓글 내용을 남겨주세요.",
                "최대 글자수를 초과하였습니다.",
                "복사가 완료되었습니다.",
                "권한이 없습니다.",
                "공지사항"
            ]
            
            for msg in ui_messages:
                content_text = content_text.replace(msg, "").strip()
            
            # 빈 줄 정리
            content_text = re.sub(r'\n\s*\n\s*\n', '\n\n', content_text)
            
            if content_text and len(content_text.strip()) > 20:
                return content_text
        
        # 백업 방법: 가장 긴 텍스트 블록 찾기 (UI 메시지 제외)
        all_containers = soup.find_all(['div', 'p', 'article', 'section'])
        max_length = 0
        best_content = ""
        
        for container in all_containers:
            container_text = container.get_text(strip=True)
            
            # UI 메시지나 네비게이션이 아닌 실제 내용인지 확인
            if (len(container_text) > max_length and 
                len(container_text) > 50 and
                not self._contains_ui_messages(container_text) and
                not self._is_navigation_content(container_text)):
                best_content = container_text
                max_length = len(container_text)
        
        return best_content if best_content else "본문 내용을 찾을 수 없습니다."
    
    def _contains_ui_messages(self, text: str) -> bool:
        """UI 메시지 포함 여부 확인"""
        ui_messages = [
            "삭제하시겠습니까?",
            "로그인이 필요합니다.",
            "댓글 내용을 남겨주세요.",
            "최대 글자수를 초과하였습니다."
        ]
        
        return any(msg in text for msg in ui_messages)
    
    def _is_navigation_content(self, text: str) -> bool:
        """네비게이션 또는 메뉴 내용인지 확인"""
        nav_keywords = [
            '홈', '로그인', '회원가입', '사이트맵', '메뉴', '네비게이션',
            '검색', '이전', '다음', '목록', '첫페이지', '마지막페이지',
            '페이지', '이동', '선택', '전체메뉴', '바로가기'
        ]
        
        for keyword in nav_keywords:
            if text.count(keyword) > 3:  # 같은 키워드가 많이 반복되면 네비게이션
                return True
        
        # 짧은 텍스트들이 많이 나열된 경우도 네비게이션일 가능성
        if len(text.split()) > 20 and len(text) / len(text.split()) < 5:
            return True
            
        return False
        
    def extract_meta_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """KEA 구조에서 메타 정보 추출"""
        meta_info = {}
        
        # list 태그에서 작성자, 날짜, 조회수 정보 찾기
        list_elem = soup.find('list')
        if list_elem:
            list_text = list_elem.get_text()
            
            # 날짜 패턴 찾기 (2025.06.26 형태)
            date_match = re.search(r'(\d{4}\.\d{2}\.\d{2})', list_text)
            if date_match:
                meta_info['작성일'] = date_match.group(1)
            
            # 조회수 패턴 찾기
            views_match = re.search(r'(\d+)(?:\s*회)?$', list_text.strip())
            if views_match:
                meta_info['조회수'] = views_match.group(1)
            
            # 작성자 (보통 관리자)
            if '관리자' in list_text:
                meta_info['작성자'] = '관리자'
        
        # 다른 방법으로 메타 정보 찾기
        if not meta_info:
            # 텍스트에서 날짜 패턴 찾기
            page_text = soup.get_text()
            date_match = re.search(r'(\d{4}\.\d{2}\.\d{2})', page_text)
            if date_match:
                meta_info['작성일'] = date_match.group(1)
        
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
        """KEA 구조에서 첨부파일 정보 추출 - 정확한 구조 기반"""
        attachments = []
        
        # KEA의 정확한 첨부파일 영역에서 추출
        attachment_selectors = [
            '.board_viewF a[href*="download"]',  # 주요 선택자
            'div.board_viewF a[href*="download.v2.php"]',  # 더 구체적
            'a[href*="download.v2.php"]'  # 백업
        ]
        
        file_links = []
        for selector in attachment_selectors:
            file_links = soup.select(selector)
            if file_links:
                logger.debug(f"첨부파일 선택자 사용: {selector}")
                break
        
        for link in file_links:
            href = link.get('href', '')
            filename_raw = link.get_text(strip=True)
            
            if href and filename_raw:
                # 절대 URL로 변환
                if href.startswith('../'):
                    # ../bbs_sun/download.v2.php -> https://www.kea.kr/bbs_sun/download.v2.php
                    file_url = self.base_url + href[2:]
                elif href.startswith('/'):
                    file_url = self.base_url + href
                else:
                    file_url = urljoin(self.base_url, href)
                
                # 파일명에서 크기 정보 제거 (예: "파일명.pdf [209kb]" -> "파일명.pdf")
                filename = re.sub(r'\s*\[[\d]+kb\]\s*', '', filename_raw).strip()
                
                # 파일 크기 정보 추출
                size_match = re.search(r'\[(\d+)kb\]', filename_raw)
                file_size_kb = size_match.group(1) if size_match else None
                
                attachments.append({
                    'filename': filename,
                    'url': file_url,
                    'type': 'direct',
                    'size_kb': file_size_kb
                })
                logger.debug(f"첨부파일 발견: {filename} ({file_size_kb}kb)")
        
        # 백업: 모든 download 링크 확인 (중복 제외)
        if not attachments:
            all_download_links = soup.find_all('a', href=re.compile(r'download'))
            for link in all_download_links:
                href = link.get('href', '')
                filename = link.get_text(strip=True)
                
                if href and filename and len(filename) > 0:
                    if href.startswith('../'):
                        file_url = self.base_url + href[2:]
                    elif href.startswith('/'):
                        file_url = self.base_url + href
                    else:
                        file_url = urljoin(self.base_url, href)
                    
                    # 파일명 정리
                    filename = re.sub(r'\s*\[[\d]+kb\]\s*', '', filename).strip()
                    
                    attachments.append({
                        'filename': filename,
                        'url': file_url,
                        'type': 'direct'
                    })
                    logger.debug(f"백업 첨부파일 발견: {filename}")
        
        # 중복 제거
        unique_attachments = []
        seen_urls = set()
        for attachment in attachments:
            if attachment['url'] not in seen_urls:
                unique_attachments.append(attachment)
                seen_urls.add(attachment['url'])
        
        logger.info(f"첨부파일 {len(unique_attachments)}개 발견")
        return unique_attachments
        
    def _download_attachments(self, attachments: List[Dict[str, Any]], folder_path: str):
        """첨부파일 다운로드 - KEA 전용 오버라이드"""
        if not attachments:
            logger.info("첨부파일이 없습니다")
            return
        
        logger.info(f"{len(attachments)}개 첨부파일 다운로드 시작")
        attachments_folder = os.path.join(folder_path, 'attachments')
        os.makedirs(attachments_folder, exist_ok=True)
        
        for i, attachment in enumerate(attachments):
            try:
                url = attachment['url']
                filename = attachment.get('filename', f'attachment_{i+1}')
                
                # 파일명 정리
                clean_filename = self.sanitize_filename(filename)
                file_path = os.path.join(attachments_folder, clean_filename)
                
                logger.info(f"  첨부파일 {i+1}: {filename}")
                
                # 헤더 설정
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Referer': self.list_url
                }
                
                response = self.session.get(url, headers=headers, stream=True, 
                                          timeout=self.timeout, verify=self.verify_ssl)
                response.raise_for_status()
                
                # Content-Disposition에서 파일명 추출 시도
                content_disposition = response.headers.get('Content-Disposition', '')
                if content_disposition:
                    extracted_filename = self.extract_filename_from_disposition(content_disposition)
                    if extracted_filename:
                        clean_filename = self.sanitize_filename(extracted_filename)
                        file_path = os.path.join(attachments_folder, clean_filename)
                
                # 파일 저장
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                file_size = os.path.getsize(file_path)
                logger.info(f"파일 다운로드 완료: {clean_filename} ({file_size} bytes)")
                
            except Exception as e:
                logger.error(f"첨부파일 다운로드 실패 - {filename}: {e}")
                continue
            
    def extract_filename_from_disposition(self, content_disposition: str) -> str:
        """Content-Disposition 헤더에서 파일명 추출 - 한글 파일명 개선"""
        try:
            # RFC 5987 형식 우선 처리 (filename*=UTF-8''filename.ext)
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
                
                # 다양한 인코딩 시도 (KEA는 EUC-KR 사용할 가능성)
                encoding_attempts = ['utf-8', 'euc-kr', 'cp949', 'iso-8859-1']
                
                for encoding in encoding_attempts:
                    try:
                        if encoding == 'utf-8':
                            # UTF-8로 잘못 해석된 경우 복구 시도
                            decoded = filename.encode('latin-1').decode('utf-8')
                        elif encoding == 'euc-kr' or encoding == 'cp949':
                            # EUC-KR/CP949 시도
                            decoded = filename.encode('latin-1').decode(encoding)
                        else:
                            decoded = filename
                        
                        # 유효한 한글 파일명인지 확인
                        if decoded and not decoded.isspace() and len(decoded.strip()) > 0:
                            clean_decoded = decoded.replace('+', ' ').strip()
                            # 한글이 포함되어 있거나 영문 파일명이 정상적으로 보이면 반환
                            if (any(ord(c) > 127 for c in clean_decoded) or 
                                (clean_decoded.isascii() and '.' in clean_decoded)):
                                logger.debug(f"{encoding} 인코딩으로 파일명 복구: {clean_decoded}")
                                return clean_decoded
                    except Exception as e:
                        logger.debug(f"{encoding} 인코딩 시도 실패: {e}")
                        continue
                        
                # 모든 인코딩 시도가 실패한 경우 원본 반환
                return filename.replace('+', ' ')
                
        except Exception as e:
            logger.debug(f"파일명 추출 실패: {e}")
            
        return None


def main():
    """메인 실행 함수"""
    scraper = EnhancedKeaScraper()
    
    try:
        # 3페이지까지 수집
        output_dir = "output/kea"
        os.makedirs(output_dir, exist_ok=True)
        
        result = scraper.scrape_pages(max_pages=3, output_base=output_dir)
        
        print(f"\n✅ KEA 스크래핑 완료!")
        print(f"수집된 공고: {result['total_announcements']}개")
        print(f"다운로드된 파일: {result['total_files']}개")
        print(f"성공률: {result['success_rate']:.1f}%")
        
    except Exception as e:
        print(f"❌ 스크래핑 실패: {e}")


if __name__ == "__main__":
    main()