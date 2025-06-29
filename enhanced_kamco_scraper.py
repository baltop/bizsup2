# -*- coding: utf-8 -*-
"""
한국자산관리공사(KAMCO) Enhanced 스크래퍼
표준 테이블 구조 기반의 게시판 스크래핑
"""

import re
import os
import time
from urllib.parse import urljoin, urlparse, unquote
from bs4 import BeautifulSoup
import logging
from enhanced_base_scraper import StandardTableScraper
from playwright.sync_api import sync_playwright
import shutil

logger = logging.getLogger(__name__)

class EnhancedKamcoScraper(StandardTableScraper):
    """한국자산관리공사(KAMCO) 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        
        # 기본 설정
        self.base_url = "https://www.kamco.or.kr"
        self.list_url = "https://www.kamco.or.kr/portal/bbs/list.do?ptIdx=380&mId=0701010000"
        
        # 사이트별 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1
        
        # 테이블 구조 설정
        self.table_selector = "table"
        self.tbody_selector = "tbody"
        self.row_selector = "tr"
        
        # 페이지네이션 설정
        self.items_per_page = 15
        
        logger.info("KAMCO 스크래퍼 초기화 완료")

    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 생성"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.list_url}&page={page_num}"

    def parse_list_page(self, html_content: str) -> list:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 테이블 찾기
        table = soup.find('table')
        if not table:
            logger.warning("테이블을 찾을 수 없습니다")
            return announcements
        
        # tbody 찾기 (없으면 table 전체 사용)
        tbody = table.find('tbody')
        rows = tbody.find_all('tr') if tbody else table.find_all('tr')
        
        # 헤더 행 제외
        data_rows = [row for row in rows if len(row.find_all('td')) >= 5]
        
        for i, row in enumerate(data_rows):
            try:
                cells = row.find_all('td')
                if len(cells) < 6:  # 번호, 제목, 담당부서, 첨부, 등록일, 조회
                    continue
                
                # 번호 (첫 번째 셀) - 공지 처리 포함
                number_cell = cells[0]
                number = self._process_notice_detection(number_cell, i)
                
                # 제목 (두 번째 셀)
                title_cell = cells[1]
                title_link = title_cell.find('a')
                if not title_link:
                    continue
                
                title = title_link.get_text(strip=True)
                href = title_link.get('href', '')
                
                # 상세 URL 처리 - onclick 이벤트 우선 확인
                onclick = title_link.get('onclick', '')
                if onclick:
                    # goTo.view('list','18905','380','0701010000') 패턴 파싱
                    onclick_match = re.search(r"goTo\.view\(['\"]([^'\"]+)['\"],\s*['\"](\d+)['\"],\s*['\"](\d+)['\"],\s*['\"]([^'\"]+)['\"]", onclick)
                    if onclick_match:
                        list_type, bidx, ptidx, mid = onclick_match.groups()
                        detail_url = f"{self.base_url}/portal/bbs/view.do?mId={mid}&bIdx={bidx}&ptIdx={ptidx}"
                    else:
                        logger.warning(f"onclick 파싱 실패: {onclick}")
                        continue
                elif href and href != '#':
                    if href.startswith('javascript:'):
                        # JavaScript 함수에서 파라미터 추출
                        js_match = re.search(r"view\.do\?([^'\"]+)", href)
                        if js_match:
                            detail_url = f"{self.base_url}/portal/bbs/view.do?{js_match.group(1)}"
                        else:
                            logger.warning(f"JavaScript 링크 파싱 실패: {href}")
                            continue
                    else:
                        detail_url = urljoin(self.base_url, href)
                else:
                    logger.warning(f"유효하지 않은 링크 - href: {href}, onclick: {onclick}")
                    continue
                
                # 담당부서 (세 번째 셀)
                department = cells[2].get_text(strip=True)
                
                # 첨부파일 여부 (네 번째 셀)
                attachment_cell = cells[3]
                has_attachment = bool(attachment_cell.find('img'))
                
                # 등록일 (다섯 번째 셀)
                date = cells[4].get_text(strip=True)
                
                # 조회수 (여섯 번째 셀)
                views = cells[5].get_text(strip=True)
                
                announcement = {
                    'number': number,
                    'title': title,
                    'url': detail_url,
                    'department': department,
                    'has_attachment': has_attachment,
                    'date': date,
                    'views': views,
                    'attachments': []
                }
                
                announcements.append(announcement)
                logger.info(f"공고 추가: [{number}] {title}")
                
            except Exception as e:
                logger.error(f"행 파싱 중 오류 발생: {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
        return announcements

    def _process_notice_detection(self, cell, row_index=0):
        """공지 이미지 감지 및 번호 처리"""
        number = cell.get_text(strip=True)
        is_notice = False
        
        # 이미지에서 공지 감지
        notice_imgs = cell.find_all('img')
        for img in notice_imgs:
            src = img.get('src', '')
            alt = img.get('alt', '')
            if '공지' in src or '공지' in alt or 'notice' in src.lower():
                is_notice = True
                break
        
        # 텍스트에서 공지 감지
        if '공지' in number:
            is_notice = True
        
        # 번호 결정
        if is_notice:
            return "공지"
        elif not number or number.isspace():
            return f"row_{row_index + 1}"
        else:
            return number

    def parse_detail_page(self, html_content: str) -> dict:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출
        title_elem = soup.find('th', string='제목')
        title = ""
        if title_elem and title_elem.find_next_sibling('td'):
            title = title_elem.find_next_sibling('td').get_text(strip=True)
        
        # 본문 내용 추출 - 테이블에서 본문 영역 찾기
        content = ""
        
        # 방법 1: 본문이 포함된 큰 셀 찾기
        content_cells = soup.find_all('td', class_=lambda x: x is None)
        for cell in content_cells:
            cell_text = cell.get_text(strip=True)
            if len(cell_text) > 100 and ('공고' in cell_text or '신청' in cell_text or '모집' in cell_text):
                content = self.h.handle(str(cell)).strip()
                break
        
        # 방법 2: 긴 텍스트가 포함된 td 찾기
        if not content:
            for td in soup.find_all('td'):
                td_text = td.get_text(strip=True)
                if len(td_text) > 50:
                    content = self.h.handle(str(td)).strip()
                    break
        
        # 첨부파일 추출
        attachments = self._extract_attachments(soup)
        
        return {
            'title': title,
            'content': content,
            'attachments': attachments
        }

    def _extract_attachments(self, soup: BeautifulSoup) -> list:
        """첨부파일 정보 추출"""
        attachments = []
        
        # 첨부파일 링크 찾기
        file_links = soup.find_all('a', href=True)
        
        for link in file_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # 파일 다운로드 링크인지 확인
            if ('[' in text and 'Byte]' in text) or any(ext in text.lower() for ext in ['.hwp', '.pdf', '.doc', '.xls', '.jpg', '.png', '.zip']):
                # 파일명과 크기 분리
                if '[' in text and ']' in text:
                    parts = text.split('[')
                    filename = parts[0].strip()
                    size_part = parts[1].split(']')[0].strip() if len(parts) > 1 else ""
                else:
                    filename = text
                    size_part = ""
                
                # 다운로드 URL 구성 - onclick 이벤트 우선 확인
                onclick = link.get('onclick', '')
                if onclick:
                    # fn_egov_downFile('FILE_000000000009941','0') 패턴 파싱
                    onclick_match = re.search(r"fn_egov_downFile\(['\"]([^'\"]+)['\"],\s*['\"]([^'\"]*)['\"]", onclick)
                    if onclick_match:
                        file_id, param = onclick_match.groups()
                        download_url = f"{self.base_url}/common/fms/FileDown.do?atchFileId={file_id}&fileSn={param}"
                    else:
                        logger.warning(f"onclick 파일 다운로드 파싱 실패: {onclick}")
                        continue
                elif href.startswith('javascript:'):
                    # JavaScript 다운로드 함수 처리
                    js_match = re.search(r"download\(['\"]([^'\"]+)['\"]", href)
                    if js_match:
                        file_id = js_match.group(1)
                        download_url = f"{self.base_url}/portal/file/download.do?fileId={file_id}"
                    else:
                        logger.warning(f"JavaScript 다운로드 링크 파싱 실패: {href}")
                        continue
                elif href.startswith('http'):
                    download_url = href
                else:
                    download_url = urljoin(self.base_url, href)
                
                attachment = {
                    'filename': filename,
                    'size': size_part,
                    'url': download_url
                }
                
                attachments.append(attachment)
                logger.info(f"첨부파일 발견: {filename} ({size_part})")
        
        return attachments


    def process_announcement_with_browser_download(self, announcement: dict, index: int, save_base_dir: str) -> dict:
        """공고 처리 시 브라우저 다운로드 사용"""
        logger.info(f"공고 처리 중 {save_base_dir}: {announcement['title']}")
        
        # 폴더 생성
        folder_title = self.sanitize_filename(announcement['title'])[:100]
        folder_name = f"{index:03d}_{folder_title}"
        folder_path = os.path.join(save_base_dir, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        
        # 콘텐츠 저장
        content_file = os.path.join(folder_path, "content.md")
        content = f"# {announcement['title']}\n\n"
        
        # 메타데이터 추가
        if announcement.get('date'):
            content += f"**작성일**: {announcement['date']}\n"
        if announcement.get('views'):
            content += f"**조회수**: {announcement['views']}\n"
        content += f"**원본 URL**: {announcement['url']}\n\n"
        content += "---\n"
        
        # 본문 추가
        if announcement.get('content'):
            content += announcement['content']
        
        with open(content_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # 첨부파일이 있는 경우 메타데이터 정보 저장
        if announcement.get('attachments'):
            attachments_dir = os.path.join(folder_path, "attachments")
            os.makedirs(attachments_dir, exist_ok=True)
            
            # 첨부파일 정보를 JSON 파일로 저장
            attachments_info = []
            for attachment in announcement['attachments']:
                attachments_info.append({
                    'filename': attachment.get('filename', 'unknown'),
                    'size': attachment.get('size', ''),
                    'url': attachment.get('url', ''),
                    'note': 'KAMCO 사이트는 세션 인증이 필요하여 직접 다운로드 불가'
                })
            
            # 첨부파일 정보 JSON 저장
            import json
            attachments_file = os.path.join(attachments_dir, "attachments_info.json")
            with open(attachments_file, 'w', encoding='utf-8') as f:
                json.dump(attachments_info, f, ensure_ascii=False, indent=2)
            
            # 첨부파일 정보를 마크다운으로도 저장
            attachments_md = os.path.join(folder_path, "attachments_info.md")
            with open(attachments_md, 'w', encoding='utf-8') as f:
                f.write("# 첨부파일 정보\n\n")
                f.write("**주의**: KAMCO 사이트는 세션 기반 인증이 필요하여 직접 파일 다운로드가 제한됩니다.\n")
                f.write("아래는 파일 메타데이터 정보입니다.\n\n")
                
                for i, attachment in enumerate(attachments_info, 1):
                    f.write(f"## {i}. {attachment['filename']}\n\n")
                    f.write(f"- **파일 크기**: {attachment['size']}\n")
                    f.write(f"- **다운로드 URL**: {attachment['url']}\n")
                    f.write(f"- **상태**: {attachment['note']}\n\n")
            
            logger.info(f"첨부파일 메타데이터 수집 완료: {len(attachments_info)}개 파일")
        
        return {"status": "success", "path": folder_path}


