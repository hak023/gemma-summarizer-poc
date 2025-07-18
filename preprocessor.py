import json
import re
from typing import Dict, List, Any
from llm_utils import correct_conversation_with_gemma

class STTPreprocessor:
    """STT 결과를 대화 형태로 전처리하는 클래스"""
    
    @staticmethod
    def remove_duplicates(conversation_list: List[str]) -> List[str]:
        """
        중복되는 대화 내용을 제거
        
        Args:
            conversation_list (List[str]): 대화 리스트
            
        Returns:
            List[str]: 중복이 제거된 대화 리스트
        """
        if not conversation_list:
            return []
        
        cleaned_list = []
        prev_speaker = None
        prev_text = None
        
        for line in conversation_list:
            # 화자와 텍스트 분리
            if " > " in line:
                speaker, text = line.split(" > ", 1)
                text = text.strip()
            else:
                continue
            
            # 빈 텍스트 제거
            if not text:
                continue
            
            # 연속된 동일한 발화 제거
            if speaker == prev_speaker and text == prev_text:
                continue
            
            # 짧은 반복 발화 제거 (예: "네", "아", "음" 등이 연속으로 나오는 경우)
            if (speaker == prev_speaker and 
                len(text) <= 3 and 
                text in ["네", "아", "음", "어", "그", "응", "yes", "no", "ok"]):
                continue
            
            # 유사한 내용의 발화 병합 (부분 일치)
            if (speaker == prev_speaker and 
                prev_text and 
                (text in prev_text or prev_text in text)):
                # 더 긴 텍스트로 교체
                if len(text) > len(prev_text):
                    cleaned_list[-1] = f"{speaker} > {text}"
                continue
            
            cleaned_list.append(line)
            prev_speaker = speaker
            prev_text = text
        
        return cleaned_list
    
    @staticmethod
    def clean_text(text: str) -> str:
        """
        텍스트 정리 (특수문자, 불필요한 공백 등 제거)
        
        Args:
            text (str): 원본 텍스트
            
        Returns:
            str: 정리된 텍스트
        """
        # 불필요한 공백 제거
        text = re.sub(r'\s+', ' ', text.strip())
        
        # 특수문자 정리 (일부는 유지)
        text = re.sub(r'[^\w\s가-힣.,!?()\-:]', '', text)
        
        return text
    
    @staticmethod
    def preprocess_stt_result(data: Dict[str, Any]) -> str:
        """
        STT 결과를 대화 형태로 전처리
        
        Args:
            data (Dict[str, Any]): STT 결과 데이터
            
        Returns:
            str: 전처리된 대화 텍스트
        """
        try:
            # sttResultList 추출
            stt_result_list = data.get('sttResultList', [])
            
            if not stt_result_list:
                return "대화 내용이 없습니다."
            
            # 대화 텍스트 생성
            conversation = []
            
            for item in stt_result_list:
                transcript = item.get('transcript', '').strip()
                rec_type = item.get('recType', 0)
                
                if not transcript:
                    continue
                
                # 텍스트 정리
                transcript = STTPreprocessor.clean_text(transcript)
                
                if not transcript:
                    continue
                
                # recType에 따라 화자 구분
                if rec_type == 4:
                    speaker = "나"
                elif rec_type == 2:
                    speaker = "상대방"
                else:
                    speaker = f"화자{rec_type}"
                
                conversation.append(f"{speaker} > {transcript}")
            
            # 중복 제거
            conversation = STTPreprocessor.remove_duplicates(conversation)
            
            # 대화 텍스트 결합
            result = "\n".join(conversation)
            
            """임시로 주석처리하고 대화 내용 보정 안함"""
            # LLM을 사용한 대화 내용 보정
            #print("대화 내용 보정 시작...")
            #corrected_result = correct_conversation_with_gemma(result)
            corrected_result = result
            
            return corrected_result
            
        except Exception as e:
            print(f"전처리 중 오류 발생: {e}")
            return f"전처리 오류: {str(e)}"
    
    @staticmethod
    def extract_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        메타데이터 추출
        
        Args:
            data (Dict[str, Any]): 원본 데이터
            
        Returns:
            Dict[str, Any]: 추출된 메타데이터
        """
        metadata = {
            'cmd': data.get('cmd', ''),
            'token': data.get('token', ''),
            'reqNo': data.get('reqNo', ''),
            'svcKey': data.get('svcKey', ''),
            'custNb': data.get('custNb', ''),
            'callId': data.get('callId', ''),
            'callbackURL': data.get('callbackURL', ''),
            'total_segments': len(data.get('sttResultList', [])),
            'speakers': set()
        }
        
        # 화자 정보 추출
        for item in data.get('sttResultList', []):
            rec_type = item.get('recType', 0)
            metadata['speakers'].add(rec_type)
        
        metadata['speakers'] = list(metadata['speakers'])
        
        return metadata

def preprocess_request_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    요청 데이터를 전처리하여 새로운 형식으로 변환
    
    Args:
        data (Dict[str, Any]): 원본 요청 데이터
        
    Returns:
        Dict[str, Any]: 전처리된 데이터
    """
    try:
        # 메타데이터 추출
        metadata = STTPreprocessor.extract_metadata(data)
        
        # 대화 텍스트 전처리
        conversation_text = STTPreprocessor.preprocess_stt_result(data)
        
        # 새로운 형식으로 변환
        processed_data = {
            "type": "request",
            "text": conversation_text,
            "request_id": metadata['reqNo'],
            "metadata": metadata,
            "processed": False,
            "timestamp": None  # 나중에 설정
        }
        
        return processed_data
        
    except Exception as e:
        print(f"요청 데이터 전처리 중 오류: {e}")
        return {
            "type": "request",
            "text": f"전처리 오류: {str(e)}",
            "request_id": data.get('reqNo', 'unknown'),
            "metadata": {},
            "processed": False,
            "timestamp": None
        }

# 테스트 코드
if __name__ == "__main__":
    print("=== 중복 제거 테스트 ===")
    
    # 테스트용 대화 데이터 (중복 포함)
    test_conversation = [
        "나 > 안녕하세요",
        "상대방 > 네 안녕하세요",
        "나 > 안녕하세요",  # 중복
        "상대방 > 네",  # 짧은 반복
        "상대방 > 네",  # 연속 중복
        "나 > 오늘 날씨가 좋네요",
        "나 > 오늘 날씨가 정말 좋네요",  # 유사한 내용
        "상대방 > 네 맞습니다",
        "상대방 > 네 맞습니다",  # 완전 중복
        "나 > 그럼 이만",
        "나 > 그럼 이만",  # 중복
    ]
    
    print("원본 대화:")
    for line in test_conversation:
        print(f"  {line}")
    
    print("\n중복 제거 후:")
    cleaned = STTPreprocessor.remove_duplicates(test_conversation)
    for line in cleaned:
        print(f"  {line}")
    
    print(f"\n원본: {len(test_conversation)}개 → 정리 후: {len(cleaned)}개") 