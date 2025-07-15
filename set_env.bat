@echo off
echo Gemma Summarizer 환경 변수 설정

REM 모델 설정
set MODEL_PATH=models/gemma-3-1b-it-Q8_0.gguf
set MODEL_CONTEXT_SIZE=2048

REM 요약 설정
set DEFAULT_MAX_TOKENS=100
set DEFAULT_TEMPERATURE=0.7

REM 출력 설정
set OUTPUT_FILE=gemma_summary.txt
set OUTPUT_ENCODING=utf-8

REM 로깅 설정
set LOG_LEVEL=INFO
set ENABLE_DEBUG=false

REM 성능 설정
set ENABLE_GPU=false
set THREADS=4

REM 파일 경로 설정
set WORKSPACE_DIR=%CD%
set MODELS_DIR=models

echo 환경 변수 설정 완료
echo.
echo 설정된 환경 변수:
echo MODEL_PATH=%MODEL_PATH%
echo MODEL_CONTEXT_SIZE=%MODEL_CONTEXT_SIZE%
echo DEFAULT_MAX_TOKENS=%DEFAULT_MAX_TOKENS%
echo OUTPUT_FILE=%OUTPUT_FILE%
echo THREADS=%THREADS%
echo WORKSPACE_DIR=%WORKSPACE_DIR%
echo.
echo 이제 gemma_summarizer_fixed.py를 실행할 수 있습니다.
pause 