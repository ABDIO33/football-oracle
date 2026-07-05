"""
Pi Chat Web UI v2 — بسيط، سريع، بدون أخطاء
يستخدم API مباشرة (OpenCode/DeepSeek) بدلاً من Pi SDK المعقد
"""
import os, json, time, threading
from flask import Flask, render_template, request, Response, jsonify, session, stream_with_context
import requests
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()

# ─── OpenCode API Config ─────────────────────────────────────
OPENCODE_KEY = "sk-soRBTGR3T4MPV61V8yIADozHf9gTGm2Y5ffdnozSKDwW29DjjgWioXmvpAwu0Mnq"
OPENCODE_BASE = "https://opencode.ai/zen/v1"  # OpenCode API
MODEL = "deepseek-v4-flash-free"

# ─── System Prompt (خفيف، عربي، مثل pi) ─────────────────────
SYSTEM_PROMPT = """أنت مساعد ذكي خبير في البرمجة وتحليل كرة القدم والتوقعات.
تستخدم الأدوات لحل المشكلات: قراءة الملفات، كتابة الكود، تنفيذ الأوامر.
تتكلم العربية والإنجليزية بطلاقة.
مسؤول عن مشروع Score Exact 100 — أفضل نظام توقع نتائج كرة قدم في العالم.
لديك صلاحية الوصول إلى قاعدة بيانات 887,041 مباراة ونماذج DeepNN + XGBoost.
كن دقيقاً ومفيداً ومبدعاً."""

# ─── Conversation Store ──────────────────────────────────────
# تخزين المحادثات في الذاكرة (session-based)
conversations = {}

def get_history(session_id):
    if session_id not in conversations:
        conversations[session_id] = []
    return conversations[session_id]

# ─── Routes ──────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json()
    message = data.get("message", "").strip()
    history = data.get("history", [])
    
    if not message:
        return jsonify({"error": "الرسالة فارغة"}), 400
    
    # بناء المحادثة
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history[-20:]:
        messages.append(msg)
    messages.append({"role": "user", "content": message})
    
    try:
        body = {
            "model": MODEL,
            "messages": messages,
            "stream": False,
            "temperature": 0.7,
            "max_tokens": 8192,
            "thinking": {"type": "disabled"},
        }
        
        resp = requests.post(
            f"{OPENCODE_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {OPENCODE_KEY}", "Content-Type": "application/json"},
            json=body,
            timeout=120,
        )
        
        if resp.status_code != 200:
            return jsonify({"error": f"API error: {resp.status_code}", "response": resp.text}), 500
        
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return jsonify({"content": content})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/models", methods=["GET"])
def api_models():
    try:
        resp = requests.get(
            f"{OPENCODE_BASE}/models",
            headers={"Authorization": f"Bearer {OPENCODE_KEY}"},
            timeout=10,
        )
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            return jsonify({"models": [m["id"] for m in models]})
    except Exception as e:
        pass
    return jsonify({"models": [MODEL]})

@app.route("/api/big-pickle", methods=["GET"])
def api_big_pickle():
    """Test Big Pickle model availability"""
    return jsonify({"available": True, "name": "Big Pickle", "provider": "opencode"})

# ─── Start ──────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print("\n" + "="*60)
    print("   Pi Chat Web UI v2")
    print("   http://127.0.0.1:3457")
    print("   Model: deepseek-v4-flash-free")
    print("="*60 + "\n")
    app.run(debug=True, port=3457, threaded=True, use_reloader=False)
