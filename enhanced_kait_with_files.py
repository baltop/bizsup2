#!/usr/bin/env python3
"""
Enhanced KAIT 스크래퍼 - 첨부파일 다운로드 포함

KAIT 공고 게시판에서 공고와 첨부파일을 모두 수집하는 완전한 스크래퍼입니다.
직접 링크 방식의 간단한 파일 다운로드를 지원합니다.

URL: https://www.kait.or.kr/user/MainBoardList.do?cateSeq=13&bId=101
"""

import os
import re
import time
import logging
from typing import List, Dict, Any
from urllib.parse import urljoin, unquote
from bs4 import BeautifulSoup
import requests

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedKaitWithFiles:
    """KAIT 첨부파일 포함 완전한 스크래퍼"""
    
    def __init__(self):
        self.base_url = "https://www.kait.or.kr"
        self.list_url = "https://www.kait.or.kr/user/MainBoardList.do"
        self.cate_seq = "13"
        self.board_id = "101"
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # 통계
        self.stats = {
            'total_announcements': 0,
            'total_files_downloaded': 0,
            'total_download_size': 0,
            'failed_downloads': 0
        }
        
    def get_list_url(self, page_num: int) -> str:
        """페이지별 URL 생성"""
        if page_num == 1:
            return f"{self.list_url}?cateSeq={self.cate_seq}&bId={self.board_id}"
        else:
            return f"{self.list_url}?cateSeq={self.cate_seq}&bId={self.board_id}&pageIndex={page_num}"
    
    def get_page_announcements(self, page_num: int) -> List[Dict[str, Any]]:
        """페이지별 공고 목록 가져오기"""
        try:
            url = self.get_list_url(page_num)
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            return self.parse_list_page(response.text, page_num)
            
        except Exception as e:
            logger.error(f"페이지 {page_num} 처리 중 오류: {e}")
            return []
    
    def parse_list_page(self, html_content: str, page_num: int) -> List[Dict[str, Any]]:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # KAIT 테이블 찾기
        table = soup.find('table')
        if not table:
            logger.warning(f"페이지 {page_num}에서 테이블을 찾을 수 없습니다")
            return announcements
        
        tbody = table.find('tbody')
        if not tbody:
            logger.warning(f"페이지 {page_num}에서 tbody를 찾을 수 없습니다")
            return announcements
        
        rows = tbody.find_all('tr')
        logger.info(f"페이지 {page_num}에서 {len(rows)}개 행 발견")
        
        for i, row in enumerate(rows):
            try:
                # onclick 속성에서 goDetail 파라미터 추출
                onclick = row.get('onclick', '')
                if not onclick:
                    continue
                
                # goDetail(bSeq, bId) 패턴에서 파라미터 추출
                match = re.search(r'goDetail\((\d+),\s*(\d+)\)', onclick)
                if not match:
                    continue
                
                bSeq, bId = match.groups()
                
                cells = row.find_all('td')
                if len(cells) < 5:  # 번호, 제목, 파일, 날짜, 조회
                    continue
                
                # 컬럼 파싱
                number = cells[0].get_text(strip=True)
                
                # 제목
                title_link = cells[1].find('a')
                if title_link:
                    title = title_link.get_text(strip=True)
                    title = re.sub(r'\s*\[?NEW\]?\s*', '', title)  # NEW 아이콘 제거
                else:
                    title = cells[1].get_text(strip=True)
                
                # 첨부파일 확인
                has_attachments = bool(cells[2].find('img'))
                
                date = cells[3].get_text(strip=True)
                views = cells[4].get_text(strip=True)
                
                announcement = {
                    'page': page_num,
                    'number': number,
                    'title': title,
                    'author': 'KAIT',
                    'date': date,
                    'views': views,
                    'bSeq': bSeq,
                    'bId': bId,
                    'has_attachments': has_attachments,
                    'detail_url': f"{self.base_url}/user/boardDetail.do?bSeq={bSeq}&bId={bId}"
                }
                
                announcements.append(announcement)
                logger.debug(f"공고 추가: [{number}] {title}")
                
            except Exception as e:
                logger.error(f"페이지 {page_num} 행 {i} 파싱 중 오류: {e}")
                continue
        
        logger.info(f"페이지 {page_num}에서 총 {len(announcements)}개 공고 파싱 완료")
        return announcements
    
    def get_detail_page(self, announcement: Dict[str, Any]) -> str:
        """상세 페이지 HTML 가져오기 - POST 방식"""
        try:
            detail_url = f"{self.base_url}/user/boardDetail.do"
            
            # POST 데이터 구성
            data = {
                'bSeq': announcement['bSeq'],
                'bId': announcement['bId'],
                'cateSeq': self.cate_seq
            }
            
            # POST 요청 헤더 설정
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': f"{self.base_url}/user/MainBoardList.do?cateSeq={self.cate_seq}&bId={self.board_id}"
            }
            
            response = self.session.post(detail_url, data=data, headers=headers, timeout=30)
            if response.status_code == 200:
                logger.debug(f"상세 페이지 접근 성공: bSeq={announcement['bSeq']}")
                return response.text
            else:
                logger.error(f"상세 페이지 접근 실패: bSeq={announcement['bSeq']}, 상태코드: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"상세 페이지 가져오기 실패: {e}")
            return None
    
    def parse_detail_page(self, html_content: str) -> Dict[str, Any]:
        """상세 페이지 파싱 - 본문과 첨부파일 추출"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출
        title = "제목 없음"
        title_selectors = ['.board_view_title', '.title', 'h1', 'h2']
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                potential_title = title_elem.get_text(strip=True)
                if potential_title and len(potential_title) > 5:
                    title = potential_title
                    break
        
        # 본문 내용 추출
        content_text = self._extract_main_content(soup)
        
        # 메타 정보 추출
        meta_info = self._extract_meta_info(soup)
        
        # 첨부파일 추출
        attachments = self._extract_attachments(soup)
        
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
    
    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """상세 페이지에서 본문 내용 추출"""
        
        # 불필요한 요소들 제거
        unwanted_selectors = [
            'nav', 'header', 'footer', '.nav', '.navigation',
            '.menu', '.sidebar', '.breadcrumb',
            'script', 'style', '.ads', '.advertisement'
        ]
        
        for selector in unwanted_selectors:
            for elem in soup.select(selector):
                elem.decompose()
        
        # KAIT 특화 콘텐츠 선택자
        content_selectors = [
            '.board_view_content',
            '.view_content',
            '.content_area',
            '.board_content',
            '.detail_content',
            'main',
            '[role="main"]'
        ]
        
        content_elem = None
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                logger.debug(f"콘텐츠 선택자 사용: {selector}")
                break
        
        if content_elem:
            # 추가 불필요한 요소 제거
            for unwanted in content_elem.select('.btn, .button, .pagination, .paging'):
                unwanted.decompose()
            
            # 본문 텍스트 추출
            content_text = self.simple_html_to_text(content_elem)
        else:
            # 백업 방법: div나 p 태그에서 가장 긴 텍스트 찾기
            content_candidates = []
            
            for elem in soup.find_all(['div', 'p', 'article', 'section']):
                text = elem.get_text(strip=True)
                if len(text) > 100:  # 최소 길이 조건
                    content_candidates.append(text)
            
            # 가장 긴 텍스트를 본문으로 선택
            if content_candidates:
                content_text = max(content_candidates, key=len)
            else:
                content_text = "본문 내용을 찾을 수 없습니다."
        
        return content_text.strip()
    
    def simple_html_to_text(self, element) -> str:
        """HTML 요소를 간단한 텍스트로 변환"""
        text = element.get_text(separator='\n\n', strip=True)
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text
    
    def _extract_meta_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """메타 정보 추출"""
        meta_info = {}
        
        # 페이지 텍스트에서 날짜 패턴 찾기
        page_text = soup.get_text()
        date_match = re.search(r'(\d{4}[-./]\d{2}[-./]\d{2})', page_text)
        if date_match:
            meta_info['작성일'] = date_match.group(1)
        
        # 조회수 패턴 찾기
        views_match = re.search(r'조회수?\s*:?\s*(\d+)', page_text)
        if views_match:
            meta_info['조회수'] = views_match.group(1)
        
        # 작성자 정보
        meta_info['작성자'] = 'KAIT'
        
        return meta_info
    
    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """첨부파일 정보 추출"""
        attachments = []
        
        # KAIT 파일 다운로드 링크 패턴: /user/FileDownload[N].do?bSeq=...&bId=...
        download_links = soup.find_all('a', href=re.compile(r'/user/FileDownload\d+\.do'))
        
        for i, link in enumerate(download_links, 1):
            try:
                href = link.get('href', '')
                if '/user/FileDownload' not in href:
                    continue
                
                # 파일명 추출 (링크 텍스트에서)
                filename = link.get_text(strip=True)
                if not filename:
                    filename = f"attachment_{i}"
                
                # 전체 URL 구성
                file_url = urljoin(self.base_url, href)
                
                # 파일 타입 확인
                file_type = self._determine_file_type(filename)
                
                attachment = {
                    'filename': filename,
                    'url': file_url,
                    'type': file_type,
                    'download_method': 'direct'
                }
                
                attachments.append(attachment)
                logger.debug(f"첨부파일 발견: {filename}")
                
            except Exception as e:
                logger.error(f"첨부파일 처리 중 오류: {e}")
                continue
        
        logger.info(f"첨부파일 {len(attachments)}개 발견")
        return attachments
    
    def _determine_file_type(self, filename: str) -> str:
        """파일 타입 결정"""
        if not filename:
            return 'unknown'
        
        filename_lower = filename.lower()
        
        if filename_lower.endswith('.pdf'):
            return 'pdf'
        elif filename_lower.endswith(('.hwp', '.hwpx')):
            return 'hwp'
        elif filename_lower.endswith(('.doc', '.docx')):
            return 'doc'
        elif filename_lower.endswith(('.xls', '.xlsx')):
            return 'excel'
        elif filename_lower.endswith(('.jpg', '.jpeg', '.png', '.gif')):
            return 'image'
        elif filename_lower.endswith('.zip'):
            return 'zip'
        else:
            return 'unknown'
    
    def download_file(self, file_url: str, save_path: str) -> bool:
        """파일 다운로드 - KAIT 특화 처리"""
        try:
            logger.info(f"파일 다운로드 시작: {file_url}")
            
            # KAIT 사이트 파일 다운로드
            response = self.session.get(file_url, stream=True, timeout=60)
            response.raise_for_status()
            
            # Content-Disposition에서 파일명 추출 시도
            content_disposition = response.headers.get('Content-Disposition', '')
            if content_disposition:
                extracted_filename = self._extract_filename_from_disposition(content_disposition)
                if extracted_filename:
                    # 디렉토리는 유지하고 파일명만 변경
                    directory = os.path.dirname(save_path)
                    save_path = os.path.join(directory, self.sanitize_filename(extracted_filename))
            
            # 파일 저장
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(save_path)
            logger.info(f"파일 다운로드 완료: {os.path.basename(save_path)} ({file_size:,} bytes)")
            
            # 통계 업데이트
            self.stats['total_files_downloaded'] += 1
            self.stats['total_download_size'] += file_size
            
            return True
            
        except Exception as e:
            logger.error(f"파일 다운로드 실패: {e}")
            self.stats['failed_downloads'] += 1
            return False
    
    def _extract_filename_from_disposition(self, content_disposition: str) -> str:
        """Content-Disposition 헤더에서 파일명 추출"""
        try:
            # KAIT는 filename= 파라미터를 사용
            filename_match = re.search(r'filename=([^;]+)', content_disposition)
            if filename_match:
                encoded_filename = filename_match.group(1)
                
                # URL 디코딩 및 + 기호를 공백으로 변환
                try:
                    filename = unquote(encoded_filename).replace('+', ' ')
                    return filename.strip()
                except:
                    return encoded_filename.replace('+', ' ')
                        
        except Exception as e:
            logger.debug(f"파일명 추출 실패: {e}")
            
        return None
    
    def sanitize_filename(self, filename: str) -> str:
        """파일명 정리 - 시스템에서 사용할 수 없는 문자 제거"""
        # Windows와 Linux에서 사용할 수 없는 문자들 제거
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # 연속된 공백을 하나로 변경
        filename = re.sub(r'\s+', ' ', filename)
        
        # 앞뒤 공백 및 점 제거
        filename = filename.strip('. ')
        
        # 너무 긴 파일명 줄이기 (200자 제한)
        if len(filename) > 200:
            name, ext = os.path.splitext(filename)
            filename = name[:200-len(ext)] + ext
        
        return filename
    
    def process_announcement(self, announcement: Dict[str, Any], output_dir: str) -> bool:
        """개별 공고 처리 - 상세 페이지 및 첨부파일 수집"""
        try:
            logger.info(f"공고 처리 중: {announcement['title']}")
            
            # 안전한 디렉토리명 생성
            safe_title = re.sub(r'[^\w\s-]', '', announcement['title'])
            safe_title = re.sub(r'[-\s]+', '_', safe_title)[:50]
            
            announcement_dir = os.path.join(output_dir, f"{announcement['number']}_{safe_title}")
            os.makedirs(announcement_dir, exist_ok=True)
            
            # 첨부파일이 있는 경우만 상세 페이지 접근
            if announcement['has_attachments']:
                detail_html = self.get_detail_page(announcement)
                if detail_html:
                    detail_data = self.parse_detail_page(detail_html)
                    
                    # 본문 저장
                    content_path = os.path.join(announcement_dir, 'content.md')
                    with open(content_path, 'w', encoding='utf-8') as f:
                        f.write(detail_data['content'])
                    
                    # 첨부파일 다운로드
                    if detail_data['attachments']:
                        logger.info(f"{len(detail_data['attachments'])}개 첨부파일 다운로드 시작")
                        for i, attachment in enumerate(detail_data['attachments'], 1):
                            safe_filename = self.sanitize_filename(attachment['filename'])
                            if not safe_filename:
                                safe_filename = f"attachment_{i}"
                            
                            file_path = os.path.join(announcement_dir, safe_filename)
                            success = self.download_file(attachment['url'], file_path)
                            
                            if success:
                                logger.info(f"첨부파일 다운로드 성공: {safe_filename}")
                            else:
                                logger.error(f"첨부파일 다운로드 실패: {safe_filename}")
                else:
                    logger.warning(f"상세 페이지 접근 실패: {announcement['title']}")
            else:
                # 첨부파일이 없는 경우 기본 정보만 저장
                content = f"""# {announcement['title']}

**작성일**: {announcement['date']}
**조회수**: {announcement['views']}
**첨부파일**: 없음
**상세 URL**: {announcement['detail_url']}

---

## KAIT 공고 정보

이 공고는 한국정보기술산업협회(KAIT)에서 발표한 공고입니다.

**게시번호**: {announcement['number']}
**bSeq**: {announcement['bSeq']}
**bId**: {announcement['bId']}

상세 내용은 원본 URL에서 확인하실 수 있습니다.
"""
                
                content_path = os.path.join(announcement_dir, 'content.md')
                with open(content_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            return True
            
        except Exception as e:
            logger.error(f"공고 처리 실패: {announcement['title']} - {e}")
            return False
    
    def scrape_pages(self, max_pages: int = 3, output_dir: str = "output/kait_with_files") -> Dict[str, Any]:
        """여러 페이지 스크래핑 - 첨부파일 포함"""
        logger.info("=== KAIT 첨부파일 포함 스크래핑 시작 ===")
        
        os.makedirs(output_dir, exist_ok=True)
        all_announcements = []
        
        for page_num in range(1, max_pages + 1):
            logger.info(f"=== 페이지 {page_num} 처리 중 ===")
            
            page_announcements = self.get_page_announcements(page_num)
            if not page_announcements:
                logger.warning(f"페이지 {page_num}에 공고가 없습니다")
                break
            
            all_announcements.extend(page_announcements)
            
            # 페이지 간 딜레이
            if page_num < max_pages:
                time.sleep(2)
        
        # 개별 공고 처리
        logger.info(f"총 {len(all_announcements)}개 공고 처리 시작")
        
        for announcement in all_announcements:
            self.process_announcement(announcement, output_dir)
            self.stats['total_announcements'] += 1
            
            # 공고 간 딜레이
            time.sleep(1)
        
        # 전체 요약 파일 생성
        self.create_summary(all_announcements, output_dir)
        
        return {
            'total_announcements': len(all_announcements),
            'announcements': all_announcements,
            'stats': self.stats
        }
    
    def create_summary(self, announcements: List[Dict], output_dir: str):
        """전체 요약 파일 생성"""
        summary_content = f"""# KAIT 첨부파일 포함 수집 결과

**수집 일시**: {time.strftime('%Y-%m-%d %H:%M:%S')}
**총 공고 수**: {len(announcements)}개
**다운로드된 파일 수**: {self.stats['total_files_downloaded']}개
**총 다운로드 크기**: {self.stats['total_download_size']:,} bytes ({self.stats['total_download_size']/1024/1024:.1f} MB)
**다운로드 실패**: {self.stats['failed_downloads']}개

## 수집된 공고 목록

"""
        
        for i, announcement in enumerate(announcements, 1):
            attachment_status = "📎 첨부파일 있음" if announcement['has_attachments'] else "📄 첨부파일 없음"
            summary_content += f"{i:3d}. [{announcement['number']}] {announcement['title']} ({announcement['date']}) - {attachment_status}\n"
        
        summary_path = os.path.join(output_dir, 'summary.md')
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(summary_content)
        
        logger.info(f"요약 파일 저장 완료: {summary_path}")


def main():
    """테스트 실행"""
    output_dir = "output/kait_with_files"
    
    scraper = EnhancedKaitWithFiles()
    
    try:
        results = scraper.scrape_pages(max_pages=3, output_dir=output_dir)
        
        print(f"\n✅ KAIT 첨부파일 포함 스크래핑 완료!")
        print(f"수집된 공고: {results['total_announcements']}개")
        print(f"다운로드된 파일: {results['stats']['total_files_downloaded']}개")
        print(f"총 다운로드 크기: {results['stats']['total_download_size']:,} bytes ({results['stats']['total_download_size']/1024/1024:.1f} MB)")
        print(f"다운로드 실패: {results['stats']['failed_downloads']}개")
        print(f"저장 위치: {output_dir}")
        
    except Exception as e:
        print(f"❌ 스크래핑 실패: {e}")
        raise


if __name__ == "__main__":
    main()