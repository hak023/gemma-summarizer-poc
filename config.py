import os
import multiprocessing
from pathlib import Path

# CPU 코어 수 자동 감지
def get_optimal_threads():
    """물리적 CPU 코어 수를 감지하고 CPU_LIMIT_PERCENT를 적용하여 최적의 스레드 수를 반환"""
    try:
        # 물리적 CPU 코어 수 감지
        cpu_count = multiprocessing.cpu_count()
        print(f"감지된 CPU 코어 수: {cpu_count}")
        
        # config에서 CPU 제한 퍼센트 가져오기
        cpu_limit_percent = DEFAULT_CONFIG.get('CPU_LIMIT_PERCENT', 20)
        
        # CPU 사용량 제한 적용
        optimal_threads = max(1, int(cpu_count * cpu_limit_percent / 100))
        print(f"CPU 제한 적용: {cpu_count}개 코어의 {cpu_limit_percent}% = {optimal_threads}개 스레드")
        
        return optimal_threads
        
    except Exception as e:
        print(f"CPU 코어 수 감지 실패: {e}, 기본값 2 사용")
        return 2

# 기본 설정값들
DEFAULT_CONFIG = {
    # 모델 설정
    #Gemma3-1b 설정일경우
    'MODEL_PATH': 'models/gemma-3-1b-it-Q8_0.gguf',
    #Gemma3-4b 설정일경우
    #'MODEL_PATH': 'models/gemma-3-4b-it-q4_0.gguf',
    #믿음2.0 Q4_K_M 설정일경우
    #'MODEL_PATH': 'models/Midm-2.0-Mini-Instruct-Q4_K_M.gguf',
    'MODEL_CONTEXT_SIZE': 8192,
    
    # 요약 설정
    'DEFAULT_MAX_TOKENS': 500,
    'DEFAULT_TEMPERATURE': 0.7,
    
    # 출력 설정
    'OUTPUT_FILE': 'gemma_summary.txt',
    'OUTPUT_ENCODING': 'utf-8',
    
    # 로깅 설정
    'LOG_LEVEL': 'INFO',
    'ENABLE_DEBUG': False,
    
    # 성능 설정
    'ENABLE_GPU': False,
    'CPU_LIMIT_PERCENT': 20,  # CPU 사용량 제한 (기본값 20%)
    
    # 파일 경로 설정
    'WORKSPACE_DIR': str(Path.cwd()),
    'MODELS_DIR': 'models',
    
    # IPC 설정
    'IPC_SHM_NAME': 'gemma_ipc_shm',
    'IPC_SHM_SIZE': 65536,  # 64KB
    'IPC_POLLING_INTERVAL': 0.5,  # 초
    'IPC_REQUEST_TIMEOUT': 300.0,  # 초 (5분으로 증가)
    'IPC_LOCK_TIMEOUT': 10.0,  # 초 (증가)
    'IPC_MAX_RETRY_COUNT': 3,
    
    # 멀티슬롯 IPC 설정
    'IPC_SLOT_COUNT': 5,  # 슬롯 개수
    'IPC_SLOT_SIZE': 262144,  # 슬롯당 크기 (bytes) - 256KB로 증가
    'IPC_WORKER_THREADS': 1,  # 워커 스레드 개수
    'IPC_RESPONSE_WRITER_THREADS': 1,  # 응답 쓰기 스레드 개수
    
    # 성능 최적화 설정
    'MODEL_TIMEOUT': 180.0,  # 모델 추론 타임아웃 (3분)
    'ENABLE_FAST_MODE': False,  # 빠른 모드 (토큰 수 줄임)
    'FAST_MODE_MAX_TOKENS': 300,  # 빠른 모드 토큰 수
}

def get_config():
    """환경 변수에서 설정을 가져오거나 기본값을 반환"""
    config = {}
    
    for key, default_value in DEFAULT_CONFIG.items():
        # 환경 변수에서 값을 가져오거나 기본값 사용
        env_value = os.getenv(key)
        if env_value is not None:
            # 타입 변환
            if isinstance(default_value, bool):
                config[key] = env_value.lower() in ('true', '1', 'yes', 'on')
            elif isinstance(default_value, int):
                config[key] = int(env_value)
            else:
                config[key] = env_value
        else:
            config[key] = default_value
    
    return config

def set_config(key, value):
    """환경 변수 설정"""
    os.environ[key] = str(value)

def get_model_path():
    """모델 파일의 전체 경로를 반환"""
    config = get_config()
    workspace_dir = config['WORKSPACE_DIR']
    model_path = config['MODEL_PATH']
    
    # 절대 경로로 변환
    if not os.path.isabs(model_path):
        model_path = os.path.join(workspace_dir, model_path)
    
    return model_path

def validate_config():
    """설정 유효성 검사"""
    config = get_config()
    model_path = get_model_path()
    
    # 모델 파일 존재 확인
    if not os.path.exists(model_path):
        print(f"경고: 모델 파일을 찾을 수 없습니다: {model_path}")
        return False
    
    # 모델 디렉토리 존재 확인
    models_dir = os.path.join(config['WORKSPACE_DIR'], config['MODELS_DIR'])
    if not os.path.exists(models_dir):
        print(f"경고: 모델 디렉토리를 찾을 수 없습니다: {models_dir}")
        return False
    
    return True

if __name__ == "__main__":
    # 설정 테스트
    print("=== 설정 테스트 ===")
    config = get_config()
    for key, value in config.items():
        print(f"{key}: {value}")
    
    print(f"\n모델 경로: {get_model_path()}")
    print(f"설정 유효성: {validate_config()}") 