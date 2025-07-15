import os
from pathlib import Path

# 기본 설정값들
DEFAULT_CONFIG = {
    # 모델 설정
    'MODEL_PATH': 'models/gemma-3-1b-it-Q8_0.gguf',
    'MODEL_CONTEXT_SIZE': 2048,
    
    # 요약 설정
    'DEFAULT_MAX_TOKENS': 100,
    'DEFAULT_TEMPERATURE': 0.7,
    
    # 출력 설정
    'OUTPUT_FILE': 'gemma_summary.txt',
    'OUTPUT_ENCODING': 'utf-8',
    
    # 로깅 설정
    'LOG_LEVEL': 'INFO',
    'ENABLE_DEBUG': False,
    
    # 성능 설정
    'ENABLE_GPU': False,
    'THREADS': 4,
    
    # 파일 경로 설정
    'WORKSPACE_DIR': str(Path.cwd()),
    'MODELS_DIR': 'models',
    
    # IPC 설정
    'IPC_SHM_NAME': 'gemma_ipc_shm',
    'IPC_SHM_SIZE': 65536,  # 64KB
    'IPC_POLLING_INTERVAL': 0.5,  # 초
    'IPC_REQUEST_TIMEOUT': 30.0,  # 초
    'IPC_LOCK_TIMEOUT': 5.0,  # 초
    'IPC_MAX_RETRY_COUNT': 3,
    
    # 멀티슬롯 IPC 설정
    'IPC_SLOT_COUNT': 5,  # 슬롯 개수
    'IPC_SLOT_SIZE': 8192,  # 슬롯당 크기 (bytes)
    'IPC_WORKER_THREADS': 1,  # 워커 스레드 개수
    'IPC_RESPONSE_WRITER_THREADS': 1  # 응답 쓰기 스레드 개수
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