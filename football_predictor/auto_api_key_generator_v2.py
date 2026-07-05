"""
Score Exact 100 — V2: AUTO API KEY GENERATOR  
يستخدم Guerrilla Mail API + 1secmail (بدون تسجيل، بدون فلوس)
"""
import requests, json, time, re, os, random, string
from datetime import datetime

BASE = "C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor"
os.makedirs(f"{BASE}/api_keys", exist_ok=True)
os.environ['PYTHONIOENCODING'] = 'utf-8'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def random_string(n=8):
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(n))

# ============================================================
# TEMP MAIL APIs — كلها مجانية 100%
# ============================================================

class GuerrillaMail:
    """Guerrilla Mail API — مجاني بالكامل، لا يحتاج تسجيل"""
    
    def __init__(self):
        self.sid = None
        self.email_addr = None
        self.api = "https://api.guerrillamail.com/ajax.php"
    
    def create(self):
        """إنشاء إيميل مؤقت"""
        try:
            r = requests.get(self.api, params={
                'f': 'get_email_address',
                'ip': '127.0.0.1',
                'agent': 'Mozilla/5.0'
            }, timeout=10)
            data = r.json()
            self.sid = data.get('sid')
            self.email_addr = data.get('email_addr')
            log(f"  [+] Guerrilla: {self.email_addr}")
            return self.email_addr
        except Exception as e:
            log(f"  [-] Guerrilla error: {e}")
            return None
    
    def check_inbox(self):
        """فححوص صندوق الوارد"""
        try:
            r = requests.get(self.api, params={
                'f': 'get_email_list',
                'sid': self.sid,
                'offset': 0
            }, timeout=10)
            data = r.json()
            emails = data.get('list', [])
            if emails:
                return emails[0]
            return None
        except:
            return None
    
    def get_email_body(self, mail_id):
        """جلب محتوى الإيميل"""
        try:
            r = requests.get(self.api, params={
                'f': 'fetch_email',
                'sid': self.sid,
                'email_id': mail_id
            }, timeout=10)
            return r.json()
        except:
            return None


class OneSecMail:
    """1secmail API — بسيط جداً، مجاني"""
    
    def __init__(self):
        self.email = None
        self.login = None
        self.domain = None
    
    def create(self):
        """إنشاء إيميل جديد"""
        self.login = random_string(10)
        self.domain = random.choice(["1secmail.com", "1secmail.org", "1secmail.net"])
        self.email = f"{self.login}@{self.domain}"
        log(f"  [+] 1secmail: {self.email}")
        return self.email
    
    def check_inbox(self):
        """فححوص صندوق الوارد"""
        try:
            r = requests.get(f"https://www.1secmail.com/api/v1/", params={
                'action': 'getMessages',
                'login': self.login,
                'domain': self.domain
            }, timeout=10)
            msgs = r.json()
            if msgs:
                return msgs[0]
            return None
        except:
            return None
    
    def read_message(self, msg_id):
        """قراءة رسالة"""
        try:
            r = requests.get(f"https://www.1secmail.com/api/v1/", params={
                'action': 'readMessage',
                'login': self.login,
                'domain': self.domain,
                'id': msg_id
            }, timeout=10)
            return r.json()
        except:
            return None


# ============================================================
# REGISTER ON APIs
# ============================================================

def register_football_data(email):
    """football-data.org - أفضل API كرة قدم مجاني"""
    log(f"    تسجيل في football-data.org...")
    try:
        r = requests.get(
            "https://api.football-data.org/v4/competitions/",
            headers={"X-Auth-Token": ""},
            timeout=10
        )
        log(f"    football-data رد: {r.status_code}")
        if r.status_code == 200:
            log(f"    ملاحظة: football-data.org يحتاج تسجيل عبر موقعهم")
            log(f"    اذهب إلى: https://www.football-data.org/client/register")
            log(f"    سجل بـ {email} واحصل على API Key مجاني")
        return None
    except Exception as e:
        log(f"    خطأ: {e}")
        return None

def register_openweather(email):
    """OpenWeatherMap - API طقس مجاني"""
    log(f"    تسجيل في OpenWeatherMap...")
    try:
        r = requests.get(
            f"https://api.openweathermap.org/data/2.5/weather?q=London&appid=test",
            timeout=10
        )
        log(f"    فشل (يحتاج مفتاح)")
    except:
        pass
    return None

# ============================================================
# HARVEST ALREADY-FREE APIs (لا تحتاج تسجيل!)
# ============================================================

