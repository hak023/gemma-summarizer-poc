import json
import time
import uuid
import sys
import subprocess
import os
from ipc_queue_manager import IPCMultiSlotManager, SlotStatus
from typing import Optional

# IPC 설정 (서버와 동일)
import config
config_dict = config.get_config()

SHM_NAME = config_dict['IPC_SHM_NAME']
SLOT_COUNT = config_dict['IPC_SLOT_COUNT']
SLOT_SIZE = config_dict['IPC_SLOT_SIZE']
POLLING_INTERVAL = config_dict['IPC_POLLING_INTERVAL']
REQUEST_TIMEOUT = config_dict['IPC_REQUEST_TIMEOUT']

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

def load_sample_request(file_path: str = "sample/sample_request_6.json") -> dict:
    """샘플 요청 JSON 파일 로드"""
    try:
        if not os.path.exists(file_path):
            print(f"파일을 찾을 수 없습니다: {file_path}")
            return None
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"샘플 요청 파일 로드 완료: {file_path}")
        return data
        
    except Exception as e:
        print(f"파일 로드 중 오류: {e}")
        return None

def send_request(data: dict, ipc_manager: IPCMultiSlotManager) -> Optional[int]:
    """요청 전송"""
    # 원본 데이터에 timestamp 추가
    data["timestamp"] = time.time()
    
    # request_id가 없으면 생성
    if "request_id" not in data:
        data["request_id"] = str(uuid.uuid4())[:8]
    
    request_id = data.get("request_id", str(uuid.uuid4())[:8])
    
    print(f"요청 전송 중... (ID: {request_id})")
    print(f"원본 데이터 크기: {len(str(data))} 문자")
    
    slot_id = ipc_manager.write_request(data)
    if slot_id is None:
        print("요청 전송 실패 - 빈 슬롯이 없습니다")
        return None
    
    print(f"요청 전송 완료: 슬롯 {slot_id}")
    return slot_id

def wait_for_response(slot_id: int, ipc_manager: IPCMultiSlotManager, timeout=REQUEST_TIMEOUT):
    """응답 대기"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        response = ipc_manager.read_response(slot_id)
        
        if response:
            return response
        
        time.sleep(POLLING_INTERVAL)
    
    print(f"응답 타임아웃 (슬롯: {slot_id})")
    return None

def test_single_summarization():
    """단일 요약 테스트"""
    print("=== IPC 단일 요청 테스트 시작 ===")
    
    # 이전 프로세스 종료
    kill_previous_processes()
    
    # IPC 관리자 초기화 (클라이언트 모드)
    try:
        ipc_manager = IPCMultiSlotManager(SHM_NAME, SLOT_COUNT, SLOT_SIZE, is_client=True)
        print(f"공유 메모리 연결됨: {SHM_NAME}")
    except FileNotFoundError:
        print(f"공유 메모리를 찾을 수 없습니다: {SHM_NAME}")
        print("서버가 실행 중인지 확인해주세요.")
        return
    except Exception as e:
        print(f"공유 메모리 연결 실패: {e}")
        print("서버가 실행 중인지 확인해주세요.")
        return
    
    try:
        # 샘플 요청 파일 로드
        sample_data = load_sample_request()
        if sample_data is None:
            print("샘플 데이터 로드 실패")
            return
        
        # 요청 전송
        slot_id = send_request(sample_data, ipc_manager)
        if slot_id is None:
            print("요청 전송 실패")
            return
        
        print(f"요청 전송 완료 (슬롯: {slot_id})")
        print("응답 대기 중...")
        
        # 응답 대기
        response = wait_for_response(slot_id, ipc_manager)
        
        if response:
            print("\n=== 응답 수신 ===")
            print(f"Transaction ID: {response.get('transactionid')}")
            print(f"Sequence No: {response.get('sequenceno')}")
            print(f"Return Code: {response.get('returncode')}")
            print(f"Return Description: {response.get('returndescription')}")
            
            response_data = response.get('response', {})
            result = response_data.get('result', '')
            fail_reason = response_data.get('failReason', '')
            summary = response_data.get('summary', '')
            
            print(f"Result: {result}")
            if fail_reason:
                print(f"Fail Reason: {fail_reason}")
            if summary:
                print(f"Summary: {summary}")
        else:
            print("응답을 받지 못했습니다.")
    
    except Exception as e:
        print(f"테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 정리
        try:
            ipc_manager.cleanup()
            print("공유 메모리 연결 해제 완료")
        except Exception as e:
            print(f"정리 중 오류: {e}")
        
        print("=== 단일 요청 테스트 완료 ===")

if __name__ == "__main__":
    test_single_summarization() 