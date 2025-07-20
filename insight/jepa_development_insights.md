# JEPA 스크래퍼 개발 인사이트

## 사이트 정보
- **URL**: https://www.jepa.kr/bbs/?b_id=notice&site=new_jepa&mn=322&sc_category=자금지원
- **기관**: 전라남도경제진흥원 (전라남도 중소기업 일자리 경제진흥원)
- **수집 대상**: 자금지원 공지사항

## 사이트 구조 분석

### 1. AJAX 기반 콘텐츠 로딩
- **핵심 발견**: 사이트는 AJAX를 통해 동적 콘텐츠를 로드함
- **AJAX URL**: `/bbs/bbs_ajax/?b_id=notice&site=new_jepa&mn=322&sc_category=%EC%9E%90%EA%B8%88%EC%A7%80%EC%9B%90`
- **페이지네이션**: `&offset={offset}&page={page_num}` 파라미터 사용
- **인코딩**: 한글 카테고리명은 URL 인코딩 필요 (`자금지원` → `%EC%9E%90%EA%B8%88%EC%A7%80%EC%9B%90`)

### 2. HTML 구조
```html
<table caption="공지사항 게시판">
  <tbody>
    <tr>
      <td>번호</td>
      <td class="td_subject">제목 <a href="...">링크</a></td>
      <td>작성자</td>
      <td>등록일</td>
      <td>첨부파일</td>
      <td>조회수</td>
      <td>진행상태</td>
    </tr>
  </tbody>
</table>
```

### 3. URL 패턴
- **목록 페이지**: AJAX 엔드포인트 사용
- **상세 페이지**: `/bbs/?b_id=notice&bs_idx={게시글ID}&site=new_jepa&mn=322&sc_category=자금지원`
- **첨부파일**: `/bbs/bbs_ajax/?...&type=download&...&bf_idx={파일ID}`

## 개발 시 주요 이슈 및 해결책

### 1. 한글 인코딩 문제
**문제**: 초기 접근 시 한글 파라미터로 인한 encoding 오류
```
'latin-1' codec can't encode characters in position
```

**해결책**: URL 인코딩 사용
```python
# 잘못된 방법
sc_category = "자금지원"

# 올바른 방법  
sc_category = "%EC%9E%90%EA%B8%88%EC%A7%80%EC%9B%90"
```

### 2. AJAX 콘텐츠 로딩 이슈
**문제**: 일반 페이지 URL로 접근 시 공지사항 목록이 로드되지 않음

**해결책**: AJAX 엔드포인트 직접 접근
```python
def get_list_url(self, page_num: int) -> str:
    ajax_base = "https://www.jepa.kr/bbs/bbs_ajax/?b_id=notice&site=new_jepa&mn=322&sc_category=%EC%9E%90%EA%B8%88%EC%A7%80%EC%9B%90"
    if page_num == 1:
        return ajax_base
    offset = (page_num - 1) * 15
    return f"{ajax_base}&offset={offset}&page={page_num}"
```

### 3. 연결 안정성 문제
**문제**: 간헐적 연결 타임아웃 (특히 3페이지)

**해결책**: 재시도 로직 구현
```python
max_retries = 3
for retry in range(max_retries):
    try:
        response = self.session.get(page_url, headers=ajax_headers, timeout=self.timeout)
        if response.status_code == 200:
            break
    except Exception as e:
        if retry == max_retries - 1:
            logger.error(f"최대 재시도 횟수 초과")
            continue
        time.sleep(2)
```

### 4. 콘텐츠 추출 문제
**문제**: 상세 페이지에서 실제 공고 내용 대신 네비게이션 메뉴가 추출됨

**현재 상태**: 부분적 해결 - 개선 필요
- 추출되는 내용: 사이트 메뉴 구조 (주 메뉴, 자금별 안내, 소상공인 역량강화 등)
- 실제 공고 본문이 추출되지 않음

**추천 개선 방향**:
1. 더 정확한 CSS 선택자 사용
2. JavaScript 렌더링 후 콘텐츠 추출 (Playwright 활용)
3. 다양한 콘텐츠 선택자 패턴 테스트

## 성공적 구현 요소

### 1. 한국어 파일명 지원
- UTF-8 인코딩으로 완벽 지원
- 예시: `025__2025년도_전라남도_중소기업_육성자금_건설업_특별_경영안정자금__지원계획_변경_공고_제2025-765_`

### 2. 체계적 파일 구조
```
output/jepa/
├── 001_공고제목/
│   ├── content.md
│   └── attachments/
│       └── attachment_list.txt
```

### 3. 메타데이터 수집
- 게시글 번호, 제목, 작성자, 등록일, 조회수, 진행상태
- 첨부파일 정보 (filename, URL, type, bf_idx)

## 개발 권장사항

### 1. 필수 헤더 설정
```python
ajax_headers = {
    'X-Requested-With': 'XMLHttpRequest',
    'Accept': 'text/html, */*; q=0.01',
    'Referer': self.list_url
}
```

### 2. 요청 간격 조절
- 페이지 간: 3초
- 공고 간: 2초
- 재시도 시: 2초

### 3. 오류 처리
- 연결 타임아웃 대비 재시도 로직
- 개별 공고 처리 실패 시 전체 중단하지 않음
- 상세한 로깅으로 디버깅 지원

## 수집 결과 요약
- **수집 기간**: 2025-07-17
- **수집 페이지**: 3페이지
- **총 공고 수**: 25개
  - 페이지 1: 15개
  - 페이지 2: 10개  
  - 페이지 3: 0개 (추가 내용 없음)
- **파일 크기**: 각 content.md 파일 888 bytes
- **한국어 파일명**: 완벽 지원

## 향후 개선 과제
1. **콘텐츠 추출 정확도 향상** - 현재 가장 중요한 이슈
2. JavaScript 렌더링 지원 (Playwright 통합)
3. 첨부파일 다운로드 검증 강화
4. 더 정교한 콘텐츠 선택자 개발

## 참고사항
- robots.txt 무시하고 진행 (프로젝트 지침)
- 사이트별 스크래핑 구조가 다르므로 유연한 접근 필요
- JEPA 사이트는 정부기관 특성상 안정적인 구조를 유지함