#!/usr/bin/env python3
"""
Enhanced GTC (경상북도문화관광공사) 공지사항 스크래퍼 - 수정된 버전
URL: https://www.gtc.co.kr/page/10059/10007.tc
"""

import os
import re
import time
import json
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import logging
from playwright.async_api import async_playwright

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GTCAnnouncementScraperFixed:
    def __init__(self, base_url: str = "https://www.gtc.co.kr/page/10059/10007.tc"):
        self.base_url = base_url
        self.domain = "https://www.gtc.co.kr"
        self.output_dir = "output/gtc"
        self.site_code = "gtc"
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
            # 페이지가 완전히 로드될 때까지 대기
            await page.wait_for_selector('tbody tr', timeout=10000)
            
            # 테이블 행 찾기
            rows = await page.query_selector_all('tbody tr')
            
            for i, row in enumerate(rows):
                try:
                    cells = await row.query_selector_all('td')
                    if len(cells) >= 5:
                        # 번호
                        number = await cells[0].text_content()
                        number = number.strip() if number else ""
                        
                        # 제목과 링크
                        title_cell = cells[1]
                        title_link = await title_cell.query_selector('a')
                        if title_link:
                            title = await title_link.text_content()
                            title = title.strip() if title else ""
                            
                            # 작성자
                            author = await cells[2].text_content()
                            author = author.strip() if author else ""
                            
                            # 조회수
                            views = await cells[3].text_content()
                            views = views.strip() if views else ""
                            
                            # 작성일
                            date = await cells[4].text_content()
                            date = date.strip() if date else ""
                            
                            # 고유 ID 생성 (번호 + 제목 해시)
                            announcement_id = f"{number}_{hash(title)}"
                            
                            announcements.append({
                                'id': announcement_id,
                                'number': number,
                                'title': title,
                                'author': author,
                                'views': views,
                                'date': date,
                                'row_index': i
                            })
                except Exception as e:
                    logger.error(f"행 {i} 처리 중 오류: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"공지사항 목록 추출 실패: {e}")
        
        logger.info(f"총 {len(announcements)}개의 공지사항을 찾았습니다.")
        return announcements
    
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
            title_cell = await target_row.query_selector('td:nth-child(2)')
            title_link = await title_cell.query_selector('a')
            
            if not title_link:
                logger.error(f"링크를 찾을 수 없습니다: {announcement['title']}")
                return None
            
            # 공지사항 링크 클릭
            await title_link.click()
            await page.wait_for_timeout(3000)  # 페이지 로딩 대기
            
            # 제목 추출
            title = announcement['title']
            
            # 본문 내용 추출 (■ 표시가 있는 div 찾기)
            content = ""
            try:
                # 더 구체적인 셀렉터 사용
                await page.wait_for_timeout(2000)  # 추가 대기
                
                # 여러 방법으로 본문 내용 찾기
                content_found = False
                
                # 방법 1: ■ 표시가 있는 div 찾기
                content_divs = await page.query_selector_all('div')
                for div in content_divs:
                    text = await div.text_content()
                    if text and '■' in text and len(text) > 100:  # 최소 길이 증가
                        content = text.strip()
                        content_found = True
                        break
                
                # 방법 2: 특정 클래스나 ID로 찾기
                if not content_found:
                    content_selectors = [
                        '.board_view_content',
                        '.content',
                        '.view_content',
                        '[class*="content"]'
                    ]
                    for selector in content_selectors:
                        try:
                            content_elem = await page.query_selector(selector)
                            if content_elem:
                                content = await content_elem.text_content()
                                if content and len(content.strip()) > 50:
                                    content = content.strip()
                                    content_found = True
                                    break
                        except:
                            continue
                
                if not content_found:
                    content = "본문 내용을 추출할 수 없습니다."
                    
            except Exception as e:
                logger.error(f"본문 내용 추출 실패: {e}")
                content = "본문 내용 추출 중 오류 발생"
            
            # 첨부파일 추출
            attachments = []
            try:
                attachment_links = await page.query_selector_all('a[href*="/file/readFile.tc"]')
                for link in attachment_links:
                    href = await link.get_attribute('href')
                    if href:
                        file_url = urljoin(self.domain, href)
                        file_name = await link.text_content()
                        if file_name:
                            # 파일 크기 정보 제거
                            file_name = re.sub(r'\\s*\\[.*?\\]\\s*$', '', file_name.strip())
                            if file_name:
                                attachments.append({
                                    'name': file_name,
                                    'url': file_url
                                })
            except Exception as e:
                logger.error(f"첨부파일 추출 실패: {e}")
            
            # 뒤로 가기
            await page.go_back()
            await page.wait_for_timeout(2000)
            
            return {
                'id': announcement['id'],
                'title': title,
                'content': content,
                'attachments': attachments,
                'author': announcement['author'],
                'date': announcement['date'],
                'views': announcement['views'],
                'number': announcement['number']
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
    
    def download_attachment(self, attachment: Dict[str, str], save_dir: str) -> bool:
        """첨부파일 다운로드"""
        try:
            # Referer 헤더 추가
            headers = self.session.headers.copy()
            headers['Referer'] = 'https://www.gtc.co.kr/page/10059/10007.tc'
            
            response = self.session.get(attachment['url'], headers=headers, timeout=30)
            response.raise_for_status()
            
            # Content-Type 확인
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' in content_type:
                logger.warning(f"HTML 응답 감지, 파일 다운로드 실패: {attachment['name']}")
                return False
            
            file_path = os.path.join(save_dir, attachment['name'])
            
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            # 파일 크기 확인
            file_size = os.path.getsize(file_path)
            if file_size < 1024:  # 1KB 미만
                # HTML 페이지인지 확인
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if '<html' in content.lower() or '<!doctype html' in content.lower():
                            logger.warning(f"HTML 파일 감지, 삭제: {attachment['name']}")
                            os.remove(file_path)
                            return False
                except:
                    pass
            
            logger.info(f"첨부파일 다운로드 완료: {attachment['name']} ({file_size:,} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"첨부파일 다운로드 실패: {attachment['name']} - {e}")
            return False
    
    def save_announcement(self, announcement_data: Dict[str, str]) -> bool:
        """공지사항 저장"""
        try:
            # 파일명에 사용할 수 없는 문자 제거
            safe_title = re.sub(r'[<>:"/\\\\|?*]', '_', announcement_data['title'])
            safe_title = safe_title.strip()
            
            # 공지사항 번호 추출 (파일명에 사용)
            number = announcement_data.get('number', '000')
            folder_name = f"{number}_{safe_title}"
            
            announcement_dir = os.path.join(self.output_dir, folder_name)
            os.makedirs(announcement_dir, exist_ok=True)
            
            # 내용 저장
            content_file = os.path.join(announcement_dir, 'content.md')
            with open(content_file, 'w', encoding='utf-8') as f:
                f.write(f"# {announcement_data['title']}\\n\\n")
                f.write(f"- 작성자: {announcement_data['author']}\\n")
                f.write(f"- 작성일: {announcement_data['date']}\\n")
                f.write(f"- 조회수: {announcement_data['views']}\\n\\n")
                f.write("---\\n\\n")
                f.write(announcement_data['content'])
            
            # 첨부파일 다운로드
            downloaded_count = 0
            if announcement_data['attachments']:
                attachments_dir = os.path.join(announcement_dir, 'attachments')
                os.makedirs(attachments_dir, exist_ok=True)
                
                for attachment in announcement_data['attachments']:
                    if self.download_attachment(attachment, attachments_dir):
                        downloaded_count += 1
                    time.sleep(0.5)  # 다운로드 간격 조절
            
            # 처리 완료 표시
            self.mark_as_processed(announcement_data['id'])
            
            logger.info(f"공지사항 저장 완료: {announcement_data['title']} (첨부파일: {downloaded_count}개)")
            return True
            
        except Exception as e:
            logger.error(f"공지사항 저장 실패: {announcement_data['title']} - {e}")
            return False
    
    async def scrape_page(self, page, page_num: int) -> List[Dict[str, str]]:
        """페이지 스크래핑"""
        try:
            if page_num == 1:
                url = self.base_url
            else:
                url = f"{self.base_url}?pageIndex={page_num}"
            
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
        logger.info("GTC 공지사항 스크래핑 시작 (수정된 버전)")
        
        # 초기 상태 로드
        status = self.load_status()
        logger.info(f"이전 실행 상태: {status}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # 한국어 설정
            await page.set_extra_http_headers({
                'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8'
            })
            
            all_data = []
            
            # 3페이지까지 수집
            for page_num in range(1, 4):
                logger.info(f"\\n{'='*60}")
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
        self.save_status(final_status)
        
        logger.info(f"\\n{'='*60}")
        logger.info(f"스크래핑 완료!")
        logger.info(f"총 {len(all_data)}개의 공지사항을 수집했습니다.")
        logger.info(f"상태 파일: {self.status_file}")
        logger.info(f"{'='*60}")
        
        return all_data

def main():
    """메인 함수"""
    try:
        scraper = GTCAnnouncementScraperFixed()
        asyncio.run(scraper.run())
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단되었습니다.")
    except Exception as e:
        logger.error(f"스크래핑 중 오류 발생: {e}")

if __name__ == "__main__":
    main()