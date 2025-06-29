# "지원사업 공고 수집" Project Guidelines

## 목표
주어진 URL의 사이트에 접속하여 사이트에 공지된 지원사업 공고문을 수집하고 첨부파일을 다운로드 하여 로컬디렉토리에 저장한다.
사이트의 공고는 대부분 pagination 기반의 BBS 형태로 되어 있다.
주어진 URL은 1 페이지의  목록 페이지 이다. 목록들은 대부분 10개에서 30개 내외이다.
수집을 위해 목록 상의 첫번째 공고의 링크를 타고 상세 페이지로 이동하여, 상세페이지에서 공고 내용을 markdown 방식으로 저장한다.
공고 본문이 있는 상세페이지에는 공고본문과 첨부파일 링크가 있다. 첨부파일 링크가 있는 경우 첨부파일들을 다운로드 하여 로컬에 저장한다.
각 공고 별로 본문 파일과 첨부파일은 분리되어 저장되어야 한다.

## 세부 단계
- 주어진 URL을 접속하여 html을 다운로드 받는다.
- html의 태그와 엘레멘트를 분석하여 DOM 구조를 파악한다.
- 공고 목록을 파악하여 각 공고의 세부페이지로 이동할 수 있는 링크나 javacript 방법을 찾아낸다.
- 첫번째 공고 상세 페이지로 이동한다.
- 상세페이지의 html를 분석하여 헤더 제목 등은 제외하고 공고 본문만 추려 낼수 있는 태그, 엘레멘트를 찾아내서 해당 부분만을 markdown으로 변환하여 파일로 저장한다.
- 상세패이지의 html을 분석하여 첨부파일이 있으면 첨부파일을 다운로드 받는다.
- 다시 목록 페이지로 되돌아 가서 다음 공고를 위와 같은 방식으로 처리하고 목록의 전체 공고가 처리될때까지 반복한다.
- 주어진 URL의 공고들을 전부 처리했으면 하단의 pagination bar를 분석하여 다음 페이지로 이동한다.
- 다음 페이지도 공고들이 있으므로 이것들으 처리하고 전부 처리되고 나면 다시 다음 페이지로 이동한다.
- 4페이지까지만 반복하고 4페이지가 끝나면 프로그램을 중단한다.

## 새로운 사이트 추가 시 주의사항

### 1. 사이트 구조 분석
새로운 사이트를 추가하기 전에 반드시 다음 사항들을 확인해야 합니다:

#### 1.1 페이지 구조 확인
- **목록 페이지 URL 패턴**: 페이지네이션이 어떻게 구현되어 있는지 확인
  - GET 파라미터 방식: `?page=2`, `?p=2`, `?pageNo=2` 등
  - POST 요청 방식: AJAX/JSON으로 데이터를 가져오는 경우
  - JavaScript 함수 호출: `onclick="goPage(2)"` 등

- **상세 페이지 접근 방식**:
  - 직접 링크: `<a href="/board/view?id=123">`
  - JavaScript 함수: `onclick="viewDetail(123)"`
  - POST 요청: 폼 전송으로 상세 페이지 접근

#### 1.2 HTML 구조 파악
- **목록 페이지 구조**:
  - 테이블 기반: `<table>`, `<tr>`, `<td>`
  - 리스트 기반: `<ul>`, `<li>` 또는 `<div>` 반복
  - 공고 제목, 날짜, 조회수, 첨부파일 여부 등의 위치 확인

- **상세 페이지 구조**:
  - 본문 영역: 공고 내용이 들어있는 컨테이너 찾기
  - 첨부파일 영역: 파일 다운로드 링크가 있는 위치
  - 메타 정보: 작성자, 작성일, 조회수 등

### 2. 기술적 고려사항

#### 2.1 정적 vs 동적 사이트
- **정적 HTML**: BeautifulSoup으로 파싱 가능
- **JavaScript 렌더링**: Playwright나 Selenium 필요
- **AJAX/JSON API**: requests로 직접 API 호출

#### 2.2 인증 및 보안
- **세션 관리**: 로그인이 필요한 경우 세션 유지
- **CSRF 토큰**: POST 요청 시 토큰 처리
- **User-Agent**: 일부 사이트는 브라우저 User-Agent 필요
- **SSL 인증서**: `verify=False` 옵션 필요할 수 있음

#### 2.3 첨부파일 다운로드
- **직접 링크**: `<a href="/download/file.pdf">`
- **JavaScript 함수**: `onclick="download(123)"`
- **인증 필요**: 세션 쿠키나 토큰이 필요한 경우
- **리다이렉트**: 여러 단계의 리다이렉트를 거치는 경우

### 3. 구현 체크리스트

