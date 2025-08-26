import json
import re
from typing import Dict, Any, Optional, Tuple


def fix_json_syntax_errors(json_str: str) -> str:
    """
    기본적인 JSON 구문 오류를 수정하는 함수
    
    Args:
        json_str (str): 오류가 있는 JSON 문자열
        
    Returns:
        str: 수정된 JSON 문자열
    """
    try:
        repaired = json_str
        
        # 1. 마지막 쉼표 제거 (trailing comma)
        repaired = re.sub(r',\s*([}\]])', r'\1', repaired)
        
        # 2. 중복 쉼표 제거
        repaired = re.sub(r',\s*,', r',', repaired)
        
        # 3. 쉼표 누락 문제 해결 - 필드 간 쉼표 추가
        # "field1": "value1" "field2": "value2" → "field1": "value1", "field2": "value2"
        repaired = re.sub(r'"\s*"([^"]+)"\s*:', r'", "\1":', repaired)
        
        # 4. 잘못된 따옴표 쌍 수정
        # 홀수 개의 따옴표가 있는 경우
        quote_count = repaired.count('"')
        if quote_count % 2 != 0:
            # 마지막에 따옴표 추가
            repaired += '"'
        
        # 5. 배열 내 객체 구분 쉼표 추가
        # }{} → }, {
        repaired = re.sub(r'}\s*{', r'}, {', repaired)
        
        # 6. 키와 값 사이 콜론 수정
        # "key" "value" → "key": "value"
        repaired = re.sub(r'"\s*"([^"]*)"(?!\s*:)', r'": "\1"', repaired)
        
        # 7. 배열/객체 끝의 잘못된 구조 수정
        # }, ] → }]
        repaired = re.sub(r'},\s*\]', r'}]', repaired)
        
        print(f"기본 JSON 구문 수정 완료")
        return repaired
        
    except Exception as e:
        print(f"기본 JSON 구문 수정 오류: {e}")
        return json_str


def extract_valid_data_from_broken_json(broken_json: str) -> Dict[str, Any]:
    """
    깨진 JSON에서 유효한 데이터만 추출하여 최소 구조로 만드는 함수
    
    Args:
        broken_json (str): 깨진 JSON 문자열
        
    Returns:
        Dict[str, Any]: 추출된 유효한 데이터
    """
    result = {
        "summary": "",
        "keyword": "",
        "paragraphs": []
    }
    
    try:
        # summary 추출 시도
        summary_match = re.search(r'"summary":\s*"([^"]*)"', broken_json)
        if summary_match:
            result["summary"] = summary_match.group(1)
            print(f"summary 추출 성공: {result['summary'][:50]}...")
        
        # keyword 추출 시도 
        keyword_match = re.search(r'"keyword":\s*(?:"([^"]*)"|(\[[^\]]*\]))', broken_json)
        if keyword_match:
            if keyword_match.group(1):  # 문자열 형태
                result["keyword"] = keyword_match.group(1)
            elif keyword_match.group(2):  # 배열 형태
                try:
                    # 배열에서 유효한 키워드들만 추출
                    array_content = keyword_match.group(2)
                    # 간단한 배열 파싱 (정규식으로)
                    keywords = re.findall(r'"([^"]*)"', array_content)
                    result["keyword"] = ", ".join(keywords)
                except:
                    result["keyword"] = ""
            print(f"keyword 추출 성공: {result['keyword']}")
        
        # paragraphs 추출 시도
        paragraphs_match = re.search(r'"paragraphs":\s*\[(.*)', broken_json, re.DOTALL)
        if paragraphs_match:
            paragraphs_content = paragraphs_match.group(1)
            
            # 각 paragraph 객체 추출
            paragraph_objects = []
            
            # 중괄호로 구분된 객체들 찾기
            brace_level = 0
            current_obj = ""
            
            for char in paragraphs_content:
                if char == '{':
                    if brace_level == 0:
                        current_obj = "{"
                    else:
                        current_obj += char
                    brace_level += 1
                elif char == '}':
                    brace_level -= 1
                    current_obj += char
                    if brace_level == 0:
                        # 완전한 객체 발견
                        paragraph_objects.append(current_obj)
                        current_obj = ""
                elif brace_level > 0:
                    current_obj += char
                elif char == ']':
                    break
            
            # 각 paragraph 객체에서 데이터 추출
            for obj_str in paragraph_objects:
                paragraph = {}
                
                # summary 추출
                p_summary_match = re.search(r'"summary":\s*"([^"]*)"', obj_str)
                if p_summary_match:
                    paragraph["summary"] = p_summary_match.group(1)
                else:
                    paragraph["summary"] = ""
                
                # keyword 추출
                p_keyword_match = re.search(r'"keyword":\s*(?:"([^"]*)"|(\[[^\]]*\]))', obj_str)
                if p_keyword_match:
                    if p_keyword_match.group(1):
                        paragraph["keyword"] = p_keyword_match.group(1)
                    elif p_keyword_match.group(2):
                        try:
                            keywords = re.findall(r'"([^"]*)"', p_keyword_match.group(2))
                            paragraph["keyword"] = ", ".join(keywords)
                        except:
                            paragraph["keyword"] = ""
                    else:
                        paragraph["keyword"] = ""
                else:
                    paragraph["keyword"] = ""
                
                # sentiment 추출
                p_sentiment_match = re.search(r'"sentiment":\s*"([^"]*)"', obj_str)
                if p_sentiment_match:
                    paragraph["sentiment"] = p_sentiment_match.group(1)
                else:
                    paragraph["sentiment"] = "보통"
                
                result["paragraphs"].append(paragraph)
            
            print(f"paragraphs 추출 성공: {len(result['paragraphs'])}개")
        
        print(f"유효한 데이터 추출 완료: summary={bool(result['summary'])}, keyword={bool(result['keyword'])}, paragraphs={len(result['paragraphs'])}")
        return result
        
    except Exception as e:
        print(f"데이터 추출 중 오류: {e}")
        # 빈 구조 반환 (고정 문자열 없음)
        return {
            "summary": "",
            "keyword": "",
            "paragraphs": []
        }


