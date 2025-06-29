#!/usr/bin/env python3
"""
Enhanced ULSANSHINBO (울산신용보증재단) 스크래퍼

울산신용보증재단 공지사항 게시판에서 공고를 수집하는 스크래퍼입니다.
표준 HTML 테이블 구조와 직접 링크 방식을 처리합니다.

URL: https://www.ulsanshinbo.co.kr/04_notice/?mcode=0404010000
"""

import os
import re
import time
import logging
from typing import List, Dict, Any
from urllib.parse import urljoin, unquote
from bs4 import BeautifulSoup
from enhanced_base_scraper import StandardTableScraper

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedUlsanshinboScraper(StandardTableScraper):
    """ULSANSHINBO 전용 Enhanced 스크래퍼 - StandardTableScraper 기반"""
    
    def __init__(self):
        super().__init__()
        
        # ULSANSHINBO 사이트 설정
        self.base_url = "https://www.ulsanshinbo.co.kr"
        self.list_url = "https://www.ulsanshinbo.co.kr/04_notice/?mcode=0404010000"
        
        # 사이트별 특화 설정
        self.verify_ssl = True  # ULSANSHINBO SSL 인증서 정상
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1
        
        # ULSANSHINBO 특화 설정
        self.mcode = "0404010000"
        self.bcode = "B012"
        
        # 현재 처리 중인 상세페이지 URL 저장 (Referer 용도)
        self.current_detail_url = None
        
    def get_list_url(self, page_num: int) -> str:
        """페이지별 URL 생성 - ULSANSHINBO는 GET 파라미터 방식"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}&mode=1&page={page_num}"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱 - ULSANSHINBO 테이블 구조"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # ULSANSHINBO 테이블 찾기 (class="목록" 또는 공지사항 리스트 테이블)
        table = soup.find('table')
        if not table:
            logger.warning("ULSANSHINBO 테이블을 찾을 수 없습니다")
            return announcements
        
        tbody = table.find('tbody')
        if not tbody:
            # tbody가 없는 경우 직접 table에서 tr 찾기
            rows = table.find_all('tr')[1:]  # 헤더 제외
        else:
            rows = tbody.find_all('tr')
        
        logger.info(f"ULSANSHINBO 테이블에서 {len(rows)}개 행 발견")
        
        for i, row in enumerate(rows):
            try:
                cells = row.find_all('td')
                if len(cells) < 6:  # No, 제목, 파일, 작성자, 조회, 작성일
                    continue
                
                # 컬럼 파싱: No, 제목, 파일, 작성자, 조회, 작성일
                number_cell = cells[0]
                title_cell = cells[1]
                file_cell = cells[2]
                author_cell = cells[3]
                views_cell = cells[4]
                date_cell = cells[5]
                
                # 번호 처리 (공지 vs 일반 번호)
                number, is_notice = self._process_notice_number(number_cell)
                
                # 제목 및 상세 페이지 링크
                title_link = title_cell.find('a')
                if not title_link:
                    continue
                
                title = title_link.get_text(strip=True)
                href = title_link.get('href', '')
                
                # 상세 페이지 URL 구성
                detail_url = self._extract_detail_url(href)
                if not detail_url:
                    continue
                
                # 작성자
                author = author_cell.get_text(strip=True)
                
                # 조회수
                views = views_cell.get_text(strip=True)
                
                # 작성일
                date = date_cell.get_text(strip=True)
                
                # 첨부파일 여부 확인
                has_attachments = self._check_attachments_in_cell(file_cell)
                
                announcement = {
                    'number': number,
                    'title': title,
                    'author': author,
                    'views': views,
                    'date': date,
                    'url': detail_url,
                    'has_attachments': has_attachments,
                    'is_notice': is_notice
                }
                
                announcements.append(announcement)
                logger.debug(f"공고 추가: [{number}] {title}")
                
            except Exception as e:
                logger.error(f"행 {i} 파싱 중 오류: {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
        return announcements
    
    def _process_notice_number(self, number_cell) -> tuple:
        """번호 셀에서 공지 여부 및 번호 추출"""
        # 공지 이미지 확인 (ULSANSHINBO는 "Notice" 이미지 사용)
        notice_img = number_cell.find('img')
        if notice_img:
            alt_text = notice_img.get('alt', '')
            src_text = notice_img.get('src', '')
            if '공지' in alt_text or '공지' in src_text or 'notice' in src_text.lower():
                return ("공지", True)
        
        # 일반 번호
        number_text = number_cell.get_text(strip=True)
        if number_text:
            return (number_text, False)
        
        return ("", False)
    
    def _extract_detail_url(self, href: str) -> str:
        """상대 경로를 절대 경로로 변환"""
        try:
            if href.startswith('/'):
                return f"{self.base_url}{href}"
            elif href.startswith('http'):
                return href
            else:
                return urljoin(self.base_url, href)
        except Exception as e:
            logger.debug(f"상세 페이지 URL 추출 실패: {e}")
        
        return None
    
    def _check_attachments_in_cell(self, file_cell) -> bool:
        """파일 셀에서 첨부파일 존재 여부 확인"""
        # 파일 아이콘이나 이미지가 있으면 첨부파일 존재
        if file_cell.find('img'):
            return True
        
        # 텍스트 내용으로 확인
        cell_text = file_cell.get_text(strip=True)
        if cell_text and cell_text not in ['-', '', 'X']:
            return True
        
        return False
    
    def parse_detail_page(self, html_content: str, url: str = None) -> Dict[str, Any]:
        """상세 페이지 파싱 - ULSANSHINBO 구조에 최적화"""
        
        # 상세 페이지 URL 저장 (다운로드 시 Referer로 사용)
        if url:
            self.current_detail_url = url
            logger.info(f"ULSANSHINBO current_detail_url 설정: {self.current_detail_url}")
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출
        title = self._extract_title(soup)
        
        # 본문 내용 추출
        content_text = self._extract_main_content(soup)
        
        # 메타 정보 추출
        meta_info = self._extract_meta_info(soup)
        
        # 첨부파일 추출
        attachments = self._extract_attachments(soup)
        
        # 마크다운 형식으로 조합
        markdown_content = f"# {title}\n\n"
        
        if meta_info:
            for key, value in meta_info.items():
                markdown_content += f"**{key}**: {value}\n"
            markdown_content += "\n"
        
        markdown_content += "---\n\n"
        markdown_content += content_text
        
        return {
            'content': markdown_content,
            'attachments': attachments
        }
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """ULSANSHINBO 상세페이지에서 제목 추출"""
        # ULSANSHINBO 상세페이지의 제목 구조 확인
        title_selectors = [
            '.board_title',
            '.view_title',
            '.notice_title',
            'h1',
            'h2',
            'h3'
        ]
        
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                title_text = title_elem.get_text(strip=True)
                if title_text and len(title_text) > 5:
                    return title_text
        
        # 백업 방법: 테이블에서 제목이 포함된 셀 찾기
        for cell in soup.find_all('td'):
            cell_text = cell.get_text(strip=True)
            # 제목으로 추정되는 긴 텍스트 찾기
            if 10 < len(cell_text) < 200 and not re.search(r'\d{4}-\d{2}-\d{2}', cell_text):
                return cell_text
        
        return "제목 없음"
    
    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """ULSANSHINBO 사이트에서 본문 내용 추출"""
        
        # 1. 불필요한 요소들 제거
        unwanted_selectors = [
            'nav', 'header', 'footer', '.nav', '.navigation',
            '.menu', '.sidebar', '.breadcrumb',
            'script', 'style', '.ads', '.advertisement',
            '.btn-group', '.pagination', '.paging'
        ]
        
        for selector in unwanted_selectors:
            for elem in soup.select(selector):
                elem.decompose()
        
        # 2. ULSANSHINBO 특화 콘텐츠 선택자
        content_selectors = [
            '.board_content',        # 게시판 콘텐츠
            '.view_content',         # 뷰 콘텐츠
            '.content_area',         # 콘텐츠 영역
            'article',               # article 태그
            '.article_content',      # 아티클 콘텐츠
            'iframe',                # PDF iframe 콘텐츠
            'main'                   # main 태그
        ]
        
        content_elem = None
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                logger.debug(f"콘텐츠 선택자 사용: {selector}")
                break
        
        if content_elem:
            # iframe인 경우 src 정보 포함
            if content_elem.name == 'iframe':
                iframe_src = content_elem.get('src', '')
                if iframe_src:
                    content_text = f"PDF 문서: {iframe_src}"
                else:
                    content_text = "PDF 문서가 포함되어 있습니다."
            else:
                # 추가 불필요한 요소 제거
                for unwanted in content_elem.select('.btn, .button, .file-list, .attach-list'):
                    unwanted.decompose()
                
                # 본문 텍스트 추출
                content_text = self.simple_html_to_text(content_elem)
        else:
            # 백업 방법: 테이블 셀에서 가장 긴 텍스트 찾기
            content_candidates = []
            
            for cell in soup.find_all('td'):
                cell_text = cell.get_text(strip=True)
                if len(cell_text) > 100:  # 최소 길이 조건
                    content_candidates.append(cell_text)
            
            # 가장 긴 텍스트를 본문으로 선택
            if content_candidates:
                content_text = max(content_candidates, key=len)
            else:
                content_text = "본문 내용을 찾을 수 없습니다."
        
        return content_text.strip()
    
    def simple_html_to_text(self, element) -> str:
        """HTML 요소를 간단한 텍스트로 변환"""
        text = element.get_text(separator='\n\n', strip=True)
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text
    
    def _extract_meta_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """ULSANSHINBO 사이트에서 메타 정보 추출"""
        meta_info = {}
        
        try:
            # ULSANSHINBO 상세페이지의 메타 정보 테이블에서 추출
            page_text = soup.get_text()
            
            # 날짜 패턴 찾기
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', page_text)
            if date_match:
                meta_info['작성일'] = date_match.group(1)
            
            # 조회수 패턴 찾기
            views_match = re.search(r'조회수?\s*:?\s*(\d+)', page_text)
            if views_match:
                meta_info['조회수'] = views_match.group(1)
            
            # 작성자 패턴 찾기
            writer_match = re.search(r'작성자\s*:?\s*([^\s\n]+)', page_text)
            if writer_match:
                meta_info['작성자'] = writer_match.group(1)
            
        except Exception as e:
            logger.debug(f"메타 정보 추출 중 오류: {e}")
        
        return meta_info
    
    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """ULSANSHINBO 구조에서 첨부파일 정보 추출"""
        attachments = []
        
        # ULSANSHINBO 파일 다운로드 링크 패턴: /_Inc/download.php
        download_links = soup.find_all('a', href=lambda x: x and 'download.php' in x)
        
        for link in download_links:
            try:
                href = link.get('href', '')
                if 'download.php' not in href:
                    continue
                
                # 파일명 추출 (링크 텍스트에서)
                filename = link.get_text(strip=True)
                if not filename:
                    # href에서 파라미터 추출하여 기본 파일명 생성
                    f_idx_match = re.search(r'f_idx=([^&]+)', href)
                    if f_idx_match:
                        f_idx = f_idx_match.group(1)
                        filename = f"attachment_{f_idx}"
                    else:
                        filename = f"attachment_{len(attachments)+1}"
                
                # 파일 크기 정보 추출 (있는 경우)
                size_info = ""
                parent = link.parent
                if parent:
                    parent_text = parent.get_text()
                    # (567.5 KB), (194.5 KB) 등의 패턴 찾기
                    size_match = re.search(r'\(([^)]+[KMG]?B?)\)', parent_text)
                    if size_match:
                        size_info = size_match.group(1)
                
                # 전체 URL 구성
                file_url = urljoin(self.base_url, href)
                
                # 파일 타입 확인
                file_type = self._determine_file_type(filename, link)
                
                attachment = {
                    'filename': filename,
                    'url': file_url,
                    'type': file_type,
                    'size': size_info,
                    'download_method': 'direct'
                }
                
                attachments.append(attachment)
                logger.debug(f"첨부파일 발견: {filename} ({size_info})")
                
            except Exception as e:
                logger.error(f"첨부파일 처리 중 오류: {e}")
                continue
        
        logger.info(f"첨부파일 {len(attachments)}개 발견")
        return attachments
    
    def _determine_file_type(self, filename: str, link_elem) -> str:
        """파일 타입 결정"""
        if not filename:
            return 'unknown'
        
        filename_lower = filename.lower()
        
        if filename_lower.endswith('.pdf'):
            return 'pdf'
        elif filename_lower.endswith(('.hwp', '.hwpx')):
            return 'hwp'
        elif filename_lower.endswith(('.doc', '.docx')):
            return 'doc'
        elif filename_lower.endswith(('.xls', '.xlsx')):
            return 'excel'
        elif filename_lower.endswith(('.jpg', '.jpeg', '.png', '.gif')):
            return 'image'
        elif filename_lower.endswith('.zip'):
            return 'zip'
        else:
            return 'unknown'
    
    def download_file(self, file_url: str, save_path: str, attachment_info: dict = None) -> bool:
        """파일 다운로드 - ULSANSHINBO 표준 다운로드"""
        try:
            logger.info(f"파일 다운로드 시작: {file_url}")
            
            # ULSANSHINBO 표준 다운로드 헤더
            download_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
                'Connection': 'keep-alive'
            }
            
            # Referer 헤더 설정 (필요시)
            if hasattr(self, 'current_detail_url') and self.current_detail_url:
                download_headers['Referer'] = self.current_detail_url
                logger.info(f"ULSANSHINBO Referer 설정: {self.current_detail_url}")
            
            # 다운로드 요청
            response = self.session.get(
                file_url, 
                headers=download_headers, 
                stream=True, 
                verify=self.verify_ssl, 
                timeout=self.timeout
            )
            
            logger.info(f"다운로드 응답: {response.status_code}, 크기: {len(response.content)} bytes")
            
            # 상태 코드 확인
            if response.status_code != 200:
                logger.error(f"다운로드 실패: HTTP {response.status_code}")
                return False
            
            # 작은 파일 크기 체크 (오류 메시지 가능성)
            if len(response.content) < 100:  # 100바이트 미만은 의심스러움
                try:
                    content_text = response.content.decode('utf-8', errors='ignore')
                    logger.warning(f"ULSANSHINBO 소용량 파일 ({len(response.content)}바이트): {content_text[:100]}...")
                except:
                    logger.warning(f"ULSANSHINBO 소용량 파일: {len(response.content)}바이트")
            
            # 파일 저장
            return self._save_file_from_response(response, save_path)
            
        except Exception as e:
            logger.error(f"파일 다운로드 중 예외 발생: {e}")
            return False
    
    def _save_file_from_response(self, response, save_path: str) -> bool:
        """응답에서 파일 저장"""
        try:
            # Content-Disposition에서 파일명 추출 시도
            content_disposition = response.headers.get('Content-Disposition', '')
            if content_disposition:
                extracted_filename = self._extract_filename_from_disposition(content_disposition)
                if extracted_filename:
                    # 디렉토리는 유지하고 파일명만 변경
                    directory = os.path.dirname(save_path)
                    save_path = os.path.join(directory, self.sanitize_filename(extracted_filename))
            
            # 파일 저장
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(save_path)
            logger.info(f"파일 다운로드 완료: {os.path.basename(save_path)} ({file_size:,} bytes)")
            return True
            
        except Exception as e:
            logger.debug(f"파일 저장 실패: {e}")
            return False
    
    def _extract_filename_from_disposition(self, content_disposition: str) -> str:
        """Content-Disposition 헤더에서 파일명 추출"""
        try:
            # RFC 5987 형식 처리 (filename*=UTF-8''filename)
            rfc5987_match = re.search(r"filename\*=([^']*)'([^']*)'(.+)", content_disposition)
            if rfc5987_match:
                encoding, lang, filename = rfc5987_match.groups()
                try:
                    filename = unquote(filename, encoding=encoding or 'utf-8')
                    return filename
                except:
                    pass
            
            # 일반 filename 파라미터 처리
            filename_match = re.search(r'filename[^;=\n]*=([\'"]*)(.*?)\1', content_disposition)
            if filename_match:
                filename = filename_match.group(2)
                
                # 다양한 인코딩 시도
                for encoding in ['utf-8', 'euc-kr', 'cp949']:
                    try:
                        if encoding == 'utf-8':
                            decoded = filename.encode('latin-1').decode('utf-8')
                        else:
                            decoded = filename.encode('latin-1').decode(encoding)
                        
                        if decoded and not decoded.isspace():
                            return decoded.replace('+', ' ').strip()
                    except:
                        continue
                        
                return filename.replace('+', ' ')
                
        except Exception as e:
            logger.debug(f"파일명 추출 실패: {e}")
            
        return None


def main():
    """테스트 실행"""
    output_dir = "output/ulsanshinbo"
    os.makedirs(output_dir, exist_ok=True)
    
    scraper = EnhancedUlsanshinboScraper()
    
    try:
        result = scraper.scrape_pages(max_pages=3, output_base=output_dir)
        print(f"✅ ULSANSHINBO 스크래핑 완료!")
        
        # scrape_pages 메서드가 dict를 반환하는지 확인
        if isinstance(result, dict):
            print(f"수집된 공고: {result.get('total_announcements', 0)}개")
            print(f"다운로드된 파일: {result.get('total_files', 0)}개")
            print(f"성공률: {result.get('success_rate', 0):.1f}%")
        else:
            print(f"스크래핑 결과: {result}")
        
    except Exception as e:
        print(f"❌ 스크래핑 실패: {e}")
        raise


if __name__ == "__main__":
    main()