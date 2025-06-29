#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
from urllib.parse import urljoin, unquote
from typing import List, Dict, Any
from bs4 import BeautifulSoup
import re
from enhanced_base_scraper import StandardTableScraper

class EnhancedKetiScraper(StandardTableScraper):
    """한국전자기술연구원(KETI) 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.keti.re.kr"
        self.list_url = "https://www.keti.re.kr/notice/notice.php"
        
        # 사이트별 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1
        
        # 로거 설정
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        self.logger.info("Enhanced KETI 스크래퍼 초기화 완료")

    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 생성"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}?pn={page_num}"

    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지에서 공고 정보 추출"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 테이블 찾기
        table = soup.find('table', class_='bbs_list')
        if not table:
            self.logger.warning("게시판 테이블을 찾을 수 없습니다")
            return announcements
        
        tbody = table.find('tbody')
        if not tbody:
            tbody = table
        
        rows = tbody.find_all('tr')
        self.logger.info(f"총 {len(rows)}개의 행을 찾았습니다")
        
        for i, row in enumerate(rows):
            try:
                cells = row.find_all('td')
                if len(cells) < 6:
                    continue
                
                # 번호 (첫 번째 셀)
                number_cell = cells[0]
                number_link = number_cell.find('a')
                if number_link:
                    number = number_link.get_text(strip=True)
                else:
                    number = number_cell.get_text(strip=True)
                
                if not number:
                    number = f"row_{i+1}"
                
                # 제목 및 링크 (두 번째 셀)
                title_cell = cells[1]
                title_link = title_cell.find('a', class_='subject')
                if not title_link:
                    title_link = title_cell.find('a')
                
                if not title_link:
                    continue
                
                title = title_link.get_text(strip=True)
                if not title:
                    continue
                
                href = title_link.get('href', '')
                detail_url = urljoin(self.base_url, href)
                
                # 작성자 (세 번째 셀)
                author = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                
                # 첨부파일 확인 (네 번째 셀)
                attachment_cell = cells[3]
                has_attachment = bool(attachment_cell.find('img'))
                
                # 조회수 (다섯 번째 셀)
                views = cells[4].get_text(strip=True) if len(cells) > 4 else ""
                
                # 등록일 (여섯 번째 셀)
                date = cells[5].get_text(strip=True) if len(cells) > 5 else ""
                
                announcement = {
                    'number': number,
                    'title': title,
                    'url': detail_url,
                    'author': author,
                    'views': views,
                    'date': date,
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
            # 제목 추출
            title_elem = soup.find('h4', class_='view_title')
            if not title_elem:
                title_elem = soup.find('h3')
            if not title_elem:
                title_elem = soup.find('div', class_='view_title')
            
            if title_elem:
                result['metadata']['title'] = title_elem.get_text(strip=True)
            
            # 메타 정보 추출 (작성자, 등록일, 조회수)
            info_table = soup.find('table', class_='view_info')
            if info_table:
                for row in info_table.find_all('tr'):
                    cells = row.find_all(['th', 'td'])
                    if len(cells) >= 2:
                        key = cells[0].get_text(strip=True)
                        value = cells[1].get_text(strip=True)
                        if '등록일' in key or 'date' in key.lower():
                            result['metadata']['date'] = value
                        elif '작성자' in key or 'author' in key.lower():
                            result['metadata']['author'] = value
                        elif '조회' in key or 'view' in key.lower():
                            result['metadata']['views'] = value
            
            # 본문 내용 추출
            content_elem = soup.find('div', class_='view_content')
            if not content_elem:
                content_elem = soup.find('div', class_='bbs_content')
            if not content_elem:
                content_elem = soup.find('div', class_='content')
            
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
                    if len(line) < 50 and any(keyword in line for keyword in ['공고', '안내', '모집', '선발', '신청']):
                        markdown_lines.append(f"## {line}\n")
                    else:
                        markdown_lines.append(line)
            
            return '\n'.join(markdown_lines)
            
        except Exception as e:
            self.logger.error(f"마크다운 변환 중 오류: {str(e)}")
            return content_elem.get_text(strip=True) if content_elem else ""

    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """첨부파일 정보 추출 - KETI 사이트 특화"""
        attachments = []
        
        try:
            # 첨부파일 영역 찾기 (여러 가능한 선택자 시도)
            attach_containers = [
                soup.find('p', class_='attach_file'),
                soup.find('div', class_='attach_file'),
                soup.find('div', class_='file_list'),
                soup.find('ul', class_='file_list'),
                soup.find('table', class_='file_list')
            ]
            
            for container in attach_containers:
                if not container:
                    continue
                    
                # 다운로드 링크 찾기
                download_links = container.find_all('a', href=re.compile(r'at=download'))
                for link in download_links:
                    href = link.get('href', '')
                    if not href or 'at=download' not in href:
                        continue
                    
                    # 링크 텍스트에서 파일명과 크기 정보 추출
                    link_text = link.get_text(strip=True)
                    
                    # 파일명 추출 (괄호 앞까지)
                    if ' (' in link_text:
                        filename = link_text.split(' (')[0].strip()
                        size_info = link_text.split(' (')[1].split(')')[0] if ')' in link_text else ""
                    else:
                        filename = link_text or f"attachment_{len(attachments)+1}"
                        size_info = ""
                    
                    # 절대 URL 생성
                    file_url = urljoin(self.base_url, href)
                    
                    attachment = {
                        'filename': filename,
                        'url': file_url,
                        'size': size_info,
                        'type': 'download'
                    }
                    
                    attachments.append(attachment)
                    self.logger.info(f"첨부파일 발견: {filename} ({size_info})")
            
            # 추가적으로 일반 다운로드 링크도 확인
            all_download_links = soup.find_all('a', href=re.compile(r'at=download'))
            for link in all_download_links:
                href = link.get('href', '')
                if href and href not in [att['url'] for att in attachments]:
                    link_text = link.get_text(strip=True)
                    if link_text and len(link_text) < 200:  # 너무 긴 텍스트 제외
                        filename = link_text.split(' (')[0].strip() if ' (' in link_text else link_text
                        file_url = urljoin(self.base_url, href)
                        
                        attachments.append({
                            'filename': filename,
                            'url': file_url,
                            'size': '',
                            'type': 'download'
                        })
                        self.logger.info(f"추가 첨부파일 발견: {filename}")
            
        except Exception as e:
            self.logger.error(f"첨부파일 추출 중 오류: {str(e)}")
        
        return attachments

    def download_file(self, url: str, save_path: str, attachment_info: Dict[str, Any] = None) -> bool:
        """파일 다운로드 - KETI 사이트 특화"""
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
                # 파일명 추출 로직 (기존 방식 사용)
                pass
            
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
    scraper = EnhancedKetiScraper()
    output_dir = "output/keti"
    
    try:
        os.makedirs(output_dir, exist_ok=True)
        print("=== 한국전자기술연구원(KETI) 스크래핑 시작 ===")
        scraper.scrape_pages(max_pages=3, output_base=output_dir)
        print("=== 한국전자기술연구원(KETI) 스크래핑 완료 ===")
        
    except KeyboardInterrupt:
        print("\n사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"스크래핑 중 오류 발생: {str(e)}")

if __name__ == "__main__":
    main()