#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
압축 로직 직접 테스트
"""

from gemma_summarizer import compress_summary_with_keywords, extract_keywords_from_text

def test_compression_logic():
    """압축 로직을 직접 테스트합니다."""
    
    test_cases = [
        {
            "original": "고객이 바우처 카드 사용 문의를 하고 상담원이 상세히 답변했습니다.",
            "keywords": ["바우처", "카드", "사용", "문의", "상담"],
            "expected_max_length": 20
        },
        {
            "original": "지급문의 관련하여 상세한 안내를 제공했습니다.",
            "keywords": ["지급", "문의", "안내", "제공"],
            "expected_max_length": 20
        },
        {
            "original": "매우 긴 문장으로 20자를 초과하는 내용을 포함하고 있어서 자동으로 압축되어야 합니다.",
            "keywords": ["문장", "초과", "내용", "압축"],
            "expected_max_length": 20
        },
        {
            "original": "짧은 요약",
            "keywords": ["짧은", "요약"],
            "expected_max_length": 20
        }
    ]
    
    print("=== 압축 로직 직접 테스트 ===\n")
    
    for i, test_case in enumerate(test_cases, 1):
        original = test_case["original"]
        keywords = test_case["keywords"]
        max_length = test_case["expected_max_length"]
        
        print(f"테스트 {i}:")
        print(f"  원본: '{original}' ({len(original)}자)")
        print(f"  키워드: {keywords}")
        
        # 압축 실행
        compressed = compress_summary_with_keywords(original, keywords, max_length)
        
        print(f"  압축 결과: '{compressed}' ({len(compressed)}자)")
        print(f"  길이 제한 준수: {'✅' if len(compressed) <= max_length else '❌'}")
        print(f"  의미 보존: {'✅' if len(compressed) >= 4 else '❌'}")
        print()

if __name__ == "__main__":
    test_compression_logic() 