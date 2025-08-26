# Gemma Summarizer

Gemma 3-1B 8Q 모델을 사용하여 통화 내용을 요약하는 프로그램입니다. IPC(Inter-Process Communication)를 통해 멀티슬롯 요청 처리를 지원하며, STT(Speech-to-Text) 결과를 전처리하고 구조화된 JSON 응답을 생성합니다. 1B 8Q 모델에 최적화된 프롬프트와 파라미터를 사용하여 안정적인 성능을 제공합니다.

## 주요 기능

- ✅ **AI 기반 텍스트 요약**: Gemma 3-1B 8Q 모델 사용
- ✅ **1B 8Q 모델 최적화**: 간단한 프롬프트와 최적화된 파라미터
- ✅ **멀티슬롯 IPC**: 동시 다중 요청 처리
- ✅ **싱글톤 모델 로딩**: 성능 최적화
- ✅ **UTF-8 디코딩 오류 방지**: 안정적인 데이터 처리
- ✅ **비동기 로깅**: 요청/응답 로그 기록
- ✅ **Windows 지원**: PowerShell 및 Command Prompt
- ✅ **STT 결과 전처리**: 화자 구분, 중복 제거, 텍스트 정리
- ✅ **구조화된 JSON 응답**: summary, keyword, paragraphs 구조
- ✅ **타입 안전성 강화**: 다양한 데이터 타입에 대한 안전한 처리
- ✅ **강화된 에러 처리**: 다양한 에러 상황에 대한 Fallback 메커니즘
- ✅ **자동 재처리 시스템**: 긴 요약 결과에 대한 자동 재질의 및 압축
- ✅ **요청-응답 시간 측정**: IPC 클라이언트에서 성능 모니터링
- ✅ **CPU 사용량 제한**: 설정 가능한 CPU 사용량 제한 (기본 50%)
- ✅ **JSON 복구 시스템**: 잘린 JSON, 깨진 JSON 자동 복구 및 마크다운 추출
- ✅ **JSON 처리 최적화**: 정상 JSON에 대해 불필요한 수정 로직 건너뛰기

## 시스템 아키텍처

### 데이터 흐름
![데이터 흐름](데이터%20흐름.png)

전체 시스템의 워크플로우와 데이터 흐름은 [워크플로우 다이어그램](workflow_diagram.md), [시퀀스 다이어그램](sequence_diagram.md), [클래스 다이어그램](class_diagram.md)을 참조하세요.

