import os
import time
import json
import asyncio
import aiofiles
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

class RequestLogger:
    """요청과 응답 처리 결과를 로그 파일로 기록하는 클래스 (비동기 지원)"""
    
    def __init__(self, log_dir="logs"):
        """
        로거 초기화
        
        Args:
            log_dir (str): 로그 파일이 저장될 디렉토리
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="Logger")
        
    def _generate_log_filename(self, process_name: str) -> str:
        """
        날짜별 로그 파일명 생성 (같은 날짜에는 같은 파일 사용)
        
        Args:
            process_name (str): 프로세스명
            
        Returns:
            str: 날짜별 로그 파일명
        """
        date_str = datetime.now().strftime("%Y%m%d")  # 날짜만 사용
        safe_process_name = "".join(c for c in process_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_process_name = safe_process_name.replace(' ', '_')
        
        return f"{safe_process_name}_{date_str}.txt"
    
    async def _async_write_log(self, log_path: str, content: str, mode: str = 'a'):
        """
        비동기로 로그 파일에 내용을 기록
        
        Args:
            log_path (str): 로그 파일 경로
            content (str): 기록할 내용
            mode (str): 파일 열기 모드 ('a' 또는 'w')
        """
        try:
            async with aiofiles.open(log_path, mode, encoding='utf-8') as f:
                await f.write(content)
        except Exception as e:
            print(f"비동기 로그 기록 오류: {e}")
    
    def _sync_write_log(self, log_path: str, content: str, mode: str = 'a'):
        """
        동기적으로 로그 파일에 내용을 기록 (fallback용)
        
        Args:
            log_path (str): 로그 파일 경로
            content (str): 기록할 내용
            mode (str): 파일 열기 모드 ('a' 또는 'w')
        """
        try:
            with open(log_path, mode, encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            print(f"동기 로그 기록 오류: {e}")
    
    def log_request(self, request_data: dict, process_name: str = "gemma_summarizer") -> str:
        """
        요청 데이터를 로그 파일에 기록 (비동기)
        Args:
            request_data (dict): 요청 데이터
            process_name (str): 프로세스명
        Returns:
            str: 생성된 로그 파일 경로
        """
        log_filename = self._generate_log_filename(process_name)
        log_path = self.log_dir / log_filename

        is_new_file = not os.path.exists(log_path)
        mode = 'a' if not is_new_file else 'w'

        content = ""
        if is_new_file:
            content += (
                "=" * 80 + "\n"
                f"요청 처리 로그\n"
                "=" * 80 + "\n"
                f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n"
                f"프로세스명: {process_name}\n"
                f"로그 파일: {log_filename}\n"
                "-" * 80 + "\n"
            )
        # 헤더는 새 파일일 때만 기록

        content += (
            "\n" + "=" * 80 + "\n"
            f"새 요청 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n"
            "-" * 80 + "\n"
            "요청 데이터:\n"
            "-" * 80 + "\n"
            f"{json.dumps(request_data, ensure_ascii=False, indent=2)}\n"
            "-" * 80 + "\n"
            "처리 시작...\n"
        )

        # 비동기로 로그 기록 (실패 시 동기 방식으로 fallback)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.run_in_executor(self.executor, self._sync_write_log, str(log_path), content, mode)
            else:
                asyncio.run(self._async_write_log(str(log_path), content, mode))
        except Exception:
            self._sync_write_log(str(log_path), content, mode)

        print(f"요청 로그 생성: {log_path}")
        return str(log_path)

    def log_response(self, log_path: str, response_data: dict, processing_time: float = None):
        """
        응답 데이터를 기존 로그 파일에 추가 (비동기)
        Args:
            log_path (str): 로그 파일 경로
            response_data (dict): 응답 데이터
            processing_time (float, optional): 처리 시간
        """
        if not log_path or not os.path.exists(log_path):
            print("로그 파일이 존재하지 않습니다.")
            return

        content = (
            "응답 데이터:\n"
            "-" * 80 + "\n"
            f"{json.dumps(response_data, ensure_ascii=False, indent=2)}\n"
        )
        if processing_time is not None:
            content += f"처리 시간: {processing_time:.3f}초\n"
        content += (
            f"완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n"
            + "=" * 80 + "\n"
        )

        # 비동기로 로그 기록
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.run_in_executor(self.executor, self._sync_write_log, log_path, content, 'a')
            else:
                asyncio.run(self._async_write_log(log_path, content, 'a'))
        except Exception:
            self._sync_write_log(log_path, content, 'a')

        print(f"응답 로그 추가 완료: {log_path}")
    
    def log_error(self, log_path: str, error_message: str, error_traceback: str = None):
        """
        오류 정보를 로그 파일에 추가 (비동기)
        
        Args:
            log_path (str): 로그 파일 경로
            error_message (str): 오류 메시지
            error_traceback (str, optional): 오류 스택 트레이스
        """
        if not log_path or not os.path.exists(log_path):
            print("로그 파일이 존재하지 않습니다.")
            return
            
        try:
            content = (
                "오류 발생:\n"
                "-" * 80 + "\n"
                f"오류 메시지: {error_message}\n"
            )
            
            if error_traceback:
                content += f"오류 상세:\n{error_traceback}\n"
            
            content += (
                f"오류 발생 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n"
                "=" * 80 + "\n"
            )
            
            # 비동기로 로그 기록
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.run_in_executor(self.executor, self._sync_write_log, log_path, content, 'a')
                else:
                    asyncio.run(self._async_write_log(log_path, content, 'a'))
            except Exception:
                self._sync_write_log(log_path, content, 'a')
                
            print(f"오류 로그 추가 완료: {log_path}")
            
        except Exception as e:
            print(f"오류 로그 추가 오류: {e}")
    
    def log_server_status(self, process_name: str = "gemma_summarizer", status: str = "running"):
        """
        서버 상태를 로그 파일에 기록 (비활성화됨)
        
        Args:
            process_name (str): 프로세스명
            status (str): 서버 상태
        """
        # 로깅 비활성화
        return ""

# 전역 로거 인스턴스
request_logger = RequestLogger()

def log_request_response(request_data: dict, response_data: dict, processing_time: float = None, 
                        process_name: str = "gemma_summarizer") -> str:
    """
    요청과 응답을 한 번에 로그 파일에 기록하는 편의 함수 (반복 로그 방지)
    
    Args:
        request_data (dict): 요청 데이터
        response_data (dict): 응답 데이터
        processing_time (float, optional): 처리 시간
        process_name (str): 프로세스명
        
    Returns:
        str: 생성된 로그 파일 경로
    """
    try:
        log_filename = request_logger._generate_log_filename(process_name)
        log_path = request_logger.log_dir / log_filename
        
        # 파일이 존재하는지 확인
        is_new_file = not os.path.exists(log_path)
        
        # 헤더는 파일이 없을 때만 추가
        if is_new_file:
            header_content = (
                "=" * 80 + "\n"
                + "요청 처리 로그\n"
                + "=" * 80 + "\n"
                + f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n"
                + f"프로세스명: {process_name}\n"
                + f"로그 파일: {log_filename}\n"
                + "-" * 80 + "\n"
            )
            # 헤더를 먼저 기록
            request_logger._sync_write_log(str(log_path), header_content, 'w')
        
        # 요청/응답 본문은 항상 추가
        content = (
            "\n" + "=" * 80 + "\n"
            + f"새 요청 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n"
            + "-" * 80 + "\n"
            + "요청 데이터:\n"
            + "-" * 80 + "\n"
            + f"{json.dumps(request_data, ensure_ascii=False, indent=2)}\n"
            + "-" * 80 + "\n"
            + "응답 데이터:\n"
            + "-" * 80 + "\n"
            + f"{json.dumps(response_data, ensure_ascii=False, indent=2)}\n"
        )
        if processing_time is not None:
            content += f"처리 시간: {processing_time:.3f}초\n"
        content += (
            f"완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n"
            + "=" * 80 + "\n"
        )

        # 요청/응답 본문을 추가 모드로 기록
        request_logger._sync_write_log(str(log_path), content, 'a')
        
        print(f"요청-응답 로그 생성: {log_path}")
        return str(log_path)
        
    except Exception as e:
        print(f"로그 기록 중 오류 발생: {e}")
        return ""

def log_request_only(request_data: dict, process_name: str = "gemma_summarizer") -> str:
    """
    요청 데이터만 별도로 로그 파일에 기록
    
    Args:
        request_data (dict): 원본 요청 데이터
        process_name (str): 프로세스명
        
    Returns:
        str: 생성된 로그 파일 경로
    """
    try:
        log_filename = request_logger._generate_log_filename(process_name)
        log_path = request_logger.log_dir / log_filename
        
        is_new_file = not os.path.exists(log_path)
        mode = 'a' if not is_new_file else 'w'
        
        content = ""
        if is_new_file:
            content += (
                "=" * 80 + "\n"
                + f"요청 데이터 로그\n"
                + "=" * 80 + "\n"
                + f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n"
                + f"프로세스명: {process_name}\n"
                + f"로그 파일: {log_filename}\n"
                + "-" * 80 + "\n"
            )
        
        content += (
            "\n" + "=" * 80 + "\n"
            + f"요청 수신 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n"
            + "-" * 80 + "\n"
            + "원본 요청 데이터:\n"
            + "-" * 80 + "\n"
            + f"{json.dumps(request_data, ensure_ascii=False, indent=2)}\n"
            + "-" * 80 + "\n"
        )
        
        request_logger._sync_write_log(str(log_path), content, mode)
        print(f"요청 로그 생성: {log_path}")
        return str(log_path)
        
    except Exception as e:
        print(f"요청 로그 생성 오류: {e}")
        return ""

def log_response_only(response_data: dict, process_name: str = "gemma_summarizer") -> str:
    """
    응답 데이터만 별도로 로그 파일에 기록
    
    Args:
        response_data (dict): 응답 데이터
        process_name (str): 프로세스명
        
    Returns:
        str: 생성된 로그 파일 경로
    """
    try:
        log_filename = request_logger._generate_log_filename(process_name)
        log_path = request_logger.log_dir / log_filename
        
        content = (
            "\n" + "=" * 80 + "\n"
            + f"응답 전송 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n"
            + "-" * 80 + "\n"
            + "응답 데이터:\n"
            + "-" * 80 + "\n"
            + f"{json.dumps(response_data, ensure_ascii=False, indent=2)}\n"
            + "-" * 80 + "\n"
        )
        
        request_logger._sync_write_log(str(log_path), content, 'a')
        print(f"응답 로그 추가: {log_path}")
        return str(log_path)
        
    except Exception as e:
        print(f"응답 로그 추가 오류: {e}")
        return ""

def log_gemma_query(query_text: str, process_name: str = "gemma_summarizer") -> str:
    """
    Gemma 모델에 전송하는 질의 텍스트를 로그 파일에 기록
    
    Args:
        query_text (str): Gemma 모델에 전송하는 질의 텍스트
        process_name (str): 프로세스명
        
    Returns:
        str: 생성된 로그 파일 경로
    """
    try:
        log_filename = request_logger._generate_log_filename(process_name)
        log_path = request_logger.log_dir / log_filename
        
        content = (
            "\n" + "=" * 80 + "\n"
            + f"Gemma 질의 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n"
            + "-" * 80 + "\n"
            + "Gemma 모델 질의 텍스트:\n"
            + "-" * 80 + "\n"
            + f"{query_text}\n"
            + "-" * 80 + "\n"
        )
        
        request_logger._sync_write_log(str(log_path), content, 'a')
        print(f"Gemma 질의 로그 추가: {log_path}")
        return str(log_path)
        
    except Exception as e:
        print(f"Gemma 질의 로그 추가 오류: {e}")
        return ""

def log_gemma_response(gemma_response: str, process_name: str = "gemma_summarizer") -> str:
    """
    Gemma 모델로부터 받은 응답을 로그 파일에 기록
    
    Args:
        gemma_response (str): Gemma 모델로부터 받은 응답
        process_name (str): 프로세스명
        
    Returns:
        str: 생성된 로그 파일 경로
    """
    try:
        log_filename = request_logger._generate_log_filename(process_name)
        log_path = request_logger.log_dir / log_filename
        
        content = (
            "\n" + "=" * 80 + "\n"
            + f"Gemma 응답 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n"
            + "-" * 80 + "\n"
            + "Gemma 모델 응답:\n"
            + "-" * 80 + "\n"
            + f"{gemma_response}\n"
            + "-" * 80 + "\n"
        )
        
        request_logger._sync_write_log(str(log_path), content, 'a')
        print(f"Gemma 응답 로그 추가: {log_path}")
        return str(log_path)
        
    except Exception as e:
        print(f"Gemma 응답 로그 추가 오류: {e}")
        return ""

def log_error_only(error_message: str, error_traceback: str = None, 
                   process_name: str = "gemma_summarizer") -> str:
    """
    오류만 로그 파일에 기록하는 편의 함수 (비동기)
    
    Args:
        error_message (str): 오류 메시지
        error_traceback (str, optional): 오류 스택 트레이스
        process_name (str): 프로세스명
        
    Returns:
        str: 생성된 로그 파일 경로
    """
    log_filename = request_logger._generate_log_filename(f"{process_name}_error")
    log_path = request_logger.log_dir / log_filename
    
    try:
        # 파일이 존재하면 추가 모드, 없으면 새로 생성
        mode = 'a' if os.path.exists(log_path) else 'w'
        
        if mode == 'w':
            content = (
                "=" * 80 + "\n"
                + f"오류 로그\n"
                + "=" * 80 + "\n"
                + f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n"
                + f"프로세스명: {process_name}\n"
                + f"로그 파일: {log_filename}\n"
                + "-" * 80 + "\n"
            )
        else:
            content = (
                "\n" + "=" * 80 + "\n"
                + f"새 오류 발생 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n"
                + "-" * 80 + "\n"
            )
        
        content += (
            + f"오류 메시지: {error_message}\n"
        )
        
        if error_traceback:
            content += f"오류 상세:\n{error_traceback}\n"
        
        content += "=" * 80 + "\n"
        
        # 비동기로 로그 기록
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.run_in_executor(request_logger.executor, request_logger._sync_write_log, str(log_path), content, mode)
            else:
                asyncio.run(request_logger._async_write_log(str(log_path), content, mode))
        except Exception:
            request_logger._sync_write_log(str(log_path), content, mode)
            
        print(f"오류 로그 생성: {log_path}")
        return str(log_path)
        
    except Exception as e:
        print(f"오류 로그 생성 오류: {e}")
        return "" 