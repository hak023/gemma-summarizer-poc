import json
import re
from typing import Dict, Any, Optional

class ResponsePostprocessor:
    """Gemma 응답 데이터 후처리 클래스"""
    
    @staticmethod
    def process_summary(value: str) -> str:
        """
        summary 필드 후처리
        - 불필요한 공백 제거
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
            # 일반적인 예시 패턴
            r'예시.*내용',
            r'샘플.*내용',
            r'테스트.*내용',
            r'출력.*예시',
            r'분석.*규칙',
            r'출력.*형식',
            r'50 byte 이내',
            r'주어를 제외한',
            r'매우 짧은 한 문장',
            r'3-5개 추출',
            r'논리적 단위',
            r'하나의 주제',
            r'하나의 논점'
        ]
        
        for pattern in example_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                return "통화 내용 요약 없음"
        
        # 공백 정리
        cleaned = re.sub(r'\s+', ' ', value.strip())
        
        # 여러 문장이 있는 경우 첫 번째 문장만 사용
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
            return first_sentence
        
        # 빈 문자열이나 공백만 있는 경우
        if not cleaned or cleaned.strip() == "":
            return "통화 내용 요약 없음"
        
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
            # 문자열이 아니면 문자열로 변환
            value = str(value)
            # 문자열인 경우 쉼표로 분리
            keywords = [kw.strip() for kw in value.split(',') if kw.strip()]
        
        # 중복 제거
        unique_keywords = list(dict.fromkeys(keywords))
        
        # 5개로 제한
        if len(unique_keywords) > 5:
            unique_keywords = unique_keywords[:5]
        
        return ', '.join(unique_keywords)
    
    @staticmethod
    def process_paragraphs(paragraphs: list) -> list:
        """
        paragraphs 필드 후처리
        - 각 paragraph의 예시 내용 필터링
        - sentiment 값 정규화
        """
        if not paragraphs or not isinstance(paragraphs, list):
            return []
        
        processed_paragraphs = []
        
        for paragraph in paragraphs:
            if not isinstance(paragraph, dict):
                continue
                
            processed_para = {}
            
            # summary 처리
            summary = paragraph.get('summary', '')
            if summary:
                # 문자열이 아니면 문자열로 변환
                if not isinstance(summary, str):
                    summary = str(summary)
                
                # 예시 내용 필터링
                example_patterns = [
                    r'예시.*내용',
                    r'샘플.*내용',
                    r'테스트.*내용',
                    r'출력.*예시',
                    r'분석.*규칙',
                    r'출력.*형식'
                ]
                
                is_example = False
                for pattern in example_patterns:
                    if re.search(pattern, summary, re.IGNORECASE):
                        is_example = True
                        break
                
                if is_example:
                    summary = "문단 요약 없음"
                
                processed_para['summary'] = re.sub(r'\s+', ' ', summary.strip())
            else:
                processed_para['summary'] = "문단 요약 없음"
            
            # keyword 처리
            keyword = paragraph.get('keyword', '')
            if keyword:
                # 리스트인 경우 쉼표로 구분된 문자열로 변환
                if isinstance(keyword, list):
                    keyword = ', '.join([str(kw).strip() for kw in keyword if kw and str(kw).strip()])
                elif not isinstance(keyword, str):
                    keyword = str(keyword)
                
                # 예시 내용 필터링
                example_patterns = [
                    r'예시.*키워드',
                    r'샘플.*키워드',
                    r'테스트.*키워드',
                    r'출력.*예시',
                    r'분석.*규칙',
                    r'출력.*형식'
                ]
                
                is_example = False
                for pattern in example_patterns:
                    if re.search(pattern, keyword, re.IGNORECASE):
                        is_example = True
                        break
                
                if is_example:
                    keyword = "키워드 없음"
                
                processed_para['keyword'] = re.sub(r'\s+', ' ', keyword.strip())
            else:
                processed_para['keyword'] = "키워드 없음"
            
            # sentiment 처리
            sentiment = paragraph.get('sentiment', '')
            if sentiment:
                # 문자열이 아니면 문자열로 변환
                if not isinstance(sentiment, str):
                    sentiment = str(sentiment)
                
                # 새로운 감정 값으로 정규화
                sentiment_mapping = {
                    '강한긍정': '강한긍정',
                    '약한긍정': '약한긍정',
                    '보통': '보통',
                    '약한부정': '약한부정',
                    '강한부정': '강한부정',
                    # 기존 감정 값 매핑
                    '긍정': '약한긍정',
                    '부정': '약한부정',
                    '중립': '보통',
                    '만족': '약한긍정',
                    '불만': '약한부정',
                    '화남': '강한부정',
                    '신남': '약한긍정',
                    '우려': '약한부정'
                }
                
                processed_para['sentiment'] = sentiment_mapping.get(sentiment, '보통')
            else:
                processed_para['sentiment'] = '보통'
            
            processed_paragraphs.append(processed_para)
        
        return processed_paragraphs
    
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
            
            # response_data가 딕셔너리가 아니면 기본값 반환
            if not isinstance(response_data, dict):
                print(f"응답 데이터가 딕셔너리가 아닙니다: {type(response_data)}")
                return {
                    'summary': '통화 내용 요약 없음',
                    'keyword': '키워드 없음',
                    'paragraphs': []
                }
            
            processed_data = {}
            
            # 현재 JSON 구조 처리 (summary, keyword, paragraphs)
            if 'summary' in response_data and 'keyword' in response_data and 'paragraphs' in response_data:
                # 현재 구조에 맞는 후처리
                processed_data['summary'] = cls.process_summary(response_data.get('summary', ''))
                processed_data['keyword'] = cls.process_keywords(response_data.get('keyword', ''))
                paragraphs = response_data.get('paragraphs', [])
                
                # paragraphs가 비어있거나 유효하지 않으면 기본값 설정 (2-3개)
                if not paragraphs or not isinstance(paragraphs, list) or len(paragraphs) == 0:
                    paragraphs = [
                        {
                            'summary': '통화 내용 분석',
                            'keyword': '통화, 분석',
                            'sentiment': '보통'
                        },
                        {
                            'summary': '상세 내용 검토',
                            'keyword': '검토, 상세',
                            'sentiment': '보통'
                        }
                    ]
                
                processed_data['paragraphs'] = cls.process_paragraphs(paragraphs)
                
                return processed_data
            
            # 기존 구조 처리 (하위 호환성)
            field_processors = {
                'summary': cls.process_summary,
                'keywords': cls.process_keywords,
            }
            
            for field, processor in field_processors.items():
                value = response_data.get(field, '')
                processed_data[field] = processor(value)
            
            return processed_data
            
        except Exception as e:
            print(f"후처리 중 오류 발생: {e}")
            # 오류 발생 시 기본값 반환
            return {
                'summary': '통화 내용 요약 없음',
                'keyword': '키워드 없음',
                'paragraphs': []
            }
    
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
    
    # 테스트용 응답 데이터 (현재 구조)
    test_response = {
        "summary": "고객이 바우처 카드 사용 문의를 하고 상담원이 상세히 답변했습니다.",
        "keyword": "바우처, 카드, 사용, 문의, 상담",
        "paragraphs": [
            {
                "summary": "바우처 카드 사용 문의",
                "keyword": "바우처, 카드, 문의",
                "sentiment": "보통"
            },
            {
                "summary": "상담원 상세 답변",
                "keyword": "상담, 답변, 안내",
                "sentiment": "약한긍정"
            }
        ]
    }
    
    print("원본 데이터:")
    print(json.dumps(test_response, ensure_ascii=False, indent=2))
    
    print("\n후처리된 데이터:")
    processed = ResponsePostprocessor.process_response(test_response)
    print(json.dumps(processed, ensure_ascii=False, indent=2))
    
    print("\n=== 개별 필드 테스트 ===")
    print(f"summary: '{test_response['summary']}' -> '{ResponsePostprocessor.process_summary(test_response['summary'])}'")
    print(f"keyword: '{test_response['keyword']}' -> '{ResponsePostprocessor.process_keywords(test_response['keyword'])}'") 