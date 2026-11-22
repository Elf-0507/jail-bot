# 제일봇

Flask 기반 마산제일고 학교생활 챗봇입니다. 말투는 app.py의 jeil_setting에서 관리합니다.
이 지침은 Gemini와 OpenAI 양쪽에 적용됩니다. ChatGPT 개인 계정의 대화 기억/맞춤 지침을 가져오지는 않습니다.

## Render 설정

- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app`
- Environment에서 환경 변수를 설정하고 **Save, rebuild, and deploy**를 선택합니다.

### OpenAI 사용

| 변수 | 값 |
| --- | --- |
| OPENAI_API_KEY | OpenAI API 플랫폼에서 발급한 비밀 키 |
| AI_PROVIDER | openai (선택 사항: OPENAI_API_KEY가 있으면 자동 선택) |
| OPENAI_MODEL | gpt-4.1-mini (선택 사항: 기본값) |

API 키: https://platform.openai.com/api-keys
ChatGPT 구독과 API는 별도 결제입니다. 키는 Render 환경 변수에만 입력하고 코드나 채팅에 공개하지 마세요.
기존 GOOGLE_API_KEY는 남겨도 됩니다. AI_PROVIDER=gemini를 명시하면 Gemini를 사용합니다.
선택한 제공자의 오류가 나도 다른 유료 제공자로 자동 전환하지 않습니다.

### 기존 Gemini 사용

OPENAI_API_KEY 없이 기존 GOOGLE_API_KEY만 있으면 Gemini를 사용합니다.
GEMINI_MODEL로 모델명을 바꿀 수 있고, 기본값은 기존 프로젝트의 gemini-3.1-flash-lite입니다.

## 기능 범위

- 마산제일고 마스코트 '제일콩'으로 소개하고 귀엽고 장난스러운 한국어 존댓말, 가끔 '질문자쿤' 호칭 사용
- 진지한 대화와 외부 제출용 문서는 상황에 맞는 문체 사용
- 이전 대화 기억과 학교 정보 실시간 조회는 아직 지원하지 않음
- 그림은 기존 Pollinations 서비스를 사용하며 OpenAI 이미지 생성으로 전환하지 않음
- API 연결 오류는 사용자에게 내부 오류 내용 대신 안내 메시지를 표시

## 참고 문서

- https://developers.openai.com/api/docs/quickstart
- https://developers.openai.com/api/docs/models/gpt-4.1-mini
- https://help.openai.com/en/articles/9039756-managing-billing-for-chatgpt-and-the-api-platform
- https://render.com/docs/configure-environment-variables

