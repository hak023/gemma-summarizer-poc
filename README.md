# Gemma Summarizer

Gemma 3-1B 모델을 사용하여 통화 내용을 요약하는 프로그램입니다. IPC(Inter-Process Communication)를 통해 멀티슬롯 요청 처리를 지원합니다.

## 주요 기능

- ✅ **AI 기반 텍스트 요약**: Gemma 3-1B 모델 사용
- ✅ **멀티슬롯 IPC**: 동시 다중 요청 처리
- ✅ **싱글톤 모델 로딩**: 성능 최적화
- ✅ **UTF-8 디코딩 오류 방지**: 안정적인 데이터 처리
- ✅ **비동기 로깅**: 요청/응답 로그 기록
- ✅ **Windows 지원**: PowerShell 및 Command Prompt

## 설치 방법

### 1. 저장소 클론
```bash
git clone <repository-url>
cd gemma_summarizer_new
```

### 2. 의존성 설치
```bash
pip install -r requirements.txt
```

### 3. 모델 다운로드
Gemma 3-1B 모델을 `models/` 디렉토리에 다운로드:
```bash
# models 디렉토리 생성
mkdir models

# Gemma 3-1B 모델 다운로드 (Hugging Face에서)
# gemma-3-1b-it-Q8_0.gguf 파일을 models/ 디렉토리에 저장
```

## 환경 설정

### 방법 1: 환경 변수 설정 (권장)

#### Windows (PowerShell)
```powershell
.\set_env.ps1
python gemma_summarizer_multi.py
```

#### Windows (Command Prompt)
```cmd
set_env.bat
python gemma_summarizer_multi.py
```

### 방법 2: 직접 환경 변수 설정
```powershell
$env:MODEL_PATH = "models/gemma-3-1b-it-Q8_0.gguf"
$env:MODEL_CONTEXT_SIZE = "2048"
$env:DEFAULT_MAX_TOKENS = "100"
$env:THREADS = "4"
```

### 방법 3: 기본 설정 사용
환경 변수를 설정하지 않으면 `config.py`의 기본값이 사용됩니다.

## 사용 방법

### 서버 실행

#### 멀티슬롯 서버 (권장)
```bash
python gemma_summarizer_multi.py
```

#### 단일 슬롯 서버
```bash
python gemma_summarizer_fixed.py
```

### 클라이언트 테스트

#### 멀티슬롯 테스트
```bash
python ipc_client_multi_test.py
```

#### 단일 슬롯 테스트
```bash
python ipc_client_test.py
```

## 설정 옵션

| 환경 변수 | 기본값 | 설명 |
|-----------|--------|------|
| MODEL_PATH | models/gemma-3-1b-it-Q8_0.gguf | 모델 파일 경로 |
| MODEL_CONTEXT_SIZE | 2048 | 모델 컨텍스트 크기 |
| DEFAULT_MAX_TOKENS | 100 | 기본 최대 토큰 수 |
| DEFAULT_TEMPERATURE | 0.7 | 생성 온도 |
| OUTPUT_FILE | gemma_summary.txt | 출력 파일명 |
| THREADS | 4 | 사용할 스레드 수 |
| ENABLE_GPU | false | GPU 사용 여부 |
| IPC_SLOT_COUNT | 5 | IPC 슬롯 개수 |
| IPC_SLOT_SIZE | 8192 | 슬롯당 크기 (bytes) |

## IPC (Inter-Process Communication) 기능

### 멀티슬롯 아키텍처
- **5개 슬롯**: 동시 요청 처리
- **공유 메모리**: 빠른 데이터 전송
- **스레드 기반**: 비동기 처리
- **락 메커니즘**: 데이터 무결성 보장

### IPC 프로토콜

#### 요청 형식 (JSON)
```json
{
    "type": "request",
    "text": "요약할 텍스트 내용",
    "request_id": "고유ID",
    "processed": false,
    "timestamp": 1234567890.123
}
```

#### 응답 형식 (JSON)
```json
{
    "type": "response",
    "summary": "요약된 텍스트",
    "request_id": "고유ID",
    "status": "success",
    "processing_time": 3.45,
    "processed": true
}
```

## 성능 최적화

### 싱글톤 모델 로딩
- 모델을 한 번만 로딩하여 재사용
- 요청 처리 시간 단축 (50% 이상 향상)
- 메모리 사용량 최적화

### UTF-8 디코딩 오류 방지
- 다단계 디코딩 시도
- 데이터 유효성 검사
- 오류 복구 메커니즘

## 파일 구조

```
gemma_summarizer_new/
├── gemma_summarizer_multi.py    # 멀티슬롯 서버 (메인)
├── gemma_summarizer.py          # AI 요약 처리 모듈
├── ipc_queue_manager.py         # IPC 관리자
├── config.py                    # 설정 관리
├── logger.py                    # 로깅 시스템
├── ipc_client_multi_test.py     # 멀티슬롯 테스트
├── ipc_client_test.py           # 단일 슬롯 테스트
├── kill_previous_processes.py   # 프로세스 정리
├── requirements.txt             # 의존성 목록
├── README.md                    # 프로젝트 문서
├── set_env.ps1                  # PowerShell 환경 설정
├── set_env.bat                  # Command Prompt 환경 설정
├── models/                      # 모델 파일 디렉토리
│   └── gemma-3-1b-it-Q8_0.gguf  # Gemma 모델 (별도 다운로드)
└── logs/                        # 로그 파일 디렉토리
    └── gemma_summarizer_YYYYMMDD.txt
```

## 문제 해결

### UTF-8 디코딩 오류
```
'utf-8' codec can't decode byte 0x82 in position 5: invalid start byte
```
- 자동으로 처리됨 (다단계 디코딩 시도)
- 로그에서 hex 출력으로 문제 진단 가능

### 모델 로딩 오류
- 모델 파일 경로 확인
- `config.py`에서 설정 검증
- 메모리 부족 시 스레드 수 조정

### IPC 연결 오류
- 이전 프로세스 정리: `python kill_previous_processes.py`
- 공유 메모리 초기화 자동 수행

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 기여

버그 리포트나 기능 제안은 GitHub Issues를 통해 제출해주세요.

## 변경 이력

### v1.0.0 (2025-07-15)
- ✅ 멀티슬롯 IPC 서버 구현
- ✅ 싱글톤 모델 로딩 최적화
- ✅ UTF-8 디코딩 오류 방지
- ✅ 비동기 로깅 시스템
- ✅ Windows 환경 지원
