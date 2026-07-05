"""
smart_bot.py — AI-powered chat responder using OpenRouter free route
Responds intelligently in team chat as opencode (Football Oracle AI)
"""
import os, time, sys, json, requests, re

AGENTROUTER_KEY = "sk-j22yAVjq7BcKpL4bgwRpqTGMcCWB74gE8ZEiGA8zyDN3AIVw"
MODEL = "claude-opus-4-6"
API_URL = "https://agentrouter.org/v1/chat/completions"

BRIDGE_DIR = os.path.dirname(os.path.abspath(__file__))
TEAM_FILE = os.path.join(BRIDGE_DIR, 'team.md')
STATE_FILE = os.path.join(BRIDGE_DIR, 'bot_state.json')

responded = set()


def load_state():
    global responded
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            responded = set(json.load(f))


def save_state():
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(responded), f)


def msg_id(m):
    return f'{m.get("time","")}|{m.get("sender","")}|{m.get("text","")[:80]}'


def load_messages():
    msgs = []
    if not os.path.exists(TEAM_FILE):
        return msgs
    with open(TEAM_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    for block in content.split('---\n'):
        block = block.strip()
        if not block:
            continue
        lines = block.split('\n')
        msg = {}
        for line in lines:
            line = line.strip()
            if line.startswith('## '):
                msg['time'] = line[3:].strip()
            elif line.startswith('من: '):
                msg['sender'] = line[3:].split('|')[0].strip()
            elif line.startswith('الرسالة: '):
                msg['text'] = line[7:].strip()
        if 'text' in msg and msg['text']:
            msg['sender'] = msg.get('sender', 'unknown')
            msgs.append(msg)
    return msgs


def post_as(sender, text):
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    entry = (f'\n---\n## {now}\n'
             f'من: {sender} | إلى: all\n'
             f'الموضوع: رسالة مباشرة\n'
             f'الرسالة: {text}\n')
    with open(TEAM_FILE, 'a', encoding='utf-8') as f:
        f.write(entry)


def call_ai(user_message, chat_history):
    """Call OpenRouter free route to generate a smart response."""
    context = "\n".join(
        [f"{m.get('sender','?')}: {m.get('text','')}" for m in chat_history[-8:]]
    )

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": (
                    "أنت opencode، مساعد ذكي خبير بكرة القدم وتوقع المباريات.\n"
                    "شخصيتك: ودود، مباشر، خبير.\n"
                    "إذا سألك عن توقع: اطلب أسماء الفريقين.\n"
                    "إذا سألك عن الكود/التطوير: أجب بدقة.\n"
                    "إذا سألك عن شيء خارج كرة القدم: جاوب بشكل طبيعي.\n"
                    "كن مختصراً (2-3 جمل) ومفيداً.\n\n"
                    f"آخر المحادثة:\n{context}\n\n"
                    f"الرسالة الجديدة:\n{user_message}\n\n"
                    f"رد الآن:"
                )
            }
        ],
        "thinking": {"type": "adaptive"},
        "temperature": 0.7,
        "max_tokens": 300
    }

    try:
        resp = requests.post(API_URL, json=payload, timeout=60,
                             headers={'Authorization': f'Bearer {AGENTROUTER_KEY}',
                                      'Content-Type': 'application/json',
                                      'HTTP-Referer': 'https://github.com/RooVetGit/Roo-Cline',
                                      'X-Title': 'Roo Code',
                                      'User-Agent': 'RooCode/3.54.0'})
        if resp.status_code == 200:
            content = resp.json()['choices'][0]['message']['content']
            return content.strip()
    except Exception:
        pass
    return None


from datetime import datetime


def main():
    load_state()
    print('=' * 50, flush=True)
    print('SMART BOT v2 — AI-powered (OpenRouter free)', flush=True)
    print(f'Watching {TEAM_FILE}', flush=True)
    print(f'Already responded: {len(responded)} msgs', flush=True)
    print('=' * 50, flush=True)

    while True:
        try:
            msgs = load_messages()
            for m in msgs:
                mid = msg_id(m)
                if mid in responded:
                    continue
                responded.add(mid)
                save_state()

                sender = m.get('sender', '').lower()
                text = m.get('text', '')

                if sender == 'user':
                    print(f'\n[{m.get("time","?")}] USER: {text[:100]}', flush=True)
                    time.sleep(1.5)
                    reply = call_ai(text, msgs)
                    if reply:
                        post_as('opencode', reply)
                        print(f'  => opencode: {reply[:150]}', flush=True)

        except Exception as e:
            print(f'Error: {e}', file=sys.stderr, flush=True)
        time.sleep(3)


if __name__ == '__main__':
    main()