#### 3.1 새 스크래퍼 클래스 생성
```python
from base_scraper import BaseScraper

class NewSiteScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.base_url = "https://example.com"
        self.list_url = "https://example.com/board/list"
    
    def get_list_url(self, page_num):
        # 페이지별 URL 생성 로직
        pass
    
    def parse_list_page(self, html_content):
        # 목록 페이지 파싱 로직
        pass
    
    def parse_detail_page(self, html_content):
        # 상세 페이지 파싱 로직
        pass
```

#### 3.2 tp_scraper.py에 추가
- 새 스크래퍼 import
- argparse choices에 추가
- 실행 로직에 새 사이트 처리 추가

### 4. 일반적인 문제 해결 방법

#### 4.1 페이지 로드 실패
- User-Agent 헤더 추가
- SSL 인증서 검증 비활성화
- 타임아웃 값 증가
- 쿠키/세션 처리

#### 4.2 파싱 실패
- HTML 구조 재확인
- JavaScript 렌더링 필요 여부 확인
- 인코딩 문제 확인 (UTF-8, EUC-KR 등)

#### 4.3 첨부파일 다운로드 실패
- 다운로드 URL 패턴 분석
- Referer 헤더 추가
- 세션 쿠키 확인
- JavaScript 실행 필요 여부

### 5. 테스트 방법

1. **단계별 테스트**:
   ```bash
   # 1. 목록 페이지 접근 테스트
   curl -s "목록URL" | grep "공고제목"
   
   # 2. 상세 페이지 접근 테스트
   python3 -c "from new_scraper import NewSiteScraper; ..."
   
   # 3. 첨부파일 다운로드 테스트
   # 개별 파일 다운로드 테스트
   ```

2. **전체 실행 테스트**:
   ```bash
   # 1페이지만 테스트
   python tp_scraper.py --site newsite --pages 1
   ```

### 6. 현재 구현된 사이트별 특징 요약

- **BTP**: 표준적인 게시판, 직접 링크 방식
- **ITP**: JavaScript 함수 기반, 파일 다운로드 제한
- **CCEI**: AJAX/JSON API, POST 요청 방식, 파일 정보가 목록 API에 포함
- **KIDP**: JavaScript 렌더링, 복잡한 URL 파라미터
- **GSIF**: Base64 인코딩된 파라미터, 특수한 테이블 구조
- **DJBEA**: SSL 인증서 문제, JavaScript 기반 네비게이션
- **MIRE**: PHP 세션 기반, EUC-KR 인코딩, 특수한 테이블 구조
- **DCB**: 표준 테이블 구조, 다양한 파일 다운로드 패턴

새로운 사이트를 추가할 때는 위 사이트들 중 가장 유사한 구조를 가진 스크래퍼를 참고하여 구현하면 됩니다.

### 7. AJAX 기반 동적 사이트 스크래핑 패턴

#### 7.1 AJAX API 직접 호출 방식
많은 최신 사이트들이 JavaScript와 AJAX를 사용해 동적으로 콘텐츠를 로드합니다. 이런 사이트들의 특징과 대응 방법:

**특징 식별 방법**:
- 페이지 소스보기와 브라우저 렌더링 결과가 다름
- 빈 `div` 컨테이너들이 존재 (`contents_detail`, `boardlist` 등)
- 네트워크 탭에서 XHR/Fetch 요청 확인 필요

**해결 패턴**:
```python
def _get_page_announcements(self, page_num: int) -> list:
    """AJAX API를 통한 공고 목록 가져오기"""
    api_url = f"{self.base_url}/front/board/boardContentsList.do"
    
    # AJAX 요청 데이터 구성
    data = {
        'miv_pageNo': str(page_num),
        'miv_pageSize': '15',
        'boardId': '10521',  # 사이트별 고유값
        'menuId': '10057',   # 사이트별 고유값
        'searchKey': 'A',
        'searchTxt': ''
    }
    
    # POST 요청으로 AJAX API 호출
    response = self.post_page(api_url, data=data)
    return self.parse_list_page(response.text)
```

**적용 사례**: 함안상공회의소, 창원상공회의소 등 한국상공회의소 계열 사이트들

#### 7.2 JavaScript 기반 네비게이션 처리
상세 페이지 접근이 JavaScript 함수로 구현된 경우:

**패턴 예시**:
- `onclick="contentsView('114136')"`
- `onclick="viewDetail('12345')"`
- `onclick="showBoard(id)"`

**추출 로직**:
```python
# JavaScript 함수에서 ID 추출
id_match = re.search(r"contentsView\('(\d+)'\)", onclick)
if id_match:
    content_id = id_match.group(1)
    detail_url = f"{self.base_url}/front/board/boardContentsView.do?contId={content_id}&boardId=10521&menuId=10057"
```

#### 7.3 Enhanced Base Scraper 활용 패턴
AJAX 사이트에서도 Enhanced Base Scraper의 장점을 최대한 활용:

