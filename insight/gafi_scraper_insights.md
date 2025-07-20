# GAFI (경기도농수산진흥원) 스크래퍼 개발 인사이트

## 사이트 정보
- **사이트명**: 경기도농수산진흥원 (GAFI)
- **URL**: https://www.gafi.or.kr/web/board/boardContentsListPage.do?board_id=42&menu_id=9d7a4fa3cd784b2ea1ab192315847444
- **사이트 코드**: gafi
- **페이지네이션**: JavaScript 기반 동적 로딩 (go_Page() 함수)

## 주요 기술적 특징

### 1. JavaScript 동적 로딩 사이트
- **핵심 문제**: 게시글 목록이 JavaScript로 동적으로 로드됨
- **초기 requests 접근**: 실패 (테이블 헤더만 존재, 데이터 없음)
- **해결 방안**: Playwright 브라우저 자동화 필수

### 2. 페이지네이션 구조
- **방식**: JavaScript 함수 `go_Page(페이지번호)` 호출
- **Ajax 요청**: POST 방식으로 `/web/board/boardContentsList.do` 호출
- **세션 관리**: JSESSIONID 기반 세션 유지 필수

### 3. HTML 구조 분석
- **목록 테이블**: `table.tstyle_list` 클래스 사용
- **게시글 링크**: `javascript:contentsView('contents_id')` 형태
- **상세 페이지**: `/web/board/boardContentsView.do?contents_id=...` 패턴

### 4. 첨부파일 시스템
- **다운로드 URL**: `/commonfile/fileidDownLoad.do?file_id=파일ID`
- **파일 링크**: `a[href*="fileidDownLoad"]` 선택자로 추출
- **한글 파일명**: 완벽 지원 (UTF-8 인코딩)

## 개발 과정에서 발견한 문제점과 해결방법

### 1. JavaScript 동적 로딩 문제
**문제**: requests 라이브러리로 접근 시 게시글 목록이 보이지 않음
- 초기 페이지 로드 시 테이블 헤더만 존재
- 실제 데이터는 Ajax 요청으로 별도 로드
- 브라우저 없이는 JavaScript 실행 불가

**해결방법**: Playwright 브라우저 자동화 도입
```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(init_url)
    page.wait_for_timeout(3000)  # 로딩 대기
    
    if page_num > 1:
        page.evaluate(f"go_Page({page_num})")
        page.wait_for_timeout(2000)
    
    html_content = page.content()
    browser.close()
```

### 2. 세션 관리 문제
**문제**: 세션 초기화 없이 Ajax 요청 시 실패
**해결방법**: 
- 첫 페이지 방문으로 세션 생성
- URL에서 JSESSIONID 추출
- 후속 요청에 세션 ID 포함

### 3. 상세 페이지 구조 파악
**문제**: 상세 페이지 테이블 구조가 복잡함
**해결방법**: 
- 여러 테이블 중 첫 번째 테이블 사용
- 다양한 fallback 방법 구현
- 본문 내용이 주로 이미지로 구성됨

### 4. 첨부파일 다운로드 최적화
**문제**: 파일 다운로드 시 HTML 응답 감지 필요
**해결방법**: 
- Content-Type 검증
- 파일 크기 검증 (1KB 미만 HTML 감지)
- 세션 유지로 다운로드 성공률 향상

## 성능 최적화 및 특별 고려사항

### 1. Playwright 성능 최적화
- **headless 모드**: 브라우저 UI 없이 실행
- **적절한 대기 시간**: 페이지 로딩 3초, 페이지 이동 2초
- **브라우저 재사용**: 각 페이지마다 새 브라우저 인스턴스 생성

### 2. 요청 간격 조절
- **페이지 간 대기**: 1.5초 (JavaScript 실행 시간 고려)
- **요청 간 대기**: 2.0초 (서버 부하 방지)
- **타임아웃 설정**: 120초 (브라우저 로딩 시간 고려)

### 3. 메모리 관리
- **브라우저 정리**: 각 페이지 처리 후 브라우저 닫기
- **세션 관리**: 불필요한 세션 데이터 정리
- **임시 파일 정리**: 브라우저 캐시 자동 정리

## 수집 결과 및 검증

### 1. 수집 성과
- **총 처리 페이지**: 3페이지
- **총 수집 게시글**: 30개
- **총 첨부파일**: 41개
- **파일 형식**: HWP, PDF, ZIP, JPG 등 다양

### 2. 데이터 품질 검증
- **본문 추출**: 성공적 (주로 이미지 기반 콘텐츠)
- **첨부파일**: 완전 다운로드 성공
- **한글 파일명**: 완벽 지원
- **파일 크기**: 정상 범위 (47KB ~ 수백KB)

### 3. 오류 처리
- **HTML 응답 감지**: 성공적으로 필터링
- **빈 파일 처리**: 1KB 미만 파일 검증
- **세션 만료**: 자동 재시도 및 복구

## 다음 개발자를 위한 권장사항

### 1. 환경 설정
```bash
pip install playwright
playwright install chromium
```

### 2. 핵심 구현 포인트
- **Playwright 필수**: requests만으로는 불가능
- **세션 관리**: 초기 페이지 방문으로 세션 생성
- **대기 시간**: 충분한 로딩 대기 시간 설정
- **오류 처리**: 브라우저 종료 및 재시도 로직 구현

### 3. 디버깅 접근법
- **브라우저 모드**: headless=False로 실제 브라우저 확인
- **스크린샷**: page.screenshot()로 페이지 상태 확인
- **네트워크 로그**: 브라우저 개발자 도구 활용

### 4. 성능 최적화
- **동시 실행 제한**: 브라우저 리소스 관리
- **캐시 비활성화**: 페이지 변경 감지 향상
- **타임아웃 설정**: 무한 대기 방지

## 사이트별 특성 요약

### 1. 장점
- **안정적인 구조**: 테이블 기반 일관된 레이아웃
- **풍부한 첨부파일**: 다양한 형식 지원
- **한글 지원**: 완벽한 UTF-8 인코딩

### 2. 단점
- **JavaScript 의존**: 브라우저 자동화 필수
- **느린 속도**: 각 페이지마다 브라우저 로딩 필요
- **리소스 사용**: 메모리 및 CPU 사용량 높음

### 3. 주의사항
- **브라우저 의존성**: Playwright 환경 필수
- **세션 관리**: 세션 만료 시 재시도 로직
- **대기 시간**: 충분한 로딩 대기 시간 확보

## 기술 스택 및 의존성

### 1. 필수 라이브러리
- **Playwright**: 브라우저 자동화 (필수)
- **BeautifulSoup4**: HTML 파싱
- **requests**: HTTP 요청 (상세 페이지용)
- **html2text**: 마크다운 변환

### 2. 시스템 요구사항
- **Chromium**: Playwright 브라우저 엔진
- **충분한 메모리**: 브라우저 실행용 (최소 1GB)
- **네트워크 안정성**: 긴 실행 시간 고려

## 개발 완료 시점
- **개발 일자**: 2025-07-18
- **테스트 상태**: 3페이지 수집 완료
- **검증 상태**: 본문 추출 및 첨부파일 다운로드 정상 작동
- **특이사항**: JavaScript 동적 로딩으로 인한 Playwright 필수 사용