### 처리 단계
1. **전처리 단계**: STT 결과 파싱 → 화자 구분 → 중복 제거 → 텍스트 정리
2. **Gemma 모델 요약**: 프롬프트 생성 → 모델 호출 → JSON 파싱 → 필드 검증
3. **후처리 단계**: 필드별 후처리 → 예시 내용 필터링 → 길이 제한 적용 → 기본값 설정
4. **재처리 단계**: 긴 요약 결과 감지 → 자동 재질의 → 압축된 요약 생성

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
지원되는 모델 중 하나를 `models/` 디렉토리에 다운로드:
```bash
# models 디렉토리 생성
mkdir models

# 현재 기본 모델: Midm-2.0-Mini (권장)
# Midm-2.0-Mini-Instruct-Q4_K_M.gguf 파일을 models/ 디렉토리에 저장

# 또는 Gemma 모델들 (Hugging Face에서)
# gemma-3-1b-it-Q8_0.gguf
# gemma-3-4b-it-q4_0.gguf
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

### 클라이언트 테스트

#### 단일 요청 테스트
```bash
python ipc_client_test.py
```
- **테스트 파일**: `sample/sample_request_17.json` (공사 진척 상황과 청소 비용 협의)
- **처리 시간**: 약 25-35초
- **용도**: 단일 요청의 정상 동작 확인

#### 다중 요청 테스트 (성능 검증)
```bash
python ipc_client_test.py multi
```
- **테스트 파일**: `sample/sample_request_1.json` ~ `sample/sample_request_17.json` (17개 파일)
- **처리 시간**: 각각 25-35초 (총 7-10분)
- **용도**: 멀티슬롯 성능 및 안정성 검증
- **결과**: `logs/` 디렉터리에 각 테스트 결과가 `1.txt`, `2.txt`, ... `17.txt`로 저장

### 테스트 JSON 샘플 파일 설명

#### sample_request_1.json - 평생교육원 포인트 문의
```json
{
    "cmd": "SummaryReq",
    "reqNo": "20250623085851B6100",
    "sttResultList": [
        {
            "transcript": "네 부산지판 가족과 평생교육진흥원입니다",
            "recType": 4,
            "startTime": 0
        },
        {
            "transcript": "예 예 안녕하세요 제가 이번에 평생그 옥수강 신사권이",
            "recType": 2,
            "startTime": 3200
        }
        // ... 더 많은 대화 내용
    ]
}
```
- **대화 주제**: 평생교육원 포인트 지급 확인 및 사용처 문의
- **화자 구분**: recType 4(상담원), recType 2(고객)
- **대화 길이**: 약 152초 (2분 32초)

#### sample_request_17.json - 공사 현장 진척 상황
```json
{
    "cmd": "SummaryReq", 
    "reqNo": "20250624104300A4064",
    "sttResultList": [
        {
            "transcript": "예 예 여보세요",
            "recType": 4,
            "startTime": 800
        },
        {
            "transcript": "아 네 과장님 여기 회장님 연결하라고 하셔서요",
            "recType": 2,
            "startTime": 1700
        }
        // ... 더 많은 대화 내용
    ]
}
```
- **대화 주제**: 지하 1층 공사 진척 상황과 청소 업체 선정 논의
- **화자 구분**: recType 4(직원), recType 2(회장)
- **대화 길이**: 약 314초 (5분 14초)

#### 테스트 결과 예시
```json
{
  "summary": "공사 진척 상황과 청소 비용 협의",
  "keyword": "공사, 청소, 비용",
  "paragraphs": [
    {
      "summary": "지하 1층 공사가 입구 쪽에 엘이디등 설치 완료됨",
      "keyword": "엘이디, 공사, 입구",
      "sentiment": "강한긍정"
    },
    {
      "summary": "청소 비용이 아파트 기준으로 평수에 따라 계산됨",
      "keyword": "청소, 비용, 아파트", 
      "sentiment": "보통"
    }
  ]
}
```

## 설정 옵션

### 모델 설정
| 환경 변수 | 기본값 | 설명 |
|-----------|--------|------|
| MODEL_PATH | models/Midm-2.0-Mini-Instruct-Q4_K_M.gguf | 현재 사용 중인 모델 파일 경로 |
| MODEL_CONTEXT_SIZE | 8192 | 모델 컨텍스트 크기 |
| DEFAULT_MAX_TOKENS | 500 | 기본 최대 토큰 수 |
| DEFAULT_TEMPERATURE | 0.7 | 생성 온도 |

### 성능 설정  
| 환경 변수 | 기본값 | 설명 |
|-----------|--------|------|
| ENABLE_GPU | false | GPU 사용 여부 |
| CPU_LIMIT_PERCENT | 20 | CPU 사용량 제한 (%) |

### IPC 설정
| 환경 변수 | 기본값 | 설명 |
|-----------|--------|------|
| IPC_SLOT_COUNT | 5 | IPC 슬롯 개수 |
| IPC_SLOT_SIZE | 262144 | 슬롯당 크기 (256KB) |
| IPC_REQUEST_TIMEOUT | 300.0 | 요청 타임아웃 (초) |
| IPC_POLLING_INTERVAL | 0.5 | 폴링 간격 (초) |

### 기타 설정
| 환경 변수 | 기본값 | 설명 |
|-----------|--------|------|
| OUTPUT_FILE | gemma_summary.txt | 출력 파일명 |
| LOG_LEVEL | INFO | 로그 레벨 |

### 지원 모델
- **Midm-2.0-Mini** (현재 기본): `models/Midm-2.0-Mini-Instruct-Q4_K_M.gguf`
- **Gemma-3-1B**: `models/gemma-3-1b-it-Q8_0.gguf` (주석 처리됨)
- **Gemma-3-4B**: `models/gemma-3-4b-it-q4_0.gguf` (주석 처리됨)

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
    "transactionid": "20250623085851B6100",
    "sequenceno": "0",
    "text": "요약할 텍스트 내용"
}
```

#### 응답 형식 (JSON)
```json
{
    "transactionid": "20250623085851B6100",
    "sequenceno": "0",
    "returncode": "1",
    "returndescription": "Success",
    "response": {
        "result": "0",
        "failReason": "",
        "summary": "구조화된 JSON 요약 결과"
    }
}
```

