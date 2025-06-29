# 지원사업 공고 수집 프로그램

여러 기관의 지원사업 공고를 자동으로 수집하는 웹 스크래퍼 프로그램입니다.

## 지원 기관

### 완전 구현됨
- **BTP** (부산테크노파크): 공고 수집 ✅, 첨부파일 ✅
- **ITP** (인천테크노파크): 공고 수집 ✅, 첨부파일 ❌ (JavaScript 보안)
- **CCEI** (충북창조경제혁신센터): 공고 수집 ✅, 첨부파일 ✅
- **KIDP** (한국디자인진흥원): 공고 수집 ✅, 첨부파일 ❌ (JavaScript 처리 필요)

### 부분 구현됨
- **GSIF** (강릉과학산업진흥원): 기본 구조 구현
- **DJBEA** (대전일자리경제진흥원): 기본 구조 구현
- **MIRE** (환동해산업연구원): 기본 구조 구현
- **DCB** (부산디자인진흥원): 템플릿만 구현

### 미구현 (sitelist.csv에 있음)
- GEPA (광주광역시 기업지원시스템)
- JBF (전남바이오진흥원)
- CEPA (충남경제진흥원)
- CheongjuCCI (청주상공회의소)
- GIB (경북바이오산업연구원)
- GBTP (경북테크노파크)
- DGDP (대구경북디자인진흥원)

## 설치

### 필요 패키지
```bash
pip install requests beautifulsoup4 html2text
```

## 사용법

### 1. 개별 사이트 수집
```bash
# 부산테크노파크 4페이지 수집 (기본값)
python tp_scraper.py --site btp

# 인천테크노파크 2페이지만 수집
python tp_scraper.py --site itp --pages 2

# 모든 구현된 사이트 수집
python tp_scraper.py --site all
```

### 2. CSV 파일 기반 자동 수집
```bash
# sitelist.csv의 모든 사이트 수집
python scrape_from_csv.py

# 특정 사이트만 수집
python scrape_from_csv.py --site gsif

# 각 사이트 2페이지씩만 수집
python scrape_from_csv.py --pages 2
```

### 3. 지원 사이트 코드
- `btp`: 부산테크노파크
- `itp`: 인천테크노파크
- `ccei`: 충북창조경제혁신센터
- `kidp`: 한국디자인진흥원
- `gsif`: 강릉과학산업진흥원
- `djbea`: 대전일자리경제진흥원
- `mire`: 환동해산업연구원
- `dcb`: 부산디자인진흥원

## 출력 구조

수집된 데이터는 다음과 같은 구조로 저장됩니다:

```
output/
├── btp/
│   ├── 001_공고제목/
│   │   ├── content.md          # 공고 본문 (Markdown)
│   │   └── attachments/        # 첨부파일
│   │       ├── 파일1.hwp
│   │       └── 파일2.pdf
│   └── 002_다른공고제목/
│       └── content.md
├── itp/
├── ccei/
└── ...
```

## 프로젝트 구조

```
btp_scraper/
├── base_scraper.py        # 추상 기본 클래스
├── btp_scraper.py         # 부산테크노파크 스크래퍼
├── itp_scraper.py         # 인천테크노파크 스크래퍼
├── ccei_scraper.py        # 충북창조경제혁신센터 스크래퍼
├── kidp_scraper.py        # 한국디자인진흥원 스크래퍼
├── gsif_scraper.py        # 강릉과학산업진흥원 스크래퍼
├── djbea_scraper.py       # 대전일자리경제진흥원 스크래퍼
├── mire_scraper.py        # 환동해산업연구원 스크래퍼
├── site_scrapers.py       # 기타 사이트 스크래퍼 모음
├── tp_scraper.py          # 통합 실행 스크립트
├── scrape_from_csv.py     # CSV 기반 자동 실행 스크립트
├── sitelist.csv           # 사이트 목록
├── CLAUDE.md              # 프로젝트 가이드라인
├── claude_code_log.txt    # 개발 로그
└── README.md              # 이 파일
```

## 새로운 사이트 추가하기

새로운 사이트를 추가하려면:

1. `base_scraper.py`를 상속받는 새 스크래퍼 클래스 생성
2. 필수 메서드 구현:
   - `get_list_url(page_num)`: 페이지별 URL 생성
   - `parse_list_page(html_content)`: 목록 페이지 파싱
   - `parse_detail_page(html_content)`: 상세 페이지 파싱
3. `tp_scraper.py`에 새 사이트 추가
4. `sitelist.csv`에 사이트 정보 추가

자세한 가이드는 [CLAUDE.md](CLAUDE.md) 파일을 참조하세요.

## 주의사항

1. **서버 부하 방지**: 각 요청 사이에 1초 대기 시간이 있습니다.
2. **User-Agent**: 일부 사이트는 브라우저 User-Agent가 필요합니다.
3. **JavaScript**: 일부 사이트는 JavaScript 렌더링이 필요하여 완전한 기능을 위해서는 Playwright 등이 필요할 수 있습니다.
4. **SSL 인증서**: 일부 사이트는 SSL 인증서 검증을 비활성화해야 합니다.

## 문제 해결

### 첨부파일이 다운로드되지 않는 경우
- JavaScript로 보호된 다운로드일 수 있습니다.
- 세션 쿠키가 필요할 수 있습니다.
- 브라우저 자동화 도구(Playwright)가 필요할 수 있습니다.

### 페이지가 로드되지 않는 경우
- User-Agent 헤더를 확인하세요.
- SSL 인증서 오류인지 확인하세요.
- 사이트가 IP를 차단했을 수 있습니다.

## 라이선스

이 프로젝트는 교육 및 연구 목적으로만 사용해야 합니다.
각 사이트의 이용약관을 준수하여 사용하세요.