```python
class EnhancedAjaxScraper(StandardTableScraper):
    """AJAX 기반 사이트용 Enhanced 스크래퍼"""
    
    def _get_page_announcements(self, page_num: int) -> list:
        """AJAX API 호출로 오버라이드"""
        # 기본 클래스의 중복 체크, 인코딩 처리 등은 그대로 활용
        api_response = self.post_page(api_url, data=data)
        return self.parse_list_page(api_response.text)
    
    def parse_list_page(self, html_content: str) -> list:
        """AJAX 응답 HTML 파싱"""
        # 나머지는 일반적인 테이블 파싱과 동일
        soup = BeautifulSoup(html_content, 'html.parser')
        # ... 테이블 파싱 로직
```

### 8. 주요 개발 인사이트

#### 8.1 인코딩 처리
웹 스크래핑 시 인코딩 문제는 매우 흔합니다. 특히 한국 사이트들은 다양한 인코딩을 사용합니다:

1. **페이지 인코딩**:
   - UTF-8이 기본이지만, 일부 사이트는 EUC-KR 사용
   - `response.encoding` 설정으로 해결
   ```python
   response = self.session.get(url)
   response.encoding = 'euc-kr'  # 또는 'utf-8'
   ```

2. **파일명 인코딩**:
   - Content-Disposition 헤더의 파일명이 잘못 인코딩된 경우가 많음
   - latin-1로 디코딩 후 실제 인코딩으로 재디코딩 필요
   ```python
   filename = filename.encode('latin-1').decode('euc-kr')
   ```

3. **RFC 5987 형식 처리**:
   - 최신 표준은 `filename*=UTF-8''%ED%95%9C%EA%B8%80.hwp` 형식
   - 인코딩과 파일명을 분리하여 처리 필요

#### 7.2 파일 다운로드 패턴
각 사이트마다 다른 파일 다운로드 방식을 사용합니다:

1. **직접 링크 방식**: 
   - 가장 단순, href 속성에 파일 URL 포함

2. **JavaScript 함수 방식**:
   - `onclick="download('file_id')"` 형태
   - 정규표현식으로 파라미터 추출 필요

3. **UUID/ID 기반 방식**:
   - CCEI처럼 파일 정보가 별도 API나 목록에 포함
   - 파일 UUID로 다운로드 URL 구성

4. **세션 기반 방식**:
   - MIRE처럼 PHP 세션 ID가 필요한 경우
   - 초기 접속 시 세션 ID 획득 후 재사용

#### 7.3 AJAX/JSON API 처리
동적 사이트 증가로 AJAX 처리가 중요해졌습니다:

1. **API 엔드포인트 찾기**:
   - 브라우저 개발자 도구의 Network 탭 활용
   - XHR/Fetch 요청 확인

2. **데이터 캐싱**:
   - CCEI처럼 목록 API에 상세 정보가 포함된 경우
   - 리스트 데이터를 캐시하여 재사용

3. **POST 요청 처리**:
   - 필요한 파라미터 확인
   - CSRF 토큰 등 보안 요소 처리

#### 7.4 에러 처리 및 복원력
안정적인 스크래퍼를 위한 필수 요소:

1. **SSL 인증서 문제**:
   - `verify=False` 옵션 사용 (보안상 주의 필요)
   - 특히 정부/공공기관 사이트에서 흔함

2. **동적 세션 관리**:
   - 세션이 만료되는 경우 자동 재획득
   - 쿠키 저장 및 재사용

3. **다단계 폴백**:
   - 파일명 인코딩 시도: EUC-KR → UTF-8 → 원본
   - 본문 추출 시도: 특정 클래스 → 대체 선택자 → 텍스트 길이 기반

4. **메타데이터 보존**:
   - 파일명을 알 수 없는 경우 임시 파일명 사용
   - UUID나 인덱스 기반 파일명 생성

#### 7.5 성능 최적화
대량 스크래핑 시 고려사항:

1. **요청 간격 조절**:
   - `time.sleep(1)` 등으로 서버 부하 방지
   - 페이지별로 다른 대기 시간 설정

2. **스트리밍 다운로드**:
   - 대용량 파일은 청크 단위로 다운로드
   - 메모리 효율성 향상

3. **병렬 처리 고려**:
   - 여러 파일 동시 다운로드 (서버 정책 확인 필요)
   - 비동기 처리 도입 가능

#### 7.6 디버깅 팁
문제 발생 시 효과적인 디버깅 방법:

1. **단계별 테스트**:
   - 목록 파싱 → 상세 페이지 접근 → 파일 다운로드 순서로 테스트
   - 각 단계별 출력 확인

2. **HTML 저장**:
   - 문제가 되는 페이지의 HTML을 파일로 저장
   - 오프라인에서 파싱 로직 테스트

