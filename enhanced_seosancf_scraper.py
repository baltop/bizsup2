#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import re
from urllib.parse import urljoin, unquote, parse_qs, urlparse
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from enhanced_base_scraper import StandardTableScraper

class EnhancedSeosancfScraper(StandardTableScraper):
    """서산문화재단(seosancf) 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "http://seosancf.or.kr"
        self.list_url = "http://seosancf.or.kr/index.php?MenuID=17"
        
        # 사이트별 특화 설정
        self.verify_ssl = False  # HTTP만 지원
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1
        
        # 로거 설정
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        self.logger.info("Enhanced 서산문화재단 스크래퍼 초기화 완료")

    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 생성 - PHP GET 파라미터 방식"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}&gotopage={page_num}"

    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지에서 공고 정보 추출 - 표준 테이블 구조"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 메인 테이블 찾기
        table = soup.find('table', id='bbs_table')
        if not table:
            table = soup.find('table', class_='table')
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
                if len(cells) < 6:  # No, 제목, 첨부, 작성자, 작성일, 조회 (6개 컬럼)
                    continue
                
                # 번호 (첫 번째 셀) - 공지 vs 일반 공고 구분
                number_cell = cells[0]
                notice_span = number_cell.find('span', class_='blueText')
                if notice_span and '공지' in notice_span.get_text():
                    number = "공지"
                else:
                    number = number_cell.get_text(strip=True)
                    if not number:
                        number = f"row_{i+1}"
                
                # 제목 및 링크 (두 번째 셀)
                title_cell = cells[1]
                link_elem = title_cell.find('a')
                if not link_elem:
                    continue
                
                title = link_elem.get_text(strip=True)
                if not title:
                    continue
                
                # PHP 상세 페이지 링크 구성
                href = link_elem.get('href', '')
                if href.startswith('/'):
                    detail_url = f"{self.base_url}{href}"
                elif href.startswith('index.php'):
                    detail_url = f"{self.base_url}/{href}"
                else:
                    detail_url = urljoin(self.base_url, href)
                
                # 첨부파일 확인 (세 번째 셀)
                file_cell = cells[2]
                file_icon = file_cell.find('i', class_='fa')
                has_attachment = bool(file_icon)
                
                # 작성자 (네 번째 셀)
                author = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                
                # 작성일 (다섯 번째 셀)
                date = cells[4].get_text(strip=True) if len(cells) > 4 else ""
                
                # 조회수 (여섯 번째 셀)
                views = cells[5].get_text(strip=True) if len(cells) > 5 else ""
                
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
            # 제목 추출 - PHP 페이지 특성에 맞게
            title_elem = soup.find('td', class_='title')
            if not title_elem:
                title_elem = soup.find('h3')
            if not title_elem:
                title_elem = soup.find('h2')
            
            if title_elem:
                result['metadata']['title'] = title_elem.get_text(strip=True)
            
            # 메타 정보 추출 (작성자, 등록일, 조회수)
            view_table = soup.find('table', class_='view_table')
            if view_table:
                info_cells = view_table.find_all('td')
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
            
            # 본문 내용 추출 - PHP 게시판 특성
            content_elem = soup.find('td', id='bbs_content')
            if not content_elem:
                content_elem = soup.find('div', class_='bbs_content')
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
        """첨부파일 정보 추출 - 서산문화재단 사이트 특화"""
        attachments = []
        
        try:
            # 첨부파일 영역 찾기 - PHP 게시판 패턴
            file_wrap = soup.find('td', id='file_list_wrap')
            if not file_wrap:
                file_wrap = soup.find('div', class_='file_list')
            
            if file_wrap:
                # download.php 링크 찾기
                download_links = file_wrap.find_all('a', href=re.compile(r'download\.php'))
                for link in download_links:
                    href = link.get('href', '')
                    if not href:
                        continue
                    
                    # 파일명 추출
                    filename = link.get_text(strip=True)
                    if not filename:
                        filename = f"attachment_{len(attachments)+1}"
                    
                    # 상대 URL을 절대 URL로 변환
                    if href.startswith('/'):
                        file_url = f"{self.base_url}{href}"
                    elif href.startswith('moa/'):
                        file_url = f"{self.base_url}/{href}"
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
        """파일 다운로드 - 서산문화재단 사이트 특화 (EUC-KR 파일명 처리)"""
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
                # 한글 파일명 처리 - EUC-KR 인코딩 고려
                filename_match = re.search(r'filename[^;=\n]*=([\'"]*)(.*?)\1', content_disposition)
                if filename_match:
                    filename = filename_match.group(2)
                    try:
                        # 다단계 인코딩 처리
                        if filename.startswith('%'):
                            # URL 인코딩된 경우
                            filename = unquote(filename, encoding='utf-8')
                        else:
                            # EUC-KR로 인코딩된 경우가 많음
                            try:
                                filename = filename.encode('latin-1').decode('euc-kr')
                            except:
                                try:
                                    filename = filename.encode('latin-1').decode('utf-8')
                                except:
                                    pass  # 원본 사용
                        
                        # 파일명이 유효하면 경로 업데이트
                        if filename and not filename.isspace() and '?' not in filename:
                            save_dir = os.path.dirname(save_path)
                            clean_filename = self.sanitize_filename(filename)
                            save_path = os.path.join(save_dir, clean_filename)
                    except Exception as decode_error:
                        self.logger.warning(f"파일명 디코딩 실패: {decode_error}")
            
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
    scraper = EnhancedSeosancfScraper()
    output_dir = "output/seosancf"
    
    try:
        os.makedirs(output_dir, exist_ok=True)
        print("=== 서산문화재단(seosancf) 스크래핑 시작 ===")
        scraper.scrape_pages(max_pages=3, output_base=output_dir)
        print("=== 서산문화재단(seosancf) 스크래핑 완료 ===")
        
    except KeyboardInterrupt:
        print("\n사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"스크래핑 중 오류 발생: {str(e)}")

if __name__ == "__main__":
    main()