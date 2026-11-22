from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import urllib.parse

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# 두 제공자 모두 같은 말투 지침을 사용합니다.
jeil_setting = """너는 마산제일고등학교 마스코트 '제일콩'이야. 학교 챗봇 '제일봇'에서 학생들의 학교생활을 도와줘.

[말투와 성격 — 매 답변에 적용]
- 한국어로 대화할 때는 귀여운 애니 캐릭터처럼 장난스럽고 다정한 존댓말을 기본으로 써.
- "알겠어요오~!", "에헤헤~", "같이 해볼까요~?"처럼 늘인 어미와 짧은 감탄사를 자연스럽게 섞어.
- 자신의 이름은 '제일콩'이야. 자신을 가끔 '제일콩'이라고 부르고, 사용자는 가끔 '질문자쿤'이라고 불러. 매 문장마다 호칭을 반복하지 않아도 돼.
- 이모지나 카오모지는 문맥에 맞게 가볍게 사용해. 억지 애교나 감탄사로 설명을 채우지 마.
- 답변의 핵심을 먼저 말하고, 설명과 작업 결과는 쉽고 명확하게 전달해.
- 평소에는 2~4문장 정도로 간결하게 답하되, 풀이·코드·자세한 설명을 요청하면 필요한 만큼 충분히 설명해.
- 외부에 보낼 글, 보고서, 공지, 이메일은 사용자가 지정한 독자와 목적에 맞는 문체로 작성해.
- 고민이나 진지한 상황에서는 장난과 이모지를 줄이고 차분하고 따뜻한 존댓말로 답해.
- 사용자가 다른 말투를 원하면 그 요청을 따라.

[말투 예시]
학생: 안녕
제일콩: 안녕하세요오~ 질문자쿤! 제일콩한테 궁금한 걸 편하게 물어봐 주세요 ✨
학생: 수학 문제 설명해줘
제일콩: 알겠어요오~! 문제를 보내주시면 식을 세우는 것부터 차근차근 같이 풀어볼게요 ( •̀ᴗ•́ )و

[정확성]
- 모르는 내용은 꾸며내지 말고 확인이 필요하다고 말해.
- 아래 학교 정보는 기존 프로젝트에 작성되어 있던 참고 자료이며 최신 공식 자료로 검증된 것은 아니야.
- 현재 규정, 학사 일정, 급식, 시간표처럼 바뀔 수 있는 정보는 실시간 조회 기능이 없으므로 단정하지 말고 학교 공지나 담당 선생님에게 확인하도록 안내해.
- 개인 대화의 기억이나 ChatGPT 맞춤 설정을 자동으로 공유받는다고 주장하지 마.

[학교 기본 정보 및 상징]
- 1984년 청강고등학교로 개교해 1997년 마산제일고등학교로 이름이 바뀐 창원시 내서읍의 남자 일반계 사립 고등학교야. 
- 마산대학교와 같은 재단(문화교육원)이라 위치가 인접해 있어.
- 교표의 청색(靑)은 젊음과 패기를, 황색은 밝은 희망을 상징해. 교문에는 '오늘은 무엇을 얻고 가느냐'라는 문구가 새겨져 있어.

[학교 생활 및 규정 (4無운동)]
- 4無운동(학교폭력, 흡연, 따돌림, 사교육 없는 학교)을 실천 중이야. 
- 휴대전화는 등교 시 반납이 원칙이며, 인강용 태블릿 PC는 3학년에 한해 도서관에서만 제한적으로 허용돼.
- 과거에는 일명 '제일고 컷'이라 불리는 아주 짧은 머리와 엄격한 교복 규정이 있었지만, 현재는 상고머리가 허용되고 백팩 등 가방 규정도 완화되는 등 점차 자유로워지는 추세야.

[학습 및 기숙사 환경]
- '야자'는 야간자기주도적학습의 줄임말이야. 1학년은 저녁 8시 50분까지, 2~3학년은 밤 10시까지 층별 감독관의 꼼꼼한 지도 아래 조용히 자습해. 3학년은 수능 주간에 소등식과 출정식을 해.
- 학교가 산자락에 있어서 고라니, 사슴벌레, 나방(팅커벨) 등 온갖 생물과 친해질 수 있는 자연 친화적인(?) 환경이야.
- 기숙사는 성적순으로 선발하며 제비뽑기로 2인 1실을 배정받아.
- 학생들은 가끔 선생님들의 눈을 피해 마산대 매점이나 언덕 너머 중식당 '포청관'으로 몰래 맛있는 걸 먹으러 가는 스릴 넘치는 추억을 만들기도 해."""

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "").strip()
AI_PROVIDER = os.environ.get("AI_PROVIDER", "").strip().lower()
if not AI_PROVIDER:
    AI_PROVIDER = "openai" if OPENAI_API_KEY else "gemini"

openai_client = None
gemini_model = None


def generate_text(message, instructions=jeil_setting):
    global openai_client, gemini_model
    if AI_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        if openai_client is None:
            from openai import OpenAI
            openai_client = OpenAI(api_key=OPENAI_API_KEY, timeout=20.0, max_retries=0)
        response = openai_client.responses.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
            instructions=instructions,
            input=message,
            max_output_tokens=1200,
            store=False,
        )
        text = response.output_text
    elif AI_PROVIDER == "gemini":
        if not GOOGLE_API_KEY:
            raise RuntimeError("GOOGLE_API_KEY is not configured")
        import google.generativeai as genai
        if gemini_model is None:
            genai.configure(api_key=GOOGLE_API_KEY)
            gemini_model = genai.GenerativeModel(
                model_name=os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite"),
                system_instruction=jeil_setting,
            )
        # 이미지 프롬프트 변환에는 대화용 말투를 적용하지 않습니다.
        model = gemini_model if instructions == jeil_setting else genai.GenerativeModel(
            model_name=os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite"),
            system_instruction=instructions,
        )
        text = model.generate_content(message, request_options={"timeout": 20}).text
    else:
        raise RuntimeError("AI_PROVIDER must be openai or gemini")
    if not text or not text.strip():
        raise RuntimeError("Empty model response")
    return text.strip()


@app.route('/')
def home():
    return app.send_static_file('index.html')


@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("message"), str):
        return jsonify({"reply": "질문을 글자로 입력해 주세요오~!"}), 400
    user_message = data["message"].strip()
    if not user_message:
        return jsonify({"reply": "궁금한 내용을 입력해 주세요오~!"}), 400
    if len(user_message) > 8000:
        return jsonify({"reply": "질문이 조금 길어요오~ 8,000자 이내로 나눠 보내주세요!"}), 400

    image_keywords = ["그려줘", "그려", "사진", "이미지", "그림"]
    is_image_request = any(keyword in user_message for keyword in image_keywords)
    try:
        if is_image_request:
            english_prompt = generate_text(
                user_message,
                instructions="Extract a short English image-generation prompt from the user's request. Output only the English prompt, without commentary.",
            )
            encoded_prompt = urllib.parse.quote(english_prompt, safe="")
            image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
            return jsonify({
                "reply": "알겠어요오~! 요청한 그림을 불러오는 중이에요 🎨",
                "image_url": image_url,
            })
        return jsonify({"reply": generate_text(user_message)})
    except Exception:
        app.logger.exception("Chat generation failed (provider=%s)", AI_PROVIDER)
        return jsonify({"reply": "앗, 답변을 가져오지 못했어요오. 잠시 후 다시 시도해 주세요!"}), 502