#### Gemma 모델 응답 형식 (JSON)
Gemma 모델은 1B 8Q 모델에 최적화된 구조화된 JSON 형식으로 응답합니다:
```json
{
    "summary": "통화 핵심 요약",
    "keyword": "키워드1, 키워드2, 키워드3",
    "paragraphs": [
        {
            "summary": "첫 번째 문단 요약",
            "keyword": "키워드1, 키워드2",
            "sentiment": "보통"
        },
        {
            "summary": "두 번째 문단 요약",
            "keyword": "키워드3, 키워드4",
            "sentiment": "보통"
        }
    ]
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

### 전처리 최적화
- 중복 발화 제거로 토큰 수 절약
- 화자별 구분으로 대화 구조 명확화
- 텍스트 정리로 모델 성능 향상

### 자동 재처리 시스템
- 긴 요약 결과 자동 감지 (120바이트 초과)
- 재질의를 통한 압축된 요약 생성
- 원본 구조 유지하면서 요약 길이 최적화
- [재질의 필요] 태그 중복 표시 방지

### CPU 사용량 제한
- 설정 가능한 CPU 사용량 제한 (기본 20%)
- 환경 변수로 동적 조정 가능
- 멀티슬롯 환경에서 안정적인 성능 보장

## 파일 구조

```
gemma_summarizer_new/
├── gemma_summarizer_multi.py    # 멀티슬롯 서버 (메인)
├── gemma_summarizer.py          # AI 요약 처리 모듈
├── preprocessor.py              # STT 결과 전처리 모듈
├── postprocessor.py             # 응답 후처리 모듈
├── json_repair.py               # JSON 복구 및 수정 모듈
├── llm_utils.py                 # LLM 관련 유틸리티
├── ipc_queue_manager.py         # IPC 관리자
├── config.py                    # 설정 관리
├── logger.py                    # 로깅 시스템
├── ipc_client_test.py           # 단일/다중 요청 테스트
├── kill_previous_processes.py   # 프로세스 정리
├── requirements.txt             # 의존성 목록
├── README.md                    # 프로젝트 문서
├── workflow_diagram.md          # 워크플로우 다이어그램
├── sequence_diagram.md          # 시퀀스 다이어그램
├── class_diagram.md             # 클래스 다이어그램
├── 전체_시스템_아키텍처.png      # 전체 시스템 아키텍처 다이어그램
├── 상세 워크플로우.png          # 상세 워크플로우 다이어그램
├── 데이터 흐름.png              # 데이터 흐름 다이어그램
├── 에러처리.png                 # 에러 처리 다이어그램
├── 전체 시스템 클래스 다이어그램.png    # 전체 시스템 클래스 다이어그램
├── 데이터 흐름 클래스 다이어그램.png    # 데이터 흐름 클래스 다이어그램
├── 의존성 관계 클래스 다이어그램.png    # 의존성 관계 클래스 다이어그램
├── 전체 시스템 시퀀스 다이어그램.png    # 전체 시스템 시퀀스 다이어그램
├── 멀티슬롯 시퀀스 다이어그램.png      # 멀티슬롯 시퀀스 다이어그램
├── 에러처리 시퀀스 다이어그램.png      # 에러처리 시퀀스 다이어그램
├── 전처리 시퀀스 다이어그램.png        # 전처리 시퀀스 다이어그램
├── 후처리 시퀀스 다이어그램.png        # 후처리 시퀀스 다이어그램
├── set_env.ps1                  # PowerShell 환경 설정
├── set_env.bat                  # Command Prompt 환경 설정
├── models/                      # 모델 파일 디렉토리
│   └── gemma-3-1b-it-Q8_0.gguf  # Gemma 모델 (별도 다운로드)
├── sample/                      # 샘플 요청 데이터
│   ├── sample_request_1.json
│   ├── sample_request_2.json
│   └── ... (17개 샘플 파일)
└── logs/                        # 로그 파일 디렉토리
    └── gemma_summarizer_YYYYMMDD.txt
