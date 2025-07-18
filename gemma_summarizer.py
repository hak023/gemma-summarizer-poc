import sys
import os
import time
import traceback
import threading
from pathlib import Path
from config import get_config, get_model_path, validate_config
from logger import log_gemma_query, log_gemma_response
from preprocessor import STTPreprocessor
from postprocessor import ResponsePostprocessor
from llm_utils import correct_conversation_with_gemma

# 전역 모델 인스턴스 (싱글톤 패턴)
_llm_instance = None
_llm_lock = threading.Lock()

def resource_path(relative_path):
    """PyInstaller 환경에서 리소스 파일 경로를 올바르게 반환"""
    try:
        # PyInstaller 환경에서는 _MEIPASS 경로 사용
        if hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.abspath(".")
        
        full_path = os.path.join(base_path, relative_path)
        print(f"모델 경로: {full_path}")
        print(f"파일 존재 여부: {os.path.exists(full_path)}")
        return full_path
    except Exception as e:
        print(f"리소스 경로 오류: {e}")
        return relative_path

def get_llm_instance():
    """전역 모델 인스턴스를 반환 (싱글톤 패턴)"""
    global _llm_instance
    
    if _llm_instance is None:
        with _llm_lock:
            if _llm_instance is None:  # Double-checked locking
                try:
                    print("llama_cpp 모듈 임포트 중...")
                    from llama_cpp import Llama
                    print("llama_cpp 모듈 임포트 성공")
                    
                    # 설정 가져오기
                    config = get_config()
                    MODEL_PATH = get_model_path()
                    
                    print(f"모델 로딩 시작: {MODEL_PATH}")
                    _llm_instance = Llama(
                        model_path=MODEL_PATH, 
                        n_ctx=config['MODEL_CONTEXT_SIZE'],
                        n_threads=config['THREADS']
                    )
                    print("모델 로딩 완료")
                    
                except Exception as e:
                    print(f"모델 로딩 실패: {e}")
                    raise
    
    return _llm_instance

