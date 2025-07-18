import json
import time
import threading
import queue
from multiprocessing import shared_memory, Lock
from typing import Optional, Dict, Any
import struct

class SlotStatus:
    """슬롯 상태 상수"""
    EMPTY = 0
    REQUEST = 1
    PROCESSING = 2
    RESPONSE = 3
    ERROR = 4

class IPCSlot:
    """개별 IPC 슬롯 클래스"""
    def __init__(self, slot_id: int, data_offset: int, data_size: int):
        self.slot_id = slot_id
        self.data_offset = data_offset
        self.data_size = data_size
        
        # 슬롯 헤더 크기: status(4) + timestamp(8) + request_id(32) + data_length(4) = 48 bytes
        self.header_size = 48
        self.max_data_size = data_size - self.header_size
    
    def get_status_offset(self) -> int:
        return self.data_offset
    
    def get_timestamp_offset(self) -> int:
        return self.data_offset + 4
    
    def get_request_id_offset(self) -> int:
        return self.data_offset + 12
    
    def get_data_length_offset(self) -> int:
        return self.data_offset + 44
    
    def get_data_offset(self) -> int:
        return self.data_offset + self.header_size

class IPCMultiSlotManager:
    """멀티슬롯 IPC 관리자"""
    
    def __init__(self, shm_name: str, slot_count: int = 5, slot_size: int = 8192, is_client: bool = False):
        self.shm_name = shm_name
        self.slot_count = slot_count
        self.slot_size = slot_size
        self.total_size = slot_count * slot_size
        self.is_client = is_client
        
        # 슬롯 정보 계산
        self.slots = []
        for i in range(slot_count):
            data_offset = i * slot_size
            self.slots.append(IPCSlot(i, data_offset, slot_size))
        
        # Lock 관리
        self.lock = Lock()
        
        # 공유 메모리 연결
        self.shm = None
        if is_client:
            self._connect_shm_client()
        else:
            self._connect_shm()
    
    def _connect_shm(self):
        """공유 메모리 연결"""
        try:
            self.shm = shared_memory.SharedMemory(name=self.shm_name, create=True, size=self.total_size)
            print(f"공유 메모리 생성됨: {self.shm_name} ({self.total_size} bytes, {self.slot_count} slots)")
            
            # 새로 생성된 메모리를 완전히 0으로 초기화
            print("공유 메모리 완전 초기화 중...")
            for i in range(self.total_size):
                self.shm.buf[i] = 0
            print("공유 메모리 초기화 완료")
            
            self._initialize_slots()
        except FileExistsError:
            # 기존 공유 메모리가 있으면 정리 후 재생성
            print(f"기존 공유 메모리 발견: {self.shm_name} - 정리 후 재생성")
            self._cleanup_existing_shm()
            
            # 강제로 공유 메모리 생성 시도 (여러 번 시도)
            for attempt in range(3):
                try:
                    self.shm = shared_memory.SharedMemory(name=self.shm_name, create=True, size=self.total_size)
                    print(f"공유 메모리 재생성됨: {self.shm_name} ({self.total_size} bytes, {self.slot_count} slots)")
                    break
                except FileExistsError:
                    print(f"공유 메모리 재생성 시도 {attempt + 1} 실패, 다시 정리 후 시도")
                    if attempt < 2:
                        self._cleanup_existing_shm()
                        time.sleep(2.0)
                    else:
                        raise Exception(f"공유 메모리 재생성 실패: {self.shm_name}")
            
            # 재생성된 메모리도 완전히 0으로 초기화
            print("재생성된 공유 메모리 완전 초기화 중...")
            for i in range(self.total_size):
                self.shm.buf[i] = 0
            print("재생성된 공유 메모리 초기화 완료")
            
            self._initialize_slots()
    
    def _connect_shm_client(self):
        """클라이언트용 공유 메모리 연결 (기존 메모리 사용)"""
        try:
            self.shm = shared_memory.SharedMemory(name=self.shm_name)
            print(f"기존 공유 메모리 연결됨: {self.shm_name}")
        except FileNotFoundError:
            raise FileNotFoundError(f"공유 메모리를 찾을 수 없습니다: {self.shm_name}")
        except Exception as e:
            raise Exception(f"공유 메모리 연결 실패: {e}")
    
    def _cleanup_existing_shm(self):
        """기존 공유 메모리 정리"""
        try:
            # Windows에서 공유 메모리 정리를 위한 더 강력한 방법
            for attempt in range(10):  # 더 많은 시도
                try:
                    temp_shm = shared_memory.SharedMemory(name=self.shm_name)
                    temp_shm.close()
                    temp_shm.unlink()
                    print(f"기존 공유 메모리 정리 완료: {self.shm_name} (시도 {attempt + 1})")
                    time.sleep(1.0)  # 더 긴 대기 시간
                    
                    # 정리 후 확인
                    try:
                        test_shm = shared_memory.SharedMemory(name=self.shm_name)
                        test_shm.close()
                        print(f"공유 메모리가 여전히 존재함: {self.shm_name}")
                        continue
                    except FileNotFoundError:
                        print(f"공유 메모리 정리 확인됨: {self.shm_name}")
                        break
                        
                except FileNotFoundError:
                    print(f"공유 메모리가 이미 정리됨: {self.shm_name}")
                    break
                except Exception as e:
                    print(f"공유 메모리 정리 시도 {attempt + 1} 실패: {e}")
                    if attempt < 9:
                        time.sleep(2.0)  # 더 긴 대기 시간
                    else:
                        print(f"공유 메모리 정리 실패, 강제로 계속 진행")
                        break
            
            # 최종 확인 및 강제 정리
            try:
                final_test = shared_memory.SharedMemory(name=self.shm_name)
                final_test.close()
                print(f"경고: 공유 메모리가 여전히 존재함: {self.shm_name}")
                print("강제로 계속 진행합니다...")
            except FileNotFoundError:
                print(f"공유 메모리 정리 최종 확인됨: {self.shm_name}")
                
        except Exception as e:
            print(f"기존 공유 메모리 정리 중 오류: {e}")
    
    def _initialize_slots(self):
        """슬롯 초기화"""
        print("모든 슬롯 초기화 중...")
        for slot in self.slots:
            # 슬롯 상태 초기화
            self._write_slot_status(slot, SlotStatus.EMPTY)
            
            # 슬롯 데이터 영역 완전 초기화
            data_start = slot.get_data_offset()
            data_end = data_start + slot.max_data_size
            
            # 모든 바이트를 0으로 초기화
            for i in range(data_start, data_end):
                self.shm.buf[i] = 0
            
            # 헤더 영역도 초기화
            # timestamp 초기화
            timestamp_start = slot.get_timestamp_offset()
            for i in range(timestamp_start, timestamp_start + 8):
                self.shm.buf[i] = 0
            
            # request_id 초기화
            request_id_start = slot.get_request_id_offset()
            for i in range(request_id_start, request_id_start + 32):
                self.shm.buf[i] = 0
            
            # data_length 초기화
            data_length_start = slot.get_data_length_offset()
            for i in range(data_length_start, data_length_start + 4):
                self.shm.buf[i] = 0
                
        print(f"{len(self.slots)}개 슬롯 초기화 완료")
    
    def _write_slot_status(self, slot: IPCSlot, status: int):
        """슬롯 상태 쓰기"""
        status_bytes = struct.pack('<I', status)
        self.shm.buf[slot.get_status_offset():slot.get_status_offset()+4] = status_bytes
    
    def _read_slot_status(self, slot: IPCSlot) -> int:
        """슬롯 상태 읽기"""
        status_bytes = bytes(self.shm.buf[slot.get_status_offset():slot.get_status_offset()+4])
        return struct.unpack('<I', status_bytes)[0]
    
    def _write_slot_data(self, slot: IPCSlot, data: Dict[str, Any]) -> bool:
        """슬롯에 데이터 쓰기"""
        try:
            json_str = json.dumps(data, ensure_ascii=False)
            json_bytes = json_str.encode('utf-8')
            
            if len(json_bytes) > slot.max_data_size:
                print(f"데이터가 너무 큽니다: {len(json_bytes)} bytes > {slot.max_data_size} bytes (슬롯 {slot.slot_id})")
                print(f"초과 크기: {len(json_bytes) - slot.max_data_size} bytes")
                print(f"현재 슬롯 크기: {slot.data_size} bytes, 헤더 크기: {slot.header_size} bytes")
                print(f"사용 가능한 데이터 크기: {slot.max_data_size} bytes")
                
                # 데이터 크기 정보 출력
                if 'text' in data:
                    text_size = len(data['text'].encode('utf-8'))
                    print(f"텍스트 크기: {text_size} bytes")
                    print(f"텍스트 길이: {len(data['text'])} 문자")
                
                return False
            
            # 헤더 정보 쓰기
            timestamp = int(time.time() * 1000)  # milliseconds
            request_id = data.get('request_id', 'unknown').ljust(32)[:32]
            
            # timestamp
            timestamp_bytes = struct.pack('<Q', timestamp)
            self.shm.buf[slot.get_timestamp_offset():slot.get_timestamp_offset()+8] = timestamp_bytes
            
            # request_id
            request_id_bytes = request_id.encode('utf-8')
            self.shm.buf[slot.get_request_id_offset():slot.get_request_id_offset()+32] = request_id_bytes
            
            # data length
            data_length_bytes = struct.pack('<I', len(json_bytes))
            self.shm.buf[slot.get_data_length_offset():slot.get_data_length_offset()+4] = data_length_bytes
            
            # data
            self.shm.buf[slot.get_data_offset():slot.get_data_offset()+len(json_bytes)] = json_bytes
            
            return True
        except Exception as e:
            print(f"슬롯 데이터 쓰기 오류: {e}")
            return False
    
    def _read_slot_data(self, slot: IPCSlot) -> Optional[Dict[str, Any]]:
        """슬롯에서 데이터 읽기"""
        try:
            # data length 읽기
            data_length_bytes = bytes(self.shm.buf[slot.get_data_length_offset():slot.get_data_length_offset()+4])
            data_length = struct.unpack('<I', data_length_bytes)[0]
            
            if data_length == 0 or data_length > slot.max_data_size:
                return None
            
            # data 읽기
            data_bytes = bytes(self.shm.buf[slot.get_data_offset():slot.get_data_offset()+data_length])
            
            # 데이터 유효성 검사
            if not data_bytes or len(data_bytes) == 0:
                print(f"빈 데이터 (슬롯 {slot.slot_id})")
                return None
            
            # 모든 바이트가 0인지 확인
            if all(b == 0 for b in data_bytes):
                print(f"모든 바이트가 0인 데이터 (슬롯 {slot.slot_id})")
                return None
            
            # 데이터 길이 로그
            print(f"슬롯 {slot.slot_id} 데이터 읽기: {len(data_bytes)} bytes")
            
            # UTF-8 디코딩 오류 방지 (더 강력한 처리)
            json_str = None
            try:
                # 먼저 정상적인 UTF-8 디코딩 시도
                json_str = data_bytes.decode('utf-8')
            except UnicodeDecodeError as e:
                print(f"UTF-8 디코딩 오류 (슬롯 {slot.slot_id}): {e}")
                print(f"문제 데이터(HEX): {data_bytes.hex()[:200]}...")  # 앞 200자만 출력
                print(f"문제 데이터 길이: {len(data_bytes)} bytes")
                print(f"문제 데이터(ASCII): {repr(data_bytes[:50])}...")  # 앞 50자만 ASCII로 출력
                
                # 방법 1: null 바이트 제거 후 재시도
                try:
                    cleaned_bytes = data_bytes.replace(b'\x00', b'')
                    if cleaned_bytes:
                        json_str = cleaned_bytes.decode('utf-8', errors='ignore')
                        print(f"null 바이트 제거 후 디코딩 성공 (슬롯 {slot.slot_id})")
                except:
                    pass
                
                # 방법 2: 방법 1이 실패하면 ignore 옵션으로 재시도
                if not json_str:
                    try:
                        json_str = data_bytes.decode('utf-8', errors='ignore')
                        print(f"ignore 옵션으로 디코딩 성공 (슬롯 {slot.slot_id})")
                    except:
                        pass
                
                # 방법 3: 마지막 수단으로 replace 옵션 사용
                if not json_str:
                    try:
                        json_str = data_bytes.decode('utf-8', errors='replace')
                        print(f"replace 옵션으로 디코딩 성공 (슬롯 {slot.slot_id})")
                    except:
                        print(f"모든 디코딩 방법 실패 (슬롯 {slot.slot_id})")
                        return None
            
            if not json_str:
                print(f"디코딩된 문자열이 없음 (슬롯 {slot.slot_id})")
                return None
            
            # JSON 파싱
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                print(f"JSON 파싱 오류 (슬롯 {slot.slot_id}): {e}")
                print(f"디코딩된 문자열: {json_str[:100]}...")  # 처음 100자만 출력
                return None
                
        except Exception as e:
            print(f"슬롯 데이터 읽기 오류 (슬롯 {slot.slot_id}): {e}")
            return None
    
    def find_empty_slot(self) -> Optional[IPCSlot]:
        """빈 슬롯 찾기"""
        if not self.lock.acquire(timeout=1.0):
            return None
        
        try:
            for slot in self.slots:
                if self._read_slot_status(slot) == SlotStatus.EMPTY:
                    return slot
            return None
        finally:
            self.lock.release()
    
    def find_request_slot(self) -> Optional[IPCSlot]:
        """요청 슬롯 찾기"""
        if not self.lock.acquire(timeout=1.0):
            return None
        
        try:
            for slot in self.slots:
                if self._read_slot_status(slot) == SlotStatus.REQUEST:
                    return slot
            return None
        finally:
            self.lock.release()
    
    def find_response_slot(self) -> Optional[IPCSlot]:
        """응답 슬롯 찾기"""
        if not self.lock.acquire(timeout=1.0):
            return None
        
        try:
            for slot in self.slots:
                if self._read_slot_status(slot) == SlotStatus.RESPONSE:
                    return slot
            return None
        finally:
            self.lock.release()
    
    def write_request(self, data: Dict[str, Any]) -> Optional[int]:
        """요청 쓰기"""
        slot = self.find_empty_slot()
        if not slot:
            return None
        
        if not self.lock.acquire(timeout=2.0):
            return None
        
        try:
            if self._write_slot_data(slot, data):
                self._write_slot_status(slot, SlotStatus.REQUEST)
                return slot.slot_id
            return None
        finally:
            self.lock.release()
    
    def read_request(self) -> Optional[tuple[int, Dict[str, Any]]]:
        """요청 읽기"""
        slot = self.find_request_slot()
        if not slot:
            return None
        
        if not self.lock.acquire(timeout=1.0):
            return None
        
        try:
            data = self._read_slot_data(slot)
            if data:
                self._write_slot_status(slot, SlotStatus.PROCESSING)
                return slot.slot_id, data
            return None
        finally:
            self.lock.release()
    
    def write_response(self, slot_id: int, data: Dict[str, Any]) -> bool:
        """응답 쓰기"""
        if slot_id >= len(self.slots):
            return False
        
        slot = self.slots[slot_id]
        
        if not self.lock.acquire(timeout=2.0):
            return False
        
        try:
            if self._write_slot_data(slot, data):
                self._write_slot_status(slot, SlotStatus.RESPONSE)
                return True
            return False
        finally:
            self.lock.release()
    
    def read_response(self, slot_id: int) -> Optional[Dict[str, Any]]:
        """응답 읽기"""
        if slot_id >= len(self.slots):
            return None
        
        slot = self.slots[slot_id]
        
        if not self.lock.acquire(timeout=1.0):
            return None
        
        try:
            if self._read_slot_status(slot) == SlotStatus.RESPONSE:
                data = self._read_slot_data(slot)
                if data:
                    self._write_slot_status(slot, SlotStatus.EMPTY)
                    return data
            return None
        finally:
            self.lock.release()
    
    def mark_slot_error(self, slot_id: int):
        """슬롯을 에러 상태로 표시"""
        if slot_id >= len(self.slots):
            return
        
        slot = self.slots[slot_id]
        if self.lock.acquire(timeout=1.0):
            try:
                self._write_slot_status(slot, SlotStatus.ERROR)
            finally:
                self.lock.release()
    
    def cleanup(self):
        """정리 작업"""
        if self.shm:
            try:
                self.shm.close()
                if not self.is_client:
                    self.shm.unlink()
                    print("공유 메모리 정리 완료")
                else:
                    print("공유 메모리 연결 해제 완료")
            except Exception as e:
                print(f"공유 메모리 정리 오류: {e}")
    
    def force_reset_all_slots(self):
        """모든 슬롯을 강제로 초기화"""
        print("모든 슬롯 강제 초기화 중...")
        for slot in self.slots:
            # 슬롯 상태 초기화
            self._write_slot_status(slot, SlotStatus.EMPTY)
            
            # 슬롯 데이터 영역 완전 초기화
            data_start = slot.get_data_offset()
            data_end = data_start + slot.max_data_size
            
            # 모든 바이트를 0으로 초기화
            for i in range(data_start, data_end):
                self.shm.buf[i] = 0
            
            # 헤더 영역도 초기화
            # timestamp 초기화
            timestamp_start = slot.get_timestamp_offset()
            for i in range(timestamp_start, timestamp_start + 8):
                self.shm.buf[i] = 0
            
            # request_id 초기화
            request_id_start = slot.get_request_id_offset()
            for i in range(request_id_start, request_id_start + 32):
                self.shm.buf[i] = 0
            
            # data_length 초기화
            data_length_start = slot.get_data_length_offset()
            for i in range(data_length_start, data_length_start + 4):
                self.shm.buf[i] = 0
                
        print(f"{len(self.slots)}개 슬롯 강제 초기화 완료")

class QueueManager:
    """큐 관리자"""
    
    def __init__(self):
        self.request_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self.running = True
    
    def put_request(self, slot_id: int, data: Dict[str, Any]):
        """요청 큐에 추가"""
        self.request_queue.put((slot_id, data))
    
    def get_request(self) -> Optional[tuple[int, Dict[str, Any]]]:
        """요청 큐에서 가져오기"""
        try:
            return self.request_queue.get(timeout=1.0)
        except queue.Empty:
            return None
    
    def put_response(self, slot_id: int, data: Dict[str, Any]):
        """응답 큐에 추가"""
        self.response_queue.put((slot_id, data))
    
    def get_response(self) -> Optional[tuple[int, Dict[str, Any]]]:
        """응답 큐에서 가져오기"""
        try:
            return self.response_queue.get(timeout=1.0)
        except queue.Empty:
            return None
    
    def stop(self):
        """중지"""
        self.running = False 