def aggressive_json_repair(json_str: str) -> str:
    """
    강력한 JSON 복구 함수 - 구조적 문제까지 해결
    
    Args:
        json_str (str): 복구할 JSON 문자열
        
    Returns:
        str: 복구된 JSON 문자열
    """
    try:
        repaired = json_str
        
        print("🔧 고급 JSON 복구 시작...")
        
        # 1. 기본 구문 수정 다시 적용
        repaired = fix_json_syntax_errors(repaired)
        
        # 2. 값이 없는 키 처리
        # "key": → "key": "기본값"
        repaired = re.sub(r'"([^"]+)":\s*([,}\]])', r'"\1": "기본값"\2', repaired)
        
        # 3. 잘못된 배열 구조 수정
        # "paragraphs": [{ → "paragraphs": [{"summary": "기본값", "keyword": "기본값", "sentiment": "보통"}]
        if '"paragraphs"' in repaired:
            # paragraphs 배열이 제대로 닫히지 않은 경우
            paragraphs_pattern = r'"paragraphs":\s*\[[^\]]*$'
            if re.search(paragraphs_pattern, repaired):
                # 미완성된 paragraphs 배열 완성
                repaired = re.sub(paragraphs_pattern, 
                    '"paragraphs": [{"summary": "복구된 요약", "keyword": "복구된 키워드", "sentiment": "보통"}]',
                    repaired)
        
        # 4. 중첩된 구조에서 오류 수정
        # 잘못된 중첩 해결
        brace_stack = []
        corrected_chars = []
        
        for i, char in enumerate(repaired):
            if char == '{':
                brace_stack.append('{')
                corrected_chars.append(char)
            elif char == '}':
                if brace_stack and brace_stack[-1] == '{':
                    brace_stack.pop()
                    corrected_chars.append(char)
                else:
                    # 매칭되지 않는 } 무시
                    continue
            elif char == '[':
                brace_stack.append('[')
                corrected_chars.append(char)
            elif char == ']':
                if brace_stack and brace_stack[-1] == '[':
                    brace_stack.pop()
                    corrected_chars.append(char)
                else:
                    # 매칭되지 않는 ] 무시
                    continue
            else:
                corrected_chars.append(char)
        
        # 남은 열린 괄호들 닫기
        while brace_stack:
            bracket = brace_stack.pop()
            if bracket == '{':
                corrected_chars.append('}')
            elif bracket == '[':
                corrected_chars.append(']')
        
        repaired = ''.join(corrected_chars)
        
        # 5. 최종 구조 검증 및 수정
        # 최소 구조 보장
        if not repaired.strip().startswith('{'):
            repaired = '{' + repaired
        if not repaired.strip().endswith('}'):
            repaired = repaired + '}'
        
        # 6. 원본 데이터를 보존하면서 필수 필드만 보장
        try:
            # JSON 파싱 시도
            parsed = json.loads(repaired)
            
            # 필수 필드 보완 (빈 값으로)
            if 'summary' not in parsed:
                parsed['summary'] = ""
            if 'keyword' not in parsed:
                parsed['keyword'] = ""
            if 'paragraphs' not in parsed:
                parsed['paragraphs'] = []
            
            repaired = json.dumps(parsed, ensure_ascii=False)
            
        except:
            # 파싱 실패 시 원본에서 추출 가능한 부분만 사용
            print("파싱 실패 - 원본 데이터 추출 시도")
            extracted_data = extract_valid_data_from_broken_json(json_str)
            repaired = json.dumps(extracted_data, ensure_ascii=False)
        
        print(f"고급 JSON 복구 완료: {len(repaired)}자")
        return repaired
        
    except Exception as e:
        print(f"고급 JSON 복구 오류: {e}")
        # 최종 fallback - 빈 구조 반환
        return '{"summary": "", "keyword": "", "paragraphs": []}'


