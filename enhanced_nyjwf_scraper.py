#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import re
import time
from urllib.parse import urljoin, unquote, parse_qs, urlparse
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from enhanced_base_scraper import StandardTableScraper

class EnhancedNyjwfScraper(StandardTableScraper):
    """남양주복지재단 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://nyjwf.or.kr"
        self.list_url = "https://nyjwf.or.kr/Home/23"
        
        # 사이트별 특화 설정
        self.verify_ssl = True  # SSL 정상
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1
        
        # 로거 설정
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        self.logger.info("Enhanced 남양주복지재단 스크래퍼 초기화 완료")

    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 생성"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}?page={page_num}"

    def _get_page_announcements(self, page_num: int) -> List[Dict[str, Any]]:
        """페이지별 공고 목록 가져오기 (User-Agent 헤더 필수)"""
        try:
            url = self.get_list_url(page_num)
            self.logger.info(f"페이지 {page_num} 요청: {url}")
            
            # User-Agent 헤더 필수 (403 에러 방지)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            response = self.session.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            # 인코딩 설정
            if response.encoding != 'utf-8':
                response.encoding = 'utf-8'
            
            return self.parse_list_page(response.text)
            
        except Exception as e:
            self.logger.error(f"페이지 {page_num} 요청 실패: {str(e)}")
            return []

    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지에서 공고 정보 추출"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 게시판 테이블 찾기
        list_div = soup.find('div', class_='list')
        if not list_div:
            self.logger.warning("게시판 목록 div를 찾을 수 없습니다")
            return announcements
        
        table = list_div.find('table')
        if not table:
            self.logger.warning("게시판 테이블을 찾을 수 없습니다")
            return announcements
        
        # tbody 찾기
        tbody = table.find('tbody')
        if not tbody:
            tbody = table
        
        rows = tbody.find_all('tr')
        self.logger.info(f"총 {len(rows)}개의 행을 찾았습니다")
        
        for i, row in enumerate(rows):
            try:
                cells = row.find_all('td')
                if len(cells) < 5:  # 5개 컬럼 필요 (번호, 분류, 제목, 첨부, 등록일자)
                    continue
                
                # 공지사항 여부 확인
                is_notice = 'board_notice' in row.get('class', [])
                
                # 번호 (첫 번째 셀)
                number_cell = cells[0]
                number = number_cell.get_text(strip=True)
                
                if is_notice or number == "공지":
                    number = "공지"
                elif not number:
                    number = f"row_{i+1}"
                
                # 분류 (두 번째 셀)
                category_cell = cells[1]
                category = category_cell.get_text(strip=True)
                
                # 제목 및 링크 (세 번째 셀)
                title_cell = cells[2]
                link_elem = title_cell.find('a')
                if not link_elem:
                    continue
                
                title = link_elem.get_text(strip=True)
                if not title:
                    continue
                
                # 상세 페이지 URL 구성
                href = link_elem.get('href', '')
                if href.startswith('?'):
                    detail_url = f"{self.list_url}{href}"
                elif href.startswith('/'):
                    detail_url = f"{self.base_url}{href}"
                else:
                    detail_url = urljoin(self.list_url, href)
                
                # 첨부파일 (네 번째 셀)
                attachment_cell = cells[3]
                file_links = attachment_cell.find_all('a', class_='file')
                has_attachment = len(file_links) > 0
                
                # 첨부파일 정보 수집
                attachments = []
                for file_link in file_links:
                    file_href = file_link.get('href', '')
                    file_title = file_link.get('title', '')
                    
                    if file_href:
                        # 절대 URL로 변환
                        if file_href.startswith('/'):
                            file_url = f"{self.base_url}{file_href}"
                        else:
                            file_url = urljoin(self.base_url, file_href)
                        
                        # 파일명이 없으면 URL에서 추출
                        filename = file_title if file_title else os.path.basename(file_href)
                        if not filename:
                            filename = f"attachment_{len(attachments)+1}"
                        
                        attachments.append({
                            'filename': filename,
                            'url': file_url,
                            'type': 'direct'
                        })
                
                # 등록일자 (다섯 번째 셀)
                date_cell = cells[4]
                date = date_cell.get_text(strip=True)
                
                announcement = {
                    'number': number,
                    'title': title,
                    'url': detail_url,
                    'category': category,
                    'date': date,
                    'has_attachment': has_attachment,
                    'is_notice': is_notice,
                    'attachments': attachments
                }
                
                announcements.append(announcement)
                self.logger.info(f"공고 추가: [{number}] {title}")
                
            except Exception as e:
                self.logger.error(f"행 파싱 중 오류 발생 (행 {i+1}): {str(e)}")
                continue
        
        self.logger.info(f"총 {len(announcements)}개의 공고를 추출했습니다")
        return announcements

    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지에서 내용과 첨부파일 정보 추출"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = {
            'content': '',
            'attachments': [],
            'metadata': {}
        }
        
        try:
            # 제목 추출
            title_elem = soup.find('h3', class_='board_title')
            if not title_elem:
                title_elem = soup.find('h2', class_='title')
            if not title_elem:
                title_elem = soup.find('h3') or soup.find('h2') or soup.find('h1')
            
            if title_elem:
                result['metadata']['title'] = title_elem.get_text(strip=True)
            
            # 메타 정보 추출 (등록일, 조회수 등)
            info_area = soup.find('div', class_='board_info')
            if not info_area:
                info_area = soup.find('div', class_='info')
            if not info_area:
                info_area = soup.find('ul', class_='info')
            
            if info_area:
                info_text = info_area.get_text(strip=True)
                result['metadata']['info'] = info_text
                
                # 날짜 패턴 찾기
                date_match = re.search(r'(\d{4}[-./]\d{1,2}[-./]\d{1,2})', info_text)
                if date_match:
                    result['metadata']['date'] = date_match.group(1)
                
                # 조회수 패턴 찾기
                views_match = re.search(r'조회[:\s]*(\d+)', info_text)
                if views_match:
                    result['metadata']['views'] = views_match.group(1)
            
            # 본문 내용 추출
            content_elem = soup.find('div', class_='board_content')
            if not content_elem:
                content_elem = soup.find('div', class_='content')
            if not content_elem:
                content_elem = soup.find('div', class_='cont')
            if not content_elem:
                # 충분한 내용이 있는 div 찾기
                for elem in soup.find_all('div'):
                    if len(elem.get_text(strip=True)) > 100:
                        content_elem = elem
                        break
            
            if content_elem:
                # 본문을 마크다운으로 변환
                content_text = self._convert_to_markdown(content_elem)
                result['content'] = content_text
            
            # 첨부파일 추출
            attachments = self._extract_attachments(soup)
            result['attachments'] = attachments
            
            self.logger.info(f"상세 페이지 파싱 완료 - 첨부파일: {len(result['attachments'])}개")
            
        except Exception as e:
            self.logger.error(f"상세 페이지 파싱 중 오류: {str(e)}")
        
        return result

    def _convert_to_markdown(self, content_elem) -> str:
        """HTML 내용을 마크다운으로 변환"""
        try:
            # 간단한 HTML to Markdown 변환
            text = content_elem.get_text(separator='\n', strip=True)
            
            # 기본적인 마크다운 형식 적용
            lines = text.split('\n')
            markdown_lines = []
            
            for line in lines:
                line = line.strip()
                if line:
                    # 제목처럼 보이는 줄 처리
                    if len(line) < 50 and any(keyword in line for keyword in ['공고', '안내', '모집', '선발', '신청', '공모']):
                        markdown_lines.append(f"## {line}\n")
                    else:
                        markdown_lines.append(line)
            
            return '\n'.join(markdown_lines)
            
        except Exception as e:
            self.logger.error(f"마크다운 변환 중 오류: {str(e)}")
            return content_elem.get_text(strip=True) if content_elem else ""

    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """첨부파일 정보 추출"""
        attachments = []
        
        try:
            # 첨부파일 영역 찾기 - 다양한 패턴
            file_areas = []
            
            # 일반적인 첨부파일 영역
            file_section = soup.find('div', class_='board_file')
            if file_section:
                file_areas.append(file_section)
            
            file_section = soup.find('div', class_='file')
            if file_section:
                file_areas.append(file_section)
            
            file_section = soup.find('div', class_='attach')
            if file_section:
                file_areas.append(file_section)
            
            # 전체 페이지에서 첨부파일 링크 찾기
            file_links = soup.find_all('a', class_='file')
            
            for link in file_links:
                href = link.get('href', '')
                title = link.get('title', '')
                
                if href and href.startswith('/File/'):
                    # 파일명 처리
                    filename = title if title else os.path.basename(href)
                    if not filename or filename == href:
                        filename = f"attachment_{len(attachments)+1}"
                    
                    # 상대 URL을 절대 URL로 변환
                    file_url = f"{self.base_url}{href}"
                    
                    attachment = {
                        'filename': filename,
                        'url': file_url,
                        'type': 'download'
                    }
                    
                    attachments.append(attachment)
                    self.logger.info(f"첨부파일 발견: {filename}")
            
            # 추가적으로 일반 파일 링크도 확인
            all_file_links = soup.find_all('a', href=re.compile(r'\.(pdf|hwp|doc|docx|xls|xlsx|jpg|jpeg|png|gif|zip)$', re.I))
            for link in all_file_links:
                href = link.get('href', '')
                if href and href not in [att['url'] for att in attachments]:
                    filename = link.get_text(strip=True)
                    if not filename:
                        filename = os.path.basename(href)
                    
                    if filename and len(filename) < 200:
                        file_url = urljoin(self.base_url, href)
                        
                        attachments.append({
                            'filename': filename,
                            'url': file_url,
                            'type': 'direct'
                        })
                        self.logger.info(f"추가 파일 발견: {filename}")
            
        except Exception as e:
            self.logger.error(f"첨부파일 추출 중 오류: {str(e)}")
        
        return attachments

    def download_file(self, url: str, save_path: str, attachment_info: Dict[str, Any] = None) -> bool:
        """파일 다운로드 - User-Agent 헤더 포함"""
        try:
            self.logger.info(f"파일 다운로드 시작: {url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': self.list_url
            }
            
            response = self.session.get(url, headers=headers, timeout=self.timeout, stream=True)
            response.raise_for_status()
            
            # Content-Disposition 헤더에서 파일명 추출 시도
            content_disposition = response.headers.get('Content-Disposition', '')
            if content_disposition and 'filename' in content_disposition:
                # 한글 파일명 처리
                filename_match = re.search(r'filename[^;=\n]*=([\'"]*)(.*?)\1', content_disposition)
                if filename_match:
                    filename = filename_match.group(2)
                    try:
                        # UTF-8 디코딩 시도
                        if filename.startswith('%'):
                            filename = unquote(filename, encoding='utf-8')
                        else:
                            filename = filename.encode('latin-1').decode('utf-8')
                        
                        # 파일명이 유효하면 경로 업데이트
                        if filename and not filename.isspace():
                            save_dir = os.path.dirname(save_path)
                            clean_filename = self.sanitize_filename(filename)
                            save_path = os.path.join(save_dir, clean_filename)
                    except:
                        pass  # 디코딩 실패 시 원본 경로 사용
            
            # 디렉토리 생성
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # 파일 저장
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(save_path)
            self.logger.info(f"파일 다운로드 완료: {save_path} ({file_size} bytes)")
            return True
            
        except Exception as e:
            self.logger.error(f"파일 다운로드 실패 ({url}): {str(e)}")
            return False

def main():
    """메인 실행 함수"""
    scraper = EnhancedNyjwfScraper()
    output_dir = "output/nyjwf"
    
    try:
        os.makedirs(output_dir, exist_ok=True)
        print("=== 남양주복지재단 스크래핑 시작 ===")
        scraper.scrape_pages(max_pages=3, output_base=output_dir)
        print("=== 남양주복지재단 스크래핑 완료 ===")
        
    except KeyboardInterrupt:
        print("\n사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"스크래핑 중 오류 발생: {str(e)}")

if __name__ == "__main__":
    main()