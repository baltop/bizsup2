#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import re
from urllib.parse import urljoin, unquote, parse_qs, urlparse
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from enhanced_base_scraper import StandardTableScraper

class EnhancedKimsScraper(StandardTableScraper):
    """한국재료연구원(KIMS) 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.kims.re.kr"
        self.list_url = "https://www.kims.re.kr/v17/bbx/board.php?bx_table=05_02"
        
        # 사이트별 특화 설정
        self.verify_ssl = False  # SSL 인증서 문제 해결
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1
        
        # 로거 설정
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        self.logger.info("Enhanced KIMS 스크래퍼 초기화 완료")

    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 생성 - PHP GET 파라미터 방식"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}&page={page_num}"

    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지에서 공고 정보 추출 - 표준 테이블 구조"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 메인 테이블 찾기 - KIMS 특화 클래스
        table = soup.find('table')
        if not table:
            table = soup.find('div', class_='tbl_wrap')
            if table:
                table = table.find('table')
        
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
                if len(cells) < 4:  # 번호, 제목, 등록일, 조회 (4개 컬럼)
                    continue
                
                # 번호 (첫 번째 셀)
                number_cell = cells[0]
                number = number_cell.get_text(strip=True)
                if not number:
                    number = f"row_{i+1}"
                
                # 제목 및 링크 (두 번째 셀)
                title_cell = cells[1]
                
                # 카테고리 링크 제거 (일반공지 등)
                category_links = title_cell.find_all('a', href=re.compile(r'sca='))
                category = ""
                for cat_link in category_links:
                    category = cat_link.get_text(strip=True)
                    cat_link.decompose()  # 카테고리 링크 제거
                
                # 메인 제목 링크 찾기
                link_elem = title_cell.find('a', href=re.compile(r'wr_id='))
                if not link_elem:
                    continue
                
                title = link_elem.get_text(strip=True)
                if not title:
                    continue
                
                # PHP 상세 페이지 링크 구성
                href = link_elem.get('href', '')
                if href.startswith('./'):
                    detail_url = f"{self.base_url}/v17/bbx/{href[2:]}"
                elif href.startswith('/'):
                    detail_url = f"{self.base_url}{href}"
                elif href.startswith('board.php'):
                    detail_url = f"{self.base_url}/v17/bbx/{href}"
                else:
                    detail_url = urljoin(self.base_url, href)
                
                # 첨부파일 확인 (아이콘으로 판단)
                file_icon = title_cell.find('img', src=re.compile(r'icon_file'))
                has_attachment = bool(file_icon)
                
                # 새글 확인 (선택사항)
                new_icon = title_cell.find('img', src=re.compile(r'icon_new'))
                is_new = bool(new_icon)
                
                # 등록일 (세 번째 셀)
                date = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                
                # 조회수 (네 번째 셀)
                views = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                
                announcement = {
                    'number': number,
                    'title': title,
                    'url': detail_url,
                    'category': category,
                    'date': date,
                    'views': views,
                    'has_attachment': has_attachment,
                    'is_new': is_new,
                    'attachments': []
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
            # 제목 추출 - KIMS 페이지 특성
            title_elem = soup.find('span', class_='bo_v_tit')
            if not title_elem:
                title_elem = soup.find('h1')
            if not title_elem:
                title_elem = soup.find('h2')
            
            if title_elem:
                result['metadata']['title'] = title_elem.get_text(strip=True)
            
            # 메타 정보 추출 (작성자, 등록일, 조회수)
            info_area = soup.find('section', class_='bo_v_info')
            if not info_area:
                info_area = soup.find('div', class_='bo_v_info')
            
            if info_area:
                info_text = info_area.get_text(strip=True)
                result['metadata']['info'] = info_text
                
                # 정규표현식으로 개별 정보 추출
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', info_text)
                if date_match:
                    result['metadata']['date'] = date_match.group(1)
                
                views_match = re.search(r'조회[:\s]*(\d+)', info_text)
                if views_match:
                    result['metadata']['views'] = views_match.group(1)
            
            # 본문 내용 추출 - KIMS 특화
            content_elem = soup.find('div', id='bo_v_con')
            if not content_elem:
                content_elem = soup.find('div', class_='bo_v_con')
            if not content_elem:
                # 큰 div 영역 찾기
                content_elem = soup.find('div', class_='view_content')
            
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
        """첨부파일 정보 추출 - KIMS 사이트 특화"""
        attachments = []
        
        try:
            # 첨부파일 영역 찾기 - KIMS 특화
            file_section = soup.find('section', id='bo_v_file')
            if not file_section:
                file_section = soup.find('div', id='bo_v_file')
            if not file_section:
                file_section = soup.find('div', class_='bo_v_file')
            
            if file_section:
                # download.php 링크 찾기
                download_links = file_section.find_all('a', href=re.compile(r'download\.php'))
                for link in download_links:
                    href = link.get('href', '')
                    if not href:
                        continue
                    
                    # 파일명 추출 - strong 태그 내부
                    filename_elem = link.find('strong')
                    if filename_elem:
                        filename = filename_elem.get_text(strip=True)
                    else:
                        filename = link.get_text(strip=True)
                        # 파일 크기 정보 제거
                        filename = re.sub(r'\([^)]+\)$', '', filename).strip()
                    
                    if not filename:
                        filename = f"attachment_{len(attachments)+1}"
                    
                    # 상대 URL을 절대 URL로 변환
                    if href.startswith('./'):
                        file_url = f"{self.base_url}/v17/bbx/{href[2:]}"
                    elif href.startswith('/'):
                        file_url = f"{self.base_url}{href}"
                    elif href.startswith('download.php'):
                        file_url = f"{self.base_url}/v17/bbx/{href}"
                    else:
                        file_url = urljoin(self.base_url, href)
                    
                    attachment = {
                        'filename': filename,
                        'url': file_url,
                        'type': 'download'
                    }
                    
                    attachments.append(attachment)
                    self.logger.info(f"첨부파일 발견: {filename}")
            
            # 추가적으로 일반 파일 링크도 확인
            all_file_links = soup.find_all('a', href=re.compile(r'\.(pdf|hwp|doc|docx|xls|xlsx|jpg|jpeg|png|gif)$', re.I))
            for link in all_file_links:
                href = link.get('href', '')
                if href and href not in [att['url'] for att in attachments]:
                    filename = link.get_text(strip=True)
                    if not filename:
                        filename = os.path.basename(href)
                    
                    if filename and len(filename) < 200:  # 너무 긴 텍스트 제외
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
        """파일 다운로드 - KIMS 사이트 특화"""
        try:
            self.logger.info(f"파일 다운로드 시작: {url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': self.list_url
            }
            
            response = self.session.get(url, headers=headers, timeout=self.timeout, stream=True, verify=False)
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
    scraper = EnhancedKimsScraper()
    output_dir = "output/kims"
    
    try:
        os.makedirs(output_dir, exist_ok=True)
        print("=== 한국재료연구원(KIMS) 스크래핑 시작 ===")
        scraper.scrape_pages(max_pages=3, output_base=output_dir)
        print("=== 한국재료연구원(KIMS) 스크래핑 완료 ===")
        
    except KeyboardInterrupt:
        print("\n사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"스크래핑 중 오류 발생: {str(e)}")

if __name__ == "__main__":
    main()