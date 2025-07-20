#!/usr/bin/env python3
"""
K-씨푸드 Enhanced Scraper
URL: https://biz.k-seafoodtrade.kr/apply/export_list.php
"""

import os
import re
import time
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup
import requests

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from enhanced_base_scraper import EnhancedBaseScraper
except ImportError:
    logger.error("enhanced_base_scraper.py 파일을 찾을 수 없습니다. 같은 디렉토리에 있는지 확인하세요.")
    raise


class EnhancedKSeafoodScraper(EnhancedBaseScraper):
    """K-씨푸드 웹사이트 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://biz.k-seafoodtrade.kr"
        self.site_code = "k-seafood"
        # 출력 디렉토리 설정
        self.output_dir = os.path.join(os.getcwd(), 'output', 'k-seafood')
        self.start_url = f"{self.base_url}/apply/export_list.php"
        
        # SSL 인증서 검증 비활성화
        self.verify_ssl = False
        
        # 사이트 특화 설정
        self.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none'
        })
        
        logger.info("=== K-씨푸드 스크래퍼 시작 ===")
    
    def initialize_session(self) -> bool:
        """세션 초기화"""
        try:
            logger.info("K-씨푸드 세션 초기화 중...")
            
            # SSL 인증서 검증 비활성화
            self.session.verify = False
            
            # 메인 페이지 접속 테스트
            response = self.session.get(self.start_url, headers=self.headers, timeout=30, verify=False)
            response.raise_for_status()
            
            # 인코딩 확인
            if response.encoding:
                response.encoding = 'utf-8'
            
            logger.info("세션 초기화 완료")
            return True
            
        except Exception as e:
            logger.error(f"세션 초기화 실패: {e}")
            return False
    
    def get_list_url(self, page_num: int) -> str:
        """목록 페이지 URL 생성"""
        if page_num == 1:
            return self.start_url
        else:
            # 페이지네이션은 biz_data 파라미터를 사용하여 Base64 인코딩
            # 브라우저에서 확인한 실제 패턴 사용
            if page_num == 2:
                return f"{self.start_url}?biz_data=c3RhcnRQYWdlPTIwJmxpc3RObz0mdGFibGU9JnNlYXJjaF9pdGVtX2Noaz0mc2VhcmNoX21lbV9pdGVtPSZzZWFyY2hfYml6X2l0ZW09JnNlYXJjaF9vcmRlcj0mc2VhcmNoX2RheT0mc2VhcmNoX2RheV9zdHI9JnBnPQ==||"
            elif page_num == 3:
                return f"{self.start_url}?biz_data=c3RhcnRQYWdlPTQwJmxpc3RObz0mdGFibGU9JnNlYXJjaF9pdGVtX2Noaz0mc2VhcmNoX21lbV9pdGVtPSZzZWFyY2hfYml6X2l0ZW09JnNlYXJjaF9vcmRlcj0mc2VhcmNoX2RheT0mc2VhcmNoX2RheV9zdHI9JnBnPQ==||"
            else:
                # 기본 패턴 (20개씩 증가)
                start_page = (page_num - 1) * 20
                import base64
                biz_data = f"startPage={start_page}&listNo=&table=&search_item_chk=&search_mem_item=&search_biz_item=&search_order=&search_day=&search_day_str=&pg="
                encoded_data = base64.b64encode(biz_data.encode('utf-8')).decode('utf-8')
                return f"{self.start_url}?biz_data={encoded_data}||"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 게시글 목록 찾기 - 실제 구조에 맞춤
        # 구조: <table> 내부의 <tbody> 안의 <tr> 태그들
        table = soup.find('table')
        if not table:
            logger.warning("게시글 목록 테이블을 찾을 수 없습니다")
            return announcements
        
        tbody = table.find('tbody')
        if not tbody:
            logger.warning("게시글 목록 tbody를 찾을 수 없습니다")
            return announcements
        
        # 각 게시글 행 찾기
        rows = tbody.find_all('tr')
        
        logger.info(f"총 {len(rows)}개의 게시글 행을 발견했습니다")
        
        for row in rows:
            try:
                cells = row.find_all('td')
                if len(cells) < 4:
                    continue
                
                # 상태 추출 (첫 번째 컬럼)
                status_cell = cells[0]
                status = status_cell.get_text(strip=True)
                
                # 사업명 추출 (두 번째 컬럼)
                title_cell = cells[1]
                title_link = title_cell.find('a')
                if not title_link:
                    continue
                
                title = title_link.get_text(strip=True)
                if not title:
                    continue
                
                # 상세 페이지 URL 추출
                href = title_link.get('href', '')
                if not href:
                    continue
                
                # 모집기간 추출 (세 번째 컬럼)
                period_cell = cells[2]
                period = period_cell.get_text(strip=True)
                
                # 수행기관 추출 (네 번째 컬럼)
                organization_cell = cells[3]
                organization = organization_cell.get_text(strip=True)
                
                # 상세 페이지 URL 생성 - 상대 경로 수정
                if href.startswith('/'):
                    detail_url = urljoin(self.base_url, href)
                else:
                    # 현재 페이지 기준으로 상대 경로 생성
                    detail_url = urljoin(self.start_url, href)
                
                # 게시글 ID 추출 (URL 파라미터에서)
                board_id = ""
                if 'biz_data=' in href:
                    # biz_data 파라미터를 디코딩하여 idx 추출
                    import base64
                    try:
                        biz_data = href.split('biz_data=')[1].split('&')[0].split('||')[0]
                        decoded_data = base64.b64decode(biz_data).decode('utf-8')
                        if 'idx=' in decoded_data:
                            board_id = decoded_data.split('idx=')[1].split('&')[0]
                    except:
                        pass
                
                announcement = {
                    'number': len(announcements) + 1,
                    'title': title,
                    'status': status,
                    'period': period,
                    'organization': organization,
                    'url': detail_url,  # base scraper에서 'url' 키를 찾음
                    'detail_url': detail_url,
                    'board_id': board_id
                }
                
                announcements.append(announcement)
                logger.debug(f"공고 파싱 완료: {title}")
                
            except Exception as e:
                logger.error(f"게시글 파싱 중 오류: {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개의 공고를 파싱했습니다")
        return announcements
    
    def parse_detail_page(self, html_content: str, detail_url: str = None) -> Dict[str, Any]:
        """공고 상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 현재 상세 페이지 URL 저장 (첨부파일 다운로드 시 Referer로 사용)
        self.current_detail_url = detail_url
        
        # 기본 반환 구조
        result = {
            'content': '',
            'attachments': []
        }
        
        # 본문 내용 추출
        content_text = ""
        
        # 방법 1: 테이블에서 모집개요 내용 추출
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    header = cells[0].get_text(strip=True)
                    if '모집개요' in header:
                        content_text = cells[1].get_text(strip=True)
                        break
            if content_text:
                break
        
        # 방법 2: 사업명, 신청기간, 사업기간, 장소 등 기본 정보 추출
        if not content_text:
            basic_info = []
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        header = cells[0].get_text(strip=True)
                        value = cells[1].get_text(strip=True)
                        if header in ['사업명', '신청기간', '사업기간', '장소', '수행기관']:
                            basic_info.append(f"**{header}**: {value}")
            
            if basic_info:
                content_text = '\n'.join(basic_info)
        
        # 방법 3: 전체 페이지에서 의미있는 내용 찾기 (백업)
        if not content_text or len(content_text) < 50:
            all_text = soup.get_text(strip=True)
            lines = all_text.split('\n')
            meaningful_lines = []
            
            for line in lines:
                line = line.strip()
                # 의미있는 내용만 추출
                if (len(line) > 10 and 
                    not any(skip in line for skip in ['메뉴', '네비게이션', '로그인', '회원가입', '홈', '사이트맵', '목록', '수정', '삭제', '이전', '다음', 'Copyright']) and
                    not line.isdigit() and
                    not re.match(r'^\d{4}-\d{2}-\d{2}', line)):
                    meaningful_lines.append(line)
                    
                    if len(meaningful_lines) >= 10:  # 상위 10개 라인
                        break
            
            if meaningful_lines:
                content_text = '\n'.join(meaningful_lines)
        
        if content_text and len(content_text) > 10:
            result['content'] = content_text
        else:
            result['content'] = "내용을 추출할 수 없습니다."
            logger.warning("상세 페이지 내용 추출 실패")
        
        # 첨부파일 추출
        # 첨부파일 링크 찾기
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    header = cells[0].get_text(strip=True)
                    if '첨부파일' in header:
                        # 첨부파일 링크들 찾기
                        links = cells[1].find_all('a')
                        for link in links:
                            href = link.get('href', '')
                            filename = link.get_text(strip=True)
                            
                            # 다운로드 링크인지 확인
                            if href and filename and (
                                'download' in href.lower() or 
                                'biz_register_file_download' in href or
                                href.startswith('./biz_register_file_download')
                            ):
                                # 상대 경로를 절대 경로로 변환
                                if href.startswith('./'):
                                    # ./ 제거 후 detail_url의 디렉토리 경로와 결합
                                    download_url = f"{self.base_url}/apply/{href[2:]}"  # ./ 제거 후 /apply/ 경로와 결합
                                else:
                                    download_url = urljoin(self.base_url, href)
                                
                                attachment = {
                                    'filename': filename,
                                    'url': download_url
                                }
                                
                                result['attachments'].append(attachment)
                                logger.debug(f"첨부파일 추가: {filename}")
        
        # 디버깅: 첨부파일을 찾지 못한 경우 HTML 내용 확인
        if not result['attachments']:
            logger.warning("첨부파일을 찾지 못했습니다. HTML 내용을 확인합니다.")
            # 모든 a 태그에서 다운로드 관련 링크 찾기
            all_links = soup.find_all('a')
            for link in all_links:
                href = link.get('href', '')
                filename = link.get_text(strip=True)
                if href and 'download' in href.lower():
                    logger.info(f"다운로드 링크 발견: {filename} -> {href}")
                    
                    # 상대 경로를 절대 경로로 변환
                    if href.startswith('./'):
                        # ./ 제거 후 /apply/ 경로와 결합
                        download_url = f"{self.base_url}/apply/{href[2:]}"  # ./ 제거 후 /apply/ 경로와 결합
                    else:
                        download_url = urljoin(self.base_url, href)
                    
                    attachment = {
                        'filename': filename,
                        'url': download_url
                    }
                    
                    result['attachments'].append(attachment)
        
        logger.info(f"상세 페이지 파싱 완료 - 내용: {len(result['content'])}자, 첨부파일: {len(result['attachments'])}개")
        return result
    
    def run_scraper(self, max_pages: int = 3) -> Dict[str, Any]:
        """스크래퍼 실행"""
        try:
            # 세션 초기화
            if not self.initialize_session():
                return {"success": False, "error": "세션 초기화 실패"}
            
            # 부모 클래스의 scrape_pages 메서드 호출 (output_base 지정)
            self.scrape_pages(max_pages, output_base=self.output_dir)
            return {"success": True}
            
        except Exception as e:
            logger.error(f"스크래퍼 실행 중 오류: {e}")
            return {"success": False, "error": str(e)}


def main():
    """메인 함수"""
    scraper = EnhancedKSeafoodScraper()
    
    try:
        # 3페이지 수집 (첨부파일 테스트)
        result = scraper.run_scraper(max_pages=3)
        
        if result.get("success", False):
            logger.info("=== K-씨푸드 스크래핑 완료 ===")
            logger.info(f"최종 통계: {scraper.get_stats()}")
        else:
            logger.error(f"스크래핑 실패: {result.get('error', '알 수 없는 오류')}")
            
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
    except Exception as e:
        logger.error(f"예상치 못한 오류: {e}")
        raise


if __name__ == "__main__":
    main()