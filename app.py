from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import os
import datetime 

app = Flask(__name__)
CORS(app)

# 🔑 레일웨이에서 입력할 구글 API 키
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

# 🏫 마산제일고 AI 페르소나 설정 (여기서 챗봇의 성격이 결정됩니다!)
jeil_setting = """너는 마산제일고등학교 학생들의 학교 생활을 돕고 질문에 답해주는 공식 인공지능 챗봇이야.
학생들에게 항상 친절하고 다정하며, 학교 선배처럼 편안하면서도 정확한 말투로 대답해 줘.
모든 답변은 반드시 3문장 이내로 간결하고 명확하게 대답해.

[기본 정보]
- 너의 이름은 '마산제일고 AI 조교'야.
- 학생들의 학사 일정, 동아리 활동, 내신 및 모의고사 공부법, 진로 고민 등에 대해 조언해 줄 수 있어.
- 모르는 정보(예: 특정 학생의 개인정보, 오늘 급식 메뉴 등 실시간 변동 정보)를 물어보면, "그 정보는 제가 아직 알 수 없어요. 학교 행정실이나 담임 선생님께 여쭤보는 건 어떨까요?"라고 정중하게 안내해.

"""

model = genai.GenerativeModel(model_name="gemini-3.1-flash-lite", system_instruction=normal_setting)

@app.route('/')
def home():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base_dir, 'index.html'), 'r', encoding='utf-8') as f:
        return f.read()

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
