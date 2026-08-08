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
jeil_setting = """너는 마산제일고등학교 학생들의 학교 생활을 돕고 질문에 답해주는 공식 인공지능 챗봇이야.
학생들에게 항상 친절하고 다정하며, 학교 선배처럼 편안하면서도 정확한 말투로 대답해 줘.
모든 답변은 반드시 3문장 이내로 간결하고 명확하게 대답해.
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
            reply_content = f"요청하신 이미지를 생성했어요! 🎨<br><br><img src='{image_url}' style='width:100%; border-radius:12px; margin-top:10px;' alt='Generated Image'>"
            
            print(f"[🤖 제일고 AI | {now}] (이미지 생성 완료: {english_prompt})\n", flush=True)
            return jsonify({"reply": reply_content})
        except Exception as e:
            print(f"🔥 이미지 생성 오류: {str(e)}", flush=True)
            return jsonify({"reply": "이미지를 생성하는 도중 오류가 발생했습니다."})

    # 일반 대화 처리
    try:
        response = model.generate_content(user_message)
        print(f"[🤖 제일고 AI | {now}] {response.text}\n", flush=True)
        return jsonify({"reply": response.text})
    except Exception as e:
        print(f"🔥 오류 발생: {str(e)}", flush=True)
        return jsonify({"reply": f"오류가 발생했습니다: {str(e)}"})
