import sys
import os
import time
import traceback
from pathlib import Path
import json
import time
from multiprocessing import shared_memory, Lock
import threading
from config import get_config, get_model_path, validate_config

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

# IPC 설정
SHM_NAME = "gemma_ipc_shm"
SHM_SIZE = 65536  # 64KB, 필요시 조정
LOCK_NAME = "gemma_ipc_lock"
POLLING_INTERVAL = 0.5  # 폴링 간격 (초)
REQUEST_TIMEOUT = 30.0  # 요청 타임아웃 (초)
MAX_RETRY_COUNT = 3     # 최대 재시도 횟수

class IPCLockManager:
    """IPC Lock 관리 클래스"""
    def __init__(self):
        self.lock = None
        self._init_lock()
    
    def _init_lock(self):
        """Lock 초기화"""
        try:
            self.lock = Lock()
        except Exception as e:
            print(f"Lock 초기화 실패: {e}")
            self.lock = None
    
    def acquire(self, timeout=5.0):
        """Lock 획득"""
        if self.lock is None:
            return False
        try:
            return self.lock.acquire(timeout=timeout)
        except Exception as e:
            print(f"Lock 획득 실패: {e}")
            return False
    
    def release(self):
        """Lock 해제"""
        if self.lock is not None:
            try:
                self.lock.release()
            except Exception as e:
                print(f"Lock 해제 실패: {e}")

def read_json_from_shm(shm, lock_manager, timeout=1.0):
    """공유 메모리에서 JSON 데이터 읽기 (Lock 보호)"""
    if not lock_manager.acquire(timeout=timeout):
        print("Lock 획득 타임아웃")
        return None
    
    try:
        raw = bytes(shm.buf[:]).rstrip(b'\x00')
        if not raw:
            return None
        try:
            return json.loads(raw.decode('utf-8'))
        except json.JSONDecodeError as e:
            print(f"JSON 파싱 오류: {e}")
            return None
        except Exception as e:
            print(f"데이터 읽기 오류: {e}")
            return None
    finally:
        lock_manager.release()

def write_json_to_shm(shm, data, lock_manager, timeout=1.0):
    """공유 메모리에 JSON 데이터 쓰기 (Lock 보호)"""
    if not lock_manager.acquire(timeout=timeout):
        print("Lock 획득 타임아웃")
        return False
    
    try:
        s = json.dumps(data, ensure_ascii=False)
        b = s.encode('utf-8')
        
        if len(b) > len(shm.buf):
            print(f"데이터가 너무 큽니다: {len(b)} > {len(shm.buf)}")
            return False
        
        shm.buf[:len(b)] = b
        shm.buf[len(b):] = b'\x00' * (len(shm.buf) - len(b))
        return True
    except Exception as e:
        print(f"데이터 쓰기 오류: {e}")
        return False
    finally:
        lock_manager.release()

def clear_shm(shm, lock_manager):
    """공유 메모리 초기화"""
    if lock_manager.acquire(timeout=1.0):
        try:
            shm.buf[:] = b'\x00' * len(shm.buf)
        finally:
            lock_manager.release()

def summarize_with_gemma(text: str, max_tokens: int = None) -> str:
    try:
        print("llama_cpp 모듈 임포트 중...")
        from llama_cpp import Llama
        print("llama_cpp 모듈 임포트 성공")
        
        # 설정 가져오기
        config = get_config()
        if max_tokens is None:
            max_tokens = config['DEFAULT_MAX_TOKENS']
        
        MODEL_PATH = get_model_path()
        
        print(f"모델 로딩 시작: {MODEL_PATH}")
        # GPU 사용 설정 적용
        enable_gpu = bool(config.get('ENABLE_GPU', False))
        n_gpu_layers = 0
        env_n_gpu_layers = os.getenv('N_GPU_LAYERS')
        if enable_gpu:
            try:
                n_gpu_layers = int(env_n_gpu_layers) if env_n_gpu_layers is not None else -1
            except ValueError:
                n_gpu_layers = -1
        # CPU 스레드 수 결정
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

        llm = Llama(
            model_path=MODEL_PATH, 
            n_ctx=config['MODEL_CONTEXT_SIZE'],
            n_threads=max_threads,
            n_threads_batch=max_threads,  # 배치 처리 스레드도 제한
            n_gpu_layers=n_gpu_layers,
            verbose=False  # 불필요한 출력 줄이기
        )
        print("모델 로딩 완료")
        
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

