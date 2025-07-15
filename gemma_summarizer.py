import sys
import os
import time
import traceback
import threading
from pathlib import Path
from config import get_config, get_model_path, validate_config
from logger import log_request_response

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
        str: 요약된 텍스트 또는 오류 메시지
    """
    try:
        # 설정 가져오기
        config = get_config()
        if max_tokens is None:
            max_tokens = config['DEFAULT_MAX_TOKENS']
        
        # 전역 모델 인스턴스 사용
        llm = get_llm_instance()
        
        prompt = f"""너는 아래 통화 내용을 한 문장으로 된 '제목'으로 만들어야 해.

[지시사항]
- 통화의 전체 내용을 대표하는 가장 핵심적인 제목을 만들 것.
- 제목은 30자 이내의 완결된 한 문장이어야 함.
- `summary:`나 `핵심:` 같은 접두사나 다른 부가 설명 없이, 오직 제목 문장만 생성할 것.

[통화 내용]
{text}
"""
        print("요약 생성 중...")
        output = llm(prompt, max_tokens=max_tokens)
        result = output["choices"][0]["text"].strip()
        print(f"요약 완료: {result}")
        return result
        
    except Exception as e:
        error_msg = f"요약 생성 중 오류 발생: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return error_msg

def process_request(data: dict) -> dict:
    """
    요청 데이터를 처리하여 응답을 반환합니다.
    
    Args:
        data (dict): 요청 데이터 (request_id, text 포함)
        
    Returns:
        dict: 응답 데이터 (type, summary, request_id, status, processing_time 포함)
    """
    try:
        request_id = data.get("request_id", "unknown")
        text = data.get("text", "")
        
        if not text.strip():
            response_data = {
                "type": "response",
                "summary": "입력 텍스트가 비어있습니다.",
                "request_id": request_id,
                "status": "error",
                "processed": False
            }
            return response_data
        
        print(f"요청 처리 시작 (ID: {request_id})")
        start_time = time.time()
        
        # 요약 수행
        summary = summarize_with_gemma(text)
        
        processing_time = time.time() - start_time
        print(f"요청 처리 완료 (ID: {request_id}, 소요시간: {processing_time:.2f}초)")
        
        response_data = {
            "type": "response",
            "summary": summary,
            "request_id": request_id,
            "status": "success",
            "processing_time": processing_time,
            "processed": False
        }
        
        # 로그 기록 (반복 로그 방지)
        log_request_response(data, response_data, processing_time, process_name="gemma_summarizer")
        
        return response_data
        
    except Exception as e:
        error_msg = f"요청 처리 중 오류: {str(e)}"
        print(error_msg)
        
        response_data = {
            "type": "response",
            "summary": error_msg,
            "request_id": data.get("request_id", "unknown"),
            "status": "error",
            "processed": False
        }
        
        # 오류 로그 기록 (반복 로그 방지)
        log_request_response(data, response_data, process_name="gemma_summarizer")
        
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