def attempt_partial_json_completion(partial_json: str) -> str:
    """
    잘린 JSON을 기본 구조로 완성시키는 함수
    
    Args:
        partial_json (str): 잘린 JSON 문자열
        
    Returns:
        str: 완성된 JSON 문자열 또는 None
    """
    try:
        if not partial_json or not partial_json.strip():
            return None
            
        print(f"부분 JSON 완성 시도: {partial_json[:300]}...")
        
        repaired = partial_json.strip()
        
        # 1단계: 미완성된 문자열 값 닫기
        # 마지막이 따옴표 없이 끝나는 경우
        if repaired and not repaired.endswith('"') and not repaired.endswith('}') and not repaired.endswith(']'):
            # 마지막 따옴표 위치 찾기
            last_quote_pos = repaired.rfind('"')
            if last_quote_pos != -1:
                # 마지막 따옴표 이후 내용 확인
                after_quote = repaired[last_quote_pos + 1:]
                # 키:값 패턴이 아니고 단순 문자열 값인 경우
                if ':' not in after_quote and ',' not in after_quote and '}' not in after_quote and ']' not in after_quote:
                    repaired += '"'
                    print("미완성된 문자열 값 닫기 완료")
        
        # 2단계: 필수 필드 보장
        required_fields = ['summary', 'keyword', 'paragraphs']
        
        # summary 필드 확인 및 추가
        if '"summary"' not in repaired:
            if repaired.strip() == '{':
                repaired = '{"summary": "요약 없음"'
            else:
                # 첫 번째 필드로 추가
                if repaired.startswith('{'):
                    repaired = repaired[:1] + '"summary": "요약 없음", ' + repaired[1:]
        
        # keyword 필드 확인 및 추가
        if '"keyword"' not in repaired:
            # summary 다음에 추가
            if '"summary"' in repaired:
                # summary 값의 끝을 찾아서 keyword 추가
                summary_pattern = r'"summary":\s*"[^"]*"'
                match = re.search(summary_pattern, repaired)
                if match:
                    end_pos = match.end()
                    # 쉼표가 없으면 추가
                    if not repaired[end_pos:].strip().startswith(','):
                        repaired = repaired[:end_pos] + ', "keyword": "키워드 없음"' + repaired[end_pos:]
                    else:
                        # 쉼표 다음에 추가
                        comma_pos = repaired.find(',', end_pos)
                        if comma_pos != -1:
                            repaired = repaired[:comma_pos+1] + ' "keyword": "키워드 없음",' + repaired[comma_pos+1:]
        
        # paragraphs 필드 확인 및 추가
        if '"paragraphs"' not in repaired:
            # 간단한 paragraphs 배열 추가
            paragraphs_json = ', "paragraphs": [{"summary": "요약 없음", "keyword": "키워드 없음", "sentiment": "보통"}]'
            
            # 마지막 필드 다음에 추가
            if '"keyword"' in repaired:
                keyword_pattern = r'"keyword":\s*"[^"]*"'
                match = re.search(keyword_pattern, repaired)
                if match:
                    end_pos = match.end()
                    repaired = repaired[:end_pos] + paragraphs_json + repaired[end_pos:]
        
        # 3단계: paragraphs 배열 완성
        if '"paragraphs"' in repaired and '"paragraphs": [' in repaired:
            paragraphs_start = repaired.find('"paragraphs": [')
            if paragraphs_start != -1:
                after_paragraphs = repaired[paragraphs_start + len('"paragraphs": ['):]
                
                # paragraphs 배열이 비어있거나 미완성인 경우
                if after_paragraphs.strip().startswith(']') or not after_paragraphs.strip():
                    # 기본 paragraph 추가
                    insert_pos = paragraphs_start + len('"paragraphs": [')
                    default_paragraph = '{"summary": "요약 없음", "keyword": "키워드 없음", "sentiment": "보통"}'
                    repaired = repaired[:insert_pos] + default_paragraph + repaired[insert_pos:]
                elif '{' in after_paragraphs:
                    # 미완성된 paragraph 객체가 있는 경우
                    last_brace = after_paragraphs.rfind('{')
                    if last_brace != -1:
                        paragraph_part = after_paragraphs[last_brace:]
                        
                        # 필수 필드들 확인 및 추가
                        if '"summary"' not in paragraph_part:
                            # summary 추가 위치 찾기
                            if paragraph_part.strip() == '{':
                                repaired = repaired.replace(paragraph_part, '{"summary": "요약 없음"')
                        
                        if '"keyword"' not in paragraph_part:
                            # keyword 추가
                            if '"summary"' in paragraph_part:
                                summary_end = repaired.rfind('"summary"')
                                if summary_end != -1:
                                    # summary 값의 끝 찾기
                                    value_start = repaired.find('"', summary_end + len('"summary"') + 1)
                                    if value_start != -1:
                                        value_end = repaired.find('"', value_start + 1)
                                        if value_end != -1:
                                            repaired = repaired[:value_end+1] + ', "keyword": "키워드 없음"' + repaired[value_end+1:]
                        
                        if '"sentiment"' not in paragraph_part:
                            # sentiment 추가
                            if '"keyword"' in paragraph_part:
                                keyword_end = repaired.rfind('"keyword"')
                                if keyword_end != -1:
                                    # keyword 값의 끝 찾기
                                    value_start = repaired.find('"', keyword_end + len('"keyword"') + 1)
                                    if value_start != -1:
                                        value_end = repaired.find('"', value_start + 1)
                                        if value_end != -1:
                                            repaired = repaired[:value_end+1] + ', "sentiment": "보통"' + repaired[value_end+1:]
        
        # 4단계: 중괄호/대괄호 균형 맞추기
        open_braces = repaired.count('{')
        close_braces = repaired.count('}')
        open_brackets = repaired.count('[')
        close_brackets = repaired.count(']')
        
        if open_braces > close_braces:
            missing_braces = open_braces - close_braces
            repaired += '}' * missing_braces
            print(f"누락된 닫는 중괄호 {missing_braces}개 추가")
        
        if open_brackets > close_brackets:
            missing_brackets = open_brackets - close_brackets
            repaired += ']' * missing_brackets
            print(f"누락된 닫는 대괄호 {missing_brackets}개 추가")
        
        # 5단계: 고급 JSON 구문 정리
        repaired = fix_json_syntax_errors(repaired)
        
        print(f"완성된 JSON: {repaired[:300]}...")
        
        # 6단계: JSON 유효성 검사
        try:
            json.loads(repaired)
            print("✅ 부분 JSON 완성 성공!")
            return repaired
        except json.JSONDecodeError as e:
            print(f"JSON 유효성 검사 실패: {e}")
            # 추가 복구 시도
            repaired = aggressive_json_repair(repaired)
            try:
                json.loads(repaired)
                print("✅ 고급 JSON 복구 성공!")
                return repaired
            except:
                print("고급 복구도 실패 - fallback 사용")
                raise e
        
    except Exception as e:
        print(f"부분 JSON 완성 중 오류: {e}")
        
        # 최후의 fallback: 원본에서 데이터 추출 시도
        print("🔄 원본 데이터 추출로 fallback")
        extracted_data = extract_valid_data_from_broken_json(partial_json)
        return json.dumps(extracted_data, ensure_ascii=False)


