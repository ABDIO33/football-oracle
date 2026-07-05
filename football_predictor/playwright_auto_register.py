"""
🔥 SCORE EXACT 100 — PLAYWRIGHT AUTO REGISTRATION BOT 🔥
يسجل آلياً في football-data.org بإيميلات مختلفة
"""
import asyncio, os, sys, json, time, random, string
from datetime import datetime

BASE = "C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.chdir(BASE)

KEY_FILE = f"{BASE}/api_keys/harvested_keys.json"
all_keys = []
if os.path.exists(KEY_FILE):
    with open(KEY_FILE, 'r') as f:
        all_keys = json.load(f)

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f"[{ts}] {msg}")
    with open(f"{BASE}/api_keys/bot_log.txt", "a", encoding='utf-8') as f:
        f.write(f"[{ts}] {msg}\n")

def save_key(service, email, key):
    all_keys.append({
        'service': service, 'email': email, 'key': key,
        'timestamp': datetime.now().isoformat()
    })
    with open(KEY_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_keys, f, ensure_ascii=False, indent=2)
    log(f"  💾 KEY SAVED: {service} → {key}")

def make_temp_email():
    """إنشاء إيميل مؤقت"""
    login = ''.join(random.choices(string.ascii_lowercase, k=10))
    domain = random.choice(['1secmail.com', '1secmail.org', '1secmail.net'])
    email = f"{login}@{domain}"
    return email, login, domain

async def check_1secmail(login, domain, timeout=120):
    """انتظار وصول رسالة"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get('https://www.1secmail.com/api/v1/', 
                           params={'action': 'getMessages', 'login': login, 'domain': domain}, timeout=10)
            msgs = r.json()
            if msgs:
                mid = msgs[0]['id']
                r2 = requests.get('https://www.1secmail.com/api/v1/', 
                                params={'action': 'readMessage', 'login': login, 'domain': domain, 'id': mid}, timeout=10)
                msg = r2.json()
                body = msg.get('textBody', '') or msg.get('htmlBody', '')
                return body
        except:
            pass
        await asyncio.sleep(3)
    return None

async def extract_key_from_email(body):
    """استخراج API Key من الإيميل"""
    if not body:
        return None
    # football-data.org key pattern
    patterns = [
        r'[A-Za-z0-9]{20,40}',  # General key pattern
        r'api[_-]?key[=:]\s*["\']?([A-Za-z0-9]+)',
        r'X-Auth-Token[=:]\s*["\']?([A-Za-z0-9]+)',
    ]
    for pat in patterns:
        match = re.search(pat, body)
        if match:
            return match.group(1) or match.group(0)
    return None

async def register_football_dot_org_playwright(email):
    """Automate registration on football-data.org using Playwright"""
    log(f"\n[🤖] Automating football-data.org registration with {email}")
    
    from playwright.async_api import async_playwright
    
    pw = await async_playwright().start()
    
    try:
        # Launch browser
        browser = await pw.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        
        # Anti-detection
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US']});
        """)
        
        page = await context.new_page()
        
        # Navigate to registration page
        log(f"    Opening football-data.org registration...")
        await page.goto('https://www.football-data.org/client/register', 
                       wait_until='networkidle', timeout=30000)
        await asyncio.sleep(2)
        
        # Take screenshot for debugging
        await page.screenshot(path=f"{BASE}/api_keys/fd_page.png")
        log(f"    Page title: {await page.title()}")
        
        # Try to find email input and fill it
        # The site might have a simple form or might require JS interaction
        
        # Check what's on the page
        content = await page.content()
        log(f"    Page content length: {len(content)}")
        
        # Try different selectors for email input
        email_selectors = [
            'input[type="email"]',
            'input[name="email"]',
            'input[id*="email"]',
            'input[placeholder*="email" i]',
            '#email',
            'input[autocomplete="email"]',
        ]
        
        email_input = None
        for sel in email_selectors:
            try:
                el = await page.wait_for_selector(sel, timeout=3000)
                if el:
                    email_input = el
                    log(f"    Found email input: {sel}")
                    break
            except:
                continue
        
        if email_input:
            # Fill email
            await email_input.click()
            await asyncio.sleep(0.5)
            for ch in email:
                await page.keyboard.type(ch, delay=random.randint(30, 80))
            await asyncio.sleep(1)
            
            # Look for submit button
            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Register")',
                'button:has-text("Sign up")',
                'button:has-text("Submit")',
                'button:has-text("Get API Key")',
            ]
            
            for sel in submit_selectors:
                try:
                    btn = await page.wait_for_selector(sel, timeout=2000)
                    if btn:
                        await btn.click()
                        log(f"    Clicked submit: {sel}")
                        await asyncio.sleep(3)
                        break
                except:
                    continue
            
            # Take screenshot after submission
            await page.screenshot(path=f"{BASE}/api_keys/fd_submitted.png")
            
            # Check response
            final_content = await page.content()
            if 'thank' in final_content.lower() or 'success' in final_content.lower() or 'check your email' in final_content.lower():
                log(f"    ✅ Registration submitted successfully!")
            else:
                log(f"    ⚠️ Check screenshot at api_keys/fd_submitted.png")
        else:
            log(f"    ⚠️ Could not find email input. The site may use a different form.")
            # Save full HTML for analysis
            with open(f"{BASE}/api_keys/fd_page.html", 'w', encoding='utf-8') as f:
                f.write(content)
            log(f"    Saved HTML to api_keys/fd_page.html for analysis")
        
        await browser.close()
        
    except Exception as e:
        log(f"    ❌ Error: {e}")
    finally:
        await pw.stop()

async def main():
    log(f"{'='*60}")
    log(f"[🤖] PLAYWRIGHT AUTO REGISTRATION BOT")
    log(f"{'='*60}")
    
    # Generate temp emails
    emails = []
    for i in range(5):
        email, login, domain = make_temp_email()
        emails.append((email, login, domain))
        log(f"  📧 Email {i+1}: {email}")
    
    # Try to register each one
    for email, login, domain in emails:
        await register_football_dot_org_playwright(email)
        await asyncio.sleep(2)
    
    # Also check inbox for any existing registrations
    log(f"\n[*] Checking inbox for API keys...")
    for email, login, domain in emails:
        body = await check_1secmail(login, domain, timeout=30)
        if body:
            key = await extract_key_from_email(body)
            if key:
                save_key('football-data.org', email, key)
                log(f"  ✅ Found key: {key}")
    
    log(f"\n{'='*60}")
    log(f"[🏆] Total keys harvested: {len(all_keys)}")
    log(f"{'='*60}")
    log(f"\n[💡] GMAIL PLUS TRICK:")
    log(f"   استخدم إيميل Gmail واحد + TAG مختلف لكل API")
    log(f"   مثال: yourname+site1@gmail.com")
    log(f"         yourname+site2@gmail.com")
    log(f"   كل الإيميلات تجي لنفس صندوق الوارد!")
    log(f"\n[✅] تم!")

if __name__ == "__main__":
    import requests, re
    asyncio.run(main())
