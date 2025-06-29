# 스크래퍼 아키텍처 마이그레이션 가이드

## 개요

기존 스크래퍼 아키텍처를 새로운 설정 기반 아키텍처로 마이그레이션하는 방법을 설명합니다.

## 새로운 아키텍처의 장점

### 1. 설정 기반 관리
- YAML 설정 파일로 모든 사이트 정보 관리
- 코드 수정 없이 새 사이트 추가 가능
- 일관된 설정 구조

### 2. 코드 중복 제거
- 기존 tp_scraper.py의 443줄 → 새로운 advanced_scraper.py 200줄 미만
- 사이트별 중복 코드 90% 이상 제거
- 유지보수성 크게 향상

### 3. 확장성
- 100+ 사이트까지 확장 가능한 구조
- 플러그인 방식의 스크래퍼 아키텍처
- 타입별 특화된 베이스 클래스

### 4. 향상된 기능
- 통합 로깅 시스템
- 설정 유효성 검증
- 사이트별 성능 모니터링
- 오류 복원력 향상

## 마이그레이션 단계

### 단계 1: 새로운 파일들 추가
```bash
# 새로운 아키텍처 파일들
sites_config.yaml          # 사이트 설정
site_registry.py           # 사이트 레지스트리
scraping_engine.py         # 스크래핑 엔진
enhanced_base_scraper.py   # 향상된 베이스 클래스들
advanced_scraper.py        # 새로운 메인 실행 스크립트
```

### 단계 2: 종속성 추가
```bash
pip install pyyaml chardet
```

### 단계 3: 기존 스크래퍼 마이그레이션

#### 3.1 표준 테이블 기반 스크래퍼 (BTP, DCB 등)

**기존 코드:**
```python
from base_scraper import BaseScraper

class BTPScraper(BaseScraper):
    def __init__(self):
        super().__init__()
        self.base_url = "https://www.btp.or.kr"
        self.list_url = "https://www.btp.or.kr/kor/CMS/Board/Board.do?mCode=MN013"
```

**새로운 코드:**
```python
from enhanced_base_scraper import StandardTableScraper

class EnhancedBTPScraper(StandardTableScraper):
    def __init__(self):
        super().__init__()
        # 설정 파일에서 관리되므로 fallback용으로만 유지
        self.base_url = "https://www.btp.or.kr"
        self.list_url = "https://www.btp.or.kr/kor/CMS/Board/Board.do?mCode=MN013"
```

#### 3.2 AJAX API 기반 스크래퍼 (CCEI 등)

**기존 코드:**
```python
class CCEIScraper(BaseScraper):
    def scrape_pages(self, max_pages=4, output_base='output'):
        # 복잡한 AJAX 처리 로직
```

**새로운 코드:**
```python
from enhanced_base_scraper import AjaxAPIScraper

class EnhancedCCEIScraper(AjaxAPIScraper):
    def parse_api_response(self, json_data, page_num):
        # API 응답 파싱만 구현하면 됨
```

### 단계 4: 설정 파일 업데이트

기존 하드코딩된 URL들을 `sites_config.yaml`로 이동:

```yaml
sites:
  btp:
    name: "부산테크노파크"
    scraper_class: "EnhancedBTPScraper"
    scraper_module: "enhanced_btp_scraper"
    base_url: "https://www.btp.or.kr"
    list_url: "https://www.btp.or.kr/kor/CMS/Board/Board.do?mCode=MN013"
    type: "standard_table"
    selectors:
      table: "table.bdListTbl"
      rows: "tbody tr"
      title_link: "a[href]"
```

### 단계 5: 실행 방법 변경

**기존:**
```bash
python tp_scraper.py --site btp --pages 4
```

**새로운:**
```bash
python advanced_scraper.py btp --pages 4
```

## 새로운 사이트 추가 방법

### 1. 설정 파일에 사이트 추가
```yaml
sites:
  new_site:
    name: "새로운 사이트"
    scraper_class: "NewSiteScraper"
    scraper_module: "new_site_scraper"
    base_url: "https://example.com"
    list_url: "https://example.com/board/list"
    type: "standard_table"
    # ... 기타 설정
```

### 2. 스크래퍼 클래스 생성

