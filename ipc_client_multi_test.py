import json
import time
import uuid
import threading
import subprocess
import sys
from ipc_queue_manager import IPCMultiSlotManager, SlotStatus
from typing import Optional

# IPC 설정 (서버와 동일)
SHM_NAME = "gemma_ipc_shm"
SLOT_COUNT = 5
SLOT_SIZE = 8192
POLLING_INTERVAL = 0.5
REQUEST_TIMEOUT = 30.0

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

def send_request(text: str, ipc_manager: IPCMultiSlotManager) -> Optional[int]:
    """요청 전송"""
    request_id = str(uuid.uuid4())[:8]  # 짧은 ID
    
    request = {
        "type": "request",
        "text": text,
        "request_id": request_id,
        "processed": False,
        "timestamp": time.time()
    }
    
    print(f"요청 전송 중... (ID: {request_id})")
    
    slot_id = ipc_manager.write_request(request)
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

def test_single_request():
    """단일 요청 테스트"""
    print("=== 단일 요청 테스트 ===")
    
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
        # 테스트 텍스트
        test_text = """
        김민준 팀장: 여보세요, 이서연 대리님. 김민준 팀장입니다.

이서연 대리: 네, 팀장님! 안녕하세요. 전화 주셨네요.

김민준 팀장: 네, 다름이 아니라 다음 주 수요일로 예정된 '알파 프로젝트' 신제품 런칭 캠페인 관련해서 최종 진행 상황 좀 체크하려고 전화했어요. 준비는 잘 되어가고 있죠?

이서연 대리: 아, 네. 마침 저도 중간 보고 드리려고 했습니다. 먼저, SNS 광고 소재는 어제 디자인팀에서 시안 2개를 받았고, 오늘 오후까지 제가 최종 1개 선택해서 전달드리겠습니다.

김민준 팀장: 좋습니다. 시안 퀄리티는 괜찮았나요?

이서연 대리: 네, 둘 다 괜찮아서 오히려 고르기가 어렵네요. 타겟 연령층 반응이 더 좋을 것 같은 B안으로 생각 중입니다.

김민준 팀장: 알겠습니다. 그건 이 대리님 판단에 맡길게요. 그리고 제가 맡은 보도자료는 초안 작성이 완료됐습니다. 이따가 메일로 보내드릴 테니, 오탈자나 어색한 부분 없는지 최종 검토 한번 부탁해요. 괜찮으면 내일 오전에 바로 홍보팀으로 넘기려고 합니다.

이서연 대리: 네, 알겠습니다! 메일 확인하고 바로 피드백 드리겠습니다. 그리고 인플루언서 협업 건은 리스트업했던 5명 중 3명에게서 긍정적인 회신을 받았습니다. 현재 계약 조건 최종 조율 중이에요.

김민준 팀장: 오, 다행이네요. 그런데 혹시 예산 문제는 없나요? 인플루언서 비용이 생각보다 높다고 들었던 것 같은데.

이서연 대리: 사실 그게 조금 문제입니다. 3명 모두와 진행할 경우, 저희가 처음 책정한 예산을 15% 정도 초과하게 됩니다. 어떻게 할까요?

김민준 팀장: 흠... 고민되네요. 일단 가장 반응이 좋고 우리 제품과 이미지가 잘 맞는 2명을 먼저 확정해서 진행합시다. 나머지 1명은 예비로 두고, 초과되는 예산은 제가 다른 항목에서 좀 조절해서 처리해 볼게요. 15% 정도는 팀장 재량으로 충분히 가능합니다.

이서연 대리: 정말요? 알겠습니다, 팀장님! 그럼 바로 두 분과 계약 마무리하고 진행 상황 공유드리겠습니다.

김민준 팀장: 네, 그렇게 합시다. 그럼 정리하자면, 이 대리님은 오늘 중으로 SNS 광고 시안 확정하고, 저는 보도자료 최종본을 내일 홍보팀에 전달하고. 인플루언서는 2명으로 확정해서 진행하는 걸로. 맞죠?

이서연 대리: 네, 맞습니다. 완벽하게 정리해주셨네요.

김민준 팀장: 좋습니다. 그럼 내일 오전에 오늘 정리된 내용 바탕으로 전체 진행 상황 다시 한번 공유하는 짧은 미팅 갖죠. 수고해요.

이서연 대리: 네, 팀장님. 내일 뵙겠습니다!
        """
        
        # 요청 전송
        slot_id = send_request(test_text, ipc_manager)
        if slot_id is None:
            print("요청 전송 실패")
            return
        
        print(f"요청 전송 완료 (슬롯: {slot_id})")
        print("응답 대기 중...")
        
        # 응답 대기
        response = wait_for_response(slot_id, ipc_manager)
        
        if response:
            print("\n=== 응답 수신 ===")
            print(f"요청 ID: {response.get('request_id')}")
            print(f"상태: {response.get('status')}")
            print(f"처리 시간: {response.get('processing_time', 'N/A')}초")
            print(f"요약 결과: {response.get('summary')}")
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
            print("공유 메모리 연결 해제")
        except Exception as e:
            print(f"정리 중 오류: {e}")
        
        print("=== 단일 요청 테스트 완료 ===")

