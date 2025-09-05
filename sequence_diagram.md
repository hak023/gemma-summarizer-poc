# 통화 요약 시스템 시퀀스 다이어그램

## 전체 시스템 시퀀스 다이어그램

```mermaid
sequenceDiagram
    participant Client as 클라이언트<br/>(외부 프로그램)
    participant IPC as IPC 서버<br/>(SLM Agent 프로그램)
    participant Preprocessor as 전처리기<br/>(SLM Agent 프로그램)
    participant Gemma as 믿음2.0 모델<br/>(SLM Agent 프로그램)
    participant Postprocessor as 후처리기<br/>(SLM Agent 프로그램)
    participant Logger as 로거<br/>(SLM Agent 프로그램)

    Note over Client,Logger: 1. 요청 시작
    Client->>IPC: STT 결과 데이터 전송
    Note right of Client: {transactionid, sequenceno, text}
    
    Note over IPC: 2. IPC 서버 처리
    IPC->>IPC: 요청 데이터 검증
    IPC->>Logger: 요청 로그 기록
    
    Note over Preprocessor: 3. 전처리 단계
    IPC->>Preprocessor: STT 데이터 전처리 요청
    Preprocessor->>Preprocessor: STT 결과 파싱 (sttResultList)
    Preprocessor->>Preprocessor: 화자 구분 (recType: 4=나, 2=상대방)
    Preprocessor->>Preprocessor: 중복 발화 제거
    Preprocessor->>Preprocessor: 텍스트 정리 (특수문자, 공백)
    Preprocessor->>Preprocessor: 대화 형태 변환
    Preprocessor->>IPC: 전처리된 대화 텍스트 반환
    
    Note over Gemma: 4. 믿음2.0 모델 요약
    IPC->>Gemma: 요약 요청
    Gemma->>Gemma: 모델 인스턴스 확인 (싱글톤)
    alt 모델이 로드되지 않은 경우
        Gemma->>Gemma: Llama 모델 초기화
        Gemma->>Gemma: 모델 로딩 (Midm-2.0-Mini-Instruct-Q4_K_M.gguf)
    end
    Gemma->>Gemma: 프롬프트 생성 (Few-shot 기법)
    Gemma->>Gemma: 모델 호출 (llama_cpp)
    Gemma->>Gemma: JSON 응답 파싱
    Gemma->>Gemma: 필드 검증 및 기본값 설정
    Gemma->>IPC: 원본 JSON 응답 반환
    
    Note over Postprocessor: 5. 후처리 단계
    IPC->>Postprocessor: 후처리 요청
    Postprocessor->>Postprocessor: summary 필드 처리 (길이 제한)
    Postprocessor->>Postprocessor: keyword 필드 처리 (형식 통일)
    Postprocessor->>Postprocessor: paragraphs 필드 처리
    Postprocessor->>Postprocessor: 각 paragraph의 summary 처리
    Postprocessor->>Postprocessor: 각 paragraph의 keyword 처리
    Postprocessor->>Postprocessor: 각 paragraph의 sentiment 처리
    Postprocessor->>Postprocessor: 재질의 로직 적용 (120byte 초과 시)
    Postprocessor->>Postprocessor: 동사 어미를 명사형으로 변환
    Postprocessor->>Postprocessor: 예시 내용 필터링
    Postprocessor->>IPC: 후처리된 JSON 반환
    
    Note over IPC: 6. 응답 생성
    IPC->>IPC: 최종 응답 데이터 구성
    IPC->>Logger: 응답 로그 기록
    IPC->>Client: 최종 응답 반환
    Note right of IPC: {transactionid, sequenceno, returncode, response}
```

## 멀티슬롯 IPC 시퀀스 다이어그램

