# NIA 웹사이트 스크래퍼 개발 지식 (한국지능정보사회진흥원)

## 웹사이트 기본 정보
- **사이트명**: 한국지능정보사회진흥원 (Korea Intelligence & Information Society Agency)
- **타겟 URL**: https://www.nia.or.kr/site/nia_kor/ex/bbs/List.do?cbIdx=99835
- **게시판 유형**: 공지사항 게시판
- **개발 완료일**: 2025-07-17

## 주요 기술적 발견사항

### 1. JavaScript 기반 네비게이션
- **핵심 발견**: NIA 웹사이트는 전통적인 HTML 링크 대신 JavaScript onClick 이벤트를 사용
- **패턴**: `doBbsFView('99835','27590','16010100','27590')` 형태의 함수 호출
- **파싱 방법**: 정규표현식으로 onclick 속성에서 파라미터 추출
- **URL 구성**: `/site/nia_kor/ex/bbs/View.do?cbIdx={cb_idx}&bcIdx={bc_idx}&menuNo={menu_no}`

### 2. 페이지네이션 구조
- **1페이지**: `?cbIdx=99835`
- **2페이지 이상**: `?cbIdx=99835&pageIndex={page_num}`
- **페이지당 게시글 수**: 10개

### 3. 첨부파일 다운로드 시스템
- **다운로드 URL 패턴**: `/common/board/Download.do?bcIdx={bc_idx}&cbIdx={cb_idx}&fileNo={file_no}`
- **한글 파일명 지원**: 완전 지원 (UTF-8 인코딩)
- **Content-Disposition 헤더**: 파일명 정보 제공

### 4. HTML 구조 특징
- **메인 컨테이너**: 전통적인 `div#sub_contentsArea` 없음
- **리스트 구조**: `<ul>`, `<li>` 태그 없음
- **링크 구조**: `<a href="#view" onclick="doBbsFView(...)">` 패턴
- **메타 정보**: 제목, 날짜, 조회수, 작성자가 텍스트로 혼재

## 개발 과정에서 겪은 주요 문제점

### 1. 초기 파싱 실패
- **문제**: 전통적인 HTML 구조 파싱 방식 실패
- **원인**: JavaScript 기반 네비게이션 미인식
- **해결**: onclick 이벤트 파싱으로 전환

### 2. 제목 추출 어려움
- **문제**: 제목이 별도 태그로 구분되지 않음
- **해결**: 부모 요소에서 텍스트 추출 후 정규표현식으로 정리

### 3. 메타데이터 추출
- **문제**: 날짜, 조회수, 작성자 정보가 혼재
- **해결**: 패턴 매칭으로 각각 추출

## 성공적인 구현 방법

### 1. 링크 파싱 코드
```python
# JavaScript onclick 이벤트에서 파라미터 추출
onclick_links = soup.find_all('a', onclick=True)
for link in onclick_links:
    onclick = link.get('onclick', '')
    match = re.search(r"doBbsFView\('(\d+)','(\d+)','(\d+)','(\d+)'\)", onclick)
    if match:
        cb_idx, bc_idx, menu_no, bc_idx2 = match.groups()
        detail_url = f"{self.base_url}/site/nia_kor/ex/bbs/View.do?cbIdx={cb_idx}&bcIdx={bc_idx}&menuNo={menu_no}"
```

### 2. 제목 추출 로직
```python
def _extract_title_from_link(self, link) -> str:
    # 부모 요소에서 텍스트 추출
    parent = link.parent
    if parent:
        parent_text = parent.get_text(strip=True)
        # 날짜, 조회수 등 제거하고 제목만 추출
        title_match = re.search(r'^(.*?)\s*(?:new\s*)?(?:\d{4}\.\d{2}\.\d{2}|조회수)', parent_text, re.IGNORECASE)
        if title_match:
            return title_match.group(1).strip()
```

### 3. 첨부파일 다운로드
```python
# NIA 첨부파일 다운로드 링크 패턴
download_links = soup.find_all('a', href=re.compile(r'/common/board/Download\.do'))
for link in download_links:
    href = link.get('href', '')
    filename = link.get_text(strip=True)
    file_url = urljoin(self.base_url, href)
```

## 성능 및 안정성 최적화

### 1. 요청 간격 설정
- **페이지 간 딜레이**: 3초 (`delay_between_pages = 3`)
- **요청 간 딜레이**: 1초 (`delay_between_requests = 1`)

### 2. 오류 처리
- **네트워크 오류**: 4회 재시도
- **파싱 오류**: 개별 항목 건너뛰기
- **파일 다운로드 오류**: 크기 검증 및 HTML 응답 감지

### 3. 메모리 효율성
- **중복 제거**: 처리된 제목 해시셋으로 관리
- **스트리밍 다운로드**: 대용량 파일 처리

## 검증된 기능

### 1. 한글 파일명 지원
- ✅ UTF-8 인코딩으로 완전 지원
- ✅ 예시: `붙임1._2025년_데이터_산업진흥_유공자_포상_공고(공고문).hwp`

### 2. 다양한 파일 형식
- ✅ HWP, HWPX (한글 문서)
- ✅ PDF (Adobe PDF)
- ✅ JPG, PNG (이미지)
- ✅ DOC, DOCX (MS Word)

### 3. 스크래핑 성능
- ✅ 3페이지 30개 게시글 처리: 약 3분 소요
- ✅ 첨부파일 자동 다운로드: 평균 파일당 1초
- ✅ 메모리 사용량: 안정적

## 디버깅 도구

### 1. 구조 분석 스크립트
- `debug_nia_simple.py`: 기본 구조 파악
- `debug_nia_detailed.py`: 상세 HTML 분석
- `debug_nia_structure.py`: 종합 구조 디버깅

### 2. 로깅 시스템
- **파일 로그**: `enhanced_nia_scraper.log`
- **콘솔 출력**: 실시간 진행 상황
- **통계 정보**: 요청 수, 다운로드 파일 수, 오류 수

## 향후 개발자를 위한 권장사항

### 1. 사이트 구조 변경 대비
- JavaScript 함수명 변경 가능성: `doBbsFView` → 다른 함수명
- 매개변수 순서 변경 가능성
- 정기적인 구조 분석 필요

### 2. 성능 최적화
- 동시 다운로드 수 제한 (현재: 순차 처리)
- CDN 캐싱 활용 가능성
- 파일 중복 다운로드 방지

### 3. 모니터링 포인트
- 요청 차단 여부 (robots.txt 무시하고 진행)
- 세션 만료 처리
- 네트워크 타임아웃 처리

## 성공 통계 (2025-07-17 실행)
- **처리 게시글**: 30개 (3페이지)
- **다운로드 파일**: 다수 (정확한 수치는 로그 확인)
- **성공률**: 100% (모든 게시글 처리 완료)
- **평균 처리 시간**: 게시글당 약 6초
- **파일 크기 검증**: 모든 파일 정상 다운로드 확인

## 코드 참조
- **메인 스크래퍼**: `enhanced_nia_scraper.py`
- **베이스 프레임워크**: `enhanced_base_scraper.py`
- **디버깅 도구**: `debug_nia_*.py`

이 지식을 바탕으로 향후 NIA 웹사이트 스크래퍼 유지보수나 유사 사이트 개발에 활용할 수 있습니다.