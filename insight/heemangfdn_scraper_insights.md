# 희망나눔재단(heemangfdn) 스크래퍼 개발 인사이트

## 사이트 정보
- **URL**: https://www.heemangfdn.or.kr/layout/res/home.php?go=pds.list&pds_type=1
- **사이트 코드**: heemangfdn
- **처리 결과**: 3페이지, 30개 공고 성공적으로 수집
- **개발 완료일**: 2025-07-20

## 주요 기술적 특징

### 1. 사이트 구조의 독특함
- **같은 페이지 확장 방식**: 일반적인 별도 상세 페이지가 아닌, 동일 페이지에서 상세 내용이 확장되는 구조
- **URL 패턴**: `home.php?go=pds.list&pds_type=1&num=1195` 형태로 직접 상세 내용 접근 가능
- **페이지네이션**: `start=0`, `start=10`, `start=20` 형태로 10개씩 증가

### 2. HTML 구조 분석
```html
<!-- 테이블 기반 목록 구조 -->
<table>
    <tr>
        <td>번호</td><td>제목</td><td>작성자</td><td>작성일</td><td>상태</td><td>조회수</td>
    </tr>
    <tr>
        <td></td>
        <td><a href="home.php?go=pds.list&pds_type=1&num=1195">제목링크</a></td>
        <td>운영자</td><td>2025-06-17</td><td>진행중</td><td>325</td>
    </tr>
</table>
```

### 3. 링크 파싱의 핵심
- **onclick 속성이 아닌 href 속성 사용**
- **정규식 패턴**: `r'num=(\d+)'`를 사용하여 공고 ID 추출
- **상대 경로 처리**: `home.php`로 시작하는 href를 절대 URL로 변환

### 4. 첨부파일 처리의 복잡성

#### 이미지 파일 분류
- **콘텐츠 이미지**: `/file/cheditor/`, `/file/banner/` 경로
- **UI 아이콘**: `/images/ico/`, `/images/board/`, `/images/icon/` 경로 (제외 필요)

#### 제외 패턴 목록
```python
excluded_patterns = [
    '/images/ico/', '/images/icon/', '/ico/', '/icon/', '/images/board/',
    'btn_', 'button_', 'arrow_', 'arr_', 'bg_', 'header_', 'footer_',
    'nav_', 'menu_', 'quick', 'close', 'play', 'pause', 'logo',
    'hd_', 'go_', 'kakao', 'facebook', 'twitter', 'instagram',
    'icon_', 'blank.gif', 'spacer.gif', 'dot.gif'
]
```

#### 다운로드 URL 패턴
- **이미지**: 직접 URL (`/file/cheditor/filename.png`)
- **문서 파일**: 다운로드 스크립트 (`/core/res/download.php?dir=../../file/pds/ID_N/&file=filename.pdf`)
- **한글 인코딩**: URL 인코딩된 한글 파일명 자동 처리

## 개발 과정의 주요 이슈

### 1. 초기 파싱 실패
- **문제**: onclick 패턴을 찾으려 했으나 실제로는 href 속성 사용
- **해결**: 브라우저 개발자 도구로 실제 HTML 구조 분석 후 수정

### 2. UI 아이콘 다운로드 문제
- **문제**: 콘텐츠와 관련 없는 UI 아이콘들이 대량 다운로드됨
- **해결**: 포괄적인 제외 패턴 리스트 구성으로 필터링

### 3. 한글 파일명 처리
- **특징**: 한글 파일명이 URL 인코딩되어 있지만 자동으로 올바르게 디코딩됨
- **예시**: `(첨부1)_소상공인_문화바우처_컬쳐패스_참여자_모집_공고문.pdf_(0.25MB)`

## 성능 및 결과

### 수집 통계
- **총 페이지**: 3페이지
- **총 공고**: 30개
- **첨부파일**: 다양한 형식 (PNG, JPG, PDF, HWP, ZIP)
- **처리 시간**: 약 1-2분 (첨부파일 다운로드 포함)

### 파일 크기 예시
- **이미지**: 20KB ~ 1MB
- **PDF 문서**: 100KB ~ 4MB
- **HWP 문서**: 200KB ~ 800KB

## 개발 팁

### 1. 사이트 분석 우선순위
```python
# 1. 브라우저 개발자 도구로 실제 HTML 구조 확인
# 2. 링크 클릭 시 JavaScript 동작 방식 파악  
# 3. 페이지네이션 방식 및 URL 패턴 분석
# 4. 첨부파일 다운로드 URL 패턴 식별
```

### 2. 디버깅 도구 활용
```python
# HTML 저장으로 오프라인 분석
with open('debug_heemangfdn_html.html', 'w', encoding='utf-8') as f:
    f.write(response.text)
```

### 3. 점진적 필터링 개선
- 처음에는 모든 이미지 다운로드
- 로그 분석을 통해 불필요한 패턴 식별
- 제외 패턴 추가로 점진적 개선

## 다른 사이트 적용 시 고려사항

### 1. 유사한 PHP 기반 사이트
- 같은 `?go=` 패턴을 사용하는 사이트에서 유사한 구조 예상
- 페이지네이션도 `start=` 파라미터 패턴일 가능성

### 2. 이미지 중심 콘텐츠 사이트
- UI 아이콘 제외 패턴 리스트 재사용 가능
- `/images/board/`, `/images/ico/` 등 공통 패턴

### 3. 한글 파일명 처리
- 대부분의 정부/공공기관 사이트에서 동일한 방식으로 처리 가능
- URL 인코딩 자동 디코딩 신뢰 가능

## 최종 검증 항목 ✅

- [x] 3페이지 30개 공고 수집 완료
- [x] 한글 파일명 정상 디코딩 확인
- [x] 첨부파일 다운로드 성공 (PNG, JPG, PDF, HWP, ZIP)
- [x] UI 아이콘 필터링 정상 작동
- [x] processed_titles_enhancedheemangfdn.json 생성 확인
- [x] 콘텐츠와 첨부파일 분리 저장 확인

## 결론

희망나눔재단 사이트는 독특한 같은 페이지 확장 방식을 사용하지만, 직접 URL 접근이 가능하여 스크래핑에 적합합니다. 가장 중요한 포인트는 UI 아이콘 필터링과 한글 파일명 처리이며, 이 두 가지를 잘 처리하면 안정적인 수집이 가능합니다.