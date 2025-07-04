# -*- coding: utf-8 -*-
"""
향상된 베이스 스크래퍼 - 설정 주입 및 특화된 베이스 클래스들
"""

import requests
from bs4 import BeautifulSoup
import os
import time
import html2text
from urllib.parse import urljoin, urlparse, parse_qs, unquote
import re
import json
import logging
import chardet
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Tuple
import hashlib
from datetime import datetime
import threading
from contextlib import contextmanager
import signal
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

class EnhancedBaseScraper(ABC):
    """향상된 베이스 스크래퍼 - 설정 주입 지원"""
    
    def __init__(self):
        # 기본 설정
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # HTML to text 변환기
        self.h = html2text.HTML2Text()
        self.h.ignore_links = False
        self.h.ignore_images = False
        
        # 기본값들
        self.verify_ssl = True
        self.default_encoding = 'auto'
        self.timeout = 120  # 기본 타임아웃 120초로 대폭 증가
        self.delay_between_requests = 1
        self.delay_between_pages = 1  # 페이지 간 대기시간 단축
        
        # 재시도 설정
        self.max_retries = 3
        self.retry_delay = 2
        
        # 성능 모니터링
        self.stats = {
            'requests_made': 0,
            'files_downloaded': 0,
            'errors_encountered': 0,
            'total_download_size': 0,
            'start_time': None,
            'end_time': None
        }
        
        # 스레드 안전성
        self._lock = threading.Lock()
        self._interrupted = False
        
        # 설정 객체 (선택적)
        self.config = None
        
        # 베이스 URL들 (하위 클래스에서 설정)
        self.base_url = None
        self.list_url = None
        
        # 중복 체크 관련
        self.processed_titles_file = None
        
        # 현재 페이지 번호 (페이지네이션 지원)
        self.current_page_num = 1
        self.processed_titles = set()  # 이전 실행에서 처리된 제목들
        self.current_session_titles = set()  # 현재 세션에서 처리된 제목들
        self.enable_duplicate_check = True
        self.duplicate_threshold = 3  # 동일 제목 3개 발견시 조기 종료
        
    def set_config(self, config):
        """설정 객체 주입"""
        self.config = config
        
        # 설정에서 값들 적용
        if config:
            self.base_url = config.base_url
            self.list_url = config.list_url
            self.verify_ssl = config.ssl_verify
            
            if config.encoding != 'auto':
                self.default_encoding = config.encoding
            
            # 헤더 업데이트
            if hasattr(config, 'user_agent') and config.user_agent:
                self.headers['User-Agent'] = config.user_agent
                self.session.headers.update(self.headers)
    
    @abstractmethod
    def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 반환"""
        pass
        
    @abstractmethod
    def parse_list_page(self, html_content: Union[str, int]) -> List[Dict[str, Any]]:
        """목록 페이지 파싱"""
        pass
        
    @abstractmethod
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱"""
        pass
    
    def get_page(self, url: str, **kwargs) -> Optional[requests.Response]:
        """페이지 가져오기 - 재시도 로직 포함"""
        for attempt in range(self.max_retries + 1):
            try:
                if self._interrupted:
                    logger.info("사용자에 의해 중단됨")
                    return None
                
                # 기본 옵션들
                options = {
                    'verify': self.verify_ssl,
                    'timeout': self.timeout,
                    **kwargs
                }
                
                with self._lock:
                    self.stats['requests_made'] += 1
                
                response = self.session.get(url, **options)
                response.raise_for_status()  # HTTP 에러 발생 시 예외 발생
                
                # 인코딩 처리
                self._fix_encoding(response)
                
                return response
                
            except requests.exceptions.RequestException as e:
                attempt_msg = f"시도 {attempt + 1}/{self.max_retries + 1}"
                
                if attempt < self.max_retries:
                    logger.warning(f"페이지 요청 실패 {url}: {e} - {attempt_msg}, {self.retry_delay}초 후 재시도")
                    time.sleep(self.retry_delay)
                    continue
                else:
                    logger.error(f"페이지 요청 최종 실패 {url}: {e} - {attempt_msg}")
                    with self._lock:
                        self.stats['errors_encountered'] += 1
                    return None
            except Exception as e:
                logger.error(f"예상치 못한 오류 {url}: {e}")
                with self._lock:
                    self.stats['errors_encountered'] += 1
                return None
        
        return None
    
    def post_page(self, url: str, data: Dict[str, Any] = None, **kwargs) -> Optional[requests.Response]:
        """POST 요청 - 재시도 로직 포함"""
        for attempt in range(self.max_retries + 1):
            try:
                if self._interrupted:
                    logger.info("사용자에 의해 중단됨")
                    return None
                
                options = {
                    'verify': self.verify_ssl,
                    'timeout': self.timeout,
                    **kwargs
                }
                
                with self._lock:
                    self.stats['requests_made'] += 1
                
                response = self.session.post(url, data=data, **options)
                response.raise_for_status()
                self._fix_encoding(response)
                
                return response
                
            except requests.exceptions.RequestException as e:
                attempt_msg = f"시도 {attempt + 1}/{self.max_retries + 1}"
                
                if attempt < self.max_retries:
                    logger.warning(f"POST 요청 실패 {url}: {e} - {attempt_msg}, {self.retry_delay}초 후 재시도")
                    time.sleep(self.retry_delay)
                    continue
                else:
                    logger.error(f"POST 요청 최종 실패 {url}: {e} - {attempt_msg}")
                    with self._lock:
                        self.stats['errors_encountered'] += 1
                    return None
            except Exception as e:
                logger.error(f"POST 예상치 못한 오류 {url}: {e}")
                with self._lock:
                    self.stats['errors_encountered'] += 1
                return None
        
        return None
    
    def _fix_encoding(self, response: requests.Response):
        """응답 인코딩 자동 수정"""
        if response.encoding is None or response.encoding == 'ISO-8859-1':
            if self.default_encoding == 'auto':
                # 자동 감지 시도
                try:
                    detected = chardet.detect(response.content[:10000])
                    if detected['confidence'] > 0.7:
                        response.encoding = detected['encoding']
                    else:
                        response.encoding = response.apparent_encoding or 'utf-8'
                except:
                    response.encoding = 'utf-8'
            else:
                response.encoding = self.default_encoding
    
    def download_file(self, url: str, save_path: str, attachment_info: Dict[str, Any] = None) -> bool:
        """파일 다운로드 - 메모리 효율적 스트리밍 다운로드"""
        for attempt in range(self.max_retries + 1):
            try:
                if self._interrupted:
                    logger.info("사용자에 의해 중단됨")
                    return False
                
                logger.info(f"파일 다운로드 시작: {url} (시도 {attempt + 1}/{self.max_retries + 1})")
                
                # 다운로드 헤더 설정
                download_headers = self.headers.copy()
                if self.base_url:
                    download_headers['Referer'] = self.base_url
                
                with self._lock:
                    self.stats['requests_made'] += 1
                
                response = self.session.get(
                    url, 
                    headers=download_headers, 
                    stream=True, 
                    timeout=self.timeout * 2,  # 파일 다운로드는 더 긴 타임아웃
                    verify=self.verify_ssl
                )
                response.raise_for_status()
                
                # 실제 파일명 추출
                actual_filename = self._extract_filename(response, save_path)
                if actual_filename != save_path:
                    save_path = actual_filename
                
                # 디렉토리 생성 보장
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                
                # 스트리밍 다운로드
                total_size = 0
                chunk_size = 8192
                
                with open(save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if self._interrupted:
                            logger.info("파일 다운로드 중단됨")
                            return False
                        
                        if chunk:
                            f.write(chunk)
                            total_size += len(chunk)
                
                file_size = os.path.getsize(save_path)
                
                with self._lock:
                    self.stats['files_downloaded'] += 1
                    self.stats['total_download_size'] += file_size
                
                logger.info(f"다운로드 완료: {save_path} ({file_size:,} bytes)")
                return True
                
            except requests.exceptions.RequestException as e:
                attempt_msg = f"시도 {attempt + 1}/{self.max_retries + 1}"
                
                if attempt < self.max_retries:
                    logger.warning(f"파일 다운로드 실패 {url}: {e} - {attempt_msg}, {self.retry_delay}초 후 재시도")
                    time.sleep(self.retry_delay)
                    continue
                else:
                    logger.error(f"파일 다운로드 최종 실패 {url}: {e} - {attempt_msg}")
                    with self._lock:
                        self.stats['errors_encountered'] += 1
                    return False
            except Exception as e:
                logger.error(f"파일 다운로드 예상치 못한 오류 {url}: {e}")
                with self._lock:
                    self.stats['errors_encountered'] += 1
                return False
        
        return False
    
    def _extract_filename(self, response: requests.Response, default_path: str) -> str:
        """Content-Disposition에서 실제 파일명 추출 - 향상된 버전"""
        content_disposition = response.headers.get('Content-Disposition', '')
        
        if not content_disposition:
            # Content-Disposition이 없으면 URL에서 파일명 추출 시도
            try:
                from urllib.parse import urlparse, unquote
                parsed_url = urlparse(response.url)
                url_filename = os.path.basename(unquote(parsed_url.path))
                if url_filename and '.' in url_filename:
                    save_dir = os.path.dirname(default_path)
                    clean_filename = self.sanitize_filename(url_filename)
                    return os.path.join(save_dir, clean_filename)
            except:
                pass
            return default_path
        
        # RFC 5987 형식 우선 시도 (filename*=UTF-8''filename.ext)
        rfc5987_match = re.search(r"filename\*=([^']*)'([^']*)'(.+)", content_disposition)
        if rfc5987_match:
            encoding = rfc5987_match.group(1) or 'utf-8'
            filename = rfc5987_match.group(3)
            try:
                filename = unquote(filename, encoding=encoding)
                save_dir = os.path.dirname(default_path)
                clean_filename = self.sanitize_filename(filename)
                logger.debug(f"RFC5987 파일명 추출: {clean_filename}")
                return os.path.join(save_dir, clean_filename)
            except Exception as e:
                logger.debug(f"RFC5987 파일명 처리 실패: {e}")
        
        # 일반적인 filename 파라미터 시도
        filename_match = re.search(r'filename[^;=\n]*=(([\'"]).*?\2|[^;\n]*)', content_disposition)
        if filename_match:
            filename = filename_match.group(1).strip('"\'')
            
            # 다양한 인코딩 시도 (순서 최적화)
            encoding_attempts = ['utf-8', 'euc-kr', 'cp949', 'iso-8859-1']
            
            for encoding in encoding_attempts:
                try:
                    if encoding == 'utf-8':
                        # UTF-8로 잘못 해석된 경우 복구 시도
                        decoded = filename.encode('latin-1').decode('utf-8')
                    else:
                        decoded = filename.encode('latin-1').decode(encoding)
                    
                    # 비어있지 않은 유효한 파일명인지 확인
                    if decoded and not decoded.isspace() and len(decoded.strip()) > 0:
                        save_dir = os.path.dirname(default_path)
                        clean_filename = self.sanitize_filename(decoded.replace('+', ' ').strip())
                        logger.debug(f"{encoding} 인코딩으로 파일명 추출: {clean_filename}")
                        return os.path.join(save_dir, clean_filename)
                except Exception as e:
                    logger.debug(f"{encoding} 인코딩 시도 실패: {e}")
                    continue
        
        logger.debug(f"파일명 추출 실패, 기본 경로 사용: {default_path}")
        return default_path
    
    def sanitize_filename(self, filename: str) -> str:
        """파일명 정리 - 향상된 버전"""
        if not filename or not filename.strip():
            return "unnamed_file"
        
        # URL 디코딩
        try:
            filename = unquote(filename)
        except:
            pass
        
        # 기본 정리
        filename = filename.strip()
        
        # Windows/Linux 파일 시스템 금지 문자 제거
        illegal_chars = r'[<>:"/\\|?*\x00-\x1f]'
        filename = re.sub(illegal_chars, '_', filename)
        
        # 연속된 공백/특수문자를 하나로
        filename = re.sub(r'[\s_]+', '_', filename)
        
        # 시작/끝 특수문자 제거
        filename = filename.strip('._-')
        
        # 빈 파일명 처리
        if not filename:
            return "unnamed_file"
        
        # 파일명 길이 제한 (확장자 보존)
        max_length = 200
        if len(filename) > max_length:
            # 확장자 분리
            name_parts = filename.rsplit('.', 1)
            if len(name_parts) == 2 and len(name_parts[1]) <= 10:  # 확장자가 10자 이하인 경우만
                name, ext = name_parts
                available_length = max_length - len(ext) - 1  # .을 위한 1자
                filename = name[:available_length] + '.' + ext
            else:
                filename = filename[:max_length]
        
        # 예약된 파일명 처리 (Windows)
        reserved_names = {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}
        name_without_ext = filename.rsplit('.', 1)[0].upper()
        if name_without_ext in reserved_names:
            filename = '_' + filename
        
        return filename
    
    def normalize_title(self, title: str) -> str:
        """제목 정규화 - 중복 체크용"""
        if not title:
            return ""
        
        # 앞뒤 공백 제거
        normalized = title.strip()
        
        # 연속된 공백을 하나로
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # 특수문자 제거 (일부 허용)
        normalized = re.sub(r'[^\w\s가-힣()-]', '', normalized)
        
        # 소문자 변환 (영문의 경우)
        normalized = normalized.lower()
        
        return normalized
    
    def get_title_hash(self, title: str) -> str:
        """제목의 해시값 생성"""
        normalized = self.normalize_title(title)
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()
    
    def load_processed_titles(self, output_base: str = 'output'):
        """처리된 제목 목록 로드"""
        if not self.enable_duplicate_check:
            return
        
        # 사이트별 파일명 생성 - enhanced 포함
        site_name = self.__class__.__name__.replace('Scraper', '').lower()
        self.processed_titles_file = os.path.join(output_base, f'processed_titles_{site_name}.json')
        
        try:
            if os.path.exists(self.processed_titles_file):
                with open(self.processed_titles_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 제목 해시만 로드
                    self.processed_titles = set(data.get('title_hashes', []))
                    logger.info(f"기존 처리된 공고 {len(self.processed_titles)}개 로드")
            else:
                self.processed_titles = set()
                logger.info("새로운 처리된 제목 파일 생성")
        except Exception as e:
            logger.error(f"처리된 제목 로드 실패: {e}")
            self.processed_titles = set()
    
    def save_processed_titles(self):
        """현재 세션에서 처리된 제목들을 이전 실행 기록에 합쳐서 저장"""
        if not self.enable_duplicate_check or not self.processed_titles_file:
            return
        
        try:
            os.makedirs(os.path.dirname(self.processed_titles_file), exist_ok=True)
            
            # 현재 세션에서 처리된 제목들을 이전 실행 기록에 합침
            all_processed_titles = self.processed_titles | self.current_session_titles
            
            data = {
                'title_hashes': list(all_processed_titles),
                'last_updated': datetime.now().isoformat(),
                'total_count': len(all_processed_titles)
            }
            
            with open(self.processed_titles_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"처리된 제목 {len(all_processed_titles)}개 저장 완료 (이전: {len(self.processed_titles)}, 현재 세션: {len(self.current_session_titles)})")
        except Exception as e:
            logger.error(f"처리된 제목 저장 실패: {e}")
    
    def is_title_processed(self, title: str) -> bool:
        """제목이 이미 처리되었는지 확인"""
        if not self.enable_duplicate_check:
            return False
        
        title_hash = self.get_title_hash(title)
        return title_hash in self.processed_titles
    
    def add_processed_title(self, title: str):
        """현재 세션에서 처리된 제목 추가 (이전 실행 기록과는 별도 관리)"""
        if not self.enable_duplicate_check:
            return
        
        title_hash = self.get_title_hash(title)
        self.current_session_titles.add(title_hash)
    
    def filter_new_announcements(self, announcements: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], bool]:
        """새로운 공고만 필터링 - 이전 실행 기록과만 중복 체크, 현재 세션 내에서는 중복 허용"""
        if not self.enable_duplicate_check:
            return announcements, False
        
        new_announcements = []
        previous_session_duplicate_count = 0  # 이전 실행 중복만 카운트
        
        for ann in announcements:
            title = ann.get('title', '')
            title_hash = self.get_title_hash(title)
            
            # 이전 실행에서 처리된 공고인지만 확인 (현재 세션은 제외)
            if title_hash in self.processed_titles:
                previous_session_duplicate_count += 1
                logger.debug(f"이전 실행에서 처리된 공고 스킵: {title[:50]}...")
                
                # 연속된 이전 실행 중복 임계값 도달시 조기 종료 신호
                if previous_session_duplicate_count >= self.duplicate_threshold:
                    logger.info(f"이전 실행 중복 공고 {previous_session_duplicate_count}개 연속 발견 - 조기 종료 신호")
                    break
            else:
                # 이전 실행에 없는 새로운 공고는 무조건 포함 (현재 세션 내 중복 완전 무시)
                new_announcements.append(ann)
                previous_session_duplicate_count = 0  # 새로운 공고 발견시 중복 카운트 리셋
                logger.debug(f"새로운 공고 추가: {title[:50]}...")
        
        should_stop = previous_session_duplicate_count >= self.duplicate_threshold
        logger.info(f"전체 {len(announcements)}개 중 새로운 공고 {len(new_announcements)}개, 이전 실행 중복 {previous_session_duplicate_count}개 발견")
        
        return new_announcements, should_stop
    
    def process_announcement(self, announcement: Dict[str, Any], index: int, output_base: str = 'output'):
        """개별 공고 처리 - 향상된 버전"""
        logger.info(f"공고 처리 중 {index}: {announcement['title']}")
        
        # 폴더 생성 - 파일시스템 제한을 고려한 제목 길이 조정
        folder_title = self.sanitize_filename(announcement['title'])[:100]  # 100자로 단축
        folder_name = f"{index:03d}_{folder_title}"
        
        # 최종 폴더명이 200자 이하가 되도록 추가 조정
        if len(folder_name) > 200:
            # 인덱스 부분(4자) + 언더스코어(1자) = 5자를 제외하고 195자로 제한
            folder_title = folder_title[:195]
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
            # URL을 함께 전달 (URL이 필요한 특수 사이트들을 위해)
            if hasattr(self, 'parse_detail_page') and 'url' in self.parse_detail_page.__code__.co_varnames:
                detail = self.parse_detail_page(response.text, announcement['url'])
            else:
                detail = self.parse_detail_page(response.text)
            logger.info(f"상세 페이지 파싱 완료 - 내용길이: {len(detail['content'])}, 첨부파일: {len(detail['attachments'])}")
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
        self._download_attachments(detail['attachments'], folder_path)
        
        # 처리된 제목으로 추가
        self.add_processed_title(announcement['title'])
        
        # 중간 저장 - 매 공고 처리 후 저장 (타임아웃 대비)
        if len(self.current_session_titles) % 5 == 0:  # 5개마다 저장
            self.save_processed_titles()
        
        # 요청 간 대기
        if self.delay_between_requests > 0:
            time.sleep(self.delay_between_requests)
    
    def _create_meta_info(self, announcement: Dict[str, Any]) -> str:
        """메타 정보 생성"""
        meta_lines = [f"# {announcement['title']}", ""]
        
        # 동적으로 메타 정보 추가
        meta_fields = {
            'writer': '작성자',
            'date': '작성일',
            'period': '접수기간',
            'status': '상태',
            'organization': '기관',
            'views': '조회수'
        }
        
        for field, label in meta_fields.items():
            if field in announcement and announcement[field]:
                meta_lines.append(f"**{label}**: {announcement[field]}")
        
        meta_lines.extend([
            f"**원본 URL**: {announcement['url']}",
            "",
            "---",
            ""
        ])
        
        return "\n".join(meta_lines)
    
    def _download_attachments(self, attachments: List[Dict[str, Any]], folder_path: str):
        """첨부파일 다운로드"""
        if not attachments:
            logger.info("첨부파일이 없습니다")
            return
        
        logger.info(f"{len(attachments)}개 첨부파일 다운로드 시작")
        attachments_folder = os.path.join(folder_path, 'attachments')
        os.makedirs(attachments_folder, exist_ok=True)
        
        for i, attachment in enumerate(attachments):
            try:
                # 파일명 추출 - 다양한 키 지원 (name, filename)
                file_name = attachment.get('filename') or attachment.get('name') or f"attachment_{i+1}"
                logger.info(f"  첨부파일 {i+1}: {file_name}")
                
                # 파일명 처리
                file_name = self.sanitize_filename(file_name)
                if not file_name or file_name.isspace():
                    file_name = f"attachment_{i+1}"
                
                file_path = os.path.join(attachments_folder, file_name)
                
                # 파일 다운로드
                success = self.download_file(attachment['url'], file_path, attachment)
                if not success:
                    logger.warning(f"첨부파일 다운로드 실패: {file_name}")
                
            except Exception as e:
                logger.error(f"첨부파일 처리 중 오류: {e}")
    
    def scrape_pages(self, max_pages: int = 4, output_base: str = 'output'):
        """여러 페이지 스크래핑 - 성능 모니터링 포함"""
        # 성능 모니터링 시작
        self.stats['start_time'] = datetime.now()
        logger.info(f"스크래핑 시작: 최대 {max_pages}페이지 - {self.stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 인터럽트 핸들러 설정
        self._setup_interrupt_handler()
        
        # 처리된 제목 목록 로드
        self.load_processed_titles(output_base)
        
        announcement_count = 0
        processed_count = 0
        early_stop = False
        stop_reason = ""
        
        try:
            for page_num in range(1, max_pages + 1):
                if self._interrupted:
                    logger.info("사용자에 의해 스크래핑이 중단되었습니다")
                    early_stop = True
                    stop_reason = "사용자 중단"
                    break
                
                logger.info(f"페이지 {page_num} 처리 중")
                
                try:
                    # 목록 가져오기 및 파싱
                    announcements = self._get_page_announcements(page_num)
                
                    if not announcements:
                        logger.warning(f"페이지 {page_num}에 공고가 없습니다")
                        if page_num == 1:
                            logger.error("첫 페이지에 공고가 없습니다. 사이트 구조를 확인해주세요.")
                            stop_reason = "첫 페이지 공고 없음"
                        else:
                            logger.info("마지막 페이지에 도달했습니다.")
                            stop_reason = "마지막 페이지 도달"
                        break
                    
                    logger.info(f"페이지 {page_num}에서 {len(announcements)}개 공고 발견")
                    
                    # 새로운 공고만 필터링 및 중복 임계값 체크
                    new_announcements, should_stop = self.filter_new_announcements(announcements)
                    
                    # 각 공고 처리
                    for ann in new_announcements:
                        announcement_count += 1
                        processed_count += 1
                        self.process_announcement(ann, announcement_count, output_base)

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
                    
                    # 페이지 간 대기
                    if page_num < max_pages and self.delay_between_pages > 0:
                        time.sleep(self.delay_between_pages)
                    
                except Exception as e:
                    logger.error(f"페이지 {page_num} 처리 중 오류: {e}")
                    stop_reason = f"오류: {e}"
                    break
        
        except Exception as e:
            logger.error(f"스크래핑 중 예상치 못한 오류: {e}")
            early_stop = True
            stop_reason = f"오류: {e}"
        finally:
            # 성능 모니터링 종료
            self.stats['end_time'] = datetime.now()
            
            # 처리된 제목 목록 저장
            self.save_processed_titles()
            
            # 최종 통계 출력
            self._print_final_stats(processed_count, early_stop, stop_reason)
        
        return True
    
    def _get_page_announcements(self, page_num: int) -> List[Dict[str, Any]]:
        """페이지별 공고 목록 가져오기 - 기본 구현"""
        page_url = self.get_list_url(page_num)
        response = self.get_page(page_url)
        
        if not response:
            logger.warning(f"페이지 {page_num} 응답을 가져올 수 없습니다")
            return []
        
        # 페이지가 에러 상태거나 잘못된 경우 감지
        if response.status_code >= 400:
            logger.warning(f"페이지 {page_num} HTTP 에러: {response.status_code}")
            return []
        
        # 현재 페이지 번호를 인스턴스 변수로 저장
        self.current_page_num = page_num
        announcements = self.parse_list_page(response.text)
        
        # 추가 마지막 페이지 감지 로직
        if not announcements and page_num > 1:
            logger.info(f"페이지 {page_num}에 공고가 없어 마지막 페이지로 판단됩니다")
        
        return announcements
    
    def _setup_interrupt_handler(self):
        """Ctrl+C 인터럽트 핸들러 설정"""
        def signal_handler(signum, frame):
            logger.info("중단 신호를 받았습니다. 안전하게 종료됩니다...")
            self._interrupted = True
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def _print_final_stats(self, processed_count: int, early_stop: bool, stop_reason: str):
        """최종 통계 출력"""
        if not self.stats['start_time'] or not self.stats['end_time']:
            return
        
        duration = self.stats['end_time'] - self.stats['start_time']
        duration_seconds = duration.total_seconds()
        
        logger.info("="*60)
        logger.info("📊 스크래핑 완료 통계")
        logger.info("="*60)
        
        if early_stop:
            logger.info(f"⏱️  실행 기간: {duration_seconds:.1f}초 (조기종료: {stop_reason})")
        else:
            logger.info(f"⏱️  실행 시간: {duration_seconds:.1f}초")
        
        logger.info(f"📄 처리된 공고: {processed_count}개")
        logger.info(f"🌐 HTTP 요청: {self.stats['requests_made']}개")
        logger.info(f"📁 다운로드 파일: {self.stats['files_downloaded']}개")
        logger.info(f"💾 전체 다운로드 크기: {self._format_size(self.stats['total_download_size'])}")
        
        if self.stats['errors_encountered'] > 0:
            logger.warning(f"⚠️  발생한 오류: {self.stats['errors_encountered']}개")
        
        # 성능 메트릭
        if duration_seconds > 0:
            requests_per_second = self.stats['requests_made'] / duration_seconds
            logger.info(f"🚀 초당 요청 수: {requests_per_second:.2f}")
        
        logger.info("="*60)
    
    def _format_size(self, size_bytes: int) -> str:
        """바이트를 읽기 쉬운 형태로 변환"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"
    
    def get_stats(self) -> Dict[str, Any]:
        """현재 통계 반환"""
        stats = self.stats.copy()
        if stats['start_time'] and stats['end_time']:
            duration = stats['end_time'] - stats['start_time']
            stats['duration_seconds'] = duration.total_seconds()
        return stats
    
    @contextmanager
    def performance_monitor(self, operation_name: str):
        """성능 모니터링 컨텍스트 매니저"""
        start_time = time.time()
        logger.debug(f"🔄 {operation_name} 시작")
        
        try:
            yield
        finally:
            end_time = time.time()
            duration = end_time - start_time
            logger.debug(f"✅ {operation_name} 완료 - {duration:.2f}초")
    
    def is_healthy(self) -> bool:
        """스크래퍼 상태 체크"""
        try:
            # 기본 URL 연결 테스트
            if self.base_url:
                response = self.session.head(self.base_url, timeout=10, verify=self.verify_ssl)
                return response.status_code < 400
            return True
        except:
            return False
    
    def reset_stats(self):
        """통계 리셋"""
        self.stats = {
            'requests_made': 0,
            'files_downloaded': 0,
            'errors_encountered': 0,
            'total_download_size': 0,
            'start_time': None,
            'end_time': None
        }
    
    def process_notice_detection(self, cell, row_index: int = 0, use_playwright: bool = False) -> str:
        """공지 이미지 감지 및 번호 처리 - 모든 CCI에서 재사용 가능"""
        if use_playwright:
            # Playwright 버전
            number = cell.inner_text().strip() if hasattr(cell, 'inner_text') else ""
            is_notice = False
            
            if hasattr(cell, 'locator'):
                notice_imgs = cell.locator('img').all()
                for img in notice_imgs:
                    src = img.get_attribute('src') or ''
                    alt = img.get_attribute('alt') or ''
                    if '공지' in src or '공지' in alt or 'notice' in src.lower():
                        is_notice = True
                        break
        else:
            # BeautifulSoup 버전
            number = cell.get_text(strip=True) if hasattr(cell, 'get_text') else str(cell).strip()
            is_notice = False
            
            if hasattr(cell, 'find_all'):
                notice_imgs = cell.find_all('img')
                for img in notice_imgs:
                    src = img.get('src', '')
                    alt = img.get('alt', '')
                    if '공지' in src or '공지' in alt or 'notice' in src.lower():
                        is_notice = True
                        break
        
        # 번호 결정
        if is_notice:
            return "공지"
        elif not number or number.isspace():
            return f"row_{row_index}"
        else:
            return number.strip()


class StandardTableScraper(EnhancedBaseScraper):
    """표준 HTML 테이블 기반 게시판용 스크래퍼"""
    
    def get_list_url(self, page_num: int) -> str:
        """표준 페이지네이션 URL 생성"""
        if not self.config:
            # 하위 클래스에서 직접 구현
            return super().get_list_url(page_num)
        
        pagination = self.config.pagination
        if pagination.get('type') == 'query_param':
            param = pagination.get('param', 'page')
            if page_num == 1:
                return self.list_url
            else:
                separator = '&' if '?' in self.list_url else '?'
                return f"{self.list_url}{separator}{param}={page_num}"
        
        return self.list_url
    
    def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """표준 테이블 파싱 - 설정 기반"""
        if not self.config or not self.config.selectors:
            # 하위 클래스에서 직접 구현
            return super().parse_list_page(html_content)
        
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        selectors = self.config.selectors
        
        # 테이블 찾기
        table = soup.select_one(selectors.get('table', 'table'))
        if not table:
            return announcements
        
        # 행들 찾기
        rows = table.select(selectors.get('rows', 'tr'))
        
        for row in rows:
            try:
                # 제목 링크 찾기
                link_elem = row.select_one(selectors.get('title_link', 'a[href]'))
                if not link_elem:
                    continue
                
                title = link_elem.get_text(strip=True)
                if not title:
                    continue
                
                # URL 구성
                href = link_elem.get('href', '')
                detail_url = urljoin(self.base_url, href)
                
                announcement = {
                    'title': title,
                    'url': detail_url
                }
                
                # 추가 필드들 (선택적)
                field_selectors = {
                    'status': 'status',
                    'writer': 'writer', 
                    'date': 'date',
                    'period': 'period'
                }
                
                for field, selector_key in field_selectors.items():
                    if selector_key in selectors:
                        elem = row.select_one(selectors[selector_key])
                        if elem:
                            announcement[field] = elem.get_text(strip=True)
                
                announcements.append(announcement)
                
            except Exception as e:
                logger.error(f"행 파싱 중 오류: {e}")
                continue
        
        return announcements


class AjaxAPIScraper(EnhancedBaseScraper):
    """AJAX/JSON API 기반 스크래퍼"""
    
    def get_list_url(self, page_num: int) -> str:
        """API URL 반환"""
        return getattr(self.config, 'api_url', self.list_url)
    
    def _get_page_announcements(self, page_num: int) -> List[Dict[str, Any]]:
        """API를 통한 공고 목록 가져오기"""
        if not self.config or not self.config.api_config:
            return super()._get_page_announcements(page_num)
        
        api_config = self.config.api_config
        api_url = getattr(self.config, 'api_url', self.list_url)
        
        # 요청 데이터 구성
        data = api_config.get('data_fields', {}).copy()
        
        # 페이지 번호 추가
        pagination = self.config.pagination
        if pagination.get('type') == 'post_data':
            param = pagination.get('param', 'page')
            data[param] = str(page_num)
        
        # API 호출
        if api_config.get('method', 'POST').upper() == 'POST':
            response = self.post_page(api_url, data=data)
        else:
            response = self.get_page(api_url, params=data)
        
        if not response:
            return []
        
        try:
            json_data = response.json()
            return self.parse_api_response(json_data, page_num)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}")
            return []
    
    def parse_api_response(self, json_data: Dict[str, Any], page_num: int) -> List[Dict[str, Any]]:
        """API 응답 파싱 - 하위 클래스에서 구현"""
        return self.parse_list_page(json_data)


class JavaScriptScraper(EnhancedBaseScraper):
    """JavaScript 실행이 필요한 사이트용 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        # Playwright나 Selenium 등을 위한 설정
        self.browser_options = {
            'headless': True,
            'timeout': 30000
        }
    
    def extract_js_data(self, html_content: str, pattern: str) -> List[str]:
        """JavaScript에서 데이터 추출"""
        matches = re.findall(pattern, html_content, re.DOTALL)
        return matches


class SessionBasedScraper(EnhancedBaseScraper):
    """세션 관리가 필요한 사이트용 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        self.session_initialized = False
        self.session_data = {}
    
    def initialize_session(self):
        """세션 초기화 - 하위 클래스에서 구현"""
        if self.session_initialized:
            return True
        
        # 기본적으로 첫 페이지 방문으로 세션 초기화
        try:
            response = self.get_page(self.base_url or self.list_url)
            if response:
                self.session_initialized = True
                return True
        except Exception as e:
            logger.error(f"세션 초기화 실패: {e}")
        
        return False
    
    def _get_page_announcements(self, page_num: int) -> List[Dict[str, Any]]:
        """세션 확인 후 공고 목록 가져오기"""
        if not self.initialize_session():
            logger.error("세션 초기화 실패")
            return []
        
        return super()._get_page_announcements(page_num)


class PlaywrightScraper(EnhancedBaseScraper):
    """Playwright 브라우저 자동화 기반 스크래퍼"""
    
    def __init__(self):
        super().__init__()
        self.browser = None
        self.page = None
        self.browser_options = {
            'headless': True,
            'timeout': 30000
        }
    
    async def initialize_browser(self):
        """브라우저 초기화 - 하위 클래스에서 Playwright 구현"""
        # 실제 Playwright 구현은 하위 클래스에서
        pass
    
    async def cleanup_browser(self):
        """브라우저 정리"""
        if self.page:
            await self.page.close()
        if self.browser:
            await self.browser.close()