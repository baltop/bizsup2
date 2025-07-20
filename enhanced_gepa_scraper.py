#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced GEPA 스크래퍼 - 경상북도경제진흥원 지원사업 공고 수집
URL: https://www.gepa.kr/?page_id=36

경상북도경제진흥원의 지원사업 공고를 수집하는 스크래퍼입니다.
"""

import os
import re
import time
import logging
from typing import List, Dict, Any
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup
import requests
from enhanced_base_scraper import EnhancedBaseScraper

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('enhanced_gepa_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class EnhancedGEPAScraper(EnhancedBaseScraper):
    """경상북도경제진흥원 지원사업 공고 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.gepa.kr"
        self.list_url = "https://www.gepa.kr/?page_id=36"
        
        # GEPA 특화 설정
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # 사이트 특화 설정
        self.verify_ssl = True
        self.timeout = 30
        self.delay_between_requests = 1
        self.delay_between_pages = 2
        
    def get_list_url(self, page_num: int) -> str:
        """페이지별 URL 생성"""
        if page_num == 1:
            return self.list_url
        return f"{self.list_url}&mode=list&board_page={page_num}&stype1=type1"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        try:
            # GEPA 사이트의 실제 공고 구조 파싱
            # vid= 파라미터가 있는 링크들을 찾기 (실제 공고들)
            announcement_links = soup.find_all('a', href=lambda x: x and 'vid=' in str(x))
            
            logger.info(f"vid 파라미터가 있는 공고 링크 {len(announcement_links)}개 발견")
            
            # 중복 제거를 위한 집합
            processed_vids = set()
            
            for link in announcement_links:
                try:
                    href = link.get('href', '')
                    
                    # vid 파라미터 추출
                    vid_match = re.search(r'vid=(\d+)', href)
                    if not vid_match:
                        continue
                    
                    vid = vid_match.group(1)
                    if vid in processed_vids:
                        continue
                    
                    processed_vids.add(vid)
                    
                    # 공고 정보 추출
                    announcement = self._parse_gepa_announcement(link)
                    if announcement:
                        announcements.append(announcement)
                        
                except Exception as e:
                    logger.error(f"공고 링크 파싱 중 오류: {e}")
                    continue
            
            logger.info(f"총 {len(announcements)}개 유효한 공고 발견")
            return announcements
            
        except Exception as e:
            logger.error(f"목록 페이지 파싱 중 오류: {e}")
            return announcements
    
    def _parse_gepa_announcement(self, link_element) -> Dict[str, Any]:
        """GEPA 공고 항목 파싱"""
        try:
            href = link_element.get('href', '')
            
            # 절대 URL로 변환
            if href.startswith('/'):
                full_url = urljoin(self.base_url, href)
            elif not href.startswith('http'):
                full_url = urljoin(self.base_url, href)
            else:
                full_url = href
            
            # 제목 추출
            title = link_element.get_text(strip=True)
            if not title or len(title) < 3:
                return None
            
            # 상위 요소에서 추가 정보 찾기
            parent = link_element.parent
            while parent and parent.name != 'body':
                # 카테고리 추출
                category_elem = parent.find(string=lambda text: text and any(cat in text for cat in ['자금경영지원', '마케팅지원', '일자리지원', '글로벌강소기업육성', '소상공인지원', '산업유산', '기타']))
                if category_elem:
                    category = category_elem.strip()
                    break
                parent = parent.parent
            else:
                category = '일반'
            
            # 상태 추출
            status_elem = link_element.find_next(string=lambda text: text and any(status in text for status in ['준비중', '진행중', '종료']))
            if status_elem:
                status = status_elem.strip()
            else:
                status = '진행중'
            
            # 날짜 추출 (형식: 2025-07-18 ~ 2025-10-31)
            date_elem = link_element.find_next(string=lambda text: text and re.search(r'\d{4}-\d{2}-\d{2}', text))
            if date_elem:
                date = date_elem.strip()
            else:
                date = time.strftime('%Y-%m-%d')
            
            return {
                'title': title,
                'url': full_url,
                'date': date,
                'category': category,
                'status': status,
                'has_attachments': False
            }
            
        except Exception as e:
            logger.error(f"GEPA 공고 파싱 중 오류: {e}")
            return None
    
    def _parse_announcement_item(self, post_element) -> Dict[str, Any]:
        """개별 공고 항목 파싱"""
        try:
            # 제목 찾기
            title = self._extract_title(post_element)
            if not title:
                return None
            
            # 링크 찾기
            link = self._extract_link(post_element)
            if not link:
                return None
            
            # 절대 URL로 변환
            if link.startswith('/'):
                link = urljoin(self.base_url, link)
            elif not link.startswith('http'):
                link = urljoin(self.base_url, link)
            
            # 날짜 찾기
            date = self._extract_date(post_element)
            
            # 카테고리 찾기
            category = self._extract_category(post_element)
            
            # 상태 찾기 (진행중, 종료, 준비중 등)
            status = self._extract_status(post_element)
            
            return {
                'title': title,
                'url': link,
                'date': date,
                'category': category,
                'status': status,
                'has_attachments': False  # 상세 페이지에서 확인
            }
            
        except Exception as e:
            logger.error(f"공고 항목 파싱 중 오류: {e}")
            return None
    
    def _extract_title(self, element) -> str:
        """제목 추출"""
        # 다양한 제목 셀렉터 시도
        title_selectors = [
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            '.title', '.subject', '.post-title', '.entry-title',
            'a[title]', 'a'
        ]
        
        for selector in title_selectors:
            title_elem = element.select_one(selector)
            if title_elem:
                title = title_elem.get_text(strip=True)
                if title and len(title) > 3:  # 최소 길이 체크
                    return title
                
                # title 속성 체크
                if title_elem.get('title'):
                    return title_elem.get('title').strip()
        
        return None
    
    def _extract_link(self, element) -> str:
        """링크 추출"""
        # 링크 찾기
        link_elem = element.find('a', href=True)
        if link_elem:
            return link_elem['href']
        
        return None
    
    def _extract_date(self, element) -> str:
        """날짜 추출"""
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',
            r'\d{4}\.\d{2}\.\d{2}',
            r'\d{4}/\d{2}/\d{2}',
            r'\d{2}-\d{2}-\d{4}',
            r'\d{2}\.\d{2}\.\d{4}',
            r'\d{2}/\d{2}/\d{4}'
        ]
        
        text = element.get_text()
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group()
        
        return time.strftime('%Y-%m-%d')
    
    def _extract_category(self, element) -> str:
        """카테고리 추출"""
        # 카테고리 키워드 찾기
        category_keywords = [
            '자금경영지원', '마케팅지원', '일자리지원', 
            '글로벌강소기업육성', '소상공인지원', '기타지원'
        ]
        
        text = element.get_text()
        for keyword in category_keywords:
            if keyword in text:
                return keyword
        
        return '일반'
    
    def _extract_status(self, element) -> str:
        """상태 추출"""
        status_keywords = {
            '진행중': '진행중',
            '종료': '종료',
            '준비중': '준비중',
            '접수중': '진행중',
            '마감': '종료'
        }
        
        text = element.get_text()
        for keyword, status in status_keywords.items():
            if keyword in text:
                return status
        
        return '진행중'
    
    def _extract_links_as_announcements(self, soup) -> List[Dict[str, Any]]:
        """페이지의 모든 링크를 공고로 간주하여 추출"""
        announcements = []
        
        # vid 파라미터가 있는 링크들을 찾기 (GEPA 사이트 특성)
        links = soup.find_all('a', href=True)
        
        for link in links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # vid 파라미터가 있거나 의미있는 텍스트가 있는 링크만 선택
            if ('vid=' in href or 'page_id=36' in href) and text and len(text) > 5:
                try:
                    # 절대 URL로 변환
                    if href.startswith('/'):
                        full_url = urljoin(self.base_url, href)
                    elif not href.startswith('http'):
                        full_url = urljoin(self.base_url, href)
                    else:
                        full_url = href
                    
                    announcements.append({
                        'title': text,
                        'url': full_url,
                        'date': time.strftime('%Y-%m-%d'),
                        'category': '지원사업',
                        'status': '진행중',
                        'has_attachments': False
                    })
                except Exception as e:
                    logger.error(f"링크 처리 중 오류: {e}")
                    continue
        
        return announcements
    
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출
        title = self._extract_detail_title(soup)
        
        # 본문 내용 추출
        content = self._extract_main_content(soup)
        
        # 첨부파일 추출
        attachments = self._extract_attachments(soup)
        
        # 마크다운 형식으로 조합
        markdown_content = f"# {title}\n\n"
        markdown_content += f"**수집 시점**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        markdown_content += "---\n\n"
        markdown_content += content
        
        return {
            'content': markdown_content,
            'attachments': attachments
        }
    
    def _extract_detail_title(self, soup) -> str:
        """상세 페이지 제목 추출"""
        # 제목 셀렉터들
        title_selectors = [
            'h1', 'h2', 'h3', 
            '.post-title', '.entry-title', '.title',
            'title'
        ]
        
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                title = title_elem.get_text(strip=True)
                if title and len(title) > 3:
                    return title
        
        return "제목 없음"
    
    def _extract_main_content(self, soup) -> str:
        """상세 페이지 본문 추출"""
        try:
            # GEPA 사이트의 공고 테이블 구조 파싱
            content_table = soup.find('table', {'class': lambda x: x and '글보기' in str(x)})
            if not content_table:
                content_table = soup.find('table')
            
            if content_table:
                content_parts = []
                
                # 테이블 행들을 순회하며 내용 추출
                rows = content_table.find_all('tr')
                
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    for cell in cells:
                        cell_text = cell.get_text(strip=True)
                        
                        # 제목 추출
                        if any(keyword in cell_text for keyword in ['공고', '모집', '지원', '사업']) and len(cell_text) > 10:
                            if not any(part.startswith('# ') for part in content_parts):
                                content_parts.append(f"# {cell_text}")
                        
                        # 담당자 정보 추출
                        if '담당자' in cell_text or '담당부서' in cell_text:
                            content_parts.append(f"## 담당자 정보")
                            content_parts.append(cell_text)
                        
                        # 모집기간 정보 추출
                        if '모집기간' in cell_text:
                            content_parts.append(f"## 모집기간")
                            content_parts.append(cell_text)
                        
                        # 이미지나 콘텐츠 설명 추출
                        if cell.find('img'):
                            images = cell.find_all('img')
                            if images:
                                content_parts.append(f"## 첨부 이미지")
                                for img in images:
                                    alt_text = img.get('alt', '')
                                    src = img.get('src', '')
                                    if alt_text:
                                        content_parts.append(f"- {alt_text}")
                                    elif src:
                                        content_parts.append(f"- 이미지: {os.path.basename(src)}")
                
                # 공고 내용 설명 추가
                if content_parts:
                    content_parts.append("\n## 공고 내용")
                    content_parts.append("본 공고는 경상북도경제진흥원에서 제공하는 지원사업입니다.")
                    content_parts.append("자세한 내용은 첨부된 파일을 참고하시기 바랍니다.")
                    
                    return '\n\n'.join(content_parts)
            
            # 기본 콘텐츠 추출
            return self._extract_basic_content(soup)
            
        except Exception as e:
            logger.error(f"상세 콘텐츠 추출 중 오류: {e}")
            return self._extract_basic_content(soup)
    
    def _extract_basic_content(self, soup) -> str:
        """기본 콘텐츠 추출"""
        # 페이지 제목 추출
        title = soup.find('title')
        if title:
            title_text = title.get_text(strip=True)
            content = f"# {title_text}\n\n"
        else:
            content = "# 공고 내용\n\n"
        
        # 주요 텍스트 추출
        main_text = soup.get_text(separator='\n', strip=True)
        
        # 내용 정리
        lines = main_text.split('\n')
        meaningful_lines = []
        
        for line in lines:
            line = line.strip()
            if line and len(line) > 5:
                # 네비게이션 제거
                if not any(nav in line for nav in ['지원사업마당', '상담·고객센터', 'GEPA소식', 'GEPA소개', 'ESG경영', '경영공시']):
                    meaningful_lines.append(line)
        
        # 중복 제거
        seen = set()
        unique_lines = []
        for line in meaningful_lines:
            if line not in seen:
                seen.add(line)
                unique_lines.append(line)
        
        content += '\n'.join(unique_lines[:20])  # 처음 20줄만
        
        return content
    
    def _clean_content(self, text: str) -> str:
        """콘텐츠 정리"""
        # 연속된 공백 제거
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        
        # 불필요한 문자 제거
        text = re.sub(r'[^\w\s\n\-\.\,\(\)\[\]\{\}]', '', text)
        
        return text.strip()
    
    def _extract_attachments(self, soup) -> List[Dict[str, Any]]:
        """첨부파일 추출"""
        attachments = []
        
        try:
            # GEPA 사이트의 첨부파일 구조 파싱
            # 첨부파일은 보통 테이블 내의 링크로 제공됨
            file_links = soup.find_all('a', href=lambda x: x and 'javascript:' in str(x))
            
            for link in file_links:
                text = link.get_text(strip=True)
                
                # 파일 확장자가 있는 텍스트만 선택
                if any(ext in text.lower() for ext in ['.pdf', '.hwp', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.rar']):
                    # 파일명과 크기 정보 추출
                    filename = text
                    size_info = ""
                    
                    # 크기 정보가 있으면 추출
                    if '(' in filename and ')' in filename:
                        parts = filename.split('(')
                        if len(parts) >= 2:
                            filename = parts[0].strip()
                            size_info = parts[1].split(')')[0].strip()
                    
                    # JavaScript 링크에서 실제 파일 URL 추출 시도
                    onclick = link.get('onclick', '')
                    href = link.get('href', '')
                    
                    # 실제 다운로드 URL 생성 (추정)
                    file_url = f"{self.base_url}/download.php?file={filename}"
                    
                    attachments.append({
                        'filename': filename,
                        'url': file_url,
                        'type': self._get_file_type(filename),
                        'size': size_info,
                        'download_method': 'javascript'
                    })
            
            # 일반 파일 링크도 확인
            regular_links = soup.find_all('a', href=lambda x: x and any(ext in str(x).lower() for ext in ['.pdf', '.hwp', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.rar']))
            
            for link in regular_links:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                filename = text if text else os.path.basename(href)
                
                # 절대 URL로 변환
                if href.startswith('/'):
                    full_url = urljoin(self.base_url, href)
                elif not href.startswith('http'):
                    full_url = urljoin(self.base_url, href)
                else:
                    full_url = href
                
                attachments.append({
                    'filename': filename,
                    'url': full_url,
                    'type': self._get_file_type(href),
                    'size': '',
                    'download_method': 'direct'
                })
        
        except Exception as e:
            logger.error(f"첨부파일 추출 중 오류: {e}")
        
        return attachments
    
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
    
    def scrape_pages(self, max_pages: int = 3, output_base: str = "output/gepa") -> bool:
        """GEPA 지원사업 공고 수집"""
        try:
            logger.info("=== GEPA 지원사업 공고 수집 시작 ===")
            
            # 출력 디렉토리 생성
            os.makedirs(output_base, exist_ok=True)
            
            all_announcements = []
            
            for page_num in range(1, max_pages + 1):
                logger.info(f"페이지 {page_num} 처리 중")
                
                # 페이지 URL 생성
                page_url = self.get_list_url(page_num)
                logger.info(f"페이지 URL: {page_url}")
                
                # 페이지 요청
                response = self.session.get(page_url, timeout=self.timeout, verify=self.verify_ssl)
                
                if response.status_code != 200:
                    logger.error(f"페이지 {page_num} 접근 실패: {response.status_code}")
                    continue
                
                # 페이지 파싱
                announcements = self.parse_list_page(response.text)
                
                if announcements:
                    logger.info(f"페이지 {page_num}에서 {len(announcements)}개 공고 발견")
                    all_announcements.extend(announcements)
                    
                    # 각 공고 상세 처리
                    for i, announcement in enumerate(announcements, 1):
                        try:
                            # 안전한 파일명 생성
                            safe_title = re.sub(r'[^\w\-_\. ]', '_', announcement['title'])
                            safe_title = safe_title.replace(' ', '_')[:100]
                            
                            # 디렉토리 생성
                            item_dir = os.path.join(output_base, f"{len(all_announcements) - len(announcements) + i:03d}_{safe_title}")
                            os.makedirs(item_dir, exist_ok=True)
                            
                            # 상세 페이지 요청
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
                                            f.write(f"크기: {attachment.get('size', 'N/A')}\n")
                                            f.write(f"다운로드 방법: {attachment.get('download_method', 'direct')}\n")
                                            f.write("-" * 50 + "\n")
                                    
                                    # 실제 파일 다운로드 시도
                                    for attachment in detail_data['attachments']:
                                        try:
                                            if attachment.get('download_method') == 'javascript':
                                                # JavaScript 기반 다운로드는 현재 지원하지 않음
                                                logger.warning(f"JavaScript 기반 첨부파일은 직접 다운로드 불가: {attachment['filename']}")
                                            else:
                                                self.download_file(attachment['url'], attachments_dir, attachment['filename'])
                                        except Exception as e:
                                            logger.error(f"첨부파일 다운로드 실패: {e}")
                                    
                                    logger.info(f"첨부파일 정보 저장 완료: {len(detail_data['attachments'])}개")
                                
                                logger.info(f"공고 {i} 처리 완료: {announcement['title']}")
                            else:
                                logger.error(f"상세 페이지 접근 실패: {announcement['url']}")
                            
                            time.sleep(self.delay_between_requests)
                            
                        except Exception as e:
                            logger.error(f"공고 {i} 처리 중 오류: {e}")
                            continue
                else:
                    logger.warning(f"페이지 {page_num}에서 공고를 찾을 수 없음")
                
                if page_num < max_pages:
                    time.sleep(self.delay_between_pages)
            
            logger.info(f"총 {len(all_announcements)}개 공고 수집 완료")
            logger.info(f"저장 위치: {output_base}")
            
            return True
            
        except Exception as e:
            logger.error(f"수집 중 오류 발생: {e}")
            return False


def main():
    """메인 실행 함수"""
    # 출력 디렉토리 설정
    output_dir = "output/gepa"
    
    # 스크래퍼 생성
    scraper = EnhancedGEPAScraper()
    
    try:
        logger.info("=== GEPA 지원사업 공고 수집 시작 ===")
        
        # 3페이지까지 수집
        success = scraper.scrape_pages(max_pages=3, output_base=output_dir)
        
        if success:
            logger.info("✅ GEPA 지원사업 공고 수집 완료!")
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