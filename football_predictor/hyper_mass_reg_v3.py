"""
HYPER SPEED MASS REGISTRATION v3 - CAPTURES API KEYS FROM REGISTRATION PAGE!
"""
import asyncio, os, json, random, re
from datetime import datetime

BASE = "C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor"
os.chdir(BASE)
os.environ['PYTHONIOENCODING'] = 'utf-8'

REG_FILE = f"{BASE}/api_keys/ALL_REGISTRATIONS.json"
KEYS_FILE = f"{BASE}/api_keys/EXTRACTED_API_KEYS.json"
OUT_FILE = f"{BASE}/api_keys/v3_bot_output.txt"

all_regs = []
all_keys = []
if os.path.exists(REG_FILE):
    with open(REG_FILE, encoding='utf-8') as f:
        all_regs = json.load(f)
if os.path.exists(KEYS_FILE):
    with open(KEYS_FILE, encoding='utf-8') as f:
        all_keys = json.load(f)

EMAIL_BASE = "elbazamine27"
LOG = []

def log(msg):
    safe = msg.encode('ascii', 'ignore').decode('ascii')
    ts = datetime.now().strftime('%H:%M:%S')
    line = f"[{ts}] {safe}"
    print(line, flush=True)
    LOG.append(line)
    with open(OUT_FILE, 'a', encoding='utf-8') as f:
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

def save_key(service, email, api_key):
    all_keys.append({
        'service': service,
        'email': email,
        'api_key': api_key,
        'ts': datetime.now().isoformat()
    })
    with open(KEYS_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_keys, f, indent=2)
    log(f"KEY CAPTURED [{service}]: {api_key}")

def extract_api_key(text):
    """Extract API keys from page text"""
    # Common patterns for API keys
    patterns = [
        r'(?:api[_-]?key|key|token|apikey)\s*[=:]\s*["\']?([A-Za-z0-9_\-]{20,50})["\']?',
        r'[A-Za-z0-9]{30,45}',  # Generic long alphanumeric
        r'X-Auth-Token:\s*([A-Za-z0-9_\-]{20,50})',
    ]
    for p in patterns:
        matches = re.findall(p, text, re.IGNORECASE)
        for m in matches:
            mc = m.strip().strip('"\'')
            if len(mc) >= 20 and mc not in [k['api_key'] for k in all_keys]:
                return mc
    return None

async def register_fd(page, tag):
    """Register on football-data.org and capture API key"""
    email = gmail(tag)
    try:
        await page.goto('https://www.football-data.org/client/register', 
                       wait_until='domcontentloaded', timeout=20000)
        await asyncio.sleep(0.3)
        
        el = await page.wait_for_selector('input[type="email"]', timeout=5000)
        await el.click()
        await el.fill(email)
        await asyncio.sleep(0.1)
        
        btn = await page.wait_for_selector('button[type="submit"]', timeout=3000)
        await btn.click()
        
        # Wait for response - maybe key is shown immediately
        await asyncio.sleep(1.5)
        
        # Get page text to capture key
        body_text = await page.evaluate('() => document.body.innerText')
        
        api_key = extract_api_key(body_text)
        if api_key:
            save_key('football-data.org', email, api_key)
            save_reg('football-data.org', email, 'REGISTERED+KEY')
            log(f"OK+KEY fd {tag}")
        else:
            save_reg('football-data.org', email, 'REGISTERED')
            log(f"OK fd {tag}")
        return True
    except Exception as e:
        save_reg('football-data.org', email, f'FAIL')
        log(f"FAIL fd {tag}: {str(e)[:30]}")
        return False

async def register_newsapi(page, tag):
    """Register on NewsAPI and capture API key"""
    email = gmail(tag)
    try:
        await page.goto('https://newsapi.org/register', 
                       wait_until='domcontentloaded', timeout=15000)
        await asyncio.sleep(0.5)
        
        # Fill email
        email_el = await page.query_selector('input[type="email"]')
        if not email_el:
            email_el = await page.query_selector('#email')
        if not email_el:
            email_el = await page.query_selector('input[name="email"]')
        if email_el:
            await email_el.click()
            await email_el.fill(email)
            await asyncio.sleep(0.1)
        
        # Click register
        btns = ['button[type="submit"]', 'button:has-text("Register")', 
                'button:has-text("Continue")', 'button:has-text("Get API Key")',
                'input[type="submit"]']
        clicked = False
        for sel in btns:
            btn = await page.query_selector(sel)
            if btn:
                await btn.click()
                await asyncio.sleep(1)
                clicked = True
                break
        
        if not clicked:
            # Try any button
            btns_all = await page.query_selector_all('button')
            for b in btns_all:
                txt = await b.text_content()
                if 'register' in txt.lower() or 'continue' in txt.lower():
                    await b.click()
                    await asyncio.sleep(1)
                    break
        
        # Get response
        body_text = await page.evaluate('() => document.body.innerText')
        api_key = extract_api_key(body_text)
        
        if api_key:
            save_key('NewsAPI', email, api_key)
            save_reg('NewsAPI', email, 'REGISTERED+KEY')
            log(f"OK+KEY news {tag}")
        else:
            save_reg('NewsAPI', email, 'REGISTERED')
            log(f"OK news {tag}")
        return True
    except Exception as e:
        save_reg('NewsAPI', email, 'FAIL')
        log(f"FAIL news {tag}")
        return False

