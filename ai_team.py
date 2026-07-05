"""
AI TEAM — 3 Models in One Chat
=================================
Nemotron Ultra 550B (Coordinator) + Qwen3 Coder 480B + GPT-OSS 120B
All free via OpenRouter.

Usage:
  python ai_team.py                    # Interactive chat mode
  python ai_team.py "your task"        # Single task mode
"""

import json, os, sys, time
from pathlib import Path
from openai import OpenAI

AUTH_FILE = os.path.join(os.environ.get("USERPROFILE", ""), ".local", "share", "opencode", "auth.json")

def get_key():
    try:
        with open(AUTH_FILE) as f: return json.load(f)["openrouter"]["key"]
    except: return os.environ.get("OPENROUTER_API_KEY", "")

BASE_URL = "https://openrouter.ai/api/v1"
KEY = get_key()

MODELS = {
    "coordinator": "nvidia/nemotron-3-ultra-550b-a55b:free",
    "worker_1":    "qwen/qwen3-coder:free",
    "worker_2":    "openai/gpt-oss-120b:free",
}

SYSTEM_PROMPT = (
    "You are part of a 3-model AI team working on a football score prediction system. "
    "You are an expert in Python, PyTorch, XGBoost, football analytics, and sports betting. "
    "Be concise, technical, and output working code when asked. "
    "The project is at C:\\Users\\zake.exe\\Desktop\\Score Exact 100\\"
)

class Model:
    def __init__(self, name, label):
        self.name = name
        self.label = label
        self.client = OpenAI(base_url=BASE_URL, api_key=KEY)
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]

    def chat(self, msg, temp=0.7, max_tokens=4096):
        self.history.append({"role": "user", "content": msg})
        try:
            r = self.client.chat.completions.create(
                model=self.name, messages=self.history,
                temperature=temp, max_tokens=max_tokens,
            )
            reply = r.choices[0].message.content
            self.history.append({"role": "assistant", "content": reply})
            return reply
        except Exception as e:
            err = f"[ERROR: {e}]"
            self.history.append({"role": "assistant", "content": err})
            return err

    def reset(self):
        self.history = [self.history[0]]

class AITeam:
    def __init__(self):
        print("=" * 60)
        print("  AI TEAM — 3 Models Working Together")
        print("=" * 60)
        self.coord = Model(MODELS["coordinator"], "Coordinator")
        self.w1    = Model(MODELS["worker_1"],    "Coder")
        self.w2    = Model(MODELS["worker_2"],    "Analyst")
        print(f"  Coordinator: {MODELS['coordinator']}")
        print(f"  Coder:       {MODELS['worker_1']}")
        print(f"  Analyst:     {MODELS['worker_2']}")
        print("=" * 60)
        print("  Type 'exit' to quit, 'reset' to clear history")
        print("=" * 60 + "\n")

    def run(self, task):
        t0 = time.time()
        print(f"\n[YOU] {task}\n")

        print("[Coordinator] Breaking down task...")
        plan = self.coord.chat(
            f"Break this task into 2 subtasks for parallel work.\n"
            f"Subtask 1 = coding, Subtask 2 = analysis/review.\n"
            f"Task: {task}\n"
            f"Format: Subtask 1: ...\\nSubtask 2: ..."
        )
        print(f"  {plan[:500]}\n")

        print("[Coder] Working...")
        code = self.w1.chat(
            f"Task: {task}\n\nPlan:\n{plan}\n\n"
            f"You are the CODER. Write complete, executable Python code. "
            f"No placeholders, no pseudocode — real working code."
        )
        print(f"  Done ({len(code)} chars)\n")

        print("[Analyst] Reviewing...")
        review = self.w2.chat(
            f"Task: {task}\n\nPlan:\n{plan}\n\nCoder output:\n{code[:3000]}\n\n"
            f"You are the ANALYST. Review the code, find bugs, suggest improvements, "
            f"and provide additional insights. Be specific."
        )
        print(f"  Done ({len(review)} chars)\n")

        print("[Coordinator] Synthesizing final answer...")
        final = self.coord.chat(
            f"Task: {task}\n\n"
            f"Coder:\n{code[:3000]}\n\n"
            f"Analyst:\n{review[:2000]}\n\n"
            f"Combine into ONE final answer. Include the best code + key insights."
        )

        elapsed = time.time() - t0
        print(f"\n{'='*60}")
        print(f"[FINAL ANSWER] ({elapsed:.0f}s)")
        print(f"{'='*60}")
        print(final)
        print(f"{'='*60}\n")
        return final

    def chat(self):
        while True:
            try:
                user = input("You > ").strip()
                if not user: continue
                if user.lower() in ("exit", "quit", "q"): break
                if user.lower() == "reset":
                    self.coord.reset(); self.w1.reset(); self.w2.reset()
                    print("[Reset] All histories cleared.\n"); continue
                self.run(user)
            except (KeyboardInterrupt, EOFError): break

def main():
    if not KEY:
        print("ERROR: No OpenRouter API key found in auth.json")
        return
    team = AITeam()
    if len(sys.argv) > 1:
        team.run(" ".join(sys.argv[1:]))
    else:
        team.chat()

if __name__ == "__main__":
    main()