def discover_free_apis():
    """APIs مجانية بالكامل — بدون مفتاح"""
    log(f"\n[+] APIs مجانية تماماً...")
    
    free_apis = [
        ("Open-Meteo Weather", 
         "https://api.open-meteo.com/v1/forecast?latitude=33.57&longitude=-7.58&hourly=temperature_2m,precipitation,wind_speed_10m&timezone=auto",
         "مجاني بالكامل - طقس المغرب"),
        
        ("Open-Meteo Air Quality",
         "https://air-quality-api.open-meteo.com/v1/air-quality?latitude=33.57&longitude=-7.58&hourly=pm2_5",
         "مجاني بالكامل"),
        
        ("GitHub API",
         "https://api.github.com/search/repositories?q=football+predictor",
         "مجاني 60 req/hour"),
        
        ("CoinGecko (Crypto)",
         "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
         "مجاني"),
        
        ("Wikipedia API",
         "https://en.wikipedia.org/api/rest_v1/page/summary/2026_FIFA_World_Cup",
         "مجاني بالكامل - معلومات كأس العالم"),
        
        ("HuggingFace Datasets",
         "https://huggingface.co/api/datasets?search=football",
         "مجاني - datasets ML"),
        
        ("REST Countries",
         "https://restcountries.com/v3.1/name/morocco",
         "معلومات الدول"),
    ]
    
    for name, url, desc in free_apis:
        try:
            r = requests.get(url, timeout=10)
            status = "✅" if r.status_code == 200 else "❌"
            log(f"  {status} {name}: {desc} [{r.status_code}]")
        except:
            log(f"  ❌ {name}: {desc} [خطأ]")
    
    return free_apis


# ============================================================
# TEST ALL TEMP MAIL
# ============================================================

def test_all_temp_services():
    """تجربة جميع خدمات الإيميل المؤقت"""
    log(f"\n{'='*60}")
    log(f"[*] تجربة خدمات الإيميل المؤقت...")
    log(f"{'='*60}")
    
    # 1. Guerrilla Mail
    log(f"\n[1] Guerrilla Mail:")
    gm = GuerrillaMail()
    email = gm.create()
    
    # 2. 1secmail  
    log(f"\n[2] 1secmail:")
    osm = OneSecMail()
    email2 = osm.create()
    
    # Return working emails
    return [email, email2]


# ============================================================
# AUTO-REGISTRATION SCRIPT
# ============================================================

def auto_register_all(emails):
    """محاولة التسجيل في كل API بكل إيميل"""
    log(f"\n{'='*60}")
    log(f"[*] بدأ التسجيل التلقائي...")
    log(f"{'='*60}")
    
    results = []
    
    for i, email in enumerate(emails):
        if not email:
            continue
        log(f"\n[+] إيميل {i+1}: {email}")
        
        # Try football-data
        key = register_football_data(email)
        
        results.append({
            'email': email,
            'football_data': key
        })
    
    return results


# ============================================================
# MAIN
# ============================================================

def main():
    log(f"{'='*60}")
    log(f"[🏆] SCORE EXACT 100 — AUTO API KEY GENERATOR v2")
    log(f"{'='*60}")
    
    # Step 1: Test temp mail services
    emails = test_all_temp_services()
    
    # Step 2: Discover free APIs
    discover_free_apis()
    
    # Step 3: Try to auto-register
    results = auto_register_all(emails)
    
    # Step 4: Print API Key generation plan
    log(f"\n{'='*60}")
    log(f"[🏆] خطة إنشاء API Keys:")
    log(f"{'='*60}")
    log(f"""
    الطريقة 1: Gmail Plus Trick (لو عندك Gmail)
    -----------------------------------------
    استخدم إيميل واحد + TAG مختلف لكل API
    مثال: your.name+footballdata@gmail.com
          your.name+rapidapi@gmail.com
          your.name+weatherapi@gmail.com
    
    كل الإيميلات تروح لنفس صندوق الوارد!
    
    الطريقة 2: Temp Mail (بدون Gmail)
    -----------------------------------------
    Guerrilla Mail / 1secmail — إيميل جديد لكل API
    
    الطريقة 3: APIs مجانية بالكامل
    -----------------------------------------
    Open-Meteo, Wikipedia, GitHub — لا تحتاج مفتاح!
    """)
    
    log(f"[✅] تم! والله يوفقك بالرهان الأول!")

if __name__ == "__main__":
    main()
