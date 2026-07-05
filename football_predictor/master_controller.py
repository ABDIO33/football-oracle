"""
MASTER CONTROLLER — يشغل التسجيل و Gmail harvester معاً
"""
import asyncio, os, subprocess, sys, json, time, threading
from datetime import datetime

BASE = "C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor"
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.chdir(BASE)

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f"[{ts}] {msg}")

# Start mass registration in background
def start_mass_reg():
    log("Starting mass registration bot...")
    proc = subprocess.Popen(
        [sys.executable, '-u', 'mass_registration_bot.py'],
        stdout=open('api_keys/mass_reg_output.txt', 'a'),
        stderr=subprocess.STDOUT,
        cwd=BASE,
        env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    )
    log(f"  PID: {proc.pid}")
    return proc

# Monitor the registration progress
def monitor_progress():
    while True:
        try:
            if os.path.exists('api_keys/ALL_REGISTRATIONS.json'):
                with open('api_keys/ALL_REGISTRATIONS.json') as f:
                    data = json.load(f)
                log(f"📊 Registrations so far: {len(data)}")
        except:
            pass
        time.sleep(15)

async def main():
    log("="*60)
    log("🔥 MASTER CONTROLLER — 1000 API KEYS 🔥")
    log("="*60)
    
    log("\n📌 المهمة 1: التسجيل الجماعي (Background)")
    reg_proc = start_mass_reg()
    
    # Monitor in a thread
    monitor_thread = threading.Thread(target=monitor_progress, daemon=True)
    monitor_thread.start()
    
    log("\n📌 المهمة 2: استلام API Keys من Gmail")
    log("\n⚠️ Chrome راح يفتح على شاشتك!")
    log("⚠️ سجل دخول في Gmail: elbazamine27@gmail.com")
    log("⚠️ كل API Keys راح تظهر هنا!")
    
    # Now run the Gmail harvester
    from playwright.async_api import async_playwright
    
    pw = await async_playwright().start()
    
    log("\n⏳ الاتصال بـ Chrome...")
    browser = None
    for i in range(30):
        try:
            browser = await pw.chromium.connect_over_cdp("http://localhost:9222")
            log("✅ متصل بـ Chrome!")
            break
        except:
            if i == 0: log("⏳ انتظار Chrome (5 دقائق)...")
            await asyncio.sleep(10)
    
    if not browser:
        log("❌ Chrome غير متاح")
        return
    
    # Get page
    context = browser.contexts[0] if browser.contexts else await browser.new_context()
    page = context.pages[0] if context.pages else await context.new_page()
    
    # Check current URL
    try:
        log(f"  الصفحة الحالية: {page.url[:60]}")
    except:
        pass
    
    # Wait for Gmail login
    log("\n⏳ انتظر تدخل Gmail...")
    log("   (شوف Chrome على شاشتك وسجل دخول)")
    
    for i in range(240):  # 20 minutes max
        try:
            url = page.url
            if 'mail.google.com' in url and 'inbox' in url:
                log("✅ داخل Gmail!")
                break
            # Maybe search box available?
            has_search = await page.query_selector('input[gh="s"], input[aria-label*="Search"]')
            if has_search:
                log("✅ Gmail مفتوح (عندي شريط البحث)!")
                break
        except:
            pass
        if i % 12 == 0:
            progress_msg = f"⏳ انتظار... ({i*5} ثانية)"
            # Also show registration progress
            try:
                with open('api_keys/ALL_REGISTRATIONS.json') as f:
                    data = json.load(f)
                progress_msg += f" | تسجيلات: {len(data)}"
            except:
                pass
            log(progress_msg)
        await asyncio.sleep(5)
    
    # SEARCH FOR API KEYS
    log("\n🔍 البحث عن API Keys في صندوق الوارد...")
    
    all_keys = []
    search_terms = [
        ('football-data.org API', 'football-data'),
        ('NewsAPI Key', 'newsapi'),
        ('API Key', 'Your API'),
        ('Welcome', 'welcome'),
    ]
    
    for label, query in search_terms:
        log(f"\n   بحث: '{label}'")
        try:
            # Go to inbox
            await page.goto('https://mail.google.com/mail/u/0/#inbox', wait_until='load')
            await asyncio.sleep(1)
            
            # Search
            search_box = await page.query_selector('input[gh="s"], input[aria-label*="Search"]')
            if search_box:
                await search_box.click()
                await search_box.fill('')
                await asyncio.sleep(0.2)
                await page.keyboard.type(query, delay=10)
                await asyncio.sleep(0.5)
                await page.keyboard.press('Enter')
                await asyncio.sleep(2)
                
                # Get email list
                emails = await page.query_selector_all('.zA, tr.zA')
                log(f"    وجد {len(emails)} إيميل")
                
                for idx in range(min(len(emails), 50)):
                    try:
                        fresh = await page.query_selector_all('.zA, tr.zA')
                        if idx < len(fresh):
                            await fresh[idx].click()
                            await asyncio.sleep(1)
                            
                            body_el = await page.query_selector('.a3s, .ii')
                            if body_el:
                                text = await body_el.inner_text()
                                
                                # Extract API keys
                                for p in [r'[A-Za-z0-9]{25,45}', r'(?:Key|Token)[-:]\s*["\']?([A-Za-z0-9_\-]{20,50})']:
                                    for m in re.findall(p, text):
                                        mc = m.strip().strip('"\'').strip()
                                        if len(mc) >= 20 and mc not in all_keys:
                                            all_keys.append(mc)
                                            log(f"    🔑 {mc}")
                            
                            await page.go_back()
                            await asyncio.sleep(0.5)
                    except:
                        pass
        except:
            pass
    
    # SAVE EVERYTHING
    log(f"\n{'='*60}")
    log(f"💾 Saving {len(all_keys)} API Keys...")
    
    # Also get registration stats
    total_regs = 0
    try:
        with open('api_keys/ALL_REGISTRATIONS.json') as f:
            total_regs = len(json.load(f))
    except:
        pass
    
    with open(f'{BASE}/api_keys/FINAL_API_KEYS.txt', 'w', encoding='utf-8') as f:
        f.write("="*60 + "\n")
        f.write(f"SCORE EXACT 100 - 1000 API KEYS COLLECTION\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"Total registrations made: {total_regs}\n")
        f.write(f"API Keys extracted from inbox: {len(all_keys)}\n")
        f.write("="*60 + "\n\n")
        
        f.write("EXTRACTED API KEYS:\n")
        f.write("-"*40 + "\n")
        for i, k in enumerate(all_keys, 1):
            f.write(f"KEY {i}: {k}\n")
        
        f.write(f"\n\nALL REGISTRATIONS ({total_regs}):\n")
        f.write("-"*40 + "\n")
        try:
            with open('api_keys/ALL_REGISTRATIONS.json') as regf:
                data = json.load(regf)
                for r in data:
                    f.write(f"{r['email']} [{r['service']}] [{r['status']}]\n")
        except:
            f.write("(registration file not available)\n")
        
        f.write("\n" + "="*60 + "\n")
        f.write("GMAIL PLUS TRICK: elbazamine27+TAG@gmail.com\n")
        f.write("="*60 + "\n")
    
    log(f"\n✅ FINAL FILE: api_keys/FINAL_API_KEYS.txt")
    log(f"✅ Keys found: {len(all_keys)}")
    log(f"✅ Registrations made: {total_regs}")
    log(f"\n🔥 الهدف: 1000 API KEY!")
    
    await browser.close()
    await pw.stop()

if __name__ == "__main__":
    import re
    asyncio.run(main())
