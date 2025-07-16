#!/usr/bin/env python3
"""
Debug output for the first article
"""

import sys
sys.path.append('.')
from enhanced_changwon_scraper import ChangwonScraper

if __name__ == "__main__":
    scraper = ChangwonScraper()
    
    # Test just the first article - the one we know has attachments
    articles = scraper.get_article_list(1)
    
    if articles:
        article = articles[0]
        print(f"Processing: {article['title']}")
        print(f"URL: {article['url']}")
        
        article_data = scraper.get_article_content(article['url'])
        print(f"Found {len(article_data['attachments'])} attachments")
        
        for att in article_data['attachments']:
            print(f"  - {att['filename']} -> {att['url']}")
        
        if article_data['attachments']:
            # Test download
            import tempfile
            import os
            with tempfile.TemporaryDirectory() as tmpdir:
                from pathlib import Path
                tmpdir = Path(tmpdir)
                
                result = scraper.save_article(article_data, article['article_num'], article['title'])
                print(f"Saved with {result} attachments")
                
                # Check if files exist
                article_dir = scraper.output_dir / f"{article['article_num']}_{article['title'][:50]}"
                if article_dir.exists():
                    att_dir = article_dir / "attachments"
                    if att_dir.exists():
                        files = list(att_dir.glob("*"))
                        print(f"Files in directory: {[f.name for f in files]}")
                        for f in files:
                            print(f"  {f.name}: {f.stat().st_size} bytes")