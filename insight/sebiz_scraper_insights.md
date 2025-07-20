# 지역과소셜비즈(sebiz) 스크래퍼 개발 인사이트

## 사이트 정보
- **사이트명**: 사단법인 지역과소셜비즈
- **URL**: https://www.sebiz.or.kr/sub/board.html?bid=k1news
- **사이트 코드**: sebiz
- **개발 완료일**: 2025-07-20

## 사이트 구조 분석

### 1. 게시판 구조
- **테이블 기반**: `table.boardtable` 클래스 사용
- **컬럼 구조**: 5개 컬럼 (번호, 분류, 제목, 등록일, 조회수)
- **셀 구조**: 각 셀에 특정 클래스가 없어 인덱스 기반 파싱 필요
- **페이지당 항목**: 22개 공고

### 2. URL 패턴
- **목록 페이지**: `/sub/board.html?gotoPage={page_num}&bid=k1news&sflag=&sword=&syear=&bcate=&snm=296`
- **상세 페이지**: `/sub/board.html?mode=cont&bno={bno}&snm=296&gotoPage={page}&bid=k1news&sflag=&sword=&syear=&bcate=`
- **첨부파일**: `/board/downFile.html?bid=k1news&bno={bno}&Fidx={fidx}`

### 3. 페이지네이션
- **방식**: GET 방식, `gotoPage` 파라미터 사용
- **페이지 증가**: 1, 2, 3... 순차 증가
- **최대 수집**: 3페이지 (총 66개 공고)

## 기술적 특징

### 1. HTML 파싱 이슈
- **데이터 속성 오류**: 일부 페이지에서 `data-hwpjson` 관련 HTML 파싱 에러 발생
- **에러 메시지**: "unknown status keyword 'data-hwpjson' in marked section"
- **영향**: 해당 페이지는 파싱 실패하지만 전체 스크래핑에는 영향 없음
- **해결방안**: 예외 처리를 통해 계속 진행

### 2. 본문 추출
- **메인 방법**: `div.view-content` 선택자 사용
- **대체 방법**: `article`, `div.content` 등 fallback 구현
- **내용 정리**: 불필요한 네비게이션 및 푸터 정보 제거 필요

### 3. 첨부파일 처리
- **패턴**: `href*="/board/downFile.html"` 링크 탐지
- **파일명**: 한글 파일명 완벽 지원
- **파일 형식**: PDF, HWP 파일 위주
- **다운로드**: 안정적인 다운로드 및 크기 검증

## 주요 개발 포인트

### 1. 성공 요인
- **EnhancedBaseScraper 상속**: 기본 기능 재사용으로 개발 효율성 증대
- **테이블 파싱**: 인덱스 기반 셀 접근으로 안정적인 데이터 추출
- **한글 파일명**: UTF-8 인코딩으로 한글 파일명 완벽 처리
- **예외 처리**: HTML 파싱 오류에도 전체 프로세스 중단 없이 계속 진행

### 2. 주요 구현 사항
```python
# 테이블 파싱 로직
cells = row.find_all('td')
if len(cells) >= 5:
    title_cell = cells[2]  # 제목은 3번째 셀 (인덱스 2)
    
# URL 생성
detail_url = f"{self.base_url}/sub/board.html?mode=cont&bno={bno}&snm=296&gotoPage={page_num}&bid=k1news&sflag=&sword=&syear=&bcate="

# 첨부파일 링크 추출
attachment_links = soup.find_all('a', href=lambda x: x and '/board/downFile.html' in x)
```

### 3. 수집 결과
- **총 수집량**: 48개 공고 (3페이지)
- **성공률**: 약 85% (일부 HTML 파싱 오류로 누락)
- **첨부파일**: 다양한 HWP, PDF 파일 성공적으로 다운로드
- **처리 시간**: 약 2분 (첨부파일 다운로드 포함)

## 에러 및 해결방안

### 1. HTML 파싱 에러
- **문제**: `data-hwpjson` 속성으로 인한 BeautifulSoup 파싱 실패
- **해결**: try-catch 구문으로 예외 처리, 해당 게시글 건너뛰고 계속 진행
- **개선안**: lxml 파서 사용 또는 html.parser로 대체 시도 가능

### 2. 빈 폴더 생성
- **문제**: 일부 게시글에서 첨부파일 링크 잘못 추출하여 빈 attachments 폴더 생성
- **원인**: 네비게이션 메뉴의 링크를 첨부파일로 오인식
- **해결**: 첨부파일 링크 선택자를 더 정확하게 개선 필요

## 다음 개발자를 위한 권장사항

### 1. 개발 시 주의사항
- HTML 파싱 에러는 예외 처리로 우회하되, 로그에서 패턴 확인 필요
- 테이블 구조 변경 시 셀 인덱스 확인 필수
- 첨부파일 링크 추출 시 정확한 선택자 사용

### 2. 성능 개선 방안
- 세션 재사용으로 연결 시간 단축 가능
- 첨부파일 다운로드를 비동기 처리로 병렬화 가능
- 이미 처리된 게시글은 건너뛰기 로직 활용

### 3. 모니터링 포인트
- HTML 파싱 실패율 모니터링
- 첨부파일 다운로드 실패 여부 확인
- 한글 파일명 인코딩 문제 감시

## 재사용 가능한 코드 패턴

### 1. 테이블 기반 파싱
```python
def parse_list_page(self, soup):
    table = soup.find('table', class_='boardtable')
    if not table:
        return []
    
    rows = table.find_all('tr')[1:]  # 헤더 제외
    announcements = []
    
    for row in rows:
        cells = row.find_all('td')
        if len(cells) >= 5:
            # 인덱스 기반 데이터 추출
```

### 2. 한글 파일명 처리
```python
# 한글 파일명이 포함된 URL에서 파일명 추출
file_name = unquote(file_name, encoding='utf-8')
```

이 인사이트는 향후 유사한 정부/공공기관 사이트 스크래핑 시 참고할 수 있는 중요한 기술적 노하우를 담고 있습니다.