```mermaid
sequenceDiagram
    participant Client1 as 클라이언트 1<br/>(외부 프로그램)
    participant Client2 as 클라이언트 2<br/>(외부 프로그램)
    participant Client3 as 클라이언트 3<br/>(외부 프로그램)
    participant IPC as 멀티슬롯 IPC 서버<br/>(SLM Agent 프로그램)
    participant Slot1 as 슬롯 1<br/>(SLM Agent 프로그램)
    participant Slot2 as 슬롯 2<br/>(SLM Agent 프로그램)
    participant Slot3 as 슬롯 3<br/>(SLM Agent 프로그램)
    participant Gemma as 믿음2.0 모델<br/>(SLM Agent 프로그램)

    Note over Client1,Gemma: 동시 요청 처리
    Client1->>IPC: 요청 1 전송
    Client2->>IPC: 요청 2 전송
    Client3->>IPC: 요청 3 전송
    
    IPC->>Slot1: 슬롯 1 할당 (요청 1)
    IPC->>Slot2: 슬롯 2 할당 (요청 2)
    IPC->>Slot3: 슬롯 3 할당 (요청 3)
    
    par 슬롯 1 처리
        Slot1->>Gemma: 요약 요청 1
        Gemma->>Slot1: 응답 1
        Slot1->>IPC: 결과 1 반환
    and 슬롯 2 처리
        Slot2->>Gemma: 요약 요청 2
        Gemma->>Slot2: 응답 2
        Slot2->>IPC: 결과 2 반환
    and 슬롯 3 처리
        Slot3->>Gemma: 요약 요청 3
        Gemma->>Slot3: 응답 3
        Slot3->>IPC: 결과 3 반환
    end
    
    IPC->>Client1: 응답 1 반환
    IPC->>Client2: 응답 2 반환
    IPC->>Client3: 응답 3 반환
```

## 에러 처리 시퀀스 다이어그램

```mermaid
sequenceDiagram
    participant Client as 클라이언트<br/>(외부 프로그램)
    participant IPC as IPC 서버<br/>(SLM Agent 프로그램)
    participant Gemma as 믿음2.0 모델<br/>(SLM Agent 프로그램)
    participant Postprocessor as 후처리기<br/>(SLM Agent 프로그램)

    Note over Client,Postprocessor: 정상 처리 경로
    Client->>IPC: 요청 전송
    IPC->>Gemma: 요약 요청
    Gemma->>IPC: JSON 응답
    IPC->>Postprocessor: 후처리 요청
    Postprocessor->>IPC: 후처리 완료
    IPC->>Client: 성공 응답

    Note over Client,Postprocessor: 에러 처리 경로들
    rect rgb(255, 200, 200)
        Note over Client,Postprocessor: 1. 모델 로딩 실패
        Client->>IPC: 요청 전송
        IPC->>Gemma: 요약 요청
        Gemma->>IPC: 모델 로딩 오류
        IPC->>Client: 기본 응답 반환
    end

    rect rgb(255, 220, 200)
        Note over Client,Postprocessor: 2. JSON 파싱 실패
        Client->>IPC: 요청 전송
        IPC->>Gemma: 요약 요청
        Gemma->>IPC: 잘못된 JSON 응답
        IPC->>Postprocessor: 후처리 요청
        Postprocessor->>Postprocessor: 정규식으로 필드 추출
        Postprocessor->>IPC: Fallback 응답
        IPC->>Client: 기본값 포함 응답
    end

    rect rgb(255, 240, 200)
        Note over Client,Postprocessor: 3. 빈 텍스트
        Client->>IPC: 빈 텍스트 요청
        IPC->>IPC: 입력 검증
        IPC->>Client: 오류 메시지 응답
    end

    rect rgb(200, 255, 200)
        Note over Client,Postprocessor: 4. 예시 내용 필터링
        Client->>IPC: 요청 전송
        IPC->>Gemma: 요약 요청
        Gemma->>IPC: 예시 내용 포함 응답
        IPC->>Postprocessor: 후처리 요청
        Postprocessor->>Postprocessor: 예시 내용 필터링
        Postprocessor->>IPC: 필터링된 응답
        IPC->>Client: 정상 응답
    end
```

## 상세 전처리 시퀀스 다이어그램

```mermaid
sequenceDiagram
    participant IPC as IPC 서버<br/>(SLM Agent 프로그램)
    participant Preprocessor as 전처리기<br/>(SLM Agent 프로그램)
    participant STTData as STT 데이터<br/>(SLM Agent 프로그램)

    Note over IPC,STTData: STT 결과 전처리 과정
    IPC->>Preprocessor: STT 데이터 전처리 요청
    Note right of IPC: {sttResultList: [{transcript, recType}, ...]}

    Preprocessor->>STTData: sttResultList 추출
    STTData->>Preprocessor: 원본 STT 데이터

    loop 각 STT 항목 처리
        Preprocessor->>Preprocessor: transcript 추출
        Preprocessor->>Preprocessor: recType 확인
        alt recType == 4
            Preprocessor->>Preprocessor: 화자 = "나"
        else recType == 2
            Preprocessor->>Preprocessor: 화자 = "상대방"
        else
            Preprocessor->>Preprocessor: 화자 = "화자{recType}"
        end
        Preprocessor->>Preprocessor: 텍스트 정리 (특수문자, 공백)
        Preprocessor->>Preprocessor: 대화 형태 변환 ("화자 > 텍스트")
    end

    Preprocessor->>Preprocessor: 중복 제거 처리
    loop 중복 제거 로직
        Preprocessor->>Preprocessor: 연속된 동일 발화 확인
        Preprocessor->>Preprocessor: 짧은 반복 발화 제거
        Preprocessor->>Preprocessor: 유사한 내용 병합
    end

    Preprocessor->>IPC: 전처리된 대화 텍스트 반환
    Note right of Preprocessor: "나 > 안녕하세요\n상대방 > 네, 안녕하세요\n..."
```

