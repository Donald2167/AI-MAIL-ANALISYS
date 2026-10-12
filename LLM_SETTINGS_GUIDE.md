# 📧 LLM 설정 가이드

대시보드의 설정 항목에서 **LLM 제공자**, **API 키**, **모델명**을 설정하면, 자동으로 모든 모듈에서 사용됩니다.

## 🎯 설정 방법

### 1️⃣ 대시보드를 통한 설정 (권장)

```bash
cd 20260501/mail_reporter
streamlit run dashboard.py
```

대시보드 우측 사이드바에서:
1. **⚙️ 설정** 메뉴 선택
2. **🤖 LLM 설정** 섹션에서
   - **LLM 제공자** 선택 (openai, gemini, ollama)
   - **API 키** 입력
   - **모델명** 확인 후
3. **💾 저장** 버튼 클릭

설정은 `./data/llm_config.json`에 저장됩니다.

### 2️⃣ 환경 변수를 통한 설정 (선택사항)

대시보드 설정이 없으면 환경 변수를 확인합니다:

```bash
# OpenAI 사용
set LLM_PROVIDER=openai
set LLM_API_KEY=sk-...your-api-key...
set LLM_MODEL=gpt-4o-mini

# Google Gemini 사용
set LLM_PROVIDER=gemini
set LLM_API_KEY=your-gemini-api-key
set LLM_MODEL=gemini-2.5-flash

# Ollama (로컬) 사용
set LLM_PROVIDER=ollama
set OLLAMA_BASE_URL=http://localhost:11434
set LLM_MODEL=llama3
```

## 🔗 설정이 적용되는 모듈

| 모듈 | 기능 | 사용처 |
|------|------|-------|
| **dashboard.py** | LLM으로 재분류 | ⚙️ 설정 > 🔄 LLM으로 재분류 |
| **main.py** | CLI 명령어 | `python main.py import-eml --llm` |
| **mail_classifier.py** | 이메일 분류 | 키워드 대신 LLM으로 분류 |
| **mail_rag.py** | 질의응답 | `python main.py query` |
| **scheduler.py** | 스케줄된 작업 | 배치 처리 시 LLM 사용 |
| **summary_generator.py** | 보고서 생성 | LLM 기반 요약 |

## 🚀 각 모듈에서 사용하기

### 대시보드에서 재분류
```bash
streamlit run dashboard.py
# 설정 → LLM으로 재분류 → 🚀 LLM으로 재분류 시작
```

### CLI에서 LLM으로 분류
```bash
python main.py import-eml --llm
```

### 대화형 질의
```bash
python main.py query
# LLM이 설정되어 있으면 자동으로 사용됩니다
```

### 스케줄러 실행
```bash
python scheduler.py
# 저장된 LLM 설정으로 자동 실행
```

## 📝 설정 파일 위치

```
./data/llm_config.json
```

내용 예시:
```json
{
  "provider": "openai",
  "api_key": "sk-...",
  "model": "gpt-4o-mini"
}
```

## ✅ 설정 확인

대시보드 설정 페이지의 **"ℹ️ 상태 확인"** 버튼으로 현재 분류 현황을 확인할 수 있습니다.

## ⚠️ 주의사항

1. **API 키 보안**: API 키를 버전 관리에 포함시키지 마세요
2. **환경 변수 우선순위**: 환경 변수가 저장된 설정보다 우선합니다
3. **네트워크 연결**: Ollama를 제외한 OpenAI/Gemini는 인터넷 연결 필요
4. **API 비용**: OpenAI/Gemini 사용 시 API 비용 발생

## 🔄 설정 업데이트

저장된 설정을 변경하려면:
1. 대시보드의 **⚙️ 설정**에서 새 값 입력
2. **💾 저장** 클릭
3. 자동으로 `llm_config.json` 업데이트됨

## 🆘 문제 해결

### "LLM 클라이언트를 초기화할 수 없습니다" 오류
- API 키 확인
- 대시보드 설정에서 API 키 재입력
- 환경 변수가 설정되어 있으면 제거

### "OpenAI/Gemini API 오류"
- API 키 유효성 확인
- 네트워크 연결 확인
- API 한도 확인 (usage 페이지)

### Ollama 연결 실패
- Ollama 서버가 실행 중인지 확인: `curl http://localhost:11434`
- OLLAMA_BASE_URL 확인

---

설정이 완료되면, 모든 모듈에서 자동으로 LLM을 사용하여 더 정확한 분류와 분석이 가능합니다! 🎉
