# LOSIMS 첨부파일 구조 분석

## 분석 대상 페이지
- URL: https://www.losims.go.kr/sp/pbcnBizCntt?id=20250286969&fyr=2025
- 공고명: 2025년 제35회 충청남도지사배 민속대제전 참가지원 지방보조금 지원 계획 공고

## 첨부파일 시스템 구조

### 1. 두 가지 유형의 첨부파일

#### A. 공고 첨부파일 (일반적인 첨부파일)
- **HTML 위치**: `<ul class="file_list" id="fileList">`
- **제어 변수**: `<input type="hidden" id="atflGrpId" value="2">`
- **AJAX API**: `/sp/pbcnBizAtflInfoInq`
- **목적**: 공고와 관련된 주요 문서들 (사업계획서, 공고문 등)

#### B. 안내 첨부파일 (가이드 문서)
- **HTML 위치**: `<ul class="file_list" id="pbacInfoFileList">`
- **제어 변수**: `<input type="hidden" id="pbacInfoAtflGrpId" value="0">`
- **AJAX API**: `/sp/pbcnBizGuiAtflInfoInq`
- **목적**: 신청 가이드, 양식 등의 보조 문서

### 2. 파일 로딩 메커니즘

#### 페이지 로드 시 실행되는 JavaScript
```javascript
$(document).ready(function(){
    // 공고 첨부파일 처리
    if( $("#atflGrpId").val() > 0 ){
        fn_attachedFile();  // 공고 첨부파일 로드
    }
    
    // 안내 첨부파일 처리
    if( $("#pbacInfoAtflGrpId").val() > 0 ){
        $("#bizInfoH").show();  // 안내서류 헤더 표시
        $("#bizInfoD").show();  // 안내파일 영역 표시
        fn_pbacFileInfo();      // 안내 첨부파일 로드
    }
});
```

### 3. AJAX 파일 정보 가져오기

#### A. 공고 첨부파일 정보 가져오기 (fn_attachedFile)
```javascript
function fn_attachedFile(){
    var url = "/sp/pbcnBizAtflInfoInq"
    var param = {};
    param.pbacNo = $("#pbacNo").val();  // 공고번호: 20250286969
    
    $.ajax({
        type: "post",
        url: url,
        data: JSON.stringify(param),
        dataType: "json",
        contentType: "application/json",
        success: function(data){
            if(!appCommon.isnull(data.prtlRsltAtflDto)){
                var fileHtml = "";
                data.prtlRsltAtflDto.forEach(function(item, index){
                    var fileNm = item.sbmsnPprsNm; 
                    if(fileNm == null){
                        fileNm = "첨부파일-"+ (index+1);
                    }
                    fileHtml += "<li><a href='javascript:fn_fileDown(\""+item.atflGrpId +"\" ,\""+item.atflSnum +"\");'> "+ fileNm +"</a></li>";
                });
                $("#fileList").html(fileHtml)
            }
        }
    });	
}
```

#### B. 안내 첨부파일 정보 가져오기 (fn_pbacFileInfo)
```javascript
function fn_pbacFileInfo(){
    var url = "/sp/pbcnBizGuiAtflInfoInq"
    var param = {};
    param.pbacNo = $("#pbacNo").val();  // 공고번호: 20250286969
    
    $.ajax({
        type: "post",
        url: url,
        data: JSON.stringify(param),
        dataType: "json",
        contentType: "application/json",
        success: function(data){
            if(!appCommon.isnull(data.prtlRsltGuiAtflDto)){
                var fileHtml = "";
                data.prtlRsltGuiAtflDto.forEach(function(item, index){
                    var aftFileNm = item.sbmsnPprsNm; 
                    if(aftFileNm == null){
                        aftFileNm = "안내파일-"+ (index+1);
                    }
                    fileHtml += "<li><a href='javascript:fn_fileDown(\""+item.atflGrpId +"\" ,\""+item.atflSnum +"\");'> "+ aftFileNm  +"</a></li>";
                });
                $("#pbacInfoFileList").html(fileHtml)
            }
        }
    });	
}
```

### 4. 파일 다운로드 메커니즘

