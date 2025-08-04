import sys
import os
import time
import traceback
import subprocess
from pathlib import Path
import threading
from datetime import datetime
from config import get_config, validate_config
from ipc_queue_manager import IPCMultiSlotManager, QueueManager, SlotStatus
from gemma_summarizer import process_request
from preprocessor import preprocess_request_data
from logger import log_request_only, log_response_only, log_gemma_query, log_gemma_response



def worker_thread(queue_manager: QueueManager):
    """AI 요약 처리 워커 스레드"""
    print("워커 스레드 시작")
    
    # CPU 제한 확인
    import multiprocessing
    import os
    cpu_count = multiprocessing.cpu_count()
    cpu_limit_percent = int(os.getenv('CPU_LIMIT_PERCENT', 25))
    max_threads = max(1, int(cpu_count * cpu_limit_percent / 100))
    force_threads = os.getenv('MAX_CPU_THREADS')
    if force_threads:
        max_threads = int(force_threads)
    
    print(f"워커 스레드 CPU 제한 설정:")
    print(f"  - 총 CPU 코어 수: {cpu_count}")
    print(f"  - CPU 제한 퍼센트: {cpu_limit_percent}%")
    print(f"  - 사용할 스레드 수: {max_threads}")
    print(f"  - 강제 스레드 설정: {force_threads if force_threads else '없음'}")
    
    while queue_manager.running:
        try:
            # 요청 큐에서 작업 가져오기
            request_item = queue_manager.get_request()
            if not request_item:
                continue
            
            slot_id, data = request_item
            print(f"워커: 슬롯 {slot_id}에서 요청 처리 시작")
            
            # 전처리 수행 (요약 전에 수행)
            if 'sttResultList' in data:
                print(f"워커: 슬롯 {slot_id} 전처리 수행 중...")
                processed_data = preprocess_request_data(data)
                print(f"워커: 슬롯 {slot_id} 전처리 완료: {len(processed_data.get('text', ''))} 문자")
                
                # 전처리된 데이터로 요약 수행
                response_data = process_request(processed_data)
            else:
                # 이미 전처리된 데이터인 경우
                print(f"워커: 슬롯 {slot_id} 이미 전처리된 데이터 사용")
                response_data = process_request(data)
            
            # 응답 데이터 로깅
            log_response_only(response_data, "gemma_summarizer")
            
            # 응답 큐에 추가
            queue_manager.put_response(slot_id, response_data)
            print(f"워커: 슬롯 {slot_id} 응답 큐에 추가 완료")
            
        except Exception as e:
            print(f"워커 스레드 오류: {e}")
            traceback.print_exc()
            time.sleep(1.0)
    
    print("워커 스레드 종료")

def response_writer_thread(ipc_manager: IPCMultiSlotManager, queue_manager: QueueManager):
    """응답 쓰기 스레드"""
    print("응답 쓰기 스레드 시작")
    
    while queue_manager.running:
        try:
            # 응답 큐에서 응답 가져오기
            response_item = queue_manager.get_response()
            if not response_item:
                continue
            
            slot_id, response_data = response_item
            print(f"응답 쓰기: 슬롯 {slot_id}에 응답 쓰기 시작")
            
            # 공유 메모리에 응답 쓰기
            if ipc_manager.write_response(slot_id, response_data):
                print(f"응답 쓰기: 슬롯 {slot_id} 응답 쓰기 완료")
            else:
                print(f"응답 쓰기: 슬롯 {slot_id} 응답 쓰기 실패")
                # 에러 상태로 표시
                ipc_manager.mark_slot_error(slot_id)
            
        except Exception as e:
            print(f"응답 쓰기 스레드 오류: {e}")
            traceback.print_exc()
            time.sleep(1.0)
    
    print("응답 쓰기 스레드 종료")

def kill_previous_processes():
    """이전에 실행 중인 프로세스들을 종료"""
    try:
        print("이전 프로세스 확인 중...")
        result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq python.exe', '/FO', 'CSV'], 
                              capture_output=True, text=True, shell=True)
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            killed_count = 0
            
            for line in lines[1:]:  # 헤더 제외
                if 'gemma_summarizer' in line or 'ipc_client' in line:
                    parts = line.split(',')
                    if len(parts) >= 2:
                        pid = parts[1].strip('"')
                        try:
                            subprocess.run(['taskkill', '/F', '/PID', pid], 
                                         capture_output=True, shell=True)
                            killed_count += 1
                            print(f"프로세스 종료: PID {pid}")
                        except:
                            pass
            
            if killed_count > 0:
                print(f"{killed_count}개 이전 프로세스 종료 완료")
                time.sleep(2)  # 프로세스 종료 대기
            else:
                print("종료할 이전 프로세스가 없습니다.")
                
    except Exception as e:
        print(f"프로세스 종료 중 오류: {e}")

