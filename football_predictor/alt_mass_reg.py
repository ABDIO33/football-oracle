"""
ALT REGISTRATION - register on APIs that give keys immediately on the page
"""
import asyncio, os, json, re, random
from datetime import datetime
from playwright.async_api import async_playwright

BASE = "C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor"
os.chdir(BASE)
os.environ['PYTHONIOENCODING'] = 'utf-8'

REG = f"{BASE}/api_keys/ALL_REGISTRATIONS.json"
KEYS = f"{BASE}/api_keys/CAPTURED_API_KEYS.json"

EMAIL_BASE = "elbazamine27"
all_regs = []
captured_keys = []

if os.path.exists(REG):
    with open(REG, encoding='utf-8') as f:
        all_regs = json.load(f)
if os.path.exists(KEYS):
    with open(KEYS, encoding='utf-8') as f:
        captured_keys = json.load(f)

def log(msg):
    safe = msg.encode('ascii', 'ignore').decode('ascii')
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {safe}", flush=True)

def gmail(tag):
    return f"{EMAIL_BASE}+{tag}@gmail.com"

def save():
    with open(REG, 'w', encoding='utf-8') as f:
        json.dump(all_regs, f, indent=2)
    with open(KEYS, 'w', encoding='utf-8') as f:
        json.dump(captured_keys, f, indent=2)

def extract_key(text, service):
    """Extract API keys from page text"""
    patterns = {
        'newsapi': [
            r'(?:api[_-]?key|key)\s*[=:]\s*[\"\']?([a-f0-9]{32})[\"\']?',
            r'([a-f0-9]{32})',
        ],
        'huggingface': [
            r'(?:hf_|api[_-]?token)[=:\s]+([a-zA-Z0-9_\-]{20,60})',
            r'(hf_[a-zA-Z0-9_\-]{10,50})',
        ],
        'exchange': [
            r'(?:api[_-]?key|key|app[_-]?id)\s*[=:]\s*[\"\']?([a-f0-9]{32})[\"\']?',
        ],
        'apininjas': [
            r'(?:api[_-]?key|key)[=:\s]+([a-zA-Z0-9_\-]{20,60})',
        ],
        'generic': [
            r'(?:api[_-]?key|key|token|apikey)\s*[=:]\s*[\"\']?([A-Za-z0-9_\-]{20,50})[\"\']?',
            r'[A-Za-z0-9]{30,45}',
        ],
    }
    
    specific = patterns.get(service, []) + patterns['generic']
    
    for pat in specific:
        matches = re.findall(pat, text, re.IGNORECASE)
        for m in matches:
            mc = m.strip().strip('"\'').strip()
            existing = [k['api_key'] for k in captured_keys]
            if len(mc) >= 20 and mc not in existing and not mc.startswith('elbazamine27'):
                return mc
    return None

async def register_huggingface(page, tag):
    """Register on HuggingFace - gives API token immediately"""
    email = gmail(tag)
    try:
        await page.goto('https://huggingface.co/join', wait_until='domcontentloaded', timeout=20000)
        await asyncio.sleep(1)
        
        # Fill email
        ei = await page.query_selector('input[type="email"], #email, input[name="email"]')
        if ei:
            await ei.fill(email)
            await asyncio.sleep(0.2)
        
        # Fill username
        ui = await page.query_selector('input[name="username"], #username')
        if ui:
            await ui.fill(f"user{tag}")
            await asyncio.sleep(0.2)
        
        # Check for password fields
        pi = await page.query_selector('input[type="password"], #password, input[name="password"]')
        if pi:
            await pi.fill(f"Pass{tag}123!")
            await asyncio.sleep(0.2)
        
        # Submit
        btn = await page.query_selector('button[type="submit"], input[type="submit"]')
        if btn:
            await btn.click()
            await asyncio.sleep(3)
        
        # Check for API token
        text = await page.evaluate('() => document.body.innerText')
        key = extract_key(text, 'huggingface')
        
        if key:
            captured_keys.append({'service': 'HuggingFace', 'email': email, 'api_key': key, 'ts': datetime.now().isoformat()})
            all_regs.append({'service': 'HuggingFace', 'email': email, 'status': 'KEY_CAPTURED'})
            log(f"KEY HF {tag}: {key[:30]}...")
            save()
            return True
        else:
            all_regs.append({'service': 'HuggingFace', 'email': email, 'status': 'REGISTERED'})
            log(f"OK HF {tag} (no key on page)")
            save()
            return True
    except Exception as e:
        all_regs.append({'service': 'HuggingFace', 'email': email, 'status': f'FAIL'})
        log(f"FAIL HF {tag}: {str(e)[:30]}")
        save()
        return False

