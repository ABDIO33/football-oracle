"""
🔥 SCORE EXACT 100 — GMAIL PLUS TRICK AUTO REGISTRATION 🔥
يستخدم Gmail Plus Trick مع Playwright لتسجيل آلي في كل APIs
"""
import asyncio, os, json, time, random
from datetime import datetime

BASE = "C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor"
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.chdir(BASE)

KEY_FILE = f"{BASE}/api_keys/keys_collected.json"
all_keys = []
if os.path.exists(KEY_FILE):
    with open(KEY_FILE, 'r') as f:
        all_keys = json.load(f)

GMAIL_BASE = "elbazamine27"

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f"[{ts}] {msg}")
    with open(f"{BASE}/api_keys/registration_log.txt", "a", encoding='utf-8') as f:
        f.write(f"[{ts}] {msg}\n")

def save_key(service, email, status):
    all_keys.append({
        'service': service,
        'email': email,
        'status': status,
        'timestamp': datetime.now().isoformat()
    })
    with open(KEY_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_keys, f, ensure_ascii=False, indent=2)
    log(f"  💾 SAVED: {service} → {email} [{status}]")

def gmail_plus(tag):
    """Gmail Plus Trick: يولد إيميل وهمي"""
    return f"{GMAIL_BASE}+{tag}@gmail.com"

async def register_footballdata(page, email):
    """التسجيل في football-data.org"""
    log(f"\n[⚽] football-data.org ← {email}")
    try:
        await page.goto('https://www.football-data.org/client/register', 
                       wait_until='networkidle', timeout=30000)
        await asyncio.sleep(2)
        
        # Fill email
        email_input = await page.wait_for_selector('input[type="email"]', timeout=5000)
        await email_input.click()
        await asyncio.sleep(0.3)
        await email_input.fill(email)
        await asyncio.sleep(0.5)
        
        # Submit
        submit_btn = await page.wait_for_selector('button[type="submit"]', timeout=3000)
        await submit_btn.click()
        await asyncio.sleep(2)
        
        # Check result
        content = await page.content()
        if 'thank' in content.lower() or 'success' in content.lower() or 'check your email' in content.lower():
            log(f"    ✅ Registration successful!")
            save_key('football-data.org', email, 'REGISTERED')
            return True
        else:
            log(f"    ⚠️ Registration submitted (check manually)")
            save_key('football-data.org', email, 'SUBMITTED')
            return True
    except Exception as e:
        log(f"    ❌ Error: {e}")
        return False

async def register_weatherapi(page, email):
    """التسجيل في WeatherAPI.com"""
    log(f"\n[🌤️] WeatherAPI ← {email}")
    try:
        await page.goto('https://www.weatherapi.com/signup.aspx', 
                       wait_until='networkidle', timeout=30000)
        await asyncio.sleep(2)
        
        # Try to find email input
        selectors = ['input[type="email"]', 'input[name="email"]', '#email', 'input[id*="email"]']
        email_input = None
        for sel in selectors:
            try:
                el = await page.wait_for_selector(sel, timeout=2000)
                if el:
                    email_input = el
                    break
            except:
                continue
        
        if email_input:
            await email_input.click()
            await asyncio.sleep(0.3)
            await email_input.fill(email)
            await asyncio.sleep(0.5)
            
            # Look for submit
            btn_selectors = ['button[type="submit"]', 'input[type="submit"]', '#btnRegister']
            for sel in btn_selectors:
                try:
                    btn = await page.wait_for_selector(sel, timeout=2000)
                    if btn:
                        await btn.click()
                        await asyncio.sleep(2)
                        log(f"    ✅ Submitted!")
                        save_key('WeatherAPI', email, 'SUBMITTED')
                        return True
                except:
                    continue
        
        log(f"    ⚠️ Could not automate, needs manual")
        save_key('WeatherAPI', email, 'MANUAL_NEEDED')
        return False
    except Exception as e:
        log(f"    ❌ Error: {e}")
        save_key('WeatherAPI', email, 'ERROR')
        return False