def test_concurrent_requests():
    """동시 요청 테스트"""
    print("\n=== 동시 요청 테스트 ===")
    
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
        return
    
    try:
        # 여러 개의 짧은 테스트 텍스트
        test_texts = [
            "안녕하세요. 오늘 날씨가 좋네요.",
            "회의 시간을 조정하고 싶습니다.",
            "프로젝트 진행 상황을 확인해주세요.",
            "새로운 아이디어가 있어서 공유하고 싶습니다.",
            "다음 주 일정을 확인해주세요."
        ]
        
        # 동시에 여러 요청 전송
        slot_ids = []
        for i, text in enumerate(test_texts):
            slot_id = send_request(text, ipc_manager)
            if slot_id is not None:
                slot_ids.append((slot_id, f"요청 {i+1}"))
                print(f"요청 {i+1} 전송 완료: 슬롯 {slot_id}")
            else:
                print(f"요청 {i+1} 전송 실패")
        
        print(f"\n총 {len(slot_ids)}개 요청 전송 완료")
        
        # 모든 응답 대기
        responses = []
        for slot_id, request_name in slot_ids:
            print(f"{request_name} 응답 대기 중... (슬롯: {slot_id})")
            response = wait_for_response(slot_id, ipc_manager, timeout=60.0)
            if response:
                responses.append((request_name, response))
                print(f"{request_name} 응답 수신 완료")
            else:
                print(f"{request_name} 응답 타임아웃")
        
        # 결과 출력
        print(f"\n=== 동시 요청 결과 ===")
        print(f"전송된 요청: {len(slot_ids)}개")
        print(f"수신된 응답: {len(responses)}개")
        
        for request_name, response in responses:
            print(f"\n{request_name}:")
            print(f"  요청 ID: {response.get('request_id')}")
            print(f"  상태: {response.get('status')}")
            print(f"  처리 시간: {response.get('processing_time', 'N/A')}초")
            print(f"  요약: {response.get('summary')}")
    
    except Exception as e:
        print(f"동시 요청 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 정리
        try:
            ipc_manager.cleanup()
            print("공유 메모리 연결 해제")
        except Exception as e:
            print(f"정리 중 오류: {e}")
        
        print("=== 동시 요청 테스트 완료 ===")

def main():
    """메인 테스트 함수"""
    print("=== IPC 멀티슬롯 클라이언트 테스트 시작 ===")
    
    # 단일 요청 테스트
    test_single_request()
    
    # 잠시 대기
    time.sleep(2.0)
    
    # 동시 요청 테스트
    test_concurrent_requests()
    
    print("\n=== 모든 테스트 완료 ===")

if __name__ == "__main__":
    main() 