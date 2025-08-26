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
from json_repair import (
    extract_json_from_markdown,
    process_and_repair_json,
    extract_valid_data_from_broken_json
)

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
                    force_threads = config.get('MAX_CPU_THREADS')
                    if force_threads is not None:
                        # 강제 스레드 수 설정
                        max_threads = force_threads
                        print(f"강제 스레드 수 설정: {max_threads}")
                    else:
                        # get_optimal_threads() 결과 사용
                        from config import get_optimal_threads
                        max_threads = get_optimal_threads()
                    
                    print(f"최종 사용 스레드 수: {max_threads}")
                    
                    # GPU 사용 설정 적용
                    enable_gpu = bool(config.get('ENABLE_GPU', False))
                    n_gpu_layers = 0
                    env_n_gpu_layers = os.getenv('N_GPU_LAYERS')
                    if enable_gpu:
                        try:
                            n_gpu_layers = int(env_n_gpu_layers) if env_n_gpu_layers is not None else -1
                        except ValueError:
                            n_gpu_layers = -1
                    # CUDA/오프로딩 지원 및 환경 정보 출력
                    try:
                        import llama_cpp as _llama_cpp
                        from llama_cpp import llama_supports_gpu_offload as _llama_supports_gpu_offload
                        print(f"llama_cpp 버전: {getattr(_llama_cpp, '__version__', 'n/a')}")
                        print(f"GPU 오프로딩 지원: {_llama_supports_gpu_offload()}")
                    except Exception as _gpu_info_err:
                        print(f"GPU 지원 정보 확인 실패: {_gpu_info_err}")
                    print(f"CUDA_VISIBLE_DEVICES={os.getenv('CUDA_VISIBLE_DEVICES')}")
                    print(f"GPU 사용 설정: {'활성화' if enable_gpu else '비활성화'} (n_gpu_layers={n_gpu_layers})")

                    # OS 레벨에서 CPU 사용량 제한 설정
                    if hasattr(os, 'sched_setaffinity'):
                        # Linux에서 CPU 코어 제한
                        available_cpus = list(range(max_threads))
                        os.sched_setaffinity(0, available_cpus)
                        print(f"CPU 친화성 설정: {available_cpus}")
                    elif os.name == 'nt':
                        # Windows에서 프로세스 우선순위 조정
                        try:
                            import psutil
                            current_process = psutil.Process()
                            current_process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                            print(f"프로세스 우선순위 조정 완료")
                        except ImportError:
                            print("psutil 패키지가 없어 우선순위 조정을 건너뜁니다")
                    
                    # 환경변수로 OpenMP 스레드 수 제한
                    os.environ['OMP_NUM_THREADS'] = str(max_threads)
                    os.environ['MKL_NUM_THREADS'] = str(max_threads)
                    os.environ['OPENBLAS_NUM_THREADS'] = str(max_threads)
                    os.environ['VECLIB_MAXIMUM_THREADS'] = str(max_threads)
                    os.environ['NUMEXPR_NUM_THREADS'] = str(max_threads)
                    
                    print(f"환경변수 스레드 제한 설정: {max_threads}")

                    _llm_instance = Llama(
                        model_path=MODEL_PATH,
                        n_ctx=config['MODEL_CONTEXT_SIZE'],
                        n_threads=max_threads,
                        n_threads_batch=max_threads,  # 배치 처리 스레드도 제한
                        n_gpu_layers=n_gpu_layers,
                        verbose=False  # 불필요한 출력 줄이기
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
            #f"아래 [분석 규칙]을 참고하여, [원본 통화 내용]을 분석하고 완벽한 JSON을 생성하세요.\n\n"
            f"--- [분석 규칙] ---\n"
            f"summary: 통화의 핵심 내용을 25자 이내의 주어를 제외한 매우 짧은 한 문장으로 요약하세요. 문장의 끝은 '명사형' 으로 끝내야 합니다.\n"
            f"keyword: 가장 중요한 키워드를 3개 추출하여 쉼표로 구분하세요.\n"
            f"paragraphs: 통화 내용을 반드시 2-3개의 논리적 단위로 나누어 각각 분석하세요.\n"
            f"  - 각 paragraph는 반드시 다음 필드를 포함해야 합니다:\n"
            f"    * summary: 해당 부분의 핵심 내용을 25자 이내로 요약\n"
            f"    * keyword: 해당 부분의 주요 키워드 3개를 쉼표로 구분\n"
            f"    * sentiment: 감정을 '강한긍정', '약한긍정', '보통', '약한부정', '강한부정' 중에서 선택\n\n"
            f"--- [응답 형식] ---\n"
            f"반드시 이 형식으로만 응답하세요:\n"
            f"```json\n"
            f'{{\n'
            f'"summary": "통화 핵심 요약",\n'
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
            f"위 내용을 분석하여 반드시 paragraphs를 포함한 완전한 JSON으로 응답하세요."
        )

        print("요약 생성 중...")
        log_gemma_query(prompt, "gemma_summarizer")

        # Gemma Query 시간 측정 시작
        gemma_query_start = time.time()
        
        # 성능 최적화 설정 적용
        config = get_config()
        model_timeout = config.get('MODEL_TIMEOUT', 180.0)
        
        # 토큰 수 설정 (Context Window 고려하여 동적 계산)
        config = get_config()
        context_size = config['MODEL_CONTEXT_SIZE']
        
        # 프롬프트 토큰 수 추정 (실제 토큰화는 비용이 크므로 추정)
        # 완성된 prompt 길이를 직접 사용 (한글 1글자 ≈ 0.8토큰)
        estimated_prompt_tokens = len(prompt) * 0.8  # 한글 토큰 비율 적용 (실제 데이터 기반)
        available_tokens = context_size - estimated_prompt_tokens - 100  # 100토큰 여유
        
        # max_tokens를 사용 가능한 토큰 수로 제한 (최소값 보장)
        max_tokens = max(500, min(4000, available_tokens))  # 최소 500, 최대 4000토큰
        
        # 프롬프트가 너무 길어서 Context Window 초과하는 경우 처리
        if available_tokens < 500:
            print(f"⚠️ 프롬프트가 Context Window를 초과합니다!")
            print(f"Context: {context_size}, 프롬프트: {estimated_prompt_tokens}")
            print(f"텍스트를 줄이거나 Context Window를 늘려야 합니다.")
            max_tokens = 500  # 최소 응답 보장
        
        print(f"추정 프롬프트 토큰: {estimated_prompt_tokens}, 사용 가능 토큰: {available_tokens}, 설정된 max_tokens: {max_tokens}")
        
        print(f"모델 추론 시작 (타임아웃: {model_timeout}초)")
        
        # 1B 8Q 모델에 맞는 파라미터 조정 (일관성 강화)
        print(f"설정된 max_tokens: {max_tokens}")
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
            # 토큰 제한으로 잘렸는지 확인
            choice = output.choices[0]
            if hasattr(choice, 'finish_reason'):
                finish_reason = choice.finish_reason
                print(f"생성 종료 이유: {finish_reason}")
                if finish_reason == 'length':
                    print(f"⚠️  토큰 제한({max_tokens})으로 응답이 잘렸습니다!")
        elif isinstance(output, dict) and 'choices' in output:
            result = output['choices'][0]['text'].strip()
            # 토큰 제한으로 잘렸는지 확인 (dict 형태)
            choice = output['choices'][0]
            if 'finish_reason' in choice:
                finish_reason = choice['finish_reason']
                print(f"생성 종료 이유: {finish_reason}")
                if finish_reason == 'length':
                    print(f"⚠️  토큰 제한({max_tokens})으로 응답이 잘렸습니다!")
        else:
            result = str(output).strip()

        # 응답 길이 정보 출력
        print(f"생성된 응답 길이: {len(result)}자")
        
        # 토큰 제한으로 잘린 경우 재시도 로직
        was_truncated = False
        if hasattr(output, 'choices') and output.choices:
            choice = output.choices[0]
            if hasattr(choice, 'finish_reason') and choice.finish_reason == 'length':
                was_truncated = True
        elif isinstance(output, dict) and 'choices' in output:
            choice = output['choices'][0]
            if choice.get('finish_reason') == 'length':
                was_truncated = True
        
        # JSON이 완전하지 않은 경우도 체크
        if not was_truncated and result:
            # JSON 블록이 있는지 확인
            if '```json' in result:
                json_block = result[result.find('```json'):]
                # JSON이 제대로 닫히지 않은 경우
                if json_block.count('{') != json_block.count('}'):
                    print("⚠️  JSON 중괄호가 맞지 않아 잘린 것으로 판단됩니다.")
                    was_truncated = True
        
        # 잘린 경우 한 번 더 시도 (토큰 수 증가)
        if was_truncated and max_tokens < 1200:
            retry_max_tokens = max_tokens * 2
            print(f"🔄 토큰 제한으로 잘린 응답 재시도 (max_tokens: {max_tokens} → {retry_max_tokens})")
            
            retry_output = llm(
                prompt,
                max_tokens=retry_max_tokens,
                temperature=0.3,
                min_p=0.1,
                top_p=0.8,
                top_k=20,
                repeat_penalty=1.05,
                echo=False
            )
            
            # 재시도 결과 처리
            if hasattr(retry_output, 'choices') and retry_output.choices:
                retry_result = retry_output.choices[0].text.strip()
                print(f"재시도 응답 길이: {len(retry_result)}자")
                
                # 재시도가 더 나은 결과를 생성했는지 확인
                if len(retry_result) > len(result) and '```json' in retry_result:
                    print("✅ 재시도 성공 - 더 완전한 응답 획득")
                    result = retry_result
                    output = retry_output
            elif isinstance(retry_output, dict) and 'choices' in retry_output:
                retry_result = retry_output['choices'][0]['text'].strip()
                print(f"재시도 응답 길이: {len(retry_result)}자")
                
                if len(retry_result) > len(result) and '```json' in retry_result:
                    print("✅ 재시도 성공 - 더 완전한 응답 획득")
                    result = retry_result
                    output = retry_output
        
        # 원본 응답을 항상 명확히 출력
        print(f"[원본 응답]:\n{result}\n---")
        log_gemma_response(result, "gemma_summarizer")


        
        # JSON 추출 및 처리 (json_repair 모듈 사용)
        json_str = extract_json_from_markdown(result)
        
        if json_str is None:
            # JSON 추출 실패 시 원본에서 데이터 추출
            print("JSON 추출 실패 - 원본 데이터 추출 시도")
            extracted_data = extract_valid_data_from_broken_json(result)
            processed_result = ResponsePostprocessor.process_response(extracted_data)
            return json.dumps(processed_result, ensure_ascii=False, indent=2)
        
        # JSON 처리 및 복구
        final_json = process_and_repair_json(json_str)
        
        # 최종 후처리
        try:
            parsed_result = json.loads(final_json)
            print(f"🔍 후처리 전 parsed_result: {parsed_result}")
            processed_result = ResponsePostprocessor.process_response(parsed_result)
            print(f"🔍 후처리 후 processed_result: {processed_result}")
            return json.dumps(processed_result, ensure_ascii=False, indent=2)
        except json.JSONDecodeError as e:
            # JSON 파싱 실패 시 상세 로그 출력
            print(f"❌ summarize_with_gemma JSON 파싱 실패: {str(e)}")
            print(f"📄 실패한 JSON 전체 내용 (길이: {len(final_json)} 문자):")
            print("="*80)
            print(final_json)
            print("="*80)
            print(f"🔍 오류 위치: 줄 {e.lineno}, 컬럼 {e.colno}, 문자 {e.pos}")
            if e.pos < len(final_json):
                start = max(0, e.pos - 50)
                end = min(len(final_json), e.pos + 50)
                print(f"🎯 오류 주변 내용: '{final_json[start:end]}'")
                print(f"🎯 오류 문자: '{final_json[e.pos] if e.pos < len(final_json) else 'EOF'}'")
            
            # 최종 실패 시 빈 구조 반환
            processed_result = ResponsePostprocessor.process_response({"summary": "", "keyword": "", "paragraphs": []})
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
            try:
                processed_response = json.loads(summary)
            except json.JSONDecodeError as e:
                print(f"❌ process_request JSON 파싱 실패: {str(e)}")
                print(f"📄 실패한 JSON 전체 내용 (길이: {len(summary)} 문자):")
                print("="*80)
                print(summary)
                print("="*80)
                print(f"🔍 오류 위치: 줄 {e.lineno}, 컬럼 {e.colno}, 문자 {e.pos}")
                if e.pos < len(summary):
                    start = max(0, e.pos - 50)
                    end = min(len(summary), e.pos + 50)
                    print(f"🎯 오류 주변 내용: '{summary[start:end]}'")
                    print(f"🎯 오류 문자: '{summary[e.pos] if e.pos < len(summary) else 'EOF'}'")
                raise
            
            # ResponsePostprocessor로 최종 후처리 수행
            print(f"🔍 process_request 후처리 전: {processed_response}")
            processed_response = ResponsePostprocessor.process_response(processed_response)
            print(f"🔍 process_request 후처리 후: {processed_response}")
            
            processed_summary = processed_response.get('summary', '')
            
            # 재질의 필요 여부 확인
            if processed_summary.startswith('[재질의 필요]'):
                # 재질의 발생 로그 기록
                original_length = len(processed_summary.replace('[재질의 필요] ', ''))
                
                # 로그 파일에 재질의 발생 기록
                log_gemma_query(f"🔄 재질의 필요 감지: {processed_summary}", "requery_detection")
                log_gemma_query(f"📏 원본 요약 길이: {original_length}바이트 (120바이트 초과)", "requery_detection")
                log_gemma_query(f"📝 재질의 이유: 요약이 너무 길어서 압축 재질의 필요", "requery_detection")
                log_gemma_query(f"재질의 전 processed_response: {json.dumps(processed_response, ensure_ascii=False, indent=2)}", "requery_detection")
                log_gemma_query(f"재질의 전 keyword: {processed_response.get('keyword', '없음')}", "requery_detection")
                log_gemma_query(f"재질의 전 sentiment: {processed_response.get('sentiment', '없음')}", "requery_detection")
                
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
                start_time = time.time()
                log_gemma_query(f"🔄 재질의 시작...", "requery_start")
                
                config = get_config()
                llm = get_llm_instance()
                
                # 재질의용 max_tokens 설정 (기본값 사용)
                requery_max_tokens = config.get('DEFAULT_MAX_TOKENS', 500)
                
                # 재질의 시작 로그
                log_gemma_query(requery_prompt, "requery_prompt")
                
                requery_response = llm(
                    requery_prompt,
                    max_tokens=requery_max_tokens,
                    temperature=0.3,  # 매우 낮은 temperature로 일관성 극대화
                    min_p=0.1,  # 더 엄격한 최소 확률
                    top_p=0.8,  # 더 낮은 top_p로 일관성 향상
                    top_k=20,  # 더 좁은 토큰 선택 범위
                    repeat_penalty=1.05,  # 반복 방지 강화
                    echo=False
                )
                
                end_time = time.time()
                requery_time = end_time - start_time
                
                requery_summary = requery_response['choices'][0]['text'].strip()
                requery_length = len(requery_summary)
                
                # 재질의 완료 로그
                log_gemma_response(f"✅ 재질의 완료 (소요시간: {requery_time:.2f}초)", "requery_result")
                log_gemma_response(f"📏 재질의 결과 길이: {requery_length}바이트", "requery_result")
                log_gemma_response(f"📝 재질의 결과: {requery_summary}", "requery_result")
                log_gemma_response(f"🔄 압축률: {original_length}바이트 → {requery_length}바이트 ({((original_length-requery_length)/original_length*100):.1f}% 단축)", "requery_result")
                
                # 재질의 결과를 processed_response의 summary에 직접 설정
                # 기존 processed_response 구조는 유지하고 summary만 업데이트
                # 재질의 전후 상태 로그
                log_gemma_response(f"재질의 전 processed_response 타입: {type(processed_response)}", "requery_processing")
                log_gemma_response(f"재질의 전 processed_response 키: {list(processed_response.keys())}", "requery_processing")
                log_gemma_response(f"재질의 전 processed_response 전체: {json.dumps(processed_response, ensure_ascii=False, indent=2)}", "requery_processing")
                
                # summary만 업데이트
                processed_response['summary'] = requery_summary
                
                log_gemma_response(f"재질의 후 processed_response: {json.dumps(processed_response, ensure_ascii=False, indent=2)}", "requery_processing")
                log_gemma_response(f"재질의 후 keyword: {processed_response.get('keyword', '없음')}", "requery_processing")
                log_gemma_response(f"재질의 후 sentiment: {processed_response.get('sentiment', '없음')}", "requery_processing")
                log_gemma_response(f"재질의 후 processed_response 타입: {type(processed_response)}", "requery_processing")
                log_gemma_response(f"재질의 후 processed_response 키: {list(processed_response.keys())}", "requery_processing")

                # 재질의 후처리 수행 (단, [재질의 필요] 태그는 다시 붙이지 않음)
                log_gemma_response(f"🔍 process_request 재질의 후처리 전: {processed_response}", "requery_postprocess")
                
                # 재질의 후에는 convert_to_noun_form만 적용하고 [재질의 필요] 태그는 붙이지 않음
                if 'summary' in processed_response:
                    original_summary_before_noun = processed_response['summary']
                    # convert_to_noun_form만 적용 (길이 체크 없이)
                    processed_summary = ResponsePostprocessor.convert_to_noun_form(original_summary_before_noun)
                    processed_response['summary'] = processed_summary
                    log_gemma_response(f"🔍 재질의 후 명사형 변환: '{original_summary_before_noun}' → '{processed_summary}'", "requery_postprocess")
                
                final_length = len(processed_response.get('summary', ''))
                log_gemma_response(f"🔍 process_request 재질의 후처리 후: {processed_response}", "requery_postprocess")
                log_gemma_response(f"🎯 재질의 전체 과정 완료: 최종 요약 길이 {final_length}바이트", "requery_complete")
                
                # 재질의 전체 과정 완료 로그
                log_gemma_response(f"[재질의 프로세스 완료] 최종 요약: {processed_response.get('summary', '')}, 최종 길이: {final_length}바이트", "requery_process_complete")

            # 최종 결과를 딕셔너리로 사용
            # processed_response는 이미 올바른 구조를 가지고 있으므로 그대로 사용
            summary = processed_response
                
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