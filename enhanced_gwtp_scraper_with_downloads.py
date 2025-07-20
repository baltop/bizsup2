#!/usr/bin/env python3
"""
Enhanced GWTP (강원테크노파크) 모집공고 스크래퍼 - 첨부파일 다운로드 수정 버전
URL: https://www.gwtp.or.kr/gwtp/bbsNew_list.php?code=sub01b&keyvalue=sub01
"""

import os
import re
import time
import json
import base64
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
import logging
from playwright.async_api import async_playwright

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GWTPAnnouncementScraperWithDownloads:
    def __init__(self, base_url: str = "https://www.gwtp.or.kr/gwtp/bbsNew_list.php?code=sub01b&keyvalue=sub01"):
        self.base_url = base_url
        self.domain = "https://www.gwtp.or.kr"
        self.output_dir = "output/gwtp"
        self.site_code = "gwtp"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 중복 실행 방지를 위한 JSON 파일 경로
        self.status_file = os.path.join(self.output_dir, f"{self.site_code}_scraping_status.json")
        
        # 세션 설정
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Host': 'www.gwtp.or.kr'
        })
        
    def load_status(self) -> Dict:
        """상태 파일 로드"""
        if os.path.exists(self.status_file):
            with open(self.status_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            'last_run': None,
            'pages_scraped': 0,
            'total_announcements': 0,
            'processed_announcements': [],
            'failed_announcements': []
        }
    
    def save_status(self, status: Dict):
        """상태 파일 저장"""
        status['last_run'] = datetime.now().isoformat()
        with open(self.status_file, 'w', encoding='utf-8') as f:
            json.dump(status, f, ensure_ascii=False, indent=2)
    
    def is_already_processed(self, announcement_id: str) -> bool:
        """이미 처리된 공지사항인지 확인"""
        status = self.load_status()
        return announcement_id in status.get('processed_announcements', [])
    
    def mark_as_processed(self, announcement_id: str):
        """공지사항을 처리 완료로 표시"""
        status = self.load_status()
        if announcement_id not in status.get('processed_announcements', []):
            status['processed_announcements'].append(announcement_id)
            self.save_status(status)
    
    async def extract_announcements_from_page(self, page) -> List[Dict[str, str]]:
        """현재 페이지의 공지사항 목록 추출"""
        announcements = []
        
        try:
            # 테이블 구조 확인
            await page.wait_for_selector('tbody tr', timeout=10000)
            
            # 테이블 행 찾기 (첫 번째 행은 헤더, 나머지는 데이터)
            rows = await page.query_selector_all('tbody tr')
            
            for i, row in enumerate(rows):
                try:
                    cells = await row.query_selector_all('td')
                    if len(cells) >= 6:  # 번호, 제목, 작성자, 등록일, 조회수, 첨부
                        # 공지사항인 경우 처리
                        first_cell = cells[0]
                        first_cell_text = await first_cell.text_content()
                        
                        # 번호 추출
                        if first_cell_text.strip() == "공지":
                            # 공지사항의 경우 제목 셀에서 추가 정보 추출
                            title_cell = cells[1]
                            title_link = await title_cell.query_selector('a')
                            if title_link:
                                title = await title_link.text_content()
                                title = title.strip() if title else ""
                                
                                # 작성자, 등록일, 조회수 추출
                                author = await cells[2].text_content()
                                author = author.strip() if author else ""
                                
                                date = await cells[3].text_content()
                                date = date.strip() if date else ""
                                
                                views = await cells[4].text_content()
                                views = views.strip() if views else ""
                                
                                # 첨부파일 여부 확인
                                attachment_cell = cells[5]
                                has_attachment = await attachment_cell.query_selector('img')
                                
                                # 고유 ID 생성
                                announcement_id = f"notice_{hash(title)}_{date}"
                                
                                announcements.append({
                                    'id': announcement_id,
                                    'number': "공지",
                                    'title': title,
                                    'author': author,
                                    'date': date,
                                    'views': views,
                                    'has_attachment': bool(has_attachment),
                                    'row_index': i,
                                    'cell_index': 1  # 제목 셀 인덱스
                                })
                        else:
                            # 일반 공지사항의 경우
                            number = first_cell_text.strip()
                            
                            title_cell = cells[1]
                            title_link = await title_cell.query_selector('a')
                            if title_link:
                                title = await title_link.text_content()
                                title = title.strip() if title else ""
                                
                                # 작성자, 등록일, 조회수 추출
                                author = await cells[2].text_content()
                                author = author.strip() if author else ""
                                
                                date = await cells[3].text_content()
                                date = date.strip() if date else ""
                                
                                views = await cells[4].text_content()
                                views = views.strip() if views else ""
                                
                                # 첨부파일 여부 확인
                                attachment_cell = cells[5]
                                has_attachment = await attachment_cell.query_selector('img')
                                
                                # 고유 ID 생성
                                announcement_id = f"{number}_{hash(title)}_{date}"
                                
                                announcements.append({
                                    'id': announcement_id,
                                    'number': number,
                                    'title': title,
                                    'author': author,
                                    'date': date,
                                    'views': views,
                                    'has_attachment': bool(has_attachment),
                                    'row_index': i,
                                    'cell_index': 1  # 제목 셀 인덱스
                                })
                except Exception as e:
                    logger.error(f"행 {i} 처리 중 오류: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"공지사항 목록 추출 실패: {e}")
        
        logger.info(f"총 {len(announcements)}개의 공지사항을 찾았습니다.")
        return announcements
    
    async def download_attachment_with_playwright(self, page, attachment_link, save_dir: str) -> bool:
        """Playwright를 사용한 첨부파일 다운로드"""
        try:
            # 첨부파일 링크에서 파일명 추출
            file_name = await attachment_link.text_content()
            file_name = file_name.strip()
            
            # 파일 크기 정보 제거
            file_name = re.sub(r'\s*\[.*?\]\s*$', '', file_name)
            
            # 파일명에 사용할 수 없는 문자 제거
            safe_filename = re.sub(r'[<>:"/\\|?*]', '_', file_name)
            
            file_path = os.path.join(save_dir, safe_filename)
            
            logger.info(f"첨부파일 다운로드 시도: {file_name}")
            
            # 다운로드 시작 대기
            async with page.expect_download() as download_info:
                await attachment_link.click()
                await page.wait_for_timeout(1000)  # 다운로드 시작 대기
            
            download = await download_info.value
            
            # 다운로드 완료 대기 및 저장
            await download.save_as(file_path)
            
            # 파일 크기 확인
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                
                # 파일 크기가 너무 작으면 HTML 페이지일 가능성 확인
                if file_size < 1024:  # 1KB 미만
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            if '<html' in content.lower() or '<!doctype html' in content.lower():
                                logger.warning(f"HTML 파일 감지, 삭제: {file_name}")
                                os.remove(file_path)
                                return False
                    except:
                        pass
                
                logger.info(f"첨부파일 다운로드 완료: {file_name} ({file_size:,} bytes)")
                return True
            else:
                logger.error(f"다운로드된 파일이 존재하지 않음: {file_name}")
                return False
                
        except Exception as e:
            logger.error(f"첨부파일 다운로드 실패: {file_name} - {e}")
            return False
    
    async def scrape_announcement_detail(self, page, announcement: Dict[str, str]) -> Optional[Dict[str, str]]:
        """공지사항 상세 내용 스크래핑"""
        try:
            # 이미 처리된 공지사항인지 확인
            if self.is_already_processed(announcement['id']):
                logger.info(f"이미 처리된 공지사항 건너뛰기: {announcement['title']}")
                return None
            
            # 새로운 방식: 행 인덱스를 사용하여 매번 새로운 링크 찾기
            rows = await page.query_selector_all('tbody tr')
            if announcement['row_index'] >= len(rows):
                logger.error(f"행 인덱스가 범위를 벗어남: {announcement['row_index']}")
                return None
            
            target_row = rows[announcement['row_index']]
            title_cell = await target_row.query_selector(f'td:nth-child({announcement["cell_index"] + 1})')
            title_link = await title_cell.query_selector('a')
            
            if not title_link:
                logger.error(f"링크를 찾을 수 없습니다: {announcement['title']}")
                return None
            
            # 공지사항 링크 클릭
            await title_link.click()
            await page.wait_for_timeout(3000)  # 페이지 로딩 대기
            
            # 상세 페이지에서 정보 추출
            title = announcement['title']
            
            # 본문 내용 추출 (개선된 방식)
            content_parts = []
            try:
                # 상세 페이지 로딩 대기
                await page.wait_for_selector('table', timeout=10000)
                
                # 본문이 있는 테이블 행 찾기 (일반적으로 마지막 행에 본문이 있음)
                content_tables = await page.query_selector_all('table')
                
                for table in content_tables:
                    rows = await table.query_selector_all('tr')
                    for row in rows:
                        cells = await row.query_selector_all('td')
                        for cell in cells:
                            # 본문 내용이 있는 셀 찾기
                            text = await cell.text_content()
                            if text and len(text.strip()) > 50:  # 의미있는 내용만
                                # HTML 태그 제거하고 텍스트만 추출
                                clean_text = text.strip()
                                if clean_text and not clean_text.startswith('목록'):
                                    content_parts.append(clean_text)
                
                # 중복 제거 및 정리
                unique_content = []
                for content in content_parts:
                    if content not in unique_content and len(content) > 20:
                        unique_content.append(content)
                
                content = '\n\n'.join(unique_content[:5]) if unique_content else "본문 내용을 추출할 수 없습니다."
                
            except Exception as e:
                logger.error(f"본문 내용 추출 실패: {e}")
                content = "본문 내용 추출 중 오류 발생"
            
            # 첨부파일 추출 및 다운로드 (Playwright 사용)
            attachments = []
            downloaded_count = 0
            
            try:
                # 첨부파일 링크 찾기
                attachment_links = await page.query_selector_all('a[href*="bbsNew_download.php"]')
                
                if attachment_links:
                    # 첨부파일 디렉토리 생성
                    safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
                    number = announcement.get('number', '000')
                    folder_name = f"{number}_{safe_title}"
                    announcement_dir = os.path.join(self.output_dir, folder_name)
                    attachments_dir = os.path.join(announcement_dir, 'attachments')
                    os.makedirs(attachments_dir, exist_ok=True)
                    
                    for link in attachment_links:
                        file_name = await link.text_content()
                        file_name = file_name.strip()
                        
                        # 파일 크기 정보 제거
                        file_name = re.sub(r'\s*\[.*?\]\s*$', '', file_name)
                        
                        if file_name:
                            logger.info(f"첨부파일 발견: {file_name}")
                            
                            # Playwright를 사용한 다운로드
                            if await self.download_attachment_with_playwright(page, link, attachments_dir):
                                downloaded_count += 1
                                attachments.append({
                                    'name': file_name,
                                    'downloaded': True
                                })
                            else:
                                attachments.append({
                                    'name': file_name,
                                    'downloaded': False
                                })
                            
                            # 다운로드 간격 조절
                            await page.wait_for_timeout(1000)
                
            except Exception as e:
                logger.error(f"첨부파일 처리 실패: {e}")
            
            # 뒤로 가기
            await page.go_back()
            await page.wait_for_timeout(2000)
            
            logger.info(f"공지사항 처리 완료: {title} (첨부파일: {downloaded_count}개 다운로드)")
            
            return {
                'id': announcement['id'],
                'title': title,
                'content': content,
                'attachments': attachments,
                'author': announcement['author'],
                'date': announcement['date'],
                'views': announcement['views'],
                'number': announcement['number'],
                'downloaded_attachments': downloaded_count
            }
            
        except Exception as e:
            logger.error(f"상세 내용 스크래핑 실패: {announcement['title']} - {e}")
            # 오류 발생 시 목록 페이지로 돌아가기
            try:
                await page.go_back()
                await page.wait_for_timeout(2000)
            except:
                pass
            return None
    
    def save_announcement(self, announcement_data: Dict[str, str]) -> bool:
        """공지사항 저장"""
        try:
            # 파일명에 사용할 수 없는 문자 제거
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', announcement_data['title'])
            safe_title = safe_title.strip()
            
            # 공지사항 번호 추출 (파일명에 사용)
            number = announcement_data.get('number', '000')
            folder_name = f"{number}_{safe_title}"
            
            announcement_dir = os.path.join(self.output_dir, folder_name)
            os.makedirs(announcement_dir, exist_ok=True)
            
            # 내용 저장
            content_file = os.path.join(announcement_dir, 'content.md')
            with open(content_file, 'w', encoding='utf-8') as f:
                f.write(f"# {announcement_data['title']}\n\n")
                f.write(f"- 작성자: {announcement_data['author']}\n")
                f.write(f"- 등록일: {announcement_data['date']}\n")
                f.write(f"- 조회수: {announcement_data['views']}\n")
                f.write(f"- 첨부파일: {announcement_data.get('downloaded_attachments', 0)}개 다운로드\n\n")
                f.write("---\n\n")
                f.write(announcement_data['content'])
            
            # 처리 완료 표시
            self.mark_as_processed(announcement_data['id'])
            
            logger.info(f"공지사항 저장 완료: {announcement_data['title']} (첨부파일: {announcement_data.get('downloaded_attachments', 0)}개)")
            return True
            
        except Exception as e:
            logger.error(f"공지사항 저장 실패: {announcement_data['title']} - {e}")
            return False
    
    def get_page_url(self, page_num: int) -> str:
        """페이지 URL 생성"""
        if page_num == 1:
            return self.base_url
        else:
            # 실제 페이지네이션 구조 분석 후 수정
            start_page = (page_num - 1) * 15  # 한 페이지당 15개씩
            
            # Base64 인코딩 생성
            param_string = f"startPage={start_page}&code=sub01b&table=cs_bbs_data_new&search_item=&search_order=&url=sub01b&keyvalue=sub01"
            encoded_param = base64.b64encode(param_string.encode()).decode()
            
            return f"{self.base_url.split('?')[0]}?bbs_data={encoded_param}||"
    
    async def scrape_page(self, page, page_num: int) -> List[Dict[str, str]]:
        """페이지 스크래핑"""
        try:
            url = self.get_page_url(page_num)
            
            logger.info(f"=== 페이지 {page_num} 스크래핑 시작: {url} ===")
            
            await page.goto(url, wait_until='networkidle')
            await page.wait_for_timeout(3000)
            
            # 공지사항 목록 추출
            announcements = await self.extract_announcements_from_page(page)
            scraped_data = []
            
            for i, announcement in enumerate(announcements):
                logger.info(f"[{i+1}/{len(announcements)}] 스크래핑 중: {announcement['title']}")
                
                # 상세 내용 스크래핑
                detail_data = await self.scrape_announcement_detail(page, announcement)
                if detail_data:
                    scraped_data.append(detail_data)
                    
                    # 저장
                    self.save_announcement(detail_data)
                else:
                    logger.warning(f"상세 내용 스크래핑 실패 또는 중복: {announcement['title']}")
                
                # 요청 간격 조절
                await page.wait_for_timeout(1500)
            
            # 페이지 완료 상태 업데이트
            status = self.load_status()
            status['pages_scraped'] = max(status.get('pages_scraped', 0), page_num)
            status['total_announcements'] = status.get('total_announcements', 0) + len(scraped_data)
            self.save_status(status)
            
            return scraped_data
            
        except Exception as e:
            logger.error(f"페이지 {page_num} 스크래핑 실패: {e}")
            return []
    
    async def run(self):
        """메인 스크래핑 실행"""
        logger.info("GWTP 모집공고 스크래핑 시작 (첨부파일 다운로드 개선 버전)")
        
        # 초기 상태 로드
        status = self.load_status()
        logger.info(f"이전 실행 상태: {status}")
        
        async with async_playwright() as p:
            # 다운로드 허용 브라우저 설정
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-web-security']
            )
            context = await browser.new_context(
                accept_downloads=True,
                extra_http_headers={
                    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8'
                }
            )
            page = await context.new_page()
            
            all_data = []
            
            # 3페이지까지 수집
            for page_num in range(1, 4):
                logger.info(f"\n{'='*60}")
                logger.info(f"페이지 {page_num} 처리 시작")
                logger.info(f"{'='*60}")
                
                page_data = await self.scrape_page(page, page_num)
                all_data.extend(page_data)
                
                logger.info(f"페이지 {page_num} 완료: {len(page_data)}개 수집")
                
                # 페이지 간 간격
                if page_num < 3:
                    await page.wait_for_timeout(3000)
            
            await browser.close()
            
        # 최종 상태 업데이트
        final_status = self.load_status()
        final_status['total_announcements'] = len(all_data)
        
        # 다운로드 통계 계산
        total_downloaded = sum(data.get('downloaded_attachments', 0) for data in all_data)
        final_status['total_downloaded_attachments'] = total_downloaded
        
        self.save_status(final_status)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"스크래핑 완료!")
        logger.info(f"총 {len(all_data)}개의 공지사항을 수집했습니다.")
        logger.info(f"총 {total_downloaded}개의 첨부파일을 다운로드했습니다.")
        logger.info(f"상태 파일: {self.status_file}")
        logger.info(f"{'='*60}")
        
        return all_data

def main():
    """메인 함수"""
    try:
        scraper = GWTPAnnouncementScraperWithDownloads()
        asyncio.run(scraper.run())
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단되었습니다.")
    except Exception as e:
        logger.error(f"스크래핑 중 오류 발생: {e}")

if __name__ == "__main__":
    main()