3. **헤더 분석**:
   - Response 헤더 확인 (특히 Content-Type, Content-Disposition)
   - Request 헤더 조정 (User-Agent, Referer 등)

4. **인코딩 테스트**:
   - `chardet` 라이브러리로 인코딩 자동 감지
   - 다양한 인코딩 조합 시도

# pip install  대신에 uv add를 사용할 것.

# robots.txt는 무시할 것.

## 9. 새로운 사이트 추가 시 실전 개발 프로세스

### 9.1 개발 단계별 체크리스트

#### 1단계: 사이트 분석 및 기본 구조 파악
```bash
# Playwright로 사이트 구조 분석
python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto('사이트URL')
    input('Press Enter after analysis...')
    browser.close()
"
```

**체크 포인트**:
- [ ] 목록 페이지 테이블/리스트 구조 확인
- [ ] 페이지네이션 방식 확인 (GET/POST/JavaScript)
- [ ] 상세 페이지 링크 패턴 확인
- [ ] 첨부파일 다운로드 링크 패턴 확인
- [ ] SSL 인증서 상태 확인
- [ ] 인코딩 방식 확인 (UTF-8/EUC-KR)

#### 2단계: Enhanced 스크래퍼 개발
```python
# enhanced_{사이트명}_scraper.py 파일 생성
from enhanced_base_scraper import StandardTableScraper

class Enhanced{사이트명}Scraper(StandardTableScraper):
    """사이트명 전용 스크래퍼 - 향상된 버전"""
    
    def __init__(self):
        super().__init__()
        # 기본 설정
        self.base_url = "https://example.com"
        self.list_url = "https://example.com/board/list"
        
        # 사이트별 특화 설정
        self.verify_ssl = True/False
        self.default_encoding = 'utf-8'/'euc-kr'
        self.timeout = 30/60
        self.delay_between_requests = 1/2
```

**필수 구현 메소드**:
- [ ] `get_list_url()` - 페이지네이션 URL 생성
- [ ] `parse_list_page()` - 목록 페이지 파싱
- [ ] `parse_detail_page()` - 상세 페이지 파싱
- [ ] `_extract_attachments()` - 첨부파일 추출
- [ ] `download_file()` - 파일 다운로드 (필요시 오버라이드)

#### 3단계: 테스트 스크립트 작성
```python
# test_enhanced_{사이트명}.py 파일 생성
def test_{사이트명}_scraper(pages=3):  # 기본값 3페이지
    """사이트명 스크래퍼 테스트"""
    scraper = Enhanced{사이트명}Scraper()
    output_dir = "output/{사이트명}"  # 표준 출력 디렉토리
    os.makedirs(output_dir, exist_ok=True)
    scraper.scrape_pages(max_pages=pages, output_base=output_dir)

def verify_results(output_dir):
    """결과 검증 - 첨부파일 검증 필수"""
    # 1. 공고 수 확인
    # 2. 첨부파일 다운로드 상태 확인
    # 3. 한글 파일명 처리 확인
    # 4. 원본 URL 포함 확인
    # 5. 성공률 계산
```

#### 4단계: 단계별 테스트 실행
```bash
# 1. 단일 페이지 테스트
python test_enhanced_{사이트명}.py --single

# 2. 3페이지 테스트
python test_enhanced_{사이트명}.py --pages 3

# 3. 결과 확인
ls -la output/{사이트명}/
find output/{사이트명} -name "*.pdf" -o -name "*.hwp" | wc -l
```

#### 5단계: 개발 인사이트 문서 작성
```bash
# {사이트명}_code.txt 파일 생성
```

**문서 포함 내용**:
- [ ] 사이트 특성 분석 (URL, 구조, 인코딩)
- [ ] 기술적 구현 특징 (코드 예시 포함)
- [ ] 주요 해결책 (인코딩, 파일다운로드, 특수 처리)
- [ ] 테스트 결과 (성공률, 파일 통계)
- [ ] 재사용 가능한 패턴
- [ ] 특별한 기술적 도전과 해결책

### 9.2 일반적인 개발 패턴별 대응책

#### 표준 HTML 테이블 기반 사이트 (JBBA, BUSANIT 타입)
```python
def parse_list_page(self, html_content: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html_content, 'html.parser')
    table = soup.find('table')
    tbody = table.find('tbody') or table
    
    for row in tbody.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) < 3:  # 최소 필드 확인
            continue
        
        # 제목 셀 (보통 두 번째)
        title_cell = cells[1]
        link_elem = title_cell.find('a')
        
        if link_elem:
            title = link_elem.get_text(strip=True)
            href = link_elem.get('href', '')
            detail_url = urljoin(self.base_url, href)
```

**적용 사이트**: 대부분의 정부기관, 공공기관 게시판

