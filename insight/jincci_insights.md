# 진주상공회의소(Jincci) 스크래퍼 개발 인사이트

## 사이트 개요
- **사이트명**: 진주상공회의소 (Jinchu Chamber of Commerce)
- **사이트 코드**: jincci
- **대상 URL**: https://jincci.korcham.net/front/board/boardContentsListPage.do?boardId=10777&menuId=1534
- **플랫폼**: 한국상공회의소 통합 플랫폼 (korcham.net)
- **구조**: 표준 CCI 구조와 동일

## 기술적 특징

### 1. 플랫폼 구조
```python
self.base_url = "https://jincci.korcham.net"
self.list_url = "https://jincci.korcham.net/front/board/boardContentsListPage.do?boardId=10777&menuId=1534"
self.detail_base_url = "https://jincci.korcham.net/front/board/boardContentsView.do"
```

- **통합 플랫폼**: 모든 CCI 사이트가 동일한 korcham.net 플랫폼 사용
- **JavaScript 렌더링**: 동적 콘텐츠로 Playwright 필수
- **표준 URL 패턴**: boardId와 menuId로 구분되는 표준 구조

### 2. JavaScript 기반 네비게이션
```python
# contentsView() 함수로 상세 페이지 접근
onclick = "javascript:contentsView('12345')"
detail_url = f"{self.detail_base_url}?contentsId={content_id}"
```

- **동적 링크**: onclick 이벤트로 JavaScript 함수 호출
- **ID 추출**: 정규표현식으로 contentsView ID 파싱
- **페이지 전환**: JavaScript 함수 실행 후 URL 변경 대기

### 3. Enhanced 타임아웃 설정
```python
self.timeout = 60  # 60초로 증가
self.delay_between_requests = 3  # 3초로 증가
page.set_default_timeout(60000)  # Playwright 60초
page.wait_for_timeout(5000)  # 추가 대기시간 5초
```

- **안정성 우선**: 네트워크 지연을 고려한 충분한 대기시간
- **단계별 대기**: 페이지 로드, 네트워크 대기, 추가 대기의 3단계 구조
- **오류 방지**: 타임아웃 에러를 방지하기 위한 보수적 설정

## 구현 세부사항

### 1. 목록 페이지 파싱
```python
def parse_list_page(self, html_content: str) -> list:
    # 1차: BeautifulSoup으로 정적 HTML 시도
    # 2차: Playwright로 JavaScript 렌더링 처리
    # contentsView ID 추출 후 상세 URL 구성
```

**핵심 로직**:
- 정적 파싱 우선 시도 → 실패 시 Playwright 사용
- JavaScript onclick에서 정규표현식으로 ID 추출
- 다양한 선택자로 안정적인 요소 탐지

### 2. 상세 페이지 처리
```python
def get_detail_page_with_playwright(self, content_id: str) -> str:
    # JavaScript 함수 실행: contentsView(content_id)
    # URL 변경 대기: boardContentsView.do
    # 폴백: 직접 URL 접근
```

**안정성 패턴**:
- JavaScript 함수 실행 → 실패 시 직접 URL 접근
- 페이지 전환 대기 → URL 패턴 매칭
- 콘텐츠 로드 대기 → networkidle 상태 확인

### 3. 첨부파일 처리
```python
def parse_detail_page(self, html_content: str) -> dict:
    # 테이블 구조에서 첨부파일 행 탐지
    # "첨부파일" 텍스트가 포함된 th 요소 찾기
    # 상대 경로를 절대 URL로 변환
```

## 테스트 결과

### 3페이지 테스트 성과
- **총 공고 수**: 18개
- **첨부파일 수**: 57개
- **파일 형식**: PDF 27개, HWP 30개  
- **총 다운로드 크기**: 12MB
- **성공률**: 100% (18/18 공고 처리 성공)
- **평균 첨부파일**: 공고당 3.2개

### 파일 크기 분석
```
📊 중간 규모 데이터 처리: 12.0MB
📈 평균 첨부파일 비율: 316.7% (공고당 3.2개)
📊 평균 파일 크기: 215,544 bytes
```

