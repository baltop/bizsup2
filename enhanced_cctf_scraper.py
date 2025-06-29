#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import re
from urllib.parse import urljoin, unquote, parse_qs, urlparse
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from enhanced_base_scraper import StandardTableScraper

class EnhancedCctfScraper(StandardTableScraper):
    """충청북도문화관광재단(CCTF) 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.cctf.or.kr"
        self.list_url = "https://www.cctf.or.kr/coding/sub5/sub1.asp"
        
        # 사이트별 특화 설정
        self.verify_ssl = True  # SSL 인증서 정상
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1
        
        # 로거 설정
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        self.logger.info("Enhanced CCTF 스크래퍼 초기화 완료")

    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 생성 - ASP 파라미터 방식"""
        return f"{self.list_url}?bseq=1&cat=-1&sk=&sv=&yy=&page={page_num}"

    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지에서 공고 정보 추출 - CCTF 테이블 구조 (7컬럼: 체크박스, 번호, 파일, 제목, 이름, 날짜, 조회)"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 메인 테이블 찾기 - class="table-list"
        table = soup.find('table', class_='table-list')
        if not table:
            # 대체 방법으로 table 태그 찾기
            table = soup.find('table')
            if not table:
                self.logger.warning("게시판 테이블을 찾을 수 없습니다")
                return announcements
        
        # tbody 찾기
        tbody = table.find('tbody')
        if not tbody:
            self.logger.warning("tbody를 찾을 수 없습니다")
            return announcements
        
        rows = tbody.find_all('tr')
        self.logger.info(f"총 {len(rows)}개의 행을 찾았습니다")
        
        for i, row in enumerate(rows):
            try:
                cells = row.find_all('td')
                if len(cells) < 7:  # 체크박스, 번호, 파일, 제목, 이름, 날짜, 조회 (7개 컬럼)
                    self.logger.debug(f"행 {i+1}: 컬럼 수 부족 ({len(cells)}개), 건너뜀")
                    continue
                
                # 번호 (두 번째 셀, 인덱스 1)
                number_cell = cells[1]
                number = number_cell.get_text(strip=True)
                if not number:
                    number = f"row_{i+1}"
                
                # 파일 (세 번째 셀, 인덱스 2) - 첨부파일 여부 확인
                file_cell = cells[2]
                has_attachment = False
                file_img = file_cell.find('img')
                if file_img:
                    img_src = file_img.get('src', '')
                    # blank.gif가 아니면 첨부파일 있음
                    if 'blank.gif' not in img_src:
                        has_attachment = True
                
                # 제목 및 링크 (네 번째 셀, 인덱스 3)
                title_cell = cells[3]
                link_elem = title_cell.find('a')
                if not link_elem:
                    self.logger.debug(f"행 {i+1}: 링크 요소를 찾을 수 없음, 건너뜀")
                    continue
                
                title = link_elem.get_text(strip=True)
                if not title:
                    self.logger.debug(f"행 {i+1}: 제목이 비어있음, 건너뜀")
                    continue
                
                # ASP 상세 페이지 링크 구성
                href = link_elem.get('href', '')
                if 'javascript:' in href:
                    # JavaScript 함수에서 aseq 파라미터 추출
                    aseq_match = re.search(r"aseq=(\d+)", href)
                    if aseq_match:
                        aseq = aseq_match.group(1)
                        detail_url = f"{self.list_url}?bseq=1&mode=view&aseq={aseq}"
                    else:
                        self.logger.debug(f"행 {i+1}: aseq 파라미터를 찾을 수 없음, 건너뜀")
                        continue
                else:
                    detail_url = urljoin(self.base_url, href)
                
                # 이름 (다섯 번째 셀, 인덱스 4)
                author = cells[4].get_text(strip=True) if len(cells) > 4 else ""
                
                # 날짜 (여섯 번째 셀, 인덱스 5)
                date = cells[5].get_text(strip=True) if len(cells) > 5 else ""
                
                # 조회수 (일곱 번째 셀, 인덱스 6)
                views = cells[6].get_text(strip=True) if len(cells) > 6 else ""
                
                announcement = {
                    'number': number,
                    'title': title,
                    'url': detail_url,
                    'author': author,
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

    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지에서 내용과 첨부파일 정보 추출"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = {
            'content': '',
            'attachments': [],
            'metadata': {}
        }
        
        try:
            # 제목 추출 - ASP 페이지 특성에 맞게
            title_elem = soup.find('td', class_='title')
            if not title_elem:
                title_elem = soup.find('h3')
            if not title_elem:
                title_elem = soup.find('h2')
            
            if title_elem:
                result['metadata']['title'] = title_elem.get_text(strip=True)
            
            # 메타 정보 추출 (작성자, 등록일, 조회수)
            info_cells = soup.find_all('td')
            for cell in info_cells:
                cell_text = cell.get_text(strip=True)
                
                # 날짜 패턴 찾기
                if re.search(r'\d{4}-\d{2}-\d{2}', cell_text):
                    result['metadata']['date'] = cell_text
                
                # 조회수 패턴 찾기
                if '조회' in cell_text and re.search(r'\d+', cell_text):
                    views_match = re.search(r'(\d+)', cell_text)
                    if views_match:
                        result['metadata']['views'] = views_match.group(1)
            
            # 본문 내용 추출 - 여러 패턴 시도
            content_elem = soup.find('td', class_='content')
            if not content_elem:
                content_elem = soup.find('div', class_='content')
            if not content_elem:
                # 큰 colspan을 가진 td 찾기 (본문 영역)
                content_elem = soup.find('td', attrs={'colspan': True})
            
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
        """첨부파일 정보 추출 - CCTF 사이트 특화"""
        attachments = []
        
        try:
            # 첨부파일 영역 찾기 - 다양한 패턴 시도
            file_areas = []
            
            # 파일 다운로드 링크 찾기
            download_links = soup.find_all('a', href=re.compile(r'download|file|attach'))
            for link in download_links:
                href = link.get('href', '')
                if not href:
                    continue
                
                filename = link.get_text(strip=True)
                if not filename:
                    filename = f"attachment_{len(attachments)+1}"
                
                # 상대 URL을 절대 URL로 변환
                file_url = urljoin(self.base_url, href)
                
                attachment = {
                    'filename': filename,
                    'url': file_url,
                    'type': 'download'
                }
                
                attachments.append(attachment)
                self.logger.info(f"첨부파일 발견: {filename}")
            
            # 이미지 파일도 첨부파일로 처리
            images = soup.find_all('img', src=re.compile(r'\.(jpg|jpeg|png|gif|pdf|hwp|doc|docx|xls|xlsx)$', re.I))
            for img in images:
                src = img.get('src', '')
                if src and not src.startswith('data:'):
                    filename = os.path.basename(src)
                    file_url = urljoin(self.base_url, src)
                    
                    # 중복 확인
                    if file_url not in [att['url'] for att in attachments]:
                        attachments.append({
                            'filename': filename,
                            'url': file_url,
                            'type': 'image'
                        })
                        self.logger.info(f"이미지 파일 발견: {filename}")
            
        except Exception as e:
            self.logger.error(f"첨부파일 추출 중 오류: {str(e)}")
        
        return attachments

    def download_file(self, url: str, save_path: str, attachment_info: Dict[str, Any] = None) -> bool:
        """파일 다운로드 - CCTF 사이트 특화"""
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
    scraper = EnhancedCctfScraper()
    output_dir = "output/cctf"
    
    try:
        os.makedirs(output_dir, exist_ok=True)
        print("=== 충청북도문화관광재단(CCTF) 스크래핑 시작 ===")
        scraper.scrape_pages(max_pages=3, output_base=output_dir)
        print("=== 충청북도문화관광재단(CCTF) 스크래핑 완료 ===")
        
    except KeyboardInterrupt:
        print("\n사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"스크래핑 중 오류 발생: {str(e)}")

if __name__ == "__main__":
    main()