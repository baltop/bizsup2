#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import re
from urllib.parse import urljoin, unquote, parse_qs, urlparse
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from enhanced_base_scraper import StandardTableScraper

class EnhancedIncheonpassScraper(StandardTableScraper):
    """인천PASS 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://incheon.pass.or.kr"
        self.list_url = "https://incheon.pass.or.kr/participation/bid_announcement_list.php"
        
        # 인천PASS 사이트 기본 파라미터
        self.default_params = {
            'group': 'basic',
            'code': 'B14',
            'abmode': 'list',
            'bsort': 'desc',
            'category': '12',
            'field': 'all',
            'search': '',
            'bfsort': ''
        }
        
        # 사이트별 특화 설정
        self.verify_ssl = True  # SSL 정상
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1
        
        # 로거 설정
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        self.logger.info("Enhanced 인천PASS 스크래퍼 초기화 완료")

    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 생성 - GET 파라미터 방식"""
        params = self.default_params.copy()
        
        if page_num > 1:
            # sno는 15씩 증가 (페이지당 15개 공고)
            params['sno'] = str((page_num - 1) * 15)
        
        # URL 파라미터 구성
        param_string = "&".join([f"{k}={v}" for k, v in params.items() if v])
        return f"{self.list_url}?{param_string}"

    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지에서 공고 정보 추출 - 표준 테이블 구조"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 메인 테이블 찾기 - 인천PASS 특화
        table = soup.find('table', class_='board_list')
        if not table:
            table = soup.find('table', {'summary': '공지사항리스트'})
        if not table:
            table = soup.find('table')
        
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
                if len(cells) < 3:  # 최소 3개 컬럼 필요
                    continue
                
                # 번호 (첫 번째 셀) - 공지 vs 일반 공고 구분
                number_cell = cells[0]
                number = number_cell.get_text(strip=True)
                
                # 공지 처리
                if '[공지]' in number or '공지' in number:
                    number = "공지"
                elif not number:
                    number = f"row_{i+1}"
                
                # 분류 (두 번째 셀) - 선택사항
                category = ""
                if len(cells) > 2:
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
                
                # 메타 정보 추출 (날짜, 조회수 등)
                date = self._extract_date_from_cell(title_cell)
                views = self._extract_views_from_cell(title_cell)
                
                # 첨부파일 확인
                has_attachment = self._check_attachment_in_cell(title_cell)
                
                announcement = {
                    'number': number,
                    'title': title,
                    'url': detail_url,
                    'category': category,
                    'date': date,
                    'views': views,
                    'has_attachment': has_attachment,
                    'attachments': []
                }
                
                announcements.append(announcement)
                self.logger.info(f"공고 추가: [{number}] {title}")
                
            except Exception as e:
                self.logger.error(f"행 파싱 중 오류 발생 (행 {i+1}): {str(e)}")
                continue
        
        self.logger.info(f"총 {len(announcements)}개의 공고를 추출했습니다")
        return announcements

    def _extract_date_from_cell(self, cell) -> str:
        """셀에서 날짜 정보 추출"""
        try:
            cell_text = cell.get_text()
            # 날짜 패턴 찾기 (YYYY-MM-DD, YYYY.MM.DD 등)
            date_match = re.search(r'(\d{4}[-./]\d{1,2}[-./]\d{1,2})', cell_text)
            if date_match:
                return date_match.group(1)
            
            # 상대적 날짜 (예: 2일전, 1주전)
            relative_match = re.search(r'(\d+[일주월년]?\s*[전후])', cell_text)
            if relative_match:
                return relative_match.group(1)
                
        except:
            pass
        
        return ""

    def _extract_views_from_cell(self, cell) -> str:
        """셀에서 조회수 정보 추출"""
        try:
            cell_text = cell.get_text()
            # 조회수 패턴 찾기
            views_match = re.search(r'조회\s*[:\s]*(\d+)', cell_text)
            if views_match:
                return views_match.group(1)
            
            # 숫자만 있는 경우 (조회수일 가능성)
            number_match = re.search(r'\b(\d{1,4})\b', cell_text)
            if number_match:
                return number_match.group(1)
                
        except:
            pass
        
        return ""

    def _check_attachment_in_cell(self, cell) -> bool:
        """셀에서 첨부파일 여부 확인"""
        try:
            # 첨부파일 아이콘 확인
            file_icon = cell.find('img', src=re.compile(r'file|attach', re.I))
            if file_icon:
                return True
            
            # 첨부파일 텍스트 확인
            cell_text = cell.get_text()
            if '첨부' in cell_text or 'file' in cell_text.lower():
                return True
                
        except:
            pass
        
        return False

    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지에서 내용과 첨부파일 정보 추출"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = {
            'content': '',
            'attachments': [],
            'metadata': {}
        }
        
        try:
            # 제목 추출 - 인천PASS 페이지 특성
            title_elem = soup.find('h3') or soup.find('h2') or soup.find('h1')
            if not title_elem:
                title_elem = soup.find('div', class_='title')
            if not title_elem:
                title_elem = soup.find('td', class_='title')
            
            if title_elem:
                result['metadata']['title'] = title_elem.get_text(strip=True)
            
            # 메타 정보 추출 (등록일, 조회수 등)
            info_area = soup.find('div', class_='info')
            if not info_area:
                info_area = soup.find('table', class_='view_info')
            if not info_area:
                # 테이블에서 정보 찾기
                info_table = soup.find('table')
                if info_table:
                    info_area = info_table
            
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
            
            # 본문 내용 추출 - 인천PASS 특화
            content_elem = soup.find('div', class_='content')
            if not content_elem:
                content_elem = soup.find('div', class_='view_content')
            if not content_elem:
                content_elem = soup.find('td', class_='content')
            if not content_elem:
                # 큰 div 또는 td 영역 찾기
                for elem in soup.find_all(['div', 'td']):
                    if len(elem.get_text(strip=True)) > 100:  # 충분한 내용이 있는 경우
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
        """첨부파일 정보 추출 - 인천PASS 사이트 특화"""
        attachments = []
        
        try:
            # 첨부파일 영역 찾기 - 다양한 패턴
            file_areas = []
            
            # 일반적인 첨부파일 영역
            file_section = soup.find('div', class_='file')
            if file_section:
                file_areas.append(file_section)
            
            file_section = soup.find('div', class_='attach')
            if file_section:
                file_areas.append(file_section)
            
            # 테이블 내 첨부파일
            file_table = soup.find('table', class_='file')
            if file_table:
                file_areas.append(file_table)
            
            # 일반 다운로드 링크
            download_links = soup.find_all('a', href=re.compile(r'download|file', re.I))
            
            for link in download_links:
                href = link.get('href', '')
                if not href:
                    continue
                
                filename = link.get_text(strip=True)
                if not filename or len(filename) > 200:
                    filename = f"attachment_{len(attachments)+1}"
                
                # 상대 URL을 절대 URL로 변환
                if href.startswith('/'):
                    file_url = f"{self.base_url}{href}"
                elif not href.startswith('http'):
                    file_url = urljoin(self.base_url, href)
                else:
                    file_url = href
                
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
        """파일 다운로드 - 인천PASS 사이트 특화"""
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
    scraper = EnhancedIncheonpassScraper()
    output_dir = "output/incheonpass"
    
    try:
        os.makedirs(output_dir, exist_ok=True)
        print("=== 인천PASS 스크래핑 시작 ===")
        scraper.scrape_pages(max_pages=3, output_base=output_dir)
        print("=== 인천PASS 스크래핑 완료 ===")
        
    except KeyboardInterrupt:
        print("\n사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"스크래핑 중 오류 발생: {str(e)}")

if __name__ == "__main__":
    main()