#### JavaScript 기반 동적 사이트 (KIDP, GSIF 타입)
```python
def get_list_url(self, page_num: int) -> str:
    if page_num == 1:
        return self.list_url
    else:
        # JavaScript 함수 파라미터 분석 후 URL 구성
        params = self._build_page_params(page_num)
        return f"{self.base_url}/api/list?{params}"

def _extract_attachments(self, soup: BeautifulSoup) -> list:
    # JavaScript 함수에서 파일 ID 추출
    onclick_pattern = r"download\('([^']+)'\)"
    for link in soup.find_all('a', onclick=re.compile(onclick_pattern)):
        match = re.search(onclick_pattern, link.get('onclick', ''))
        if match:
            file_id = match.group(1)
            file_url = f"{self.base_url}/download?id={file_id}"
```

**적용 사이트**: 최신 기술 스택을 사용하는 사이트

#### AJAX/JSON API 기반 사이트 (CCEI 타입)
```python
def fetch_announcements_api(self, page_num: int) -> dict:
    api_url = f"{self.base_url}/api/announcements"
    payload = {
        'page': page_num,
        'size': 20,
        'boardType': 'notice'
    }
    
    response = self.session.post(api_url, json=payload)
    return response.json()

def parse_api_response(self, api_data: dict) -> list:
    announcements = []
    for item in api_data.get('data', []):
        announcement = {
            'title': item.get('title'),
            'url': f"{self.base_url}/view/{item.get('id')}",
            'attachments': item.get('files', [])  # API에 첨부파일 정보 포함
        }
        announcements.append(announcement)
    return announcements
```

**적용 사이트**: 최신 웹 애플리케이션, SPA 기반 사이트

### 9.3 한글 파일명 처리 표준 패턴

#### 다단계 인코딩 처리 패턴
```python
def _extract_filename_from_response(self, response, default_path):
    content_disposition = response.headers.get('Content-Disposition', '')
    
    if content_disposition:
        # 1. RFC 5987 형식 우선 처리
        rfc5987_match = re.search(r"filename\*=([^']*)'([^']*)'(.+)", content_disposition)
        if rfc5987_match:
            encoding, lang, filename = rfc5987_match.groups()
            try:
                filename = unquote(filename, encoding=encoding or 'utf-8')
                return os.path.join(save_dir, self.sanitize_filename(filename))
            except:
                pass
        
        # 2. 일반 filename 파라미터 처리
        filename_match = re.search(r'filename[^;=\n]*=([\'"]*)(.*?)\1', content_disposition)
        if filename_match:
            filename = filename_match.group(2)
            
            # 3. 다양한 인코딩 시도
            for encoding in ['utf-8', 'euc-kr', 'cp949']:
                try:
                    if encoding == 'utf-8':
                        decoded = filename.encode('latin-1').decode('utf-8')
                    else:
                        decoded = filename.encode('latin-1').decode(encoding)
                    
                    if decoded and not decoded.isspace():
                        clean_filename = self.sanitize_filename(decoded.replace('+', ' '))
                        return os.path.join(save_dir, clean_filename)
                except:
                    continue
    
    return default_path
```

### 9.4 새로운 사이트 추가 시 실전 개발 프로세스에 대한 상세한 가이드라인을 정리했습니다.
- 다양한 사이트 유형에 대한 스크래핑 패턴을 제공합니다.
- 인코딩, 파일명 처리 등 실무에서 중요한 기술적 노하우를 포함했습니다.

# pip install  대신에 uv add를 사용할 것.

# robots.txt는 무시할 것.

## 10. 상공회의소(CCI) 스크래퍼 공지 공고 포함 수집 가이드

### 10.1 문제 상황
기존 상공회의소 스크래퍼들은 "공지" 표시가 있는 상단 고정 공고들을 제외하고 번호가 붙은 일반 공고만 수집하는 문제가 있었습니다.

**문제점**:
- 게시판 상단의 중요한 "공지" 공고들이 수집되지 않음
- 번호가 없는 공고들이 필터링되어 누락됨
- 실제 수집 공고 수가 예상보다 적음

### 10.2 해결 방안 (양산상공회의소 기준)

#### 10.2.1 공지 이미지 인식 로직 추가

**HTML 파싱 버전 (BeautifulSoup)**:
```python
# 번호 (첫 번째 셀) - "공지" 이미지 처리
number_cell = cells[0]
number = number_cell.get_text(strip=True)

# 공지 이미지 확인
notice_img = number_cell.find_all('img')
is_notice = False

if notice_img:
    for img in notice_img:
        src = img.get('src', '')
        alt = img.get('alt', '')
        if '공지' in src or '공지' in alt or 'notice' in src.lower():
            is_notice = True
            number = "공지"
            break

# 공지인 경우 번호를 "공지"로 설정
if is_notice:
    number = "공지"
elif not number:
    # 번호도 없고 공지도 아닌 경우, 행 인덱스를 번호로 사용
    number = f"row_{len(announcements)+1}"
```

