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

def load_sample_request(file_path: str = "sample/sample_request_2.json") -> dict:
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
    # 요청 시작 시간 기록
    request_start_time = time.time()
    
    # 원본 데이터에 timestamp 추가
    data["timestamp"] = request_start_time
    
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
    return slot_id, request_start_time

def wait_for_response(slot_id: int, ipc_manager: IPCMultiSlotManager, timeout=REQUEST_TIMEOUT):
    """응답 대기"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        response = ipc_manager.read_response(slot_id)
        
        if response:
            # 응답 수신 시간 기록
            response_time = time.time()
            return response, response_time
        
        time.sleep(POLLING_INTERVAL)
    
    print(f"응답 타임아웃 (슬롯: {slot_id})")
    return None, None

def parse_summary_response(summary_str: str) -> dict:
    """요약 응답 JSON 파싱 - 실제 응답 구조에 맞게 수정"""
    try:
        if isinstance(summary_str, str):
            response_data = json.loads(summary_str)
        elif isinstance(summary_str, dict):
            response_data = summary_str
        else:
            return {"summary": str(summary_str), "keyword": "", "paragraphs": []}
        
        # 실제 응답 구조에 맞게 필드 매핑
        # 기존 응답: summary, summary_no_limit, keywords, call_purpose, my_main_content, caller_main_content, my_emotion, caller_emotion, caller_info, my_action_after_call
        # 새로운 응답: summary, keyword, paragraphs
        
        # 새로운 구조로 변환
        new_response = {
            "summary": response_data.get('summary', ''),
            "keyword": response_data.get('keyword', ''),
            "paragraphs": response_data.get('paragraphs', [])
        }
        
        # 기존 구조의 필드들도 보존
        legacy_fields = {
            "summary_no_limit": response_data.get('summary_no_limit', ''),
            "keywords": response_data.get('keywords', ''),
            "call_purpose": response_data.get('call_purpose', ''),
            "my_main_content": response_data.get('my_main_content', ''),
            "caller_main_content": response_data.get('caller_main_content', ''),
            "my_emotion": response_data.get('my_emotion', ''),
            "caller_emotion": response_data.get('caller_emotion', ''),
            "caller_info": response_data.get('caller_info', ''),
            "my_action_after_call": response_data.get('my_action_after_call', '')
        }
        
        # 모든 필드 병합
        new_response.update(legacy_fields)
            
        return new_response
    except json.JSONDecodeError as e:
        print(f"JSON 파싱 오류: {e}")
        return {"summary": summary_str, "keyword": "", "paragraphs": [], "error": "JSON 파싱 실패"}

def display_raw_json_response(response_data: dict):
    """IPC로부터 수신받은 JSON 원문을 보기 좋게 출력"""
    print("\n" + "="*60)
    print("📄 IPC 수신 JSON 원문")
    print("="*60)
    
    try:
        # response 필드에서 summary 추출
        summary_str = response_data.get('response', {}).get('summary', '')
        if summary_str:
            # JSON 파싱 시도
            try:
                summary_json = json.loads(summary_str)
                # 보기 좋게 포맷팅
                formatted_json = json.dumps(summary_json, ensure_ascii=False, indent=2)
                print(formatted_json)
            except json.JSONDecodeError:
                # JSON이 아닌 경우 그대로 출력
                print(summary_str)
        else:
            print("❌ summary 필드가 없습니다.")
            
    except Exception as e:
        print(f"❌ JSON 출력 중 오류: {e}")

def display_summary_analysis(summary_data: dict):
    """요약 데이터 상세 분석 및 표시"""
    print("\n" + "="*60)
    print("📊 요약 분석 결과")
    print("="*60)
    
    # 기본 정보
    summary = summary_data.get('summary', '')
    keyword = summary_data.get('keyword', '')
    keywords = summary_data.get('keywords', '')  # 기존 필드도 확인
    
    print(f"📝 전체 요약: {summary}")
    print(f"🔑 주요 키워드: {keyword if keyword else keywords if keywords else '(없음)'}")
    
    # 기존 구조의 추가 정보도 표시
    summary_no_limit = summary_data.get('summary_no_limit', '')
    call_purpose = summary_data.get('call_purpose', '')
    my_main_content = summary_data.get('my_main_content', '')
    caller_main_content = summary_data.get('caller_main_content', '')
    my_emotion = summary_data.get('my_emotion', '')
    caller_emotion = summary_data.get('caller_emotion', '')
    caller_info = summary_data.get('caller_info', '')
    my_action_after_call = summary_data.get('my_action_after_call', '')
    
    if summary_no_limit and summary_no_limit != '통화 내용 상세 요약 없음':
        print(f"📄 상세 요약: {summary_no_limit}")
    if call_purpose and call_purpose != '통화 목적 미상':
        print(f"🎯 통화 목적: {call_purpose}")
    if my_main_content and my_main_content != '내용 없음':
        print(f"💬 내 주요 내용: {my_main_content}")
    if caller_main_content and caller_main_content != '내용 없음':
        print(f"📞 상대방 주요 내용: {caller_main_content}")
    if my_emotion and my_emotion != '보통':
        print(f"😊 내 감정: {my_emotion}")
    if caller_emotion and caller_emotion != '보통':
        print(f"😊 상대방 감정: {caller_emotion}")
    if caller_info:
        print(f"👤 상대방 정보: {caller_info}")
    if my_action_after_call and my_action_after_call != '없음':
        print(f"✅ 통화 후 행동: {my_action_after_call}")
    
    # paragraphs 분석
    paragraphs = summary_data.get('paragraphs', [])
    if paragraphs:
        print(f"\n📋 세부 분석 ({len(paragraphs)}개 단락):")
        print("-" * 50)
        
        for i, paragraph in enumerate(paragraphs, 1):
            para_summary = paragraph.get('summary', '')
            para_keyword = paragraph.get('keyword', '')
            sentiment = paragraph.get('sentiment', '보통')
            
            # 감정 이모지 매핑
            sentiment_emoji = {
                '강한긍정': '😊',
                '약한긍정': '🙂',
                '보통': '😐',
                '약한부정': '😕',
                '강한부정': '😠'
            }.get(sentiment, '😐')
            
            print(f"  {i}. {sentiment_emoji} {para_summary}")
            print(f"     키워드: {para_keyword}")
            print(f"     감정: {sentiment}")
            print()
    else:
        print("\n⚠️ 세부 분석 정보가 없습니다.")
    
    # 통계 정보
    print("📈 통계 정보:")
    print(f"  - 전체 요약 길이: {len(summary)}자")
    print(f"  - 키워드 개수: {len(keyword.split(',')) if keyword else 0}개")
    print(f"  - 분석 단락 수: {len(paragraphs)}개")
    
    # 감정 분포 분석
    if paragraphs:
        sentiment_counts = {}
        for para in paragraphs:
            sentiment = para.get('sentiment', '보통')
            sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1
        
        print(f"  - 감정 분포: {', '.join([f'{k}({v})' for k, v in sentiment_counts.items()])}")

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
        result = send_request(sample_data, ipc_manager)
        if result is None:
            print("요청 전송 실패")
            return
        
        slot_id, request_start_time = result
        print(f"요청 전송 완료 (슬롯: {slot_id})")
        print("응답 대기 중...")
        
        # 응답 대기
        response_result = wait_for_response(slot_id, ipc_manager)
        
        if response_result[0]:
            response, response_time = response_result
            
            # 요청-응답 시간 계산
            total_time = response_time - request_start_time
            print(f"\n⏱️ 요청-응답 시간: {total_time:.3f}초")
            
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
            
            # IPC 수신 JSON 원문 출력
            display_raw_json_response(response)
            
            # 새로운 JSON 구조 파싱 및 분석
            if summary:
                try:
                    summary_data = parse_summary_response(summary)
                    display_summary_analysis(summary_data)
                except Exception as e:
                    print(f"요약 분석 중 오류: {e}")
                    print(f"원본 요약: {summary}")
        else:
            print("응답을 받지 못했습니다.")
            if response_result[1] is None:
                print("⏱️ 요청-응답 시간: 타임아웃 (응답 없음)")
    
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

def test_multiple_requests():
    """다중 요청 테스트"""
    print("=== IPC 다중 요청 테스트 시작 ===")
    
    # 이전 프로세스 종료
    kill_previous_processes()
    
    # IPC 관리자 초기화
    try:
        ipc_manager = IPCMultiSlotManager(SHM_NAME, SLOT_COUNT, SLOT_SIZE, is_client=True)
        print(f"공유 메모리 연결됨: {SHM_NAME}")
    except Exception as e:
        print(f"공유 메모리 연결 실패: {e}")
        return
    
    try:
        # 여러 샘플 파일 테스트
        sample_files = [
            "sample/sample_request_1.json",
            "sample/sample_request_2.json",
            "sample/sample_request_3.json"
        ]
        
        results = []
        
        for i, sample_file in enumerate(sample_files, 1):
            if not os.path.exists(sample_file):
                print(f"파일을 찾을 수 없습니다: {sample_file}")
                continue
                
            print(f"\n--- 테스트 {i}: {sample_file} ---")
            
            # 샘플 데이터 로드
            sample_data = load_sample_request(sample_file)
            if sample_data is None:
                continue
            
            # 요청 전송
            result = send_request(sample_data, ipc_manager)
            if result is None:
                continue
            
            slot_id, request_start_time = result
            
            # 응답 대기
            response_result = wait_for_response(slot_id, ipc_manager)
            
            if response_result[0]:
                response, response_time = response_result
                
                # 요청-응답 시간 계산
                total_time = response_time - request_start_time
                print(f"⏱️ 요청-응답 시간: {total_time:.3f}초")
                
                response_data = response.get('response', {})
                result = response_data.get('result', '')
                summary = response_data.get('summary', '')
                
                if result == '0' and summary:
                    try:
                        summary_data = parse_summary_response(summary)
                        results.append({
                            'file': sample_file,
                            'summary': summary_data.get('summary', ''),
                            'paragraphs_count': len(summary_data.get('paragraphs', [])),
                            'response_time': total_time
                        })
                        print(f"✅ 성공: {summary_data.get('summary', '')}")
                    except Exception as e:
                        print(f"❌ 파싱 실패: {e}")
                else:
                    print(f"❌ 실패: {response_data.get('failReason', 'Unknown error')}")
            else:
                print("❌ 응답 없음")
                if response_result[1] is None:
                    print("⏱️ 요청-응답 시간: 타임아웃 (응답 없음)")
        
        # 결과 요약
        print(f"\n=== 테스트 결과 요약 ===")
        print(f"총 테스트: {len(sample_files)}개")
        print(f"성공: {len(results)}개")
        print(f"실패: {len(sample_files) - len(results)}개")
        
        if results:
            print("\n성공한 요약들:")
            total_response_time = 0
            for result in results:
                response_time = result.get('response_time', 0)
                total_response_time += response_time
                print(f"  - {result['file']}: {result['summary']} ({result['paragraphs_count']}개 단락, {response_time:.3f}초)")
            
            if results:
                avg_response_time = total_response_time / len(results)
                print(f"\n📊 평균 응답 시간: {avg_response_time:.3f}초")
    
    except Exception as e:
        print(f"다중 테스트 중 오류: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            ipc_manager.cleanup()
            print("공유 메모리 연결 해제 완료")
        except Exception as e:
            print(f"정리 중 오류: {e}")
        
        print("=== 다중 요청 테스트 완료 ===")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "multi":
        test_multiple_requests()
    else:
        test_single_summarization() 