def extract_json_from_markdown(result: str) -> Optional[str]:
    """
    마크다운 응답에서 JSON을 추출하는 함수
    
    Args:
        result (str): 마크다운 형태의 응답 텍스트
        
    Returns:
        Optional[str]: 추출된 JSON 문자열 또는 None
    """
    try:
        # ```json 형식을 유연하게 찾기
        json_str = None
        json_start = result.find('```json')
        
        if json_start != -1:
            # ```json 이후의 첫 번째 { 찾기
            brace_start = result.find('{', json_start)
            if brace_start != -1:
                # 중괄호 카운팅으로 완전한 JSON 추출 시도
                brace_count = 0
                json_end = brace_start
                complete_json_found = False
                
                for i in range(brace_start, len(result)):
                    if result[i] == '{':
                        brace_count += 1
                    elif result[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            complete_json_found = True
                            break
                
                if complete_json_found:
                    json_str = result[brace_start:json_end]
                    print("```json 마크다운 코드 블록에서 완전한 JSON 발견 (중괄호 카운팅)")
                    print(f"추출된 JSON 길이: {len(json_str)}")
                    print(f"추출된 JSON 시작: {repr(json_str[:100])}")
                else:
                    # 완전하지 않은 JSON이지만 부분 추출 시도
                    print("⚠️  완전하지 않은 JSON 감지 - 부분 추출 시도")
                    
                    # 가능한 한 많은 JSON 내용을 추출
                    # 다음 ``` 또는 문자열 끝까지 추출
                    json_end = result.find('```', brace_start + 1)
                    if json_end == -1:
                        json_end = len(result)
                    
                    json_str = result[brace_start:json_end].strip()
                    print(f"부분 추출된 JSON 길이: {len(json_str)}")
                    print(f"부분 추출된 JSON: {repr(json_str[:200])}")
                    
                    # 잘린 JSON 복구 시도
                    json_str = attempt_partial_json_completion(json_str)
                    if not json_str:
                        print("부분 JSON 복구 실패 - 원본 데이터 추출 시도")
                        extracted_data = extract_valid_data_from_broken_json(result)
                        return json.dumps(extracted_data, ensure_ascii=False)
            else:
                print("```json 블록에서 { 를 찾을 수 없습니다.")
                return None
        else:
            # ```json이 없으면 일반 ``` 블록에서 JSON 찾기
            json_start = result.find('```')
            if json_start != -1:
                # ``` 이후의 첫 번째 { 찾기
                brace_start = result.find('{', json_start)
                if brace_start != -1:
                    # 중괄호 카운팅으로 완전한 JSON 추출 시도
                    brace_count = 0
                    json_end = brace_start
                    complete_json_found = False
                    
                    for i in range(brace_start, len(result)):
                        if result[i] == '{':
                            brace_count += 1
                        elif result[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_end = i + 1
                                complete_json_found = True
                                break
                    
                    if complete_json_found:
                        json_str = result[brace_start:json_end]
                        print("일반 마크다운 코드 블록에서 완전한 JSON 발견 (중괄호 카운팅)")
                        print(f"추출된 JSON 길이: {len(json_str)}")
                        print(f"추출된 JSON 시작: {repr(json_str[:100])}")
                    else:
                        # 완전하지 않은 JSON이지만 부분 추출 시도
                        print("⚠️  완전하지 않은 JSON 감지 - 부분 추출 시도")
                        
                        # 가능한 한 많은 JSON 내용을 추출
                        # 다음 ``` 또는 문자열 끝까지 추출
                        json_end = result.find('```', brace_start + 1)
                        if json_end == -1:
                            json_end = len(result)
                        
                        json_str = result[brace_start:json_end].strip()
                        print(f"부분 추출된 JSON 길이: {len(json_str)}")
                        print(f"부분 추출된 JSON: {repr(json_str[:200])}")
                        
                        # 잘린 JSON 복구 시도
                        json_str = attempt_partial_json_completion(json_str)
                        if not json_str:
                            print("부분 JSON 복구 실패 - 원본 데이터 추출 시도")
                            extracted_data = extract_valid_data_from_broken_json(result)
                            return json.dumps(extracted_data, ensure_ascii=False)
                else:
                    print("일반 ``` 블록에서 { 를 찾을 수 없습니다.")
                    return None
            else:
                # 마크다운 블록이 없으면 fallback
                print("모든 패턴으로 ```json 블록을 찾을 수 없습니다.")
                return None
        
        # JSON 추출 후 유효성 검사
        if not json_str or not json_str.strip():
            print("추출된 JSON이 비어있습니다.")
            return None
        
        return json_str
        
    except Exception as e:
        print(f"마크다운 JSON 추출 중 오류: {e}")
        return None


def process_and_repair_json(json_str: str) -> str:
    """
    추출된 JSON을 처리하고 복구하는 함수
    
    Args:
        json_str (str): 추출된 JSON 문자열
        
    Returns:
        str: 처리된 유효한 JSON 문자열
    """
    try:
        # 먼저 JSON이 이미 파싱 가능한지 체크
        try:
            json.loads(json_str)
            print("JSON이 이미 유효함 - 수정 로직 건너뛰기")
            return json_str
        except json.JSONDecodeError:
            print(f"JSON 복구 처리 시작 - 입력 길이: {len(json_str)}")
            pass  # 수정 로직 계속 진행
        
        # JSON 정리 및 garbage data 제거
        cleaned_json = json_str.strip()
        
        # 1단계: trailing comma 제거
        cleaned_json = re.sub(r',\s*([}\]])', r'\1', cleaned_json)
        
        # 2단계: JSON 객체의 끝을 찾아서 이후 내용 제거
        # 가장 마지막의 } 또는 }] 패턴을 찾아서 그 이후 내용 제거
        json_end_patterns = [
            r'(\{[^{}]*\}(?:\s*,\s*\{[^{}]*\})*\s*\})\s*$',  # 단일 객체
            r'(\{[^{}]*"paragraphs"\s*:\s*\[[^\]]*\]\s*[^{}]*\})\s*$',  # paragraphs 포함
            r'(\{[^{}]*\})\s*$',  # 기본 객체
        ]
        
        json_extracted = None
        for pattern in json_end_patterns:
            match = re.search(pattern, cleaned_json, re.DOTALL)
            if match:
                json_extracted = match.group(1)
                print(f"JSON 패턴 매칭 성공: {pattern[:50]}...")
                break
        
        if json_extracted:
            cleaned_json = json_extracted
            print(f"Garbage data 제거 후 JSON 길이: {len(cleaned_json)}")
        else:
            print("JSON 패턴 매칭 실패, 원본 사용")
            print(f"원본 cleaned_json 길이: {len(cleaned_json)}")
            print(f"원본 cleaned_json 내용: {repr(cleaned_json[:200])}")
            
            # 빈 문자열이나 유효하지 않은 JSON인 경우 기본값 반환
            if not cleaned_json.strip():
                print("빈 JSON 문자열 감지 - 기본값 반환")
                return json.dumps({"summary": "", "keyword": "", "paragraphs": []}, ensure_ascii=False)
        
        # 3단계: JSON 구문 오류 수정
        original_full_json = cleaned_json  # 전체 수정 과정 추적용
        any_modification = False  # 수정 발생 여부 추적
        
        # 1) sentiment 값의 띄어쓰기 수정
        original_json = cleaned_json
        cleaned_json = re.sub(r'"sentiment":\s*"(약한긍)\s+(정)"', r'"sentiment": "\1\2"', cleaned_json)
        cleaned_json = re.sub(r'"sentiment":\s*"(약한부)\s+(정)"', r'"sentiment": "\1\2"', cleaned_json)
        cleaned_json = re.sub(r'"sentiment":\s*"(강한긍)\s+(정)"', r'"sentiment": "\1\2"', cleaned_json)
        cleaned_json = re.sub(r'"sentiment":\s*"(강한부)\s+(정)"', r'"sentiment": "\1\2"', cleaned_json)
        if original_json != cleaned_json:
            print("sentiment 띄어쓰기 수정 적용됨")
            any_modification = True
        
        # 2) 불필요한 공백 제거
        before_space_removal = cleaned_json
        cleaned_json = re.sub(r'\s+', ' ', cleaned_json)
        # 3) 마지막 쉼표 제거
        cleaned_json = re.sub(r',\s*([}\]])', r'\1', cleaned_json)
        
        # 공백/쉼표 정리도 수정으로 간주 (의미있는 변화가 있을 때)
        if before_space_removal != cleaned_json and len(before_space_removal) != len(cleaned_json):
            any_modification = True
        
        # 실제 수정이 발생했을 때만 로그 출력
        if any_modification:
            print(f"JSON 수정 전: {original_full_json[:200]}...")
            print(f"JSON 수정 완료: {cleaned_json[:200]}...")
        
        # JSON 파싱 직전 최종 검증
        if not cleaned_json.strip():
            print("최종 검증: 빈 JSON 문자열")
            return json.dumps({"summary": "", "keyword": "", "paragraphs": []}, ensure_ascii=False)
        
        if not cleaned_json.strip().startswith('{'):
            print(f"최종 검증: JSON이 중괄호로 시작하지 않음: {repr(cleaned_json[:50])}")
            return json.dumps({"summary": "", "keyword": "", "paragraphs": []}, ensure_ascii=False)
        
        parsed_result = json.loads(cleaned_json)
        print("JSON 파싱 성공")
        
        return json.dumps(parsed_result, ensure_ascii=False, indent=2)
        
    except json.JSONDecodeError as e:
        print(f"JSON 파싱 실패: {e}")
        print(f"문제 JSON: {cleaned_json[:4000]}...")
        
        # 추가 복구 시도: 중괄호 밖의 내용 제거
        try:
            # 첫 번째 {와 마지막 } 사이만 추출
            brace_match = re.search(r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})', cleaned_json, re.DOTALL)
            if brace_match:
                cleaned_json = brace_match.group(1)
                print(f"중괄호 기반 복구 시도: {len(cleaned_json)}자")
                
                # 복구된 JSON에도 같은 수정 적용
                cleaned_json = re.sub(r'"sentiment":\s*"(약한긍)\s+(정)"', r'"sentiment": "\1\2"', cleaned_json)
                cleaned_json = re.sub(r'"sentiment":\s*"(약한부)\s+(정)"', r'"sentiment": "\1\2"', cleaned_json)
                cleaned_json = re.sub(r'"sentiment":\s*"(강한긍)\s+(정)"', r'"sentiment": "\1\2"', cleaned_json)
                cleaned_json = re.sub(r'"sentiment":\s*"(강한부)\s+(정)"', r'"sentiment": "\1\2"', cleaned_json)
                cleaned_json = re.sub(r',\s*([}\]])', r'\1', cleaned_json)
                
                parsed_result = json.loads(cleaned_json)
                print("JSON 파싱 복구 성공")
                return json.dumps(parsed_result, ensure_ascii=False, indent=2)
            else:
                raise Exception("중괄호 패턴을 찾을 수 없습니다")
        except Exception as recovery_error:
            print(f"복구 시도 실패: {recovery_error}")
            
            # 최후의 수단: 고급 JSON 복구 시도
            print("🛠️  고급 JSON 복구 시도...")
            try:
                recovered_json = aggressive_json_repair(cleaned_json)
                parsed_result = json.loads(recovered_json)
                print("✅ 고급 JSON 복구 성공!")
                return recovered_json
            except Exception as repair_error:
                print(f"고급 JSON 복구 실패: {repair_error}")
                # 마크다운 블록에서 추출한 JSON이 유효하지 않으면 오류 반환
                return json.dumps({"summary": "", "keyword": "", "paragraphs": []}, ensure_ascii=False)
    
    except Exception as e:
        print(f"JSON 처리 중 예상치 못한 오류: {e}")
        return json.dumps({"summary": "", "keyword": "", "paragraphs": []}, ensure_ascii=False)


def attempt_json_repair(broken_json: str) -> str:
    """
    잘린 JSON을 복구하려고 시도하는 함수
    
    Args:
        broken_json (str): 잘린 JSON 문자열
        
    Returns:
        str: 복구된 JSON 문자열 또는 None
    """
    try:
        if not broken_json or not broken_json.strip():
            return None
            
        print(f"복구 시도 대상 JSON: {broken_json[:200]}...")
        
        # 1단계: 기본 닫기 시도
        repaired = broken_json.strip()
        
        # 2단계: 미완성된 문자열 값 닫기
        # 마지막이 따옴표 없이 끝나는 경우
        if repaired.endswith('"'):
            # 이미 따옴표로 끝남
            pass
        elif '"' in repaired and not repaired.endswith('"'):
            # 마지막 따옴표를 찾아서 닫기
            last_quote_pos = repaired.rfind('"')
            if last_quote_pos != -1:
                # 따옴표 이후의 내용을 확인
                after_quote = repaired[last_quote_pos + 1:]
                if ':' not in after_quote and ',' not in after_quote and '}' not in after_quote:
                    # 미완성된 문자열 값으로 판단
                    repaired += '"'
        
        # 3단계: 중괄호 균형 맞추기
        open_braces = repaired.count('{')
        close_braces = repaired.count('}')
        
        if open_braces > close_braces:
            # 닫는 중괄호 추가
            missing_braces = open_braces - close_braces
            print(f"누락된 닫는 중괄호 {missing_braces}개 추가")
            repaired += '}' * missing_braces
        
        # 4단계: 배열 균형 맞추기 
        open_brackets = repaired.count('[')
        close_brackets = repaired.count(']')
        
        if open_brackets > close_brackets:
            # 닫는 대괄호 추가
            missing_brackets = open_brackets - close_brackets
            print(f"누락된 닫는 대괄호 {missing_brackets}개 추가")
            repaired += ']' * missing_brackets
        
        # 5단계: 불완전한 paragraphs 구조 복구
        if '"paragraphs"' in repaired and '"paragraphs": [' in repaired:
            # paragraphs 배열이 시작되었지만 완료되지 않은 경우
            paragraphs_start = repaired.find('"paragraphs": [')
            if paragraphs_start != -1:
                after_paragraphs = repaired[paragraphs_start + len('"paragraphs": ['):]
                # 마지막 paragraph가 완료되지 않은 경우 기본값으로 완성
                if '{' in after_paragraphs and after_paragraphs.count('{') > after_paragraphs.count('}'):
                    # 미완성된 paragraph 객체가 있음
                    if not repaired.rstrip().endswith('}') and not repaired.rstrip().endswith(']'):
                        # 기본값으로 완성
                        if '"summary"' in after_paragraphs and '"keyword"' not in after_paragraphs:
                            repaired += ', "keyword": "키워드 없음", "sentiment": "보통"}'
                        elif '"keyword"' in after_paragraphs and '"sentiment"' not in after_paragraphs:
                            repaired += ', "sentiment": "보통"}'
        
        # 6단계: 쉼표 정리
        repaired = re.sub(r',\s*([}\]])', r'\1', repaired)
        
        print(f"복구된 JSON: {repaired[:200]}...")
        
        # 7단계: JSON 유효성 검사
        json.loads(repaired)
        return repaired
        
    except Exception as e:
        print(f"JSON 복구 중 오류: {e}")
        return None


# 테스트 코드
if __name__ == "__main__":
    print("=== JSON 복구 모듈 테스트 ===")
    
    # 테스트용 잘린 JSON
    test_broken_json = '''{
"summary": "대화 내용의 핵심은...",
"keyword": ["네", "알", "서리머니"],
"paragraphs": [
{
"summary": "대화는 '네, 네'를...",
"keyword": ["네", "차량 발송'''
    
    print("원본 잘린 JSON:")
    print(test_broken_json)
    
    print("\n=== 복구 시도 ===")
    repaired = attempt_partial_json_completion(test_broken_json)
    
    print(f"\n=== 복구 결과 ===")
    print(repaired)
    
    # JSON 파싱 테스트
    try:
        parsed = json.loads(repaired)
        print("\n✅ JSON 파싱 성공!")
        print(f"summary: {parsed.get('summary', '없음')}")
        print(f"keyword: {parsed.get('keyword', '없음')}")
        print(f"paragraphs: {len(parsed.get('paragraphs', []))}개")
    except Exception as e:
        print(f"\n❌ JSON 파싱 실패: {e}")
