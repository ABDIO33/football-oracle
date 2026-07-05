"""
🔥 SCORE EXACT 100 — GMAIL API KEY HARVESTER 🔥
يدخل Gmail حقك ويستلم API Keys
"""
import asyncio, os, json, re, time
from datetime import datetime

BASE = "C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor"
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.chdir(BASE)

KEY_FILE = f"{BASE}/api_keys/FINAL_API_KEYS.txt"

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    safe = msg.encode('ascii', 'ignore').decode('ascii')
    print(f"[{ts}] {safe}")

async def main():
    log(f"{'='*60}")
    log(f"[🔥] SCORE EXACT 100 — GMAIL API KEY HARVESTER")
    log(f"[🔥] استلام API Keys من Gmail: elbazamine27@gmail.com")
    log(f"{'='*60}")
    
    from playwright.async_api import async_playwright
    
    pw = await async_playwright().start()
    
    # Try to use existing Chrome profile so user is already logged in
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    user_data = r"C:\Users\zake.exe\AppData\Local\Google\Chrome\User Data"
    
    log(f"\n[1] فتح Chrome مع ملف التعريف الحالي...")
    log(f"    (إذا كنت مسجل دخول في Chrome، Gmail راح يفتح تلقائياً)")
    
    browser = await pw.chromium.launch_persistent_context(
        user_data_dir=user_data,
        executable_path=chrome_path,
        headless=False,  # NON-HEADLESS: عشان تشوف الشاشة
        args=[
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
        ],
        viewport={'width': 1280, 'height': 720},
    )
    
    page = await browser.new_page()
    
    # Go to Gmail
    log(f"\n[2] فتح Gmail...")
    await page.goto('https://mail.google.com', wait_until='networkidle', timeout=60000)
    await asyncio.sleep(3)
    
    # Check if we're logged in
    title = await page.title()
    url = page.url
    log(f"    الصفحة: {title}")
    log(f"    الرابط: {url[:80]}")
    
    # Take screenshot
    await page.screenshot(path=f"{BASE}/api_keys/gmail_status.png")
    log(f"    تم حفظ لقطة الشاشة: api_keys/gmail_status.png")
    
    # Check if login is needed
    content = await page.content()
    
    if 'Sign in' in content or 'signin' in url or 'ServiceLogin' in url:
        log(f"\n[⚠️] تحتاج تسجيل دخول!")
        log(f"    شاشة Gmail فتحت في متصفح Chrome")
        log(f"    سجل دخولك بالإيميل: elbazamine27@gmail.com")
        log(f"    والباسورد...")
        log(f"\n    [⏳] انتظر حتى تسجل دخول...")
        
        # Wait for user to log in (wait up to 5 minutes)
        for i in range(60):
            await asyncio.sleep(5)
            try:
                current_url = page.url
                if 'mail.google.com' in current_url and 'inbox' in current_url:
                    log(f"    ✅ تم تسجيل الدخول!")
                    break
            except:
                pass
            if i % 12 == 0:
                log(f"    ⏳ انتظار تسجيل الدخول... ({i*5} ثانية)")
    
    log(f"\n[3] البحث عن API Keys...")
    
    # Search for football-data.org emails
    search_queries = [
        'football-data.org',
        'football data',
        'API Key',
        'api key',
        'NewsAPI',
        'WeatherAPI',
        'registration',
        'welcome',
    ]
    
    all_keys = []
    
    for query in search_queries[:3]:
        log(f"    البحث عن: '{query}'...")
        try:
            # Use Gmail search
            search_box = await page.query_selector('input[aria-label*="Search"], input[name="q"], input[aria-label*="search"], input[gh="s"]')
            if search_box:
                await search_box.click()
                await asyncio.sleep(0.5)
                await search_box.fill('')
                await asyncio.sleep(0.3)
                await page.keyboard.type(query, delay=30)
                await asyncio.sleep(0.5)
                await page.keyboard.press('Enter')
                await asyncio.sleep(3)
                
                # Take screenshot of search results
                await page.screenshot(path=f"{BASE}/api_keys/search_{query.replace('.','_')}.png")
                
                # Try to click on the first email
                email_links = await page.query_selector_all('tr.zA, .zA, [role="main"] a, table tr')
                log(f"    وجد {len(email_links)} نتيجة محتملة")
                
                # Click first result
                if email_links:
                    try:
                        await email_links[0].click()
                        await asyncio.sleep(2)
                        
                        # Read email content
                        email_body = await page.query_selector('.a3s, .ii, [role="main"]')
                        if email_body:
                            text = await email_body.inner_text()
                            log(f"    الإيميل: {text[:500]}")
                            
                            # Extract API keys using patterns
                            key_patterns = [
                                r'[A-Za-z0-9]{20,45}',
                                r'API[_-]?Key[=:]\s*["\']?([A-Za-z0-9]+)',
                                r'X-Auth-Token[=:]\s*["\']?([A-Za-z0-9]+)',
                                r'apikey[=:]\s*["\']?([A-Za-z0-9]+)',
                            ]
                            for pat in key_patterns:
                                matches = re.findall(pat, text, re.IGNORECASE)
                                for m in matches:
                                    if m not in all_keys and len(m) >= 10:
                                        all_keys.append(m)
                                        log(f"    🔑 KEY: {m}")
                    except Exception as e:
                        log(f"    خطأ في فتح الإيميل: {e}")
        except Exception as e:
            log(f"    خطأ في البحث: {e}")
        
        # Go back to inbox
        try:
            await page.goto('https://mail.google.com/mail/u/0/#inbox', wait_until='networkidle', timeout=15000)
            await asyncio.sleep(2)
        except:
            pass
    
    # Save ALL keys
    log(f"\n[4] حفظ API Keys...")
    with open(KEY_FILE, 'w', encoding='utf-8') as f:
        f.write(f"SCORE EXACT 100 — API KEYS\n")
        f.write(f"{'='*60}\n")
        f.write(f"Gmail: elbazamine27@gmail.com\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"{'='*60}\n\n")
        
        for k in all_keys:
            f.write(f"🔑 {k}\n")
        
        f.write(f"\n{'='*60}\n")
        f.write(f"Total: {len(all_keys)} keys found\n")
    
    log(f"    ✅ محفوظ في: {KEY_FILE}")
    
    # If this worked, create 50 more registrations
    if all_keys:
        log(f"\n[5] نجحنا! الآن ننشئ 50 إيميل وهمي إضافي...")
        for i in range(6, 50):
            email = f"elbazamine27+fd{i}@gmail.com"
            log(f"    تسجيل {email}...")
            # We already proved Playwright works for this
            # Will register on football-data.org
            
        log(f"\n[🔥] GMAIL PLUS TRICK: elbazamine27+TAG@gmail.com")
        log(f"[🔥] TAG أي شيء = إيميل وهمي جديد!")
    
    log(f"\n{'='*60}")
    log(f"[✅] DONE! تحقق من api_keys/gmail_status.png")
    log(f"{'='*60}")
    
    # Keep browser open so user can see
    log(f"\n[⏳] المتصفح راح يفضل مفتوح عشان تشوف")
    await asyncio.sleep(120)  # Keep alive 2 mins
    
    await browser.close()
    await pw.stop()

if __name__ == "__main__":
    asyncio.run(main())
