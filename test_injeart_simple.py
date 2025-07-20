#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple test for injeart scraper - 1 page only
"""

import os
import sys
import logging
from enhanced_injeart_scraper import EnhancedInjeartScraper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_injeart.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def test_single_page():
    """Test single page scraping"""
    logger.info("=== 인제 스크래퍼 1페이지 테스트 시작 ===")
    
    # 출력 디렉토리 설정
    output_dir = "test_output"
    if os.path.exists(output_dir):
        import shutil
        shutil.rmtree(output_dir)
    
    try:
        scraper = EnhancedInjeartScraper()
        
        # 1페이지만 테스트
        logger.info("1페이지 목록 가져오기 테스트...")
        page_url = scraper.get_list_url(1)
        logger.info(f"페이지 URL: {page_url}")
        
        response = scraper.get_page(page_url)
        if not response:
            logger.error("페이지 응답 실패")
            return False
        
        logger.info(f"페이지 응답 상태: {response.status_code}")
        
        # 목록 파싱 테스트
        announcements = scraper.parse_list_page(response.text)
        logger.info(f"파싱된 공고 수: {len(announcements)}")
        
        if not announcements:
            logger.error("공고를 찾을 수 없습니다")
            return False
        
        # 첫 번째 공고만 처리
        first_announcement = announcements[0]
        logger.info(f"첫 번째 공고: {first_announcement['title']}")
        logger.info(f"상세 URL: {first_announcement['url']}")
        
        # 상세 페이지 가져오기
        detail_response = scraper.get_page(first_announcement['url'])
        if not detail_response:
            logger.error("상세 페이지 응답 실패")
            return False
        
        logger.info("상세 페이지 응답 성공")
        
        # 상세 페이지 파싱
        detail_info = scraper.parse_detail_page(detail_response.text)
        logger.info(f"본문 길이: {len(detail_info['content'])}")
        logger.info(f"첨부파일 수: {len(detail_info['attachments'])}")
        
        if detail_info['attachments']:
            for i, att in enumerate(detail_info['attachments']):
                logger.info(f"  첨부파일 {i+1}: {att['filename']} -> {att['url']}")
        
        logger.info("=== 테스트 성공 ===")
        return True
        
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = test_single_page()
    sys.exit(0 if success else 1)