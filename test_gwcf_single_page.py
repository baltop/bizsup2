#!/usr/bin/env python3
"""
Test GWCF scraper with single page to verify filename fixes
"""

from enhanced_gwcf_scraper import GWCFScraper

def main():
    # Configuration - test with 1 page only
    base_url = "http://www.gwcf.or.kr/ko/culture-business/business-top/business.html?no=1"
    site_code = "gwcf_test"
    max_pages = 1
    
    # Initialize scraper
    scraper = GWCFScraper(base_url, site_code)
    
    try:
        # Start scraping
        scraper.scrape_pages(max_pages)
        
        # Print statistics
        scraper.print_statistics()
        
    except KeyboardInterrupt:
        scraper.logger.info("\nScraping interrupted by user")
    except Exception as e:
        scraper.logger.error(f"Scraping failed: {str(e)}")
    finally:
        scraper.logger.info("Scraping completed")

if __name__ == "__main__":
    main()