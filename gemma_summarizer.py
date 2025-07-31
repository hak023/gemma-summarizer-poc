import sys
import os
import time
import traceback
import threading
import re
import json
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

        # 프롬프트를 전문가 역할 기반으로 변경 (출력 예시 제거)
        prompt = (
            f"당신은 대화 내용을 분석하고 지정된 JSON 형식으로 요약하는 전문가입니다.\n"
            f"아래 [분석 규칙]을 참고하여, [원본 통화 내용]을 분석하고 완벽한 JSON을 생성하세요.\n\n"
            f"--- [분석 규칙] ---\n\n"
            f"summary: 통화의 핵심 내용을 20자 이내의 주어를 제외한 매우 짧은 한 문장'으로 요약하세요.\n"
            f"keyword: 가장 중요한 키워드를 3개 추출하여 쉼표로 구분하세요.\n"
            f"paragraphs: 통화 내용을 논리적 단위로 나누어 각각 분석하세요.\n"
#            f"통화 내용의 복잡도에 따라 2-3개의 paragraph를 생성하세요.\n"
            f"각 paragraph는 하나의 주제나 논점을 다루어야 하며, 다음 필드를 포함해야 합니다:\n"
            f"- summary: 해당 부분의 핵심 내용을 20자 이내의 길이로 요약\n"
            f"- keyword: 해당 부분의 주요 키워드를 2개 추출\n"
            f"- sentiment: 감정을 '강한긍정', '약한긍정', '보통', '약한부정', '강한부정' 중에서 선택\n\n"
            f"--- [출력 형식] ---\n"
            f"반드시 다음 JSON 형식으로 응답하세요:\n"
            f"```json\n"
            f'{{\n'
            f'"summary": "",\n'
            f'"keyword": "",\n'
            f'"paragraphs": [\n'
            f'{{\n'
            f'"summary": "",\n'
            f'"keyword": "",\n'
            f'"sentiment": ""\n'
            f'}},\n'
            f'{{\n'
            f'"summary": "",\n'
            f'"keyword": "",\n'
            f'"sentiment": ""\n'
            f'}}\n'
            f']\n'
            f'}}\n'
            f"```\n\n"
            f"대화화 내용:\n{text}\n\n"
            f"위 내용을 분석하여 JSON으로 응답하세요."
        )

        print("요약 생성 중...")
        log_gemma_query(prompt, "gemma_summarizer")

        # Gemma Query 시간 측정 시작
        gemma_query_start = time.time()
        
        # 1B 8Q 모델에 맞는 파라미터 조정
        output = llm(
            prompt,
            max_tokens=400,  # 작은 모델에 맞게 토큰 수 조정
            temperature=0.3,  # 더 일관된 응답을 위해 낮춤
            min_p=0.1,  # 최소 확률 조정
            top_p=0.8,  # 다양성 줄임
            top_k=20,  # 토큰 선택 범위 축소
            repeat_penalty=1.05,  # 반복 방지 (더 낮춤)
            echo=False
        )
        
        # Gemma Query 시간 측정 완료
        gemma_query_end = time.time()
        gemma_query_elapsed = gemma_query_end - gemma_query_start
        print(f"[Gemma Query 소요시간] {gemma_query_elapsed:.2f}초")
        
        print(f"output 전체: {output}")

        # 응답 처리 개선
        if hasattr(output, 'choices') and output.choices:
            result = output.choices[0].text.strip()
        elif isinstance(output, dict) and 'choices' in output:
            result = output['choices'][0]['text'].strip()
        else:
            result = str(output).strip()

        # 원본 응답을 항상 명확히 출력
        print(f"[원본 응답]:\n{result}\n---")
        log_gemma_response(result, "gemma_summarizer")

        # 마크다운 코드 블록에서 JSON만 파싱
        json_blocks = re.findall(r'```(?:json)?\s*(\{.*?\})\s*```', result, re.DOTALL)
        if json_blocks:
            json_str = json_blocks[0]  # 첫 번째 JSON 블록 사용
            print("마크다운 코드 블록에서 JSON 발견")
        else:
            # 마크다운 블록이 없으면 fallback
            print("```json으로 시작하는 마크다운 코드 블록을 찾을 수 없습니다.")
            return json.dumps({"summary": "올바른 JSON 형식을 찾을 수 없습니다.", "keyword": "", "paragraphs": []}, ensure_ascii=False)

        # 2. JSON 파싱 (마크다운 블록에서 추출한 JSON만 처리)
        try:
            # 기본적인 JSON 정리만 수행
            cleaned_json = json_str.strip()
            
            # trailing comma 제거
            cleaned_json = re.sub(r',\s*([}\]])', r'\1', cleaned_json)
            
            parsed_result = json.loads(cleaned_json)
            print("JSON 파싱 성공")
            
        except json.JSONDecodeError as e:
            print(f"JSON 파싱 실패: {e}")
            print(f"문제 JSON: {cleaned_json[:200]}...")
            
            # 마크다운 블록에서 추출한 JSON이 유효하지 않으면 오류 반환
            return json.dumps({"summary": "올바른 JSON 형식이 아닙니다.", "keyword": "", "paragraphs": []}, ensure_ascii=False)

        # 마크다운 블록에서 추출한 JSON을 후처리하여 반환
        processed_result = ResponsePostprocessor.process_response(parsed_result)
        return json.dumps(processed_result, ensure_ascii=False, indent=2)
            
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