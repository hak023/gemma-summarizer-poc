import json
from gemma_summarizer import summarize_with_gemma

def test_direct_summary():
    """직접 요약 함수 테스트"""
    
    # 샘플 텍스트 (sample_request_1.json에서 추출)
    sample_text = """
    네 부산지판 가족과 평생교육진흥원입니다
    예 예 안녕하세요 제가 이번에 평생그 옥수강 신사권이
    어 이게 저 해당이 돼서 지 인제 지급된다고 문자가 왔는데
    그 돈 어 제가 농협 카드가 있는데 신용 카드 있는데 신규로 또 발급해야 되나요
    어 어 선생님 그 혹시 갖고 계신 농협 카드에 체웅 카드라고 로고가 따로 적혀 있으실까요
    예 예 있습니다 그러고가 있어요
    네 저희 쪽에서 확인했을 때 새로 발급은 안 해주셔도 괜찮을 것 같아서
    예 근데 문자 내용 보니까 시 어 그래 있더라도 신규를 발급하라고 문자가 있더라고예
    어 어 그럼 제가 한번 요거를 확인해 봐야 될 거 같은데
    네 선생님 혹시 성함이 어떻게 되실까요
    김태희
    예 금혜 자 희 자 맞으세요
    3시 퇴희
    태희요
    네 그 생년월일이 어떻게 되실까요
    64 1127
    어 선생님 저희 쪽에 확인을 해 보니까 그 포인트 지급됐다고 확인이 되는데
    아 그래요
    네 요거 바로 사용 시작해 주시면 될 거 같애요
    예 그러면 어 35만 포인트가 지급된 거죠
    예 아 그러면 저 사용처가 어딘가예
    네 저희가 사용 기간이 지금 89 건 정도 돼서
    아 여기가 지금 기간이 지금 89 건 정도 돼서
    """
    
    print("=== 직접 요약 함수 테스트 ===")
    print(f"입력 텍스트 길이: {len(sample_text)} 문자")
    
    try:
        result = summarize_with_gemma(sample_text)
        print(f"\n=== 요약 결과 ===")
        print(result)
        
        # JSON 파싱 테스트
        try:
            parsed = json.loads(result)
            print(f"\n=== 파싱된 JSON ===")
            print(json.dumps(parsed, indent=2, ensure_ascii=False))
            
            # 필드 확인
            print(f"\n=== 필드 확인 ===")
            print(f"summary: {parsed.get('summary', '없음')}")
            print(f"keyword: {parsed.get('keyword', '없음')}")
            print(f"paragraphs: {len(parsed.get('paragraphs', []))}개")
            
            if 'paragraphs' in parsed and parsed['paragraphs']:
                for i, p in enumerate(parsed['paragraphs']):
                    print(f"  단락 {i+1}: {p}")
                    
        except json.JSONDecodeError as e:
            print(f"JSON 파싱 실패: {e}")
            print(f"원본 결과: {result}")
            
    except Exception as e:
        print(f"요약 함수 실행 오류: {e}")

if __name__ == "__main__":
    test_direct_summary() 