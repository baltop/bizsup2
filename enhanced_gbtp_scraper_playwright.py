# -*- coding: utf-8 -*-
"""
경북테크노파크 Playwright 스크래퍼 - Enhanced 버전
향상된 아키텍처와 중복 체크, 로깅 지원
"""

import os
import time
import re
import html2text
import logging
from pathlib import Path
from urllib.parse import urljoin
from enhanced_base_scraper import EnhancedBaseScraper
from typing import Dict, List, Any, Optional
import json

logger = logging.getLogger(__name__)

class EnhancedGBTPPlaywrightScraper(EnhancedBaseScraper):
    """경북테크노파크 스크래퍼 - Enhanced Playwright 버전"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://gbtp.or.kr"
        self.list_url = "https://gbtp.or.kr/user/board.do?bbsId=BBSMSTR_000000000023"
        
        # Playwright 관련 속성
        self.playwright = None
        self.browser = None
        self.page = None
        
        # HTML to text 변환기 (Playwright 전용)
        self.h = html2text.HTML2Text()
        self.h.ignore_links = False
        self.h.ignore_images = False
        
        # 브라우저 옵션
        self.browser_options = {
            'headless': True,
            'timeout': 30000,
            'args': ['--ignore-certificate-errors', '--disable-web-security']
        }
        
        # 대기 시간 설정
        self.page_load_timeout = 30000
        self.element_timeout = 10000
        
    def _init_playwright(self) -> bool:
        """Playwright 초기화"""
        try:
            from playwright.sync_api import sync_playwright
            
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=self.browser_options['headless'],
                args=self.browser_options['args']
            )
            self.page = self.browser.new_page()
            
            # 사용자 에이전트 설정
            self.page.set_extra_http_headers({
                'User-Agent': self.headers['User-Agent']
            })
            
            logger.info("Playwright 초기화 완료")
            return True
            
        except ImportError:
            logger.error("Playwright가 설치되지 않았습니다. 'uv add playwright' 후 'playwright install chromium' 실행")
            return False
        except Exception as e:
            logger.error(f"Playwright 초기화 실패: {e}")
            return False
    
    def _close_playwright(self):
        """Playwright 정리"""
        try:
            if self.page:
                self.page.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            logger.info("Playwright 정리 완료")
        except Exception as e:
            logger.warning(f"Playwright 정리 중 오류: {e}")
    
    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 반환"""
        if page_num == 1:
            return self.list_url
        return f"{self.list_url}&pageIndex={page_num}"
    
    def parse_list_page(self, page_num: int) -> List[Dict[str, Any]]:
        """Playwright로 목록 페이지 파싱 - Enhanced 버전"""
        try:
            url = self.get_list_url(page_num)
            logger.info(f"목록 페이지 로드 중: {url}")
            
            # 페이지 로드
            self.page.goto(url, wait_until="networkidle", timeout=self.page_load_timeout)
            
            # 테이블 로드 대기
            self.page.wait_for_selector('table.board-list, table', timeout=self.element_timeout)
            
            announcements = []
            
            # 테이블 행들 가져오기
            rows = self.page.query_selector_all('table tbody tr, table tr')
            logger.debug(f"{len(rows)}개 행 발견")
            
            for i, row in enumerate(rows):
                try:
                    announcement = self._parse_table_row(row, i)
                    if announcement:
                        announcements.append(announcement)
                        
                except Exception as e:
                    logger.error(f"행 {i} 파싱 중 오류: {e}")
                    continue
            
            logger.info(f"페이지 {page_num}에서 {len(announcements)}개 공고 파싱 완료")
            return announcements
            
        except Exception as e:
            logger.error(f"목록 페이지 파싱 실패: {e}")
            return []
    
    def _parse_table_row(self, row, row_index: int) -> Optional[Dict[str, Any]]:
        """테이블 행 파싱"""
        cells = row.query_selector_all('td')
        if len(cells) < 6:  # 최소 컬럼 수 체크
            return None
        
        # 번호 (첫 번째 td)
        number_cell = cells[0]
        number = number_cell.inner_text().strip()
        
        # 숫자가 아니면 헤더 행이므로 스킵
        if not number.isdigit():
            return None
        
        # 상태 (두 번째 td)
        status_cell = cells[1]
        status = status_cell.inner_text().strip()
        
        # 제목 및 링크 (세 번째 td)
        title_cell = cells[2]
        title_link = title_cell.query_selector('a')
        if not title_link:
            return None
        
        title = title_link.inner_text().strip()
        onclick = title_link.get_attribute('onclick') or ''
        
        # onclick 속성에서 파라미터 추출
        if onclick:
            match = re.search(r"fn_detail\('([^']+)',\s*'([^']+)'\)", onclick)
            if match:
                bbs_seq = match.group(1)
                page_index = match.group(2)
            else:
                logger.warning(f"onclick 파싱 실패: {onclick}")
                return None
        else:
            logger.warning(f"onclick 속성 없음: {title}")
            return None
        
        # 추가 정보 추출
        period = cells[3].inner_text().strip() if len(cells) > 3 else ""
        hits = cells[4].inner_text().strip() if len(cells) > 4 else ""
        
        # 첨부파일 여부
        file_cell = cells[5] if len(cells) > 5 else None
        has_attachment = False
        if file_cell:
            file_icon = file_cell.query_selector('i.fa-file-download, i.far.fa-file-download')
            has_attachment = bool(file_icon)
        
        # 작성자 (일곱 번째 td, 있는 경우)
        writer = ""
        if len(cells) > 6:
            writer = cells[6].inner_text().strip()
        
        return {
            'number': number,
            'title': title,
            'bbs_seq': bbs_seq,
            'page_index': page_index,
            'status': status,
            'period': period,
            'hits': hits,
            'writer': writer,
            'has_attachment': has_attachment,
            'onclick': onclick,
            'url': f"javascript:fn_detail('{bbs_seq}', '{page_index}')"  # 가상 URL
        }
    
    def parse_detail_page(self, announcement: Dict[str, Any]) -> Dict[str, Any]:
        """상세 페이지 파싱 - Enhanced 버전"""
        try:
            logger.info(f"상세 페이지 로드 중: {announcement['title']}")
            
            # JavaScript 함수 실행
            self.page.evaluate(f"fn_detail('{announcement['bbs_seq']}', '{announcement['page_index']}')")
            
            # 페이지 내용 변경 대기
            time.sleep(2)
            
            # 본문 내용 추출
            content = self._extract_detail_content()
            
            # 첨부파일 추출
            attachments = self._extract_detail_attachments()
            
            logger.debug(f"상세 페이지 파싱 완료 - 내용: {len(content)}자, 첨부파일: {len(attachments)}개")
            
            return {
                'content': content,
                'attachments': attachments
            }
            
        except Exception as e:
            logger.error(f"상세 페이지 파싱 실패: {e}")
            return {'content': '', 'attachments': []}
    
    def _extract_detail_content(self) -> str:
        """상세 페이지 본문 추출"""
        content_selectors = [
            '#contentDiv',
            '.board-view .view-content',
            '.board-view .content',
            '.view-content',
            '.content-area',
            '.board-content'
        ]
        
        content_element = None
        for selector in content_selectors:
            content_element = self.page.query_selector(selector)
            if content_element:
                break
        
        if content_element:
            content_html = content_element.inner_html()
            return self.h.handle(content_html)
        else:
            # 전체 페이지에서 추출 (fallback)
            logger.warning("본문 컨테이너를 찾지 못해 전체 페이지에서 추출")
            body_html = self.page.query_selector('body').inner_html()
            return self.h.handle(body_html)
    
    def _extract_detail_attachments(self) -> List[Dict[str, Any]]:
        """상세 페이지 첨부파일 추출"""
        attachments = []
        
        # 첨부파일 링크 찾기
        download_links = self.page.query_selector_all(
            'a[onclick*="fn_egov_downFile"], a[href*="fn_egov_downFile"], .view_file_download'
        )
        
        for link in download_links:
            try:
                onclick = link.get_attribute('onclick') or ''
                href = link.get_attribute('href') or ''
                
                # fn_egov_downFile('atchFileId', 'fileSn') 패턴 추출
                pattern = r"fn_egov_downFile\('([^']+)',\s*'([^']+)'\)"
                match = re.search(pattern, onclick + href)
                
                if match:
                    atch_file_id = match.group(1)
                    file_sn = match.group(2)
                    
                    # 다운로드 URL 생성
                    download_url = f"{self.base_url}/cmm/fms/FileDown.do?atchFileId={atch_file_id}&fileSn={file_sn}"
                    
                    # 파일명 추출 및 정리
                    file_name = link.inner_text().strip()
                    file_name = re.sub(r'^\s*\[?붙임\d*\]?\s*', '', file_name).strip()
                    
                    if not file_name or file_name in ['다운로드', '첨부파일', '']:
                        file_name = f"attachment_{file_sn}"
                    
                    attachments.append({
                        'name': file_name,
                        'url': download_url,
                        'atch_file_id': atch_file_id,
                        'file_sn': file_sn
                    })
                    
            except Exception as e:
                logger.error(f"첨부파일 링크 파싱 오류: {e}")
                continue
        
        return attachments
    
    def download_file(self, url: str, save_path: str, attachment_info: Dict[str, Any] = None) -> bool:
        """Enhanced 파일 다운로드 - Playwright와 HTTP 방식 모두 지원"""
        try:
            logger.info(f"파일 다운로드 시작: {url}")
            
            # 디렉토리 생성
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # Playwright 다운로드 시도
            if attachment_info and 'atch_file_id' in attachment_info:
                success = self._download_with_playwright(attachment_info, save_path)
                if success:
                    return True
            
            # HTTP 다운로드 fallback
            return self._download_with_http(url, save_path)
            
        except Exception as e:
            logger.error(f"파일 다운로드 실패 {url}: {e}")
            return False
    
    def _download_with_playwright(self, attachment_info: Dict[str, Any], save_path: str) -> bool:
        """Playwright JavaScript 실행으로 파일 다운로드"""
        try:
            atch_file_id = attachment_info['atch_file_id']
            file_sn = attachment_info['file_sn']
            
            logger.debug(f"Playwright 다운로드 시도: {atch_file_id}/{file_sn}")
            
            # JavaScript 함수로 다운로드
            with self.page.expect_download(timeout=30000) as download_info:
                self.page.evaluate(f"fn_egov_downFile('{atch_file_id}', '{file_sn}')")
            
            download = download_info.value
            download.save_as(save_path)
            
            file_size = os.path.getsize(save_path)
            logger.info(f"Playwright 다운로드 완료: {save_path} ({file_size:,} bytes)")
            return True
            
        except Exception as e:
            logger.warning(f"Playwright 다운로드 실패: {e}")
            return False
    
    def _download_with_http(self, url: str, save_path: str) -> bool:
        """HTTP 직접 요청으로 파일 다운로드"""
        try:
            logger.debug(f"HTTP 다운로드 시도: {url}")
            
            # 세션에 Referer 헤더 추가
            headers = self.headers.copy()
            headers['Referer'] = self.base_url
            
            response = self.session.get(
                url, 
                headers=headers, 
                stream=True, 
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            
            # 실제 파일명 추출
            actual_filename = self._extract_filename(response, save_path)
            if actual_filename != save_path:
                save_path = actual_filename
            
            # 파일 저장
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(save_path)
            logger.info(f"HTTP 다운로드 완료: {save_path} ({file_size:,} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"HTTP 다운로드 실패: {e}")
            return False
    
    def process_announcement(self, announcement: Dict[str, Any], index: int, output_base: str = 'output'):
        """Enhanced 공고 처리 - Playwright 버전"""
        logger.info(f"공고 처리 중 {index}: {announcement['title']}")
        
        # 폴더 생성
        folder_title = self.sanitize_filename(announcement['title'])[:50]
        folder_name = f"{index:03d}_{folder_title}"
        folder_path = os.path.join(output_base, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        
        # 상세 페이지 내용 가져오기 (Playwright 방식)
        detail = self.parse_detail_page(announcement)
        
        logger.debug(f"상세 내용 길이: {len(detail['content'])}, 첨부파일: {len(detail['attachments'])}")
        
        # 메타 정보 생성
        meta_info = self._create_meta_info_playwright(announcement)
        
        # 본문 저장
        content_path = os.path.join(folder_path, 'content.md')
        with open(content_path, 'w', encoding='utf-8') as f:
            f.write(meta_info + detail['content'])
        
        logger.info(f"내용 저장 완료: {content_path}")
        
        # 첨부파일 다운로드
        self._download_attachments(detail['attachments'], folder_path)
        
        # 처리된 제목으로 추가
        self.add_processed_title(announcement['title'])
        
        # 목록 페이지로 돌아가기
        self.page.goto(self.get_list_url(1), wait_until="networkidle")
        
        # 요청 간 대기
        if self.delay_between_requests > 0:
            time.sleep(self.delay_between_requests)
    
    def _create_meta_info_playwright(self, announcement: Dict[str, Any]) -> str:
        """Playwright 버전 메타 정보 생성"""
        meta_lines = [f"# {announcement['title']}", ""]
        
        # GBTP 특화 메타 정보
        meta_fields = [
            ('writer', '작성자'),
            ('status', '상태'), 
            ('period', '접수기간'),
            ('hits', '조회수'),
            ('number', '번호')
        ]
        
        for field, label in meta_fields:
            if field in announcement and announcement[field]:
                meta_lines.append(f"**{label}**: {announcement[field]}")
        
        meta_lines.extend([
            f"**원본 사이트**: GBTP (경북테크노파크)",
            f"**BBS Seq**: {announcement.get('bbs_seq', 'N/A')}",
            "",
            "---",
            ""
        ])
        
        return "\n".join(meta_lines)
    
    def _get_page_announcements(self, page_num: int) -> List[Dict[str, Any]]:
        """페이지별 공고 목록 가져오기 - Playwright 버전"""
        return self.parse_list_page(page_num)
    
    def scrape_pages(self, max_pages: int = 4, output_base: str = 'output'):
        """Enhanced 페이지 스크래핑 - Playwright 지원"""
        # Playwright 초기화
        if not self._init_playwright():
            logger.error("Playwright 초기화 실패 - 스크래핑 중단")
            return
        
        try:
            # 처리된 제목 목록 로드
            self.load_processed_titles(output_base)
            
            logger.info(f"GBTP Playwright 스크래핑 시작: 최대 {max_pages}페이지")
            
            announcement_count = 0
            processed_count = 0
            early_stop = False
            stop_reason = ""
            
            for page_num in range(1, max_pages + 1):
                logger.info(f"페이지 {page_num} 처리 중")
                
                try:
                    # 목록 가져오기 및 파싱
                    announcements = self._get_page_announcements(page_num)
                    
                    if not announcements:
                        logger.warning(f"페이지 {page_num}에 공고가 없습니다")
                        stop_reason = "공고 없음"
                        break
                    
                    logger.info(f"페이지 {page_num}에서 {len(announcements)}개 공고 발견")
                    
                    # 새로운 공고만 필터링 및 중복 임계값 체크
                    new_announcements, should_stop = self.filter_new_announcements(announcements)
                    
                    # 중복 임계값 도달시 조기 종료
                    if should_stop:
                        logger.info(f"중복 공고 {self.duplicate_threshold}개 연속 발견으로 조기 종료")
                        early_stop = True
                        stop_reason = f"중복 {self.duplicate_threshold}개 연속"
                        break
                    
                    # 새로운 공고가 없으면 조기 종료 (연속된 페이지에서)
                    if not new_announcements and page_num > 1:
                        logger.info("새로운 공고가 없어 스크래핑 조기 종료")
                        early_stop = True
                        stop_reason = "새로운 공고 없음"
                        break
                    
                    # 각 공고 처리
                    for ann in new_announcements:
                        announcement_count += 1
                        processed_count += 1
                        self.process_announcement(ann, announcement_count, output_base)
                    
                    # 페이지 간 대기
                    if page_num < max_pages and self.delay_between_pages > 0:
                        time.sleep(self.delay_between_pages)
                    
                except Exception as e:
                    logger.error(f"페이지 {page_num} 처리 중 오류: {e}")
                    stop_reason = f"오류: {e}"
                    break
            
            # 처리된 제목 목록 저장
            self.save_processed_titles()
            
            if early_stop:
                logger.info(f"GBTP 스크래핑 완료: 총 {processed_count}개 새로운 공고 처리 (조기종료: {stop_reason})")
            else:
                logger.info(f"GBTP 스크래핑 완료: 총 {processed_count}개 새로운 공고 처리")
            
        except Exception as e:
            logger.error(f"스크래핑 중 치명적 오류: {e}")
        finally:
            self._close_playwright()


# 하위 호환성을 위한 별칭
GBTPPlaywrightScraper = EnhancedGBTPPlaywrightScraper

if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    scraper = EnhancedGBTPPlaywrightScraper()
    scraper.scrape_pages(max_pages=1, output_base='output/gbtp_enhanced')