**Playwright 버전 (JavaScript 렌더링)**:
```python
# 번호 (공지 이미지 포함 처리)
number_cell = cells[0]
number = number_cell.inner_text().strip()

# 공지 이미지 확인
notice_img = number_cell.locator('img').all()
is_notice = False

if notice_img:
    for img in notice_img:
        src = img.get_attribute('src') or ''
        alt = img.get_attribute('alt') or ''
        if '공지' in src or '공지' in alt or 'notice' in src.lower():
            is_notice = True
            number = "공지"
            break

# 공지인 경우 번호를 "공지"로 설정
if is_notice:
    number = "공지"
elif not number:
    number = f"row_{i}"
```

#### 10.2.2 유효성 검사 완화

**기존 (문제있는) 코드**:
```python
# 이 조건으로 인해 공지 공고들이 제외됨
if not number or (number.isdigit() == False and number != "공지"):
    continue
```

**수정된 (올바른) 코드**:
```python
# 모든 행을 처리하도록 유효성 검사 완화
# (번호가 있거나, 공지이거나, 임시 번호가 있으면 처리)
# 별도 continue 조건 제거하여 모든 공고 처리
```

#### 10.2.3 로그 출력 개선

```python
# 공고 유형을 명확히 표시
logger.info(f"공고 추가: [{number}] {title}")

# 결과 예시:
# 공고 추가: [공지] 양산상공회의소 공식 인스타그램·카카오톡 채널 개설 안내
# 공고 추가: [415] 2025년 연중모금캠페인 희망나눔 착착착 나눔캠페인 성금 모금
```

### 10.3 적용 대상 스크래퍼 목록

다음 상공회의소 스크래퍼들에 동일한 수정사항을 적용해야 합니다:

1. **yongincci** - 용인상공회의소
2. **jinjucci** - 진주상공회의소  
3. **tongyeongcci** - 통영상공회의소
4. **sacheoncci** - 사천상공회의소
5. **changwoncci** - 창원상공회의소
6. **yangsancci** - 양산상공회의소 ✅ (완료)

### 10.4 수정 작업 체크리스트

각 CCI 스크래퍼별로 다음 항목들을 확인하고 수정:

#### ✅ 필수 수정사항
- [ ] **공지 이미지 인식 로직** 추가 (HTML 파싱 버전)
- [ ] **공지 이미지 인식 로직** 추가 (Playwright 버전)
- [ ] **유효성 검사 완화** (모든 공고 처리하도록)
- [ ] **임시 번호 부여** 로직 추가
- [ ] **로그 출력 개선** (공고 유형 표시)

#### ✅ 테스트 항목
- [ ] **1페이지 테스트**: 공지 공고 포함 15개 모두 수집되는지 확인
- [ ] **3페이지 테스트**: 페이지네이션 정상 작동 및 전체 45개 수집 확인
- [ ] **첨부파일 다운로드**: 공지 공고의 첨부파일도 정상 다운로드되는지 확인
- [ ] **파일명 처리**: 한글 파일명 및 특수문자 정상 처리 확인

#### ✅ 검증 기준
- **수집 공고 수**: 페이지당 15개 (공지 ~10개 + 번호 공고 ~5개)
- **성공률**: 100% (모든 공고 정상 처리)
- **파일 다운로드**: 첨부파일 무결성 확인
- **하위 호환성**: 기존 기능 정상 작동 확인

### 10.5 표준 코드 템플릿

#### 10.5.1 공지 처리 함수 (공통)

```python
def _process_notice_detection(self, cell, row_index=0):
    """공지 이미지 감지 및 번호 처리 - 모든 CCI에서 재사용 가능"""
    number = cell.get_text(strip=True) if hasattr(cell, 'get_text') else cell.inner_text().strip()
    is_notice = False
    
    # 이미지 찾기 (BeautifulSoup vs Playwright)
    if hasattr(cell, 'find_all'):  # BeautifulSoup
        notice_imgs = cell.find_all('img')
        for img in notice_imgs:
            src = img.get('src', '')
            alt = img.get('alt', '')
            if '공지' in src or '공지' in alt or 'notice' in src.lower():
                is_notice = True
                break
    else:  # Playwright
        notice_imgs = cell.locator('img').all()
        for img in notice_imgs:
            src = img.get_attribute('src') or ''
            alt = img.get_attribute('alt') or ''
            if '공지' in src or '공지' in alt or 'notice' in src.lower():
                is_notice = True
                break
    
    # 번호 결정
    if is_notice:
        return "공지"
    elif not number:
        return f"row_{row_index}"
    else:
        return number
```

#### 10.5.2 수정 전후 비교 예시

