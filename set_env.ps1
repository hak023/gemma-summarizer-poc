# Gemma Summarizer 환경 변수 설정 (PowerShell)

Write-Host "Gemma Summarizer 환경 변수 설정" -ForegroundColor Green

# 모델 설정
$env:MODEL_PATH = "models/gemma-3-1b-it-Q8_0.gguf"
$env:MODEL_CONTEXT_SIZE = "8192"

# 요약 설정
$env:DEFAULT_MAX_TOKENS = "500"
$env:DEFAULT_TEMPERATURE = "0.7"

# 출력 설정
$env:OUTPUT_FILE = "gemma_summary.txt"
$env:OUTPUT_ENCODING = "utf-8"

# 로깅 설정
$env:LOG_LEVEL = "INFO"
$env:ENABLE_DEBUG = "false"

# 성능 설정
$env:ENABLE_GPU = "false"
$env:THREADS = "4"

# 파일 경로 설정
$env:WORKSPACE_DIR = Get-Location
$env:MODELS_DIR = "models"

Write-Host "환경 변수 설정 완료" -ForegroundColor Green
Write-Host ""
Write-Host "설정된 환경 변수:" -ForegroundColor Yellow
Write-Host "MODEL_PATH: $env:MODEL_PATH"
Write-Host "MODEL_CONTEXT_SIZE: $env:MODEL_CONTEXT_SIZE"
Write-Host "DEFAULT_MAX_TOKENS: $env:DEFAULT_MAX_TOKENS"
Write-Host "OUTPUT_FILE: $env:OUTPUT_FILE"
Write-Host "THREADS: $env:THREADS"
Write-Host "WORKSPACE_DIR: $env:WORKSPACE_DIR"
Write-Host ""
Write-Host "이제 gemma_summarizer_fixed.py를 실행할 수 있습니다." -ForegroundColor Cyan

# 현재 세션에서만 유효하므로, 실행 명령어도 제공
Write-Host "실행 명령어: python gemma_summarizer_fixed.py" -ForegroundColor Magenta 