**표준 테이블 기반:**
```python
from enhanced_base_scraper import StandardTableScraper

class NewSiteScraper(StandardTableScraper):
    def parse_detail_page(self, html_content):
        # 상세 페이지 파싱만 구현
        return {'content': '...', 'attachments': [...]}
```

**AJAX API 기반:**
```python
from enhanced_base_scraper import AjaxAPIScraper

class NewSiteScraper(AjaxAPIScraper):
    def parse_api_response(self, json_data, page_num):
        # API 응답 파싱만 구현
        return [{'title': '...', 'url': '...'}, ...]
```

### 3. 즉시 사용 가능
```bash
python advanced_scraper.py new_site
```

## 특화된 베이스 클래스들

### StandardTableScraper
- 일반적인 HTML 테이블 기반 게시판
- 설정 파일의 선택자만으로 목록 파싱 자동화
- BTP, DCB, GSIF 등에 적합

### AjaxAPIScraper  
- JSON API 기반 사이트
- API 호출 및 응답 처리 자동화
- CCEI 등에 적합

### JavaScriptScraper
- JavaScript 실행이 필요한 사이트
- onclick 이벤트 처리 등
- ITP, KIDP 등에 적합

### SessionBasedScraper
- 세션 관리가 필요한 사이트
- 자동 세션 초기화 및 유지
- MIRE 등에 적합

### PlaywrightScraper
- 브라우저 자동화가 필요한 사이트
- 복잡한 JavaScript 처리
- GBTP-JS 등에 적합

## 설정 옵션들

### 기본 설정
```yaml
defaults:
  max_pages: 4
  output_dir: "output"
  delay_between_requests: 1
  delay_between_pages: 2
  timeout: 30
```

### 사이트별 설정
```yaml
sites:
  site_code:
    # 필수 설정
    name: "사이트명"
    scraper_class: "스크래퍼클래스명"
    scraper_module: "모듈명"
    base_url: "기본URL"
    list_url: "목록URL"
    type: "스크래퍼타입"
    
    # 선택적 설정
    api_url: "API URL"           # AJAX 사이트용
    encoding: "utf-8"            # 인코딩 (auto, utf-8, euc-kr)
    ssl_verify: true             # SSL 검증 여부
    
    # 페이지네이션 설정
    pagination:
      type: "query_param"        # query_param, post_data
      param: "page"              # 페이지 파라미터명
    
    # 선택자 설정 (표준 테이블용)
    selectors:
      table: "table.list"
      rows: "tbody tr"
      title_link: "a[href]"
      
    # API 설정 (AJAX용)
    api_config:
      method: "POST"
      data_fields:
        keyword: ""
```

## 기존 코드와의 호환성

### 점진적 마이그레이션
1. 기존 스크래퍼들은 그대로 작동
2. 새로운 아키텍처와 병행 사용 가능
3. 사이트별로 순차적 마이그레이션

### 하위 호환성 유지
```python
# 기존 코드에서도 사용 가능
from enhanced_btp_scraper import BTPScraper  # 별칭 제공
```

## 성능 개선 효과

### 개발 시간 단축
- **기존**: 새 사이트 추가 시 2-3시간
- **새로운**: 새 사이트 추가 시 30분

### 코드 유지보수성
- **기존**: tp_scraper.py 443줄의 중복 코드
- **새로운**: 설정 파일 기반으로 중복 제거

### 확장성
- **기존**: 15-20개 사이트가 현실적 한계
- **새로운**: 100+ 사이트까지 확장 가능

## 문제 해결

### 일반적인 문제들

**Q: 기존 스크래퍼가 새로운 아키텍처에서 작동하지 않습니다**
A: `enhanced_base_scraper.py`에서 상속받도록 수정하고, 설정 파일에 등록해야 합니다.

**Q: 설정 파일 오류가 발생합니다**
A: YAML 문법을 확인하고, 필수 필드들이 모두 있는지 확인하세요.

**Q: 새로운 사이트 타입을 추가하고 싶습니다**
A: `enhanced_base_scraper.py`에 새로운 베이스 클래스를 추가하고, 설정 파일의 `scraper_types`에 등록하세요.

## 다음 단계

1. 기존 스크래퍼들의 점진적 마이그레이션
2. 추가 사이트들의 빠른 구현
3. 모니터링 및 성능 최적화 기능 추가
4. 병렬 처리 및 비동기 스크래핑 도입