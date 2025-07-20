# -*- coding: utf-8 -*-
"""
희망나눔재단 자료실 스크래퍼
URL: https://www.heemangfdn.or.kr/layout/res/home.php?go=pds.list&pds_type=1
"""

import os
import time
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from enhanced_base_scraper import EnhancedBaseScraper
from typing import List, Dict, Any
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('heemangfdn_scraper.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class EnhancedHeemangfdnScraper(EnhancedBaseScraper):
    """희망나눔재단 자료실 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.heemangfdn.or.kr"
        self.list_url = "https://www.heemangfdn.or.kr/layout/res/home.php?go=pds.list&pds_type=1"
        self.site_code = "heemangfdn"
        
        # 헤더 설정
        self.headers.update({
            'Referer': self.base_url,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        self.session.headers.update(self.headers)
        
        # 사이트별 설정
        self.verify_ssl = True
        self.timeout = 30
        self.delay_between_requests = 1
        
    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 반환"""
        if page_num == 1:
            return self.list_url
        else:
            # 헤만재단은 start= 파라미터 사용 (10개씩)
            start = (page_num - 1) * 10
            return f"{self.base_url}/layout/res/home.php?go=pds.list&pds_type=1&start={start}"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지에서 공고 목록 추출"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 공고 목록이 담긴 테이블 찾기 - heemangfdn 사이트 구조 분석 필요
        table = soup.find('table')
        if not table:
            logger.warning("공고 목록 테이블을 찾을 수 없습니다")
            return announcements
        
        # 테이블의 행들 찾기 (헤더 제외)
        rows = table.select('tr')
        
        if not rows:
            logger.warning("테이블에 데이터 행이 없습니다")
            return announcements
        
        logger.info(f"총 {len(rows)}개의 행 발견")
        
        # 첫 번째 행은 헤더일 가능성이 높으므로 건너뛰기
        data_rows = rows[1:] if len(rows) > 1 else rows
        
        for i, row in enumerate(data_rows):
            try:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 3:
                    logger.debug(f"행 {i}: 셀 수가 부족합니다 ({len(cells)}개)")
                    continue
                
                # 제목과 링크 찾기 - heemangfdn은 href 속성 사용
                title_link = None
                title = ""
                announcement_id = None
                
                # 방법 1: href 속성에 num= 파라미터가 있는 a 태그 찾기
                for cell in cells:
                    links = cell.find_all('a', href=True)
                    for link in links:
                        href = link.get('href', '')
                        text = link.get_text(strip=True)
                        
                        # href="home.php?go=pds.list&pds_type=1&num=1195&..." 패턴
                        if href and 'num=' in href and text:
                            # num 파라미터 추출
                            num_match = re.search(r'num=(\d+)', href)
                            if num_match:
                                title_link = link
                                title = text
                                announcement_id = num_match.group(1)
                                break
                    
                    if title_link:
                        break
                
                if not title_link or not announcement_id:
                    logger.debug(f"행 {i}: 제목 링크 또는 ID를 찾을 수 없습니다")
                    continue
                
                # heemangfdn 사이트의 상세 URL 구성
                # 실제로는 같은 페이지에서 확장되지만, 직접 접근 가능한 URL 구성
                detail_url = f"{self.base_url}/layout/res/home.php?go=pds.list&pds_type=1&num={announcement_id}"
                
                # 기본 공고 정보
                announcement = {
                    'title': title.strip(),
                    'url': detail_url,
                    'announcement_id': announcement_id
                }
                
                # 추가 정보 추출 (번호, 분류, 작성일, 조회수)
                try:
                    # 번호 (첫번째 셀)
                    if cells[0]:
                        number = cells[0].get_text(strip=True)
                        if number and not number.lower() in ['번호', 'no']:
                            announcement['number'] = number
                    
                    # 작성일 (끝에서 두번째 셀)
                    if len(cells) >= 4:
                        date_text = cells[-2].get_text(strip=True)
                        if date_text and not date_text.lower() in ['등록일', '작성일', 'date']:
                            announcement['date'] = date_text
                    
                    # 조회수 (마지막 셀)
                    views_text = cells[-1].get_text(strip=True)
                    if views_text and views_text.isdigit():
                        announcement['views'] = views_text
                        
                except Exception as e:
                    logger.debug(f"행 {i} 추가 정보 추출 중 오류: {e}")
                
                announcements.append(announcement)
                logger.debug(f"공고 추가: {title[:50]}... (ID: {announcement_id})")
                
            except Exception as e:
                logger.error(f"행 {i} 파싱 중 오류: {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개 공고 추출 완료")
        return announcements
    
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지에서 내용과 첨부파일 추출 - heemangfdn 사이트 특화"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 본문 내용 추출
        content_parts = []
        
        # heemangfdn 사이트의 상세보기는 같은 페이지에서 확장되는 형태
        # 상세 내용은 목록 아래에 표시됨
        
        # 방법 1: 이미지가 포함된 본문 찾기 (UI 아이콘 제외)
        # heemangfdn은 이미지를 많이 사용함
        all_images = soup.find_all('img')
        for img in all_images:
            src = img.get('src', '')
            alt = img.get('alt', '')
            
            # UI 아이콘이나 시스템 이미지는 제외
            excluded_patterns = [
                '/images/ico/', '/images/icon/', '/ico/', '/icon/', '/images/board/',
                'btn_', 'button_', 'arrow_', 'arr_', 'bg_', 'header_', 'footer_',
                'nav_', 'menu_', 'quick', 'close', 'play', 'pause', 'logo',
                'hd_', 'go_', 'kakao', 'facebook', 'twitter', 'instagram',
                'icon_', 'blank.gif', 'spacer.gif', 'dot.gif'
            ]
            
            # UI 패턴이 포함되어 있으면 건너뛰기
            if any(pattern in src.lower() for pattern in excluded_patterns):
                continue
            
            # 상대 경로를 절대 경로로 변환
            if src and not src.startswith('http'):
                if src.startswith('/'):
                    img_url = self.base_url + src
                else:
                    img_url = urljoin(self.base_url, src)
                
                # 이미지 파일명에서 확장자 확인
                if any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']):
                    content_parts.append(f"![{alt}]({img_url})")
        
        # 방법 2: 테이블 셀에서 긴 텍스트 찾기
        all_cells = soup.find_all('td')
        for cell in all_cells:
            cell_text = cell.get_text(strip=True)
            # 상당히 긴 텍스트만 본문으로 간주
            if len(cell_text) > 100:
                # 너무 긴 경우 일부만 사용
                if len(cell_text) > 2000:
                    cell_text = cell_text[:2000] + "..."
                content_parts.append(cell_text)
        
        # 방법 3: div나 p 태그에서 본문 찾기
        content_elements = soup.find_all(['div', 'p'])
        for element in content_elements:
            text = element.get_text(strip=True)
            if len(text) > 50 and len(text) <= 1000:
                content_parts.append(text)
        
        # 본문 조합
        content = '\n\n'.join(content_parts) if content_parts else ""
        
        # 중복 제거 및 정리
        if content:
            # 중복된 텍스트 제거
            lines = content.split('\n')
            unique_lines = []
            seen_lines = set()
            for line in lines:
                line = line.strip()
                if line and line not in seen_lines and len(line) > 10:
                    unique_lines.append(line)
                    seen_lines.add(line)
            content = '\n\n'.join(unique_lines)
                
        # 첨부파일 추출 - heemangfdn 특화
        attachments = []
        
        # 방법 1: 이미지 파일들을 첨부파일로 처리 (UI 아이콘 제외)
        for img in all_images:
            src = img.get('src', '')
            if src and any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']):
                # UI 아이콘이나 시스템 이미지는 제외
                excluded_patterns = [
                    '/images/ico/', '/images/icon/', '/ico/', '/icon/', '/images/board/',
                    'btn_', 'button_', 'arrow_', 'arr_', 'bg_', 'header_', 'footer_',
                    'nav_', 'menu_', 'quick', 'close', 'play', 'pause', 'logo',
                    'hd_', 'go_', 'kakao', 'facebook', 'twitter', 'instagram',
                    'icon_', 'blank.gif', 'spacer.gif', 'dot.gif'
                ]
                
                # UI 패턴이 포함되어 있으면 건너뛰기
                if any(pattern in src.lower() for pattern in excluded_patterns):
                    continue
                
                # 파일명 추출
                filename = os.path.basename(src)
                if not filename:
                    continue
                
                # 절대 URL 구성
                if src.startswith('/'):
                    img_url = self.base_url + src
                else:
                    img_url = urljoin(self.base_url, src)
                
                # 중복 확인
                if not any(att['filename'] == filename for att in attachments):
                    attachments.append({
                        'filename': filename,
                        'url': img_url
                    })
                    logger.debug(f"이미지 첨부파일 발견: {filename}")
        
        # 방법 2: "첨부파일" 라벨이 있는 행에서 다운로드 링크 찾기
        attach_cells = soup.find_all(['th', 'td'], string=lambda text: text and '첨부파일' in text)
        for cell in attach_cells:
            parent_row = cell.find_parent('tr')
            if parent_row:
                file_links = parent_row.find_all('a', href=True)
                for link in file_links:
                    href = link.get('href', '')
                    filename = link.get_text(strip=True)
                    
                    if filename and href and not href.startswith('#'):
                        download_url = urljoin(self.base_url, href)
                        # 중복 확인
                        if not any(att['filename'] == filename for att in attachments):
                            attachments.append({
                                'filename': filename,
                                'url': download_url
                            })
                            logger.debug(f"첨부파일 발견: {filename} -> {download_url}")
        
        # 방법 3: 모든 파일 확장자 링크 찾기
        file_extensions = ['.pdf', '.hwp', '.doc', '.docx', '.xls', '.xlsx', '.zip', '.jpg', '.jpeg', '.png', '.gif', '.bmp']
        all_links = soup.find_all('a', href=True)
        for link in all_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # href나 텍스트에 파일 확장자가 포함된 경우
            if any(ext in href.lower() for ext in file_extensions) or any(ext in text.lower() for ext in file_extensions):
                filename = text if text else os.path.basename(href)
                if filename and not filename.startswith('#'):
                    download_url = urljoin(self.base_url, href)
                    # 중복 확인
                    if not any(att['filename'] == filename for att in attachments):
                        attachments.append({
                            'filename': filename,
                            'url': download_url
                        })
                        logger.debug(f"파일 확장자 기반 첨부파일 발견: {filename}")
        
        logger.info(f"본문 길이: {len(content)}, 첨부파일: {len(attachments)}개")
        
        return {
            'content': content,
            'attachments': attachments
        }


def main():
    """메인 실행 함수"""
    scraper = EnhancedHeemangfdnScraper()
    
    # output/heemangfdn 디렉토리 설정
    output_dir = os.path.join('output', scraper.site_code)
    
    logger.info("="*60)
    logger.info("🏛️ 희망나눔재단 자료실 스크래퍼 시작")
    logger.info(f"📂 저장 경로: {output_dir}")
    logger.info(f"🌐 대상 사이트: {scraper.base_url}")
    logger.info("="*60)
    
    try:
        # 3페이지까지 스크래핑 실행
        success = scraper.scrape_pages(max_pages=3, output_base=output_dir)
        
        if success:
            logger.info("✅ 스크래핑이 성공적으로 완료되었습니다!")
        else:
            logger.error("❌ 스크래핑 중 오류가 발생했습니다.")
            
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단되었습니다.")
    except Exception as e:
        logger.error(f"예상치 못한 오류: {e}")
        raise


if __name__ == "__main__":
    main()