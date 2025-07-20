#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test gidp scraper - 1 page only to check syntax errors
"""

import logging
from enhanced_gidp_scraper import EnhancedGidpScraper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_1_page():
    """Test 1 page scraping"""
    scraper = EnhancedGidpScraper()
    
    output_dir = 'output/gidp_test'
    
    logger.info("Starting 1 page test for gidp")
    
    try:
        success = scraper.scrape_pages(max_pages=1, output_base=output_dir)
        
        if success:
            logger.info("✅ 1 page test completed successfully!")
        else:
            logger.error("❌ 1 page test failed.")
            
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        raise

if __name__ == "__main__":
    test_1_page()