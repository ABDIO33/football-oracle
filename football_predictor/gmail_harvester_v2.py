"""
SCORE EXACT 100 — GMAIL API KEY HARVESTER v2
يفتح متصفح Chrome عشان تسجل دخول في Gmail وتستلم API Keys
"""
import asyncio, os, json, re, time
from datetime import datetime

BASE = "C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor"
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.chdir(BASE)

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    safe = msg.encode('utf-8', 'ignore').decode('utf-8', 'ignore')
    print(f"[{ts}] {safe}")

async def main():
    log("="*60)
    log("SCORE EXACT 100 — GMAIL API KEY HARVESTER")
    log("الهدف: استلام API Keys من Gmail")
    log("="*60)
    
    from playwright.async_api import async_playwright
    
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    
    context = await browser.new_context(
        viewport={'width': 1280, 'height': 720}
    )
    
    page = await context.new_page()
    
    log("\n[1] فتح Gmail...")
    log("    Chrome راح يفتح. سجل دخولك في Gmail")
    log(f"    الايميل: elbazamine27@gmail.com")
    log("    اكتب الباسورد (انا ما اشوفه)")
    
    await page.goto('https://mail.google.com', wait_until='networkidle')
    await asyncio.sleep(2)
    
    # Screenshot
    await page.screenshot(path=f"{BASE}/api_keys/gmail_start.png")
    
    # Wait for user to log in (check every 5 seconds for 5 minutes)
    log("\n[⏳] انتظر تسجيل الدخول... (الوقت: 5 دقائق)")
    logged_in = False
    
    for i in range(60):
        await asyncio.sleep(5)
        try:
            current_url = page.url
            if 'mail.google.com' in current_url and ('inbox' in current_url or 'search' in current_url):
                logged_in = True
                log("✅ تم تسجيل الدخول!")
                break
            content = await page.content()
            if 'Inbox' in content or 'صندوق الوارد' in content:
                logged_in = True
                log("✅ تم تسجيل الدخول!")
                break
        except:
            pass
        if i % 6 == 0:
            log(f"   ⏳ انتظار... ({i*5} ثانية)")
    
    if not logged_in:
        log("⚠️ لم يتم تسجيل الدخول. جرب مرة اخرى")
        await browser.close()
        await pw.stop()
        return
    
    # SEARCH FOR API KEYS
    log("\n[2] البحث عن API Keys...")
    
    all_found_keys = []
    searches = [
        'football-data.org',
        'NewsAPI',
        'API Key',
        'api key',
        'Your API',
    ]
    
    for query in searches:
        log(f"\n   بحث: '{query}'")
        try:
            # Go to inbox
            await page.goto('https://mail.google.com/mail/u/0/#inbox', wait_until='networkidle')
            await asyncio.sleep(1)
            
            # Use search
            search_box = await page.query_selector('input[aria-label*="Search"], input[gh="s"], input[name="q"]')
            if search_box:
                await search_box.click()
                await search_box.fill('')
                await page.keyboard.type(query, delay=20)
                await page.keyboard.press('Enter')
                await asyncio.sleep(2)
                
                # Click first email
                email_items = await page.query_selector_all('tr.zA, .zA')
                if email_items:
                    log(f"   وجد {len(email_items)} ايميل")
                    await email_items[0].click()
                    await asyncio.sleep(2)
                    
                    # Read content
                    body = await page.query_selector('.a3s, .ii, [role="main"]')
                    if body:
                        text = await body.inner_text()
                        log(f"   المحتوى: {text[:600]}")
                        
                        # Save to file
                        safe_q = query.replace('.','_').replace(' ','_')
                        with open(f"{BASE}/api_keys/email_{safe_q}.txt", 'w', encoding='utf-8') as f:
                            f.write(text)
                        
                        # Extract API keys
                        for pat in [r'[A-Za-z0-9]{20,45}', r'Key[=:]\s*["\']?([A-Za-z0-9]+)',
                                    r'Token[=:]\s*["\']?([A-Za-z0-9]+)']:
                            matches = re.findall(pat, text)
                            for m in matches:
                                if m not in all_found_keys and len(m) >= 15:
                                    all_found_keys.append(m)
                                    log(f"   🔑 KEY: {m}")
        except Exception as e:
            log(f"   خطأ: {str(e)[:100]}")
    
    # SAVE ALL KEYS
    log("\n[3] حفظ API Keys...")
    with open(f"{BASE}/api_keys/FINAL_API_KEYS.txt", 'w', encoding='utf-8') as f:
        f.write("="*60 + "\n")
        f.write("SCORE EXACT 100 — FINAL API KEYS\n")
        f.write(f"Gmail: elbazamine27@gmail.com\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write("="*60 + "\n\n")
        
        if all_found_keys:
            for i, k in enumerate(all_found_keys):
                f.write(f"KEY {i+1}: {k}\n")
        else:
            f.write("(No API keys found in inbox yet)\n")
            f.write("Check your Gmail manually for verification emails\n")
        
        f.write("\n" + "="*60 + "\n")
        f.write("GMAIL PLUS TRICK: elbazamine27+TAG@gmail.com\n")
        f.write("="*60 + "\n")
    
    log(f"\n✅ تم الحفظ: api_keys/FINAL_API_KEYS.txt")
    log(f"✅ وجد {len(all_found_keys)} Key")
    
    log("\n" + "="*60)
    log("DONE!")
    log("="*60)
    log("\n💡 نصيحة:")
    log("   افتح mail.google.com بنفسك")
    log("   وابحث عن 'football-data' و'NewsAPI'")
    log("   استلم API Keys يدوياً")
    
    await asyncio.sleep(10)
    await browser.close()
    await pw.stop()

if __name__ == "__main__":
    asyncio.run(main())