### 처리 시간 및 안정성
- **페이지당 처리시간**: 약 2-3분 (대기시간 포함)
- **타임아웃 에러**: 0건 (충분한 대기시간으로 해결)
- **파싱 실패**: 0건 (Playwright 안정성)
- **파일 다운로드 실패**: 0건

## 재사용 가능한 패턴

### 1. CCI 사이트 공통 패턴
```python
class EnhancedCciScraper(StandardTableScraper):
    def __init__(self):
        super().__init__()
        self.base_url = "https://{site}cci.korcham.net"
        self.timeout = 60  # CCI 표준 타임아웃
        self.delay_between_requests = 3  # CCI 표준 대기시간
```

### 2. JavaScript 함수 호출 패턴
```python
# contentsView ID 추출
match = re.search(r"contentsView\('(\d+)'\)", onclick)
if match:
    content_id = match.group(1)

# JavaScript 함수 실행
page.evaluate(f"contentsView('{content_id}')")
page.wait_for_url("**/boardContentsView.do**", timeout=30000)
```

### 3. 다단계 폴백 전략
```python
try:
    # 1단계: JavaScript 함수 실행
    page.evaluate(f"contentsView('{content_id}')")
    page.wait_for_url("**/boardContentsView.do**")
except Exception:
    # 2단계: 직접 URL 접근
    direct_url = f"{self.detail_base_url}?contentsId={content_id}"
    page.goto(direct_url)
```

## 성능 최적화 요소

### 1. 메모리 효율성
- Playwright 브라우저 즉시 종료
- 큰 HTML 콘텐츠 처리 후 가비지 컬렉션
- 파일 스트리밍 다운로드

### 2. 네트워크 최적화
- 요청 간 충분한 간격 (3초)
- 재시도 로직으로 일시적 네트워크 오류 대응
- User-Agent 설정으로 차단 방지

### 3. 에러 처리
```python
try:
    # 메인 로직
    html_content = self.get_detail_page_with_playwright(content_id)
except Exception as e:
    logger.error(f"상세 페이지 가져오기 실패: {e}")
    # 기본 콘텐츠로 계속 진행
    detail = {'content': '상세 내용을 가져올 수 없습니다.'}
```

## 개발 시 주의사항

### 1. CCI 플랫폼 공통 이슈
- **JavaScript 의존성**: 모든 CCI 사이트는 JavaScript 렌더링 필수
- **동일한 구조**: boardId와 menuId만 다르고 나머지는 동일
- **타임아웃 민감**: 네트워크 상태에 따라 로딩 시간 편차 큼

### 2. 개발 효율성 팁
- **기존 CCI 스크래퍼 재사용**: yongincci 등 기존 코드 복사 후 URL만 변경
- **테스트 우선**: 1페이지 테스트 후 전체 실행
- **로그 모니터링**: Playwright 로그로 JavaScript 실행 상태 확인

### 3. 안정성 확보 방법
- **충분한 타임아웃**: 60초 이상 권장
- **다단계 대기**: 페이지 로드 → networkidle → 추가 대기
- **폴백 전략**: JavaScript 실패 시 직접 URL 접근

## 결론

Jincci 스크래퍼는 표준 CCI 플랫폼의 전형적인 사례로, JavaScript 렌더링과 동적 네비게이션을 안정적으로 처리하는 패턴을 확립했습니다. 

**핵심 성공 요소**:
1. **충분한 타임아웃**: 60초 설정으로 네트워크 지연 대응
2. **Playwright 활용**: JavaScript 기반 동적 콘텐츠 안정적 처리  
3. **다단계 폴백**: JavaScript 실패 시 직접 접근으로 복원력 확보
4. **표준 패턴 재사용**: 기존 CCI 스크래퍼 구조 활용으로 개발 효율성 극대화

이 패턴은 다른 CCI 사이트 개발 시 그대로 재사용 가능하며, JavaScript 기반 동적 사이트의 범용 솔루션으로 활용할 수 있습니다.