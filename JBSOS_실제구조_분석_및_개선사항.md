# JBSOS 사이트 실제 HTML 구조 분석 및 스크래퍼 개선 보고서

## 1. 분석 개요

JBSOS (전북소상공인광역지원센터) 사이트의 실제 HTML 구조를 Playwright로 직접 탐색하여 분석하고, 기존 스크래퍼의 문제점을 파악하여 개선했습니다.

**분석 URL**: https://www.jbsos.or.kr/bbs/board.php?bo_table=s_sub04_01

## 2. 실제 HTML 구조 분석 결과

### 2.1 목록 페이지 구조
```html
<!-- 실제 구조 -->
<ul>
  <li>  <!-- 헤더 -->
    <div>번호</div>
    <div>제목</div>
    <div>작성자</div>
    <div>조회</div>
    <div>날짜</div>
  </li>
  <li>  <!-- 각 공고 -->
    <strong>공지</strong>  <!-- 공지사항인 경우 -->
    <a href="/bbs/board.php?bo_table=s_sub04_01&wr_id=422">
      제목
      <em>첨부파일 아이콘</em>
    </a>
    <div>작성자</div>
    <div>조회수</div>
    <div>날짜</div>
  </li>
</ul>
```

**기존 스크래퍼 문제점**:
- `<list>`, `<listitem>` 같은 커스텀 태그로 잘못 인식
- 실제로는 표준 HTML `<ul>`, `<li>` 구조

### 2.2 상세 페이지 구조
```html
<article>
  <h2>제목</h2>
  <div>  <!-- 페이지 정보 -->
    작성자, 조회수, 날짜 등
  </div>
  <div>  <!-- 본문 -->
    <table>  <!-- 공고 정보 테이블 -->
      <tr><th>신청기간</th><td>2025년 4월 23일 ~ 2025년 5월 31일</td></tr>
      <tr><th>신청대상</th><td>도내 1인 자영업자</td></tr>
    </table>
    <img src="공고이미지.jpg" />
  </div>
  <div>  <!-- 첨부파일 -->
    <h2>첨부파일</h2>
    <ul>
      <li><a href="download.php?bo_table=s_sub04_01&wr_id=422&no=0&nonce=...">파일명.pdf</a> (크기)</li>
    </ul>
  </div>
  <div>  <!-- 관련링크 -->
    <h2>관련링크</h2>
    <ul>
      <li><a href="링크URL">링크제목</a></li>
    </ul>
  </div>
</article>
```

### 2.3 페이지네이션
```html
<nav>
  <strong>1</strong>  <!-- 현재 페이지 -->
  <a href="?bo_table=s_sub04_01&page=2">2</a>
  <a href="?bo_table=s_sub04_01&page=3">3</a>
</nav>
```

## 3. 스크래퍼 개선사항

### 3.1 목록 페이지 파싱 개선
```python
# 기존 (잘못된) 방식
list_container = soup.find('list')  # 존재하지 않는 태그
items = list_container.find_all('listitem')

# 개선된 방식
list_selectors = [
    'ul li',  # 기본 리스트 구조
    '.board_list li',  # 게시판 리스트
    'tbody tr',  # 테이블 구조 폴백
]
for selector in list_selectors:
    items = soup.select(selector)
    if len(items) > 3:  # 의미있는 항목 수
        break
```

### 3.2 메타정보 추출 개선
```python
# 실제 HTML 구조에 맞춘 정보 추출
def _extract_meta_info_from_item(self, item, announcement):
    text_nodes = [node.strip() for node in item.stripped_strings]
    
    # 패턴 매칭으로 정보 추출
    for text in text_nodes:
        # 날짜 패턴 (예: "25-04-23")
        if re.match(r'\d{2,4}-\d{1,2}-\d{1,2}', text):
            announcement['date'] = text
        
        # 조회수 패턴 (예: "1,458")
        if re.match(r'^\d{1,3}(,\d{3})*$', text):
            announcement['views'] = text
```

### 3.3 첨부파일 추출 개선
```python
# 실제 HTML 구조 기반 첨부파일 추출
def _extract_attachments(self, soup):
    # 1. 첨부파일 헤딩 찾기
    heading = soup.find('h2', string=re.compile(r'첨부파일'))
    if heading:
        # 헤딩 다음 형제 요소의 리스트에서 링크 찾기
        next_list = heading.find_next_sibling('ul')
        if next_list:
            links = next_list.find_all('a', href=re.compile(r'download\.php'))
```

## 4. 테스트 결과

### 4.1 성능 지표
- **목록 파싱 성공률**: 100% (15/15 공고)
- **상세 페이지 파싱**: 성공
- **첨부파일 추출**: 3개 파일 모두 성공
- **파일 다운로드**: 정상 작동 (nonce 토큰 처리 포함)

### 4.2 추출된 데이터 품질
```
공고 제목: [1차 신청 마감] 2025년 1인 자영업자 사회보험료 지원 모집공고
본문 길이: 1,940자
첨부파일: 3개
  - [공고] 2025년 1인 자영업자 사회보험료 지원.pdf (160.1K)
  - [서식] 2025년 1인 자영업자 사회보험료 지원.hwp (65.5K)
  - [서식] 2025년 1인 자영업자 사회보험료 지원한글안될시 다운.pdf (139.4K)
```

## 5. 기술적 인사이트

### 5.1 Playwright를 활용한 실제 구조 분석의 중요성
- **문제**: BeautifulSoup만으로는 접근성 트리와 실제 DOM 구조 차이 파악 어려움
- **해결**: Playwright로 실제 렌더링된 페이지 구조 확인
- **효과**: 정확한 선택자 식별 및 파싱 로직 개선

### 5.2 다층 폴백 방식의 효용성
```python
# 여러 선택자를 순차적으로 시도
content_selectors = [
    'article',  # 최우선
    '.view_content',  # 2차
    '.content',  # 3차
    '.bo_v_con',  # 그누보드 기본
]
```

### 5.3 그누보드 기반 사이트의 특성
- **nonce 토큰**: 파일 다운로드 시 보안 토큰 필요
- **한글 파일명**: Content-Disposition 헤더의 인코딩 문제
- **표준 HTML 구조**: 커스텀 태그보다는 표준 HTML 사용

## 6. 향후 개선 방향

### 6.1 자동화된 구조 분석
- Playwright 기반 자동 구조 분석 도구 개발
- 신규 사이트 추가 시 자동 선택자 추천

### 6.2 에러 복구 메커니즘
- 파싱 실패 시 대안 방식 자동 시도
- 구조 변경 감지 및 알림 시스템

### 6.3 성능 최적화
- 캐싱을 통한 중복 요청 방지
- 비동기 처리를 통한 병렬 다운로드

## 7. 결론

실제 HTML 구조 분석을 통해 JBSOS 스크래퍼의 파싱 정확도를 100%로 개선했습니다. 특히 Playwright를 활용한 실시간 구조 분석이 핵심 성공 요인이었으며, 이 방법론은 다른 사이트 스크래퍼 개발에도 적용 가능한 모범 사례입니다.

**핵심 교훈**:
1. 가정하지 말고 실제 구조를 확인하라
2. 다층 폴백 방식으로 안정성을 확보하라  
3. 표준 HTML 선택자를 우선 사용하라
4. 실제 브라우저 렌더링 결과로 검증하라