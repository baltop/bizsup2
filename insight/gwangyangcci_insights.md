# Gwangyangcci (광양상공회의소) 스크래퍼 개발 인사이트

## 사이트 기본 정보
- **사이트명**: 광양상공회의소
- **URL**: https://gwangyangcci.korcham.net/front/board/boardContentsListPage.do?boardId=10836&menuId=2059
- **사이트 코드**: gwangyangcci
- **구조**: 대한상공회의소 표준 플랫폼 (GECCI, Gimhaecci와 동일)

## 기술적 특징

### 1. 사이트 구조
- **플랫폼**: 대한상공회의소 표준 웹 플랫폼
- **JavaScript 의존성**: 높음 (동적 로딩 필요)
- **SSL 지원**: HTTPS 지원
- **인코딩**: UTF-8

### 2. 페이지네이션
- **방식**: JavaScript 기반 go_Page() 함수
- **URL 패턴**: `&page={page_num}` 파라미터 추가
- **구현**: `get_list_url()` 메소드에서 처리

### 3. 상세 페이지 접근
- **방식**: JavaScript 함수 `contentsView('ID')` 호출
- **구현**: Playwright를 사용한 동적 실행
- **폴백**: 직접 URL 접근 (`boardContentsView.do?contentsId={id}`)

## 개발 구현 사항

### 1. 스크래퍼 클래스 구조
```python
class EnhancedGwangyangcciScraper(StandardTableScraper):
    def __init__(self):
        self.base_url = "https://gwangyangcci.korcham.net"
        self.verify_ssl = True
        self.delay_between_requests = 1  # 빠른 실행
```

### 2. 핵심 기능
- **목록 파싱**: BeautifulSoup + Playwright 폴백
- **상세 페이지**: Playwright 필수 (JavaScript 실행)
- **첨부파일**: 표준 테이블 구조에서 추출
- **콘텐츠 추출**: 마크다운 변환

### 3. 성능 최적화
- **지연 시간**: 1초로 설정 (서버 부하 고려)
- **SSL 검증**: 활성화
- **타임아웃**: 30초
- **인코딩**: UTF-8 기본

## 스크래핑 결과

### 테스트 통계 (3페이지)
- **총 공고 수**: 38개
- **내용 파일**: 37개
- **첨부파일**: 56개
- **총 파일 크기**: 47.2 MB
- **성공률**: 97.3% (37/38)

### 파일 형식 분포
- **HWP 파일**: 주요 한글 문서
- **PDF 파일**: 공식 문서, 지침서
- **DOC/DOCX**: MS Word 문서
- **XLSX**: 엑셀 신청서
- **PPTX**: 프레젠테이션
- **JPG**: 이미지 파일

### 대용량 파일
- **2025년 청년일자리도약장려금 사업운영 지침.pdf**: 7.5MB
- **온라인 법정의무교육.hwp**: 5.5MB
- **참가기업 소개서 템플릿.pptx**: 1.1MB

## 기술적 도전과 해결책

### 1. JavaScript 렌더링 문제
**문제**: 정적 HTML 파싱으로는 공고 목록 추출 불가
**해결**: Playwright를 사용한 동적 렌더링 후 파싱

### 2. 상세 페이지 접근
**문제**: `contentsView()` JavaScript 함수로만 접근 가능
**해결**: 
- Playwright에서 JavaScript 함수 직접 실행
- 실패 시 직접 URL 접근으로 폴백

### 3. 첨부파일 다운로드
**특징**: 표준 테이블 구조로 안정적
**구현**: 상세 페이지 테이블에서 `첨부파일` 행 찾기

### 4. 한글 파일명 처리
**문제**: URL 인코딩된 한글 파일명
**해결**: 
- UTF-8 디코딩
- 파일명 정규화
- 특수문자 제거

## 재사용 가능한 패턴

### 1. 대한상공회의소 표준 플랫폼
- GECCI, Gimhaecci, Gwangyangcci 동일 구조
- `contentsView()` JavaScript 함수 표준
- 테이블 기반 첨부파일 구조

### 2. Playwright 통합 패턴
```python
def _parse_with_playwright(self):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(self.list_url)
        page.wait_for_load_state('networkidle')
        # 파싱 로직
```

### 3. 다단계 선택자 전략
```python
selectors = ['tbody tr', 'table tr', 'tr']
for selector in selectors:
    temp_rows = page.locator(selector).all()
    if temp_rows:
        rows = temp_rows
        break
```

## 성능 특성

### 1. 실행 시간
- **3페이지 처리**: 약 5분 (Playwright 오버헤드 포함)
- **페이지당 평균**: 약 1.5분
- **공고당 평균**: 약 8초

### 2. 메모리 사용량
- **Playwright**: 브라우저 인스턴스 메모리
- **파일 버퍼링**: 스트리밍 다운로드로 최적화
- **HTML 파싱**: BeautifulSoup 메모리 효율적

### 3. 네트워크 효율성
- **연결 재사용**: requests.Session 활용
- **적절한 지연**: 서버 부하 방지
- **에러 복구**: 자동 재시도 메커니즘

## 확장 가능성

### 1. 다른 상공회의소 적용
- 동일한 플랫폼을 사용하는 다른 상공회의소에 쉽게 적용
- URL과 ID만 변경하면 재사용 가능

### 2. 추가 기능
- 이메일 알림 기능
- 데이터베이스 저장
- API 서버 통합

### 3. 모니터링
- 성공률 추적
- 파일 크기 통계
- 처리 시간 분석

## 유지보수 고려사항

### 1. 사이트 변경 대응
- JavaScript 함수명 변경 가능성
- 테이블 구조 변경 모니터링
- 선택자 업데이트 필요성

### 2. 성능 최적화
- Playwright 버전 업데이트
- 파일 다운로드 최적화
- 메모리 사용량 모니터링

### 3. 에러 처리
- 네트워크 오류 복구
- JavaScript 실행 실패 대응
- 파일 다운로드 검증

## 결론

Gwangyangcci 스크래퍼는 대한상공회의소 표준 플랫폼의 JavaScript 의존적 구조를 성공적으로 처리하며, 높은 성공률과 안정적인 파일 다운로드를 달성했습니다. Playwright 기반의 동적 렌더링 접근법은 동일한 플랫폼을 사용하는 다른 상공회의소 사이트에도 효과적으로 적용될 수 있습니다.