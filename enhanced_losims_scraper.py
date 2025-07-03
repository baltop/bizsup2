# -*- coding: utf-8 -*-
"""
지방보조금관리시스템(LOSIMS) 공고 스크래퍼 - Enhanced 버전
URL: https://www.losims.go.kr/sp/pbcnBizSrch
"""

import requests
from bs4 import BeautifulSoup
import os
import time
import re
import json
from urllib.parse import urljoin, urlparse, unquote
import logging
from enhanced_base_scraper import EnhancedBaseScraper
from datetime import datetime

logger = logging.getLogger(__name__)

class EnhancedLosimsScraper(EnhancedBaseScraper):
    """지방보조금관리시스템 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        # 기본 설정
        self.base_url = "https://www.losims.go.kr"
        self.list_url = "https://www.losims.go.kr/sp/pbcnBizSrch"
        self.list_api_url = f"{self.base_url}/sp/pbcnBizSrchInq"
        self.detail_url_pattern = f"{self.base_url}/sp/pbcnBizCntt"
        self.file_check_url = f"{self.base_url}/sp/fileDownCheck"
        self.file_download_url = f"{self.base_url}/sp/pbcnBizSrch/fileDownload"
        self.file_info_url = f"{self.base_url}/sp/pbcnBizAtflInfoInq"
        self.guide_file_info_url = f"{self.base_url}/sp/pbcnBizGuiAtflInfoInq"
        
        # 사이트별 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 60
        self.delay_between_requests = 2  # AJAX 요청 간 대기
        self.delay_between_pages = 3  # 페이지 간 대기 시간
        
        # LOSIMS 특화 설정 - AJAX API 기반
        self.use_playwright = False  # API 호출 방식
        self.page_size = 20  # 페이지당 최대 항목 수
        
        # 세션 초기화
        self._init_session()
    
    def _init_session(self):
        """LOSIMS 세션 초기화"""
        try:
            logger.info("LOSIMS 사이트 세션 초기화 중...")
            
            # 1. 메인 페이지 접속으로 기본 쿠키/세션 획득
            main_response = self.session.get(self.list_url, timeout=self.timeout, verify=self.verify_ssl)
            main_response.raise_for_status()
            
            # 2. 필요한 헤더 설정
            self.session.headers.update({
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
                'Content-Type': 'application/json; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': self.list_url,
                'Origin': self.base_url
            })
            
            # 3. 첫 번째 API 호출로 세션 검증
            test_data = {
                "curPage": 1,
                "pageSize": 5,
                "pbacNm": "",
                "lafWa": "A",
                "lafPry": "A",
                "fyr": "2025",
                "sPbacDate": "",
                "ePbacDate": "",
                "sAplyDate": "",
                "eAplyDate": ""
            }
            
            test_response = self.session.post(self.list_api_url, json=test_data, timeout=self.timeout)
            test_response.raise_for_status()
            
            test_result = test_response.json()
            if 'prtlPbcnBizSrchInqInfoDao' in test_result:
                logger.info(f"세션 초기화 성공 - 총 {test_result.get('input', {}).get('totCnt', 0)}개 공고 확인")
            else:
                logger.warning("세션 초기화 경고: API 응답 구조가 예상과 다름")
                
        except Exception as e:
            logger.error(f"세션 초기화 실패: {e}")
            raise
    
    def get_list_url(self, page_num: int) -> str:
        """페이지별 목록 URL 생성 (API URL 반환)"""
        return self.list_api_url
    
    def _get_page_announcements(self, page_num: int) -> list:
        """API 호출을 통한 공고 목록 가져오기"""
        try:
            logger.info(f"페이지 {page_num} API 호출 중...")
            
            # AJAX API 호출 데이터
            api_data = {
                "curPage": page_num,
                "pageSize": self.page_size,
                "pbacNm": "",  # 공모명 (빈 문자열로 전체 검색)
                "lafWa": "A",  # 광역 (A = 전체)
                "lafPry": "A",  # 기초 (A = 전체)
                "fyr": "2025",  # 사업년도
                "sPbacDate": "",  # 공모시작일
                "ePbacDate": "",  # 공모종료일
                "sAplyDate": "",  # 접수시작일
                "eAplyDate": ""   # 접수종료일
            }
            
            # API 요청
            response = self.session.post(self.list_api_url, json=api_data, timeout=self.timeout)
            response.raise_for_status()
            
            # JSON 응답 파싱
            data = response.json()
            return self.parse_api_response(data)
            
        except Exception as e:
            logger.error(f"API 호출 실패 (페이지 {page_num}): {e}")
            return []
    
    def parse_api_response(self, data: dict) -> list:
        """API 응답 데이터 파싱"""
        announcements = []
        
        try:
            # API 응답에서 공고 목록 추출
            announcement_list = data.get('prtlPbcnBizSrchInqInfoDao', [])
            input_info = data.get('input', {})
            total_count = input_info.get('totCnt', 0)
            current_page = input_info.get('curPage', 1)
            
            logger.info(f"API 응답: 현재 페이지 {current_page}, 총 {total_count}개 공고 중 {len(announcement_list)}개 수신")
            
            for i, item in enumerate(announcement_list):
                try:
                    # 기본 정보 추출
                    pbac_no = item.get('pbacNo', '')  # 공모번호
                    fyr = item.get('fyr', '2025')  # 사업년도
                    title = item.get('pbacNm', '')  # 공모명
                    region = item.get('allLafNm', '')  # 지역명
                    
                    # 날짜 정보
                    announcement_start = item.get('pbacBgngYmd', '')  # 공모시작일
                    announcement_end = item.get('pbacEndYmd', '')  # 공모종료일
                    application_start = item.get('pbcnAplyRcptBgngYmd', '')  # 접수시작일
                    application_end = item.get('pbcnAplyRcptEndYmd', '')  # 접수종료일
                    
                    # 조회수
                    view_count = item.get('inqNum', '0')
                    
                    # 상세 페이지 URL 생성
                    detail_url = f"{self.detail_url_pattern}?id={pbac_no}&fyr={fyr}"
                    
                    # 번호는 공모번호 사용
                    number = pbac_no
                    
                    # 카테고리는 지역으로 설정
                    category = region
                    
                    # 날짜는 공모시작일 사용
                    date = announcement_start
                    
                    announcement = {
                        'number': number,
                        'category': category,
                        'title': title,
                        'url': detail_url,
                        'date': date,
                        'pbac_no': pbac_no,
                        'fyr': fyr,
                        'region': region,
                        'announcement_period': f"{announcement_start} ~ {announcement_end}",
                        'application_period': f"{application_start} ~ {application_end}",
                        'view_count': view_count,
                        'attachment_count': 0  # 상세페이지에서 확인
                    }
                    
                    announcements.append(announcement)
                    logger.info(f"공고 추가: [{pbac_no}] {region} - {title[:50]}...")
                    
                except Exception as e:
                    logger.error(f"공고 파싱 중 오류 (항목 {i}): {e}")
                    continue
            
            logger.info(f"총 {len(announcements)}개 공고 파싱 완료")
            return announcements
            
        except Exception as e:
            logger.error(f"API 응답 파싱 실패: {e}")
            return []
    
    def parse_list_page(self, html_content: str) -> list:
        """목록 페이지 파싱 - API 기반이므로 사용되지 않음"""
        # 이 메서드는 _get_page_announcements에서 API를 직접 호출하므로 사용되지 않음
        logger.warning("parse_list_page 호출됨 - API 기반 스크래퍼에서는 사용되지 않아야 함")
        return []
    
    def parse_detail_page(self, html_content: str) -> dict:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출
        title = ""
        title_selectors = [
            'h3.tit',
            '.tit',
            'h1',
            'h2',
            'h3'
        ]
        
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                title = title_elem.get_text(strip=True)
                if len(title) > 10:
                    break
        
        if not title:
            # 페이지 타이틀에서 추출
            page_title = soup.find('title')
            if page_title:
                title = page_title.get_text().strip()
        
        if not title:
            title = "제목 없음"
        
        # 본문 내용 추출
        content = ""
        
        # LOSIMS 특화 본문 영역 찾기
        content_selectors = [
            '.detail_cont',
            '.cont_area',
            '.content_area',
            '.detail_area',
            '.pbcn_detail'
        ]
        
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem and len(content_elem.get_text(strip=True)) > 100:
                content = self.h.handle(str(content_elem))
                break
        
        # 본문이 짧으면 모든 텍스트 영역에서 가장 긴 것 찾기
        if len(content.strip()) < 100:
            all_divs = soup.find_all('div')
            max_text = ""
            for div in all_divs:
                div_text = div.get_text(strip=True)
                if len(div_text) > len(max_text) and len(div_text) > 200:
                    # 하위 div가 적은 영역 선택 (순수 텍스트)
                    sub_divs = div.find_all('div')
                    if len(sub_divs) < 3:
                        max_text = div_text
            
            if max_text:
                content = max_text
        
        # 날짜 추출
        date = ""
        date_patterns = [
            r'(\d{4}-\d{2}-\d{2})',
            r'(\d{4}\.\d{2}\.\d{2})',
            r'(\d{4}/\d{2}/\d{2})'
        ]
        
        page_text = soup.get_text()
        for pattern in date_patterns:
            date_match = re.search(pattern, page_text)
            if date_match:
                date = date_match.group(1)
                break
        
        return {
            'title': title,
            'content': content,
            'date': date,
            'author': "지방보조금관리시스템",
            'attachments': []  # 첨부파일은 scrape_pages에서 별도 처리
        }
    
    def _extract_attachments_from_detail(self, soup: BeautifulSoup, announcement_data: dict = None) -> list:
        """상세 페이지에서 첨부파일 정보 추출 - AJAX API 활용"""
        attachments = []
        
        try:
            # 공고 정보에서 pbac_no와 fyr 추출
            pbac_no = announcement_data.get('pbac_no', '') if announcement_data else ''
            fyr = announcement_data.get('fyr', '2025') if announcement_data else '2025'
            
            if not pbac_no:
                # URL에서 추출 시도
                page_url = soup.find('meta', property='og:url')
                if page_url:
                    url_content = page_url.get('content', '')
                    pbac_match = re.search(r'id=([^&]+)', url_content)
                    if pbac_match:
                        pbac_no = pbac_match.group(1)
                
                # 현재 브라우저 URL에서 추출 시도 (JavaScript 변수 확인)
                if not pbac_no:
                    scripts = soup.find_all('script')
                    for script in scripts:
                        if script.string:
                            pbac_match = re.search(r'pbacNo["\']?\s*[:=]\s*["\']([^"\',\s]+)["\']', script.string)
                            if pbac_match:
                                pbac_no = pbac_match.group(1)
                                break
            
            logger.info(f"첨부파일 정보 조회: pbac_no={pbac_no}, fyr={fyr}")
            
            if pbac_no:
                # 일반 첨부파일 조회 (공고 관련 파일)
                normal_files = self._get_attachments_via_api(pbac_no, fyr, 'normal')
                attachments.extend(normal_files)
                logger.info(f"일반 첨부파일 {len(normal_files)}개 발견")
                
                # 안내 첨부파일 조회 (가이드 파일)
                guide_files = self._get_attachments_via_api(pbac_no, fyr, 'guide')
                attachments.extend(guide_files)
                logger.info(f"안내 첨부파일 {len(guide_files)}개 발견")
            else:
                logger.warning("pbac_no를 찾을 수 없어 API 조회를 건너뜁니다.")
            
            # API 조회가 실패한 경우 HTML에서 추출 시도
            if not attachments:
                logger.info("API 조회 실패, HTML 파싱으로 전환")
                html_files = self._extract_attachments_from_html(soup)
                attachments.extend(html_files)
                logger.info(f"HTML에서 {len(html_files)}개 첨부파일 발견")
            
        except Exception as e:
            logger.error(f"첨부파일 추출 중 오류: {e}")
        
        logger.info(f"총 {len(attachments)}개 첨부파일 추출 완료")
        return attachments
    
    def _get_attachments_via_api(self, pbac_no: str, fyr: str, file_type: str = 'normal') -> list:
        """AJAX API를 통한 첨부파일 정보 조회"""
        attachments = []
        
        try:
            if file_type == 'guide':
                api_url = self.guide_file_info_url
                api_data = {
                    "pbacNo": pbac_no,
                    "fyr": fyr
                }
            else:
                api_url = self.file_info_url
                api_data = {
                    "pbacNo": pbac_no,
                    "fyr": fyr
                }
            
            logger.info(f"{file_type} 파일 정보 API 호출: {api_url} with {api_data}")
            
            # JSON 헤더가 정확히 설정되었는지 확인
            headers = {
                'Content-Type': 'application/json; charset=UTF-8',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            response = self.session.post(api_url, json=api_data, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            # 응답 내용 로깅
            logger.info(f"API 응답 상태: {response.status_code}")
            logger.info(f"API 응답 Content-Type: {response.headers.get('Content-Type')}")
            
            try:
                file_data = response.json()
            except ValueError as e:
                logger.error(f"JSON 파싱 실패: {e}")
                logger.error(f"응답 내용 (처음 500자): {response.text[:500]}")
                return attachments
            
            logger.info(f"API 응답 데이터: {file_data}")
            
            # 응답 구조 파싱 - LOSIMS 특화
            file_list = []
            if isinstance(file_data, list):
                file_list = file_data
            elif isinstance(file_data, dict):
                # LOSIMS API 응답 구조에 맞는 키 확인
                if file_type == 'guide':
                    file_list = (file_data.get('prtlRsltGuiAtflDto', []) or 
                               file_data.get('guideFiles', []) or
                               file_data.get('files', []))
                else:
                    file_list = (file_data.get('prtlRsltAtflDto', []) or 
                               file_data.get('attachments', []) or 
                               file_data.get('files', []))
            
            logger.info(f"{file_type} 파일 목록 크기: {len(file_list)}")
            
            for i, file_item in enumerate(file_list):
                if isinstance(file_item, dict):
                    # LOSIMS API 응답 구조에 맞는 필드명 사용
                    filename = (file_item.get('sbmsnPprsNm') or  # LOSIMS 기본 파일명 필드
                              file_item.get('atflNm') or 
                              file_item.get('fileName') or 
                              f'{file_type}_첨부파일_{i+1}.file')
                    
                    atfl_grp_id = (file_item.get('atflGrpId') or 
                                 file_item.get('atfl_grp_id') or 
                                 file_item.get('fileGroupId', ''))
                    
                    atfl_snum = (file_item.get('atflSnum') or 
                               file_item.get('atfl_snum') or 
                               file_item.get('fileSeq') or 
                               str(i + 1))
                    
                    file_size = (file_item.get('atflSize') or 
                               file_item.get('fileSize') or 
                               file_item.get('size', ''))
                    
                    logger.info(f"파일 항목 {i+1}: filename={filename}, atflGrpId={atfl_grp_id}, atflSnum={atfl_snum}")
                    
                    if atfl_grp_id and atfl_snum:  # 필수 파라미터가 있어야 유효한 파일
                        attachment = {
                            'filename': filename,
                            'url': self.file_download_url,
                            'atfl_grp_id': atfl_grp_id,
                            'atfl_snum': atfl_snum,
                            'file_size': file_size,
                            'file_type': file_type
                        }
                        
                        attachments.append(attachment)
                        logger.info(f"✅ {file_type} 파일 발견: {filename} (ID: {atfl_grp_id}, SEQ: {atfl_snum})")
                    else:
                        logger.warning(f"⚠️  파일 {i+1} 스킵: 필수 파라미터 누락 (atflGrpId={atfl_grp_id}, atflSnum={atfl_snum})")
            
        except Exception as e:
            logger.error(f"{file_type} 파일 정보 API 조회 실패: {e}")
            import traceback
            logger.error(f"상세 오류: {traceback.format_exc()}")
        
        return attachments
    
    def _extract_attachments_from_html(self, soup: BeautifulSoup) -> list:
        """HTML에서 첨부파일 정보 추출 (백업 방법)"""
        attachments = []
        
        try:
            # JavaScript 함수에서 파일 정보 추출
            script_texts = soup.find_all('script')
            
            for script in script_texts:
                if script.string:
                    script_content = script.string
                    
                    # fn_fileDown 호출 패턴 찾기
                    file_down_pattern = r'fn_fileDown\(["\']([^"\']+)["\'],\s*["\']([^"\']+)["\']'
                    matches = re.findall(file_down_pattern, script_content)
                    
                    for match in matches:
                        atfl_grp_id = match[0]
                        atfl_snum = match[1]
                        
                        attachment = {
                            'filename': f"첨부파일_{atfl_snum}.file",
                            'url': self.file_download_url,
                            'atfl_grp_id': atfl_grp_id,
                            'atfl_snum': atfl_snum,
                            'file_type': 'html_extracted'
                        }
                        
                        attachments.append(attachment)
                        logger.info(f"HTML에서 파일 발견: {atfl_grp_id}")
            
            # HTML에서 직접 파일 링크 찾기
            file_links = soup.find_all('a', href=re.compile(r'javascript:.*fn_fileDown'))
            
            for link in file_links:
                onclick = link.get('onclick', '')
                href = link.get('href', '')
                
                # onclick 또는 href에서 파라미터 추출
                combined_text = onclick + ' ' + href
                file_match = re.search(r'fn_fileDown\(["\']([^"\']+)["\'],\s*["\']([^"\']+)["\']', combined_text)
                
                if file_match:
                    atfl_grp_id = file_match.group(1)
                    atfl_snum = file_match.group(2)
                    
                    # 중복 확인
                    existing = any(att['atfl_grp_id'] == atfl_grp_id and att['atfl_snum'] == atfl_snum 
                                 for att in attachments)
                    
                    if not existing:
                        filename = link.get_text(strip=True)
                        if not filename:
                            filename = f"첨부파일_{atfl_snum}.file"
                        
                        attachment = {
                            'filename': filename,
                            'url': self.file_download_url,
                            'atfl_grp_id': atfl_grp_id,
                            'atfl_snum': atfl_snum,
                            'file_type': 'html_link'
                        }
                        
                        attachments.append(attachment)
                        logger.info(f"HTML 링크에서 파일 발견: {filename}")
            
        except Exception as e:
            logger.error(f"HTML 첨부파일 추출 중 오류: {e}")
        
        return attachments
    
    def _get_file_info(self, atfl_grp_id: str, atfl_snum: str) -> list:
        """파일 정보 API 호출"""
        try:
            # 일반 첨부파일 정보 조회
            file_info_data = {
                "atflGrpId": atfl_grp_id
            }
            
            response = self.session.post(self.file_info_url, json=file_info_data, timeout=self.timeout)
            response.raise_for_status()
            
            file_data = response.json()
            files = []
            
            # 응답에서 파일 목록 추출
            if isinstance(file_data, list):
                file_list = file_data
            elif isinstance(file_data, dict):
                file_list = file_data.get('files', file_data.get('data', []))
            else:
                file_list = []
            
            for file_item in file_list:
                if isinstance(file_item, dict):
                    filename = file_item.get('atflNm', file_item.get('filename', f'첨부파일_{atfl_snum}.file'))
                    file_size = file_item.get('atflSize', file_item.get('fileSize', ''))
                    
                    attachment = {
                        'filename': filename,
                        'url': self.file_download_url,
                        'atfl_grp_id': atfl_grp_id,
                        'atfl_snum': atfl_snum,
                        'file_size': file_size
                    }
                    
                    files.append(attachment)
                    logger.debug(f"파일 정보 조회 성공: {filename}")
            
            return files
            
        except Exception as e:
            logger.debug(f"파일 정보 조회 실패 ({atfl_grp_id}): {e}")
            
            # 기본 정보로 첨부파일 객체 생성
            return [{
                'filename': f"첨부파일_{atfl_snum}.file",
                'url': self.file_download_url,
                'atfl_grp_id': atfl_grp_id,
                'atfl_snum': atfl_snum
            }]
    
    def download_file(self, file_url: str, save_path: str, **kwargs) -> bool:
        """LOSIMS 특화 파일 다운로드"""
        try:
            # kwargs에서 필요한 파라미터 추출
            atfl_grp_id = kwargs.get('atfl_grp_id')
            atfl_snum = kwargs.get('atfl_snum')
            
            if not atfl_grp_id or not atfl_snum:
                logger.error("파일 다운로드에 필요한 파라미터 누락")
                return False
            
            logger.info(f"파일 다운로드 시도: {save_path}")
            
            # 1단계: 파일 다운로드 가능 여부 확인 (JSON 형식)
            check_data = {
                "atflGrpId": atfl_grp_id,
                "atflSnum": atfl_snum
            }
            
            check_headers = {
                'Content-Type': 'application/json; charset=UTF-8',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            logger.info(f"파일 다운로드 권한 확인: {check_data}")
            check_response = self.session.post(self.file_check_url, json=check_data, headers=check_headers, timeout=self.timeout)
            check_response.raise_for_status()
            
            # 권한 확인 응답 체크
            try:
                check_result = check_response.json()
                logger.info(f"권한 확인 응답: {check_result}")
                
                if check_result.get('message', {}).get('status') != 'SUCCESS':
                    logger.error(f"파일 다운로드 권한 없음: {check_result}")
                    return False
            except ValueError as e:
                logger.error(f"권한 확인 응답 파싱 실패: {e}")
                return False
            
            # 2단계: 실제 파일 다운로드 (Form POST)
            download_data = {
                'atflGrpId': atfl_grp_id,
                'atflSnum': str(atfl_snum)  # 문자열로 변환
            }
            
            logger.info(f"파일 다운로드 요청: {download_data}")
            
            # Form 기반 POST 요청 - 브라우저 폼 제출과 동일하게
            download_headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Referer': self.list_url,  # 중요: 어디서 왔는지 명시
                'Origin': self.base_url,
                'Upgrade-Insecure-Requests': '1'
            }
            
            download_response = self.session.post(
                self.file_download_url, 
                data=download_data,  # JSON이 아닌 form data
                headers=download_headers,
                timeout=self.timeout * 2,
                stream=True,
                allow_redirects=True  # 리다이렉트 허용
            )
            download_response.raise_for_status()
            
            # Content-Type 확인
            content_type = download_response.headers.get('Content-Type', '').lower()
            if 'text/html' in content_type:
                logger.error(f"다운로드 실패 - HTML 페이지 반환: {content_type}")
                return False
            
            # 파일명 추출 및 저장
            actual_filename = self._extract_filename_from_response(download_response, save_path)
            
            # 파일 저장
            with open(actual_filename, 'wb') as f:
                for chunk in download_response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(actual_filename)
            logger.info(f"파일 다운로드 완료: {actual_filename} ({file_size:,} bytes)")
            
            return True
            
        except Exception as e:
            logger.error(f"파일 다운로드 실패 {save_path}: {e}")
            return False
    
    def _extract_filename_from_response(self, response, default_path):
        """응답 헤더에서 파일명 추출"""
        save_dir = os.path.dirname(default_path)
        original_filename = os.path.basename(default_path)
        
        content_disposition = response.headers.get('Content-Disposition', '')
        
        if content_disposition:
            # RFC 5987 형식 처리
            rfc5987_match = re.search(r"filename\*=([^']*)'([^']*)'(.+)", content_disposition)
            if rfc5987_match:
                encoding, lang, encoded_filename = rfc5987_match.groups()
                try:
                    decoded_filename = unquote(encoded_filename, encoding=encoding or 'utf-8')
                    clean_filename = self.sanitize_filename(decoded_filename)
                    return os.path.join(save_dir, clean_filename)
                except Exception as e:
                    logger.debug(f"RFC 5987 디코딩 실패: {e}")
            
            # 일반 filename 파라미터 처리
            filename_match = re.search(r'filename[^;=\n]*=([\'"]*)(.*?)\1', content_disposition)
            if filename_match:
                raw_filename = filename_match.group(2)
                
                # 한글 파일명 다단계 디코딩
                decodings_to_try = [
                    lambda x: unquote(x, encoding='utf-8'),
                    lambda x: unquote(x, encoding='euc-kr'),
                    lambda x: x.encode('latin-1').decode('utf-8'),
                    lambda x: x.encode('latin-1').decode('euc-kr'),
                    lambda x: x
                ]
                
                for decode_func in decodings_to_try:
                    try:
                        decoded = decode_func(raw_filename)
                        if decoded and len(decoded) > 0:
                            if any(ord(char) > 127 for char in decoded) or '.' in decoded:
                                clean_filename = self.sanitize_filename(decoded)
                                return os.path.join(save_dir, clean_filename)
                    except:
                        continue
        
        # 기존 파일명 사용
        return os.path.join(save_dir, self.sanitize_filename(original_filename))
    
    def sanitize_filename(self, filename: str) -> str:
        """파일명 정리"""
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = filename.replace('\n', '').replace('\t', '').strip()
        return filename[:200]  # 파일명 길이 제한
    
    def scrape_pages(self, max_pages: int = 3, output_base: str = "output") -> dict:
        """페이지 스크래핑 실행"""
        results = {
            'total_announcements': 0,
            'total_files': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'pages_processed': 0
        }
        
        try:
            for page_num in range(1, max_pages + 1):
                logger.info(f"\n{'='*50}")
                logger.info(f"페이지 {page_num} 처리 시작")
                logger.info(f"{'='*50}")
                
                # API를 통한 공고 목록 가져오기
                announcements = self._get_page_announcements(page_num)
                
                if not announcements:
                    logger.warning(f"페이지 {page_num}에서 공고를 찾을 수 없음")
                    break
                
                results['total_announcements'] += len(announcements)
                
                # 각 공고 처리
                for announcement in announcements:
                    try:
                        # 상세 페이지 가져오기
                        detail_response = self.get_page(announcement['url'])
                        if not detail_response:
                            continue
                        
                        detail_html = detail_response.text
                        
                        # 상세 정보 파싱 (공고 정보 전달)
                        detail_info = self.parse_detail_page(detail_html)
                        
                        # 첨부파일 추출 시 공고 정보 전달
                        detail_info['attachments'] = self._extract_attachments_from_detail(
                            BeautifulSoup(detail_html, 'html.parser'), 
                            announcement
                        )
                        
                        # 출력 디렉토리 생성
                        safe_title = self.sanitize_filename(announcement['title'][:50])
                        announcement_dir = os.path.join(output_base, f"{announcement['number']}_{safe_title}")
                        os.makedirs(announcement_dir, exist_ok=True)
                        
                        # 본문 저장
                        content_file = os.path.join(announcement_dir, "content.md")
                        with open(content_file, 'w', encoding='utf-8') as f:
                            f.write(f"# {detail_info['title']}\n\n")
                            f.write(f"- 카테고리: {announcement['category']}\n")
                            f.write(f"- 공모번호: {announcement['number']}\n")
                            f.write(f"- 지역: {announcement['region']}\n")
                            f.write(f"- 날짜: {detail_info['date']}\n")
                            f.write(f"- 공모기간: {announcement['announcement_period']}\n")
                            f.write(f"- 접수기간: {announcement['application_period']}\n")
                            f.write(f"- 조회수: {announcement['view_count']}\n")
                            f.write(f"- 원본 URL: {announcement['url']}\n\n")
                            f.write("## 본문\n\n")
                            f.write(detail_info['content'])
                        
                        # 첨부파일 다운로드
                        if detail_info['attachments']:
                            attachments_dir = os.path.join(announcement_dir, "attachments")
                            os.makedirs(attachments_dir, exist_ok=True)
                            
                            for attachment in detail_info['attachments']:
                                file_path = os.path.join(attachments_dir, attachment['filename'])
                                
                                results['total_files'] += 1
                                
                                # 다운로드 파라미터 전달
                                download_kwargs = {
                                    'atfl_grp_id': attachment.get('atfl_grp_id'),
                                    'atfl_snum': attachment.get('atfl_snum')
                                }
                                
                                if self.download_file(attachment['url'], file_path, **download_kwargs):
                                    results['successful_downloads'] += 1
                                else:
                                    results['failed_downloads'] += 1
                        
                        logger.info(f"공고 처리 완료: {announcement['title'][:50]}...")
                        
                    except Exception as e:
                        logger.error(f"공고 처리 중 오류: {e}")
                        continue
                
                results['pages_processed'] += 1
                
                # 페이지 간 대기
                if page_num < max_pages:
                    time.sleep(self.delay_between_pages)
            
        except Exception as e:
            logger.error(f"스크래핑 중 오류: {e}")
        
        return results

def test_losims_scraper(pages=3):
    """LOSIMS 스크래퍼 테스트"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    scraper = EnhancedLosimsScraper()
    output_dir = "output/losims"
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"LOSIMS 스크래퍼 테스트 시작 - {pages}페이지")
    results = scraper.scrape_pages(max_pages=pages, output_base=output_dir)
    
    logger.info(f"\n{'='*50}")
    logger.info("테스트 결과 요약")
    logger.info(f"{'='*50}")
    logger.info(f"처리된 페이지: {results['pages_processed']}")
    logger.info(f"총 공고 수: {results['total_announcements']}")
    logger.info(f"총 파일 수: {results['total_files']}")
    logger.info(f"다운로드 성공: {results['successful_downloads']}")
    logger.info(f"다운로드 실패: {results['failed_downloads']}")
    
    if results['total_files'] > 0:
        success_rate = (results['successful_downloads'] / results['total_files']) * 100
        logger.info(f"성공률: {success_rate:.1f}%")
    
    return results

if __name__ == "__main__":
    test_losims_scraper(3)