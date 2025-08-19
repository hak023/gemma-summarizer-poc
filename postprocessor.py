import json
import re
from typing import Dict, Any, Optional

class ResponsePostprocessor:
    """Gemma 응답 데이터 후처리 클래스"""
    
    @staticmethod
    def select_best_sentence(sentences: list) -> str:
        """
        여러 문장 중에서 가장 적합한 문장을 선택
        가중치 기준: 길이, 핵심 키워드 포함 여부, 명확성
        """
        if not sentences:
            return ""
        
        if len(sentences) == 1:
            return sentences[0]
        
        # 각 문장의 점수 계산
        sentence_scores = []
        for sentence in sentences:
            score = 0
            
            # 1. 길이 점수 (너무 짧거나 긴 것 제외)
            length = len(sentence.strip())
            if 10 <= length <= 50:
                score += 3
            elif 5 <= length <= 80:
                score += 2
            else:
                score += 1
            
            # 2. 핵심 키워드 포함 점수
            keywords = ['문의', '답변', '안내', '설명', '처리', '해결', '확인', '검토', '분석']
            for keyword in keywords:
                if keyword in sentence:
                    score += 2
                    break
            
            # 3. 명확성 점수 (구체적인 동사 포함)
            action_words = ['문의', '답변', '안내', '설명', '처리', '해결', '확인', '검토', '분석', '제공', '발급', '이용']
            for word in action_words:
                if word in sentence:
                    score += 1
            
            # 4. 부정적 표현 제외
            negative_words = ['불가능', '불가', '오류', '오류', '실패', '실패', '문제', '문제']
            for word in negative_words:
                if word in sentence:
                    score -= 1
            
            sentence_scores.append((sentence, score))
        
        # 가장 높은 점수의 문장 선택
        best_sentence = max(sentence_scores, key=lambda x: x[1])
        return best_sentence[0]
    
    @staticmethod
    def extract_first_sentence(text: str) -> str:
        """
        입력 텍스트에서 첫 번째 문장만 추출하여 반환
        - 한국어/영문 공통 문장 종결부호(. ! ?) 및 유사 기호(。 ！ ？) 기준
        - 종결부호가 없으면 전체를 반환
        """
        if not text:
            return ""
        text = text.strip()
        match = re.search(r'^(.+?[\.!?。！？])', text)
        if match:
            return match.group(1).strip()
        return text
    
    @staticmethod
    def process_summary(value: str) -> str:
        """
        summary 필드 후처리
        - 예시 내용 필터링
        - 80 byte 초과 시 재질의 필요 표시
        - 불필요한 공백 제거
        """
        if not value:
            return "요약이 불가능한 내용입니다."
        
        # 문자열이 아니면 문자열로 변환
        if not isinstance(value, str):
            value = str(value)
        
        # 이미 [재질의 필요] 표시가 있으면 그대로 반환
        if value.startswith('[재질의 필요]'):
            return value
        
        # 예시 내용 필터링
        example_patterns = [
            r'예시.*내용',
            r'샘플.*내용',
            r'테스트.*내용',
            r'출력.*예시',
            r'분석.*규칙',
            r'출력.*형식',
            r'```json',
            r'```',
            r'JSON.*형식',
            r'다음.*형식'
        ]
        
        is_example = False
        for pattern in example_patterns:
            if re.search(pattern, value, re.IGNORECASE):
                is_example = True
                break
        
        if is_example:
            return "요약 없음"
        
        # 불필요한 공백 제거
        cleaned = re.sub(r'\s+', ' ', value.strip())
        
        # 60 byte 초과 시 재질의 필요 표시
        if len(cleaned.encode('utf-8')) > 80:
            return f"[재질의 필요] {cleaned}"
        
        return cleaned
    
    @staticmethod
    def process_keywords(value: str) -> str:
        """
        keyword 필드 후처리
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
        - paragraphs의 summary는 재질의 로직 제외
        - paragraphs의 summary는 최고 문장(select_best_sentence)만 사용
        """
        if not paragraphs or not isinstance(paragraphs, list):
            return []
        
        processed_paragraphs = []
        
        for paragraph in paragraphs:
            if not isinstance(paragraph, dict):
                continue
                
            processed_para = {}
            
            # summary 처리 (paragraphs의 summary는 재질의 로직 제외)
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
                
                cleaned_summary = re.sub(r'\s+', ' ', summary.strip())
                # 문장 분리 후 최고 문장 선택
                sentences = [s.strip() for s in re.split(r'(?<=[\.!?。！？])\s+', cleaned_summary) if s.strip()]
                if not sentences:
                    sentences = [cleaned_summary]
                best_sentence = ResponsePostprocessor.select_best_sentence(sentences)
                processed_para['summary'] = best_sentence
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
                            'summary': '요약이 불가능한 내용입니다.'
                        }
                    ]
                
                processed_data['paragraphs'] = cls.process_paragraphs(paragraphs)
                
                return processed_data
            
            # 기존 구조가 아닌 경우 기본값 반환
            print(f"현재 구조가 아닌 응답 데이터: {list(response_data.keys())}")
            return {
                'summary': '통화 내용 요약 없음',
                'keyword': '키워드 없음',
                'paragraphs': []
            }
            
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
    
    print("\n=== 60 byte 초과 테스트 ===")
    long_summary = "고객이 바우처 카드 사용법에 대해 매우 상세하게 문의를 했고, 상담원이 모든 절차를 자세히 설명해드렸으며, 고객이 완전히 만족스러워했습니다."
    print(f"긴 요약: '{long_summary}'")
    print(f"처리 결과: '{ResponsePostprocessor.process_summary(long_summary)}'")
    print(f"바이트 길이: {len(long_summary.encode('utf-8'))}")
    
    print("\n=== 다중 문장 가중치 비교 테스트 ===")
    multi_sentence_tests = [
        "고객이 바우처 카드 사용법을 문의했습니다. 상담원이 상세히 답변했습니다. 고객이 만족했습니다.",
        "시스템 점검 중입니다. 서비스가 일시 중단되었습니다. 빠른 복구를 위해 노력하고 있습니다.",
        "바우처 카드 발급 절차를 안내했습니다. 고객이 이해했습니다. 추가 문의사항이 없었습니다.",
        "고객이 불만을 제기했습니다. 상담원이 사과했습니다. 문제를 해결했습니다."
    ]
    
    print("\n=== 다중 문장 처리 테스트 ===")
    for text in multi_sentence_tests:
        result = ResponsePostprocessor.process_summary(text)
        print(f"원본: '{text}'")
        print(f"선택된 문장: '{result}'")
        print("---") 