def summarize_with_gemma(text: str, max_tokens: int = None) -> str:
    """
    Gemma 모델을 사용하여 텍스트를 요약합니다.
    
    Args:
        text (str): 요약할 텍스트
        max_tokens (int, optional): 최대 토큰 수. None이면 설정값 사용
        
    Returns:
        str: 반드시 JSON 형태의 문자열 (summary 키에 요약)
    """
    try:
        # 설정 가져오기
        config = get_config()
        if max_tokens is None:
            max_tokens = config['DEFAULT_MAX_TOKENS']
        
        # 텍스트 전처리 (중복 제거)
        if text and isinstance(text, str):
            # 대화 형태로 분리
            lines = text.strip().split('\n')
            # 중복 제거
            cleaned_lines = STTPreprocessor.remove_duplicates(lines)
            # 다시 결합
            text = '\n'.join(cleaned_lines)
            print(f"전처리 후 텍스트 길이: {len(text)}자")
        
        llm = get_llm_instance()
        
        # 프롬프트: Few-shot 기법을 이용한 통화 분석 요청
        prompt = (
            f"당신은 통화 내용을 분석하고 지정된 JSON 형식으로 요약하는 전문가입니다.\n"
            f"아래 [분석 규칙]을 참고하여, [원본 통화 내용]을 분석하고 완벽한 JSON을 생성하세요.\n\n"
            f"--- [분석 규칙] ---\n"
            f"1. summary: 통화의 핵심 내용을 '매우 짧은 한 문장'으로 요약하세요. (약 30자 내외)\n"
            f"2. summary_no_limit: 전체 통화 내용을 상세하게 요약하세요.\n"
            f"3. keywords: 가장 중요한 키워드를 5개 추출하여 쉼표로 구분하세요.\n"
            f"4. call_purpose: 통화의 목적을 '짧은 구절'로 요약하세요. (약 20자 내외)\n"
            f"5. my_main_content: '나'의 주요 발언을 요약이 아닌, 실제 내용 중심으로 상세히 기록하세요.\n"
            f"6. caller_main_content: '상대방'의 주요 발언을 실제 내용 중심으로 상세히 기록하세요.\n"
            f"7. my_emotion: 나의 감정은 '보통', '만족', '불만', '화남', '신남', '우려' 중에서 선택하세요.\n"
            f"8. caller_emotion: 상대방의 감정은 '보통', '만족', '불만', '화남', '신남', '우려' 중에서 선택하세요.\n"
            f"9. caller_info: 상대방이 직접 밝힌 신상 정보(이름, 소속 등)를 기재하고, 없으면 빈 문자열 \"\"로 두세요.\n"
            f"10. my_action_after_call: 통화 후 '나'의 할 일을 명확히 쓰고, 없으면 \"없음\"으로 기재하세요.\n\n"
            f"--- [출력 형식] ---\n"
            f"반드시 다음 JSON 형식으로 응답하세요:\n"
            f"{{\n"
            f'    "summary": "",\n'
            f'    "summary_no_limit": "",\n'
            f'    "keywords": "",\n'
            f'    "call_purpose": "",\n'
            f'    "my_main_content": "",\n'
            f'    "caller_main_content": "",\n'
            f'    "my_emotion": "",\n'
            f'    "caller_emotion": "",\n'
            f'    "caller_info": "",\n'
            f'    "my_action_after_call": ""\n'
            f"}}\n\n"
            f"--- [원본 통화 내용] ---\n"
            f"{text}\n\n"
            f"위 통화 내용을 분석하여 JSON 형식으로 응답하세요:\n"
        )
        
        print("요약 생성 중...")
        log_gemma_query(prompt, "gemma_summarizer")
        
        # 모델 호출 - llama_cpp의 올바른 API 사용
        output = llm(
            prompt,
            max_tokens=2000,  # 충분한 토큰 수 확보
            temperature=0.9,  # 창의적이면서도 일관성 유지
            top_p=0.7,  # 적절한 다양성 유지
            top_k=20,  # 적절한 토큰 선택
            repeat_penalty=1.3,  # 반복 방지
            echo=False
        )
        print(f"output 전체: {output}")
        
        # 응답 처리 개선
        import re, json
        if hasattr(output, 'choices') and output.choices:
            result = output.choices[0].text.strip()
        elif isinstance(output, dict) and 'choices' in output:
            result = output['choices'][0]['text'].strip()
        else:
            result = str(output).strip()
        
        # 원본 응답을 항상 명확히 출력
        print(f"[원본 응답]:\n{result}\n---")
        log_gemma_response(result, "gemma_summarizer")
        
        # JSON robust 파싱 - 새로운 구조에 맞게 수정
        parsed_result = None
        try:
            # 1. ```json ... ``` 블록 우선 추출
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', result, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 2. 그냥 { ... } 블록 (모든 필드 포함)
                json_match = re.search(r'\{[^{}]*"summary"[^{}]*"keywords"[^{}]*\}', result, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    # 3. 더 넓은 범위로 JSON 찾기
                    json_match = re.search(r'\{.*?\}', result, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(0)
                    else:
                        # 4. JSON을 찾을 수 없으면 fallback
                        print("JSON을 찾을 수 없습니다. 전체 응답을 반환합니다.")
                        return json.dumps({"summary": result.strip()}, ensure_ascii=False)
            
            # JSON 파싱
            parsed_result = json.loads(json_str)
            
            # 필수 필드 확인 및 기본값 설정
            required_fields = {
                'summary': '',
                'summary_no_limit': '',
                'keywords': '',
                'call_purpose': '',
                'my_main_content': '',
                'caller_main_content': '',
                'my_emotion': '보통',
                'caller_emotion': '보통',
                'caller_info': '',
                'my_action_after_call': '없음'
            }
            
            # 기존 값과 기본값 병합
            for field, default_value in required_fields.items():
                if field not in parsed_result:
                    parsed_result[field] = default_value
                elif parsed_result[field] is None:
                    parsed_result[field] = default_value
                    
        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            print(f"JSON 파싱 오류: {e}")
            # fallback: 개별 필드 추출 시도
            parsed_result = {
                'summary': '',
                'summary_no_limit': '',
                'keywords': '',
                'call_purpose': '',
                'my_main_content': '',
                'caller_main_content': '',
                'my_emotion': '보통',
                'caller_emotion': '보통',
                'caller_info': '',
                'my_action_after_call': '없음'
            }
            
            # 개별 필드 추출
            field_patterns = {
                'summary': r'"summary"\s*:\s*"([^"]+)"',
                'summary_no_limit': r'"summary_no_limit"\s*:\s*"([^"]+)"',
                'keywords': r'"keywords"\s*:\s*"([^"]+)"',
                'call_purpose': r'"call_purpose"\s*:\s*"([^"]+)"',
                'my_main_content': r'"my_main_content"\s*:\s*"([^"]+)"',
                'caller_main_content': r'"caller_main_content"\s*:\s*"([^"]+)"',
                'my_emotion': r'"my_emotion"\s*:\s*"([^"]+)"',
                'caller_emotion': r'"caller_emotion"\s*:\s*"([^"]+)"',
                'caller_info': r'"caller_info"\s*:\s*"([^"]*)"',
                'my_action_after_call': r'"my_action_after_call"\s*:\s*"([^"]+)"'
            }
            
            for field, pattern in field_patterns.items():
                match = re.search(pattern, result)
                if match:
                    parsed_result[field] = match.group(1)
        
        # 최종 결과를 JSON 형태로 반환
        if parsed_result:
            # 후처리 적용
            processed_result = ResponsePostprocessor.process_response(parsed_result)
            return json.dumps(processed_result, ensure_ascii=False, indent=2)
        else:
            fallback_data = {"summary": result.strip()}
            processed_fallback = ResponsePostprocessor.process_response(fallback_data)
            return json.dumps(processed_fallback, ensure_ascii=False, indent=2)
    except Exception as e:
        error_msg = f"요약 생성 중 오류 발생: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return json.dumps({"summary": "요약을 생성할 수 없습니다."}, ensure_ascii=False)

def process_request(data: dict) -> dict:
    """
    요청 데이터를 처리하여 응답을 반환합니다.
    
    Args:
        data (dict): 요청 데이터 (request_id, text 포함)
        
    Returns:
        dict: 새로운 응답 규격에 맞는 응답 데이터
    """
    try:
        # 요청 데이터에서 필요한 정보 추출
        transactionid = data.get("transactionid", "")
        sequenceno = data.get("sequenceno", "0")
        request_id = data.get("request_id", "unknown")
        text = data.get("text", "")
        
        if not text.strip():
            response_data = {
                "transactionid": transactionid,
                "sequenceno": sequenceno,
                "returncode": "1",
                "returndescription": "Success",
                "response": {
                    "result": "1",
                    "failReason": "입력 텍스트가 비어있습니다.",
                    "summary": ""
                }
            }
            return response_data
        
        print(f"요청 처리 시작 (ID: {request_id})")
        start_time = time.time()
        
        # 요약 수행
        summary = summarize_with_gemma(text)
        
        processing_time = time.time() - start_time
        print(f"요청 처리 완료 (ID: {request_id}, 소요시간: {processing_time:.2f}초)")
        
        # 성공 응답
        response_data = {
            "transactionid": transactionid,
            "sequenceno": sequenceno,
            "returncode": "1",
            "returndescription": "Success",
            "response": {
                "result": "0",
                "failReason": "",
                "summary": summary
            }
        }
        
        return response_data
        
    except Exception as e:
        error_msg = f"요청 처리 중 오류: {str(e)}"
        print(error_msg)
        
        # 오류 응답
        response_data = {
            "transactionid": data.get("transactionid", ""),
            "sequenceno": data.get("sequenceno", "0"),
            "returncode": "1",
            "returndescription": "Success",
            "response": {
                "result": "1",
                "failReason": error_msg,
                "summary": ""
            }
        }
        
        return response_data

# 단독 실행 시 테스트
if __name__ == "__main__":
    print("=== Gemma Summarizer 모듈 테스트 ===")
    
    # 설정 유효성 검사
    if not validate_config():
        print("설정 오류가 있습니다. config.py를 확인해주세요.")
        sys.exit(1)
    
    # 테스트 텍스트
    test_text = """
    김민준 팀장: 여보세요, 이서연 대리님. 김민준 팀장입니다.

이서연 대리: 네, 팀장님! 안녕하세요. 전화 주셨네요.

김민준 팀장: 네, 다름이 아니라 다음 주 수요일로 예정된 '알파 프로젝트' 신제품 런칭 캠페인 관련해서 최종 진행 상황 좀 체크하려고 전화했어요. 준비는 잘 되어가고 있죠?

이서연 대리: 아, 네. 마침 저도 중간 보고 드리려고 했습니다. 먼저, SNS 광고 소재는 어제 디자인팀에서 시안 2개를 받았고, 오늘 오후까지 제가 최종 1개 선택해서 전달드리겠습니다.
    """
    
    # 요약 테스트
    result = summarize_with_gemma(test_text)
    print(f"\n=== 요약 결과 ===")
    print(result) 