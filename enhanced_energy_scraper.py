#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
한국에너지공단 공지사항 스크래퍼
URL: https://www.energy.or.kr/front/board/List2.do
"""

import re
import json
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from enhanced_base_scraper import EnhancedBaseScraper

logger = logging.getLogger(__name__)

class EnhancedEnergyScraper(EnhancedBaseScraper):
    """한국에너지공단 공지사항 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        
        # 사이트 기본 설정
        self.base_url = "https://www.energy.or.kr"
        self.list_url = "https://www.energy.or.kr/front/board/List2.do"
        self.detail_url = "https://www.energy.or.kr/front/board/View2.do"
        self.download_url = "https://www.energy.or.kr/commonFile/fileDownload.do"
        self.start_url = self.list_url
        
        # 헤더 설정
        self.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        self.session.headers.update(self.headers)
        
        # 세션 초기화
        self._initialize_session()
        
    def _initialize_session(self):
        """세션 초기화 및 쿠키 설정"""
        try:
            logger.info("에너지공단 사이트 세션 초기화 중...")
            response = self.session.get(self.list_url, timeout=10)
            response.raise_for_status()
            logger.info("에너지공단 사이트 세션 초기화 완료")
        except Exception as e:
            logger.warning(f"세션 초기화 중 오류 (계속 진행): {e}")
    
    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 생성 (POST 방식이므로 동일)"""
        return self.list_url
    
    def _get_page_content(self, page_num: int) -> str:
        """페이지별 내용 가져오기 (POST 방식)"""
        try:
            data = {
                'page': str(page_num),
                'searchfield': 'ALL',
                'searchword': ''
            }
            
            response = self.session.post(self.list_url, data=data, timeout=10)
            response.raise_for_status()
            
            return response.text
        except Exception as e:
            logger.error(f"페이지 {page_num} 가져오기 실패: {e}")
            return ""
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        logger.debug("에너지공단 사이트 목록 페이지 파싱 시작")
        
        # 테이블 구조 찾기
        table = soup.find('table')
        if not table:
            logger.warning("게시판 테이블을 찾을 수 없음")
            return announcements
        
        # tbody 내의 tr 요소들 찾기
        tbody = table.find('tbody')
        if not tbody:
            logger.warning("tbody를 찾을 수 없음")
            return announcements
        
        rows = tbody.find_all('tr')
        logger.debug(f"발견된 행 수: {len(rows)}")
        
        for i, row in enumerate(rows):
            try:
                # td 요소들 찾기
                cells = row.find_all('td')
                if len(cells) < 5:  # 번호, 제목, 첨부, 작성일, 조회수
                    continue
                
                # 번호 추출
                number_cell = cells[0]
                number = number_cell.get_text(strip=True)
                
                # 제목 및 링크 추출
                title_cell = cells[1]
                link_element = title_cell.find('a')
                if not link_element:
                    continue
                
                title = link_element.get_text(strip=True)
                if not title:
                    continue
                
                # onclick 속성에서 boardMngNo, boardNo 추출
                onclick = link_element.get('onclick', '')
                if not onclick or 'fn_Detail' not in onclick:
                    continue
                
                # fn_Detail('2','24437') 패턴 파싱
                match = re.search(r"fn_Detail\('(\d+)','(\d+)'\)", onclick)
                if not match:
                    continue
                
                board_mng_no = match.group(1)
                board_no = match.group(2)
                
                # 첨부파일 여부 확인
                attachment_cell = cells[2]
                attachment_text = attachment_cell.get_text(strip=True)
                has_attachment = '첨부' in attachment_text
                
                # 작성일 추출
                date_cell = cells[3]
                date = date_cell.get_text(strip=True)
                
                # 조회수 추출
                views_cell = cells[4]
                views = views_cell.get_text(strip=True)
                
                # 상세 페이지 URL 생성 (POST 방식이므로 파라미터 저장)
                detail_url = self.detail_url
                
                # 공지사항 정보 구성
                announcement = {
                    'number': number,
                    'title': title,
                    'url': detail_url,
                    'board_mng_no': board_mng_no,
                    'board_no': board_no,
                    'has_attachment': has_attachment,
                    'date': date,
                    'views': views
                }
                
                announcements.append(announcement)
                logger.debug(f"공고 파싱 완료: {number} - {title[:50]}...")
                
            except Exception as e:
                logger.error(f"공고 {i+1} 파싱 중 오류: {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
        return announcements
    
    def _get_page_announcements(self, page_num: int) -> List[Dict[str, Any]]:
        """특정 페이지의 공고 목록 가져오기"""
        try:
            html_content = self._get_page_content(page_num)
            if not html_content:
                return []
            
            return self.parse_list_page(html_content)
        except Exception as e:
            logger.error(f"페이지 {page_num} 공고 목록 가져오기 실패: {e}")
            return []
    
    def parse_detail_page(self, html_content: str, detail_url: str = None) -> Dict[str, Any]:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 첨부파일 추출
        attachments = self._extract_attachments(soup)
        
        # 본문 내용 추출
        content = self._extract_content(soup)
        
        return {
            'content': content,
            'attachments': attachments
        }
    
    def _extract_content(self, soup: BeautifulSoup) -> str:
        """본문 내용 추출 (정확한 선택자 사용)"""
        try:
            # 실제 본문 내용이 있는 컨테이너 찾기
            content_selectors = [
                'div.view_cont',       # 가장 정확한 본문 컨테이너
                'div.view_inner',      # 대안 컨테이너
                'article div.board_view',  # 전체 게시글 컨테이너
                'article'              # 최후 옵션
            ]
            
            content_element = None
            for selector in content_selectors:
                content_element = soup.select_one(selector)
                if content_element:
                    logger.debug(f"본문 컨테이너 발견: {selector}")
                    break
            
            if not content_element:
                logger.warning("본문 컨테이너를 찾을 수 없습니다.")
                return ""
            
            # 실제 본문 내용 추출
            content_parts = []
            
            # 1. p 태그에서 실제 내용 추출
            paragraphs = content_element.find_all('p')
            for p in paragraphs:
                text = p.get_text(strip=True)
                if text and len(text) > 5:  # 의미있는 내용만
                    # 첨부파일이나 네비게이션 섹션에 도달하면 중단
                    if any(keyword in text for keyword in ['첨부파일', '이전글', '다음글', '목록보기']):
                        break
                    content_parts.append(text)
            
            # 2. div 태그에서 내용 추출 (p 태그가 없는 경우)
            if not content_parts:
                divs = content_element.find_all('div')
                for div in divs:
                    # 첨부파일 섹션은 제외
                    if div.get('class') and ('file' in str(div.get('class')) or 'attach' in str(div.get('class'))):
                        continue
                    
                    text = div.get_text(strip=True)
                    if text and len(text) > 10:
                        if any(keyword in text for keyword in ['첨부파일', '이전글', '다음글', '목록보기']):
                            break
                        content_parts.append(text)
            
            # 3. 전체 텍스트 추출 후 정리 (마지막 수단)
            if not content_parts:
                text = content_element.get_text(strip=True)
                if text:
                    # 불필요한 네비게이션 텍스트 제거
                    unwanted_phrases = [
                        "작성일 :", "URL 복사하기", "첨부파일", "등록된 파일이 없습니다.",
                        "이전글", "다음글", "이전 게시글이 존재하지 않습니다.",
                        "다음 게시글이 존재하지 않습니다.", "목록", "조회수",
                        "파일 아이콘", "공지사항", "한글파일 아이콘", "pdf파일 아이콘"
                    ]
                    
                    for phrase in unwanted_phrases:
                        text = text.replace(phrase, "")
                    
                    # 연속된 공백 및 줄바꿈 정리
                    text = re.sub(r'\s+', ' ', text).strip()
                    
                    if text and len(text) > 20:
                        content_parts.append(text)
            
            # 결과 반환
            if content_parts:
                return '\n\n'.join(content_parts)
            else:
                logger.warning("본문 내용을 추출할 수 없습니다.")
                return ""
                
        except Exception as e:
            logger.error(f"본문 추출 중 오류: {str(e)}")
            return ""
    
    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """첨부파일 추출"""
        attachments = []
        
        # 첨부파일 섹션 찾기 (ul.view_file)
        attachment_section = soup.find('ul', class_='view_file')
        if not attachment_section:
            logger.debug("첨부파일 섹션(ul.view_file)을 찾을 수 없습니다.")
            return attachments
        
        # 첨부파일 링크 찾기 (onclick 속성에 fileDownload 함수 호출)
        file_links = attachment_section.find_all('a', onclick=re.compile(r'fileDownload'))
        
        logger.debug(f"첨부파일 링크 {len(file_links)}개 발견")
        
        for link in file_links:
            try:
                onclick = link.get('onclick', '')
                
                # span 요소에서 실제 파일명 추출
                span_elem = link.find('span')
                if not span_elem:
                    continue
                
                # em 태그(아이콘) 제거 후 파일명 추출
                filename_text = span_elem.get_text(strip=True)
                
                # fileDownload('fileNo','fileSeq','boardMngNo') 패턴 파싱
                match = re.search(r"fileDownload\('([^']+)','([^']+)','([^']+)'\)", onclick)
                if not match:
                    logger.debug(f"onclick 패턴 매칭 실패: {onclick}")
                    continue
                
                file_no = match.group(1)
                file_seq = match.group(2)
                board_mng_no = match.group(3)
                
                # 파일명 정리 (아이콘 텍스트 제거)
                filename = re.sub(r'^[^[]*\[첨부\d*\]', '[첨부' + file_seq + ']', filename_text)
                filename = filename.strip()
                
                if not filename:
                    logger.debug(f"파일명 추출 실패: {filename_text}")
                    continue
                
                # 파일 확장자 추출
                if '.' in filename:
                    file_ext = filename.split('.')[-1].upper()
                else:
                    file_ext = 'UNKNOWN'
                
                attachments.append({
                    'filename': filename,
                    'file_no': file_no,
                    'file_seq': file_seq,
                    'board_mng_no': board_mng_no,
                    'url': self.download_url,
                    'size': '',
                    'type': file_ext
                })
                
                logger.debug(f"첨부파일 추출 성공: {filename} (fileNo: {file_no}, fileSeq: {file_seq})")
                
            except Exception as e:
                logger.error(f"첨부파일 추출 중 오류: {e}")
                continue
        
        logger.info(f"첨부파일 {len(attachments)}개 추출")
        return attachments
    
    def get_detail_content(self, announcement: Dict[str, Any]) -> str:
        """상세 페이지 내용 가져오기"""
        try:
            data = {
                'boardMngNo': announcement['board_mng_no'],
                'boardNo': announcement['board_no']
            }
            
            response = self.session.post(self.detail_url, data=data, timeout=10)
            response.raise_for_status()
            
            return response.text
        except Exception as e:
            logger.error(f"상세 페이지 가져오기 실패: {e}")
            return ""
    
    
    def download_file(self, url: str, save_path: str, attachment_info: Dict[str, Any] = None) -> bool:
        """첨부파일 다운로드"""
        try:
            if not attachment_info:
                return False
            
            # POST 데이터 구성
            data = {
                'fileNo': attachment_info['file_no'],
                'fileSeq': attachment_info['file_seq'],
                'boardMngNo': attachment_info['board_mng_no']
            }
            
            response = self.session.post(self.download_url, data=data, timeout=30)
            response.raise_for_status()
            
            # 파일 내용 검증
            if len(response.content) < 100:
                logger.warning(f"파일 크기가 너무 작음: {len(response.content)} bytes")
                return False
            
            # Content-Type 확인
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' in content_type:
                logger.warning(f"HTML 응답 감지됨: {content_type}")
                return False
            
            # 파일 저장
            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"다운로드 완료: {save_path} ({len(response.content):,} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"파일 다운로드 실패: {e}")
            return False


def main():
    """메인 실행 함수 - 3페이지 수집"""
    import sys
    import os
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('energy_scraper.log', encoding='utf-8')
        ]
    )
    
    logger.info("="*60)
    logger.info("🚀 한국에너지공단 공지사항 스크래퍼 시작")
    logger.info("="*60)
    
    # 출력 디렉토리 설정
    output_dir = "output/energy"
    
    # 기존 출력 디렉토리 정리
    if os.path.exists(output_dir):
        import shutil
        logger.info(f"기존 출력 디렉토리 정리: {output_dir}")
        shutil.rmtree(output_dir)
    
    # 스크래퍼 초기화
    scraper = EnhancedEnergyScraper()
    
    try:
        # 3페이지 수집 실행 (첨부파일 포함)
        success = scraper.scrape_pages(max_pages=3, output_base="output/energy")
        
        if success:
            logger.info("✅ 스크래핑 완료!")
            
            # 통계 출력
            stats = scraper.get_stats()
            logger.info(f"📊 처리 통계: {stats}")
            
        else:
            logger.error("❌ 스크래핑 실패")
            return 1
            
    except KeyboardInterrupt:
        logger.info("⏹️  사용자에 의해 중단됨")
        return 1
    except Exception as e:
        logger.error(f"❌ 예상치 못한 오류: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())