async def register_newsapi(page, email):
    """التسجيل في NewsAPI"""
    log(f"\n[📰] NewsAPI ← {email}")
    try:
        await page.goto('https://newsapi.org/register', 
                       wait_until='networkidle', timeout=30000)
        await asyncio.sleep(2)
        
        # Fill email
        selectors = ['input[type="email"]', 'input[name="email"]', '#email']
        for sel in selectors:
            try:
                el = await page.wait_for_selector(sel, timeout=2000)
                if el:
                    await el.click()
                    await asyncio.sleep(0.3)
                    await el.fill(email)
                    await asyncio.sleep(0.5)
                    break
            except:
                continue
        
        # Look for submit/register button
        btn_selectors = ['button[type="submit"]', 'input[type="submit"]', 'button:has-text("Register")']
        for sel in btn_selectors:
            try:
                btn = await page.wait_for_selector(sel, timeout=2000)
                if btn:
                    await btn.click()
                    await asyncio.sleep(2)
                    log(f"    ✅ Submitted!")
                    save_key('NewsAPI', email, 'SUBMITTED')
                    return True
            except:
                continue
        
        log(f"    ⚠️ Could not automate")
        save_key('NewsAPI', email, 'MANUAL_NEEDED')
        return False
    except Exception as e:
        log(f"    ❌ Error: {e}")
        return False

async def register_thesportsdb(page, email):
    """TheSportsDB free API"""
    log(f"\n[🏅] TheSportsDB ← {email}")
    try:
        await page.goto('https://www.thesportsdb.com/free', 
                       wait_until='networkidle', timeout=30000)
        await asyncio.sleep(2)
        log(f"    ⚠️ TheSportsDB free tier: {await page.title()}")
        save_key('TheSportsDB', email, 'VISITED')
        return True
    except Exception as e:
        log(f"    ❌ Error: {e}")
        return False

async def main():
    log(f"{'='*60}")
    log(f"[🔥] GMAIL PLUS TRICK — AUTO REGISTRATION")
    log(f"[🔥] BASE: {GMAIL_BASE}@gmail.com")
    log(f"{'='*60}")
    
    log(f"\n[*] Gmail Plus Trick يولد إيميلات وهمية من:")
    log(f"    {GMAIL_BASE}+TAG@gmail.com")
    log(f"    كل الإيميلات تروح لـ {GMAIL_BASE}@gmail.com\n")
    
    from playwright.async_api import async_playwright
    
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=True,
        args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
    )
    
    context = await browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    )
    
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    """)
    
    page = await context.new_page()
    
    # List of APIs to register with their tags
    registrations = [
        ('football-data.org', 'footballdata'),
        ('WeatherAPI', 'weatherapi'),
        ('NewsAPI', 'newsapi'),
        ('TheSportsDB', 'sportsdb'),
        ('football-data.org #2', 'footballdata2'),
        ('football-data.org #3', 'footballdata3'),
        ('football-data.org #4', 'footballdata4'),
        ('football-data.org #5', 'footballdata5'),
    ]
    
    for service_name, tag in registrations:
        email = gmail_plus(tag)
        
        if 'football-data' in service_name.lower():
            await register_footballdata(page, email)
        elif 'weather' in service_name.lower():
            await register_weatherapi(page, email)
        elif 'news' in service_name.lower():
            await register_newsapi(page, email)
        elif 'sportsdb' in service_name.lower():
            await register_thesportsdb(page, email)
        
        await asyncio.sleep(random.uniform(1, 3))
    
    await browser.close()
    await pw.stop()
    
    # Final report
    log(f"\n{'='*60}")
    log(f"[🏆] REGISTRATION COMPLETE!")
    log(f"{'='*60}")
    log(f"\n✅ تم التسجيل في:")
    for k in all_keys:
        log(f"  • {k['service']}: {k['email']} [{k['status']}]")
    
    log(f"\n📧 التحقق: إفتح Gmail حقك:")
    log(f"    https://mail.google.com")
    log(f"    وابحث عن رسائل التفعيل")
    log(f"\n🔑 API keys: راح توصلك عالبريد")
    log(f"\n[✅] FINISHED!")

if __name__ == "__main__":
    asyncio.run(main())
