from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import os
import datetime 

# 💡 핵심 수정 부분: 현재 폴더 안의 모든 파일(html, 이미지)을 자동으로 읽도록 권한 부여!
app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

# 🏫 마산제일고 AI 페르소나 설정
jeil_setting = """너는 마산제일고등학교 학생들의 학교 생활을 돕고 질문에 답해주는 공식 인공지능 챗봇이야.
학생들에게 항상 친절하고 다정하며, 학교 선배처럼 편안하면서도 정확한 말투로 대답해 줘.
모든 답변은 반드시 3문장 이내로 간결하고 명확하게 대답해.

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

model = genai.GenerativeModel(model_name="gemini-3.1-flash-lite", system_instruction=normal_setting)

@app.route('/')
def home():
    # 이제 무조건 index.html을 찾아서 메인 화면으로 띄웁니다.
    return app.send_static_file('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get("message", "")
    
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[🧑‍🎓 학생 | {now}] {user_message}", flush=True)

    try:
        response = model.generate_content(user_message)
        print(f"[🤖 제일고 AI | {now}] {response.text}\n", flush=True)
        return jsonify({"reply": response.text})
    except Exception as e:
        print(f"🔥 오류 발생: {str(e)}", flush=True)
        return jsonify({"reply": f"오류가 발생했습니다: {str(e)}"})
