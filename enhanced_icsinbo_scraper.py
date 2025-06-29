#!/usr/bin/env python3
"""
Enhanced ICSINBO (인천신용보증재단) 스크래퍼

인천신용보증재단 공지사항 게시판에서 공고를 수집하는 스크래퍼입니다.
JSON API 기반 동적 사이트와 JavaScript 함수 호출 방식을 처리합니다.

URL: https://www.icsinbo.or.kr/home/board/brdList.do?menu_cd=000096
"""

import os
import re
import time
import json
import logging
from typing import List, Dict, Any
from urllib.parse import urljoin, unquote
from bs4 import BeautifulSoup
from enhanced_base_scraper import EnhancedBaseScraper

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedIcsinboScraper(EnhancedBaseScraper):
    """ICSINBO 전용 Enhanced 스크래퍼 - JSON API 기반"""
    
    def __init__(self):
        super().__init__()
        
        # ICSINBO 사이트 설정
        self.base_url = "https://www.icsinbo.or.kr"
        self.list_url = "https://www.icsinbo.or.kr/home/board/brdList.do?menu_cd=000096"
        
        # 사이트별 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 2
        
        # ICSINBO 특화 설정
        self.menu_cd = "000096"
        self.page_size = 10  # 페이지당 공고 수
        
    def get_list_url(self, page_num: int) -> str:
        """페이지별 URL 생성 - ICSINBO는 JSON API 방식"""
        return f"{self.base_url}/home/board/brdList.do?menu_cd={self.menu_cd}&currentPageNo={page_num}"
    
    
    def _get_page_announcements(self, page_num: int) -> List[Dict[str, Any]]:
        """ICSINBO JSON API를 통한 공고 목록 가져오기"""
        try:
            logger.info(f"ICSINBO 페이지 {page_num} JSON API 호출")
            
            # JSON API URL 구성
            api_url = f"{self.base_url}/home/board/brdList.do"
            params = {
                'menu_cd': self.menu_cd,
                'currentPageNo': str(page_num),
                'recordCountPerPage': '10'
            }
            
            # JSON 요청
            response = self.session.get(api_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            # JSON 응답 파싱
            try:
                json_data = response.json()
                return self._parse_json_response(json_data)
            except (ValueError, json.JSONDecodeError):
                # HTML 응답인 경우 파싱 시도
                logger.warning("JSON 응답이 아님, HTML 파싱으로 전환")
                return self.parse_list_page(response.text)
                
        except Exception as e:
            logger.error(f"ICSINBO API 호출 실패: {e}")
            return []
    
    def _parse_json_response(self, json_data: dict) -> List[Dict[str, Any]]:
        """JSON 응답에서 공고 목록 추출"""
        announcements = []
        
        try:
            brd_list = json_data.get('brdList', [])
            logger.info(f"JSON에서 {len(brd_list)}개 공고 발견")
            
            for item in brd_list:
                announcement = {
                    'number': str(item.get('num', '')),
                    'title': item.get('title', '제목 없음'),
                    'author': item.get('username', 'ICSINBO'),
                    'date': item.get('write_dt', ''),
                    'views': str(item.get('cnt', '0')),
                    'has_attachments': item.get('att_file', 'N') == 'Y',
                    'url': f"{self.base_url}/home/board/brdDetail.do",
                    'is_notice': not str(item.get('num', '')).isdigit(),
                    'num': str(item.get('num', ''))  # POST 요청용 번호
                }
                
                announcements.append(announcement)
                logger.debug(f"JSON 공고 추가: [{announcement['number']}] {announcement['title']}")
            
        except Exception as e:
            logger.error(f"JSON 응답 파싱 중 오류: {e}")
        
        return announcements
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """HTML 페이지 파싱 (Fallback) - ul/li 구조"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        try:
            # ul 리스트 찾기
            list_container = soup.find('ul')
            if not list_container:
                logger.warning("ICSINBO 공고 목록을 찾을 수 없습니다")
                return announcements
            
            items = list_container.find_all('li')
            logger.info(f"ICSINBO 리스트에서 {len(items)}개 항목 발견")
            
            for item in items:
                try:
                    link = item.find('a')
                    if not link:
                        continue
                    
                    # JavaScript 함수에서 번호 추출
                    onclick = link.get('onclick', '')
                    num_match = re.search(r"pageviewform\('(\d+)'\)", onclick)
                    if not num_match:
                        continue
                    
                    announcement_num = num_match.group(1)
                    
                    # 제목 추출
                    title_p = item.find('p')
                    title = title_p.get_text(strip=True) if title_p else '제목 없음'
                    
                    # 메타 정보 추출
                    meta_spans = item.find_all('span')
                    author = meta_spans[0].get_text(strip=True) if len(meta_spans) > 0 else 'ICSINBO'
                    date = meta_spans[1].get_text(strip=True) if len(meta_spans) > 1 else ''
                    views = meta_spans[2].get_text(strip=True) if len(meta_spans) > 2 else '0'
                    
                    announcement = {
                        'number': announcement_num,
                        'title': title,
                        'author': author,
                        'date': date,
                        'views': views,
                        'url': f"{self.base_url}/home/board/brdDetail.do",
                        'has_attachments': False,  # HTML에서는 확인 어려움
                        'is_notice': not announcement_num.isdigit(),
                        'num': announcement_num
                    }
                    
                    announcements.append(announcement)
                    logger.debug(f"HTML 공고 추가: [{announcement_num}] {title}")
                    
                except Exception as e:
                    logger.error(f"리스트 항목 파싱 중 오류: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"HTML 파싱 중 오류: {e}")
        
        logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
        return announcements
    
    def get_page_content(self, url: str, announcement_data: dict = None) -> str:
        """ICSINBO 상세 페이지 POST 요청으로 가져오기"""
        try:
            if announcement_data and 'num' in announcement_data:
                # POST 요청으로 상세 페이지 JSON 데이터 가져오기
                post_data = {
                    'menu_cd': self.menu_cd,
                    'num': announcement_data['num']
                }
                
                # 필수 헤더 설정
                headers = {
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json, text/javascript, */*; q=0.01',
                    'Referer': self.list_url
                }
                
                logger.debug(f"ICSINBO 상세 페이지 POST 요청: num={post_data['num']}")
                
                response = self.session.post(url, data=post_data, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                
                return response.text
            else:
                # 일반 GET 요청
                return super().get_page_content(url)
                
        except Exception as e:
            logger.error(f"ICSINBO 페이지 가져오기 실패: {e}")
            raise
    
    
    
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱 - ICSINBO JSON 응답 처리"""
        try:
            # JSON 응답 파싱 시도
            json_data = json.loads(html_content)
            return self._parse_detail_json(json_data)
        except (ValueError, json.JSONDecodeError):
            # HTML 응답인 경우 기존 방식으로 파싱
            return self._parse_detail_html(html_content)
    
    def _parse_detail_json(self, json_data: dict) -> Dict[str, Any]:
        """JSON 응답에서 상세 페이지 정보 추출"""
        try:
            brd = json_data.get('brd', {})
            file_list = json_data.get('fileList', [])
            board_att_url = json_data.get('boardAttUrl', '')
            
            # 제목 추출
            title = brd.get('title', '제목 없음')
            
            # HTML 콘텐츠에서 텍스트 추출
            content_html = brd.get('cont', '')
            if content_html:
                soup = BeautifulSoup(content_html, 'html.parser')
                content_text = soup.get_text(separator='\n\n', strip=True)
            else:
                content_text = "본문 내용이 없습니다."
            
            # 메타 정보
            meta_info = {
                '작성자': brd.get('username', ''),
                '작성일': brd.get('write_dt', ''),
                '조회수': str(brd.get('cnt', '0'))
            }
            
            # 첨부파일 처리
            attachments = []
            for file_info in file_list:
                file_url = f"{self.base_url}{board_att_url}/{file_info.get('subpath', '')}/{file_info.get('file_save', '')}"
                
                attachment = {
                    'filename': file_info.get('file_org', 'unknown'),
                    'url': file_url,
                    'type': self._determine_file_type(file_info.get('file_org', ''), None),
                    'size': self._format_file_size(file_info.get('file_size', 0)),
                    'download_method': 'direct'
                }
                
                attachments.append(attachment)
            
            # 마크다운 형식으로 조합
            markdown_content = f"# {title}\n\n"
            
            for key, value in meta_info.items():
                if value:
                    markdown_content += f"**{key}**: {value}\n"
            markdown_content += "\n---\n\n"
            markdown_content += content_text
            
            return {
                'content': markdown_content,
                'attachments': attachments
            }
            
        except Exception as e:
            logger.error(f"JSON 상세 페이지 파싱 중 오류: {e}")
            return {
                'content': "상세 페이지를 파싱할 수 없습니다.",
                'attachments': []
            }
    
    def _parse_detail_html(self, html_content: str) -> Dict[str, Any]:
        """HTML 응답 파싱 (Fallback)"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출
        title = self._extract_title(soup)
        
        # 본문 내용 추출
        content_text = self._extract_main_content(soup)
        
        # 메타 정보 추출
        meta_info = self._extract_meta_info(soup)
        
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
    
    def _format_file_size(self, size_bytes: int) -> str:
        """파일 크기를 읽기 쉬운 형태로 변환"""
        if size_bytes == 0:
            return ""
        elif size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes/1024:.1f}KB"
        else:
            return f"{size_bytes/(1024*1024):.1f}MB"
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """ICSINBO 상세페이지에서 제목 추출"""
        # ICSINBO 상세페이지의 제목 구조 확인
        title_selectors = [
            '.view_title',
            '.board_title',
            'h1',
            'h2',
            'h3'
        ]
        
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                title_text = title_elem.get_text(strip=True)
                if title_text and len(title_text) > 5:
                    return title_text
        
        # 백업 방법: 페이지에서 가장 적절한 제목 후보 찾기
        title_candidates = []
        for elem in soup.find_all(['h1', 'h2', 'h3', 'strong', 'b']):
            text = elem.get_text(strip=True)
            if 10 < len(text) < 100:
                title_candidates.append(text)
        
        if title_candidates:
            return title_candidates[0]
        
        return "제목 없음"
    
    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """ICSINBO 사이트에서 본문 내용 추출"""
        
        # 1. 불필요한 요소들 제거
        unwanted_selectors = [
            'nav', 'header', 'footer', '.nav', '.navigation',
            '.menu', '.sidebar', '.breadcrumb',
            'script', 'style', '.ads', '.advertisement',
            '.btn-group', '.pagination', '.paging'
        ]
        
        for selector in unwanted_selectors:
            for elem in soup.select(selector):
                elem.decompose()
        
        # 2. ICSINBO 특화 콘텐츠 선택자
        content_selectors = [
            '.view_content',         # 뷰 콘텐츠
            '.board_content',        # 게시판 콘텐츠
            '.content_area',         # 콘텐츠 영역
            'article',               # article 태그
            '.article_content',      # 아티클 콘텐츠
            'main',                  # main 태그
            '[role="main"]'          # main 역할
        ]
        
        content_elem = None
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                logger.debug(f"콘텐츠 선택자 사용: {selector}")
                break
        
        if content_elem:
            # 추가 불필요한 요소 제거
            for unwanted in content_elem.select('.btn, .button, .file-list, .attach-list'):
                unwanted.decompose()
            
            # 본문 텍스트 추출
            content_text = self.simple_html_to_text(content_elem)
        else:
            # 백업 방법: div나 p 태그에서 가장 긴 텍스트 찾기
            content_candidates = []
            
            for elem in soup.find_all(['div', 'p', 'article', 'section']):
                text = elem.get_text(strip=True)
                if len(text) > 100:  # 최소 길이 조건
                    content_candidates.append(text)
            
            # 가장 긴 텍스트를 본문으로 선택
            if content_candidates:
                content_text = max(content_candidates, key=len)
            else:
                content_text = "본문 내용을 찾을 수 없습니다."
        
        return content_text.strip()
    
    def simple_html_to_text(self, element) -> str:
        """HTML 요소를 간단한 텍스트로 변환"""
        text = element.get_text(separator='\n\n', strip=True)
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text
    
    def _extract_meta_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """ICSINBO 사이트에서 메타 정보 추출"""
        meta_info = {}
        
        try:
            # ICSINBO 상세페이지의 메타 정보 테이블에서 추출
            meta_table = soup.find('table')
            if meta_table:
                rows = meta_table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    # 작성자, 작성일, 조회수가 포함된 행 찾기
                    for cell in cells:
                        cell_text = cell.get_text(strip=True)
                        
                        # 작성자 추출
                        if '작성자' in cell_text:
                            author_match = re.search(r'작성자:\s*(.+?)(?:\s|$)', cell_text)
                            if author_match:
                                meta_info['작성자'] = author_match.group(1)
                        
                        # 작성일 추출
                        if '작성일' in cell_text:
                            date_match = re.search(r'작성일:\s*(.+?)(?:\s|$)', cell_text)
                            if date_match:
                                meta_info['작성일'] = date_match.group(1)
                        
                        # 조회수 추출
                        if '조회수' in cell_text:
                            views_match = re.search(r'조회수:\s*(\d+)', cell_text)
                            if views_match:
                                meta_info['조회수'] = views_match.group(1)
            
            # 추가로 페이지 텍스트에서 패턴 찾기
            page_text = soup.get_text()
            
            # 날짜 패턴 찾기
            date_match = re.search(r'(\d{2}/\d{2}/\d{2})', page_text)
            if date_match and '작성일' not in meta_info:
                meta_info['작성일'] = date_match.group(1)
            
            # 조회수 패턴 찾기
            views_match = re.search(r'조회수?\s*:?\s*(\d+)', page_text)
            if views_match and '조회수' not in meta_info:
                meta_info['조회수'] = views_match.group(1)
            
        except Exception as e:
            logger.debug(f"메타 정보 추출 중 오류: {e}")
        
        return meta_info
    
    
    def collect_single_announcement(self, announcement: dict, output_base: str) -> dict:
        """ICSINBO 개별 공고 수집 - POST 요청 처리"""
        try:
            logger.info(f"공고 처리 중: {announcement['title']}")
            
            # 상세 페이지 가져오기 (POST 요청)
            detail_html = self.get_page_content(announcement['url'], announcement)
            
            # 상세 페이지 파싱
            detail_result = self.parse_detail_page(detail_html)
            
            # 공고 정보를 마크다운에 추가
            content = detail_result['content']
            
            # 메타 정보 추가
            meta_info = f"**작성일**: {announcement.get('date', '')}\n"
            meta_info += f"**조회수**: {announcement.get('views', '')}\n"
            meta_info += f"**원본 URL**: {announcement['url']}\n\n"
            
            # 최종 컨텐츠 구성
            title_line = content.split('\n')[0] if content else f"# {announcement['title']}"
            content_body = '\n'.join(content.split('\n')[1:]) if '\n' in content else content
            
            final_content = f"{title_line}\n\n{meta_info}---\n{content_body}"
            
            # 파일 저장 경로 생성
            safe_title = self.sanitize_filename(announcement['title'])
            announcement_dir = os.path.join(output_base, f"{announcement.get('number', 'unknown')}_{safe_title}")
            os.makedirs(announcement_dir, exist_ok=True)
            
            # 내용 저장
            content_file = os.path.join(announcement_dir, "content.md")
            with open(content_file, 'w', encoding='utf-8') as f:
                f.write(final_content)
            
            logger.info(f"내용 저장 완료: {content_file}")
            
            # 첨부파일 처리
            attachments = detail_result.get('attachments', [])
            downloaded_files = 0
            
            if attachments:
                logger.info(f"{len(attachments)}개 첨부파일 다운로드 시작")
                
                attachment_dir = os.path.join(announcement_dir, "attachments")
                os.makedirs(attachment_dir, exist_ok=True)
                
                for i, attachment in enumerate(attachments, 1):
                    logger.info(f"  첨부파일 {i}: {attachment.get('filename', 'unknown')}")
                    
                    # 파일 다운로드
                    filename = attachment.get('filename', f'attachment_{i}')
                    safe_filename = self.sanitize_filename(filename)
                    save_path = os.path.join(attachment_dir, safe_filename)
                    
                    if self.download_file(attachment['url'], save_path, attachment):
                        downloaded_files += 1
            else:
                logger.info("첨부파일이 없습니다")
            
            return {
                'success': True,
                'content_length': len(final_content),
                'attachments': attachments,
                'downloaded_files': downloaded_files
            }
            
        except Exception as e:
            logger.error(f"공고 수집 실패: {announcement['title']} - {e}")
            return {
                'success': False,
                'error': str(e),
                'attachments': [],
                'downloaded_files': 0
            }
    
    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """HTML에서 첨부파일 정보 추출 (Fallback)"""
        attachments = []
        
        # 첨부파일 링크 찾기
        download_links = soup.find_all('a', href=lambda x: x and ('fileDown' in x or 'download' in x))
        
        for link in download_links:
            try:
                href = link.get('href', '')
                filename = link.get_text(strip=True)
                
                if not filename:
                    filename = f"attachment_{len(attachments)+1}"
                
                file_url = urljoin(self.base_url, href)
                file_type = self._determine_file_type(filename, link)
                
                attachment = {
                    'filename': filename,
                    'url': file_url,
                    'type': file_type,
                    'size': "",
                    'download_method': 'direct'
                }
                
                attachments.append(attachment)
                
            except Exception as e:
                logger.error(f"첨부파일 처리 중 오류: {e}")
                continue
        
        return attachments
    
    def _determine_file_type(self, filename: str, link_elem) -> str:
        """파일 타입 결정"""
        if not filename:
            return 'unknown'
        
        filename_lower = filename.lower()
        
        if filename_lower.endswith('.pdf'):
            return 'pdf'
        elif filename_lower.endswith(('.hwp', '.hwpx')):
            return 'hwp'
        elif filename_lower.endswith(('.doc', '.docx')):
            return 'doc'
        elif filename_lower.endswith(('.xls', '.xlsx')):
            return 'excel'
        elif filename_lower.endswith(('.jpg', '.jpeg', '.png', '.gif')):
            return 'image'
        elif filename_lower.endswith('.zip'):
            return 'zip'
        else:
            return 'unknown'
    
    def download_file(self, file_url: str, save_path: str, attachment_info: dict = None) -> bool:
        """파일 다운로드 - ICSINBO 특화 처리 (개선된 버전)"""
        try:
            logger.info(f"파일 다운로드 시작: {file_url}")
            
            # 1단계: 기본 헤더로 시도
            success = self._try_basic_download(file_url, save_path)
            if success:
                return True
            
            # 2단계: 브라우저 헤더 모방으로 시도
            success = self._try_browser_headers_download(file_url, save_path)
            if success:
                return True
            
            logger.error(f"모든 다운로드 방법 실패: {file_url}")
            return False
            
        except Exception as e:
            logger.error(f"파일 다운로드 중 예외 발생: {e}")
            return False
    
    def _try_basic_download(self, file_url: str, save_path: str) -> bool:
        """기본 다운로드 시도"""
        try:
            logger.info(f"기본 다운로드 시도: {file_url}")
            response = self.session.get(file_url, stream=True, timeout=self.timeout)
            response.raise_for_status()
            return self._save_file_from_response(response, save_path)
        except Exception as e:
            logger.debug(f"기본 다운로드 실패: {e}")
            return False
    
    def _try_browser_headers_download(self, file_url: str, save_path: str) -> bool:
        """브라우저 헤더 모방 다운로드 시도"""
        try:
            logger.info(f"브라우저 헤더 모방 다운로드 시도: {file_url}")
            
            # 실제 브라우저와 유사한 헤더 설정
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
                'Referer': self.list_url
            }
            
            response = self.session.get(file_url, headers=headers, stream=True, timeout=self.timeout)
            response.raise_for_status()
            return self._save_file_from_response(response, save_path)
        except Exception as e:
            logger.debug(f"브라우저 헤더 다운로드 실패: {e}")
            return False
    
    def _save_file_from_response(self, response, save_path: str) -> bool:
        """응답에서 파일 저장"""
        try:
            # Content-Disposition에서 파일명 추출 시도
            content_disposition = response.headers.get('Content-Disposition', '')
            if content_disposition:
                extracted_filename = self._extract_filename_from_disposition(content_disposition)
                if extracted_filename:
                    # 디렉토리는 유지하고 파일명만 변경
                    directory = os.path.dirname(save_path)
                    save_path = os.path.join(directory, self.sanitize_filename(extracted_filename))
            
            # 파일 저장
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(save_path)
            logger.info(f"파일 다운로드 완료: {os.path.basename(save_path)} ({file_size:,} bytes)")
            
            return True
            
        except Exception as e:
            logger.debug(f"파일 저장 실패: {e}")
            return False
    
    def _extract_filename_from_disposition(self, content_disposition: str) -> str:
        """Content-Disposition 헤더에서 파일명 추출"""
        try:
            # RFC 5987 형식 처리
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
                
                # 다양한 인코딩 시도
                for encoding in ['utf-8', 'euc-kr', 'cp949']:
                    try:
                        if encoding == 'utf-8':
                            decoded = filename.encode('latin-1').decode('utf-8')
                        else:
                            decoded = filename.encode('latin-1').decode(encoding)
                        
                        if decoded and not decoded.isspace():
                            return decoded.replace('+', ' ').strip()
                    except:
                        continue
                        
                return filename.replace('+', ' ')
                
        except Exception as e:
            logger.debug(f"파일명 추출 실패: {e}")
            
        return None


def main():
    """테스트 실행"""
    output_dir = "output/icsinbo"
    os.makedirs(output_dir, exist_ok=True)
    
    scraper = EnhancedIcsinboScraper()
    
    try:
        result = scraper.scrape_pages(max_pages=3, output_base=output_dir)
        print(f"✅ ICSINBO 스크래핑 완료!")
        
        # scrape_pages 메서드가 dict를 반환하는지 확인
        if isinstance(result, dict):
            print(f"수집된 공고: {result.get('total_announcements', 0)}개")
            print(f"다운로드된 파일: {result.get('total_files', 0)}개")
            print(f"성공률: {result.get('success_rate', 0):.1f}%")
        else:
            print(f"스크래핑 결과: {result}")
        
    except Exception as e:
        print(f"❌ 스크래핑 실패: {e}")
        raise


if __name__ == "__main__":
    main()