# -*- coding: utf-8 -*-
"""
서울소셜벤처허브(SVHC) 스크래퍼 - Enhanced 버전
사이트: https://svhc.or.kr/Notice/?category=P488271h88
"""

import requests
from bs4 import BeautifulSoup
import os
import re
import logging
import time
from urllib.parse import urljoin, urlparse, parse_qs, unquote
from typing import Dict, List, Any, Optional
from enhanced_base_scraper import EnhancedBaseScraper

logger = logging.getLogger(__name__)

class EnhancedSvhcScraper(EnhancedBaseScraper):
    """서울소셜벤처허브 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        
        # 기본 설정
        self.base_url = "https://svhc.or.kr"
        self.list_url = "https://svhc.or.kr/Notice/?category=P488271h88"
        
        # 사이트별 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1
        
        # 사이트별 헤더 설정
        self.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        })
        self.session.headers.update(self.headers)
        
        # Base64 인코딩된 q 파라미터 (분석 결과)
        self.q_param = "YToxOntzOjEyOiJrZXl3b3JkX3R5cGUiO3M6MzoiYWxsIjt9"
        
        logger.info("서울소셜벤처허브 스크래퍼 초기화 완료")
    
    def get_list_url(self, page_num: int) -> str:
        """페이지 번호별 목록 URL 생성"""
        if page_num == 1:
            return self.list_url
        else:
            return f"{self.base_url}/Notice/?q={self.q_param}&page={page_num}&category=P488271h88"
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱 - 리스트 기반 구조 (수정된 버전)"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        try:
            # ul.li_body 요소들 찾기 (분석 결과에 따른 정확한 선택자)
            list_items = soup.find_all('ul', class_='li_body')
            logger.info(f"발견된 li_body 요소 수: {len(list_items)}")
            
            if not list_items:
                logger.warning("ul.li_body 요소를 찾을 수 없습니다")
                return announcements
            
            # 각 공고 항목 처리
            for list_elem in list_items:
                try:
                    # 제목과 링크 추출 (li.tit a.list_text_title)
                    title_li = list_elem.find('li', class_='tit')
                    if not title_li:
                        continue
                    
                    title_link = title_li.find('a', class_='list_text_title')
                    if not title_link:
                        continue
                    
                    # 제목 추출 (span 태그 안의 텍스트)
                    title_span = title_link.find('span')
                    if title_span:
                        title = title_span.get_text(strip=True)
                    else:
                        title = title_link.get_text(strip=True)
                    
                    if not title:
                        continue
                    
                    # 링크 URL 구성
                    href = title_link.get('href', '')
                    if href and not href.startswith('http'):
                        detail_url = urljoin(self.base_url, href)
                    else:
                        detail_url = href
                    
                    if not detail_url or 'javascript:' in detail_url:
                        continue
                    
                    # 공고 정보 구성
                    announcement = {
                        'title': title,
                        'url': detail_url
                    }
                    
                    # 추가 메타데이터 추출
                    try:
                        # 카테고리 (li.category a em)
                        category_li = list_elem.find('li', class_='category')
                        if category_li:
                            category_link = category_li.find('a')
                            if category_link:
                                category_em = category_link.find('em')
                                if category_em:
                                    category = category_em.get_text(strip=True)
                                    if category:
                                        announcement['category'] = category
                        
                        # 작성일 (li.time)
                        time_li = list_elem.find('li', class_='time')
                        if time_li:
                            # title 속성에서 정확한 날짜 추출
                            date_title = time_li.get('title', '')
                            if date_title and re.match(r'\d{4}-\d{2}-\d{2}', date_title):
                                announcement['date'] = date_title.split(' ')[0]  # 시간 부분 제거
                            else:
                                # 텍스트에서 상대적 시간 추출
                                date_text = time_li.get_text(strip=True)
                                if date_text:
                                    announcement['relative_date'] = date_text
                        
                        # 조회수 (li.read)
                        read_li = list_elem.find('li', class_='read')
                        if read_li:
                            read_text = read_li.get_text(strip=True)
                            # "조회수" 텍스트 제거하고 숫자만 추출
                            read_match = re.search(r'\d+', read_text)
                            if read_match:
                                announcement['views'] = int(read_match.group())
                        
                    except Exception as e:
                        logger.warning(f"메타데이터 추출 중 오류: {e}")
                    
                    announcements.append(announcement)
                    logger.debug(f"공고 추가: {title}")
                    
                except Exception as e:
                    logger.error(f"공고 항목 파싱 중 오류: {e}")
                    continue
            
            logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
            return announcements
            
        except Exception as e:
            logger.error(f"목록 페이지 파싱 실패: {e}")
            return announcements
    
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = {
            'content': '',
            'attachments': []
        }
        
        try:
            # 제목 추출
            title_elem = soup.find('h1')
            title = title_elem.get_text(strip=True) if title_elem else ""
            
            # 메타 정보 생성
            meta_info = []
            if title:
                meta_info.append(f"# {title}")
                meta_info.append("")
            
            # 본문 내용 추출
            content_parts = []
            
            # 방법 1: main 태그 내에서 본문 찾기
            main_content = soup.find('main')
            if main_content:
                # 네비게이션과 제목을 제외한 본문 영역 찾기
                content_divs = main_content.find_all(['div', 'section', 'article'])
                
                for div in content_divs:
                    # 네비게이션, 버튼 등 제외
                    if any(keyword in str(div.get('class', [])).lower() for keyword in ['nav', 'btn', 'button', 'paging']):
                        continue
                    
                    text_content = div.get_text(strip=True)
                    if len(text_content) > 50:  # 충분한 길이의 텍스트만
                        # HTML을 마크다운으로 변환
                        content_html = str(div)
                        content_markdown = self.h.handle(content_html)
                        content_parts.append(content_markdown.strip())
                        break
            
            # 방법 2: 본문을 찾지 못한 경우 paragraphs 찾기
            if not content_parts:
                paragraphs = soup.find_all('p')
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if len(text) > 20:
                        content_parts.append(text)
            
            # 방법 3: 모든 방법이 실패한 경우 전체 텍스트에서 추출
            if not content_parts:
                logger.warning("본문 영역을 찾을 수 없어 전체 텍스트에서 추출합니다")
                all_text = soup.get_text()
                # 불필요한 부분 제거
                cleaned_text = re.sub(r'\s+', ' ', all_text).strip()
                if len(cleaned_text) > 200:
                    content_parts.append(cleaned_text[:1000] + "...")
                else:
                    content_parts.append(cleaned_text)
            
            # 첨부파일 추출
            attachments = self._extract_attachments(soup)
            
            # 결과 조합
            if meta_info:
                meta_info.append("")
                meta_info.append("---")
                meta_info.append("")
            
            final_content = "\n".join(meta_info + content_parts)
            
            result = {
                'content': final_content,
                'attachments': attachments
            }
            
            logger.info(f"상세 페이지 파싱 완료 - 내용: {len(final_content)}자, 첨부파일: {len(attachments)}개")
            return result
            
        except Exception as e:
            logger.error(f"상세 페이지 파싱 실패: {e}")
            return result
    
    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """첨부파일 추출"""
        attachments = []
        
        try:
            # 방법 1: download나 file 관련 링크 찾기
            download_patterns = [
                r'download',
                r'file',
                r'attach',
                r'첨부',
                r'다운로드'
            ]
            
            for pattern in download_patterns:
                links = soup.find_all('a', href=re.compile(pattern, re.I))
                for link in links:
                    try:
                        href = link.get('href', '')
                        if not href:
                            continue
                        
                        # 파일 URL 구성
                        file_url = urljoin(self.base_url, href)
                        
                        # 파일명 추출
                        filename = link.get_text(strip=True)
                        if not filename:
                            # URL에서 파일명 추출 시도
                            parsed_url = urlparse(href)
                            if parsed_url.path:
                                filename = os.path.basename(parsed_url.path)
                        
                        if not filename:
                            filename = f"attachment_{len(attachments) + 1}"
                        
                        attachment = {
                            'filename': filename,
                            'url': file_url
                        }
                        
                        attachments.append(attachment)
                        logger.debug(f"첨부파일 발견: {filename} - {file_url}")
                        
                    except Exception as e:
                        logger.error(f"첨부파일 추출 중 오류: {e}")
                        continue
            
            # 방법 2: img 태그에서 이미지 파일 찾기 (본문 이미지가 아닌 첨부 이미지)
            img_tags = soup.find_all('img')
            for img in img_tags:
                try:
                    src = img.get('src', '')
                    if src and any(ext in src.lower() for ext in ['.jpg', '.png', '.gif', '.pdf', '.doc', '.hwp']):
                        file_url = urljoin(self.base_url, src)
                        filename = os.path.basename(urlparse(src).path)
                        
                        if filename and filename not in [att['filename'] for att in attachments]:
                            attachment = {
                                'filename': filename,
                                'url': file_url
                            }
                            attachments.append(attachment)
                            logger.debug(f"이미지 첨부파일 발견: {filename} - {file_url}")
                            
                except Exception as e:
                    logger.error(f"이미지 첨부파일 추출 중 오류: {e}")
                    continue
            
            logger.info(f"총 {len(attachments)}개 첨부파일 추출")
            return attachments
            
        except Exception as e:
            logger.error(f"첨부파일 추출 실패: {e}")
            return attachments
    
    def download_file(self, url: str, save_path: str, attachment_info: Dict[str, Any] = None) -> bool:
        """파일 다운로드 - SVHC 특화"""
        try:
            logger.info(f"파일 다운로드 시작: {url}")
            
            # 다운로드 헤더 설정
            download_headers = self.headers.copy()
            download_headers['Referer'] = self.base_url
            
            response = self.session.get(
                url,
                headers=download_headers,
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
            logger.info(f"다운로드 완료: {save_path} ({file_size:,} bytes)")
            
            # 파일 크기 검증
            if file_size == 0:
                logger.warning(f"다운로드된 파일 크기가 0입니다: {save_path}")
                return False
            elif file_size < 100:
                logger.warning(f"다운로드된 파일 크기가 너무 작습니다: {save_path} ({file_size} bytes)")
                # 파일 내용 확인
                with open(save_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(200)
                    if any(keyword in content.lower() for keyword in ['error', 'not found', '404', '403']):
                        logger.error(f"다운로드 실패 - 에러 응답: {content}")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"파일 다운로드 실패 {url}: {e}")
            return False


def test_svhc_scraper(pages: int = 3):
    """서울소셜벤처허브 스크래퍼 테스트"""
    print(f"서울소셜벤처허브 스크래퍼 테스트 시작 ({pages}페이지)")
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('svhc_scraper.log', encoding='utf-8')
        ]
    )
    
    # 출력 디렉토리 설정
    output_dir = "output/svhc"
    os.makedirs(output_dir, exist_ok=True)
    
    # 스크래퍼 실행
    scraper = EnhancedSvhcScraper()
    
    try:
        success = scraper.scrape_pages(max_pages=pages, output_base=output_dir)
        
        if success:
            print(f"\n=== 스크래핑 완료 ===")
            print(f"결과 저장 위치: {output_dir}")
            
            # 결과 통계
            verify_results(output_dir)
        else:
            print("스크래핑 실패")
            
    except Exception as e:
        print(f"스크래핑 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()


def verify_results(output_dir: str):
    """결과 검증"""
    print(f"\n=== 결과 검증 ===")
    
    try:
        # 폴더 수 확인
        if not os.path.exists(output_dir):
            print(f"출력 디렉토리가 존재하지 않습니다: {output_dir}")
            return
        
        folders = [d for d in os.listdir(output_dir) if os.path.isdir(os.path.join(output_dir, d))]
        print(f"생성된 공고 폴더 수: {len(folders)}")
        
        # 각 폴더별 통계
        total_files = 0
        total_size = 0
        attachment_counts = []
        
        for folder in folders:
            folder_path = os.path.join(output_dir, folder)
            
            # content.md 확인
            content_file = os.path.join(folder_path, 'content.md')
            if os.path.exists(content_file):
                size = os.path.getsize(content_file)
                print(f"  {folder}: content.md ({size:,} bytes)")
            else:
                print(f"  {folder}: content.md 없음")
            
            # 첨부파일 확인
            attachments_dir = os.path.join(folder_path, 'attachments')
            if os.path.exists(attachments_dir):
                files = os.listdir(attachments_dir)
                attachment_counts.append(len(files))
                for file in files:
                    file_path = os.path.join(attachments_dir, file)
                    file_size = os.path.getsize(file_path)
                    total_files += 1
                    total_size += file_size
                    print(f"    첨부파일: {file} ({file_size:,} bytes)")
            else:
                attachment_counts.append(0)
        
        # 통계 요약
        print(f"\n=== 통계 요약 ===")
        print(f"총 공고 수: {len(folders)}")
        print(f"총 첨부파일 수: {total_files}")
        print(f"총 첨부파일 크기: {total_size:,} bytes ({total_size/1024/1024:.2f} MB)")
        if attachment_counts:
            print(f"평균 첨부파일 수: {sum(attachment_counts)/len(attachment_counts):.1f}")
            print(f"최대 첨부파일 수: {max(attachment_counts)}")
        
    except Exception as e:
        print(f"결과 검증 중 오류: {e}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='서울소셜벤처허브 스크래퍼')
    parser.add_argument('--pages', type=int, default=3, help='스크래핑할 페이지 수 (기본값: 3)')
    parser.add_argument('--output', type=str, default='output/svhc', help='출력 디렉토리')
    
    args = parser.parse_args()
    
    test_svhc_scraper(args.pages)