공지가 빠지는 경우는  gbfood 사이트.
79 line 
        
        for row in list_rows:
            try:
                # 공지사항이나 제목 행 건너뛰기
                if 'notice-row' in row.get('class', []) or 'list-top' in row.get('class', []):
                    continue

중복체크 로직에 문제가 있음. 새로운 건을 처리하지 않고 3개연속 중복으로 중단.    enhanced_gbsinbo_scraper
enhanced_base_scraper 에 있음.
346 line  
    def filter_new_announcements(self, announcements: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], bool]:
        """새로운 공고만 필터링 - 이전 실행 기록과만 중복 체크, 현재 세션 내에서는 중복 허용"""
        if not self.enable_duplicate_check:
            return announcements, False
        
        new_announcements = []
        previous_session_duplicate_count = 0  # 이전 실행 중복만 카운트
        
        for ann in announcements:
            title = ann.get('title', '')
            title_hash = self.get_title_hash(title)
            
            # 이전 실행에서 처리된 공고인지만 확인 (현재 세션은 제외)
            if title_hash in self.processed_titles:
                previous_session_duplicate_count += 1
                logger.debug(f"이전 실행에서 처리된 공고 스킵: {title[:50]}...")
                
                # 연속된 이전 실행 중복 임계값 도달시 조기 종료 신호
                if previous_session_duplicate_count >= self.duplicate_threshold:
                    logger.info(f"이전 실행 중복 공고 {previous_session_duplicate_count}개 연속 발견 - 조기 종료 신호")
                    break
            else:
                # 이전 실행에 없는 새로운 공고는 무조건 포함 (현재 세션 내 중복 완전 무시)
                new_announcements.append(ann)
                previous_session_duplicate_count = 0  # 새로운 공고 발견시 중복 카운트 리셋
                logger.debug(f"새로운 공고 추가: {title[:50]}...")
        
        should_stop = previous_session_duplicate_count >= self.duplicate_threshold
        logger.info(f"전체 {len(announcements)}개 중 새로운 공고 {len(new_announcements)}개, 이전 실행 중복 {previous_session_duplicate_count}개 발견")
        
        return new_announcements, should_stop
    
    def process_announcement(self, announcement: Dict[str, Any], index: int, output_base: str = 'output'):


실제 처리는 522라인을 볼것.