**수정 전 (문제)**:
```python
# 기존 코드 - 공지 공고 제외됨
if not number or (number.isdigit() == False and number != "공지"):
    continue  # 공지 공고들이 여기서 제외

# 결과: 페이지당 5개만 수집 (공지 10개 누락)
```

**수정 후 (해결)**:
```python
# 수정된 코드 - 모든 공고 포함
number = self._process_notice_detection(cells[0], i)
# 별도 continue 조건 제거

# 결과: 페이지당 15개 모두 수집 (공지 10개 + 번호 5개)
```

### 10.6 테스트 스크립트 템플릿

```python
def test_cci_notice_collection(site_code, pages=3):
    """CCI 사이트 공지 포함 수집 테스트"""
    # 예: test_cci_notice_collection('yongincci', 3)
    
    scraper_class = f"Enhanced{site_code.capitalize()}Scraper"
    output_dir = f"output/{site_code}_notice_test"
    
    # 테스트 실행
    scraper = globals()[scraper_class]()
    scraper.scrape_pages(max_pages=pages, output_base=output_dir)
    
    # 결과 검증
    total_announcements = len([f for f in os.listdir(output_dir) if os.path.isdir(os.path.join(output_dir, f))])
    expected = pages * 15  # 페이지당 15개 예상
    
    print(f"✅ {site_code} 테스트 결과:")
    print(f"   수집 공고: {total_announcements}개 / 예상: {expected}개")
    print(f"   성공률: {(total_announcements/expected)*100:.1f}%")
```

### 10.7 우선순위

1. **높음**: yongincci, changwoncci (많이 사용되는 스크래퍼)
2. **중간**: jinjucci, tongyeongcci, sacheoncci
3. **참고**: yangsancci (이미 완료됨 - 참고용)

이 가이드를 따라 모든 CCI 스크래퍼를 수정하면 공지 공고를 포함한 완전한 수집이 가능해집니다.

## 11. Enhanced Base Scraper 수정 시 하위 호환성 보장 원칙

### ⚠️ **극히 중요: 절대 지켜야 할 원칙**

Enhanced Base Scraper(`enhanced_base_scraper.py`)는 **수백 개의 스크래퍼 클래스들이 상속**하고 있습니다. 
기본 클래스를 수정할 때는 **하위 호환성(Backward Compatibility)**을 반드시 보장해야 합니다.

### 11.1 절대 하지 말아야 할 수정 (❌ 금지)

#### ❌ 메서드 시그니처 변경
```python
# 절대 금지 - 기존 자식 클래스들이 모두 오류 발생
def parse_list_page(self, html_content: str, page_num: int) -> List[Dict]:  # ❌
def parse_detail_page(self, html_content: str, extra_param: str) -> Dict:   # ❌
def get_list_url(self, page_num: int, category: str) -> str:                # ❌
```

#### ❌ 추상 메서드 추가
```python
# 절대 금지 - 기존 자식 클래스들에서 구현되지 않아 오류
@abstractmethod
def new_required_method(self):  # ❌
    pass
```

#### ❌ 필수 속성 추가
```python
# 절대 금지 - 기존 자식 클래스들이 속성을 설정하지 않아 오류
def __init__(self):
    self.required_new_attribute = None  # ❌ 기존 클래스에서 오류
```

#### ❌ 기존 메서드 제거
```python
# 절대 금지 - 기존 자식 클래스들이 호출하던 메서드 삭제
# def old_method(self):  # ❌ 삭제하면 모든 자식 클래스 오류
#     pass
```

### 11.2 안전한 수정 방법 (✅ 허용)

#### ✅ 새로운 선택적 속성 추가
```python
def __init__(self):
    # 기존 속성들...
    
    # 새로운 속성 - 기본값 제공으로 하위 호환성 보장
    self.new_optional_attribute = None  # ✅ 안전
    self.current_page_num = 1          # ✅ 안전 (기본값 있음)
```

#### ✅ 새로운 선택적 메서드 추가
```python
def new_optional_method(self, param=None):
    """새로운 기능 - 선택적 사용"""
    # 기본 구현 제공
    return param

def enhanced_feature(self):
    """향상된 기능 - 기존 클래스는 사용하지 않아도 됨"""
    if hasattr(self, 'supports_enhanced_feature'):
        return self.supports_enhanced_feature
    return False  # 기본값
```

#### ✅ 기존 메서드 내부 로직 개선
```python
def existing_method(self, html_content: str) -> List[Dict]:
    """기존 메서드 시그니처 유지하면서 내부 로직만 개선"""
    # 새로운 속성이 있으면 활용, 없으면 기존 방식
    page_num = getattr(self, 'current_page_num', 1)  # ✅ 안전
    
    # 기존 로직 개선
    return self._enhanced_parsing(html_content, page_num)
```

#### ✅ 기존 메서드에 기본값 매개변수 추가
```python
def existing_method(self, html_content: str, new_param=None):
    """기본값이 있는 새 매개변수 추가는 안전"""
    if new_param is None:
        new_param = "default_value"
    # 로직 처리...
```

