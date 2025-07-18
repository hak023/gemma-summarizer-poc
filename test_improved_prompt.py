#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from gemma_summarizer import summarize_with_gemma

def test_improved_prompt():
    """개선된 프롬프트 테스트"""
    
    # 테스트용 통화 내용
    test_conversation = """
    여보세요, 안녕하세요. 저는 ABC 회사의 김영수입니다.
    네, 안녕하세요. 저는 XYZ 회사에서 일하고 있는 박철수입니다.
    다름이 아니라, 지난주에 주문하신 제품 배송 관련해서 연락드렸습니다.
    아, 네. 언제 도착할 예정인가요?
    내일 오후 2시경에 도착할 예정입니다. 혹시 수령 가능하신가요?
    네, 가능합니다. 감사합니다.
    네, 그럼 내일 오후에 다시 한번 연락드리겠습니다.
    네, 알겠습니다. 수고하세요.
    네, 감사합니다. 안녕히 계세요.
    """
    
    print("=== 개선된 프롬프트 테스트 ===")
    print(f"테스트 통화 내용:\n{test_conversation.strip()}\n")
    
    try:
        # 요약 생성
        result = summarize_with_gemma(test_conversation)
        
        # JSON 파싱
        parsed_result = json.loads(result)
        
        print("=== 결과 ===")
        print(f"summary: {parsed_result.get('summary', 'N/A')}")
        print(f"summary_no_limit: {parsed_result.get('summary_no_limit', 'N/A')}")
        print(f"keywords: {parsed_result.get('keywords', 'N/A')}")
        print(f"call_purpose: {parsed_result.get('call_purpose', 'N/A')}")
        print(f"my_main_content: {parsed_result.get('my_main_content', 'N/A')}")
        print(f"caller_main_content: {parsed_result.get('caller_main_content', 'N/A')}")
        print(f"my_emotion: {parsed_result.get('my_emotion', 'N/A')}")
        print(f"caller_emotion: {parsed_result.get('caller_emotion', 'N/A')}")
        print(f"caller_info: {parsed_result.get('caller_info', 'N/A')}")
        print(f"my_action_after_call: {parsed_result.get('my_action_after_call', 'N/A')}")
        
        # 예시 내용이 포함되었는지 확인
        example_patterns = [
            "통화 핵심 요약",
            "전체 통화 상세 요약", 
            "키워드1,키워드2,키워드3,키워드4,키워드5",
            "통화 목적",
            "내 주요 발언 내용",
            "상대방 주요 발언 내용"
        ]
        
        print("\n=== 예시 내용 검사 ===")
        has_example_content = False
        for field, value in parsed_result.items():
            for pattern in example_patterns:
                if pattern in str(value):
                    print(f"⚠️  예시 내용 발견: {field} = '{value}' (패턴: {pattern})")
                    has_example_content = True
        
        if not has_example_content:
            print("✅ 예시 내용이 포함되지 않았습니다.")
        
        # 요약 길이 확인
        summary = parsed_result.get('summary', '')
        if len(summary) <= 30:
            print(f"✅ summary 길이 적절: {len(summary)}자")
        else:
            print(f"⚠️  summary 길이 초과: {len(summary)}자")
        
        return True
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_improved_prompt()
    if success:
        print("\n✅ 테스트 성공!")
    else:
        print("\n❌ 테스트 실패!") 