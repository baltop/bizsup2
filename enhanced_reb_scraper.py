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

class EnhancedRebScraper(StandardTableScraper):
    """한국부동산원(REB) 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.reb.or.kr"
        self.list_url = "https://www.reb.or.kr/reb/na/ntt/selectNttList.do"
        
        # REB 사이트 필수 파라미터
        self.mi = "9564"
        self.bbsId = "1134"
        
        # 사이트별 특화 설정
        self.verify_ssl = True  # SSL 정상
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 2  # 봇 차단 방지
        
        # 봇 차단 대응 헤더 설정
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Referer': self.base_url
        })
        
        # 로거 설정
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        self.logger.info("Enhanced REB 스크래퍼 초기화 완료")

    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 생성"""
        if page_num == 1:
            return f"{self.list_url}?mi={self.mi}&bbsId={self.bbsId}"
        else:
            # 2페이지부터는 POST 방식 폼 제출
            return self.list_url

    def _get_page_announcements(self, page_num: int) -> list:
        """페이지별 공고 수집 - REB 특화 (POST 방식)"""
        try:
            if page_num == 1:
                # 첫 페이지는 GET 방식
                self.logger.info(f"페이지 {page_num} GET 방식 접근")
                response = self.get_page(self.get_list_url(page_num))
            else:
                # 2페이지부터는 POST 방식 폼 제출
                self.logger.info(f"페이지 {page_num} POST 방식 접근")
                data = {
                    'mi': self.mi,
                    'bbsId': self.bbsId,
                    'currPage': str(page_num)
                }
                response = self.post_page(self.list_url, data=data)
            
            if response and response.status_code == 200:
                return self.parse_list_page(response.text)
            else:
                self.logger.error(f"페이지 {page_num} 접근 실패: {response.status_code if response else 'No response'}")
                return []
                
        except Exception as e:
            self.logger.error(f"페이지 {page_num} 처리 중 오류: {str(e)}")
            return []

    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지에서 공고 정보 추출 - JSP 테이블 구조"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 메인 테이블 찾기 - REB 사이트 특화
        table = soup.find('table', class_='table')
        if not table:
            table = soup.find('table')
        
        if not table:
            self.logger.warning("게시판 테이블을 찾을 수 없습니다")
            return announcements
        
        # tbody 또는 직접 tr 찾기
        tbody = table.find('tbody')
        if not tbody:
            tbody = table
        
        rows = tbody.find_all('tr')
        self.logger.info(f"총 {len(rows)}개의 행을 찾았습니다")
        
        for i, row in enumerate(rows):
            try:
                cells = row.find_all('td')
                if len(cells) < 4:  # 번호, 제목, 등록일, 조회수 최소 4개
                    continue
                
                # 번호 (첫 번째 셀)
                number_cell = cells[0]
                number = number_cell.get_text(strip=True)
                if not number:
                    number = f"row_{i+1}"
                
                # 제목 및 링크 (두 번째 셀) - JavaScript 링크 처리
                title_cell = cells[1]
                link_elem = title_cell.find('a')
                if not link_elem:
                    continue
                
                title = link_elem.get_text(strip=True)
                if not title:
                    continue
                
                # nttSn 추출 - data-id 속성에서 가져오기
                ntt_sn = link_elem.get('data-id', '')
                
                if not ntt_sn:
                    # 대안: href나 onclick에서 찾기 (이전 방식)
                    href = link_elem.get('href', '')
                    onclick = link_elem.get('onclick', '')
                    
                    if 'javascript:' in href or onclick:
                        js_content = href if href else onclick
                        ntt_match = re.search(r'nttSn[\'"]?\s*[=:]\s*[\'"]?(\d+)', js_content)
                        if ntt_match:
                            ntt_sn = ntt_match.group(1)
                
                if not ntt_sn:
                    self.logger.warning(f"nttSn을 찾을 수 없습니다. 링크 속성: {link_elem.attrs}")
                    continue
                
                # 상세 페이지 URL 구성
                detail_url = f"{self.base_url}/reb/na/ntt/selectNttInfo.do?nttSn={ntt_sn}&bbsId={self.bbsId}&mi={self.mi}"
                
                # 첨부파일 확인 (파일 아이콘)
                has_attachment = False
                if len(cells) > 4:
                    file_cell = cells[4] if len(cells) > 4 else cells[-1]
                    file_icon = file_cell.find('img') or file_cell.find('i', class_='fa-file')
                    has_attachment = bool(file_icon)
                
                # 등록일 (세 번째 또는 네 번째 셀)
                date_idx = 2 if len(cells) <= 5 else 3
                date = cells[date_idx].get_text(strip=True) if len(cells) > date_idx else ""
                
                # 조회수 (마지막에서 두 번째 또는 마지막)
                views_idx = len(cells) - (2 if has_attachment else 1)
                views = cells[views_idx].get_text(strip=True) if len(cells) > views_idx else ""
                
                announcement = {
                    'number': number,
                    'title': title,
                    'url': detail_url,
                    'nttSn': ntt_sn,
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

    def _get_detail_content(self, announcement: Dict[str, Any]) -> Dict[str, Any]:
        """상세 페이지 내용 가져오기 - REB 특화 POST 방식"""
        try:
            detail_url = f"{self.base_url}/reb/na/ntt/selectNttInfo.do"
            
            # POST 데이터로 상세 페이지 접근
            data = {
                'nttSn': announcement['nttSn'],
                'bbsId': self.bbsId,
                'mi': self.mi
            }
            
            self.logger.info(f"상세 페이지 POST 요청: nttSn={announcement['nttSn']}")
            response = self.post_page(detail_url, data=data)
            
            if response and response.status_code == 200:
                return self.parse_detail_page(response.text)
            else:
                self.logger.error(f"상세 페이지 접근 실패: {response.status_code if response else 'No response'}")
                return {'content': '', 'attachments': [], 'metadata': {}}
                
        except Exception as e:
            self.logger.error(f"상세 페이지 접근 중 오류: {str(e)}")
            return {'content': '', 'attachments': [], 'metadata': {}}

    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지에서 내용과 첨부파일 정보 추출"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = {
            'content': '',
            'attachments': [],
            'metadata': {}
        }
        
        try:
            # 제목 추출 - REB 사이트 특화: <th class="title">
            title_elem = soup.find('th', class_='title')
            if not title_elem:
                title_elem = soup.find('h3') or soup.find('h2') or soup.find('h1')
            if not title_elem:
                title_elem = soup.find('div', class_='title')
            
            if title_elem:
                result['metadata']['title'] = title_elem.get_text(strip=True)
            
            # 메타 정보 추출 (등록일) - REB 테이블 구조
            date_row = soup.find('th', string='등록일')
            if date_row:
                date_cell = date_row.find_next_sibling('td')
                if date_cell:
                    result['metadata']['date'] = date_cell.get_text(strip=True)
            
            # 본문 내용 추출 - REB 특화: <div class="nttSynapView">
            content_elem = soup.find('div', class_='nttSynapView')
            if not content_elem:
                content_elem = soup.find('div', class_='se-contents')
            if not content_elem:
                content_elem = soup.find('div', class_='content')
            if not content_elem:
                content_elem = soup.find('div', id='content')
            if not content_elem:
                content_elem = soup.find('div', class_='view_content')
            if not content_elem:
                content_elem = soup.find('div', class_='board_content')
            
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
        """첨부파일 정보 추출 - REB 사이트 특화 (RAONK 업로더)"""
        attachments = []
        
        try:
            # REB 특화: <ul class="file"> 내의 첨부파일들
            file_ul = soup.find('ul', class_='file')
            if file_ul:
                file_items = file_ul.find_all('li')
                for item in file_items:
                    # 파일명 추출 (li 텍스트에서 amp; 제거하고 정리)
                    filename_text = item.get_text(strip=True)
                    if not filename_text:
                        continue
                    
                    # 파일명에서 "미리보기" 제거
                    filename = filename_text.replace('미리보기', '').replace('&nbsp;', '').strip()
                    if not filename or len(filename) > 200:
                        continue
                    
                    # JavaScript 함수에서 파일 ID 추출
                    view_link = item.find('a', onclick=re.compile(r"openDocView"))
                    if view_link:
                        onclick = view_link.get('onclick', '')
                        # openDocView('파일ID') 패턴에서 파일ID 추출
                        file_id_match = re.search(r"openDocView\('([^']+)'\)", onclick)
                        if file_id_match:
                            file_id = file_id_match.group(1)
                            
                            # REB 파일 다운로드 URL 구성 (추정)
                            file_url = f"{self.base_url}/docview/download/{file_id}"
                            
                            attachment = {
                                'filename': filename,
                                'url': file_url,
                                'file_id': file_id,
                                'type': 'reb_docview'
                            }
                            
                            attachments.append(attachment)
                            self.logger.info(f"첨부파일 발견: {filename} (ID: {file_id})")
            
            # 추가적으로 일반적인 첨부파일 영역도 확인
            file_areas = []
            
            # 다른 패턴의 첨부파일 영역
            file_section = soup.find('div', class_='attach') or soup.find('div', class_='file_area')
            if file_section:
                file_areas.append(file_section)
            
            # 테이블 내 첨부파일
            file_table = soup.find('table', class_='file') or soup.find('table', class_='attach')
            if file_table:
                file_areas.append(file_table)
            
            for file_area in file_areas:
                # 다운로드 링크 찾기
                download_links = file_area.find_all('a', href=re.compile(r'download|file'))
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
                    self.logger.info(f"일반 첨부파일 발견: {filename}")
            
        except Exception as e:
            self.logger.error(f"첨부파일 추출 중 오류: {str(e)}")
        
        return attachments

    def download_file(self, url: str, save_path: str, attachment_info: Dict[str, Any] = None) -> bool:
        """파일 다운로드 - REB 사이트 특화"""
        try:
            self.logger.info(f"파일 다운로드 시작: {url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
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
    scraper = EnhancedRebScraper()
    output_dir = "output/reb"
    
    try:
        os.makedirs(output_dir, exist_ok=True)
        print("=== 한국부동산원(REB) 스크래핑 시작 ===")
        scraper.scrape_pages(max_pages=3, output_base=output_dir)
        print("=== 한국부동산원(REB) 스크래핑 완료 ===")
        
    except KeyboardInterrupt:
        print("\n사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"스크래핑 중 오류 발생: {str(e)}")

if __name__ == "__main__":
    main()