### 11.3 실제 적용 사례: 페이지네이션 지원

#### ❌ 잘못된 접근 (하위 호환성 파괴)
```python
# 이렇게 하면 수백 개 클래스 모두 수정 필요
@abstractmethod
def parse_list_page(self, html_content: str, page_num: int):  # ❌
    pass
```

#### ✅ 올바른 접근 (하위 호환성 보장)
```python
class EnhancedBaseScraper:
    def __init__(self):
        # 새로운 속성 추가 (기본값 제공)
        self.current_page_num = 1  # ✅ 안전

    def _get_page_announcements(self, page_num: int):
        # 인스턴스 변수에 페이지 번호 저장
        self.current_page_num = page_num  # ✅ 안전
        
        # 기존 시그니처 유지
        return self.parse_list_page(html_content)  # ✅ 안전

    @abstractmethod
    def parse_list_page(self, html_content: str):  # ✅ 시그니처 유지
        pass
```

#### ✅ 자식 클래스에서 활용
```python
class ChildScraper(EnhancedBaseScraper):
    def parse_list_page(self, html_content: str):
        # 새로운 속성 안전하게 사용
        page_num = getattr(self, 'current_page_num', 1)  # ✅ 안전
        
        if page_num > 1:
            # 페이지별 특별 처리
            pass
        
        # 기존 로직...
```

### 11.4 수정 전 필수 체크리스트

Base Scraper 수정 전에 반드시 확인:

#### ✅ 하위 호환성 체크
- [ ] 기존 메서드 시그니처가 변경되지 않았는가?
- [ ] 새로운 필수 매개변수가 추가되지 않았는가?
- [ ] 새로운 추상 메서드가 추가되지 않았는가?
- [ ] 기존 메서드가 삭제되지 않았는가?
- [ ] 새로운 필수 속성이 기본값 없이 추가되지 않았는가?

#### ✅ 기존 스크래퍼 테스트
```python
# 수정 후 반드시 기존 스크래퍼 테스트
def test_backward_compatibility():
    """기존 스크래퍼들이 여전히 작동하는지 확인"""
    test_scrapers = ['yongincci', 'changwoncci', 'btp', 'itp']
    
    for scraper_name in test_scrapers:
        try:
            # 기존 스크래퍼 인스턴스 생성 테스트
            scraper = create_scraper(scraper_name)
            scraper.scrape_pages(max_pages=1)
            print(f"✅ {scraper_name}: 정상 작동")
        except Exception as e:
            print(f"❌ {scraper_name}: 오류 발생 - {e}")
            raise  # 즉시 중단
```

### 11.5 안전한 Base Scraper 진화 전략

#### 1단계: 새로운 기능을 선택적으로 추가
```python
def __init__(self):
    # 기존 코드...
    self.supports_new_feature = False  # 기본적으로 비활성화
```

#### 2단계: 기존 메서드에서 새 기능 지원 감지
```python
def existing_method(self, html_content):
    if getattr(self, 'supports_new_feature', False):
        return self._new_enhanced_logic(html_content)
    else:
        return self._legacy_logic(html_content)  # 기존 방식 유지
```

#### 3단계: 자식 클래스에서 선택적 활성화
```python
class ModernScraper(EnhancedBaseScraper):
    def __init__(self):
        super().__init__()
        self.supports_new_feature = True  # 새 기능 활성화
```

### 11.6 비상 복구 계획

만약 실수로 하위 호환성을 깨뜨렸다면:

#### 즉시 롤백 절차
1. **즉시 git revert** 실행
2. **모든 영향받는 스크래퍼 목록** 작성
3. **수정 방법 재검토** 후 안전한 방식으로 재구현
4. **광범위한 테스트** 후 재배포

#### 영향 범위 확인
```bash
# Base Scraper를 상속하는 모든 클래스 찾기
grep -r "EnhancedBaseScraper\|StandardTableScraper" --include="*.py" .

# 영향받는 스크래퍼 개수 확인
find . -name "*_scraper.py" | wc -l
```

### 11.7 결론

**Enhanced Base Scraper는 생태계의 핵심**입니다. 
수백 개의 스크래퍼가 의존하고 있기 때문에 **극도로 신중하게** 수정해야 합니다.

**원칙**: 
- 🟢 **기능 추가**: 항상 선택적이고 기본값 제공
- 🔴 **기존 변경**: 절대 금지
- 🟡 **내부 개선**: 외부 인터페이스 유지하면서만

**기억하세요**: "한 번의 잘못된 Base Scraper 수정이 수백 개 스크래퍼를 망가뜨릴 수 있습니다!"

## 12. 새로운 메모리

- 스크래퍼 개발 시 robots.txt는 무시하고 진행한다.