## 상세 후처리 시퀀스 다이어그램

```mermaid
sequenceDiagram
    participant IPC as IPC 서버<br/>(SLM Agent 프로그램)
    participant Postprocessor as 후처리기<br/>(SLM Agent 프로그램)
    participant Fields as 필드별 처리기<br/>(SLM Agent 프로그램)

    Note over IPC,Fields: 응답 후처리 과정
    IPC->>Postprocessor: 원본 JSON 응답 후처리 요청
    Note right of IPC: {summary, keyword, paragraphs}

    Note over Postprocessor: 필드별 순차 처리
    Postprocessor->>Fields: summary 필드 처리
    Fields->>Fields: 재질의 로직 (120byte 초과 시 [재질의 필요] 태그)
    Fields->>Fields: 동사 어미를 명사형으로 변환
    Fields->>Fields: 예시 내용 필터링
    Fields->>Postprocessor: 처리된 summary

    Postprocessor->>Fields: keyword 필드 처리
    Fields->>Fields: 쉼표로 분리
    Fields->>Fields: 중복 제거
    Fields->>Fields: 형식 통일
    Fields->>Postprocessor: 처리된 keyword

    Postprocessor->>Fields: paragraphs 필드 처리
    Fields->>Fields: 각 paragraph 순회
    loop 각 paragraph 처리
        Fields->>Fields: paragraph.summary 처리 (동사→명사 변환)
        Fields->>Fields: paragraph.keyword 처리 (형식 통일)
        Fields->>Fields: paragraph.sentiment 처리 (값 검증)
    end
    Fields->>Postprocessor: 처리된 paragraphs

    Postprocessor->>IPC: 최종 후처리된 JSON 반환
    Note right of Postprocessor: 모든 필드가 검증되고 정리된 JSON
```

## 시퀀스 다이어그램 설명

### 시스템 구성 요소 구분
- **외부 프로그램**: 클라이언트 - 요약 요청을 보내는 외부 애플리케이션
- **SLM Agent 프로그램**: 모든 내부 컴포넌트들
  - IPC 서버, 전처리기, 믿음2.0 모델, 후처리기, 로거
  - participant 라벨에 "(SLM Agent 프로그램)" 표시로 구분

### 1. 전체 시스템 시퀀스 다이어그램
- **6단계 처리**: 요청 시작 → IPC 서버 처리 → 전처리 → 믿음2.0 모델 → 후처리 → 응답 생성
- **각 컴포넌트의 역할**: 명확한 책임 분리와 데이터 흐름
- **로깅 시스템**: 요청/응답 로그 기록
- **시스템 경계**: 외부 클라이언트와 내부 프로그램 컴포넌트 명확 구분

### 2. 멀티슬롯 IPC 시퀀스 다이어그램
- **동시 처리**: 여러 클라이언트의 요청을 동시에 처리
- **슬롯 할당**: 각 요청을 별도 슬롯에 할당
- **병렬 처리**: 각 슬롯에서 독립적으로 요약 처리

### 3. 에러 처리 시퀀스 다이어그램
- **4가지 에러 시나리오**: 모델 로딩 실패, JSON 파싱 실패, 빈 텍스트, 예시 내용 필터링
- **Fallback 메커니즘**: 각 에러 상황별 대응 방안
- **색상 구분**: 에러 타입별 시각적 구분

### 4. 상세 전처리 시퀀스 다이어그램
- **STT 데이터 처리**: 원본 STT 결과를 대화 형태로 변환
- **화자 구분**: recType에 따른 화자 식별
- **중복 제거**: 다양한 중복 제거 로직

### 5. 상세 후처리 시퀀스 다이어그램
- **3개 필드 처리**: summary, keyword, paragraphs 필드별 전용 처리 로직
- **순차 처리**: 필드별 순서대로 처리
- **검증 및 정리**: 재질의 로직, 동사→명사 변환, 감정값 검증, 형식 통일

이 시퀀스 다이어그램들을 통해 통화 요약 시스템의 전체적인 데이터 흐름과 각 컴포넌트 간의 상호작용을 명확하게 이해할 수 있습니다. 