"""
Score Exact 100 — AUTO API KEY GENERATOR
يستخدم Gmail Plus Trick + Temp Mail APIs + تسجيل آلي
"""
import requests, json, time, re, sys, os
from datetime import datetime

BASE = "C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# ============================================================
# PART 1: GMAIL PLUS TRICK — أنشئ عدد لا نهائي من API keys
# ============================================================
# Gmail Plus: username+TAG@gmail.com → username@gmail.com
# هذا خاصية رسمية من Google! كل TAG يعتبر إيميل مختلف
# لكن كل الإيميلات تجي لنفس الصندوق
# ============================================================

# ============================================================
# PART 2: TEMP MAIL API — بدون حساب Gmail أصلاً!
# ============================================================
class TempMailAPI:
    """باستخدام Mail.tm API — إيميلات مؤقتة بدون تسجيل!"""
    
    def __init__(self):
        self.base = "https://api.mail.tm"
        self.email = None
        self.password = None
        self.token = None
        self.account_id = None
        
    def create_account(self):
        """إنشاء إيميل مؤقت جديد"""
        # Generate random identity
        identities = [
            ("football.predictor", "GoalScorer99!"),
            ("soccer.analyst", "DataDriven1!"),
            ("match.predict", "WinPredict$5"),
            ("score.exact", "ExactScore!7"),
            ("world.cup.pro", "WC2026Pro#"),
            ("goal.prediction", "PredGoal$2"),
            ("football.data", "DataFoot!8"),
            ("match.analytics", "Analytics!3"),
            ("sports.forecast", "Forecast$9"),
            ("ai.football", "AIFootball!1"),
        ]
        
        for username, pw in identities:
            try:
                # Create account
                email = f"{username}@tiiny.site"
                data = {"address": email, "password": pw}
                r = requests.post(f"{self.base}/accounts", json=data, timeout=10)
                
                if r.status_code == 201:
                    self.email = email
                    self.password = pw
                    self.account_id = r.json().get('id', '')
                    
                    # Get token
                    r2 = requests.post(f"{self.base}/token", 
                                       json={"address": email, "password": pw}, timeout=10)
                    if r2.status_code == 200:
                        self.token = r2.json().get('token', '')
                        log(f"✅ Temp email: {email}")
                        return email
            except:
                continue
        
        return None
    
    def wait_for_message(self, timeout=60):
        """انتظار وصول رسالة"""
        headers = {"Authorization": f"Bearer {self.token}"}
        start = time.time()
        while time.time() - start < timeout:
            try:
                r = requests.get(f"{self.base}/messages", headers=headers, timeout=10)
                if r.status_code == 200 and len(r.json().get('hydra:member', [])) > 0:
                    msg = r.json()['hydra:member'][0]
                    # Get full message
                    mid = msg['id']
                    r2 = requests.get(f"{self.base}/messages/{mid}", headers=headers, timeout=10)
                    if r2.status_code == 200:
                        return r2.json()
            except:
                pass
            time.sleep(3)
        return None
    
    def extract_verification_link(self, message):
        """استخراج رابط التفعيل من الإيميل"""
        if not message:
            return None
        html = message.get('html', [''])[0] if isinstance(message.get('html'), list) else str(message.get('html', ''))
        urls = re.findall(r'https?://[^\s<>"\']+', html)
        for url in urls:
            if 'verify' in url.lower() or 'confirm' in url.lower() or 'activate' in url.lower():
                return url
        return urls[0] if urls else None


# ============================================================
# PART 3: REGISTER ON FREE APIS
# ============================================================
def register_football_data(email):
    """التسجيل في football-data.org (أفضل API مجاني)"""
    log(f"تسجيل في football-data.org بـ {email}...")
    try:
        r = requests.post("https://www.football-data.org/client/register", 
                         json={"email": email}, timeout=15)
        data = r.json()
        if 'apiKey' in data:
            log(f"  ✅ API Key: {data['apiKey']}")
            return data['apiKey']
    except:
        pass
    
    # Trial with their free tier
    try:
        r = requests.get(f"https://api.football-data.org/v4/competitions/", 
                        headers={"X-Unnamed-Client": email}, timeout=10)
        log(f"  ⚠️ Football-data response: {r.status_code}")
    except:
        pass
    return None

def register_weather_api(email):
    """التسجيل في WeatherAPI"""
    log(f"تسجيل في WeatherAPI بـ {email}...")
    try:
        r = requests.post("https://api.weatherapi.com/v1/register.json", 
                         json={"email": email}, timeout=15)
        if 'key' in r.json():
            key = r.json()['key']
            log(f"  ✅ API Key: {key}")
            return key
    except:
        pass
    return None

def get_free_apis():
    """APIs لا تحتاج حتى تسجيل!"""
    apis = {
        "Open-Meteo (Weather)": "https://api.open-meteo.com/v1/forecast?latitude=35&longitude=139&hourly=temperature_2m",
        "Google Gemini (AI)": "تقدر تستخدمه مجاناً من Google AI Studio",
        "Hugging Face (ML Datasets)": "https://huggingface.co/api/datasets",
    }
    for name, url in apis.items():
        log(f"✅ FREE: {name} — {url}")


# ============================================================
# MAIN
# ============================================================
def main():
    log("="*60)
    log("🏆 SCORE EXACT 100 — AUTO API KEY GENERATOR")
    log("="*60)
    
    # METHOD 1: استخدم Gmail Plus Trick لو عندك Gmail
    print("\n📌 الطريقة الأولى: Gmail Plus Trick")
    print("   إيميل واحد + TAG = عدد لا نهائي من API keys!")
    print('   مثال: yourmail+1@gmail.com, yourmail+2@gmail.com')
    print("   (جميع الإيميلات تروح لنفس الصندوق)")
    
    # METHOD 2: Temp Mail API (بدون Gmail)
    print("\n📌 الطريقة الثانية: Temp Mail API")
    print("   إيميلات مؤقتة بدون تسجيل!")
    
    temp = TempMailAPI()
    email = temp.create_account()
    
    if email:
        log(f"\n🚀 بدأ التسجيل في APIs...")
        
        # football-data.org
        key1 = register_football_data(email)
        if key1:
            save_key("football-data.org", email, key1)
        
        # WeatherAPI
        key2 = register_weather_api(email)
        if key2:
            save_key("WeatherAPI", email, key2)
        
        # Free APIs
        get_free_apis()
    
    # METHOD 3: Try other temp mail domains
    print("\n📌 الطريقة الثالثة: أكثر من Temp Mail service")
    for domain in ["guerrillamail.com", "mailnator.com", "10minutemail.com"]:
        log(f"بديل: {domain}")
    
    log("\n" + "="*60)
    log("🏆 الخلاصة: ")
    log("   1. Gmail Plus Trick = UNLIMITED API keys من إيميل واحد!")
    log("   2. Temp Mail API = إيميلات مؤقتة بدون أي تكلفة")
    log("   3. في APIs كثيرة لا تحتاج حتى تسجيل!")
    log("="*60)

def save_key(service, email, key):
    """حفظ API key"""
    os.makedirs(f"{BASE}/api_keys", exist_ok=True)
    with open(f"{BASE}/api_keys/keys.txt", "a") as f:
        f.write(f"[{datetime.now()}] {service} | {email} | {key}\n")
    log(f"  💾 محفوظ في api_keys/keys.txt")

if __name__ == "__main__":
    main()
