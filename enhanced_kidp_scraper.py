# -*- coding: utf-8 -*-
"""
Enhanced KIDP 스크래퍼 - JavaScript 실행 기반
한국디자인진흥원 전용 스크래퍼 (Enhanced 아키텍처)
kidp_scraper.py 기반 리팩토링
"""

from enhanced_base_scraper import JavaScriptScraper
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
import os
import logging

logger = logging.getLogger(__name__)

class EnhancedKIDPScraper(JavaScriptScraper):
    """한국디자인진흥원 전용 스크래퍼 - Enhanced 버전"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://kidp.or.kr"
        self.list_url = "https://kidp.or.kr/?menuno=1202"
        
    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 반환"""
        # KIDP는 pageIndex 파라미터를 사용
        if page_num == 1:
            return f"{self.list_url}&mode=list"
        else:
            return f"{self.list_url}&mode=list&pageIndex={page_num}"
            
    def parse_list_page(self, html_content: str) -> list:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 테이블 찾기 - board01-list 클래스나 summary 속성으로 찾기
        table = soup.find('table', class_='board01-list') or soup.find('table', attrs={'summary': lambda x: x and '번호' in x})
        if not table:
            # 모든 테이블을 확인하여 tbody가 있는 것 찾기
            tables = soup.find_all('table')
            for t in tables:
                if t.find('tbody') and len(t.find('tbody').find_all('tr')) > 0:
                    table = t
                    break
            
        if not table:
            logger.warning("게시판 테이블을 찾을 수 없습니다")
            return announcements
            
        tbody = table.find('tbody')
        if not tbody:
            logger.warning("테이블 tbody를 찾을 수 없습니다")
            return announcements
            
        rows = tbody.find_all('tr')
        logger.info(f"테이블에서 {len(rows)}개 행 발견")
        
        for i, row in enumerate(rows):
            try:
                tds = row.find_all('td')
                if len(tds) < 4:
                    logger.debug(f"행 {i}: 컬럼 수 부족 ({len(tds)}개)")
                    continue
                
                # 번호
                num = tds[0].get_text(strip=True)
                
                # 제목 및 링크
                title_td = tds[1]
                link_elem = title_td.find('a')
                if not link_elem:
                    logger.debug(f"행 {i}: 링크 요소 없음")
                    continue
                    
                title = link_elem.get_text(strip=True)
                if not title:
                    logger.debug(f"행 {i}: 제목 없음")
                    continue
                
                # onclick에서 seq 추출
                onclick = link_elem.get('onclick', '')
                seq_match = re.search(r"submitForm\(this,'(\w+)',(\d+)\)", onclick)
                if seq_match:
                    action = seq_match.group(1)
                    seq = seq_match.group(2)
                    # 상세 페이지 URL 구성 - 실제 상세페이지 URL 패턴 사용
                    detail_url = f"{self.base_url}/?menuno=1202&bbsno={seq}&siteno=16&act=view&ztag=rO0ABXQAMzxjYWxsIHR5cGU9ImJvYXJkIiBubz0iNjIyIiBza2luPSJraWRwX2JicyI%2BPC9jYWxsPg%3D%3D"
                else:
                    logger.debug(f"행 {i}: onclick에서 seq 추출 실패 - {onclick}")
                    continue
                
                # 날짜
                date = tds[2].get_text(strip=True) if len(tds) > 2 else ''
                
                # 조회수
                views = tds[3].get_text(strip=True) if len(tds) > 3 else ''
                
                # 첨부파일 여부
                has_attachment = False
                if len(tds) > 4:
                    # 첨부파일 아이콘 확인
                    file_img = tds[4].find('img')
                    if file_img:
                        has_attachment = True
                
                announcements.append({
                    'title': title,
                    'url': detail_url,
                    'date': date,
                    'views': views,
                    'has_attachment': has_attachment,
                    'seq': seq,
                    'num': num
                })
                
                logger.debug(f"공고 {i+1} 파싱 완료: {title[:30]}...")
                
            except Exception as e:
                logger.error(f"행 {i} 파싱 중 오류: {e}")
                continue
                
        logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
        return announcements
        
    def parse_detail_page(self, html_content: str) -> dict:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 본문 내용 찾기
        content_area = self._find_content_area(soup)
        
        # 첨부파일 찾기
        attachments = self._extract_attachments(soup)
        
        # 본문을 마크다운으로 변환
        content_md = ""
        if content_area:
            content_md = self.h.handle(str(content_area))
            logger.debug(f"본문 변환 완료: {len(content_md)} 문자")
        else:
            # 전체 페이지에서 헤더/푸터 제외하고 추출 시도
            main_content = soup.find('div', class_='content_wrap') or soup.find('div', id='content')
            if main_content:
                content_md = self.h.handle(str(main_content))
                logger.debug("전체 페이지에서 본문 추출")
            else:
                logger.warning("본문 영역을 찾을 수 없습니다")
                
        return {
            'content': content_md,
            'attachments': attachments
        }
    
    def _find_content_area(self, soup):
        """본문 영역 찾기"""
        # KIDP 특화 선택자들 우선 시도
        kidp_selectors = [
            'div.board_view_data',
            'div.board_view_content',
            'div.view_data', 
            'div.contents_view',
            'td[class*="content"]',
            '.view_con'
        ]
        
        for selector in kidp_selectors:
            content_area = soup.select_one(selector)
            if content_area:
                logger.debug(f"KIDP 본문 영역 발견: {selector}")
                return content_area
        
        # 일반적인 본문 선택자들
        content_selectors = [
            'div.board_view',
            'div.view_content',
            'div.board_content',
            'div.content_view',
            'td.content',
            'div.view_body',
            'div.bbs_content',
            'div.view_area'
        ]
        
        for selector in content_selectors:
            content_area = soup.select_one(selector)
            if content_area:
                logger.debug(f"본문 영역 발견: {selector}")
                return content_area
                
        # 테이블 구조에서 본문 찾기 - KIDP는 테이블 기반
        for table in soup.find_all('table'):
            for tr in table.find_all('tr'):
                th = tr.find('th')
                if th and '내용' in th.get_text():
                    content_area = tr.find('td')
                    if content_area:
                        logger.debug("테이블 구조에서 본문 발견")
                        return content_area
        
        # 최후 수단: 본문으로 추정되는 긴 텍스트 영역 찾기
        for td in soup.find_all('td'):
            text_length = len(td.get_text(strip=True))
            if text_length > 200:  # 200자 이상의 텍스트가 있는 셀
                # 네비게이션이나 메뉴가 아닌지 확인
                if not any(menu_word in td.get_text().lower() for menu_word in ['menu', 'navigation', 'nav', '목록', '검색']):
                    logger.debug(f"긴 텍스트 영역에서 본문 발견: {text_length}자")
                    return td
                        
        return None
    
    def _extract_attachments(self, soup):
        """첨부파일 추출"""
        attachments = []
        
        # 테이블에서 첨부파일 찾기 - KIDP는 테이블 구조 사용
        file_area = None
        for tr in soup.find_all('tr'):
            th = tr.find('th')
            if th and '첨부파일' in th.get_text():
                file_area = tr.find('td')
                if file_area:
                    break
                    
        if file_area:
            logger.debug("첨부파일 영역 발견")
            # 파일 링크 찾기
            file_links = file_area.find_all('a')
            for link in file_links:
                file_name = link.get_text(strip=True)
                
                # onclick 처리 - submitForm(this,'down',64274,'')
                onclick = link.get('onclick', '')
                if onclick and 'submitForm' in onclick:
                    # submitForm에서 파일 ID 추출
                    match = re.search(r"submitForm\(this,'down',(\d+)", onclick)
                    if match:
                        file_id = match.group(1)
                        # 다운로드용 URL은 실제로는 사용되지 않지만 식별용으로 유지
                        file_url = f"{self.base_url}/skin/board/Valid.html"
                        
                        # 파일명 정리 - (1) 등 제거
                        file_name = re.sub(r'\s*\(\d+\)\s*$', '', file_name)
                        
                        if file_name and not file_name.isspace():
                            attachments.append({
                                'name': file_name,
                                'url': file_url,
                                'file_id': file_id,
                                'detail_url': soup.find('meta', {'property': 'og:url'})['content'] if soup.find('meta', {'property': 'og:url'}) else None
                            })
                            logger.debug(f"첨부파일 발견: {file_name} (file_id: {file_id})")
        
        # 다른 패턴으로도 첨부파일 찾기
        if not attachments:
            # 직접 파일 링크 패턴
            download_patterns = [
                'a[href*="download"]',
                'a[href*="fileDown"]',
                'a[onclick*="download"]',
                'a[href*=".hwp"]',
                'a[href*=".pdf"]',
                'a[href*=".docx"]',
                'a[href*=".xlsx"]',
                'a[href*=".zip"]'
            ]
            
            for pattern in download_patterns:
                links = soup.select(pattern)
                for link in links:
                    file_name = link.get_text(strip=True)
                    file_url = link.get('href', '')
                    
                    if file_url and file_name:
                        # 상대 경로 처리
                        if not file_url.startswith(('http://', 'https://')):
                            file_url = urljoin(self.base_url, file_url)
                            
                        # 중복 제거
                        if not any(att['url'] == file_url for att in attachments):
                            attachments.append({
                                'name': file_name,
                                'url': file_url
                            })
                            logger.debug(f"직접 링크 첨부파일 발견: {file_name}")
        
        logger.info(f"총 {len(attachments)}개 첨부파일 발견")
        return attachments
    
    def download_file(self, url: str, save_path: str, attachment_info: dict = None) -> bool:
        """파일 다운로드 - KIDP 특화 처리"""
        try:
            logger.info(f"파일 다운로드 시작: {url}")
            
            # KIDP 특화 파일 다운로드 처리 - file_id가 있으면 KIDP 방식 사용
            if 'kidp.or.kr' in url and attachment_info and attachment_info.get('file_id'):
                return self._download_kidp_file(url, save_path, attachment_info)
            
            # 일반 파일 다운로드
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
            return True
            
        except Exception as e:
            logger.error(f"파일 다운로드 실패 {url}: {e}")
            return False
    
    def _download_kidp_file(self, url: str, save_path: str, attachment_info: dict = None) -> bool:
        """KIDP 전용 파일 다운로드 - JavaScript 폼 제출 방식"""
        try:
            # attachment_info에서 file_id 추출 (onclick에서 파싱된 값)
            file_id = attachment_info.get('file_id') if attachment_info else None
            
            if not file_id:
                logger.error("파일 ID를 찾을 수 없습니다")
                return False
            
            # KIDP의 실제 다운로드 엔드포인트
            download_url = f"{self.base_url}/skin/board/Valid.html"
            
            # 상세 페이지 URL을 Referer로 설정
            detail_page_url = attachment_info.get('detail_url') if attachment_info else f"{self.base_url}/?menuno=1202&mode=list"
            
            # JavaScript submitForm()이 사용하는 것과 동일한 헤더
            headers = self.headers.copy()
            headers.update({
                'Referer': detail_page_url,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': self.base_url,
                'Upgrade-Insecure-Requests': '1'
            })
            
            # JavaScript submitForm()과 동일한 폼 데이터
            import time
            timestamp = int(time.time() * 1000)  # JavaScript의 new Date().getMilliseconds() 대체
            
            data = {
                'ztag': 'rO0ABXQAMzxjYWxsIHR5cGU9ImJvYXJkIiBubz0iNjIyIiBza2luPSJraWRwX2JicyI+PC9jYWxsPg==',
                'cates': '',
                'key': '',
                'keyword': '',
                'siteno': '16',
                'pageIndex': '1',
                'subname': '',
                'act': 'down',
                'fno': file_id  # JavaScript에서 setHidden('fno', n)으로 설정하는 값
            }
            
            # 타임스탬프를 URL에 추가 (JavaScript와 동일)
            full_download_url = f"{download_url}?{timestamp}"
            
            logger.debug(f"KIDP 파일 다운로드 시도: {full_download_url} with fno={file_id}")
            
            response = self.session.post(
                full_download_url,
                data=data,
                headers=headers,
                stream=True,
                allow_redirects=True,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            
            response.raise_for_status()
            
            # Content-Type 확인
            content_type = response.headers.get('Content-Type', '')
            content_disposition = response.headers.get('Content-Disposition', '')
            
            logger.debug(f"응답 헤더 - Content-Type: {content_type}, Content-Disposition: {content_disposition}")
            
            # HTML 응답인지 확인
            if 'text/html' in content_type and not content_disposition:
                # 응답의 첫 부분을 확인하여 실제로 HTML인지 체크
                peek_content = response.content[:200]
                if b'<!DOCTYPE html' in peek_content or b'<html' in peek_content:
                    logger.error(f"HTML 응답 받음 - 파일 다운로드 실패 (file_id: {file_id})")
                    logger.debug(f"응답 내용 시작: {peek_content}")
                    return False
            
            # 실제 파일명 추출
            actual_filename = self._extract_filename(response, save_path)
            if actual_filename != save_path:
                save_path = actual_filename
            
            # 파일 저장
            with open(save_path, 'wb') as f:
                if hasattr(response, 'iter_content'):
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                else:
                    f.write(response.content)
            
            file_size = os.path.getsize(save_path)
            logger.info(f"KIDP 파일 다운로드 완료: {save_path} ({file_size:,} bytes)")
            
            # 다운로드된 파일이 실제 파일인지 재확인
            with open(save_path, 'rb') as f:
                first_bytes = f.read(100)
                logger.debug(f"파일 시작 바이트: {first_bytes[:50]}")
                
                if b'<!DOCTYPE html' in first_bytes or b'<html' in first_bytes:
                    logger.error(f"❌ HTML 파일이 다운로드됨: {save_path}")
                    # HTML 파일로 저장하고 실패로 처리
                    html_path = save_path + '.html'
                    import shutil
                    shutil.move(save_path, html_path)
                    return False
                else:
                    logger.info(f"✅ 정상 파일 다운로드 확인: {file_size:,} bytes")
            
            return True
            
        except Exception as e:
            logger.error(f"KIDP 파일 다운로드 실패 {url}: {e}")
            return False
    
    def process_announcement(self, announcement: dict, index: int, output_base: str = 'output'):
        """개별 공고 처리 - KIDP 특화"""
        logger.info(f"공고 처리 중 {index}: {announcement['title']}")
        
        # 폴더 생성
        folder_title = self.sanitize_filename(announcement['title'])[:50]
        folder_name = f"{index:03d}_{folder_title}"
        folder_path = os.path.join(output_base, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        
        # 상세 페이지 가져오기
        response = self.get_page(announcement['url'])
        if not response:
            logger.error(f"상세 페이지 가져오기 실패: {announcement['title']}")
            return
            
        # 상세 내용 파싱
        try:
            detail = self.parse_detail_page(response.text)
            logger.info(f"상세 페이지 파싱 완료 - 내용길이: {len(detail['content'])}, 첨부파일: {len(detail['attachments'])}")
            
            # 첨부파일에 detail_url 추가
            for attachment in detail['attachments']:
                if not attachment.get('detail_url'):
                    attachment['detail_url'] = announcement['url']
                    
        except Exception as e:
            logger.error(f"상세 페이지 파싱 실패: {e}")
            return
        
        # 메타 정보 생성
        meta_info = self._create_meta_info(announcement)
        
        # 본문 저장
        content_path = os.path.join(folder_path, 'content.md')
        with open(content_path, 'w', encoding='utf-8') as f:
            f.write(meta_info + detail['content'])
            
        logger.info(f"내용 저장 완료: {content_path}")
        
        # 첨부파일 다운로드
        if detail['attachments']:
            logger.info(f"{len(detail['attachments'])}개 첨부파일 다운로드 시작")
            attachments_folder = os.path.join(folder_path, 'attachments')
            os.makedirs(attachments_folder, exist_ok=True)
            
            for i, attachment in enumerate(detail['attachments']):
                logger.info(f"  첨부파일 {i+1}: {attachment['name']}")
                file_name = self.sanitize_filename(attachment['name'])
                file_name = file_name.replace('+', ' ')
                
                if not file_name or file_name.isspace():
                    file_name = f"attachment_{i+1}"
                    
                file_path = os.path.join(attachments_folder, file_name)
                
                if self.download_file(attachment['url'], file_path, attachment):
                    logger.info(f"다운로드 성공: {attachment['name']}")
                else:
                    logger.warning(f"다운로드 실패: {attachment['name']}")
        else:
            logger.info("첨부파일이 없습니다")
        
        # 처리된 제목으로 추가
        self.add_processed_title(announcement['title'])
                
        # 요청 간 대기
        if self.delay_between_requests > 0:
            logger.debug(f"{self.delay_between_requests}초 대기")
            import time
            time.sleep(self.delay_between_requests)
    
    def _create_meta_info(self, announcement: dict) -> str:
        """메타 정보 생성"""
        meta_lines = [f"# {announcement['title']}", ""]
        
        # KIDP 특화 메타 정보
        meta_fields = {
            'num': '번호',
            'date': '작성일',
            'views': '조회수'
        }
        
        for field, label in meta_fields.items():
            if field in announcement and announcement[field]:
                meta_lines.append(f"**{label}**: {announcement[field]}")
        
        # 첨부파일 여부
        if announcement.get('has_attachment'):
            meta_lines.append("**첨부파일**: 있음")
        else:
            meta_lines.append("**첨부파일**: 없음")
        
        meta_lines.extend([
            f"**원본 URL**: {announcement['url']}",
            "",
            "---",
            ""
        ])
        
        return "\n".join(meta_lines)