# -*- coding: utf-8 -*-
"""
Enhanced 함안상공회의소 스크래퍼
URL: https://hamancci.korcham.net/front/board/boardContentsListPage.do?boardId=10521&menuId=10057
"""

import re
import logging
import os
from urllib.parse import urljoin, unquote
from bs4 import BeautifulSoup
from enhanced_base_scraper import StandardTableScraper

logger = logging.getLogger(__name__)

class EnhancedHamanCCIScraper(StandardTableScraper):
    """함안상공회의소 전용 스크래퍼 - Enhanced 버전"""
    
    def __init__(self):
        super().__init__()
        
        # 기본 설정
        self.base_url = "https://hamancci.korcham.net"
        self.list_url = "https://hamancci.korcham.net/front/board/boardContentsListPage.do?boardId=10521&menuId=10057"
        
        # 사이트별 특화 설정
        self.verify_ssl = True
        self.default_encoding = 'utf-8'
        self.timeout = 30
        self.delay_between_requests = 1
        
        # 페이지네이션 설정
        self.page_param = 'miv_pageNo'
        
        logger.info("함안상공회의소 스크래퍼 초기화 완료")

    def get_list_url(self, page_num: int) -> str:
        """페이지별 URL 생성 - AJAX API 방식"""
        # AJAX API URL 사용
        return f"{self.base_url}/front/board/boardContentsList.do"
    
    def _get_page_announcements(self, page_num: int) -> list:
        """AJAX API를 통한 공고 목록 가져오기"""
        api_url = self.get_list_url(page_num)
        
        # AJAX 요청 데이터 구성
        data = {
            'miv_pageNo': str(page_num),
            'miv_pageSize': '15',
            'total_cnt': '',
            'LISTOP': '',
            'mode': 'W',
            'contId': '',
            'delYn': 'N',
            'menuId': '10057',
            'boardId': '10521',
            'readRat': 'A',
            'boardCd': 'N',
            'searchKey': 'A',
            'searchTxt': ''
        }
        
        # POST 요청으로 AJAX API 호출
        response = self.post_page(api_url, data=data)
        
        if not response:
            logger.warning(f"AJAX API 호출 실패 - 페이지 {page_num}")
            return []
        
        if response.status_code != 200:
            logger.warning(f"AJAX API HTTP 에러 {response.status_code} - 페이지 {page_num}")
            return []
        
        # HTML 응답 파싱
        return self.parse_list_page(response.text)

    def parse_list_page(self, html_content: str) -> list:
        """목록 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        announcements = []
        
        # 테이블 찾기 - 여러 방법 시도
        table = soup.find('table', cellspacing="0")
        if not table:
            # 대안 1: class boardlist 내부의 테이블
            boardlist = soup.find('div', class_='boardlist')
            if boardlist:
                table = boardlist.find('table')
            
        if not table:
            # 대안 2: summary 속성이 있는 테이블
            table = soup.find('table', attrs={'summary': lambda x: x and '공지사항' in x})
            
        if not table:
            # 대안 3: 첫 번째 테이블
            table = soup.find('table')
            
        if not table:
            logger.warning("공고 테이블을 찾을 수 없습니다")
            # 디버깅을 위해 HTML 구조 일부 출력
            boardlist_div = soup.find('div', class_='boardlist')
            if boardlist_div:
                logger.info("boardlist div는 찾았지만 내부 테이블이 없습니다")
            else:
                logger.info("boardlist div를 찾을 수 없습니다")
            
            # 추가 디버깅: contents_detail div 확인
            contents_detail = soup.find('div', class_='contents_detail')
            if contents_detail:
                logger.info("contents_detail div 발견")
                # 이 div 내부에 AJAX로 로드되는 내용이 있을 수 있음
                scripts = soup.find_all('script')
                for script in scripts:
                    if 'boardLiat' in script.get_text():
                        logger.info("AJAX 로딩 스크립트 발견 - 동적 로딩이 필요할 수 있음")
                        break
            
            # HTML 구조 샘플 출력 (처음 1000자)
            logger.info(f"HTML 샘플 (처음 1000자): {html_content[:1000]}")
            return announcements
        
        tbody = table.find('tbody')
        if not tbody:
            tbody = table
        
        rows = tbody.find_all('tr')
        logger.info(f"총 {len(rows)}개 행 발견")
        
        for i, row in enumerate(rows):
            try:
                cells = row.find_all('td')
                if len(cells) < 3:
                    continue
                
                # 번호 (첫 번째 셀) - 공지 이미지 처리
                number_cell = cells[0]
                number = self.process_notice_detection(number_cell, i)
                
                # 제목 (두 번째 셀)
                title_cell = cells[1]
                link_elem = title_cell.find('a')
                
                if not link_elem:
                    continue
                
                title = link_elem.get_text(strip=True)
                if not title:
                    continue
                
                # JavaScript contentsView 함수에서 ID 추출
                onclick = link_elem.get('onclick', '') or link_elem.get('href', '')
                content_id = None
                
                # contentsView('114136') 패턴 찾기
                id_match = re.search(r"contentsView\('(\d+)'\)", onclick)
                if id_match:
                    content_id = id_match.group(1)
                    detail_url = f"{self.base_url}/front/board/boardContentsView.do?contId={content_id}&boardId=10521&menuId=10057"
                else:
                    # 직접 href가 있는 경우
                    href = link_elem.get('href', '')
                    if href:
                        detail_url = urljoin(self.base_url, href)
                    else:
                        logger.warning(f"링크를 찾을 수 없습니다: {title}")
                        continue
                
                # 작성일 (세 번째 셀)
                date = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                
                announcement = {
                    'title': title,
                    'url': detail_url,
                    'date': date,
                    'number': number
                }
                
                announcements.append(announcement)
                logger.info(f"공고 추가: [{number}] {title}")
                
            except Exception as e:
                logger.error(f"행 파싱 중 오류: {e}")
                continue
        
        logger.info(f"총 {len(announcements)}개 공고 추출 완료")
        return announcements

    def parse_detail_page(self, html_content: str) -> dict:
        """상세 페이지 파싱"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 본문 추출
        content_td = soup.find('td', class_='td_p')
        if content_td:
            # HTML을 마크다운으로 변환
            content = self.h.handle(str(content_td))
        else:
            # 대체 방법: boardveiw 테이블에서 내용 추출
            boardview = soup.find('div', class_='boardveiw')
            if boardview:
                # 테이블의 마지막 td (본문이 들어있는 td)
                content_rows = boardview.find_all('tr')
                content = ""
                for row in content_rows:
                    tds = row.find_all('td')
                    for td in tds:
                        if td.get('colspan') == '4' and 'td_p' in td.get('class', []):
                            content = self.h.handle(str(td))
                            break
                    if content:
                        break
            else:
                content = "본문을 찾을 수 없습니다."
        
        # 첨부파일 추출
        attachments = self._extract_attachments(soup)
        
        return {
            'content': content,
            'attachments': attachments
        }

    def _extract_attachments(self, soup: BeautifulSoup) -> list:
        """첨부파일 추출"""
        attachments = []
        
        # 첨부파일 영역 찾기
        file_list = soup.find('ul', class_='file_view')
        if not file_list:
            return attachments
        
        file_items = file_list.find_all('li')
        logger.info(f"{len(file_items)}개 첨부파일 링크 발견")
        
        for i, item in enumerate(file_items):
            try:
                link = item.find('a')
                if not link:
                    continue
                
                # 파일명 및 URL 추출
                filename = link.get_text(strip=True)
                href = link.get('href', '')
                
                if not href or not filename:
                    continue
                
                # URL 구성 - 완전한 URL인지 확인
                if href.startswith('http'):
                    file_url = href
                elif href.startswith('/'):
                    file_url = self.base_url + href
                else:
                    # 상대 경로인 경우
                    file_url = urljoin(self.base_url, href)
                
                # 파일명 정리
                clean_filename = self.sanitize_filename(filename)
                if not clean_filename:
                    clean_filename = f"attachment_{i+1}"
                
                attachment = {
                    'filename': clean_filename,
                    'url': file_url,
                    'original_name': filename
                }
                
                attachments.append(attachment)
                logger.info(f"첨부파일 추가: {clean_filename}")
                
            except Exception as e:
                logger.error(f"첨부파일 추출 중 오류: {e}")
                continue
        
        return attachments

    def download_file(self, url: str, save_path: str, attachment_info: dict = None) -> bool:
        """파일 다운로드 - 함안상공회의소 특화"""
        try:
            logger.info(f"파일 다운로드 시작: {url}")
            
            # 다운로드 헤더 설정
            download_headers = self.headers.copy()
            download_headers['Referer'] = self.base_url
            
            # URL 파라미터 확인 및 수정
            if '/file/dext5uploaddata/' in url and not url.startswith('http'):
                # 상대 경로를 절대 경로로 변환
                if url.startswith('/'):
                    url = self.base_url + url
                else:
                    url = urljoin(self.base_url, url)
            
            response = self.session.get(
                url,
                headers=download_headers,
                stream=True,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            
            # 상태 코드 확인
            if response.status_code != 200:
                logger.warning(f"파일 다운로드 실패 - HTTP {response.status_code}: {url}")
                return False
            
            # Content-Disposition에서 실제 파일명 추출
            actual_filename = self._extract_filename_from_response(response, save_path)
            if actual_filename != save_path:
                save_path = actual_filename
            
            # 파일 저장
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(save_path)
            logger.info(f"다운로드 완료: {save_path} ({file_size:,} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"파일 다운로드 실패 {url}: {e}")
            return False

    def _extract_filename_from_response(self, response, default_path):
        """응답에서 실제 파일명 추출 - 함안상공회의소 특화"""
        import os
        from urllib.parse import unquote
        
        content_disposition = response.headers.get('Content-Disposition', '')
        save_dir = os.path.dirname(default_path)
        
        if content_disposition:
            # RFC 5987 형식 우선 처리
            rfc5987_match = re.search(r"filename\*=([^']*)'([^']*)'(.+)", content_disposition)
            if rfc5987_match:
                encoding, lang, filename = rfc5987_match.groups()
                try:
                    filename = unquote(filename, encoding=encoding or 'utf-8')
                    return os.path.join(save_dir, self.sanitize_filename(filename))
                except:
                    pass
            
            # 일반 filename 파라미터 처리
            filename_match = re.search(r'filename[^;=\n]*=([\'"]*)(.*?)\1', content_disposition)
            if filename_match:
                filename = filename_match.group(2)
                
                # 다양한 인코딩 시도
                for encoding in ['utf-8', 'euc-kr', 'cp949']:
                    try:
                        if encoding == 'utf-8':
                            decoded = filename.encode('latin-1').decode('utf-8')
                        else:
                            decoded = filename.encode('latin-1').decode(encoding)
                        
                        if decoded and not decoded.isspace():
                            clean_filename = self.sanitize_filename(decoded.replace('+', ' '))
                            return os.path.join(save_dir, clean_filename)
                    except:
                        continue
        
        return default_path


def test_hamancci_scraper(pages=3):
    """함안상공회의소 스크래퍼 테스트"""
    import os
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    scraper = EnhancedHamanCCIScraper()
    output_dir = "output/hamancci"
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"함안상공회의소 스크래퍼 테스트 시작 - {pages}페이지")
    
    try:
        scraper.scrape_pages(max_pages=pages, output_base=output_dir)
        logger.info("스크래핑 완료!")
        
        # 결과 확인
        result_folders = [f for f in os.listdir(output_dir) if os.path.isdir(os.path.join(output_dir, f))]
        print(f"\n✅ 함안상공회의소 테스트 결과:")
        print(f"   수집 공고: {len(result_folders)}개")
        print(f"   저장 위치: {output_dir}")
        
        # 첨부파일 확인
        total_files = 0
        for folder in result_folders:
            attachments_dir = os.path.join(output_dir, folder, 'attachments')
            if os.path.exists(attachments_dir):
                files = os.listdir(attachments_dir)
                total_files += len(files)
        
        print(f"   첨부파일: {total_files}개")
        
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {e}")


if __name__ == "__main__":
    # 3페이지 테스트
    test_hamancci_scraper(3)