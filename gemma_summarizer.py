import sys
import os
import time
import traceback
import threading
import re
import json
import multiprocessing
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
                    
                    # CPU 제한 강제 적용
                    cpu_count = multiprocessing.cpu_count()
                    cpu_limit_percent = int(os.getenv('CPU_LIMIT_PERCENT', 25))  # 기본값 25%로 더 엄격하게
                    max_threads = max(1, int(cpu_count * cpu_limit_percent / 100))
                    
                    # 환경 변수로 강제 스레드 수 설정 가능
                    force_threads = os.getenv('MAX_CPU_THREADS')
                    if force_threads:
                        max_threads = int(force_threads)
                    
                    print(f"CPU 제한 적용: {cpu_count}개 코어의 {cpu_limit_percent}% = {max_threads}개 스레드 사용")
                    
                    _llm_instance = Llama(
                        model_path=MODEL_PATH,
                        n_ctx=config['MODEL_CONTEXT_SIZE'],
                        n_threads=max_threads  # 강제 제한된 스레드 수 사용
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

        # 프롬프트를 요점 중심으로 변경 (간결한 요약) - 강제성 강화
        prompt = (
            f"당신은 대화 내용을 분석하고 지정된 JSON 형식으로 요약하는 전문가입니다.\n"
            f"반드시 아래 형식에 맞춰 JSON으로 응답하세요.\n\n"
            f"--- [분석 규칙] ---\n"
            f"1. summary: 통화의 핵심 내용을 25자 이내의 주어를 제외한 짧은 한 문장으로 요약하세요.\n"
            f"2. keyword: 가장 중요한 키워드 3개를 쉼표로 구분\n"
            f"3. paragraphs: 통화 내용을 2-3개 단위로 분석 (반드시 포함)\n"
            f"  - 각 paragraph는 반드시 다음 필드를 포함해야 합니다:\n"
            f"    * summary: 해당 부분의 핵심 내용을 25자 이내로 요약\n"
            f"    * keyword: 해당 부분의 주요 키워드 3개를 쉼표로 구분\n"
            f"    * sentiment: 감정을 '강한긍정', '약한긍정', '보통', '약한부정', '강한부정' 중에서 선택\n\n"
            f"--- [응답 형식] ---\n"
            f"반드시 이 형식으로만 응답하세요:\n"
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
            f"대화 내용:\n{text}\n\n"
            f"위 내용을 분석하여 반드시 JSON 형식으로 응답하세요."
        )

        print("요약 생성 중...")
        log_gemma_query(prompt, "gemma_summarizer")

        # Gemma Query 시간 측정 시작
        gemma_query_start = time.time()
        
        # 성능 최적화 설정 적용
        config = get_config()
        model_timeout = config.get('MODEL_TIMEOUT', 180.0)
        enable_fast_mode = config.get('ENABLE_FAST_MODE', False)
        
        # 빠른 모드 설정
        if enable_fast_mode:
            max_tokens = config.get('FAST_MODE_MAX_TOKENS', 300)
            print(f"빠른 모드 활성화: 최대 토큰 수 {max_tokens}")
        else:
            max_tokens = 600  # paragraphs 생성을 위해 토큰 수 증가
        
        print(f"모델 추론 시작 (타임아웃: {model_timeout}초)")
        
        # 1B 8Q 모델에 맞는 파라미터 조정 (일관성 강화)
        output = llm(
            prompt,
            max_tokens=max_tokens,
            temperature=0.3,  # 매우 낮은 temperature로 일관성 극대화
            min_p=0.1,  # 더 엄격한 최소 확률
            top_p=0.8,  # 더 낮은 top_p로 일관성 향상
            top_k=20,  # 더 좁은 토큰 선택 범위
            repeat_penalty=1.05,  # 반복 방지 강화
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
        # 디버깅 출력 최적화 (빠른 모드에서는 간소화)
        if not enable_fast_mode:
            print(f"=== 원본 응답 디버깅 ===")
            print(f"원본 응답 길이: {len(result)}")
            print(f"원본 응답 전체:\n{result}")
            print(f"=== 원본 응답 끝 ===")
        else:
            print(f"빠른 모드: 원본 응답 길이 {len(result)}자")
        
        # ```json 형식을 유연하게 찾기 (중첩된 중괄호 처리 개선)
        # 첫 번째 {와 마지막 } 사이의 모든 내용을 추출하는 방식으로 변경
        json_start = result.find('```json')
        if json_start != -1:
            # ```json 이후의 첫 번째 { 찾기
            brace_start = result.find('{', json_start)
            if brace_start != -1:
                # 중괄호 카운팅으로 완전한 JSON 추출
                brace_count = 0
                json_end = brace_start
                for i in range(brace_start, len(result)):
                    if result[i] == '{':
                        brace_count += 1
                    elif result[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break
                
                json_str = result[brace_start:json_end]
                print("```json 마크다운 코드 블록에서 JSON 발견 (중괄호 카운팅)")
            else:
                print("```json 블록에서 { 를 찾을 수 없습니다.")
                return json.dumps({"summary": "올바른 JSON 형식을 찾을 수 없습니다.", "keyword": "", "paragraphs": []}, ensure_ascii=False)
        else:
            # ```json이 없으면 일반 ``` 블록에서 JSON 찾기
            json_start = result.find('```')
            if json_start != -1:
                # ``` 이후의 첫 번째 { 찾기
                brace_start = result.find('{', json_start)
                if brace_start != -1:
                    # 중괄호 카운팅으로 완전한 JSON 추출
                    brace_count = 0
                    json_end = brace_start
                    for i in range(brace_start, len(result)):
                        if result[i] == '{':
                            brace_count += 1
                        elif result[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_end = i + 1
                                break
                    
                    json_str = result[brace_start:json_end]
                    print("일반 마크다운 코드 블록에서 JSON 발견 (중괄호 카운팅)")
                else:
                    print("일반 ``` 블록에서 { 를 찾을 수 없습니다.")
                    return json.dumps({"summary": "올바른 JSON 형식을 찾을 수 없습니다.", "keyword": "", "paragraphs": []}, ensure_ascii=False)
            else:
                # 마크다운 블록이 없으면 fallback
                print("모든 패턴으로 ```json 블록을 찾을 수 없습니다.")
                return json.dumps({"summary": "올바른 JSON 형식을 찾을 수 없습니다.", "keyword": "", "paragraphs": []}, ensure_ascii=False)

        # 2. JSON 파싱 (마크다운 블록에서 추출한 JSON만 처리)
        try:
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
            
            # 3단계: 추가 정리
            # 불필요한 공백 제거
            cleaned_json = re.sub(r'\s+', ' ', cleaned_json)
            # 마지막 쉼표 제거
            cleaned_json = re.sub(r',\s*([}\]])', r'\1', cleaned_json)
            
            parsed_result = json.loads(cleaned_json)
            print("JSON 파싱 성공")
            
        except json.JSONDecodeError as e:
            print(f"JSON 파싱 실패: {e}")
            print(f"문제 JSON: {cleaned_json[:200]}...")
            
            # 추가 복구 시도: 중괄호 밖의 내용 제거
            try:
                # 첫 번째 {와 마지막 } 사이만 추출
                brace_match = re.search(r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})', cleaned_json, re.DOTALL)
                if brace_match:
                    cleaned_json = brace_match.group(1)
                    print(f"중괄호 기반 복구 시도: {len(cleaned_json)}자")
                    parsed_result = json.loads(cleaned_json)
                    print("JSON 파싱 복구 성공")
                else:
                    raise Exception("중괄호 패턴을 찾을 수 없습니다")
            except Exception as recovery_error:
                print(f"복구 시도 실패: {recovery_error}")
                # 마크다운 블록에서 추출한 JSON이 유효하지 않으면 오류 반환
                return json.dumps({"summary": "올바른 JSON 형식을 찾을 수 없습니다.", "keyword": "", "paragraphs": []}, ensure_ascii=False)

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

        # 첫 번째 요약 수행
        summary = summarize_with_gemma(text)
        
        # 후처리 수행
        try:
            # summarize_with_gemma 함수에서 이미 1차 후처리를 완료했으므로,
            # 여기서는 json 파싱만 수행하여 재질의 필요 여부를 확인합니다.
            processed_response = json.loads(summary)
            
            # ResponsePostprocessor로 최종 후처리 수행
            processed_response = ResponsePostprocessor.process_response(processed_response)
            
            processed_summary = processed_response.get('summary', '')
            
            # 재질의 필요 여부 확인
            if processed_summary.startswith('[재질의 필요]'):
                print(f"재질의 필요 감지: {processed_summary}")
                print(f"재질의 전 processed_response: {json.dumps(processed_response, ensure_ascii=False, indent=2)}")
                print(f"재질의 전 keyword: {processed_response.get('keyword', '없음')}")
                print(f"재질의 전 sentiment: {processed_response.get('sentiment', '없음')}")
                
                # 재질의용 프롬프트 생성 (이미 처리된 summary를 재질의)
                # [재질의 필요] 문구 제거
                original_summary = processed_summary.replace('[재질의 필요] ', '')
                requery_prompt = (
                    f"다음 요약을 매우 짧은 요약으로 다시 요약해주세요.\n\n"
                    f"예시:\n"
                    f"원본: 기존 평생 교육 희망 카드는 작년까지만 사용 가능했고 농협 체험 카드를 발급받아야 포인트 지급 가능하여 카드 발급 방법을 안내드렸습니다.\n"
                    f"요약: 농협 카드 발급 안내\n\n"
                    f"원본 요약:\n{original_summary}\n\n"
                    f"재요약:"
                )
                
                # 재질의 수행
                config = get_config()
                llm = get_llm_instance()
                requery_response = llm(
                    requery_prompt,
                    max_tokens=100,
                    temperature=0.3,
                    stop=["\n\n", "```"]
                )
                
                requery_summary = requery_response['choices'][0]['text'].strip()
                print(f"재질의 결과: {requery_summary}")
                
                # 재질의 결과를 processed_response의 summary에 직접 설정
                # 기존 processed_response 구조는 유지하고 summary만 업데이트
                print(f"재질의 전 processed_response 타입: {type(processed_response)}")
                print(f"재질의 전 processed_response 키: {list(processed_response.keys())}")
                print(f"재질의 전 processed_response 전체: {json.dumps(processed_response, ensure_ascii=False, indent=2)}")
                
                # summary만 업데이트
                processed_response['summary'] = requery_summary
                
                print(f"재질의 후 processed_response: {json.dumps(processed_response, ensure_ascii=False, indent=2)}")
                print(f"재질의 후 keyword: {processed_response.get('keyword', '없음')}")
                print(f"재질의 후 sentiment: {processed_response.get('sentiment', '없음')}")
                print(f"재질의 후 processed_response 타입: {type(processed_response)}")
                print(f"재질의 후 processed_response 키: {list(processed_response.keys())}")
                
            # 최종 결과를 JSON으로 직렬화
            # processed_response는 이미 올바른 구조를 가지고 있으므로 그대로 사용
            summary = json.dumps(processed_response, ensure_ascii=False)
                
        except json.JSONDecodeError:
            print("원본 요약 JSON 파싱 실패 - 원본 사용")
            # JSON 파싱 실패 시 원본 사용
            pass

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

    # 테스트 텍스트 (재질의 발생을 위한 매우 긴 텍스트)
    test_text = """
    김민준 팀장: 여보세요, 이서연 대리님. 김민준 팀장입니다.

이서연 대리: 네, 팀장님! 안녕하세요. 전화 주셨네요.

김민준 팀장: 네, 다름이 아니라 다음 주 수요일로 예정된 '알파 프로젝트' 신제품 런칭 캠페인 관련해서 최종 진행 상황 좀 체크하려고 전화했어요. 준비는 잘 되어가고 있죠?

이서연 대리: 아, 네. 마침 저도 중간 보고 드리려고 했습니다. 먼저, SNS 광고 소재는 어제 디자인팀에서 시안 2개를 받았고, 오늘 오후까지 제가 최종 1개 선택해서 전달드리겠습니다. 그리고 인플루언서 협업은 총 5명과 계약이 완료되었고, 각각의 콘텐츠 기획안도 승인받았습니다. 또한 오프라인 이벤트는 다음 주 월요일부터 목요일까지 4일간 강남역, 홍대입구, 부산 서면에서 진행할 예정이고, 현장 스태프 20명도 모두 확정되었습니다. 마지막으로 디지털 마케팅 예산은 총 5천만원으로 설정했고, 페이스북, 인스타그램, 유튜브 채널에 골고루 배분했습니다. 그리고 추가로 고객 데이터베이스 구축도 완료되었고, CRM 시스템 연동도 끝났습니다. 마케팅 자동화 툴도 설정 완료했고, A/B 테스트 계획도 수립했습니다. 소셜미디어 모니터링 시스템도 구축했고, 실시간 대시보드도 준비했습니다. 고객 피드백 수집 시스템도 구축했고, 분석 리포트 템플릿도 만들었습니다. 그리고 추가로 네이버 블로그 마케팅도 진행할 예정이고, 카카오톡 채널도 개설해서 고객과의 소통 채널을 확보했습니다. 마지막으로 PR 활동도 준비 중이며, 주요 IT 매체들과 인터뷰 일정도 조율하고 있습니다. 그리고 고객 만족도 조사 시스템도 구축했고, 리뷰 관리 시스템도 준비했습니다. 마케팅 성과 측정 지표도 설정했고, ROI 분석 도구도 구축했습니다.
    """

    # 요약 테스트
    result = summarize_with_gemma(test_text)
    print(f"\n=== 요약 결과 ===")
    print(result)