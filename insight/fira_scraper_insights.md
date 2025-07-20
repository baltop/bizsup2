# FIRA (한국수산자원공단) 스크래퍼 개발 인사이트

## 사이트 정보
- **사이트명**: 한국수산자원공단 (Korea Fisheries Resources Agency)
- **URL**: https://www.fira.or.kr/fira/fira_010101_1.jsp
- **사이트 코드**: fira
- **페이지네이션**: GET 방식 (pager.offset 파라미터 사용)

## 주요 기술적 특징

### 1. 페이지네이션 구조
- **방식**: GET 방식 페이지네이션
- **파라미터**: 
  - `mode=list&board_no=2` (첫 페이지)
  - `mode=list&board_no=2&pager.offset=10` (두 번째 페이지)
- **페이지당 게시글 수**: 10개
- **URL 패턴**: 기본 URL + 쿼리 파라미터

### 2. HTML 구조 분석
- **목록 페이지**: `table.lmode` 클래스 사용
- **상세 페이지**: `table.vmode` 클래스 사용
- **본문 내용**: `div#article_text` 또는 테이블 4번째 행의 td
- **첨부파일**: `ul.attach_list` 또는 테이블 3번째 행 내 위치

### 3. 중요한 URL 처리
- **상세 페이지 URL**: 쿼리 스트링으로 시작 (`?mode=view&article_no=...`)
- **URL 구성**: 기본 페이지 경로 + 쿼리 스트링
- **올바른 처리**: `self.list_url + href` (href가 '?'로 시작하는 경우)

## 개발 과정에서 발견한 문제점과 해결방법

### 1. 상세 페이지 URL 구성 오류
**문제**: 초기 구현에서 상세 페이지 URL이 잘못 구성됨
- 잘못된 URL: `https://www.fira.or.kr?mode=view&...`
- 올바른 URL: `https://www.fira.or.kr/fira/fira_010101_1.jsp?mode=view&...`

**해결방법**:
```python
if href.startswith('?'):
    # 쿼리 스트링으로 시작하는 경우 기본 페이지 경로 추가
    detail_url = self.list_url + href
else:
    detail_url = urljoin(self.base_url, href)
```

### 2. 첨부파일 다운로드 URL 패턴
**문제**: 초기 분석에서 잘못된 다운로드 URL 패턴 사용
- 잘못된 패턴: `/_custom/cms/_common/download.do?file_seq=`
- 올바른 패턴: `/_custom/cms/_common/board/fira.jsp?attach_no=`

**해결방법**: JavaScript 함수 분석을 통해 올바른 URL 패턴 발견
```python
# 실제 다운로드 URL 구성
download_url = f"{self.base_url}/_custom/cms/_common/board/fira.jsp?attach_no={file_id}"
```

### 3. 본문 내용 추출 실패
**문제**: 초기 구현에서 본문 내용이 0길이로 추출됨
**해결방법**: 다중 추출 방법 구현
1. `div#article_text` 직접 찾기 (가장 정확함)
2. 테이블 4번째 행의 td에서 추출
3. colspan이 큰 td 찾기

### 4. 테이블 구조 분석
**문제**: `table.lmode`와 `table.vmode` 클래스 정확히 식별 필요
**해결방법**: 
- 디버깅 로그로 모든 테이블 구조 확인
- 대안 방법으로 첫 번째 테이블 사용

## 성능 최적화 설정
- **요청 간격**: 1.5초 (delay_between_requests)
- **페이지 간격**: 1.0초 (delay_between_pages)
- **타임아웃**: 기본 설정 사용
- **헤더 설정**: 한국어 Accept-Language 포함

## 파일 다운로드 검증
- **HTML 응답 감지**: Content-Type 확인
- **파일 크기 검증**: 1KB 미만 파일의 HTML 내용 검사
- **오류 파일 삭제**: HTML 내용 감지 시 자동 삭제
- **UTF-8 지원**: 한글 파일명 완전 지원

## 수집 결과
- **총 처리 페이지**: 3페이지
- **총 수집 게시글**: 30개
- **본문 추출**: 성공적으로 마크다운 변환
- **첨부파일**: PDF, HWP 등 다양한 형식 지원

## 다음 개발자를 위한 권장사항

### 1. 디버깅 접근법
- 항상 HTML 구조를 먼저 분석
- 모든 테이블 태그의 클래스와 ID 확인
- 쿼리 스트링 기반 URL 처리 주의

### 2. 테스트 방법
- 단일 페이지 먼저 테스트
- 본문 길이와 첨부파일 개수 확인
- 파일 다운로드 후 크기 검증

### 3. 오류 처리
- 각 단계별 예외 처리 구현
- 상세한 로그 메시지 추가
- 대안 방법 여러 개 준비

### 4. 사이트별 특성
- FIRA 사이트는 상대적으로 안정적인 구조
- GET 방식 페이지네이션으로 간단함
- 첨부파일 다운로드 시 Referer 헤더 필요

## 기술 스택
- **언어**: Python 3.x
- **라이브러리**: requests, BeautifulSoup4, html2text
- **상속**: EnhancedBaseScraper 클래스
- **로깅**: Python logging 모듈
- **인코딩**: UTF-8 완전 지원

## 개발 완료 시점
- **개발 일자**: 2025-07-18
- **테스트 상태**: 3페이지 수집 완료
- **검증 상태**: 본문 추출 및 첨부파일 다운로드 정상 작동