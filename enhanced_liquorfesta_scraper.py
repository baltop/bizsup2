# -*- coding: utf-8 -*-
"""
광주주류관광페스타(Liquor Festa) 공고 스크래퍼 - Enhanced 버전
URL: https://www.liquorfesta.com/bbs/board.php?bo_table=notice
"""

import requests
from bs4 import BeautifulSoup
import os
import time
import re
from urllib.parse import urljoin, urlparse, unquote
import logging
from enhanced_base_scraper import StandardTableScraper
from datetime import datetime

logger = logging.getLogger(__name__)

class EnhancedLiquorFestaScraper(StandardTableScraper):
    """광주주류관광페스타 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        # 기본 설정
        self.base_url = "https://www.liquorfesta.com"
        self.list_url = "https://www.liquorfesta.com/bbs/board.php?bo_table=notice"
        
        # 사이트별 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1  # 요청 간 지연
        self.delay_between_pages = 2  # 페이지 간 대기 시간
        
        # 그누보드5 특화 설정
        self.use_playwright = False  # 정적 HTML 파싱으로 충분
        
        # 세션 초기화
        self._initialize_session()
    
    def _initialize_session(self):
        """그누보드5 사이트용 세션 초기화"""
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        })
        
        try:
            # 메인 페이지 방문으로 세션 설정
            logger.info("Liquor Festa 사이트 세션 초기화 중...")
            response = self.session.get(self.base_url, verify=self.verify_ssl, timeout=self.timeout)
            response.raise_for_status()
            logger.info(f"세션 초기화 완료 (쿠키 {len(self.session.cookies)}개 설정)")
        except Exception as e:
            logger.warning(f"세션 초기화 실패: {e}")
    
    def get_list_url(self, page_num: int) -> str:
        """페이지별 목록 URL 생성"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}&page={page_num}"
    
    def parse_list_page(self, html_content: str) -> list:
        """목록 페이지 파싱 - 그누보드5 구조"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        try:
            # 그누보드5 테이블 구조: #bo_list .tbl_wrap table tbody
            table = soup.select_one('#bo_list .tbl_wrap table tbody')
            
            if not table:
                logger.warning("공고 목록 테이블을 찾을 수 없습니다.")
                return announcements
            
            rows = table.find_all('tr')
            logger.info(f"목록에서 {len(rows)}개 행 발견")
            
            for i, row in enumerate(rows):
                try:
                    # 그누보드 광고나 빈 행 건너뛰기
                    if 'td_empty' in row.get('class', []) or len(row.find_all('td')) < 3:
                        continue
                    
                    cells = row.find_all('td')
                    if len(cells) < 3:
                        continue
                    
                    # 번호 또는 공지 확인 (첫 번째 셀)
                    number_cell = cells[0]
                    is_notice = 'bo_notice' in row.get('class', []) or number_cell.find('i', class_='fa-bell')
                    
                    if is_notice:
                        number = "공지"
                    else:
                        number_text = number_cell.get_text(strip=True)
                        number = number_text if number_text and number_text.isdigit() else f"row_{i+1}"
                    
                    # 제목 및 링크 추출 (두 번째 셀)
                    subject_cell = cells[1]
                    title_link = subject_cell.find('a')
                    
                    if not title_link:
                        continue
                    
                    title = title_link.get_text(strip=True)
                    href = title_link.get('href', '')
                    
                    if not title or not href:
                        continue
                    
                    # 절대 URL 생성
                    detail_url = urljoin(self.base_url, href)
                    
                    # 메타 정보 추출 (작성자, 날짜, 조회수)
                    author = "관리자"
                    date = ""
                    view_count = ""
                    
                    # 그누보드5 구조에서 메타 정보 추출
                    meta_area = subject_cell.find('ul', class_='bo_tit_ul3')
                    if meta_area:
                        meta_text = meta_area.get_text()
                        
                        # 작성자 추출
                        author_span = meta_area.find('span', class_='bo_names')
                        if author_span:
                            author = author_span.get_text(strip=True)
                        
                        # 날짜 추출 (시계 아이콘 뒤)
                        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', meta_text)
                        if date_match:
                            date = date_match.group(1)
                        
                        # 조회수 추출 (눈 아이콘 뒤)
                        view_match = re.search(r'(\d+)$', meta_text.strip())
                        if view_match:
                            view_count = view_match.group(1)
                    
                    # 카테고리는 공지/일반으로 구분
                    category = "공지사항" if is_notice else "일반공고"
                    
                    # 첨부파일 여부 확인 (네 번째 셀)
                    attachment_count = 0
                    if len(cells) > 3:
                        attachment_cell = cells[3]
                        if attachment_cell.find('i', class_='fa-file') or attachment_cell.find('img'):
                            attachment_count = 1
                    
                    announcement = {
                        'number': number,
                        'category': category,
                        'title': title,
                        'url': detail_url,
                        'date': date,
                        'author': author,
                        'view_count': view_count,
                        'attachment_count': attachment_count
                    }
                    
                    announcements.append(announcement)
                    logger.info(f"공고 추가: [{number}] {title[:50]}...")
                    
                except Exception as e:
                    logger.error(f"공고 파싱 중 오류 (행 {i}): {e}")
                    continue
            
            logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
            return announcements
            
        except Exception as e:
            logger.error(f"목록 페이지 파싱 실패: {e}")
            return announcements
    
    def parse_detail_page(self, html_content: str) -> dict:
        """상세 페이지 파싱 - 그누보드5 구조"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출
        title = ""
        title_elem = soup.find('h2', id='bo_v_title')
        if title_elem:
            title = title_elem.get_text(strip=True)
        
        if not title:
            # 대체 제목 추출
            title_selectors = ['h1', 'h2', '.page_title', '.title']
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem and len(title_elem.get_text(strip=True)) > 5:
                    title = title_elem.get_text(strip=True)
                    break
        
        if not title:
            title = "제목 없음"
        
        # 본문 내용 추출
        content = ""
        
        # 그누보드5 본문 영역
        content_elem = soup.find('div', id='bo_v_con')
        if content_elem:
            content = self.h.handle(str(content_elem))
        
        if not content or len(content.strip()) < 50:
            # 대체 본문 영역 찾기
            content_selectors = [
                '#bo_v_atc',
                '.view_content',
                '.content',
                '.bo_content'
            ]
            
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem and len(content_elem.get_text(strip=True)) > 50:
                    content = self.h.handle(str(content_elem))
                    break
        
        # 작성자 추출
        author = "관리자"
        author_elem = soup.select_one('#bo_v_info .profile_info .sv_member')
        if author_elem:
            author = author_elem.get_text(strip=True)
        
        # 날짜 추출
        date = ""
        date_patterns = [
            r'(\d{4}-\d{2}-\d{2})',
            r'(\d{4}\.\d{2}\.\d{2})',
            r'(\d{4}/\d{2}/\d{2})'
        ]
        
        page_text = soup.get_text()
        for pattern in date_patterns:
            date_match = re.search(pattern, page_text)
            if date_match:
                date = date_match.group(1)
                break
        
        # 첨부파일 추출
        attachments = self._extract_attachments_from_detail(soup)
        
        return {
            'title': title,
            'content': content,
            'date': date,
            'author': author,
            'attachments': attachments
        }
    
    def _extract_attachments_from_detail(self, soup: BeautifulSoup) -> list:
        """상세 페이지에서 첨부파일 정보 추출"""
        attachments = []
        
        try:
            # 1. 이미지 첨부파일 추출 (#bo_v_img 영역)
            img_section = soup.find('div', id='bo_v_img')
            if img_section:
                # 이미지 링크에서 파일명 추출 (view_image.php 링크 활용)
                img_links = img_section.find_all('a', href=re.compile(r'view_image\.php'))
                for link in img_links:
                    href = link.get('href', '')
                    # fn= 파라미터에서 파일명 추출
                    fn_match = re.search(r'fn=([^&]+)', href)
                    if fn_match:
                        filename = fn_match.group(1)
                        # 직접 파일 경로로 접근 (view_image.php 대신)
                        image_url = f"{self.base_url}/data/file/notice/{filename}"
                        
                        attachment = {
                            'filename': filename,
                            'url': image_url,
                            'type': 'image'
                        }
                        attachments.append(attachment)
                        logger.info(f"이미지 첨부파일 발견: {filename}")
                
                # 추가로 img 태그에서도 직접 추출 (썸네일에서 원본 추출)
                images = img_section.find_all('img')
                for img in images:
                    src = img.get('src', '')
                    if src and '/data/file/' in src and 'thumb-' in src:
                        # 썸네일에서 원본 파일명 추출: thumb-{해시}_크기.jpg -> {해시}.jpg
                        thumb_match = re.search(r'thumb-([^_]+)_\d+x\d+\.(\w+)', src)
                        if thumb_match:
                            hash_code = thumb_match.group(1)
                            extension = thumb_match.group(2)
                            filename = f"{hash_code}.{extension}"
                            
                            # 중복 확인
                            if not any(att['filename'] == filename for att in attachments):
                                image_url = f"{self.base_url}/data/file/notice/{filename}"
                                
                                attachment = {
                                    'filename': filename,
                                    'url': image_url,
                                    'type': 'image'
                                }
                                attachments.append(attachment)
                                logger.info(f"썸네일에서 원본 이미지 추출: {filename}")
            
            # 2. 본문 내 이미지 추출
            content_section = soup.find('div', id='bo_v_con')
            if content_section:
                content_images = content_section.find_all('img')
                for img in content_images:
                    src = img.get('src', '')
                    if src and '/data/file/' in src:
                        # 썸네일인 경우 원본 파일명 추출
                        if 'thumb-' in src:
                            thumb_match = re.search(r'thumb-([^_]+)_\d+x\d+\.(\w+)', src)
                            if thumb_match:
                                hash_code = thumb_match.group(1)
                                extension = thumb_match.group(2)
                                filename = f"{hash_code}.{extension}"
                            else:
                                continue
                        else:
                            # 원본 이미지인 경우 파일명 그대로 사용
                            filename = os.path.basename(src)
                        
                        # 중복 확인
                        if not any(att['filename'] == filename for att in attachments):
                            # 직접 파일 경로로 접근
                            image_url = f"{self.base_url}/data/file/notice/{filename}"
                            
                            attachment = {
                                'filename': filename,
                                'url': image_url,
                                'type': 'image'
                            }
                            attachments.append(attachment)
                            logger.info(f"본문 이미지 첨부파일 발견: {filename}")
            
            # 3. 관련 링크 추출 (#bo_v_link 영역)
            link_section = soup.find('section', id='bo_v_link')
            if link_section:
                links = link_section.find_all('a')
                for i, link in enumerate(links):
                    href = link.get('href', '')
                    link_text = link.get_text(strip=True)
                    
                    if href and href.startswith('http'):
                        # 외부 링크를 텍스트 파일로 저장
                        link_filename = f"관련링크_{i+1}.txt"
                        
                        attachment = {
                            'filename': link_filename,
                            'url': href,
                            'type': 'link',
                            'link_text': link_text
                        }
                        attachments.append(attachment)
                        logger.info(f"관련 링크 발견: {link_text} -> {href}")
            
            # 4. 일반 첨부파일 링크 찾기 (혹시 있을 경우)
            download_links = soup.find_all('a', href=re.compile(r'download|file_download'))
            for link in download_links:
                href = link.get('href', '')
                link_text = link.get_text(strip=True)
                
                if href:
                    file_url = urljoin(self.base_url, href)
                    filename = link_text if link_text else f"첨부파일_{len(attachments)+1}"
                    
                    attachment = {
                        'filename': filename,
                        'url': file_url,
                        'type': 'file'
                    }
                    attachments.append(attachment)
                    logger.info(f"첨부파일 링크 발견: {filename}")
            
        except Exception as e:
            logger.error(f"첨부파일 추출 중 오류: {e}")
        
        logger.info(f"총 {len(attachments)}개 첨부파일 추출 완료")
        return attachments
    
    def download_file(self, file_url: str, save_path: str, attachment: dict = None, **kwargs) -> bool:
        """Liquor Festa 특화 파일 다운로드"""
        try:
            # attachment 딕셔너리에서 타입과 기타 정보 추출
            if attachment:
                attachment_type = attachment.get('type', 'file')
                link_text = attachment.get('link_text', '')
            else:
                attachment_type = kwargs.get('type', 'file')
                link_text = kwargs.get('link_text', '')
            
            if attachment_type == 'link':
                # 외부 링크를 텍스트 파일로 저장
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write(f"관련 링크: {link_text}\n")
                    f.write(f"URL: {file_url}\n")
                    f.write(f"수집일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                
                logger.info(f"관련 링크 저장 완료: {save_path}")
                return True
            
            # 일반 파일 또는 이미지 다운로드
            logger.info(f"파일 다운로드 시도: {save_path}")
            
            headers = {
                'Referer': self.list_url,
                'Accept': '*/*'
            }
            
            response = self.session.get(file_url, headers=headers, timeout=self.timeout, stream=True)
            response.raise_for_status()
            
            # Content-Type 확인
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' in content_type and attachment_type != 'link':
                logger.error(f"HTML 페이지 반환됨 - 다운로드 실패: {content_type}")
                return False
            
            # 파일명 추출 및 저장
            actual_filename = self._extract_filename_from_response(response, save_path)
            
            # 파일 저장
            with open(actual_filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(actual_filename)
            logger.info(f"파일 다운로드 완료: {actual_filename} ({file_size:,} bytes)")
            
            return True
            
        except Exception as e:
            logger.error(f"파일 다운로드 실패 {save_path}: {e}")
            return False
    
    def _extract_filename_from_response(self, response, default_path):
        """응답 헤더에서 파일명 추출"""
        save_dir = os.path.dirname(default_path)
        original_filename = os.path.basename(default_path)
        
        content_disposition = response.headers.get('Content-Disposition', '')
        
        if content_disposition:
            # RFC 5987 형식 처리
            rfc5987_match = re.search(r"filename\*=([^']*)'([^']*)'(.+)", content_disposition)
            if rfc5987_match:
                encoding, lang, encoded_filename = rfc5987_match.groups()
                try:
                    decoded_filename = unquote(encoded_filename, encoding=encoding or 'utf-8')
                    clean_filename = self.sanitize_filename(decoded_filename)
                    return os.path.join(save_dir, clean_filename)
                except Exception as e:
                    logger.debug(f"RFC 5987 디코딩 실패: {e}")
            
            # 일반 filename 파라미터 처리
            filename_match = re.search(r'filename[^;=\n]*=([\'"]*)(.*?)\1', content_disposition)
            if filename_match:
                raw_filename = filename_match.group(2)
                
                # 한글 파일명 다단계 디코딩
                for encoding in ['utf-8', 'euc-kr', 'cp949']:
                    try:
                        if encoding == 'utf-8':
                            decoded = raw_filename.encode('latin-1').decode('utf-8')
                        else:
                            decoded = raw_filename.encode('latin-1').decode(encoding)
                        
                        if decoded and len(decoded) > 0:
                            clean_filename = self.sanitize_filename(decoded)
                            return os.path.join(save_dir, clean_filename)
                    except:
                        continue
        
        # 기본 파일명 사용
        return os.path.join(save_dir, self.sanitize_filename(original_filename))
    
    def sanitize_filename(self, filename: str) -> str:
        """파일명 정리"""
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = filename.replace('\n', '').replace('\t', '').strip()
        return filename[:200]  # 파일명 길이 제한

def test_liquorfesta_scraper(pages=3):
    """Liquor Festa 스크래퍼 테스트"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    scraper = EnhancedLiquorFestaScraper()
    output_dir = "output/liquorfesta"
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"Liquor Festa 스크래퍼 테스트 시작 - {pages}페이지")
    success = scraper.scrape_pages(max_pages=pages, output_base=output_dir)
    
    logger.info(f"\n{'='*50}")
    logger.info("테스트 결과 요약")
    logger.info(f"{'='*50}")
    logger.info(f"스크래핑 성공: {success}")
    
    # 결과 폴더에서 통계 계산
    if os.path.exists(output_dir):
        announcement_dirs = [d for d in os.listdir(output_dir) if os.path.isdir(os.path.join(output_dir, d))]
        total_announcements = len(announcement_dirs)
        
        total_files = 0
        for ann_dir in announcement_dirs:
            att_dir = os.path.join(output_dir, ann_dir, "attachments")
            if os.path.exists(att_dir):
                files = [f for f in os.listdir(att_dir) if os.path.isfile(os.path.join(att_dir, f))]
                total_files += len(files)
        
        logger.info(f"처리된 공고: {total_announcements}개")
        logger.info(f"총 파일 수: {total_files}개")
    
    return success

if __name__ == "__main__":
    test_liquorfesta_scraper(3)