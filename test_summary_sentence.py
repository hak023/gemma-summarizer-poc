#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
summary 필드 문장 처리 테스트
"""

from postprocessor import ResponsePostprocessor

def test_summary_sentence_processing():
    """summary 필드의 문장 처리 로직을 테스트합니다."""
    
    test_cases = [
        # 테스트 케이스: (입력, 기대 출력)
        ("안녕하세요. 오늘 날씨가 좋네요.", "안녕하세요."),
        ("통화 내용 요약입니다! 상세 내용은 별도로 확인하세요.", "통화 내용 요약입니다!"),
        ("프로젝트 진행 상황을 확인했습니다? 다음 단계로 진행하겠습니다.", "프로젝트 진행 상황을 확인했습니다?"),
        ("단일 문장입니다", "단일 문장입니다"),
        ("첫 번째 문장. 두 번째 문장. 세 번째 문장.", "첫 번째 문장."),
        ("긴 문장이지만 마침표가 없는 경우 전체가 하나의 문장으로 처리됩니다", "긴 문장이지만 마침표가 없는 경우 전체가 하나의"),
        ("짧은 문장.", "짧은 문장."),
        ("", "통화 내용 요약 없음"),
        ("   ", "통화 내용 요약 없음"),
        ("알파 프로젝트 광고 시안 최종 선택", "통화 내용 요약 없음"),  # 예시 내용 필터링
    ]
    
    print("=== Summary 필드 문장 처리 테스트 ===\n")
    
    for i, (input_text, expected) in enumerate(test_cases, 1):
        result = ResponsePostprocessor.process_summary(input_text)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        
        print(f"테스트 {i}: {status}")
        print(f"  입력: '{input_text}'")
        print(f"  기대: '{expected}'")
        print(f"  결과: '{result}'")
        print(f"  길이: {len(result)}자")
        print()

def test_summary_length_limit():
    """summary 필드의 길이 제한을 테스트합니다."""
    
    long_sentence = "이것은 매우 긴 문장으로 20자를 초과하는 내용을 포함하고 있어서 자동으로 잘려야 합니다."
    
    print("=== Summary 필드 길이 제한 테스트 ===\n")
    
    result = ResponsePostprocessor.process_summary(long_sentence)
    print(f"입력: '{long_sentence}'")
    print(f"길이: {len(long_sentence)}자")
    print(f"결과: '{result}'")
    print(f"길이: {len(result)}자")
    print(f"20자 제한 준수: {'✅' if len(result) <= 20 else '❌'}")

if __name__ == "__main__":
    test_summary_sentence_processing()
    print("\n" + "="*50 + "\n")
    test_summary_length_limit() 