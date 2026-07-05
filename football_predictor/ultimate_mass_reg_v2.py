"""
SCORE EXACT 100 — ULTIMATE MASS REGISTRATION BOT v2
يسجل آلاف الحسابات في football-data.org باستخدام Gmail Plus Trick
"""
import asyncio, os, json, random, sys
from datetime import datetime

BASE = "C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor"
os.chdir(BASE)
os.environ['PYTHONIOENCODING'] = 'utf-8'

REG_FILE = f"{BASE}/api_keys/ALL_REGISTRATIONS.json"
out_file = f"{BASE}/api_keys/bot_output.txt"

all_regs = []
if os.path.exists(REG_FILE):
    with open(REG_FILE, encoding='utf-8') as f:
        all_regs = json.load(f)

EMAIL_BASE = "elbazamine27"
TARGET = 1000

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    # Strip non-ASCII for safety
    safe = msg.encode('ascii', 'ignore').decode('ascii')
    line = f"[{ts}] {safe}"
    print(line, flush=True)
    with open(out_file, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def gmail(tag):
    return f"{EMAIL_BASE}+{tag}@gmail.com"

def save_reg(service, email, status):
    all_regs.append({
        'service': service,
        'email': email,
        'status': status,
        'ts': datetime.now().isoformat()
    })
    with open(REG_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_regs, f, indent=2)

async def register_fd(page, tag):
    """Register on football-data.org"""
    email = gmail(tag)
    try:
        await page.goto('https://www.football-data.org/client/register', wait_until='domcontentloaded', timeout=20000)
        await asyncio.sleep(0.5)
        
        el = await page.wait_for_selector('input[type="email"]', timeout=5000)
        await el.click()
        await el.fill(email)
        await asyncio.sleep(0.2)
        
        btn = await page.wait_for_selector('button[type="submit"]', timeout=3000)
        await btn.click()
        await asyncio.sleep(0.5)
        
        save_reg('football-data.org', email, 'REGISTERED')
        log(f"OK fd {tag}")
        return True
    except Exception as e:
        save_reg('football-data.org', email, f'FAIL')
        log(f"FAIL fd {tag}: {str(e)[:30]}")
        return False

async def register_newsapi(page, tag):
    """Register on NewsAPI"""
    email = gmail(tag)
    try:
        await page.goto('https://newsapi.org/register', wait_until='domcontentloaded', timeout=15000)
        await asyncio.sleep(0.5)
        
        for sel in ['input[type="email"]', '#email', 'input[name="email"]']:
            el = await page.query_selector(sel)
            if el:
                await el.click()
                await el.fill(email)
                await asyncio.sleep(0.2)
                break
        
        for sel in ['button[type="submit"]', 'button:has-text("Register")', 'button:has-text("Get API Key")']:
            btn = await page.query_selector(sel)
            if btn:
                await btn.click()
                await asyncio.sleep(0.5)
                break
        
        save_reg('NewsAPI', email, 'REGISTERED')
        log(f"OK news {tag}")
        return True
    except:
        save_reg('NewsAPI', email, 'FAIL')
        log(f"FAIL news {tag}")
        return False

async def main():
    log("="*60)
    log(f"ULTIMATE MASS REGISTRATION v2")
    log(f"Target: {TARGET} per service")
    log(f"Started with: {len(all_regs)} existing")
    log("="*60)
    
    from playwright.async_api import async_playwright
    
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
    context = await browser.new_context(viewport={'width': 1280, 'height': 720})
    page = await context.new_page()
    
    # Count existing
    existing_fd = sum(1 for r in all_regs if r['service'] == 'football-data.org')
    existing_news = sum(1 for r in all_regs if r['service'] == 'NewsAPI')
    
    # PHASE 1: football-data.org up to 1000
    if existing_fd < TARGET:
        log(f"\nPHASE 1: football-data.org ({existing_fd} -> {TARGET})")
        for i in range(existing_fd + 1, TARGET + 1):
            tag = f"fd{i}"
            await register_fd(page, tag)
            await asyncio.sleep(random.uniform(0.3, 0.8))
            
            if i % 50 == 0:
                log(f"  Progress: {i}/{TARGET}")
    
    # PHASE 2: NewsAPI up to 1000
    if existing_news < TARGET:
        log(f"\nPHASE 2: NewsAPI ({existing_news} -> {TARGET})")
        for i in range(existing_news + 1, TARGET + 1):
            tag = f"news{i}"
            await register_newsapi(page, tag)
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            if i % 50 == 0:
                log(f"  Progress: {i}/{TARGET}")
    
    await browser.close()
    await pw.stop()
    
    # Final stats
    fd = sum(1 for r in all_regs if r['service'] == 'football-data.org')
    news = sum(1 for r in all_regs if r['service'] == 'NewsAPI')
    log(f"\nFINAL: fd={fd}, news={news}, total={len(all_regs)}")

if __name__ == "__main__":
    asyncio.run(main())
