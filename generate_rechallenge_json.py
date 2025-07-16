#!/usr/bin/env python3
"""
RECHALLENGE 수집 결과를 기반으로 JSON 파일 생성
"""
import os
import json
from pathlib import Path
from datetime import datetime
import re

def extract_metadata_from_content(content_file):
    """content.md 파일에서 메타데이터 추출"""
    try:
        with open(content_file, 'r', encoding='utf-8') as f:
            content = f.read()
            # \n이 문자열로 저장되어 있는 경우 실제 줄바꿈으로 변환
            content = content.replace('\\n', '\n')
        
        # 메타데이터 추출
        metadata = {}
        
        # 제목 추출
        title_match = re.search(r'^# (.+)', content, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()
            # 제목에서 줄바꿈 제거
            if '\n' in title:
                title = title.split('\n')[0].strip()
            metadata['title'] = title
        
        # 게시글 번호 추출
        number_match = re.search(r'\*\*게시글 번호:\*\* (.+)$', content, re.MULTILINE)
        if number_match:
            metadata['number'] = number_match.group(1).strip()
        
        # 게시글 ID 추출
        id_match = re.search(r'\*\*게시글 ID:\*\* (.+)$', content, re.MULTILINE)
        if id_match:
            metadata['id'] = id_match.group(1).strip()
        
        # 작성자 추출
        author_match = re.search(r'\*\*작성자:\*\* (.+)$', content, re.MULTILINE)
        if author_match:
            metadata['author'] = author_match.group(1).strip()
        
        # 작성일 추출
        date_match = re.search(r'\*\*작성일:\*\* (.+)$', content, re.MULTILINE)
        if date_match:
            metadata['date'] = date_match.group(1).strip()
        
        # 조회수 추출
        views_match = re.search(r'\*\*조회수:\*\* (.+)$', content, re.MULTILINE)
        if views_match:
            metadata['views'] = views_match.group(1).strip()
        
        # URL 추출
        url_match = re.search(r'\*\*URL:\*\* (.+)$', content, re.MULTILINE)
        if url_match:
            metadata['url'] = url_match.group(1).strip()
        
        # 수집 시간 추출
        scraped_match = re.search(r'\*\*수집 시간:\*\* (.+)$', content, re.MULTILINE)
        if scraped_match:
            metadata['scraped_at'] = scraped_match.group(1).strip()
        
        return metadata
        
    except Exception as e:
        print(f"메타데이터 추출 실패: {content_file}, 에러: {e}")
        return {}

def count_attachments(post_dir):
    """첨부파일 개수 계산"""
    attachments_dir = post_dir / "attachments"
    if attachments_dir.exists():
        return len([f for f in attachments_dir.iterdir() if f.is_file()])
    return 0

def generate_json():
    """JSON 파일 생성"""
    output_dir = Path("output/rechallenge")
    
    if not output_dir.exists():
        print(f"출력 디렉토리가 없습니다: {output_dir}")
        return
    
    processed_titles = []
    
    # 모든 게시글 폴더 탐색
    for post_dir in output_dir.iterdir():
        if post_dir.is_dir():
            content_file = post_dir / "content.md"
            
            if content_file.exists():
                # 메타데이터 추출
                metadata = extract_metadata_from_content(content_file)
                
                # 첨부파일 개수 계산
                attachment_count = count_attachments(post_dir)
                metadata['attachment_count'] = attachment_count
                
                # ISO 형식 시간 변환
                if 'scraped_at' in metadata:
                    try:
                        # "2025-07-15 00:43:30" 형식을 ISO 형식으로 변환
                        dt = datetime.strptime(metadata['scraped_at'], '%Y-%m-%d %H:%M:%S')
                        metadata['scraped_at'] = dt.isoformat()
                    except:
                        pass
                
                processed_titles.append(metadata)
                title_display = metadata.get('title', 'Unknown')
                if title_display and '\n' in title_display:
                    title_display = title_display.split('\n')[0]
                print(f"처리 완료: {title_display}")
                if not metadata.get('title'):
                    print(f"  제목 추출 실패: {post_dir.name}")
                    print(f"  첫 10줄: {content[:200]}...")
    
    # ID 순서대로 정렬 (숫자 ID는 숫자로, 문자는 문자로)
    def sort_key(item):
        number = item.get('number', '')
        if number.isdigit():
            return (0, int(number))  # 숫자는 0그룹에서 숫자값으로 정렬
        else:
            return (1, number)  # 문자는 1그룹에서 문자값으로 정렬
    
    processed_titles.sort(key=sort_key, reverse=True)  # 최신순 정렬
    
    # JSON 파일 저장
    json_file = output_dir / "processed_titles_enhanced_rechallenge.json"
    
    try:
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(processed_titles, f, ensure_ascii=False, indent=2)
        
        print(f"\n=== JSON 파일 생성 완료 ===")
        print(f"파일 위치: {json_file}")
        print(f"총 게시글 수: {len(processed_titles)}")
        print(f"총 첨부파일 수: {sum(item.get('attachment_count', 0) for item in processed_titles)}")
        
    except Exception as e:
        print(f"JSON 파일 저장 실패: {e}")

if __name__ == "__main__":
    generate_json()