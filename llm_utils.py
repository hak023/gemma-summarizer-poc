import traceback
import os
import multiprocessing
from logger import log_gemma_query, log_gemma_response
from config import get_config

def get_llm_instance():
    # gemma_summarizer.py의 get_llm_instance를 복사(임시)
    import sys, os, threading
    global _llm_instance, _llm_lock
    try:
        _llm_instance
    except NameError:
        _llm_instance = None
    try:
        _llm_lock
    except NameError:
        _llm_lock = threading.Lock()
    if _llm_instance is None:
        with _llm_lock:
            if _llm_instance is None:
                from llama_cpp import Llama
                config = get_config()
                from config import get_model_path
                MODEL_PATH = get_model_path()
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
    return _llm_instance

def correct_conversation_with_gemma(text: str) -> str:
    """
    LLM을 사용하여 STT 결과의 대화 내용을 보정합니다.
    Args:
        text (str): 보정할 대화 텍스트
    Returns:
        str: 보정된 대화 텍스트
    """
    try:
        if not text or not isinstance(text, str):
            return text
        llm = get_llm_instance()
        prompt = (
            f"다음은 STT(음성인식) 결과로 생성된 대화 내용입니다. "
            f"음성인식 오류로 인해 문장이 부자연스럽거나 의미가 명확하지 않은 부분이 있을 수 있습니다.\n\n"
            f"다음 규칙에 따라 대화 내용을 자연스럽고 명확하게 보정해주세요:\n\n"
            f"1. 문맥상 명확한 의미로 수정 (예: '상품이 배송되지 않았습니다' → '상품이 아직 배송되지 않았습니다')\n"
            f"2. 문법 오류 수정 (예: '배송 확인해주세요' → '배송을 확인해주세요')\n"
            f"3. 불완전한 문장이 있다면 완성하지 말고 그대로 두세요.\n"
            f"4. 대화의 자연스러운 흐름 유지\n"
            f"5. 원래 의미는 최대한 보존\n"
            f"⚠️ 반드시 원본과 동일한 화자 구분 형식을 유지하고, JSON이나 다른 형식으로 변환하지 마세요.\n\n"
            f"[원본 대화 내용]\n{text}\n\n"
            f"[보정된 대화 내용]"
        )
        print("대화 내용 보정 중...")
        log_gemma_query(prompt, "conversation_correction")
        output = llm(
            prompt,
            max_tokens=2000,
            temperature=0.1,
            top_p=0.9,
            top_k=40,
            repeat_penalty=1.1,
            echo=False
        )
        if hasattr(output, 'choices') and output.choices:
            result = output.choices[0].text.strip()
        elif isinstance(output, dict) and 'choices' in output:
            result = output['choices'][0]['text'].strip()
        else:
            result = str(output).strip()
        print(f"[보정된 대화]:\n{result}\n---")
        log_gemma_response(result, "conversation_correction")
        return result
    except Exception as e:
        print(f"대화 보정 중 오류 발생: {e}")
        traceback.print_exc()
        return text  # 오류 시 원본 반환 