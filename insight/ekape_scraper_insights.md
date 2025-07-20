# EKAPE 스크래퍼 개발 인사이트

## 웹사이트 개요
- **사이트명**: 축산물품질평가원 (EKAPE)
- **URL**: https://www.ekape.or.kr/board/list.do?menuId=menu149208&nextUrl=
- **사이트 코드**: ekape
- **개발 완료일**: 2025-07-18

## 주요 기술적 특징

### 1. HTML 테이블 구조 분석
- **핵심 발견**: EKAPE 웹사이트는 기존 일반적인 테이블 구조와 다르게 **data-column 속성**을 사용하여 각 셀을 구분합니다
- **중요한 CSS 선택자**:
  ```python
  # 일반적인 셀 인덱스 방식이 아닌 data-column 속성 사용
  number_cell = row.find('td', attrs={'data-column': '번호'})
  title_cell = row.find('td', attrs={'data-column': '제목'})
  author_cell = row.find('td', attrs={'data-column': '등록자'})
  date_cell = row.find('td', attrs={'data-column': '등록일'})
  views_cell = row.find('td', attrs={'data-column': '조회수'})
  ```

### 2. JavaScript 기반 링크 시스템
- **상세 페이지 접근**: `goBoardView()` JavaScript 함수를 통해 상세 페이지로 이동
- **URL 패턴**: 
  ```
  https://www.ekape.or.kr/board/view.do?menuId=menu149208&boardNo={boardNo}&dmlType=SELECT&pageIndex={pageIndex}&pageUnit=10&searchCondition=SUBJECT&searchKeyword=
  ```
- **boardNo 추출**: JavaScript 함수에서 정규식으로 게시글 번호 추출
  ```python
  board_no_match = re.search(r"goBoardView\('(\d+)'\)", href)
  ```

### 3. 첨부파일 다운로드 시스템 (핵심 해결사항)
- **초기 문제**: 모든 첨부파일이 0바이트로 다운로드됨
- **원인**: JavaScript 함수 `attachfileDownload()`의 매개변수를 올바르게 파싱하지 못함
- **해결책**: JavaScript 함수에서 매개변수를 정확히 추출하여 실제 다운로드 URL 생성

#### 첨부파일 URL 패턴
```javascript
// HTML에서 발견되는 패턴
attachfileDownload('/attachfile/attachfileDownload.do','0024','830','1')
```

```python
# 실제 다운로드 URL 생성
download_url = f"{self.base_url}/attachfile/attachfileDownload.do?boardInfoNo={board_info_no}&boardNo={board_no}&fileId={file_id}"
```

#### 매개변수 의미
- `boardInfoNo`: 게시판 정보 번호 (예: '0024')
- `boardNo`: 게시글 번호 (예: '830')
- `fileId`: 첨부파일 순번 (예: '1', '2', '3', '4')

### 4. 세션 관리 및 헤더 설정
- **중요**: 첨부파일 다운로드 시 적절한 `Referer` 헤더 설정이 필요
- **해결 방법**: 상세 페이지 URL을 `current_detail_url`로 저장하여 첨부파일 다운로드 시 Referer로 사용

```python
# 상세 페이지에서 URL 저장
self.current_detail_url = detail_url

# 첨부파일 다운로드 시 Referer 설정
if hasattr(self, 'current_detail_url') and self.current_detail_url:
    download_headers['Referer'] = self.current_detail_url
```

## 페이지네이션 구조
- **URL 패턴**: `pageIndex` 매개변수로 페이지 번호 제어
- **페이지 당 게시물 수**: 10개 (pageUnit=10)
- **다음 페이지 URL**: 
  ```
  https://www.ekape.or.kr/board/list.do?menuId=menu149208&nextUrl=&pageIndex=2
  ```

## 주요 개발 이슈 및 해결책

### 1. 테이블 파싱 실패 (해결됨)
- **문제**: 초기 테스트에서 10개 행을 발견했지만 0개 공고만 파싱됨
- **원인**: 일반적인 셀 인덱스 접근법(`cells[0]`) 사용
- **해결**: `data-column` 속성 기반 셀 찾기로 변경

### 2. 첨부파일 다운로드 실패 (해결됨)
- **문제**: 모든 첨부파일이 0바이트로 다운로드됨
- **원인**: JavaScript 함수의 매개변수를 올바르게 파싱하지 못함
- **해결**: 정규식을 사용하여 `attachfileDownload()` 함수에서 매개변수 추출

### 3. 한글 파일명 처리 (안정적)
- **특징**: EKAPE 웹사이트는 한글 파일명을 UTF-8로 올바르게 제공
- **결과**: 추가적인 인코딩 처리 없이도 한글 파일명 정상 저장

## 성능 및 수집 결과

### 최종 수집 통계 (2025-07-18)
- **총 처리 페이지**: 3페이지
- **총 수집 공고**: 30개
- **총 첨부파일**: 47개
- **총 다운로드 크기**: 약 9MB
- **평균 처리 시간**: 페이지당 약 1분
- **첨부파일 성공률**: 100%

### 파일 크기 분포
- **HWP 파일**: 평균 150KB (33KB ~ 420KB)
- **PDF 파일**: 평균 200KB (95KB ~ 692KB)
- **ZIP 파일**: 평균 900KB (255KB ~ 1.9MB)

## 향후 개발자를 위한 권장사항

### 1. 코드 재사용 가능성
- **높음**: 다른 정부기관 웹사이트에서도 유사한 `data-column` 속성 방식 사용 가능
- **JavaScript 함수 파싱**: 정규식 기반 매개변수 추출 방식은 다른 사이트에서도 응용 가능

### 2. 확장성 고려사항
- **다중 게시판 지원**: `menuId` 매개변수 변경으로 다른 게시판 수집 가능
- **검색 기능**: `searchCondition`, `searchKeyword` 매개변수 활용 가능

### 3. 에러 처리
- **네트워크 타임아웃**: 대용량 ZIP 파일 다운로드 시 타임아웃 설정 충분히 확보
- **JavaScript 파싱 실패**: 백업 방식으로 기존 href 기반 파싱 로직 유지

### 4. 모니터링 포인트
- **첨부파일 다운로드 실패**: 0바이트 파일 감지 시 즉시 알림
- **게시판 구조 변경**: `data-column` 속성 사라짐 감지
- **JavaScript 함수 변경**: `attachfileDownload()` 함수 시그니처 변경 감지

## 기술적 혁신 포인트

### 1. 이중 백업 시스템
- **주요 방식**: `data-column` 속성 기반 파싱
- **백업 방식**: 기존 href 기반 파싱 (호환성 보장)

### 2. 동적 URL 생성
- **JavaScript 함수 파싱**: 정적 HTML에서 동적 URL 추출
- **매개변수 조합**: 복잡한 쿼리 스트링 자동 생성

### 3. 세션 유지 최적화
- **상세 페이지 URL 저장**: 첨부파일 다운로드 시 Referer 자동 설정
- **헤더 최적화**: 사이트별 맞춤형 헤더 설정

## 결론
EKAPE 스크래퍼는 특히 **JavaScript 기반 첨부파일 다운로드 시스템**과 **data-column 속성 기반 테이블 파싱**에서 혁신적인 해결책을 제시했습니다. 이러한 기술적 접근 방식은 다른 정부기관 웹사이트 스크래핑에도 직접 적용 가능하며, 특히 복잡한 JavaScript 기반 다운로드 시스템을 가진 사이트에서 유용할 것입니다.

---
*개발자: Claude Code*  
*최종 수정: 2025-07-18*  
*스크래퍼 파일: enhanced_ekape_scraper.py*