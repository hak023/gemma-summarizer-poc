import json
from gemma_summarizer import summarize_with_gemma

def test_few_shot_prompt():
    """Few-shot 프롬프트 변경사항 테스트"""
    
    # 테스트용 대화 내용
    test_text = """나 > 안녕하세요, 부산여성가족과 평생교육진흥원입니다.
상대방 > 안녕하세요, 평생교육 이용권 신청 관련해서 문의드립니다.
나 > 네, 평생교육 이용권 신청 도와드리겠습니다. 어떤 이용권을 신청하고 싶으신가요?
상대방 > 5월 14일에 시작하는 요리 강좌 이용권을 신청하고 싶습니다.
나 > 네, 5월 14일 요리 강좌 이용권 신청을 도와드리겠습니다. 신청 방법을 안내해드릴게요.
상대방 > 감사합니다. 신청 방법을 알려주세요.
나 > 평생교육진흥원 홈페이지에서 온라인 신청이 가능하고, 전화 신청도 가능합니다.
상대방 > 알겠습니다. 홈페이지에서 신청하겠습니다. 감사합니다.
나 > 네, 신청하시고 궁금한 점 있으시면 언제든 연락주세요."""

    print("=== Few-shot 프롬프트 테스트 ===")
    print("테스트 대화 내용:")
    print(test_text)
    print("\n" + "="*50 + "\n")
    
    try:
        # 요약 수행
        result = summarize_with_gemma(test_text)
        
        # JSON 파싱
        if isinstance(result, str):
            parsed_result = json.loads(result)
        else:
            parsed_result = result
        
        print("=== 분석 결과 ===")
        print(f"summary: {parsed_result.get('summary', 'N/A')} ({len(parsed_result.get('summary', ''))}자)")
        print(f"call_purpose: {parsed_result.get('call_purpose', 'N/A')} ({len(parsed_result.get('call_purpose', ''))}자)")
        print(f"keyword: {parsed_result.get('keyword', 'N/A')}")
        print(f"my_emotion: {parsed_result.get('my_emotion', 'N/A')}")
        print(f"caller_emotion: {parsed_result.get('caller_emotion', 'N/A')}")
        print(f"caller_info: {parsed_result.get('caller_info', 'N/A')}")
        print(f"my_action_after_call: {parsed_result.get('my_action_after_call', 'N/A')}")
        
        print("\n=== 상세 내용 ===")
        print(f"summary_no_limit: {parsed_result.get('summary_no_limit', 'N/A')}")
        print(f"my_main_content: {parsed_result.get('my_main_content', 'N/A')}")
        print(f"caller_main_content: {parsed_result.get('caller_main_content', 'N/A')}")
        
        # 글자 수 제한 확인
        print("\n=== 글자 수 제한 확인 ===")
        summary_length = len(parsed_result.get('summary', ''))
        call_purpose_length = len(parsed_result.get('call_purpose', ''))
        
        print(f"summary: {summary_length}자 (제한: 20자) - {'✅ 통과' if summary_length <= 20 else '❌ 초과'}")
        print(f"call_purpose: {call_purpose_length}자 (제한: 20자) - {'✅ 통과' if call_purpose_length <= 20 else '❌ 초과'}")
        
        # 예시 값 복사 여부 확인
        print("\n=== 예시 값 복사 여부 확인 ===")
        example_values = ["알파 프로젝트", "김민준 팀장", "이서연 대리", "SNS 광고"]
        found_example = False
        
        for example in example_values:
            if example in str(parsed_result):
                print(f"❌ 예시 값 발견: {example}")
                found_example = True
        
        if not found_example:
            print("✅ 예시 값이 복사되지 않음")
        
    except Exception as e:
        print(f"테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_few_shot_prompt() 