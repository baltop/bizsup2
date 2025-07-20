# JNSE Scraper Development Insights

## 사이트 정보
- **URL**: http://www.jn-se.kr/bbs/board.php?bo_table=nco4_1
- **사이트 코드**: jnse
- **사이트명**: 전남사회적경제통합지원센터 센터공지

## 개발 과정 및 발견사항

### 1. 사이트 구조 분석
- **플랫폼**: PHP 기반 게시판 시스템
- **페이지네이션**: GET 방식, `&page=` 파라미터 사용
- **목록 구조**: `ul.board_list_ul` > `li` 항목들
- **컬럼**: 번호, 분류, 제목, 작성일, 조회수

### 2. 주요 기술적 발견

#### 게시판 구조 특징
- **테이블 없음**: 전통적인 `<table>` 대신 `<ul><li>` 구조 사용
- **모바일 친화적**: 반응형 디자인으로 설계된 게시판
- **CSS 클래스**: `board_list_ul`, `bo_subjecta` 등 명확한 클래스 네이밍

#### URL 패턴
```python
# 목록 페이지
http://www.jn-se.kr/bbs/board.php?bo_table=nco4_1&page={page_num}

# 상세 페이지
http://www.jn-se.kr/bbs/board.php?bo_table=nco4_1&wr_id={post_id}

# 첨부파일 다운로드
http://www.jn-se.kr/bbs/download.php?bo_table=nco4_1&wr_id={post_id}&no={file_index}&page={page_num}
```

### 3. 첨부파일 처리 특성

#### 표준 다운로드 패턴
- **다운로드 스크립트**: `/bbs/download.php` 사용
- **파라미터**: `bo_table`, `wr_id`, `no`, `page` 조합
- **파일 크기 표시**: 링크 텍스트에 파일 크기 포함 (예: "파일명.hwp(167.5K)")

#### 파일 검증 로직
```python
# 중복 파일 처리 확인 필요
# 일부 게시글에서 같은 파일이 여러 번 나타남
if filename not in [att['filename'] for att in attachments]:
    attachments.append({
        'filename': filename,
        'url': urljoin(self.base_url, href)
    })
```

### 4. 한글 처리 및 인코딩
- **한글 파일명**: UTF-8 완전 지원
- **특수문자**: 괄호, 점 등 특수문자 포함된 파일명 정상 처리
- **대용량 파일**: PDF 9.5MB, HWP 1.7MB 등 대용량 파일 정상 다운로드

### 5. 성능 및 통계

#### 3페이지 테스트 결과
- **총 공고 수**: 45개 (15개/페이지)
- **총 첨부파일**: 120개
- **다운로드 성공률**: 100% (모든 파일 정상 다운로드)
- **실행 시간**: 약 1분 47초

#### 파일 유형 분포
- **HWP 파일**: 대부분의 공고문
- **PDF 파일**: 매뉴얼 및 가이드 문서 (특히 대용량)
- **ZIP 파일**: 신청서 서식 모음

### 6. 개발자 권장사항

#### 파싱 최적화
```python
# ul.board_list_ul 구조에 특화된 파싱
board_list = soup.find('ul', class_='board_list_ul')
list_items = board_list.find_all('li')

# 헤더 행 제외
for item in list_items:
    if item.get('class') and 'bo_head' in item.get('class'):
        continue
```

#### 첨부파일 다운로드 최적화
- **중복 파일 체크**: 같은 파일이 여러 번 링크되는 경우 대비
- **대용량 파일 처리**: 9MB+ 파일도 정상 다운로드됨
- **파일명 파싱**: 링크 텍스트에서 파일 크기 정보 제거 필요

### 7. 특별 고려사항

#### 중복 첨부파일 이슈
- **문제**: 일부 게시글에서 동일 파일이 여러 번 링크됨
- **해결**: 파일명 기반 중복 제거 로직 구현
- **주의**: 실제로는 같은 파일이지만 다른 `no` 파라미터 사용

#### 대용량 파일 처리
- **9.5MB PDF**: 정상 다운로드 (약 1-2초 소요)
- **1.7MB HWP**: 정상 다운로드 (약 0.3초 소요)
- **네트워크 안정성**: 재시도 메커니즘으로 안정성 확보

### 8. 에러 패턴 및 해결

#### 발견된 문제점
1. **중복 첨부파일**: 동일 파일의 여러 링크
2. **파일명 파싱**: 링크 텍스트에 크기 정보 포함

#### 해결 방법
1. **중복 제거**: 파일명 기반 필터링
2. **파일명 정리**: 크기 정보 제거 로직

### 9. 성공 요인
1. **ul/li 구조 파악**: 테이블이 아닌 목록 구조 이해
2. **PHP 게시판 패턴**: 표준 PHP 게시판 다운로드 패턴 적용
3. **한글 지원**: 완전한 UTF-8 처리
4. **중복 처리**: 효율적인 중복 파일 제거

### 10. 재사용 가능한 패턴

#### PHP 게시판 공통 패턴
```python
# 다운로드 URL 패턴
download_url = f"{base_url}/bbs/download.php?bo_table={board}&wr_id={post_id}&no={file_no}&page={page}"

# ul/li 기반 목록 파싱
board_list = soup.find('ul', class_='board_list_ul')
items = [item for item in board_list.find_all('li') if 'bo_head' not in item.get('class', [])]
```

이 인사이트는 향후 PHP 기반 게시판 시스템 스크래핑 시 참고할 수 있는 가이드라인을 제공합니다.