def process_request(data, shm, lock_manager):
    """요청 처리 함수"""
    try:
        request_id = data.get("request_id", "unknown")
        text = data.get("text", "")
        
        if not text.strip():
            return {
                "type": "response",
                "summary": "입력 텍스트가 비어있습니다.",
                "request_id": request_id,
                "status": "error",
                "processed": True
            }
        
        print(f"요청 처리 시작 (ID: {request_id})")
        start_time = time.time()
        
        # 요약 수행
        summary = summarize_with_gemma(text)
        
        processing_time = time.time() - start_time
        print(f"요청 처리 완료 (ID: {request_id}, 소요시간: {processing_time:.2f}초)")
        
        return {
            "type": "response",
            "summary": summary,
            "request_id": request_id,
            "status": "success",
            "processing_time": processing_time,
            "processed": True
        }
        
    except Exception as e:
        error_msg = f"요청 처리 중 오류: {str(e)}"
        print(error_msg)
        return {
            "type": "response",
            "summary": error_msg,
            "request_id": data.get("request_id", "unknown"),
            "status": "error",
            "processed": True
        }

def main():
    print("=== Gemma IPC Summarizer 시작 ===")
    print(f"현재 작업 디렉토리: {os.getcwd()}")
    print(f"Python 실행 파일: {sys.executable}")
    
    # 설정 유효성 검사
    if not validate_config():
        print("설정 오류가 있습니다. config.py를 확인해주세요.")
        sys.exit(1)
    
    # Lock 관리자 초기화
    lock_manager = IPCLockManager()
    
    # 공유 메모리 생성 또는 연결
    shm = None
    try:
        try:
            shm = shared_memory.SharedMemory(name=SHM_NAME, create=True, size=SHM_SIZE)
            print(f"공유 메모리 생성됨: {SHM_NAME} ({SHM_SIZE} bytes)")
        except FileExistsError:
            shm = shared_memory.SharedMemory(name=SHM_NAME)
            print(f"기존 공유 메모리 연결됨: {SHM_NAME}")
        
        # 초기화
        clear_shm(shm, lock_manager)
        
        print("IPC 서버 시작 - 대기 중...")
        print(f"폴링 간격: {POLLING_INTERVAL}초")
        print(f"요청 타임아웃: {REQUEST_TIMEOUT}초")
        
        last_activity = time.time()
        
        while True:
            try:
                # 입력 대기 (폴링)
                data = read_json_from_shm(shm, lock_manager, timeout=1.0)
                
                if data and data.get("type") == "request" and not data.get("processed"):
                    last_activity = time.time()
                    print(f"새 요청 수신: {data.get('request_id', 'unknown')}")
                    
                    # 요청 처리
                    result = process_request(data, shm, lock_manager)
                    
                    # 결과 전송
                    if write_json_to_shm(shm, result, lock_manager, timeout=2.0):
                        print(f"요약 결과 전송 완료 (ID: {result['request_id']})")
                    else:
                        print(f"결과 전송 실패 (ID: {result['request_id']})")
                    
                    # 원본 요청을 processed로 표시
                    data["processed"] = True
                    write_json_to_shm(shm, data, lock_manager, timeout=1.0)
                
                # 타임아웃 체크
                if time.time() - last_activity > REQUEST_TIMEOUT:
                    print("활동 없음 - 서버 상태 확인 중...")
                    last_activity = time.time()
                
                time.sleep(POLLING_INTERVAL)
                
            except KeyboardInterrupt:
                print("\n사용자에 의해 중단됨")
                break
            except Exception as e:
                print(f"메인 루프 오류: {e}")
                print(traceback.format_exc())
                time.sleep(1.0)  # 오류 발생 시 잠시 대기
    
    except Exception as e:
        print(f"초기화 오류: {e}")
        print(traceback.format_exc())
    
    finally:
        # 정리 작업
        print("정리 작업 중...")
        if shm:
            try:
                shm.close()
                shm.unlink()
                print("공유 메모리 정리 완료")
            except Exception as e:
                print(f"공유 메모리 정리 오류: {e}")
        
        print("=== 프로그램 종료 ===")

if __name__ == "__main__":
    main() 