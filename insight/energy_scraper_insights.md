# 한국에너지공단 공지사항 스크래퍼 개발 인사이트

## 프로젝트 개요
- **사이트**: 한국에너지공단 (https://www.energy.or.kr/front/board/List2.do)
- **사이트 코드**: energy
- **개발 기간**: 2025-07-18
- **수집 결과**: 3페이지 30개 공고 수집 완료

## 핵심 기술적 특징

### 1. POST 기반 페이지네이션 시스템
- **특징**: 일반적인 GET 방식과 달리 POST 방식으로 페이지 이동
- **POST 데이터 구조**:
  ```python
  {
      'page': str(page_num),
      'searchfield': 'ALL',
      'searchword': ''
  }
  ```
- **중요**: 사이트 세션 초기화 후 POST 요청 필요

### 2. JavaScript 기반 상세 페이지 네비게이션
- **함수**: `fn_Detail('boardMngNo', 'boardNo')`
- **파라미터 추출**: 정규표현식으로 onclick 속성 파싱
- **예시**: `fn_Detail('2','24437')` → boardMngNo=2, boardNo=24437

### 3. 첨부파일 다운로드 시스템
- **JavaScript 함수**: `fileDownload(fileNo, fileSeq, boardMngNo)`
- **다운로드 URL**: `https://www.energy.or.kr/commonFile/fileDownload.do`
- **POST 데이터**: 
  ```python
  {
      'fileNo': file_no,
      'fileSeq': file_seq,
      'boardMngNo': board_mng_no
  }
  ```

### 4. 본문 내용 추출
- **주요 CSS 선택자**:
  - `.view_inner` (608자) - 순수 본문 내용
  - `.view_cont` (608자) - 순수 본문 내용
  - `.board_view` (851자) - 제목 + 본문
  - `article .content_inner` (859자) - 전체 내용
  - `article .board_wrap` (859자) - 전체 내용

## 개발 중 발견한 문제점과 해결방안

### 1. 본문 추출 이슈
- **문제**: 초기 CSS 선택자 `.view_cont .view_inner` 등이 작동하지 않음
- **원인**: 실제 DOM 구조와 불일치
- **해결**: 디버깅을 통해 정확한 선택자 확인
- **최종 선택자**: `.view_inner`, `.view_cont` 우선 사용

### 2. 세션 관리 중요성
- **문제**: 세션 초기화 없이 바로 POST 요청 시 실패
- **해결**: 반드시 목록 페이지 초기 GET 요청 후 POST 요청 수행
- **코드**:
  ```python
  # 세션 초기화
  response = self.session.get(self.list_url, timeout=10)
  
  # 이후 POST 요청
  response = self.session.post(self.list_url, data=data, timeout=10)
  ```

### 3. 첨부파일 감지 패턴
- **HTML 구조**: `<a onclick="fileDownload('fileNo','fileSeq','boardMngNo')">파일명</a>`
- **파일명 정리**: `[첨부1]`, `[첨부2]` 등 불필요한 접두사 제거
- **정규표현식**: `fileDownload\('([^']+)','([^']+)','([^']+)'\)`

### 4. 한글 파일명 지원
- **인코딩**: UTF-8 완전 지원
- **파일명 예시**: `국제협력실해외사업('25년~'27년)위탁정산기관모집공고.hwp`
- **특수문자 처리**: 괄호, 작은따옴표 등 모든 특수문자 정상 처리

## 성능 및 안정성

### 1. 요청 간격 제어
- **설정**: 1초 간격으로 요청
- **목적**: 서버 부하 방지 및 차단 회피
- **구현**: `time.sleep(1)` 사용

### 2. 오류 처리
- **HTTP 오류**: 각 요청마다 try-catch 처리
- **파싱 오류**: 각 공고별 독립적 오류 처리
- **파일 다운로드**: Content-Type 및 파일 크기 검증

### 3. 중복 방지
- **방식**: 제목 해시 기반 중복 검사
- **파일**: `processed_titles.json`
- **효과**: 재실행 시 중복 처리 방지

## 수집 결과 분석

### 1. 성공 통계
- **총 공고 수**: 30개 (3페이지)
- **실행 시간**: 44.5초
- **HTTP 요청**: 30개
- **초당 요청 수**: 0.67개

### 2. 파일 구조
```
output/energy/
├── 001_한국에너지공단_해외사업('25년~'27년)_위탁정산기관_모집_안내/
│   ├── content.md
│   └── attachments/ (첨부파일이 있는 경우)
├── 002_2025_기후에너지_혁신상_선정_결과/
│   └── content.md
...
```

### 3. 메타데이터 포함
- **제목**: 한글 제목 완전 지원
- **작성일**: 정확한 날짜 정보
- **조회수**: 실시간 조회수 반영
- **원본 URL**: 상세 페이지 URL 기록

## 향후 개발자를 위한 권장사항

### 1. 필수 구현 사항
- **세션 관리**: 반드시 사이트 초기화 후 POST 요청
- **오류 처리**: 각 단계별 독립적 오류 처리
- **요청 간격**: 1초 이상 간격 유지
- **인코딩**: UTF-8 인코딩 필수

### 2. 개선 가능 영역
- **병렬 처리**: 첨부파일 다운로드 시 병렬 처리 고려
- **재시도 로직**: 네트워크 오류 시 재시도 메커니즘
- **로그 상세화**: 더 상세한 디버깅 정보 제공

### 3. 주의사항
- **robots.txt**: 이 사이트는 robots.txt 준수 불필요
- **User-Agent**: 적절한 User-Agent 헤더 필수
- **세션 쿠키**: 세션 쿠키 자동 관리 필요

## 디버깅 도구
프로젝트에는 다음 디버깅 도구들이 포함되어 있습니다:
- `debug_energy_content.py`: 본문 추출 디버깅
- `debug_energy_detail.py`: 상세 페이지 분석
- `test_energy_scraper_direct.py`: 스크래퍼 직접 테스트

이러한 도구들을 활용하여 문제 발생 시 빠른 디버깅이 가능합니다.

## 결론
한국에너지공단 스크래퍼는 POST 기반 페이지네이션과 JavaScript 기반 네비게이션을 성공적으로 구현하였습니다. 특히 한글 파일명 지원과 안정적인 세션 관리를 통해 실제 운영 환경에서 안정적으로 동작할 수 있습니다.

---
*개발일: 2025-07-18*
*개발자: Claude Code*