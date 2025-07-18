import json
import re
from typing import Dict, Any, Optional

class ResponsePostprocessor:
    """Gemma 응답 데이터 후처리 클래스"""
    
    @staticmethod
    def process_call_purpose(value: str) -> str:
        """
        call_purpose 필드 후처리
        - 불필요한 공백 제거
        - 20자 제한 적용
        """
        if not value:
            return "통화 목적 미상"
        
        # 리스트인 경우 첫 번째 요소 사용
        if isinstance(value, list):
            if value:
                value = str(value[0])
            else:
                return "통화 목적 미상"
        
        # 문자열이 아니면 문자열로 변환
        value = str(value)
        
        # 불필요한 공백 제거
        cleaned = re.sub(r'\s+', ' ', value.strip())
        
        # 20자 제한 적용
        if len(cleaned) > 20:
            # 20자 이내로 자르기 (단어 단위로 자르기)
            words = cleaned.split()
            truncated = ""
            for word in words:
                if len(truncated + word) <= 20:
                    truncated += (word + " ")
                else:
                    break
            
            truncated = truncated.strip()
            return truncated
        
        return cleaned
    
    @staticmethod
    def process_summary(value: str) -> str:
        """
        summary 필드 후처리
        - 불필요한 공백 제거
        - 한 문장으로 강제 변환 (마침표, 느낌표, 물음표로 끝나도록)
        - 30자 제한 엄격 적용
        - 예시 내용 필터링
        - 여러 문장이 있을 경우 첫 번째 문장만 사용
        """
        if not value:
            return "통화 내용 요약 없음"
        
        # 리스트인 경우 첫 번째 요소 사용
        if isinstance(value, list):
            if value:
                value = str(value[0])
            else:
                return "통화 내용 요약 없음"
        
        # 문자열이 아니면 문자열로 변환
        value = str(value)
        
        # 예시 내용 필터링
        example_patterns = [
            r'알파 프로젝트.*광고 시안.*최종 선택',
            r'김민준 팀장.*이서연 대리',
            r'신제품 런칭.*캠페인',
            r'통화 핵심 요약.*30자',
            r'키워드1.*키워드5',
            r'통화 목적.*20자',
            r'나의 주요 발언 내용',
            r'상대방 주요 발언 내용',
            r'보통/만족/불만/화남/신남/우려',
            r'상대방 신상 정보.*빈 문자열',
            r'통화 후 할 일.*없음'
        ]
        
        for pattern in example_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return "통화 내용 요약 없음"
        
        # 공백 정리
        cleaned = re.sub(r'\s+', ' ', value.strip())
        
        # 여러 문장이 있는 경우 첫 번째 문장만 사용 (개선된 로직)
        # 마침표, 느낌표, 물음표로 문장을 분리
        sentence_endings = ['.', '!', '?']
        
        # 첫 번째 문장 끝 위치 찾기
        first_sentence_end = -1
        for ending in sentence_endings:
            pos = cleaned.find(ending)
            if pos != -1:
                if first_sentence_end == -1 or pos < first_sentence_end:
                    first_sentence_end = pos
        
        if first_sentence_end != -1:
            # 첫 번째 문장만 추출 (구두점 포함)
            first_sentence = cleaned[:first_sentence_end + 1].strip()
        else:
            # 문장 끝 구두점이 없으면 전체를 첫 번째 문장으로 처리
            first_sentence = cleaned
        
        if first_sentence:
            # 30자 이내인 경우 변경 없이 그대로 반환
            if len(first_sentence) <= 30:
                return first_sentence
            
            # 30자 초과인 경우에만 자르기
            words = first_sentence.split()
            truncated = ""
            
            for word in words:
                # 현재 단어를 추가했을 때의 길이 계산
                test_truncated = truncated + word
                if len(test_truncated) <= 30:
                    truncated = test_truncated + " "
                else:
                    break
            
            truncated = truncated.strip()
            
            # 원본 문장에 구두점이 없었으면 마침표를 추가하지 않음
            if truncated and not truncated.endswith(('.', '!', '?')) and first_sentence_end == -1:
                # 원본에 구두점이 없었던 경우 마침표 추가하지 않음
                pass
            elif truncated and not truncated.endswith(('.', '!', '?')):
                truncated += '.'
            
            return truncated
        
        # 빈 문자열이나 공백만 있는 경우
        if not cleaned or cleaned.strip() == "":
            return "통화 내용 요약 없음"
        
        return cleaned
    
    @staticmethod
    def process_summary_no_limit(value: str) -> str:
        """
        summary_no_limit 필드 후처리
        - 불필요한 공백 제거
        - 여러 문장 허용 (글자 제한 없음)
        - 예시 내용 필터링 강화
        """
        if not value:
            return "통화 내용 상세 요약 없음"
        
        # 리스트인 경우 첫 번째 요소 사용
        if isinstance(value, list):
            if value:
                value = str(value[0])
            else:
                return "통화 내용 상세 요약 없음"
        
        # 문자열이 아니면 문자열로 변환
        value = str(value)
        
        # 예시 내용 필터링 강화
        example_patterns = [
            r'알파 프로젝트.*광고 시안.*최종 선택',
            r'김민준 팀장.*이서연 대리',
            r'신제품 런칭.*캠페인',
            r'전체 통화 상세 요약',
            r'상세 요약',
            r'예시.*내용',
            r'샘플.*내용',
            r'핵심 요약',
            r'통화 목적',
            r'나의 발언',
            r'상대방 발언',
            r'신상 정보',
            r'할 일',
            r'키워드1.*키워드5',
            r'보통.*만족.*불만.*화남.*신남.*우려',
            r'핵심 요약',
            r'상세 요약',
            r'키워드',
            r'목적',
            r'내 발언',
            r'상대방 발언',
            r'감정',
            r'정보',
            r'할 일',
            r'통화 핵심 요약',
            r'전체 통화 상세 요약',
            r'내 주요 발언 내용',
            r'상대방 주요 발언 내용'
        ]
        
        for pattern in example_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return "통화 내용 상세 요약 없음"
        
        # 공백 정리
        cleaned = re.sub(r'\s+', ' ', value.strip())
        
        return cleaned
    
    @staticmethod
    def process_keywords(value: str) -> str:
        """
        keywords 필드 후처리
        - 쉼표로 구분된 키워드 정리
        - 중복 제거
        - 5개로 제한
        """
        if not value:
            return "키워드 없음"
        
        # 리스트인 경우 문자열로 변환
        if isinstance(value, list):
            keywords = [str(kw).strip() for kw in value if kw and str(kw).strip()]
        else:
            # 문자열인 경우 쉼표로 분리
            keywords = [kw.strip() for kw in str(value).split(',') if kw.strip()]
        
        # 중복 제거
        unique_keywords = list(dict.fromkeys(keywords))
        
        # 5개로 제한
        if len(unique_keywords) > 5:
            unique_keywords = unique_keywords[:5]
        
        return ', '.join(unique_keywords)
    
    @staticmethod
    def process_main_content(value: str) -> str:
        """
        my_main_content, caller_main_content 필드 후처리
        - 불필요한 공백 제거
        """
        if not value:
            return "내용 없음"
        
        # 공백 정리
        cleaned = re.sub(r'\s+', ' ', value.strip())
        
        return cleaned
    
    @staticmethod
    def process_emotion(value: str) -> str:
        """
        emotion 필드 후처리
        - 허용된 감정 상태로 정규화
        """
        allowed_emotions = ['보통', '만족', '불만', '화남', '신남', '우려']
        
        if not value:
            return "보통"
        
        # 정확히 일치하는 경우
        if value in allowed_emotions:
            return value
        
        # 유사한 감정 매핑
        emotion_mapping = {
            '평온': '보통',
            '기쁨': '만족',
            '행복': '만족',
            '즐거움': '만족',
            '불만족': '불만',
            '답답함': '불만',
            '우울': '우려',
            '슬픔': '우려',
            '걱정': '우려',
            '분노': '화남',
            '화가남': '화남',
            '흥미': '신남',
            '호기심': '신남',
            '신기함': '신남'
        }
        
        return emotion_mapping.get(value, '보통')
    
    @staticmethod
    def process_caller_info(value: str) -> str:
        """
        caller_info 필드 후처리
        - 빈 값 처리
        - 특수문자 정리
        - 예시 값이나 부적절한 값 필터링
        """
        if not value:
            return ""
        
        # 리스트인 경우 첫 번째 요소 사용
        if isinstance(value, list):
            if value:
                value = str(value[0])
            else:
                return ""
        
        # 문자열이 아니면 문자열로 변환
        value = str(value)
        
        if value.strip() == "":
            return ""
        
        # 예시 값이나 부적절한 값 필터링
        inappropriate_values = [
            "박영수", "김민수", "이철수", "홍길동", "김철수", "이영희", "박영희",
            "예시", "샘플", "테스트", "test", "example", "sample",
            "이름", "name", "고객", "customer", "사용자", "user"
        ]
        
        cleaned_value = value.strip()
        
        # 부적절한 값인지 확인
        for inappropriate in inappropriate_values:
            if inappropriate.lower() in cleaned_value.lower():
                return ""
        
        # 특수문자 정리 (이름에 적합하지 않은 문자 제거)
        cleaned = re.sub(r'[^\w\s가-힣]', '', cleaned_value)
        
        # 너무 짧거나 긴 이름 필터링 (1-10자)
        if len(cleaned) < 1 or len(cleaned) > 10:
            return ""
        
        return cleaned
    
    @staticmethod
    def process_action_after_call(value: str) -> str:
        """
        my_action_after_call 필드 후처리
        - 빈 값 처리
        - 불필요한 공백 제거
        """
        if not value:
            return "없음"
        
        # 리스트인 경우 첫 번째 요소 사용
        if isinstance(value, list):
            if value:
                value = str(value[0])
            else:
                return "없음"
        
        # 문자열이 아니면 문자열로 변환
        value = str(value)
        
        if value.strip() == "":
            return "없음"
        
        # 공백 정리
        cleaned = re.sub(r'\s+', ' ', value.strip())
        
        return cleaned
    
    @classmethod
    def process_response(cls, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        전체 응답 데이터 후처리
        
        Args:
            response_data (Dict[str, Any]): 원본 응답 데이터
            
        Returns:
            Dict[str, Any]: 후처리된 응답 데이터
        """
        try:
            # JSON 문자열인 경우 파싱
            if isinstance(response_data, str):
                response_data = json.loads(response_data)
            
            processed_data = {}
            
            # 각 필드별 후처리 적용
            field_processors = {
                'summary': cls.process_summary,
                'summary_no_limit': cls.process_summary_no_limit,
                'keywords': cls.process_keywords,
                'call_purpose': cls.process_call_purpose,
                'my_main_content': cls.process_main_content,
                'caller_main_content': cls.process_main_content,
                'my_emotion': cls.process_emotion,
                'caller_emotion': cls.process_emotion,
                'caller_info': cls.process_caller_info,
                'my_action_after_call': cls.process_action_after_call
            }
            
            for field, processor in field_processors.items():
                value = response_data.get(field, '')
                processed_data[field] = processor(value)
            
            return processed_data
            
        except Exception as e:
            print(f"후처리 중 오류 발생: {e}")
            # 오류 발생 시 원본 데이터 반환
            return response_data
    
    @classmethod
    def process_response_to_json(cls, response_data: Dict[str, Any]) -> str:
        """
        응답 데이터 후처리 후 JSON 문자열로 반환
        
        Args:
            response_data (Dict[str, Any]): 원본 응답 데이터
            
        Returns:
            str: 후처리된 JSON 문자열
        """
        processed_data = cls.process_response(response_data)
        return json.dumps(processed_data, ensure_ascii=False, indent=2)


# 테스트 코드
if __name__ == "__main__":
    print("=== 응답 후처리 테스트 ===")
    
    # 테스트용 응답 데이터
    test_response = {
        "summary": "고객이 바우처 카드 사용 문의를 하고 상담원이 상세히 답변했습니다.",
        "keywords": "바우처, 카드, 사용, 문의, 상담",
        "call_purpose": "바우처 카드 사용 가능 여부 확인",
        "my_main_content": "바우처 카드 사용 방법과 제한사항을 상세히 안내했습니다.",
        "caller_main_content": "바우처 카드 사용 가능 여부와 방법을 문의했습니다.",
        "my_emotion": "평온",
        "caller_emotion": "호기심",
        "caller_info": "김철수",
        "my_action_after_call": "문자로 상세 안내서 발송"
    }
    
    print("원본 데이터:")
    print(json.dumps(test_response, ensure_ascii=False, indent=2))
    
    print("\n후처리된 데이터:")
    processed = ResponsePostprocessor.process_response(test_response)
    print(json.dumps(processed, ensure_ascii=False, indent=2))
    
    print("\n=== 개별 필드 테스트 ===")
    print(f"call_purpose: '{test_response['call_purpose']}' -> '{ResponsePostprocessor.process_call_purpose(test_response['call_purpose'])}'")
    print(f"summary: '{test_response['summary']}' -> '{ResponsePostprocessor.process_summary(test_response['summary'])}'")
    print(f"emotion: '{test_response['my_emotion']}' -> '{ResponsePostprocessor.process_emotion(test_response['my_emotion'])}'") 