#### A. 파일 다운로드 함수 (fn_fileDown)
```javascript
function fn_fileDown(atflGrpId, no){
    if(!appCommon.isnull(atflGrpId) && atflGrpId !="" && !appCommon.isnull(no) && no !=""){
        var url = "/sp/fileDownCheck";
        var param = {atflGrpId:atflGrpId, atflSnum:no};
        
        $.ajax({
            type: "post",
            url: url,
            data: JSON.stringify(param),
            dataType: "json",
            contentType: "application/json",
            success: function(data){
                if(data.message.status == "SUCCESS"){
                    // 동적 폼 생성하여 파일 다운로드
                    var fileForm = $('<form></from>');
                    fileForm.attr("name", "fileForm");
                    fileForm.attr("method", "post");
                    fileForm.attr("action", "/sp/pbcnBizSrch/fileDownload");
                    fileForm.append($('<input/>',{type:'hidden', name:'atflGrpId', value:atflGrpId}));
                    fileForm.append($('<input/>',{type:'hidden', name:'atflSnum', value:no}));
                    fileForm.appendTo('body');
                    fileForm.submit();
                }
            }
        });
    }
}
```

### 5. 실제 발견된 파일 정보

#### 현재 페이지에서 발견된 첨부파일 (2개)
1. **사업계획서**
   - atflGrpId: `44900005b8c0367-8894-4799-a372-c91700b34133`
   - atflSnum: `1`
   - 다운로드 링크: `javascript:fn_fileDown("44900005b8c0367-8894-4799-a372-c91700b34133" ,"1");`

2. **공고문**
   - atflGrpId: `44900000abb77c5-a2fb-4ce7-abbe-20d68fde54bc`
   - atflSnum: `1`
   - 다운로드 링크: `javascript:fn_fileDown("44900000abb77c5-a2fb-4ce7-abbe-20d68fde54bc" ,"1");`

#### 안내 첨부파일
- `pbacInfoAtflGrpId` 값이 `0`이므로 안내 첨부파일 없음
- 해당 섹션은 숨겨져 있음 (`display: none`)

### 6. 스크래퍼가 놓치고 있는 이유

#### 문제점 분석
1. **동적 로딩**: 첨부파일 목록이 페이지 로드 후 AJAX로 동적 생성됨
2. **JavaScript 의존**: 파일 다운로드가 JavaScript 함수로만 구현됨
3. **다단계 프로세스**: 
   - 1단계: 파일 정보 AJAX 조회 (`/sp/pbcnBizAtflInfoInq`)
   - 2단계: 다운로드 권한 확인 (`/sp/fileDownCheck`)
   - 3단계: 실제 파일 다운로드 (`/sp/pbcnBizSrch/fileDownload`)

### 7. 해결방안

#### A. Playwright 기반 동적 스크래핑 필요
```python
# 페이지 로드 후 AJAX 완료까지 대기
page.wait_for_load_state('networkidle')

# 또는 파일 목록이 나타날 때까지 대기
page.wait_for_selector('#fileList li', timeout=10000)
```

#### B. AJAX API 직접 호출
```python
# 1. 공고 첨부파일 정보 조회
response = session.post('https://www.losims.go.kr/sp/pbcnBizAtflInfoInq', 
                       json={'pbacNo': '20250286969'})
file_info = response.json()

# 2. 각 파일에 대해 다운로드 권한 확인 후 다운로드
for file_item in file_info.get('prtlRsltAtflDto', []):
    atfl_grp_id = file_item['atflGrpId']
    atfl_snum = file_item['atflSnum']
    file_name = file_item.get('sbmsnPprsNm', f'첨부파일-{index+1}')
    
    # 다운로드 권한 확인
    check_response = session.post('https://www.losims.go.kr/sp/fileDownCheck',
                                 json={'atflGrpId': atfl_grp_id, 'atflSnum': atfl_snum})
    
    if check_response.json().get('message', {}).get('status') == 'SUCCESS':
        # 실제 파일 다운로드
        download_data = {'atflGrpId': atfl_grp_id, 'atflSnum': atfl_snum}
        file_response = session.post('https://www.losims.go.kr/sp/pbcnBizSrch/fileDownload',
                                   data=download_data)
```

### 8. 추가 고려사항

1. **세션 관리**: AJAX 호출 시 동일한 세션 유지 필요
2. **헤더 설정**: `Content-Type: application/json` 필수
3. **에러 처리**: 각 단계별 응답 상태 확인 필요
4. **안내 파일**: `pbacInfoAtflGrpId > 0`인 경우 안내 파일도 별도 처리
5. **파일명 처리**: `sbmsnPprsNm`이 null인 경우 기본 파일명 사용

이 분석을 바탕으로 LOSIMS 스크래퍼의 첨부파일 추출 로직을 완전히 재구현해야 합니다.