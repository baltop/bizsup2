# Injeart Scraper Development Insights

## 사이트 정보
- **URL**: http://www.injeart.or.kr/?p=19&page=1
- **사이트 코드**: injeart
- **사이트명**: 인제군문화재단 공지사항

## 개발 과정 및 발견사항

### 1. 사이트 구조 분석
- **페이지네이션**: GET 방식, `&page=` 파라미터 사용
- **목록 테이블**: 표준 HTML table 구조
- **컬럼 구조**: 번호, 분류, 제목, 등록일, 조회수 (5개 컬럼)

### 2. 주요 기술적 발견

#### URL 패턴 버그 수정
- **문제**: 기존 코드에 중복 page 파라미터 존재
  ```python
  # 잘못된 URL (버그)
  f"{self.base_url}/?p=19&page=1&page={page_num}"
  
  # 수정된 URL
  f"{self.base_url}/?p=19&page={page_num}"
  ```

#### 테이블 파싱 최적화
- **기존**: 복잡한 테이블 찾기 로직 (특정 헤더 검색)
- **개선**: 단순화된 파싱 (`soup.find('table')` 첫 번째 테이블 사용)
- **이유**: injeart 사이트는 첫 번째 테이블이 공고 목록 테이블

### 3. 첨부파일 처리 특성

#### chkDownAuth() JavaScript 패턴
- **패턴**: `chkDownAuth('202507181020209469')`
- **다운로드 URL**: `/inc/down.php?fileidx={file_id}`
- **처리**: 정규표현식으로 파일 ID 추출

```python
match = re.search(r"chkDownAuth\('([^']+)'\)", onclick)
if match and filename:
    file_id = match.group(1)
    download_url = f"{self.base_url}/inc/down.php?fileidx={file_id}"
```

### 4. 한글 파일명 처리
- **인코딩**: UTF-8 완전 지원
- **파일 형식**: HWP, PDF 등 한국어 파일명 정상 처리
- **검증**: 1페이지 테스트에서 12개 첨부파일 정상 다운로드 확인

### 5. 성능 및 안정성

#### 파일 검증 로직
```python
# HTML 페이지 다운로드 감지
if file_size < 1024:
    with open(save_path, 'rb') as f:
        content = f.read(500).decode('utf-8', errors='ignore')
        if '<html' in content.lower() or '<!doctype' in content.lower():
            logger.warning(f"HTML 페이지가 다운로드됨. 파일 삭제: {save_path}")
            os.remove(save_path)
            return False
```

#### 요청 간격 및 안정성
- **딜레이**: 1초 간격 (서버 부하 방지)
- **타임아웃**: 30초
- **재시도**: 기본 스크래퍼의 재시도 메커니즘 활용

### 6. 테스트 결과

#### 1페이지 테스트
- **공고 수**: 10개
- **첨부파일**: 12개 (HWP, PDF)
- **한글 파일명**: 정상 처리
- **중복 방지**: processed_titles_enhancedinjeart.json 생성

#### 3페이지 전체 테스트
- **총 공고 수**: 30개 (10 × 3페이지)
- **전체 첨부파일**: 정상 다운로드
- **폴더 구조**: output/injeart/{번호_제목}/content.md, attachments/

### 7. 개발자 권장사항

#### 디버깅 팁
1. **URL 확인**: 중복 파라미터 주의
2. **테이블 구조**: 첫 번째 테이블이 목록인지 확인
3. **JavaScript 패턴**: chkDownAuth() 함수 존재 여부 확인

#### 성능 최적화
1. **단순한 파싱**: 복잡한 선택자보다 기본 태그 우선 사용
2. **파일 검증**: HTML 응답 감지로 오류 파일 방지
3. **로깅**: 상세한 로그로 디버깅 지원

### 8. 주의사항
- **세션 관리**: 필요 시 초기화
- **인코딩**: UTF-8 완전 지원 확인
- **파일 크기**: 1KB 미만 파일 HTML 검증 필수
- **중복 방지**: JSON 파일 생성 및 활용

### 9. 성공 요인
1. **기존 코드 분석**: 버그 식별 및 수정
2. **단계별 테스트**: 1페이지 → 3페이지 순차 검증
3. **한글 지원**: 완전한 UTF-8 처리
4. **안정성**: 파일 검증 및 오류 처리

이 인사이트는 향후 유사한 정부/공공기관 사이트 스크래핑 시 참고할 수 있는 가이드라인을 제공합니다.