async def register_weatherapi(page, tag):
    """Register on WeatherAPI"""
    email = gmail(tag)
    try:
        await page.goto('https://www.weatherapi.com/signup.aspx', 
                       wait_until='domcontentloaded', timeout=15000)
        await asyncio.sleep(0.5)
        
        # Fill email
        for sel in ['input[type="email"]', '#email', 'input[name="email"]']:
            el = await page.query_selector(sel)
            if el and el.is_visible():
                await el.click()
                await el.fill(email)
                await asyncio.sleep(0.1)
                break
        
        # Click submit
        for sel in ['button[type="submit"]', 'input[type="submit"]',
                    'button:has-text("Sign Up")', 'button:has-text("Register")']:
            btn = await page.query_selector(sel)
            if btn:
                await btn.click()
                await asyncio.sleep(1)
                break
        
        body_text = await page.evaluate('() => document.body.innerText')
        api_key = extract_api_key(body_text)
        
        if api_key:
            save_key('WeatherAPI', email, api_key)
            save_reg('WeatherAPI', email, 'REGISTERED+KEY')
            log(f"OK+KEY weather {tag}")
        else:
            save_reg('WeatherAPI', email, 'REGISTERED')
            log(f"OK weather {tag}")
        return True
    except:
        save_reg('WeatherAPI', email, 'FAIL')
        return False

async def main():
    log("="*60)
    log("HYPER SPEED v3 - CAPTURING API KEYS FROM PAGES")
    log(f"Target: 1000 each service")
    log(f"Existing: fd={sum(1 for r in all_regs if r['service']=='football-data.org')}, "
         f"news={sum(1 for r in all_regs if r['service']=='NewsAPI')}")
    log("="*60)
    
    from playwright.async_api import async_playwright
    
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True, 
        args=['--disable-blink-features=AutomationControlled',
              '--no-sandbox', '--disable-dev-shm-usage'])
    context = await browser.new_context(viewport={'width': 1280, 'height': 720})
    page = await context.new_page()
    
    # Track existing counts
    existing_fd = sum(1 for r in all_regs if r['service'] == 'football-data.org')
    existing_news = sum(1 for r in all_regs if r['service'] == 'NewsAPI')
    existing_weather = sum(1 for r in all_regs if r['service'] == 'WeatherAPI')
    
    TARGET = 1000
    
    # PHASE 1: football-data.org
    if existing_fd < TARGET:
        log(f"\nPHASE 1: football-data.org {existing_fd} -> {TARGET}")
        for i in range(existing_fd + 1, TARGET + 1):
            await register_fd(page, f"fd{i}")
            await asyncio.sleep(random.uniform(0.2, 0.5))
            if i % 100 == 0:
                log(f"  *** FD {i}/{TARGET} ***")
    
    # PHASE 2: NewsAPI
    if existing_news < TARGET:
        log(f"\nPHASE 2: NewsAPI {existing_news} -> {TARGET}")
        for i in range(existing_news + 1, TARGET + 1):
            await register_newsapi(page, f"news{i}")
            await asyncio.sleep(random.uniform(0.3, 0.7))
            if i % 100 == 0:
                log(f"  *** NewsAPI {i}/{TARGET} ***")
    
    # PHASE 3: WeatherAPI
    if existing_weather < TARGET:
        log(f"\nPHASE 3: WeatherAPI {existing_weather} -> {TARGET}")
        for i in range(existing_weather + 1, TARGET + 1):
            await register_weatherapi(page, f"weather{i}")
            await asyncio.sleep(random.uniform(0.3, 0.6))
            if i % 100 == 0:
                log(f"  *** WeatherAPI {i}/{TARGET} ***")
    
    await browser.close()
    await pw.stop()
    
    # Final
    with open(REG_FILE) as f: final_regs = json.load(f)
    with open(KEYS_FILE) as f: final_keys = json.load(f)
    log(f"\nFINAL: {len(final_regs)} regs, {len(final_keys)} keys captured!")
    log(f"  fd={sum(1 for r in final_regs if r['service']=='football-data.org')}")
    log(f"  news={sum(1 for r in final_regs if r['service']=='NewsAPI')}")
    log(f"  keys={len(final_keys)}")

if __name__ == "__main__":
    asyncio.run(main())
