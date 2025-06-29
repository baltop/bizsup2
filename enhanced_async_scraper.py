# -*- coding: utf-8 -*-
"""
Enhanced Async Base Scraper - 비동기 처리 지원 베이스 클래스
"""

import asyncio
import aiohttp
import aiofiles
import os
import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from contextlib import asynccontextmanager
import re
import json
from urllib.parse import urljoin, urlparse, unquote
from bs4 import BeautifulSoup
import chardet
import hashlib
import signal
import threading

logger = logging.getLogger(__name__)

class EnhancedAsyncBaseScraper(ABC):
    """향상된 비동기 베이스 스크래퍼"""
    
    def __init__(self):
        # 기본 설정
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # 비동기 세션
        self.session: Optional[aiohttp.ClientSession] = None
        
        # 기본값들
        self.verify_ssl = True
        self.default_encoding = 'auto'
        self.timeout = 30
        self.delay_between_requests = 1
        self.delay_between_pages = 2
        
        # 재시도 설정
        self.max_retries = 3
        self.retry_delay = 2
        
        # 비동기 설정
        self.max_concurrent_requests = 5
        self.max_concurrent_downloads = 3
        
        # 성능 모니터링
        self.stats = {
            'requests_made': 0,
            'files_downloaded': 0,
            'errors_encountered': 0,
            'total_download_size': 0,
            'start_time': None,
            'end_time': None,
            'concurrent_requests': 0,
            'peak_concurrent_requests': 0
        }
        
        # 스레드 안전성
        self._lock = asyncio.Lock()
        self._interrupted = False
        
        # 베이스 URL들 (하위 클래스에서 설정)
        self.base_url = None
        self.list_url = None
        
        # 중복 체크 관련
        self.processed_titles_file = None
        self.current_page_num = 1
        self.processed_titles = set()
        self.current_session_titles = set()
        self.enable_duplicate_check = True
        self.duplicate_threshold = 3
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        await self.initialize_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        await self.cleanup_session()
    
    async def initialize_session(self):
        """비동기 세션 초기화"""
        if self.session is None:
            connector = aiohttp.TCPConnector(
                verify_ssl=self.verify_ssl,
                limit=self.max_concurrent_requests,
                limit_per_host=self.max_concurrent_requests
            )
            
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            
            self.session = aiohttp.ClientSession(
                headers=self.headers,
                connector=connector,
                timeout=timeout
            )
    
    async def cleanup_session(self):
        """비동기 세션 정리"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
    
    @abstractmethod
    async def get_list_url(self, page_num: int) -> str:
        """페이지 번호에 따른 목록 URL 반환"""
        pass
    
    @abstractmethod
    async def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """목록 페이지 파싱"""
        pass
    
    @abstractmethod
    async def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱"""
        pass
    
    async def get_page(self, url: str, **kwargs) -> Optional[aiohttp.ClientResponse]:
        """비동기 페이지 가져오기"""
        if not self.session:
            await self.initialize_session()
        
        async with self._lock:
            self.stats['concurrent_requests'] += 1
            if self.stats['concurrent_requests'] > self.stats['peak_concurrent_requests']:
                self.stats['peak_concurrent_requests'] = self.stats['concurrent_requests']
        
        try:
            for attempt in range(self.max_retries + 1):
                try:
                    if self._interrupted:
                        logger.info("사용자에 의해 중단됨")
                        return None
                    
                    async with self._lock:
                        self.stats['requests_made'] += 1
                    
                    async with self.session.get(url, **kwargs) as response:
                        response.raise_for_status()
                        
                        # 인코딩 처리
                        await self._fix_encoding_async(response)
                        
                        return response
                        
                except aiohttp.ClientError as e:
                    attempt_msg = f"시도 {attempt + 1}/{self.max_retries + 1}"
                    
                    if attempt < self.max_retries:
                        logger.warning(f"페이지 요청 실패 {url}: {e} - {attempt_msg}, {self.retry_delay}초 후 재시도")
                        await asyncio.sleep(self.retry_delay)
                        continue
                    else:
                        logger.error(f"페이지 요청 최종 실패 {url}: {e} - {attempt_msg}")
                        async with self._lock:
                            self.stats['errors_encountered'] += 1
                        return None
                        
                except Exception as e:
                    logger.error(f"예상치 못한 오류 {url}: {e}")
                    async with self._lock:
                        self.stats['errors_encountered'] += 1
                    return None
            
            return None
            
        finally:
            async with self._lock:
                self.stats['concurrent_requests'] -= 1
    
    async def post_page(self, url: str, data: Dict[str, Any] = None, **kwargs) -> Optional[aiohttp.ClientResponse]:
        """비동기 POST 요청"""
        if not self.session:
            await self.initialize_session()
        
        async with self._lock:
            self.stats['concurrent_requests'] += 1
            if self.stats['concurrent_requests'] > self.stats['peak_concurrent_requests']:
                self.stats['peak_concurrent_requests'] = self.stats['concurrent_requests']
        
        try:
            for attempt in range(self.max_retries + 1):
                try:
                    if self._interrupted:
                        logger.info("사용자에 의해 중단됨")
                        return None
                    
                    async with self._lock:
                        self.stats['requests_made'] += 1
                    
                    async with self.session.post(url, data=data, **kwargs) as response:
                        response.raise_for_status()
                        await self._fix_encoding_async(response)
                        return response
                        
                except aiohttp.ClientError as e:
                    attempt_msg = f"시도 {attempt + 1}/{self.max_retries + 1}"
                    
                    if attempt < self.max_retries:
                        logger.warning(f"POST 요청 실패 {url}: {e} - {attempt_msg}, {self.retry_delay}초 후 재시도")
                        await asyncio.sleep(self.retry_delay)
                        continue
                    else:
                        logger.error(f"POST 요청 최종 실패 {url}: {e} - {attempt_msg}")
                        async with self._lock:
                            self.stats['errors_encountered'] += 1
                        return None
                        
                except Exception as e:
                    logger.error(f"POST 예상치 못한 오류 {url}: {e}")
                    async with self._lock:
                        self.stats['errors_encountered'] += 1
                    return None
            
            return None
            
        finally:
            async with self._lock:
                self.stats['concurrent_requests'] -= 1
    
    async def _fix_encoding_async(self, response: aiohttp.ClientResponse):
        """비동기 응답 인코딩 자동 수정"""
        # aiohttp는 자동으로 인코딩을 처리하므로 기본적으로 별도 처리 불필요
        # 필요시 하위 클래스에서 오버라이드
        pass
    
    async def download_file(self, url: str, save_path: str, attachment_info: Dict[str, Any] = None) -> bool:
        """비동기 파일 다운로드"""
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
                
                async with self._lock:
                    self.stats['requests_made'] += 1
                
                async with self.session.get(url, headers=download_headers) as response:
                    response.raise_for_status()
                    
                    # 실제 파일명 추출
                    actual_filename = await self._extract_filename_async(response, save_path)
                    if actual_filename != save_path:
                        save_path = actual_filename
                    
                    # 디렉토리 생성 보장
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    
                    # 비동기 스트리밍 다운로드
                    total_size = 0
                    
                    async with aiofiles.open(save_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            if self._interrupted:
                                logger.info("파일 다운로드 중단됨")
                                return False
                            
                            await f.write(chunk)
                            total_size += len(chunk)
                    
                    file_size = os.path.getsize(save_path)
                    
                    async with self._lock:
                        self.stats['files_downloaded'] += 1
                        self.stats['total_download_size'] += file_size
                    
                    logger.info(f"다운로드 완료: {save_path} ({file_size:,} bytes)")
                    return True
                    
            except aiohttp.ClientError as e:
                attempt_msg = f"시도 {attempt + 1}/{self.max_retries + 1}"
                
                if attempt < self.max_retries:
                    logger.warning(f"파일 다운로드 실패 {url}: {e} - {attempt_msg}, {self.retry_delay}초 후 재시도")
                    await asyncio.sleep(self.retry_delay)
                    continue
                else:
                    logger.error(f"파일 다운로드 최종 실패 {url}: {e} - {attempt_msg}")
                    async with self._lock:
                        self.stats['errors_encountered'] += 1
                    return False
                    
            except Exception as e:
                logger.error(f"파일 다운로드 예상치 못한 오류 {url}: {e}")
                async with self._lock:
                    self.stats['errors_encountered'] += 1
                return False
        
        return False
    
    async def _extract_filename_async(self, response: aiohttp.ClientResponse, default_path: str) -> str:
        """비동기 파일명 추출"""
        content_disposition = response.headers.get('Content-Disposition', '')
        
        if not content_disposition:
            # Content-Disposition이 없으면 URL에서 파일명 추출 시도
            try:
                parsed_url = urlparse(str(response.url))
                url_filename = os.path.basename(unquote(parsed_url.path))
                if url_filename and '.' in url_filename:
                    save_dir = os.path.dirname(default_path)
                    clean_filename = self.sanitize_filename(url_filename)
                    return os.path.join(save_dir, clean_filename)
            except:
                pass
            return default_path
        
        # RFC 5987 형식 우선 시도
        rfc5987_match = re.search(r"filename\\*=([^']*)'([^']*)'(.+)", content_disposition)
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
        filename_match = re.search(r'filename[^;=\\n]*=([\\\"]*)(.*?)\\1', content_disposition)
        if filename_match:
            filename = filename_match.group(2)
            
            # 다양한 인코딩 시도
            encoding_attempts = ['utf-8', 'euc-kr', 'cp949', 'iso-8859-1']
            
            for encoding in encoding_attempts:
                try:
                    if encoding == 'utf-8':
                        decoded = filename.encode('latin-1').decode('utf-8')
                    else:
                        decoded = filename.encode('latin-1').decode(encoding)
                    
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
        """파일명 정리"""
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
        illegal_chars = r'[<>:"/\\\\|?*\\x00-\\x1f]'
        filename = re.sub(illegal_chars, '_', filename)
        
        # 연속된 공백/특수문자를 하나로
        filename = re.sub(r'[\\s_]+', '_', filename)
        
        # 시작/끝 특수문자 제거
        filename = filename.strip('._-')
        
        # 빈 파일명 처리
        if not filename:
            return "unnamed_file"
        
        # 파일명 길이 제한
        max_length = 200
        if len(filename) > max_length:
            name_parts = filename.rsplit('.', 1)
            if len(name_parts) == 2 and len(name_parts[1]) <= 10:
                name, ext = name_parts
                available_length = max_length - len(ext) - 1
                filename = name[:available_length] + '.' + ext
            else:
                filename = filename[:max_length]
        
        # 예약된 파일명 처리 (Windows)
        reserved_names = {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}
        name_without_ext = filename.rsplit('.', 1)[0].upper()
        if name_without_ext in reserved_names:
            filename = '_' + filename
        
        return filename
    
    async def scrape_pages_async(self, max_pages: int = 4, output_base: str = 'output'):
        """비동기 여러 페이지 스크래핑"""
        # 성능 모니터링 시작
        self.stats['start_time'] = datetime.now()
        logger.info(f"비동기 스크래핑 시작: 최대 {max_pages}페이지 - {self.stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 처리된 제목 목록 로드
        self.load_processed_titles(output_base)
        
        processed_count = 0
        early_stop = False
        stop_reason = ""
        
        try:
            # 세마포어로 동시 처리 제한
            semaphore = asyncio.Semaphore(self.max_concurrent_requests)
            
            # 페이지별 태스크 생성
            page_tasks = []
            for page_num in range(1, max_pages + 1):
                task = self._process_page_async(semaphore, page_num, output_base)
                page_tasks.append(task)
            
            # 모든 페이지 비동기 처리
            page_results = await asyncio.gather(*page_tasks, return_exceptions=True)
            
            # 결과 집계
            for i, result in enumerate(page_results):
                if isinstance(result, Exception):
                    logger.error(f"페이지 {i+1} 처리 중 오류: {result}")
                    continue
                
                if result:
                    processed_count += len(result)
            
        except Exception as e:
            logger.error(f"비동기 스크래핑 중 예상치 못한 오류: {e}")
            early_stop = True
            stop_reason = f"오류: {e}"
        finally:
            # 성능 모니터링 종료
            self.stats['end_time'] = datetime.now()
            
            # 처리된 제목 목록 저장
            self.save_processed_titles()
            
            # 최종 통계 출력
            self._print_final_stats_async(processed_count, early_stop, stop_reason)
        
        return True
    
    async def _process_page_async(self, semaphore: asyncio.Semaphore, page_num: int, output_base: str) -> List[Dict[str, Any]]:
        """단일 페이지 비동기 처리"""
        async with semaphore:
            try:
                logger.info(f"페이지 {page_num} 비동기 처리 중")
                
                # 페이지 공고 목록 가져오기
                announcements = await self._get_page_announcements_async(page_num)
                
                if not announcements:
                    logger.warning(f"페이지 {page_num}에 공고가 없습니다")
                    return []
                
                logger.info(f"페이지 {page_num}에서 {len(announcements)}개 공고 발견")
                
                # 새로운 공고만 필터링
                new_announcements, should_stop = await self.filter_new_announcements_async(announcements)
                
                if not new_announcements:
                    logger.info(f"페이지 {page_num}에 새로운 공고가 없습니다")
                    return []
                
                # 공고별 처리 태스크 생성
                announcement_tasks = []
                for i, ann in enumerate(new_announcements):
                    task = self.process_announcement_async(ann, i + 1, output_base)
                    announcement_tasks.append(task)
                
                # 공고들 병렬 처리 (제한된 동시성)
                announcement_semaphore = asyncio.Semaphore(self.max_concurrent_downloads)
                
                async def process_with_semaphore(ann_task):
                    async with announcement_semaphore:
                        return await ann_task
                
                # 세마포어 적용된 태스크들 실행
                bounded_tasks = [process_with_semaphore(task) for task in announcement_tasks]
                await asyncio.gather(*bounded_tasks, return_exceptions=True)
                
                # 페이지 간 대기
                if self.delay_between_pages > 0:
                    await asyncio.sleep(self.delay_between_pages)
                
                return new_announcements
                
            except Exception as e:
                logger.error(f"페이지 {page_num} 비동기 처리 중 오류: {e}")
                return []
    
    async def _get_page_announcements_async(self, page_num: int) -> List[Dict[str, Any]]:
        """페이지별 공고 목록 비동기 가져오기"""
        page_url = await self.get_list_url(page_num)
        response = await self.get_page(page_url)
        
        if not response:
            logger.warning(f"페이지 {page_num} 응답을 가져올 수 없습니다")
            return []
        
        # HTTP 에러 체크
        if response.status >= 400:
            logger.warning(f"페이지 {page_num} HTTP 에러: {response.status}")
            return []
        
        # HTML 내용 읽기
        html_content = await response.text()
        
        # 현재 페이지 번호 저장
        self.current_page_num = page_num
        announcements = await self.parse_list_page(html_content)
        
        return announcements
    
    async def filter_new_announcements_async(self, announcements: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], bool]:
        """새로운 공고만 비동기 필터링"""
        if not self.enable_duplicate_check:
            return announcements, False
        
        new_announcements = []
        previous_session_duplicate_count = 0
        
        for ann in announcements:
            title = ann.get('title', '')
            title_hash = self.get_title_hash(title)
            
            # 이전 실행에서 처리된 공고인지만 확인
            if title_hash in self.processed_titles:
                previous_session_duplicate_count += 1
                logger.debug(f"이전 실행에서 처리된 공고 스킵: {title[:50]}...")
                
                # 연속된 이전 실행 중복 임계값 도달시 조기 종료 신호
                if previous_session_duplicate_count >= self.duplicate_threshold:
                    logger.info(f"이전 실행 중복 공고 {previous_session_duplicate_count}개 연속 발견 - 조기 종료 신호")
                    break
            else:
                # 이전 실행에 없는 새로운 공고는 무조건 포함
                new_announcements.append(ann)
                previous_session_duplicate_count = 0
                logger.debug(f"새로운 공고 추가: {title[:50]}...")
        
        should_stop = previous_session_duplicate_count >= self.duplicate_threshold
        logger.info(f"전체 {len(announcements)}개 중 새로운 공고 {len(new_announcements)}개, 이전 실행 중복 {previous_session_duplicate_count}개 발견")
        
        return new_announcements, should_stop
    
    async def process_announcement_async(self, announcement: Dict[str, Any], index: int, output_base: str = 'output'):
        """개별 공고 비동기 처리"""
        logger.info(f"공고 비동기 처리 중 {index}: {announcement['title']}")
        
        # 폴더 생성
        folder_title = self.sanitize_filename(announcement['title'])[:100]
        folder_name = f"{index:03d}_{folder_title}"
        
        if len(folder_name) > 200:
            folder_title = folder_title[:195]
            folder_name = f"{index:03d}_{folder_title}"
        
        folder_path = os.path.join(output_base, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        
        # 상세 페이지 가져오기
        response = await self.get_page(announcement['url'])
        if not response:
            logger.error(f"상세 페이지 가져오기 실패: {announcement['title']}")
            return
        
        html_content = await response.text()
        
        # 상세 내용 파싱
        try:
            detail = await self.parse_detail_page(html_content)
            logger.info(f"상세 페이지 파싱 완료 - 내용길이: {len(detail['content'])}, 첨부파일: {len(detail['attachments'])}")
        except Exception as e:
            logger.error(f"상세 페이지 파싱 실패: {e}")
            return
        
        # 메타 정보 생성
        meta_info = self._create_meta_info(announcement)
        
        # 본문 저장
        content_path = os.path.join(folder_path, 'content.md')
        async with aiofiles.open(content_path, 'w', encoding='utf-8') as f:
            await f.write(meta_info + detail['content'])
        
        logger.info(f"내용 저장 완료: {content_path}")
        
        # 첨부파일 비동기 다운로드
        await self._download_attachments_async(detail['attachments'], folder_path)
        
        # 처리된 제목으로 추가
        self.add_processed_title(announcement['title'])
        
        # 요청 간 대기
        if self.delay_between_requests > 0:
            await asyncio.sleep(self.delay_between_requests)
    
    async def _download_attachments_async(self, attachments: List[Dict[str, Any]], folder_path: str):
        """첨부파일 비동기 다운로드"""
        if not attachments:
            logger.info("첨부파일이 없습니다")
            return
        
        logger.info(f"{len(attachments)}개 첨부파일 비동기 다운로드 시작")
        attachments_folder = os.path.join(folder_path, 'attachments')
        os.makedirs(attachments_folder, exist_ok=True)
        
        # 첨부파일 다운로드 태스크 생성
        download_tasks = []
        for i, attachment in enumerate(attachments):
            task = self._download_single_attachment_async(attachment, attachments_folder, i)
            download_tasks.append(task)
        
        # 병렬 다운로드 (제한된 동시성)
        semaphore = asyncio.Semaphore(self.max_concurrent_downloads)
        
        async def download_with_semaphore(download_task):
            async with semaphore:
                return await download_task
        
        # 세마포어 적용된 다운로드 태스크들 실행
        bounded_tasks = [download_with_semaphore(task) for task in download_tasks]
        await asyncio.gather(*bounded_tasks, return_exceptions=True)
    
    async def _download_single_attachment_async(self, attachment: Dict[str, Any], attachments_folder: str, index: int):
        """단일 첨부파일 비동기 다운로드"""
        try:
            # 파일명 추출
            file_name = attachment.get('filename') or attachment.get('name') or f"attachment_{index+1}"
            logger.info(f"  첨부파일 {index+1}: {file_name}")
            
            # 파일명 처리
            file_name = self.sanitize_filename(file_name)
            if not file_name or file_name.isspace():
                file_name = f"attachment_{index+1}"
            
            file_path = os.path.join(attachments_folder, file_name)
            
            # 파일 다운로드
            success = await self.download_file(attachment['url'], file_path, attachment)
            if not success:
                logger.warning(f"첨부파일 다운로드 실패: {file_name}")
            
        except Exception as e:
            logger.error(f"첨부파일 처리 중 오류: {e}")
    
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
            'views': '조회수',
            'number': '번호'
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
        
        return "\\n".join(meta_lines)
    
    def load_processed_titles(self, output_base: str = 'output'):
        """처리된 제목 목록 로드"""
        if not self.enable_duplicate_check:
            return
        
        # 사이트별 파일명 생성
        site_name = self.__class__.__name__.replace('Scraper', '').lower()
        self.processed_titles_file = os.path.join(output_base, f'processed_titles_{site_name}.json')
        
        try:
            if os.path.exists(self.processed_titles_file):
                with open(self.processed_titles_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
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
                
            logger.info(f"처리된 제목 {len(all_processed_titles)}개 저장 완료")
        except Exception as e:
            logger.error(f"처리된 제목 저장 실패: {e}")
    
    def get_title_hash(self, title: str) -> str:
        """제목의 해시값 생성"""
        normalized = self.normalize_title(title)
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()
    
    def normalize_title(self, title: str) -> str:
        """제목 정규화"""
        if not title:
            return ""
        
        normalized = title.strip()
        normalized = re.sub(r'\\s+', ' ', normalized)
        normalized = re.sub(r'[^\\w\\s가-힣()-]', '', normalized)
        normalized = normalized.lower()
        
        return normalized
    
    def add_processed_title(self, title: str):
        """현재 세션에서 처리된 제목 추가"""
        if not self.enable_duplicate_check:
            return
        
        title_hash = self.get_title_hash(title)
        self.current_session_titles.add(title_hash)
    
    def _print_final_stats_async(self, processed_count: int, early_stop: bool, stop_reason: str):
        """비동기 최종 통계 출력"""
        if not self.stats['start_time'] or not self.stats['end_time']:
            return
        
        duration = self.stats['end_time'] - self.stats['start_time']
        duration_seconds = duration.total_seconds()
        
        logger.info("="*60)
        logger.info("📊 비동기 스크래핑 완료 통계")
        logger.info("="*60)
        
        if early_stop:
            logger.info(f"⏱️  실행 기간: {duration_seconds:.1f}초 (조기종료: {stop_reason})")
        else:
            logger.info(f"⏱️  실행 시간: {duration_seconds:.1f}초")
        
        logger.info(f"📄 처리된 공고: {processed_count}개")
        logger.info(f"🌐 HTTP 요청: {self.stats['requests_made']}개")
        logger.info(f"📁 다운로드 파일: {self.stats['files_downloaded']}개")
        logger.info(f"💾 전체 다운로드 크기: {self._format_size(self.stats['total_download_size'])}")
        logger.info(f"🔄 최대 동시 요청: {self.stats['peak_concurrent_requests']}개")
        
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


# 비동기 표준 테이블 스크래퍼
class AsyncStandardTableScraper(EnhancedAsyncBaseScraper):
    """비동기 표준 HTML 테이블 기반 게시판용 스크래퍼"""
    
    async def get_list_url(self, page_num: int) -> str:
        """표준 페이지네이션 URL 생성"""
        # 기본 구현 - 하위 클래스에서 오버라이드
        if page_num == 1:
            return self.list_url
        else:
            separator = '&' if '?' in self.list_url else '?'
            return f"{self.list_url}{separator}page={page_num}"
    
    async def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
        """표준 테이블 파싱 - 하위 클래스에서 구현"""
        # 기본 구현 - 하위 클래스에서 오버라이드 필요
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 테이블 찾기
        table = soup.find('table')
        if not table:
            return announcements
        
        # 행들 찾기
        rows = table.find_all('tr')
        
        for row in rows:
            try:
                cells = row.find_all('td')
                if len(cells) < 2:
                    continue
                
                # 제목 링크 찾기
                link_elem = cells[1].find('a')
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
                
                announcements.append(announcement)
                
            except Exception as e:
                logger.error(f"행 파싱 중 오류: {e}")
                continue
        
        return announcements
    
    async def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱 - 하위 클래스에서 구현"""
        # 기본 구현 - 하위 클래스에서 오버라이드 필요
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 간단한 본문 추출
        content = soup.get_text(strip=True)[:1000] + "..."
        
        return {
            'title': '',
            'content': f"## 공고 내용\\n\\n{content}\\n\\n",
            'attachments': [],
            'date': ''
        }