async def register_exchange_api(page, tag):
    """Register on ExchangeRate-API"""
    email = gmail(tag)
    try:
        await page.goto('https://www.exchangerate-api.com/sign-up', wait_until='domcontentloaded', timeout=15000)
        await asyncio.sleep(1)
        
        ei = await page.query_selector('input[type="email"], #email, input[name="email"]')
        if ei:
            await ei.fill(email)
            await asyncio.sleep(0.2)
        
        btn = await page.query_selector('button[type="submit"], input[type="submit"]')
        if btn:
            await btn.click()
            await asyncio.sleep(2)
        
        text = await page.evaluate('() => document.body.innerText')
        key = extract_key(text, 'exchange')
        
        if key:
            captured_keys.append({'service': 'ExchangeRate', 'email': email, 'api_key': key, 'ts': datetime.now().isoformat()})
            all_regs.append({'service': 'ExchangeRate', 'email': email, 'status': 'KEY_CAPTURED'})
            log(f"KEY EX {tag}: {key[:30]}...")
        else:
            all_regs.append({'service': 'ExchangeRate', 'email': email, 'status': 'REGISTERED'})
            log(f"OK EX {tag}")
        save()
        return True
    except:
        all_regs.append({'service': 'ExchangeRate', 'email': email, 'status': 'FAIL'})
        save()
        return False

async def register_apininjas(page, tag):
    """Register on API Ninjas"""
    email = gmail(tag)
    try:
        await page.goto('https://api-ninjas.com/register', wait_until='domcontentloaded', timeout=15000)
        await asyncio.sleep(1)
        
        ei = await page.query_selector('input[type="email"], #email, input[name="email"]')
        if ei:
            await ei.fill(email)
            await asyncio.sleep(0.2)
        
        pi = await page.query_selector('input[type="password"]')
        if pi:
            await pi.fill(f"Pass{tag}123!")
            await asyncio.sleep(0.2)
        
        btn = await page.query_selector('button[type="submit"], input[type="submit"]')
        if btn:
            await btn.click()
            await asyncio.sleep(3)
        
        text = await page.evaluate('() => document.body.innerText')
        key = extract_key(text, 'apininjas')
        
        if key:
            captured_keys.append({'service': 'APINinjas', 'email': email, 'api_key': key, 'ts': datetime.now().isoformat()})
            all_regs.append({'service': 'APINinjas', 'email': email, 'status': 'KEY_CAPTURED'})
            log(f"KEY AN {tag}: {key[:30]}...")
        else:
            all_regs.append({'service': 'APINinjas', 'email': email, 'status': 'REGISTERED'})
            log(f"OK AN {tag}")
        save()
        return True
    except:
        all_regs.append({'service': 'APINinjas', 'email': email, 'status': 'FAIL'})
        save()
        return False

async def main():
    log("="*60)
    log("ALT MASS REGISTRATION - KEYS ON PAGE")
    log("="*60)
    
    existing_hf = sum(1 for r in all_regs if r['service'] == 'HuggingFace')
    existing_ex = sum(1 for r in all_regs if r['service'] == 'ExchangeRate')
    existing_an = sum(1 for r in all_regs if r['service'] == 'APINinjas')
    log(f"Existing: HF={existing_hf}, EX={existing_ex}, AN={existing_an}")
    log(f"Captured keys: {len(captured_keys)}")
    
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True,
        args=['--disable-blink-features=AutomationControlled'])
    context = await browser.new_context(viewport={'width':1280,'height':720})
    page = await context.new_page()
    
    # Try HuggingFace
    if existing_hf < 200:
        log("\n--- HuggingFace (200 targets) ---")
        for i in range(existing_hf + 1, 201):
            await register_huggingface(page, f"hf{i}")
            await asyncio.sleep(random.uniform(0.5, 1.0))
            if i % 20 == 0:
                log(f"  HF {i}/200")
    
    # Try ExchangeRate
    if existing_ex < 200:
        log("\n--- ExchangeRate (200 targets) ---")
        for i in range(existing_ex + 1, 201):
            await register_exchange_api(page, f"ex{i}")
            await asyncio.sleep(random.uniform(0.3, 0.8))
            if i % 20 == 0:
                log(f"  EX {i}/200")
    
    # Try API Ninjas
    if existing_an < 200:
        log("\n--- API Ninjas (200 targets) ---")
        for i in range(existing_an + 1, 201):
            await register_apininjas(page, f"an{i}")
            await asyncio.sleep(random.uniform(0.5, 1.0))
            if i % 20 == 0:
                log(f"  AN {i}/200")
    
    await browser.close()
    await pw.stop()
    
    log(f"\nFINAL: {len(all_regs)} regs, {len(captured_keys)} keys captured!")
    key_services = {}
    for k in captured_keys:
        s = k['service']
        key_services[s] = key_services.get(s, 0) + 1
    for s, c in key_services.items():
        log(f"  {s}: {c} keys")

if __name__ == "__main__":
    asyncio.run(main())
