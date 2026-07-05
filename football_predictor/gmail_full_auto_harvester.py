"""
SCORE EXACT 100 — GMAIL API KEY HARVESTER v3 (FULL AUTO)
يدخل Gmail آلياً ويستلم كل API Keys
"""
import asyncio, os, json, re, time
from datetime import datetime

BASE = "C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor"
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.chdir(BASE)
KEY_FILE = f"{BASE}/api_keys/FINAL_API_KEYS.txt"

EMAIL = "elbazamine27@gmail.com"
PASSWORD = "ABDO1122334455"

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f"[{ts}] {msg}")
    with open(f"{BASE}/api_keys/gmail_bot_log.txt", "a", encoding='utf-8') as f:
        f.write(f"[{ts}] {msg}\n")

async def main():
    log("="*60)
    log("SCORE EXACT 100 - GMAIL API KEY HARVESTER v3")
    log("هدف: استلام كل API Keys من Gmail آلياً")
    log("="*60)
    
    from playwright.async_api import async_playwright
    
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=True,
        args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
    )
    
    context = await browser.new_context(
        viewport={'width': 1280, 'height': 720}
    )
    # Anti-detection
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
    """)
    
    page = await context.new_page()
    
    # STEP 1: Go to Gmail and login
    log("\n[1] فتح Gmail...")
    await page.goto('https://accounts.google.com/ServiceLogin?service=mail', wait_until='networkidle')
    await asyncio.sleep(2)
    
    # Type email
    log("    كتابة الإيميل...")
    # Google uses #identifierId for email input
    email_input = await page.wait_for_selector('#identifierId', timeout=15000)
    await email_input.click()
    await asyncio.sleep(0.3)
    await email_input.fill(EMAIL)
    await asyncio.sleep(0.5)
    
    # Click Next
    next_btn = await page.wait_for_selector('#identifierNext', timeout=5000)
    await next_btn.click()
    await asyncio.sleep(3)
    
    # Type password
    log("    كتابة الباسورد...")
    pw_input = await page.wait_for_selector('input[type="password"]', timeout=10000)
    await pw_input.click()
    await asyncio.sleep(0.3)
    await pw_input.fill(PASSWORD)
    await asyncio.sleep(0.5)
    
    # Click Next
    pw_next = await page.wait_for_selector('#passwordNext', timeout=5000)
    await pw_next.click()
    await asyncio.sleep(3)
    
    # Check if login succeeded
    current_url = page.url
    log(f"    URL بعد التسجيل: {current_url[:80]}")
    
    if 'challenge' in current_url or '2sv' in current_url:
        log("    ⚠️ طلب تحقق إضافي (2FA/هاتف)")
        log("    Chrome مفتوح - أكمل التحقق بنفسك")
        await page.screenshot(path=f"{BASE}/api_keys/2fa_challenge.png")
        # Wait 60s for user to complete
        for i in range(12):
            await asyncio.sleep(5)
            if 'mail.google.com' in page.url:
                log("    ✅ تم التحقق!")
                break
    elif 'mail.google.com' in current_url:
        log("    ✅ تم تسجيل الدخول!")
    else:
        log(f"    ⚠️ الصفحة الحالية: {current_url[:60]}")
        await page.screenshot(path=f"{BASE}/api_keys/login_status.png")
        # Try to navigate to Gmail directly
        await page.goto('https://mail.google.com/mail/u/0/#inbox', wait_until='networkidle')
        await asyncio.sleep(2)
    
    # Take screenshot of inbox
    await page.screenshot(path=f"{BASE}/api_keys/gmail_inbox.png")
    
    # STEP 2: Search for API keys
    log("\n[2] البحث عن API Keys...")
    
    all_keys = []
    searches = [
        ('football-data', 'football-data.org API'),
        ('NewsAPI', 'NewsAPI key'),
        ('Your API', 'General API key'),
        ('welcome', 'Welcome email'),
        ('registration', 'Registration confirm'),
    ]
    
    for query, desc in searches:
        log(f"\n   بحث: '{query}' ({desc})")
        try:
            # Ensure at inbox
            await page.goto('https://mail.google.com/mail/u/0/#inbox', wait_until='load')
            await asyncio.sleep(1)
            
            # Click search
            search_box = await page.wait_for_selector('input[aria-label*="Search"], input[gh="s"], input[aria-label*="search"]', timeout=5000)
            if search_box:
                await search_box.click()
                await search_box.fill('')
                await asyncio.sleep(0.2)
                await page.keyboard.type(query, delay=15)
                await asyncio.sleep(0.3)
                await page.keyboard.press('Enter')
                await asyncio.sleep(3)
                
                # Screenshot search
                await page.screenshot(path=f"{BASE}/api_keys/search_{query}.png")
                
                # Count results
                items = await page.query_selector_all('.zA, tr.zA')
                log(f"    نتائج: {len(items)} ايميل")
                
                # Click each result
                for idx in range(min(len(items), 3)):
                    try:
                        # Re-get items (they may have changed)
                        fresh_items = await page.query_selector_all('.zA, tr.zA')
                        if idx < len(fresh_items):
                            await fresh_items[idx].click()
                            await asyncio.sleep(2)
                            
                            # Read email content
                            body = await page.query_selector('.a3s, .ii, [role="main"]')
                            if body:
                                text = await body.inner_text()
                                log(f"    ايميل {idx+1}: {text[:200]}")
                                
                                # Save full email
                                safe_q = query.replace('.','_')
                                with open(f"{BASE}/api_keys/email_{safe_q}_{idx}.txt", 'w', encoding='utf-8') as f:
                                    f.write(text)
                                
                                # Extract KEY from text
                                for pat in [
                                    r'[A-Za-z0-9]{25,45}',
                                    r'(?:API|Key|Token)[=:]\s*["\']?([A-Za-z0-9_\-]{20,50})',
                                    r'(?:api[_-]?key|apikey)[=:]\s*["\']?([A-Za-z0-9_\-]+)',
                                ]:
                                    matches = re.findall(pat, text, re.IGNORECASE)
                                    for m in matches:
                                        m_clean = m.strip().strip('"\'')
                                        if len(m_clean) >= 15 and m_clean not in all_keys:
                                            all_keys.append(m_clean)
                                            log(f"    🔑 KEY FOUND: {m_clean}")
                            
                            # Go back
                            await page.go_back()
                            await asyncio.sleep(1)
                    except Exception as e:
                        log(f"    خطأ: {str(e)[:80]}")
        except Exception as e:
            log(f"    خطأ بحث: {str(e)[:80]}")
    
    # STEP 3: Save all keys
    log("\n[3] حفظ API Keys...")
    os.makedirs(f"{BASE}/api_keys", exist_ok=True)
    
    with open(KEY_FILE, 'w', encoding='utf-8') as f:
        f.write("="*60 + "\n")
        f.write("SCORE EXACT 100 - FINAL API KEYS COLLECTION\n")
        f.write(f"Email: {EMAIL}\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write("="*60 + "\n\n")
        
        if all_keys:
            for i, k in enumerate(all_keys, 1):
                f.write(f"KEY {i}: {k}\n")
        else:
            f.write("(لم يتم العثور على API Keys في صندوق الوارد)\n")
            f.write("قد تحتاج انتظار رسائل التفعيل من football-data.org\n")
        
        f.write("\n\n" + "="*60 + "\n")
        f.write("GMAIL PLUS TRICK: elbazamine27+TAG@gmail.com\n")
        f.write("كل TAG = API Key جديد!\n")
        f.write("="*60 + "\n")
    
    log(f"\n✅ ملف API Keys: {KEY_FILE}")
    log(f"✅ عدد المفاتيح: {len(all_keys)}")
    
    # STEP 4: If keys found, create MORE accounts
    if all_keys:
        log("\n[4] نجحنا! نستمر في إنشاء 50+ API Key إضافي...")
        log("    استخدم Gmail Plus Trick:")
        log("    elbazamine27+footballdataX@gmail.com")
        for i in range(10):
            tag = f"fd{i+6}"
            log(f"    📧 {EMAIL.replace('@', '+'+tag+'@')}")
    
    # Summary
    log("\n" + "="*60)
    log("DONE!")
    log("="*60)
    log(f"\nAPI Keys: {KEY_FILE}")
    
    await browser.close()
    await pw.stop()

if __name__ == "__main__":
    asyncio.run(main())
