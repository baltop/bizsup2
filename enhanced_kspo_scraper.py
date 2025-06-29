#!/usr/bin/env python3
"""
Enhanced KSPO (체육진흥공단) 스크래퍼

KSPO 공지사항 게시판에서 공고를 수집하는 스크래퍼입니다.
표준 HTML 테이블 기반 사이트이므로 BeautifulSoup으로 파싱합니다.

URL: https://www.kspo.or.kr/kspo/bbs/B0000027/list.do?menuNo=200149
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


class EnhancedKspoScraper(StandardTableScraper):
    """KSPO 전용 Enhanced 스크래퍼 - 표준 테이블 기반"""
    
    def __init__(self):
        super().__init__()
        
        # KSPO 사이트 설정
        self.base_url = "https://www.kspo.or.kr"
        self.list_url = "https://www.kspo.or.kr/kspo/bbs/B0000027/list.do?menuNo=200149"
        
        # 사이트별 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1
        
        # 고정 파라미터
        self.menu_no = "200149"
        self.bbs_id = "B0000027"
        
    def get_list_url(self, page_num: int) -> str:
        """페이지별 URL 생성"""
        if page_num == 1:
            return f"{self.list_url}&searchWrd=&pageIndex=1"
        else:
            return f"{self.list_url}&searchWrd=&pageIndex={page_num}"
        
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 게시판 테이블 찾기
        table = soup.find('table')
        if not table:
            logger.error("게시판 테이블을 찾을 수 없습니다")
            return announcements
            
        tbody = table.find('tbody')
        if not tbody:
            logger.error("테이블 본문을 찾을 수 없습니다")
            return announcements
            
        rows = tbody.find_all('tr')
        logger.info(f"발견된 행 수: {len(rows)}")
        
        for i, row in enumerate(rows):
            try:
                cells = row.find_all('td')
                if len(cells) < 6:
                    continue
                    
                # 번호 (첫 번째 셀) - "공지" 또는 숫자
                number_cell = cells[0]
                number = number_cell.get_text(strip=True)
                
                # 구분 (두 번째 셀)
                category_cell = cells[1]
                category = category_cell.get_text(strip=True)
                
                # 제목 (세 번째 셀)
                title_cell = cells[2]
                title_link = title_cell.find('a')
                if not title_link:
                    continue
                    
                title = title_link.get_text(strip=True)
                href = title_link.get('href', '')
                
                # 상대 URL을 절대 URL로 변환
                if href.startswith('/'):
                    detail_url = self.base_url + href
                else:
                    detail_url = urljoin(self.base_url, href)
                
                # 등록일 (네 번째 셀)
                date_cell = cells[3]
                date = date_cell.get_text(strip=True)
                
                # 첨부파일 (다섯 번째 셀) - PC에서만 표시
                attach_cell = cells[4]
                has_attachments = bool(attach_cell.find('a'))
                
                # 조회수 (여섯 번째 셀)
                views_cell = cells[5]
                views = views_cell.get_text(strip=True)
                
                announcement = {
                    'number': number,
                    'title': title,
                    'date': date,
                    'views': views,
                    'url': detail_url,
                    'category': category,
                    'has_attachments': has_attachments
                }
                
                announcements.append(announcement)
                logger.info(f"공고 추가: [{number}] {title}")
                
            except Exception as e:
                logger.error(f"행 {i} 파싱 실패: {e}")
                continue
                
        logger.info(f"총 {len(announcements)}개 공고 수집완료")
        return announcements
        
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱 - KSPO 구조에 최적화"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # KSPO 공지사항 구조에 맞는 선택자 사용
        article = soup.select_one('article.bbs-view')
        if not article:
            logger.warning("KSPO 공지사항 구조를 찾을 수 없습니다")
            return {
                'content': "본문 내용을 찾을 수 없습니다.",
                'attachments': []
            }
        
        # 제목 추출 (KSPO 구조)
        title_elem = article.select_one('h3.tit')
        title = title_elem.get_text(strip=True) if title_elem else "제목 없음"
        
        # 본문 내용 추출 (핵심 부분)
        content_div = article.select_one('div.cont')
        if content_div:
            content_text = self.simple_html_to_text(content_div)
        else:
            logger.warning("본문 내용(div.cont)을 찾을 수 없습니다")
            content_text = "본문 내용을 찾을 수 없습니다."
        
        # 메타 정보 추출 (KSPO 구조)
        meta_info = self.extract_meta_info(article)
        
        # 첨부파일 추출 (KSPO 구조)
        attachments = self._extract_attachments(article)
        
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
        
    def extract_meta_info(self, article: BeautifulSoup) -> Dict[str, str]:
        """KSPO 구조에서 메타 정보 추출"""
        meta_info = {}
        
        # KSPO의 .etc div에서 정보 추출
        etc_div = article.select_one('.etc')
        if etc_div:
            # 등록일 추출
            date_elem = etc_div.select_one('.date')
            if date_elem:
                date_text = date_elem.get_text(strip=True)
                # "등록일 : 2025-06-23" -> "2025-06-23"
                meta_info['작성일'] = date_text.replace('등록일 :', '').strip()
            
            # 조회수 추출
            hit_elem = etc_div.select_one('.hit')
            if hit_elem:
                hit_text = hit_elem.get_text(strip=True)
                # "조회수 : 634" -> "634"
                meta_info['조회수'] = hit_text.replace('조회수 :', '').strip()
            
            # 작성자 추출 (마지막 span)
            spans = etc_div.find_all('span')
            if len(spans) >= 3:
                author_text = spans[-1].get_text(strip=True)
                if author_text and author_text not in ['등록일', '조회수']:
                    # "작성자 : 체육인복지팀" -> "체육인복지팀"
                    meta_info['작성자'] = author_text.replace('작성자 :', '').strip()
        
        # 담당부서 정보 (하단에서 추출)
        bot_div = article.select_one('.bot')
        if bot_div:
            writer_elems = bot_div.select('.writer')
            for writer in writer_elems:
                writer_text = writer.get_text(strip=True)
                if '담당부서' in writer_text:
                    meta_info['담당부서'] = writer_text.replace('담당부서 :', '').strip()
                elif '담당자' in writer_text:
                    meta_info['담당자'] = writer_text.replace('담당자 :', '').strip()
        
        return meta_info
        
    def simple_html_to_text(self, element) -> str:
        """HTML 요소를 간단한 텍스트로 변환"""
        # 단락 분리
        text = element.get_text(separator='\n\n', strip=True)
        
        # 과도한 공백 제거
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        
        return text
        
    def _extract_attachments(self, article: BeautifulSoup) -> List[Dict[str, Any]]:
        """KSPO 구조에서 첨부파일 정보 추출"""
        attachments = []
        
        # KSPO의 .view-att 영역에서 첨부파일 찾기
        view_att = article.select_one('.view-att')
        if view_att:
            # dl.att dd a 구조
            att_links = view_att.select('.att dd a')
            for link in att_links:
                href = link.get('href', '')
                filename = link.get_text(strip=True)
                
                if href and filename:
                    # 절대 URL로 변환
                    if href.startswith('/'):
                        file_url = self.base_url + href
                    else:
                        file_url = urljoin(self.base_url, href)
                    
                    # 파일 클래스 확인 (pdf, hwp, doc 등)
                    file_class = link.get('class', [])
                    file_type = file_class[0] if file_class else 'unknown'
                    
                    attachments.append({
                        'filename': filename,
                        'url': file_url,
                        'type': 'direct',
                        'file_type': file_type
                    })
                    logger.debug(f"첨부파일 발견: {filename} (타입: {file_type})")
        
        # 추가로 일반적인 fileDown.do 링크 확인
        file_links = article.find_all('a', href=True)
        for link in file_links:
            href = link.get('href', '')
            if 'fileDown.do' in href:
                filename = link.get_text(strip=True)
                
                if filename and href not in [att['url'] for att in attachments]:
                    # 절대 URL로 변환
                    if href.startswith('/'):
                        file_url = self.base_url + href
                    else:
                        file_url = urljoin(self.base_url, href)
                    
                    attachments.append({
                        'filename': filename,
                        'url': file_url,
                        'type': 'direct'
                    })
                    logger.debug(f"추가 첨부파일 발견: {filename}")
        
        # 중복 제거
        unique_attachments = []
        seen_urls = set()
        for attachment in attachments:
            if attachment['url'] not in seen_urls:
                unique_attachments.append(attachment)
                seen_urls.add(attachment['url'])
        
        logger.info(f"첨부파일 {len(unique_attachments)}개 발견")
        return unique_attachments
        
    def _download_attachments(self, attachments: List[Dict[str, Any]], folder_path: str):
        """첨부파일 다운로드 - KSPO 전용 오버라이드"""
        if not attachments:
            logger.info("첨부파일이 없습니다")
            return
        
        logger.info(f"{len(attachments)}개 첨부파일 다운로드 시작")
        attachments_folder = os.path.join(folder_path, 'attachments')
        os.makedirs(attachments_folder, exist_ok=True)
        
        for i, attachment in enumerate(attachments):
            try:
                url = attachment['url']
                filename = attachment.get('filename', f'attachment_{i+1}')
                
                # 파일명 정리
                clean_filename = self.sanitize_filename(filename)
                file_path = os.path.join(attachments_folder, clean_filename)
                
                logger.info(f"  첨부파일 {i+1}: {filename}")
                
                # 헤더 설정
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Referer': self.list_url
                }
                
                response = self.session.get(url, headers=headers, stream=True, 
                                          timeout=self.timeout, verify=self.verify_ssl)
                response.raise_for_status()
                
                # Content-Disposition에서 파일명 추출 시도
                content_disposition = response.headers.get('Content-Disposition', '')
                if content_disposition:
                    extracted_filename = self.extract_filename_from_disposition(content_disposition)
                    if extracted_filename:
                        clean_filename = self.sanitize_filename(extracted_filename)
                        file_path = os.path.join(attachments_folder, clean_filename)
                
                # 파일 저장
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                file_size = os.path.getsize(file_path)
                logger.info(f"파일 다운로드 완료: {clean_filename} ({file_size} bytes)")
                
            except Exception as e:
                logger.error(f"첨부파일 다운로드 실패 - {filename}: {e}")
                continue
            
    def extract_filename_from_disposition(self, content_disposition: str) -> str:
        """Content-Disposition 헤더에서 파일명 추출"""
        try:
            # RFC 5987 형식 우선 처리
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
                
                # UTF-8 디코딩 시도
                try:
                    if filename.encode('latin-1'):
                        decoded = filename.encode('latin-1').decode('utf-8')
                        return decoded.replace('+', ' ')
                except:
                    pass
                        
                return filename.replace('+', ' ')
                
        except Exception as e:
            logger.debug(f"파일명 추출 실패: {e}")
            
        return None


def main():
    """메인 실행 함수"""
    scraper = EnhancedKspoScraper()
    
    try:
        # 3페이지까지 수집
        output_dir = "output/kspo"
        os.makedirs(output_dir, exist_ok=True)
        
        result = scraper.scrape_pages(max_pages=3, output_base=output_dir)
        
        print(f"\n✅ KSPO 스크래핑 완료!")
        print(f"수집된 공고: {result['total_announcements']}개")
        print(f"다운로드된 파일: {result['total_files']}개")
        print(f"성공률: {result['success_rate']:.1f}%")
        
    except Exception as e:
        print(f"❌ 스크래핑 실패: {e}")


if __name__ == "__main__":
    main()