def main():
    print("=== Gemma Multi-Slot IPC Summarizer 시작 ===")
    print(f"현재 작업 디렉토리: {os.getcwd()}")
    print(f"Python 실행 파일: {sys.executable}")
    
    # 이전 프로세스 종료
    kill_previous_processes()
    
    # 설정 유효성 검사
    if not validate_config():
        print("설정 오류가 있습니다. config.py를 확인해주세요.")
        sys.exit(1)
    
    # 서버 시작 로그 생성 완전 제거
    server_log_path = None
    
    # 설정 가져오기
    config = get_config()
    
    # IPC 관리자 초기화
    ipc_manager = None
    queue_manager = None
    worker_thread_obj = None
    response_writer_thread_obj = None
    
    try:
        # IPC 관리자 초기화
        shm_name = config.get('IPC_SHM_NAME', 'gemma_ipc_shm')
        slot_count = config.get('IPC_SLOT_COUNT', 5)
        slot_size = config.get('IPC_SLOT_SIZE', 8192)
        
        ipc_manager = IPCMultiSlotManager(shm_name, slot_count, slot_size)
        queue_manager = QueueManager()
        
        # 서버 시작 시 모든 슬롯 강제 초기화
        ipc_manager.force_reset_all_slots()
        
        print(f"IPC 설정: {slot_count}개 슬롯, 슬롯당 {slot_size} bytes")
        print("IPC 서버 시작 - 대기 중...")
        
        # 워커 스레드 시작
        worker_thread_obj = threading.Thread(
            target=worker_thread, 
            args=(queue_manager,),
            daemon=True
        )
        worker_thread_obj.start()
        
        # 응답 쓰기 스레드 시작
        response_writer_thread_obj = threading.Thread(
            target=response_writer_thread,
            args=(ipc_manager, queue_manager),
            daemon=True
        )
        response_writer_thread_obj.start()
        
        print("모든 스레드 시작 완료")
        
        # 메인 루프: 요청 감지 및 큐에 추가
        last_activity = time.time()
        polling_interval = config.get('IPC_POLLING_INTERVAL', 0.5)
        request_timeout = config.get('IPC_REQUEST_TIMEOUT', 30.0)
        
        while True:
            try:
                # 새로운 요청 감지
                request_item = ipc_manager.read_request()
                if request_item:
                    last_activity = time.time()
                    slot_id, data = request_item
                    print(f"새 요청 감지: 슬롯 {slot_id}, ID: {data.get('request_id', 'unknown')}")
                    
                    # 원본 요청 데이터 로깅
                    log_request_only(data, "gemma_summarizer")
                    
                    # 원본 데이터를 그대로 큐에 추가 (전처리는 worker에서 수행)
                    queue_manager.put_request(slot_id, data)
                    print(f"요청 큐에 추가 완료: 슬롯 {slot_id}")
                
                # 타임아웃 체크
                if time.time() - last_activity > request_timeout:
                    print("활동 없음 - 서버 상태 확인 중...")
                    last_activity = time.time()
                
                time.sleep(polling_interval)
                
            except KeyboardInterrupt:
                print("\n사용자에 의해 중단됨")
                break
            except Exception as e:
                print(f"메인 루프 오류: {e}")
                print(traceback.format_exc())
                time.sleep(1.0)
    
    except Exception as e:
        print(f"초기화 오류: {e}")
        print(traceback.format_exc())
    
    finally:
        # 정리 작업
        print("정리 작업 중...")
        
        # 서버 종료 로그 추가 완전 제거
        pass
        
        # 큐 매니저 중지
        if queue_manager:
            queue_manager.stop()
        
        # 스레드 종료 대기
        if worker_thread_obj and worker_thread_obj.is_alive():
            worker_thread_obj.join(timeout=5.0)
        
        if response_writer_thread_obj and response_writer_thread_obj.is_alive():
            response_writer_thread_obj.join(timeout=5.0)
        
        # IPC 관리자 정리
        if ipc_manager:
            ipc_manager.cleanup()
        
        print("=== 프로그램 종료 ===")

if __name__ == "__main__":
    main() 