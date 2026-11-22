from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import os
import datetime 
import urllib.parse

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

# 🏫 마산제일고 AI 페르소나 설정
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
- 학생들은 가끔 선생님들의 눈을 피해 마산대 매점이나 언덕 너머 중식당 '포청관'으로 몰래 맛있는 걸 먹으러 가는 스릴 넘치는 추억을 만들기도 해.
"""

model = genai.GenerativeModel(model_name="gemini-3.1-flash-lite", system_instruction=jeil_setting)

@app.route('/')
def home():
    return app.send_static_file('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get("message", "")
    
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[🧑‍🎓 학생 | {now}] {user_message}", flush=True)

    # 🎨 사용자가 이미지 요청을 했는지 확인하는 키워드 체크
    image_keywords = ["그려줘", "그려", "사진", "이미지", "그림"]
    is_image_request = any(keyword in user_message for keyword in image_keywords)

    if is_image_request:
        try:
            # 이미지 프롬프트를 영문으로 변환하기 위한 Gemini 요청
            prompt_gen = model.generate_content(f"Extract only a short English prompt suitable for AI image generation from this Korean request: '{user_message}'. Output only the English prompt text.")
            english_prompt = prompt_gen.text.strip()
            
            # Pollinations AI 이미지 생성 URL 조합
            encoded_prompt = urllib.parse.quote(english_prompt)
            image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
            
            # HTML 태그 형태로 챗봇에게 전달
            reply_content = f"알겠어요오~! 질문자쿤이 요청한 그림이에요 🎨<br><br><img src='{image_url}' style='width:100%; border-radius:12px; margin-top:10px;' alt='Generated Image'>"
            
            print(f"[🤖 제일고 AI | {now}] (이미지 생성 완료: {english_prompt})\n", flush=True)
            return jsonify({"reply": reply_content})
        except Exception as e:
            print(f"🔥 이미지 생성 오류: {str(e)}", flush=True)
            return jsonify({"reply": "앗, 그림을 만드는 중에 오류가 났어요오. 잠시 후 다시 시도해 주세요!"})

    # 일반 대화 처리
    try:
        response = model.generate_content(user_message)
        print(f"[🤖 제일고 AI | {now}] {response.text}\n", flush=True)
        return jsonify({"reply": response.text})
    except Exception as e:
        print(f"🔥 오류 발생: {str(e)}", flush=True)
        return jsonify({"reply": f"앗, 답변을 가져오지 못했어요오: {str(e)}"})
