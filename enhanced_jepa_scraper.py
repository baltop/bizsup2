#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced JEPA 스크래퍼 - 전라남도경제진흥원 자금지원 공지사항 수집
URL: https://www.jepa.kr/bbs/?b_id=notice&site=new_jepa&mn=322&sc_category=자금지원

전라남도경제진흥원의 자금지원 공지사항을 수집하는 스크래퍼입니다.
"""

import os
import re
import time
import logging
import json
from typing import List, Dict, Any
from urllib.parse import urljoin, urlparse, parse_qs, quote
from bs4 import BeautifulSoup
import requests
from enhanced_base_scraper import EnhancedBaseScraper

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('enhanced_jepa_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class EnhancedJEPAScraper(EnhancedBaseScraper):
    """전라남도경제진흥원 자금지원 공지사항 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.jepa.kr"
        self.list_url = "https://www.jepa.kr/bbs/?b_id=notice&site=new_jepa&mn=322&sc_category=%EC%9E%90%EA%B8%88%EC%A7%80%EC%9B%90"
        
        # JEPA 특화 설정
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://www.jepa.kr/'
        })
        
        # 사이트 특화 설정
        self.verify_ssl = True
        self.timeout = 30
        self.delay_between_requests = 2
        self.delay_between_pages = 3
        
    def get_list_url(self, page_num: int) -> str:
        """페이지별 URL 생성"""
        # JEPA 사이트는 AJAX로 콘텐츠 로드 (한글 URL 인코딩 적용)
        ajax_base = "https://www.jepa.kr/bbs/bbs_ajax/?b_id=notice&site=new_jepa&mn=322&sc_category=%EC%9E%90%EA%B8%88%EC%A7%80%EC%9B%90"
        
        if page_num == 1:
            return ajax_base
        
        # 페이지 2부터는 offset 파라미터 사용
        offset = (page_num - 1) * 15
        return f"{ajax_base}&offset={offset}&page={page_num}"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        try:
            # 공지사항 게시판 테이블 찾기
            notice_table = soup.find('table', caption=lambda text: text and '공지사항' in text)
            if not notice_table:
                # 대안으로 테이블 찾기
                notice_table = soup.find('table')
            
            if not notice_table:
                logger.warning("공지사항 테이블을 찾을 수 없습니다.")
                return announcements
            
            # 테이블 본문에서 공지사항 행 찾기
            tbody = notice_table.find('tbody')
            if not tbody:
                tbody = notice_table
            
            rows = tbody.find_all('tr')
            logger.info(f"테이블에서 {len(rows)}개 행 발견")
            
            for row in rows:
                try:
                    announcement = self._parse_notice_row(row)
                    if announcement:
                        announcements.append(announcement)
                except Exception as e:
                    logger.error(f"공지사항 행 파싱 중 오류: {e}")
                    continue
            
            logger.info(f"총 {len(announcements)}개 공지사항 발견")
            return announcements
            
        except Exception as e:
            logger.error(f"목록 페이지 파싱 중 오류: {e}")
            return announcements
    
    def _parse_notice_row(self, row) -> Dict[str, Any]:
        """개별 공지사항 행 파싱"""
        try:
            cells = row.find_all('td')
            if len(cells) < 5:  # 최소 필요한 열 수 확인
                return None
            
            # 번호 (첫 번째 열)
            number_cell = cells[0]
            number_text = number_cell.get_text(strip=True)
            
            # 제목 (두 번째 열)
            title_cell = cells[1]
            title_link = title_cell.find('a')
            if not title_link:
                return None
            
            title = title_link.get_text(strip=True)
            link_href = title_link.get('href', '')
            
            # 절대 URL로 변환
            if link_href.startswith('/'):
                full_url = urljoin(self.base_url, link_href)
            elif not link_href.startswith('http'):
                full_url = urljoin(self.base_url, link_href)
            else:
                full_url = link_href
            
            # bs_idx 추출
            bs_idx = self._extract_bs_idx(link_href)
            
            # 작성자 (세 번째 열)
            author = cells[2].get_text(strip=True) if len(cells) > 2 else ""
            
            # 등록일 (네 번째 열)
            date = cells[3].get_text(strip=True) if len(cells) > 3 else ""
            
            # 첨부파일 여부 (다섯 번째 열)
            attachment_cell = cells[4] if len(cells) > 4 else None
            has_attachments = False
            if attachment_cell:
                attachment_img = attachment_cell.find('img')
                if attachment_img and '첨부파일' in attachment_img.get('alt', ''):
                    has_attachments = True
            
            # 조회수 (여섯 번째 열)
            views = cells[5].get_text(strip=True) if len(cells) > 5 else ""
            
            # 진행상태 (일곱 번째 열)
            status = cells[6].get_text(strip=True) if len(cells) > 6 else ""
            
            return {
                'number': number_text,
                'title': title,
                'url': full_url,
                'bs_idx': bs_idx,
                'author': author,
                'date': date,
                'has_attachments': has_attachments,
                'views': views,
                'status': status
            }
            
        except Exception as e:
            logger.error(f"공지사항 행 파싱 중 오류: {e}")
            return None
    
    def _extract_bs_idx(self, url: str) -> str:
        """URL에서 bs_idx 파라미터 추출"""
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            return params.get('bs_idx', [''])[0]
        except:
            return ""
    
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        try:
            # 제목 추출
            title = self._extract_detail_title(soup)
            
            # 본문 내용 추출
            content = self._extract_main_content(soup)
            
            # 첨부파일 추출
            attachments = self._extract_attachments(soup)
            
            # 메타 정보 추출
            meta_info = self._extract_meta_info(soup)
            
            # 마크다운 형식으로 조합
            markdown_content = f"# {title}\n\n"
            markdown_content += f"**수집 시점**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            # 메타 정보 추가
            if meta_info:
                markdown_content += "## 공지사항 정보\n\n"
                for key, value in meta_info.items():
                    markdown_content += f"- **{key}**: {value}\n"
                markdown_content += "\n"
            
            markdown_content += "---\n\n"
            markdown_content += content
            
            return {
                'content': markdown_content,
                'attachments': attachments
            }
            
        except Exception as e:
            logger.error(f"상세 페이지 파싱 중 오류: {e}")
            return {
                'content': f"# 파싱 오류\n\n상세 페이지 파싱 중 오류가 발생했습니다: {e}",
                'attachments': []
            }
    
    def _extract_detail_title(self, soup) -> str:
        """상세 페이지 제목 추출"""
        # 다양한 제목 셀렉터 시도
        title_selectors = [
            'h1', 'h2', 'h3', 'h4',
            '.title', '.subject', '.board_title',
            'title'
        ]
        
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                title = title_elem.get_text(strip=True)
                if title and len(title) > 3 and '공지사항' not in title:
                    return title
        
        # 페이지 제목에서 추출
        page_title = soup.find('title')
        if page_title:
            title = page_title.get_text(strip=True)
            if '>' in title:
                return title.split('>')[-1].strip()
        
        return "제목 없음"
    
    def _extract_main_content(self, soup) -> str:
        """상세 페이지 본문 추출"""
        try:
            # JEPA 사이트의 게시판 구조에 맞는 본문 추출
            content_selectors = [
                '.board_content',
                '.bbs_content', 
                '.content',
                '.view_content',
                '.board_view_content'
            ]
            
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    # 불필요한 요소 제거
                    for unwanted in content_elem.find_all(['script', 'style', 'nav', 'footer', 'header']):
                        unwanted.decompose()
                    
                    # 텍스트 추출 및 정리
                    text = content_elem.get_text(separator='\n', strip=True)
                    if text and len(text) > 50:
                        return self._clean_content(text)
            
            # 테이블 기반 내용 추출
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    for cell in cells:
                        cell_text = cell.get_text(strip=True)
                        if len(cell_text) > 100:  # 충분한 길이의 내용
                            return self._clean_content(cell_text)
            
            # 기본 콘텐츠 추출
            return self._extract_basic_content(soup)
            
        except Exception as e:
            logger.error(f"본문 추출 중 오류: {e}")
            return self._extract_basic_content(soup)
    
    def _extract_basic_content(self, soup) -> str:
        """기본 콘텐츠 추출"""
        try:
            # 페이지 전체 텍스트에서 의미있는 내용 추출
            main_text = soup.get_text(separator='\n', strip=True)
            lines = main_text.split('\n')
            
            # 필터링: 네비게이션, 메뉴 등 제거
            meaningful_lines = []
            skip_keywords = [
                '로그인', '회원가입', '사이트맵', '검색', '메뉴', '홈',
                '개인정보처리방침', '저작권', 'Copyright', '전체메뉴',
                '바로가기', '관련사이트', '만족도', '평가'
            ]
            
            for line in lines:
                line = line.strip()
                if len(line) > 10 and not any(keyword in line for keyword in skip_keywords):
                    meaningful_lines.append(line)
            
            # 중복 제거
            seen = set()
            unique_lines = []
            for line in meaningful_lines:
                if line not in seen:
                    seen.add(line)
                    unique_lines.append(line)
            
            content = '\n\n'.join(unique_lines[:20])  # 처음 20줄만
            
            if not content:
                content = "본문 내용을 추출할 수 없습니다."
            
            return content
            
        except Exception as e:
            logger.error(f"기본 콘텐츠 추출 중 오류: {e}")
            return "본문 내용을 추출할 수 없습니다."
    
    def _extract_meta_info(self, soup) -> Dict[str, str]:
        """메타 정보 추출"""
        meta_info = {}
        
        try:
            # 테이블에서 메타 정보 추출
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        key = cells[0].get_text(strip=True)
                        value = cells[1].get_text(strip=True)
                        
                        # 유용한 메타 정보만 추출
                        if any(keyword in key for keyword in ['작성자', '등록일', '조회', '신청기간', '접수기간']):
                            meta_info[key] = value
            
            return meta_info
            
        except Exception as e:
            logger.error(f"메타 정보 추출 중 오류: {e}")
            return {}
    
    def _clean_content(self, text: str) -> str:
        """콘텐츠 정리"""
        # 연속된 공백 제거
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        
        # 불필요한 문자 제거
        text = re.sub(r'[^\w\s\n\-\.\,\(\)\[\]\{\}\:\;\!\?\"\'\`\~\@\#\$\%\^\&\*\+\=\|\\\/\<\>]', '', text)
        
        return text.strip()
    
    def _extract_attachments(self, soup) -> List[Dict[str, Any]]:
        """첨부파일 추출"""
        attachments = []
        
        try:
            # JEPA 사이트의 실제 다운로드 링크 패턴 찾기
            # 패턴: /bbs/bbs_ajax/?...&type=download&...&bf_idx=...
            download_links = soup.find_all('a', href=lambda x: x and 'type=download' in str(x) and 'bf_idx=' in str(x))
            
            logger.info(f"다운로드 링크 {len(download_links)}개 발견")
            
            for link in download_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                # 파일명 추출 (링크 텍스트에서)
                filename = text if text and text != '' else "첨부파일"
                
                # 절대 URL로 변환
                if href.startswith('/'):
                    full_url = urljoin(self.base_url, href)
                elif not href.startswith('http'):
                    full_url = urljoin(self.base_url, href)
                else:
                    full_url = href
                
                # bf_idx 추출
                bf_idx = self._extract_bf_idx(href)
                
                logger.info(f"첨부파일 발견: {filename} | bf_idx: {bf_idx}")
                
                attachments.append({
                    'filename': filename,
                    'url': full_url,
                    'bf_idx': bf_idx,
                    'type': self._get_file_type(filename)
                })
            
            # 만약 위 방법으로 찾지 못했다면 대안 방법 시도
            if not attachments:
                logger.info("기본 다운로드 링크 방식으로 첨부파일을 찾을 수 없음, 대안 방법 시도")
                
                # 일반적인 파일 확장자 링크 찾기
                file_extensions = ['.pdf', '.hwp', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.rar']
                for link in soup.find_all('a', href=True):
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    
                    if any(ext in href.lower() or ext in text.lower() for ext in file_extensions):
                        filename = text if text else os.path.basename(href)
                        
                        if href.startswith('/'):
                            full_url = urljoin(self.base_url, href)
                        elif not href.startswith('http'):
                            full_url = urljoin(self.base_url, href)
                        else:
                            full_url = href
                        
                        attachments.append({
                            'filename': filename,
                            'url': full_url,
                            'bf_idx': '',
                            'type': self._get_file_type(filename)
                        })
        
        except Exception as e:
            logger.error(f"첨부파일 추출 중 오류: {e}")
        
        return attachments
    
    def _extract_bf_idx(self, url: str) -> str:
        """URL에서 bf_idx 파라미터 추출"""
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            return params.get('bf_idx', [''])[0]
        except:
            return ""
    
    def _get_file_type(self, filename: str) -> str:
        """파일 타입 결정"""
        ext = os.path.splitext(filename.lower())[1]
        type_map = {
            '.pdf': 'pdf',
            '.hwp': 'hwp',
            '.doc': 'doc',
            '.docx': 'docx',
            '.xls': 'xls',
            '.xlsx': 'xlsx',
            '.ppt': 'ppt',
            '.pptx': 'pptx',
            '.zip': 'zip',
            '.rar': 'rar'
        }
        return type_map.get(ext, 'unknown')
    
    def scrape_pages(self, max_pages: int = 3, output_base: str = "output/jepa") -> bool:
        """JEPA 자금지원 공지사항 수집"""
        try:
            logger.info("=== JEPA 자금지원 공지사항 수집 시작 ===")
            
            # 출력 디렉토리 생성
            os.makedirs(output_base, exist_ok=True)
            
            all_announcements = []
            processed_titles = []
            
            for page_num in range(1, max_pages + 1):
                logger.info(f"페이지 {page_num} 처리 중")
                
                try:
                    # 페이지 URL 생성
                    page_url = self.get_list_url(page_num)
                    logger.info(f"페이지 URL: {page_url}")
                    
                    # AJAX 요청 헤더 설정
                    ajax_headers = {
                        'X-Requested-With': 'XMLHttpRequest',
                        'Accept': 'text/html, */*; q=0.01',
                        'Referer': self.list_url
                    }
                    
                    # 페이지 요청 (재시도 로직 추가)
                    max_retries = 3
                    for retry in range(max_retries):
                        try:
                            response = self.session.get(page_url, headers=ajax_headers, timeout=self.timeout, verify=self.verify_ssl)
                            if response.status_code == 200:
                                break
                        except Exception as e:
                            logger.warning(f"페이지 {page_num} 요청 재시도 {retry + 1}/{max_retries}: {e}")
                            if retry == max_retries - 1:
                                logger.error(f"페이지 {page_num} 접근 실패: 최대 재시도 횟수 초과")
                                continue
                            time.sleep(2)
                    
                    if response.status_code != 200:
                        logger.error(f"페이지 {page_num} 접근 실패: {response.status_code}")
                        continue
                    
                    # 페이지 파싱
                    announcements = self.parse_list_page(response.text)
                    
                    if announcements:
                        logger.info(f"페이지 {page_num}에서 {len(announcements)}개 공지사항 발견")
                        all_announcements.extend(announcements)
                        
                        # 각 공지사항 상세 처리
                        for i, announcement in enumerate(announcements, 1):
                            try:
                                # 안전한 파일명 생성
                                safe_title = re.sub(r'[^\w\-_\. ]', '_', announcement['title'])
                                safe_title = safe_title.replace(' ', '_')[:100]
                                
                                # 디렉토리 생성
                                item_dir = os.path.join(output_base, f"{announcement.get('number', str(len(all_announcements) - len(announcements) + i)).zfill(3)}_{safe_title}")
                                os.makedirs(item_dir, exist_ok=True)
                                
                                # 상세 페이지 요청
                                try:
                                    detail_response = self.session.get(announcement['url'], timeout=self.timeout)
                                    
                                    if detail_response.status_code == 200:
                                        # 상세 페이지 파싱
                                        detail_data = self.parse_detail_page(detail_response.text)
                                        
                                        # 콘텐츠 파일 저장
                                        content_file = os.path.join(item_dir, "content.md")
                                        with open(content_file, 'w', encoding='utf-8') as f:
                                            f.write(detail_data['content'])
                                        
                                        # 첨부파일 다운로드
                                        if detail_data.get('attachments'):
                                            attachments_dir = os.path.join(item_dir, "attachments")
                                            os.makedirs(attachments_dir, exist_ok=True)
                                            
                                            # 첨부파일 목록 저장
                                            attachment_list_file = os.path.join(attachments_dir, "attachment_list.txt")
                                            with open(attachment_list_file, 'w', encoding='utf-8') as f:
                                                for attachment in detail_data['attachments']:
                                                    f.write(f"파일명: {attachment['filename']}\n")
                                                    f.write(f"URL: {attachment['url']}\n")
                                                    f.write(f"유형: {attachment['type']}\n")
                                                    f.write(f"bf_idx: {attachment.get('bf_idx', 'N/A')}\n")
                                                    f.write("-" * 50 + "\n")
                                            
                                            # 실제 파일 다운로드 시도
                                            for attachment in detail_data['attachments']:
                                                try:
                                                    # 파일 경로 생성
                                                    safe_filename = self.sanitize_filename(attachment['filename'])
                                                    file_path = os.path.join(attachments_dir, safe_filename)
                                                    
                                                    success = self.download_file(attachment['url'], file_path, attachment)
                                                    if success:
                                                        logger.info(f"첨부파일 다운로드 성공: {safe_filename}")
                                                    else:
                                                        logger.warning(f"첨부파일 다운로드 실패: {safe_filename}")
                                                except Exception as e:
                                                    logger.error(f"첨부파일 다운로드 실패: {e}")
                                            
                                            logger.info(f"첨부파일 정보 저장 완료: {len(detail_data['attachments'])}개")
                                        
                                        # 처리된 제목 리스트에 추가
                                        processed_titles.append({
                                            'title': announcement['title'],
                                            'url': announcement['url'],
                                            'number': announcement.get('number', ''),
                                            'date': announcement.get('date', ''),
                                            'processed_at': time.strftime('%Y-%m-%d %H:%M:%S')
                                        })
                                        
                                        logger.info(f"공지사항 {i} 처리 완료: {announcement['title']}")
                                    else:
                                        logger.error(f"상세 페이지 접근 실패: {announcement['url']}")
                                        
                                except Exception as e:
                                    logger.error(f"상세 페이지 처리 중 오류: {e}")
                                    continue
                                
                                time.sleep(self.delay_between_requests)
                                
                            except Exception as e:
                                logger.error(f"공지사항 {i} 처리 중 오류: {e}")
                                continue
                    else:
                        logger.warning(f"페이지 {page_num}에서 공지사항을 찾을 수 없음")
                    
                except Exception as e:
                    logger.error(f"페이지 {page_num} 처리 중 오류: {e}")
                    continue
                
                if page_num < max_pages:
                    time.sleep(self.delay_between_pages)
            
            logger.info(f"총 {len(all_announcements)}개 공지사항 수집 완료")
            logger.info(f"저장 위치: {output_base}")
            
            # 처리된 제목들을 JSON 파일로 저장
            json_file = os.path.join(output_base, "processed_titles_enhancedjepa.json")
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(processed_titles, f, ensure_ascii=False, indent=2)
            logger.info(f"처리된 제목 목록 저장: {json_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"수집 중 오류 발생: {e}")
            return False


def main():
    """메인 실행 함수"""
    # 출력 디렉토리 설정
    output_dir = "output/jepa"
    
    # 스크래퍼 생성
    scraper = EnhancedJEPAScraper()
    
    try:
        logger.info("=== JEPA 자금지원 공지사항 수집 시작 ===")
        
        # 3페이지까지 수집
        success = scraper.scrape_pages(max_pages=3, output_base=output_dir)
        
        if success:
            logger.info("✅ JEPA 자금지원 공지사항 수집 완료!")
            logger.info(f"저장 위치: {output_dir}")
            
            # 한국어 파일명 및 파일 크기 확인
            if os.path.exists(output_dir):
                for item in os.listdir(output_dir):
                    item_path = os.path.join(output_dir, item)
                    if os.path.isdir(item_path):
                        logger.info(f"생성된 폴더: {item}")
                        
                        # 콘텐츠 파일 크기 확인
                        content_file = os.path.join(item_path, "content.md")
                        if os.path.exists(content_file):
                            size = os.path.getsize(content_file)
                            logger.info(f"  콘텐츠 파일: content.md ({size} bytes)")
                        
                        # 첨부파일 확인
                        attachments_dir = os.path.join(item_path, "attachments")
                        if os.path.exists(attachments_dir):
                            for attachment in os.listdir(attachments_dir):
                                attachment_path = os.path.join(attachments_dir, attachment)
                                if os.path.isfile(attachment_path):
                                    size = os.path.getsize(attachment_path)
                                    logger.info(f"  첨부파일: {attachment} ({size} bytes)")
        else:
            logger.error("❌ 수집 실패")
            
    except Exception as e:
        logger.error(f"수집 중 오류 발생: {e}")
        raise


if __name__ == "__main__":
    main()