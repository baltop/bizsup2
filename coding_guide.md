# 웹 스크래핑 개발자 매뉴얼

## 개요
이 문서는 정부 기관 및 공공 기관 웹사이트에서 공고문과 첨부파일을 수집하는 Enhanced Scraper 개발 과정을 정리한 가이드입니다.

## 목차
1. [개발 환경 설정](#개발-환경-설정)
2. [사이트 분석 방법론](#사이트-분석-방법론)
3. [스크래퍼 개발 프로세스](#스크래퍼-개발-프로세스)
4. [코드 구조 및 템플릿](#코드-구조-및-템플릿)
5. [한글 파일명 처리](#한글-파일명-처리)
6. [디버깅 및 문제 해결](#디버깅-및-문제-해결)
7. [성능 최적화](#성능-최적화)
8. [테스트 및 검증](#테스트-및-검증)
9. [사이트별 특성 분석](#사이트별-특성-분석)

## 개발 환경 설정

### 필수 라이브러리
```python
import os
import re
import time
import requests
from urllib.parse import urljoin, quote, unquote, urlparse, parse_qs
from bs4 import BeautifulSoup
import html2text
from datetime import datetime
import logging
from pathlib import Path
import json
import hashlib
```

### 기본 설정
```python
# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 세션 헤더 설정
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
})
```

## 사이트 분석 방법론

### 1. 초기 분석 체크리스트
- [ ] 사이트 기술 스택 확인 (PHP, Java, JavaScript 등)
- [ ] 공고 목록 페이지 HTML 구조 분석
- [ ] 페이지네이션 방식 확인
- [ ] 상세 페이지 구조 분석
- [ ] 첨부파일 다운로드 방식 확인
- [ ] 보안 조치 (CSRF, robots.txt 등) 확인

### 2. Task 도구 활용
```python
# 사이트 분석 시 Task 도구 사용 예시
task_prompt = """
웹사이트 {URL}을 분석하여 다음 정보를 제공해주세요:
1. 기술 스택 및 웹사이트 구조
2. 공고 목록 테이블 구조
3. 페이지네이션 시스템
4. 첨부파일 다운로드 메커니즘
5. 한글 파일명 처리 방법
6. 보안 조치 현황
"""
```

### 3. 테이블 구조 분석 방법
```python
# 디버깅을 위한 테이블 구조 확인
def analyze_table_structure(soup):
    tables = soup.find_all('table')
    for i, table in enumerate(tables):
        print(f"Table {i}: {table.get('class', 'no class')}")
        
        tbody = table.find('tbody')
        if tbody:
            rows = tbody.find_all('tr')
            print(f"  Rows: {len(rows)}")
            
            if rows:
                first_row = rows[0]
                cells = first_row.find_all('td')
                print(f"  Columns: {len(cells)}")
                
                for j, cell in enumerate(cells):
                    print(f"    Cell {j}: {cell.get_text(strip=True)[:50]}...")
```

## 스크래퍼 개발 프로세스

### 1. 기본 클래스 구조
```python
class EnhancedScraper:
    def __init__(self, base_url, site_code, output_dir="output"):
        self.base_url = base_url
        self.site_code = site_code
        self.output_dir = output_dir
        self.session = requests.Session()
        
        # 로깅 설정
        self.logger = logging.getLogger(__name__)
        
        # HTML to markdown 변환기
        self.h = html2text.HTML2Text()
        self.h.ignore_links = False
        self.h.ignore_images = False
        self.h.ignore_emphasis = False
        
        # 통계 추적
        self.stats = {
            'total_notices': 0,
            'total_files': 0,
            'failed_downloads': 0,
            'pages_processed': 0
        }
        
        # 중복 처리 방지
        self.processed_titles = set()
        self.current_session_titles = set()
        
        self.setup_directories()
        self.load_processed_titles()
```

### 2. 핵심 메서드 구현

#### 공고 목록 추출
```python
def extract_notice_list(self, soup):
    """공고 목록에서 데이터 추출"""
    notices = []
    
    # 테이블 구조에 따라 선택자 조정
    # 예시 1: 표준 테이블 구조
    table = soup.select_one('.tbl_head01.tbl_wrap table')
    
    # 예시 2: 클래스 기반 테이블
    table = soup.find('table', class_='board_list')
    
    if not table:
        return notices
    
    rows = table.find('tbody').find_all('tr')
    
    for row in rows:
        cells = row.find_all('td')
        if len(cells) < 4:  # 최소 셀 개수 확인
            continue
            
        # 셀 구조에 따라 데이터 추출
        # 4컬럼 구조: 제목, 작성자, 날짜, 조회수
        title_cell = cells[0]
        title_link = title_cell.find('a')
        
        if not title_link:
            continue
            
        # 데이터 추출 및 정리
        notice_data = {
            'title': title_link.get_text(strip=True),
            'detail_url': urljoin(self.base_url, title_link.get('href')),
            'author': cells[1].get_text(strip=True),
            'date': cells[2].get_text(strip=True),
            'views': cells[3].get_text(strip=True)
        }
        
        notices.append(notice_data)
    
    return notices
```

#### 상세 페이지 처리
```python
def scrape_notice_detail(self, notice_data):
    """개별 공고 상세 페이지 처리"""
    try:
        response = self.session.get(notice_data['detail_url'], timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser', from_encoding='utf-8')
        
        # 디렉토리 생성
        safe_title = self.get_safe_filename(notice_data['title'], notice_data['id'])
        notice_dir = os.path.join(self.output_dir, self.site_code, safe_title)
        os.makedirs(notice_dir, exist_ok=True)
        
        # 첨부파일 디렉토리
        attachments_dir = os.path.join(notice_dir, "attachments")
        os.makedirs(attachments_dir, exist_ok=True)
        
        # 콘텐츠 추출
        content_html = self.extract_content(soup)
        content_markdown = self.h.handle(content_html)
        
        # 마크다운 파일 저장
        self.save_content(notice_dir, notice_data, content_markdown)
        
        # 첨부파일 다운로드
        downloaded_files = self.download_attachments(soup, attachments_dir)
        
        self.stats['total_notices'] += 1
        self.add_processed_title(notice_data['title'])
        
        return True
        
    except Exception as e:
        self.logger.error(f"Failed to scrape notice {notice_data['id']}: {str(e)}")
        return False
```

## 코드 구조 및 템플릿

### 1. 파일 다운로드 템플릿
```python
def download_file(self, file_url, attachments_dir, original_filename):
    """첨부파일 다운로드"""
    try:
        if not file_url.startswith('http'):
            file_url = urljoin(self.base_url, file_url)
        
        response = self.session.get(file_url, stream=True, timeout=30)
        response.raise_for_status()
        
        # 파일명 추출 및 한글 처리
        filename = self.extract_filename(response, original_filename)
        
        # 파일 저장
        file_path = os.path.join(attachments_dir, filename)
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        file_size = os.path.getsize(file_path)
        self.logger.info(f"Downloaded: {filename} ({file_size} bytes)")
        self.stats['total_files'] += 1
        
        return filename, file_size
        
    except Exception as e:
        self.logger.error(f"Failed to download file {file_url}: {str(e)}")
        self.stats['failed_downloads'] += 1
        return None, 0
```

### 2. 중복 처리 방지 시스템
```python
def normalize_title(self, title):
    """제목 정규화"""
    if not title:
        return ""
    
    normalized = title.strip()
    normalized = re.sub(r'\s+', ' ', normalized)
    normalized = re.sub(r'[^\w\s가-힣()-]', '', normalized)
    normalized = normalized.lower()
    
    return normalized

def get_title_hash(self, title):
    """제목 해시 생성"""
    normalized = self.normalize_title(title)
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()

def is_title_processed(self, title):
    """중복 확인"""
    title_hash = self.get_title_hash(title)
    return title_hash in self.processed_titles
```

## 한글 파일명 처리

### 1. 인코딩별 처리 방법

#### EUC-KR 인코딩 (PHP 사이트)
```python
def extract_filename_euckr(self, response, original_filename):
    """EUC-KR 인코딩 파일명 처리"""
    filename = original_filename
    
    if 'content-disposition' in response.headers:
        cd = response.headers['content-disposition']
        filename_match = re.search(r'filename\s*=\s*"([^"]+)"', cd)
        
        if filename_match:
            raw_filename = filename_match.group(1)
            try:
                # EUC-KR 디코딩
                filename = raw_filename.encode('latin-1').decode('euc-kr')
                self.logger.info(f"EUC-KR decoded filename: {filename}")
            except (UnicodeDecodeError, UnicodeEncodeError):
                # UTF-8 fallback
                try:
                    filename = raw_filename.encode('latin-1').decode('utf-8')
                except:
                    filename = raw_filename
    
    return self.clean_filename(filename)
```

#### UTF-8 인코딩 (Java 사이트)
```python
def extract_filename_utf8(self, response, original_filename):
    """UTF-8 인코딩 파일명 처리"""
    filename = original_filename
    
    if 'content-disposition' in response.headers:
        cd = response.headers['content-disposition']
        
        # UTF-8 인코딩 처리
        if '%' in cd:
            try:
                filename = unquote(cd.split('filename=')[1].strip('"'))
            except:
                pass
        else:
            try:
                filename = cd.split('filename=')[1].strip('"')
                filename = filename.encode('latin-1').decode('utf-8')
            except:
                pass
    
    return self.clean_filename(filename)
```

### 2. JavaScript 파일 시스템 처리
```python
def extract_files_from_javascript(self, soup):
    """JavaScript 기반 파일 다운로드 처리"""
    files = []
    
    # onclick 핸들러에서 파일 정보 추출
    onclick_elements = soup.find_all(attrs={"onclick": True})
    
    for element in onclick_elements:
        onclick_value = element.get('onclick', '')
        if 'fnClickFileDown' in onclick_value:
            match = re.search(r'fnClickFileDown\([\'"]([^\'"]+)[\'"]', onclick_value)
            if match:
                file_data = match.group(1)
                file_info = self.parse_js_file_data(file_data)
                if file_info:
                    files.append(file_info)
    
    return files
```

## 디버깅 및 문제 해결

### 1. 일반적인 문제 해결 방법

#### 테이블 구조 확인
```python
# 디버깅 모드로 테이블 분석
def debug_table_structure(self, soup):
    tables = soup.find_all('table')
    self.logger.debug(f"Found {len(tables)} tables")
    
    for i, table in enumerate(tables):
        self.logger.debug(f"Table {i}: {table.get('class', 'no class')}")
        
        tbody = table.find('tbody')
        if tbody:
            rows = tbody.find_all('tr')
            self.logger.debug(f"  Rows: {len(rows)}")
            
            for j, row in enumerate(rows[:3]):  # 첫 3개 행만 확인
                cells = row.find_all('td')
                cell_texts = [cell.get_text(strip=True) for cell in cells]
                self.logger.debug(f"  Row {j}: {cell_texts}")
```

#### 파일 다운로드 실패 처리
```python
def download_with_retry(self, file_url, attachments_dir, filename, max_retries=3):
    """재시도 로직이 포함된 파일 다운로드"""
    for attempt in range(max_retries):
        try:
            return self.download_file(file_url, attachments_dir, filename)
        except Exception as e:
            self.logger.warning(f"Download attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 지수 백오프
            else:
                self.logger.error(f"All download attempts failed for {file_url}")
                return None, 0
```

### 2. 로깅 전략
```python
# 상세 로깅 설정
def setup_detailed_logging(self):
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 파일 핸들러
    file_handler = logging.FileHandler(f'scraper_{self.site_code}.log')
    file_handler.setFormatter(formatter)
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    self.logger.addHandler(file_handler)
    self.logger.addHandler(console_handler)
    self.logger.setLevel(logging.DEBUG)
```

## 성능 최적화

### 1. 메모리 효율성
```python
# 스트리밍 다운로드
def download_large_file(self, file_url, file_path):
    """대용량 파일 스트리밍 다운로드"""
    with requests.get(file_url, stream=True) as response:
        response.raise_for_status()
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
```

### 2. 요청 간 딜레이
```python
# 정중한 스크래핑을 위한 딜레이
def polite_delay(self, base_delay=1):
    """서버 부하 방지를 위한 딜레이"""
    import random
    delay = base_delay + random.uniform(0, 1)
    time.sleep(delay)
```

### 3. 세션 관리
```python
def setup_session(self):
    """세션 설정 및 최적화"""
    self.session.mount('http://', requests.adapters.HTTPAdapter(max_retries=3))
    self.session.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))
    
    # 연결 풀 크기 설정
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=10,
        pool_maxsize=20
    )
    self.session.mount('http://', adapter)
    self.session.mount('https://', adapter)
```

## 테스트 및 검증

### 1. 파일 크기 검증
```python
def check_file_integrity(self):
    """다운로드된 파일의 무결성 검사"""
    site_dir = os.path.join(self.output_dir, self.site_code)
    file_sizes = {}
    
    for root, dirs, files in os.walk(site_dir):
        for file in files:
            if not file.endswith('.md'):
                file_path = os.path.join(root, file)
                size = os.path.getsize(file_path)
                
                if size in file_sizes:
                    file_sizes[size].append(file_path)
                else:
                    file_sizes[size] = [file_path]
    
    # 동일 크기 파일 검사 (오류 가능성)
    suspicious_sizes = {size: paths for size, paths in file_sizes.items() if len(paths) > 1}
    
    if suspicious_sizes:
        self.logger.warning("Found files with identical sizes (potential errors):")
        for size, paths in suspicious_sizes.items():
            self.logger.warning(f"Size {size} bytes: {len(paths)} files")
    else:
        self.logger.info("All files have different sizes - download integrity verified")
```

### 2. 한글 파일명 검증
```python
def verify_korean_filenames(self):
    """한글 파일명 처리 검증"""
    korean_files = []
    
    for root, dirs, files in os.walk(os.path.join(self.output_dir, self.site_code)):
        for file in files:
            if re.search(r'[가-힣]', file):
                korean_files.append(file)
    
    self.logger.info(f"Found {len(korean_files)} files with Korean names")
    
    # 파일명 인코딩 문제 검사
    problematic_files = []
    for file in korean_files:
        try:
            file.encode('utf-8')
        except UnicodeEncodeError:
            problematic_files.append(file)
    
    if problematic_files:
        self.logger.warning(f"Found {len(problematic_files)} files with encoding issues")
    else:
        self.logger.info("All Korean filenames properly encoded")
```

## 사이트별 특성 분석

### 1. PHP 기반 게시판 (예: GEI)
```python
# 특징:
# - 표준 HTML 테이블 구조
# - EUC-KR 인코딩 파일명
# - download.php 스크립트 사용
# - 직접 다운로드 링크

class PHPBoardScraper(EnhancedScraper):
    def extract_notice_list(self, soup):
        # 4컬럼 구조: 제목, 작성자, 날짜, 조회수
        table = soup.select_one('.tbl_head01.tbl_wrap table')
        # ... 구현
    
    def extract_filename(self, response, original_filename):
        # EUC-KR 인코딩 처리
        return self.extract_filename_euckr(response, original_filename)
```

### 2. Java 기반 시스템 (예: GFUND)
```python
# 특징:
# - JavaScript 기반 파일 다운로드
# - UTF-8 인코딩
# - 보안 강화 (CSRF, 세션 관리)
# - 엔터프라이즈 구조

class JavaSystemScraper(EnhancedScraper):
    def extract_attachments(self, soup):
        # JavaScript 함수에서 파일 정보 추출
        return self.extract_files_from_javascript(soup)
    
    def download_file(self, file_url, attachments_dir, filename):
        # 세션 기반 다운로드 처리
        # ... 구현
```

### 3. 커스텀 CMS 시스템 (예: GIBAMONEY)
```python
# 특징:
# - 커스텀 UI 프레임워크
# - 복잡한 메타데이터 구조
# - 다양한 파일 형식 지원

class CustomCMSScraper(EnhancedScraper):
    def extract_metadata(self, soup):
        # 복잡한 메타데이터 추출
        info_container = soup.find('div', class_='info1')
        # ... 구현
```

## 모범 사례 및 주의사항

### 1. 모범 사례
- **점진적 개발**: 사이트 분석 → 기본 스크래퍼 → 기능 추가 → 최적화
- **철저한 테스트**: 각 단계별 검증 및 오류 처리
- **로깅 활용**: 상세한 로그로 디버깅 지원
- **중복 방지**: 제목 해시 기반 중복 처리 시스템
- **정중한 스크래핑**: 적절한 딜레이 및 에러 처리

### 2. 주의사항
- **robots.txt 확인**: 프로젝트 요구사항에 따라 무시 가능
- **서버 부하 고려**: 과도한 요청으로 서버 부하 방지
- **인코딩 처리**: 한글 파일명 처리 시 다양한 인코딩 고려
- **세션 관리**: 필요시 쿠키 및 세션 상태 유지
- **보안 고려**: CSRF 토큰 등 보안 조치 대응

## 개발 체크리스트

### 사이트 분석 단계
- [ ] 기술 스택 확인
- [ ] HTML 구조 분석
- [ ] 페이지네이션 방식 확인
- [ ] 첨부파일 다운로드 메커니즘 확인
- [ ] 인코딩 방식 확인
- [ ] 보안 조치 확인

### 개발 단계
- [ ] 기본 클래스 구조 구현
- [ ] 공고 목록 추출 로직 구현
- [ ] 상세 페이지 처리 로직 구현
- [ ] 파일 다운로드 로직 구현
- [ ] 한글 파일명 처리 구현
- [ ] 중복 방지 시스템 구현

### 테스트 단계
- [ ] 기본 기능 테스트
- [ ] 파일 다운로드 테스트
- [ ] 한글 파일명 처리 테스트
- [ ] 파일 크기 검증
- [ ] 중복 처리 테스트
- [ ] 오류 처리 테스트

### 완성 단계
- [ ] 통계 정보 출력
- [ ] 인사이트 문서 생성
- [ ] 로그 파일 정리
- [ ] 성능 최적화
- [ ] 문서화 완료

## 결론

이 매뉴얼은 다양한 정부 기관 웹사이트에서 공고문과 첨부파일을 효율적으로 수집하기 위한 종합적인 가이드를 제공합니다. 각 사이트의 특성을 파악하고 적절한 기술을 적용하여 안정적이고 효율적인 스크래퍼를 개발할 수 있습니다.

핵심은 **철저한 분석, 점진적 개발, 충분한 테스트**를 통해 품질 높은 스크래퍼를 만드는 것입니다. 이 가이드를 참고하여 향후 프로젝트에서 더욱 효율적인 개발이 가능할 것입니다.

## 참고 자료

### 성공 사례
1. **GFUND 스크래퍼**: JavaScript 기반 파일 시스템 극복
2. **GEI 스크래퍼**: PHP 게시판 시스템 완벽 처리
3. **GIBAMONEY 스크래퍼**: 커스텀 CMS 시스템 대응

### 기술 스택별 특징
- **PHP 기반**: 표준 HTML, EUC-KR 인코딩, 직접 다운로드
- **Java 기반**: JavaScript 파일 시스템, UTF-8 인코딩, 보안 강화
- **커스텀 CMS**: 복잡한 구조, 다양한 메타데이터, 유연한 접근 필요

이 매뉴얼을 기반으로 향후 웹 스크래핑 프로젝트의 성공률을 크게 높일 수 있을 것입니다.