```

## 주요 모듈 설명

### gemma_summarizer.py
- **싱글톤 모델 관리**: 전역 모델 인스턴스 관리
- **1B 8Q 최적화**: 간단하고 명확한 프롬프트 생성
- **JSON 파싱**: 다양한 형태의 JSON 응답을 안정적으로 파싱
- **필드 검증**: 필수 필드 확인 및 기본값 설정
- **자동 재처리**: 긴 요약 결과에 대한 자동 재질의 및 압축

### preprocessor.py
- **STT 결과 파싱**: `sttResultList`에서 대화 내용 추출
- **화자 구분**: `recType`에 따라 "나"(4), "상대방"(2) 구분
- **중복 제거**: 연속된 동일 발화, 짧은 반복 발화 제거
- **텍스트 정리**: 특수문자, 불필요한 공백 제거

### postprocessor.py
- **필드별 처리**: 각 필드에 맞는 전용 처리 로직
- **타입 안전성**: 리스트, 문자열 등 다양한 데이터 타입 안전 처리
- **형식 통일**: paragraphs 내 keyword 필드 형식 통일
- **기본값 설정**: 누락된 필드에 대한 기본값 제공

### json_repair.py
- **JSON 복구**: 잘린 JSON, 깨진 JSON 자동 복구
- **마크다운 JSON 추출**: 마크다운 코드 블록에서 JSON 추출
- **고급 복구 시스템**: 다단계 JSON 구문 오류 수정
- **데이터 추출**: 유효한 데이터만 추출하여 최소 구조 생성

### llm_utils.py
- **LLM 유틸리티**: 대화 내용 보정, 텍스트 처리 등
- **공통 함수**: 여러 모듈에서 사용하는 공통 기능

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

### JSON 파싱 오류
- 자동 Fallback 메커니즘으로 개별 필드 추출
- 정규식을 이용한 안정적인 파싱
- 기본값 설정으로 응답 무결성 보장
- JSON 복구 모듈로 잘린 JSON 자동 복구
- 마크다운 코드 블록에서 JSON 추출

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 기여

버그 리포트나 기능 제안은 GitHub Issues를 통해 제출해주세요.

## 변경 이력

### v1.6.0 (2025-08-26)
- ✅ **JSON 처리 최적화**: 정상 JSON에 대해 불필요한 수정 로직 건너뛰기
- ✅ **재질의 로직 개선**: [재질의 필요] 태그 중복 표시 문제 해결
- ✅ **재질의 조건 완화**: 80byte → 120byte로 변경하여 과도한 재질의 방지
- ✅ **시스템 안정성 향상**: ResponsePostprocessor 호출 최적화
- ✅ **상세한 에러 로깅**: JSON 파싱 실패 시 상세한 디버깅 정보 제공
- ✅ **성능 최적화**: 정상 JSON 파싱 시 처리 시간 단축

### v1.5.0 (2025-08-15)
- ✅ **JSON 복구 시스템**: 잘린 JSON, 깨진 JSON 자동 복구 기능 (json_repair.py)
- ✅ **마크다운 JSON 추출**: 마크다운 코드 블록에서 JSON 추출 및 처리
- ✅ **고급 JSON 복구**: 다단계 JSON 구문 오류 수정 및 데이터 추출
- ✅ **부분 JSON 완성**: 불완전한 JSON을 유효한 구조로 자동 완성
- ✅ **강화된 오류 처리**: sentiment 값 띄어쓰기 수정 등 세밀한 오류 수정

### v1.4.0 (2025-08-05)
- ✅ **자동 재처리 시스템**: 긴 요약 결과에 대한 자동 재질의 및 압축 기능
- ✅ **요청-응답 시간 측정**: IPC 클라이언트에서 성능 모니터링 기능 추가
- ✅ **CPU 사용량 제한**: 설정 가능한 CPU 사용량 제한 (기본 50%)
- ✅ **성능 최적화**: 멀티슬롯 환경에서 안정적인 성능 보장
- ✅ **로깅 개선**: CPU 제한 설정 및 재처리 과정 상세 로깅

### v1.3.0 (2025-07-25)
- ✅ **1B 8Q 모델 최적화**: 간단한 프롬프트와 최적화된 파라미터 적용
- ✅ **모델 파라미터 조정**: temperature, max_tokens 등 1B 8Q 모델에 맞게 최적화
- ✅ **postprocessor.py 개선**: 불필요한 필드 제거 및 타입 안전성 강화
- ✅ **형식 통일**: paragraphs 내 keyword 필드 형식 통일 (리스트 → 쉼표 구분 문자열)
- ✅ **오류 처리 개선**: 더 안전한 예외 처리 및 기본값 제공
- ✅ **타입 안전성 강화**: 다양한 데이터 타입에 대한 안전한 처리

### v1.2.0 (2025-07-18)
- ✅ **전처리 모듈 추가**: STT 결과 전처리 기능 (preprocessor.py)
- ✅ **후처리 모듈 추가**: 응답 후처리 및 필터링 기능 (postprocessor.py)
- ✅ **LLM 유틸리티 추가**: 공통 LLM 기능 모듈화 (llm_utils.py)
- ✅ **구조화된 JSON 응답**: summary, keyword, paragraphs 구조
- ✅ **타입 안전성 강화**: 다양한 데이터 타입에 대한 안전한 처리
- ✅ **강화된 에러 처리**: 다양한 에러 상황에 대한 Fallback 메커니즘
- ✅ **워크플로우 문서화**: 시스템 아키텍처 및 데이터 흐름 다이어그램
- ✅ **시퀀스 다이어그램 추가**: 상세한 데이터 흐름 및 컴포넌트 간 상호작용 문서화
- ✅ **샘플 데이터 확장**: 17개의 다양한 테스트 케이스 추가

### v1.1.0 (2025-07-15)
- ✅ Gemma 모델 JSON 응답 형식 적용
- ✅ 요약 결과를 "summary" 키로 표준화
- ✅ 연동규격 업데이트 (transactionid, sequenceno 기반)
- ✅ JSON 파싱 오류 처리 강화

### v1.0.0 (2025-07-15)
- ✅ 멀티슬롯 IPC 서버 구현
- ✅ 싱글톤 모델 로딩 최적화
- ✅ UTF-8 디코딩 오류 방지
- ✅ 비동기 로깅 시스템
- ✅ Windows 환경 지원
