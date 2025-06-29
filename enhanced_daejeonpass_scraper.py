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

class EnhancedDaejeonpassScraper(StandardTableScraper):
    """대전PASS 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://daejeon.pass.or.kr"
        self.list_url = "https://daejeon.pass.or.kr/board.es"
        
        # 대전PASS 사이트 기본 파라미터
        self.default_params = {
            'mid': 'a10201000000',
            'bid': '0003',
            'act': 'list',
            'nPage': '1',
            'b_list': '10',
            'orderby': '',
            'dept_code': '',
            'tag': '',
            'list_no': '',
        }
        
        # 사이트별 특화 설정
        self.verify_ssl = True  # SSL 정상
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1
        
        # 로거 설정
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        self.logger.info("Enhanced 대전PASS 스크래퍼 초기화 완료")

    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 생성 - GET 파라미터 방식"""
        params = self.default_params.copy()
        params['nPage'] = str(page_num)
        
        # URL 파라미터 구성
        param_string = "&".join([f"{k}={v}" for k, v in params.items() if v])
        return f"{self.list_url}?{param_string}"

    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지에서 공고 정보 추출 - 리스트 구조"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 메인 리스트 컨테이너 찾기
        list_container = soup.find('div', class_='tstyle_list')
        if not list_container:
            self.logger.warning("게시판 리스트 컨테이너를 찾을 수 없습니다")
            return announcements
        
        # 공고 아이템들 찾기
        items = list_container.find_all('ul')
        self.logger.info(f"총 {len(items)}개의 공고 항목을 찾았습니다")
        
        for i, item in enumerate(items):
            try:
                # 컬럼들 추출 (5개 컬럼: 번호, 제목, 날짜, 첨부파일, 조회수)
                columns = item.find_all('li')
                if len(columns) < 5:  # 최소 5개 컬럼 필요
                    continue
                
                # 공지 여부 확인
                is_notice = 'notice' in item.get('class', [])
                
                # 번호 (첫 번째 컬럼)
                number_col = columns[0]
                if is_notice:
                    number = "공지"
                else:
                    number = number_col.get_text(strip=True)
                    if not number:
                        number = f"row_{i+1}"
                
                # 제목 및 링크 (두 번째 컬럼)
                title_col = columns[1]
                link_elem = title_col.find('a')
                if not link_elem:
                    continue
                
                title = link_elem.get_text(strip=True)
                if not title:
                    continue
                
                # 상세 페이지 URL 구성
                href = link_elem.get('href', '')
                onclick = link_elem.get('onclick', '')
                
                # onclick에서 list_no 추출
                list_no_match = re.search(r"goView\('(\d+)'\)", onclick)
                if list_no_match:
                    list_no = list_no_match.group(1)
                    detail_url = f"{self.list_url}?mid=a10201000000&bid=0003&act=view&list_no={list_no}&nPage=1"
                elif href:
                    detail_url = urljoin(self.base_url, href)
                else:
                    continue
                
                # 날짜 (세 번째 컬럼)
                date_col = columns[2]
                date = date_col.get_text(strip=True)
                
                # 첨부파일 여부 (네 번째 컬럼)
                file_col = columns[3]
                has_attachment = bool(file_col.find('img'))
                
                # 조회수 (다섯 번째 컬럼)
                views_col = columns[4]
                views = views_col.get_text(strip=True)
                
                # NEW 표시 확인
                is_new = bool(title_col.find('i', class_='xi-new'))
                
                announcement = {
                    'number': number,
                    'title': title,
                    'url': detail_url,
                    'date': date,
                    'views': views,
                    'has_attachment': has_attachment,
                    'is_notice': is_notice,
                    'is_new': is_new,
                    'list_no': list_no_match.group(1) if list_no_match else '',
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
            title_elem = soup.find('h3', class_='tit') or soup.find('h2') or soup.find('h1')
            if not title_elem:
                title_elem = soup.find('div', class_='view-title')
            
            if title_elem:
                result['metadata']['title'] = title_elem.get_text(strip=True)
            
            # 메타 정보 추출 (등록일, 조회수 등)
            info_area = soup.find('div', class_='view-info')
            if not info_area:
                info_area = soup.find('div', class_='info')
            if not info_area:
                info_area = soup.find('ul', class_='view-info')
            
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
            content_elem = soup.find('div', class_='view-cont')
            if not content_elem:
                content_elem = soup.find('div', class_='cont')
            if not content_elem:
                content_elem = soup.find('div', class_='content')
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
        """첨부파일 정보 추출 - 대전PASS 사이트 특화"""
        attachments = []
        
        try:
            # 첨부파일 영역 찾기
            file_area = soup.find('div', class_='add_file_list')
            if not file_area:
                file_area = soup.find('ul', class_='add_file')
            
            if file_area:
                # 파일 리스트 찾기
                file_items = file_area.find_all('li')
                
                for item in file_items:
                    try:
                        # 파일 다운로드 링크 찾기
                        file_link = item.find('a', class_='file-down')
                        if not file_link:
                            file_link = item.find('a', href=re.compile(r'boardDownload'))
                        if not file_link:
                            file_link = item.find('a', class_='btn-down')
                        
                        if file_link:
                            href = file_link.get('href', '')
                            filename = file_link.get_text(strip=True)
                            
                            # 파일명이 너무 길거나 비어있는 경우 처리
                            if not filename or len(filename) > 200:
                                # 파일 확장자 이미지에서 추출 시도
                                file_img = item.find('img')
                                if file_img:
                                    img_src = file_img.get('src', '')
                                    if 'pdf.png' in img_src:
                                        filename = f"attachment_{len(attachments)+1}.pdf"
                                    elif 'hwp.png' in img_src:
                                        filename = f"attachment_{len(attachments)+1}.hwp"
                                    elif 'doc.png' in img_src:
                                        filename = f"attachment_{len(attachments)+1}.doc"
                                    elif 'xls.png' in img_src:
                                        filename = f"attachment_{len(attachments)+1}.xls"
                                    elif 'zip.png' in img_src:
                                        filename = f"attachment_{len(attachments)+1}.zip"
                                    else:
                                        filename = f"attachment_{len(attachments)+1}"
                                else:
                                    filename = f"attachment_{len(attachments)+1}"
                            
                            # 상대 URL을 절대 URL로 변환
                            if href.startswith('/'):
                                file_url = f"{self.base_url}{href}"
                            elif not href.startswith('http'):
                                file_url = urljoin(self.base_url, href)
                            else:
                                file_url = href
                            
                            # 파일 크기 정보 추출
                            file_size = ""
                            size_span = item.find('span', class_='fileSize')
                            if size_span:
                                file_size = size_span.get_text(strip=True)
                            
                            attachment = {
                                'filename': filename,
                                'url': file_url,
                                'size': file_size,
                                'type': 'download'
                            }
                            
                            attachments.append(attachment)
                            self.logger.info(f"첨부파일 발견: {filename} ({file_size})")
                    
                    except Exception as e:
                        self.logger.error(f"첨부파일 처리 중 오류: {str(e)}")
                        continue
            
            # 추가로 일반 다운로드 링크도 확인
            download_links = soup.find_all('a', href=re.compile(r'boardDownload', re.I))
            for link in download_links:
                href = link.get('href', '')
                if href and href not in [att['url'] for att in attachments]:
                    filename = link.get_text(strip=True)
                    if not filename:
                        filename = f"download_{len(attachments)+1}"
                    
                    if filename and len(filename) < 200:
                        file_url = urljoin(self.base_url, href)
                        
                        attachments.append({
                            'filename': filename,
                            'url': file_url,
                            'size': '',
                            'type': 'direct'
                        })
                        self.logger.info(f"추가 다운로드 링크 발견: {filename}")
            
        except Exception as e:
            self.logger.error(f"첨부파일 추출 중 오류: {str(e)}")
        
        return attachments

    def download_file(self, url: str, save_path: str, attachment_info: Dict[str, Any] = None) -> bool:
        """파일 다운로드 - 대전PASS 사이트 특화"""
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
    scraper = EnhancedDaejeonpassScraper()
    output_dir = "output/daejeonpass"
    
    try:
        os.makedirs(output_dir, exist_ok=True)
        print("=== 대전PASS 스크래핑 시작 ===")
        scraper.scrape_pages(max_pages=3, output_base=output_dir)
        print("=== 대전PASS 스크래핑 완료 ===")
        
    except KeyboardInterrupt:
        print("\n사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"스크래핑 중 오류 발생: {str(e)}")

if __name__ == "__main__":
    main()