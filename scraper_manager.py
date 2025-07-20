# -*- coding: utf-8 -*-
"""
Enhanced 스크래퍼 관리자 - 여러 스크래퍼를 병렬로 실행
"""

import os
import sys
import argparse
import importlib
import threading
import time
import glob
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import json
from typing import List, Dict, Any
from datetime import datetime

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('scraper_manager.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

class ScraperManager:
    """Enhanced 스크래퍼 병렬 실행 관리자"""
    
    def __init__(self, output_base_dir="output", max_pages=3, max_workers=30):
        self.output_base_dir = output_base_dir
        self.max_pages = max_pages
        self.max_workers = max_workers
        self.lock_dir = Path("locks")
        self.lock_dir.mkdir(exist_ok=True)
        self.results = {}
        self.start_time = None
        
    def get_available_scrapers(self) -> List[str]:
        """사용 가능한 enhanced 스크래퍼 목록을 알파벳 순으로 반환"""
        scrapers = []
        pattern = "enhanced_*_scraper.py"
        
        for file_path in sorted(glob.glob(pattern)):
            if os.path.isfile(file_path):
                # enhanced_base_scraper.py와 enhanced_async_scraper.py는 제외
                if file_path not in ["enhanced_base_scraper.py", "enhanced_async_scraper.py"]:
                    scrapers.append(file_path)
                    
        return scrapers
    
    def extract_site_code(self, scraper_file: str) -> str:
        """스크래퍼 파일명에서 사이트 코드 추출"""
        # enhanced_kidp_scraper.py -> kidp
        filename = os.path.basename(scraper_file)
        return filename.replace("enhanced_", "").replace("_scraper.py", "")
    
    def is_scraper_running(self, site_code: str) -> bool:
        """스크래퍼가 이미 실행 중인지 확인 (락 파일 기반)"""
        lock_file = self.lock_dir / f"{site_code}.lock"
        
        if lock_file.exists():
            try:
                # 락 파일이 있으면 프로세스 존재 여부 확인
                with open(lock_file, 'r', encoding='utf-8') as f:
                    lock_data = json.load(f)
                
                # 5분 이상 된 락 파일은 stale로 간주
                lock_time = datetime.fromisoformat(lock_data.get('start_time', ''))
                if (datetime.now() - lock_time).total_seconds() > 300:
                    logger.warning(f"{site_code}: 오래된 락 파일 감지, 삭제 중...")
                    lock_file.unlink()
                    return False
                
                logger.info(f"{site_code}: 이미 실행 중 (PID: {lock_data.get('pid', 'unknown')})")
                return True
                
            except (json.JSONDecodeError, ValueError, KeyError):
                # 손상된 락 파일은 삭제
                logger.warning(f"{site_code}: 손상된 락 파일 삭제")
                lock_file.unlink()
                return False
        
        return False
    
    def create_lock_file(self, site_code: str):
        """락 파일 생성"""
        lock_file = self.lock_dir / f"{site_code}.lock"
        lock_data = {
            'pid': os.getpid(),
            'start_time': datetime.now().isoformat(),
            'site_code': site_code
        }
        
        with open(lock_file, 'w', encoding='utf-8') as f:
            json.dump(lock_data, f, ensure_ascii=False, indent=2)
    
    def remove_lock_file(self, site_code: str):
        """락 파일 삭제"""
        lock_file = self.lock_dir / f"{site_code}.lock"
        if lock_file.exists():
            try:
                lock_file.unlink()
                logger.debug(f"{site_code}: 락 파일 삭제 완료")
            except Exception as e:
                logger.warning(f"{site_code}: 락 파일 삭제 실패 - {e}")
    
    def load_scraper_class(self, scraper_file: str):
        """스크래퍼 파일에서 클래스 동적 로드"""
        import importlib.util
        try:
            # 파일명에서 모듈명 추출 (확장자 제거)
            module_name = os.path.basename(scraper_file).replace('.py', '')
            
            # 동적 import
            spec = importlib.util.spec_from_file_location(module_name, scraper_file)
            if spec is None or spec.loader is None:
                raise ImportError(f"모듈 스펙 로드 실패: {scraper_file}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Enhanced{SiteCode}Scraper 클래스명 패턴으로 찾기
            site_code = self.extract_site_code(scraper_file)
            class_name = f"Enhanced{site_code.upper()}Scraper"
            
            # 실제 클래스명이 다를 수 있으므로 여러 패턴으로 시도
            possible_names = [
                class_name,
                f"Enhanced{site_code.capitalize()}Scraper",
                f"Enhanced{site_code}Scraper"
            ]
            
            scraper_class = None
            for name in possible_names:
                if hasattr(module, name):
                    scraper_class = getattr(module, name)
                    break
            
            # 패턴으로 찾지 못하면 모든 클래스를 검사
            if scraper_class is None:
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        attr_name.startswith('Enhanced') and 
                        attr_name.endswith('Scraper') and
                        attr_name != 'EnhancedBaseScraper'):
                        scraper_class = attr
                        break
            
            if scraper_class is None:
                raise ImportError(f"스크래퍼 클래스를 찾을 수 없음: {scraper_file}")
            
            return scraper_class
            
        except Exception as e:
            logger.error(f"스크래퍼 로드 실패 {scraper_file}: {e}")
            return None
    
    def run_single_scraper(self, scraper_file: str) -> Dict[str, Any]:
        """단일 스크래퍼 실행"""
        site_code = self.extract_site_code(scraper_file)
        output_dir = os.path.join(self.output_base_dir, site_code)
        
        result = {
            'site_code': site_code,
            'scraper_file': scraper_file,
            'status': 'failed',
            'output_dir': output_dir,
            'start_time': None,
            'end_time': None,
            'duration': 0,
            'error': None,
            'stats': {}
        }
        
        try:
            # 이중 실행 방지 확인
            if self.is_scraper_running(site_code):
                result['status'] = 'skipped'
                result['error'] = 'Already running'
                return result
            
            # 락 파일 생성
            self.create_lock_file(site_code)
            
            result['start_time'] = datetime.now()
            logger.info(f"{site_code}: 스크래핑 시작 ({scraper_file})")
            
            # 출력 디렉토리 생성
            os.makedirs(output_dir, exist_ok=True)
            
            # 스크래퍼 클래스 로드
            scraper_class = self.load_scraper_class(scraper_file)
            if scraper_class is None:
                raise Exception("스크래퍼 클래스 로드 실패")
            
            # 스크래퍼 인스턴스 생성 및 실행
            scraper = scraper_class()
            # signal 핸들러는 메인 스레드가 아니면 설정하지 않음
            if hasattr(scraper, '_setup_signal_handlers'):
                try:
                    scraper._setup_signal_handlers()
                except ValueError:
                    # signal은 메인 스레드에서만 작동하므로 무시
                    pass
            scraper.scrape_pages(max_pages=self.max_pages, output_base=output_dir)
            
            result['end_time'] = datetime.now()
            result['duration'] = (result['end_time'] - result['start_time']).total_seconds()
            result['status'] = 'completed'
            
            # 통계 정보 수집
            if hasattr(scraper, 'stats'):
                result['stats'] = scraper.stats.copy()
            
            logger.info(f"{site_code}: 완료 ({result['duration']:.1f}초)")
            
        except Exception as e:
            result['end_time'] = datetime.now()
            if result['start_time']:
                result['duration'] = (result['end_time'] - result['start_time']).total_seconds()
            result['error'] = str(e)
            logger.error(f"{site_code}: 실패 - {e}")
            
        finally:
            # 락 파일 정리
            self.remove_lock_file(site_code)
        
        return result
    
    def run_parallel_scrapers(self, scraper_count: int = 30):
        """병렬로 여러 스크래퍼 실행"""
        available_scrapers = self.get_available_scrapers()
        
        if not available_scrapers:
            logger.error("실행 가능한 스크래퍼가 없습니다.")
            return
        
        # 요청된 개수만큼 스크래퍼 선택 (알파벳 순)
        selected_scrapers = available_scrapers[:scraper_count]
        
        logger.info(f"총 {len(selected_scrapers)}개 스크래퍼 병렬 실행 시작")
        logger.info(f"출력 디렉토리: {self.output_base_dir}")
        logger.info(f"최대 페이지 수: {self.max_pages}")
        logger.info(f"최대 워커 수: {self.max_workers}")
        
        self.start_time = datetime.now()
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 모든 스크래퍼 작업 제출
            future_to_scraper = {
                executor.submit(self.run_single_scraper, scraper_file): scraper_file 
                for scraper_file in selected_scrapers
            }
            
            # 완료된 작업들 처리
            completed_count = 0
            for future in as_completed(future_to_scraper):
                scraper_file = future_to_scraper[future]
                try:
                    result = future.result()
                    self.results[result['site_code']] = result
                    completed_count += 1
                    
                    progress = (completed_count / len(selected_scrapers)) * 100
                    logger.info(f"진행률: {progress:.1f}% ({completed_count}/{len(selected_scrapers)})")
                    
                except Exception as exc:
                    site_code = self.extract_site_code(scraper_file)
                    logger.error(f"{site_code}: 예외 발생 - {exc}")
        
        # 실행 결과 요약
        self.print_summary()
    
    def print_summary(self):
        """실행 결과 요약 출력"""
        if not self.results:
            return
        
        total_time = (datetime.now() - self.start_time).total_seconds()
        
        completed = [r for r in self.results.values() if r['status'] == 'completed']
        failed = [r for r in self.results.values() if r['status'] == 'failed']
        skipped = [r for r in self.results.values() if r['status'] == 'skipped']
        
        print("\n" + "="*80)
        print("스크래퍼 병렬 실행 결과 요약")
        print("="*80)
        print(f"전체 실행 시간: {total_time:.1f}초")
        print(f"총 스크래퍼 수: {len(self.results)}")
        print(f"성공: {len(completed)}개")
        print(f"실패: {len(failed)}개")
        print(f"건너뜀: {len(skipped)}개")
        
        if completed:
            print(f"\n✅ 성공한 스크래퍼들:")
            for result in sorted(completed, key=lambda x: x['site_code']):
                stats = result['stats']
                print(f"  - {result['site_code']}: {result['duration']:.1f}초, "
                      f"게시글 {stats.get('total_posts', 0)}개, "
                      f"파일 {stats.get('files_downloaded', 0)}개")
        
        if failed:
            print(f"\n❌ 실패한 스크래퍼들:")
            for result in sorted(failed, key=lambda x: x['site_code']):
                print(f"  - {result['site_code']}: {result['error']}")
        
        if skipped:
            print(f"\n⏭️  건너뛴 스크래퍼들:")
            for result in sorted(skipped, key=lambda x: x['site_code']):
                print(f"  - {result['site_code']}: {result['error']}")
        
        print("="*80)


def main():
    parser = argparse.ArgumentParser(description='Enhanced 스크래퍼 병렬 실행 관리자')
    parser.add_argument('--output-dir', '-o', default='output', 
                       help='출력 디렉토리 (기본값: output)')
    parser.add_argument('--pages', '-p', type=int, default=3,
                       help='수집할 페이지 수 (기본값: 3)')
    parser.add_argument('--count', '-c', type=int, default=30,
                       help='실행할 스크래퍼 개수 (기본값: 30)')
    parser.add_argument('--workers', '-w', type=int, default=30,
                       help='최대 동시 실행 워커 수 (기본값: 30)')
    parser.add_argument('--list', '-l', action='store_true',
                       help='사용 가능한 스크래퍼 목록 출력')
    
    args = parser.parse_args()
    
    manager = ScraperManager(
        output_base_dir=args.output_dir,
        max_pages=args.pages,
        max_workers=args.workers
    )
    
    if args.list:
        # 사용 가능한 스크래퍼 목록 출력
        scrapers = manager.get_available_scrapers()
        print(f"사용 가능한 Enhanced 스크래퍼: {len(scrapers)}개")
        for i, scraper in enumerate(scrapers, 1):
            site_code = manager.extract_site_code(scraper)
            print(f"{i:3d}. {site_code:15s} ({scraper})")
        return
    
    try:
        # 병렬 스크래퍼 실행
        manager.run_parallel_scrapers(args.count)
        
    except KeyboardInterrupt:
        print("\n\n사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"실행 중 오류 발생: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()