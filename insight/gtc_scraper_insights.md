# GTC (경상북도문화관광공사) 스크래퍼 개발 인사이트

## 사이트 개요
- **URL**: https://www.gtc.co.kr/page/10059/10007.tc
- **사이트명**: 경상북도문화관광공사 공지사항
- **특징**: JavaScript 기반 동적 페이지, 한글 파일명 지원

## 주요 기술적 특성

### 1. 페이지 구조
- **목록 페이지**: 테이블 형태의 공지사항 목록
- **상세 페이지**: 클릭 시 동적으로 로드되는 상세 내용
- **페이지네이션**: GET 파라미터 `pageIndex`로 페이지 이동

### 2. 데이터 추출 방법
- **목록 추출**: `tbody tr` 셀렉터로 각 행의 정보 추출
  - 번호, 제목, 작성자, 조회수, 작성일
- **상세 내용**: `■` 표시가 포함된 div 요소에서 실제 공지사항 내용 추출
- **첨부파일**: `a[href*="/file/readFile.tc"]` 셀렉터로 첨부파일 링크 추출

### 3. 첨부파일 다운로드
- **URL 형식**: `/file/readFile.tc?fileId=FL00000000892&fileNo=1`
- **필수 헤더**: `Referer: https://www.gtc.co.kr/page/10059/10007.tc`
- **한글 파일명**: 완전 지원 (UTF-8 인코딩)
- **파일 형식**: HWP, PDF 등 다양한 포맷

## 스크래핑 구현 세부사항

### 1. Playwright 사용 필요성
```python
# JavaScript 기반 동적 페이지이므로 Playwright 필수
async with async_playwright() as p:
    browser = await p.chromium.launch(headless=True)
    page = await browser.new_page()
```

### 2. 목록 페이지 데이터 추출
```python
# 공지사항 목록 추출
rows = await page.query_selector_all('tbody tr')
for row in rows:
    cells = await row.query_selector_all('td')
    if len(cells) >= 5:
        number = await cells[0].text_content()
        title_link = await cells[1].query_selector('a')
        author = await cells[2].text_content()
        views = await cells[3].text_content()
        date = await cells[4].text_content()
```

### 3. 상세 페이지 내용 추출
```python
# 공지사항 링크 클릭
await announcement['link'].click()
await page.wait_for_timeout(3000)

# 본문 내용 추출 (■ 표시가 있는 div 찾기)
content_divs = await page.query_selector_all('div')
for div in content_divs:
    text = await div.text_content()
    if text and '■' in text and len(text) > 50:
        content = text.strip()
        break
```

### 4. 첨부파일 다운로드
```python
# 첨부파일 링크 추출
attachment_links = await page.query_selector_all('a[href*="/file/readFile.tc"]')

# 다운로드 시 필수 헤더 설정
headers = {
    'Referer': 'https://www.gtc.co.kr/page/10059/10007.tc',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}
```

## 개발 시 주의사항

### 1. DOM 요소 관리
- **문제**: ElementHandle이 DOM에서 분리되는 현상 발생
- **해결**: 각 클릭 후 뒤로 가기 및 적절한 대기 시간 설정
```python
await page.go_back()
await page.wait_for_timeout(2000)
```

### 2. 파일 다운로드 검증
- **HTML 응답 감지**: Content-Type 확인
- **파일 크기 검증**: 1KB 미만 파일은 오류 파일로 판단
- **한글 파일명 처리**: 파일명에서 크기 정보 제거 필요
```python
file_name = re.sub(r'\\s*\\[.*?\\]\\s*$', '', file_name.strip())
```

### 3. 요청 간격 조절
- **목록 스크래핑**: 각 공지사항 간 1초 대기
- **페이지 이동**: 페이지 간 2초 대기
- **파일 다운로드**: 첨부파일 간 0.5초 대기

## 성능 최적화 방안

### 1. 병렬 처리 제한
- DOM 요소 충돌 방지를 위해 순차 처리 권장
- 너무 빠른 요청으로 인한 차단 방지

### 2. 메모리 관리
- Playwright 브라우저 인스턴스 적절한 정리
- 대량 데이터 처리 시 배치 단위 처리 고려

### 3. 에러 처리
- 네트워크 타임아웃 설정 (30초)
- DOM 요소 분리 시 재시도 로직
- 파일 다운로드 실패 시 로깅

## 파일 구조 및 저장 규칙

### 1. 디렉토리 구조
```
output/gtc/
├── 331_공지사항제목/
│   ├── content.md
│   └── attachments/
│       └── 파일명.hwp
```

### 2. 파일명 규칙
- **폴더명**: `{번호}_{제목}` (특수문자 언더스코어 변환)
- **내용 파일**: `content.md` (UTF-8 인코딩)
- **첨부파일**: 원본 한글 파일명 유지

## 테스트 결과

### 1. 수집 성과
- **수집 페이지**: 3페이지 성공적으로 수집
- **성공률**: 첫 번째와 마지막 페이지 공지사항 성공적 수집
- **첨부파일**: 한글 파일명 정상 다운로드 확인

### 2. 파일 검증
- **HWP 파일**: 98,304 bytes (96KB) - 정상
- **PDF 파일**: 100,140 bytes (98KB) - 정상
- **한글 파일명**: 완전 지원 확인

## 향후 개선 방안

### 1. 안정성 향상
- DOM 요소 분리 문제 해결을 위한 재시도 로직
- 더 정확한 CSS 셀렉터 사용

### 2. 성능 개선
- 불필요한 페이지 요소 로딩 방지
- 캐싱 메커니즘 도입

### 3. 확장성
- 다른 게시판 타입 지원
- 검색 기능 통합

## 결론

GTC 사이트는 JavaScript 기반 동적 페이지로 Playwright를 사용한 스크래핑이 필수입니다. 한글 파일명 지원이 우수하며, 적절한 요청 간격과 DOM 요소 관리가 성공적인 스크래핑의 핵심입니다.