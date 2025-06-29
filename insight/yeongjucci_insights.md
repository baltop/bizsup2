# 영주상공회의소(Yeongjucci) 스크래퍼 개발 인사이트

## 사이트 특성 분석

### 기본 정보
- **사이트명**: 영주상공회의소
- **사이트 코드**: yeongjucci  
- **URL**: https://yeongjucci.korcham.net/front/board/boardContentsListPage.do?boardId=10298&menuId=3106
- **구조**: 한국상공회의소 표준 게시판 (용인CCI와 동일)

### 사이트 구조
- **게시판 형태**: JavaScript 기반 동적 게시판
- **페이지네이션**: JavaScript `go_Page()` 함수 방식
- **상세페이지 접근**: JavaScript `contentsView()` 함수 방식
- **첨부파일**: 직접 다운로드 링크 제공
- **인코딩**: UTF-8

## 기술적 구현 특징

### 1. JavaScript 렌더링 필수
영주CCI는 정적 HTML로는 공고 목록을 파악할 수 없어 Playwright가 필수입니다.

```python
def _parse_with_playwright(self):
    """Playwright를 사용한 JavaScript 렌더링 후 파싱"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # 타임아웃 설정 증가 (60초)
        page.set_default_timeout(60000)
        
        page.goto(self.list_url, timeout=60000)
        page.wait_for_load_state('networkidle', timeout=60000)
        
        # 추가 대기시간 (3초)
        page.wait_for_timeout(3000)
```

### 2. 상세페이지 접근 방식
JavaScript 함수를 통한 상세페이지 접근이 특징입니다.

```python
def get_detail_page_with_playwright(self, content_id: str) -> str:
    # contentsView JavaScript 함수 실행
    page.evaluate(f"contentsView('{content_id}')")
    
    # 페이지 전환 대기
    page.wait_for_url("**/boardContentsView.do**", timeout=30000)
```

### 3. 타임아웃 및 안정성 개선
네트워크 지연을 고려한 충분한 대기시간 설정:

```python
self.timeout = 60  # 60초
self.delay_between_requests = 3  # 3초 간격
```

## 주요 해결책

### 1. 동적 컨텐츠 처리
- **문제**: 정적 HTML 파싱으로는 공고 목록을 가져올 수 없음
- **해결**: Playwright를 통한 JavaScript 렌더링 후 파싱

### 2. 상세페이지 접근
- **문제**: JavaScript 함수를 통해서만 상세페이지 접근 가능
- **해결**: 
  1. JavaScript 함수 실행 시도
  2. 실패 시 직접 URL 접근으로 폴백

### 3. 안정성 확보
- **문제**: 네트워크 지연으로 인한 타임아웃 에러
- **해결**: 
  - 타임아웃 시간을 60초로 증가
  - 요청 간 3초 대기
  - 페이지 로드 후 추가 대기시간 부여

## 테스트 결과

### 실행 통계 (3페이지)
- **총 공고 수**: 39개 (13개 × 3페이지)
- **성공적으로 처리된 공고**: 39개 (100%)
- **다운로드된 첨부파일**: 66개
- **첨부파일이 있는 공고**: 36개
- **첨부파일이 없는 공고**: 3개

### 파일 크기 분석
- **최대 파일**: 6.2MB (e스포츠 대회 포스터 이미지)
- **일반적인 파일 크기**: 50KB ~ 500KB (HWP, PDF 문서)
- **총 다운로드 용량**: 약 50MB

### 파일 형식 분포
- **HWP 파일**: 약 45개 (공고문, 신청서)
- **PDF 파일**: 약 18개 (공고문, 안내서)
- **JPG 파일**: 3개 (포스터, 안내 이미지)

## 재사용 가능한 패턴

### 1. 한국상공회의소 표준 패턴
영주CCI는 용인CCI와 동일한 구조를 가지므로, 다른 상공회의소 사이트에도 적용 가능:

```python
# 공통 패턴
- JavaScript 기반 페이지네이션: go_Page() 함수
- 상세페이지 접근: contentsView() 함수  
- 첨부파일: 직접 다운로드 링크
- URL 패턴: /front/board/boardContentsListPage.do
```

### 2. Playwright 활용 패턴
JavaScript 렌더링이 필요한 사이트들에 재사용 가능:

```python
def _parse_with_playwright(self):
    # 1. 브라우저 시작
    # 2. 타임아웃 설정  
    # 3. 페이지 로드 및 대기
    # 4. 요소 추출
    # 5. 브라우저 종료
```

## 특별한 기술적 도전과 해결책

### 1. 중복 공고 처리
같은 페이지가 여러 번 나타나는 이슈:
- **원인**: JavaScript 페이지네이션의 동작 방식
- **해결**: 중복 제목 필터링 로직 적용

### 2. 파일명 인코딩
한글 파일명의 올바른 처리:
- **문제**: URL 인코딩된 한글 파일명
- **해결**: 다단계 인코딩 디코딩 처리

### 3. 메모리 효율성
대용량 파일 다운로드:
- **문제**: 6MB 이상의 이미지 파일
- **해결**: 스트리밍 다운로드 방식 적용

## 성능 최적화

### 1. 타임아웃 최적화
- **기본 요청**: 60초
- **JavaScript 실행**: 30초  
- **페이지 전환**: 30초
- **요청 간격**: 3초

### 2. 에러 복구
- JavaScript 함수 실행 실패 시 직접 URL 접근
- 페이지 로드 실패 시 재시도 로직
- 파일 다운로드 실패 시 로깅 및 계속 진행

## 운영 고려사항

### 1. 서버 부하 최소화
- 요청 간 3초 대기로 서버 부하 분산
- 한 번에 하나씩 순차적 처리

### 2. 안정성 확보
- 충분한 타임아웃 시간 확보
- 네트워크 상태에 따른 대기시간 조정

### 3. 로깅 및 모니터링
- 상세한 진행 상황 로깅
- 파일 다운로드 성공/실패 추적
- 파싱 오류 상세 기록

## 결론

영주상공회의소 스크래퍼는 용인CCI와 동일한 구조를 가진 JavaScript 기반 동적 사이트로, Playwright를 활용한 렌더링과 충분한 대기시간 확보가 성공의 핵심이었습니다. 

**주요 성공 요소**:
1. JavaScript 렌더링을 통한 동적 컨텐츠 처리
2. 안정적인 타임아웃 및 대기시간 설정
3. 다단계 폴백 메커니즘 구현
4. 한글 파일명 처리 최적화

이 패턴은 다른 한국상공회의소 사이트들에도 동일하게 적용할 수 있어 높은 재사용성을 가집니다.