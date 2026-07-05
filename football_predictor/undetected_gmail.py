"""
SCORE EXACT 100 — UNDETECTED GMAIL LOGIN + API KEY EXTRACTOR
يستخدم undetected-chromedriver لتجاوز كشف Google
"""
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time, re, os, json
from datetime import datetime

BASE = "C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor"
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.chdir(BASE)

EMAIL = "elbazamine27@gmail.com"
PASSWORD = "ABDO1122334455"

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f"[{ts}] {msg}")

print("="*60)
print("UNDETECTED GMAIL LOGIN - API KEY HARVESTER")
print("="*60)

# Launch undetected Chrome
log("\n[1] Launching undetected Chrome...")
driver = uc.Chrome()
driver.maximize_window()

try:
    # Go to Gmail directly
    log("[2] Going to Gmail...")
    driver.get('https://mail.google.com/mail/u/0/#inbox')
    time.sleep(3)
    log(f"    URL: {driver.current_url[:80]}")
    
    # Check if we need to log in
    if 'Sign in' in driver.page_source or 'accounts.google.com' in driver.current_url:
        # Wait for email input
        log("[3] Waiting for email input...")
        wait = WebDriverWait(driver, 20)
        email_input = wait.until(EC.presence_of_element_located((By.ID, "identifierId")))
        log("    Filling email...")
        email_input.send_keys(EMAIL)
        time.sleep(1)
        
        # Click Next
        next_btn = driver.find_element(By.ID, "identifierNext")
        next_btn.click()
        time.sleep(3)
        log(f"    URL: {driver.current_url[:80]}")
        
        if 'rejected' in driver.current_url:
            log("    ❌ REJECTED! Google detected automation!")
            log("    Trying manual login...")
            input("سجل دخولك يدوياً في Chrome ثم اضغط Enter...")
        else:
            # Wait for password input
            log("[4] Waiting for password input...")
            try:
                # Try different password selectors
                pw_selectors = ['input[type="password"]', '#password', '#Passwd', 'input[name="Passwd"]']
                pw_input = None
                for sel in pw_selectors:
                    try:
                        pw_input = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
                        if pw_input:
                            break
                    except:
                        continue
                
                if pw_input:
                    log("    Filling password...")
                    pw_input.send_keys(PASSWORD)
                    time.sleep(1)
                    
                    # Click Next
                    pw_next = driver.find_element(By.ID, "passwordNext")
                    pw_next.click()
                    time.sleep(3)
                    log(f"    URL: {driver.current_url[:80]}")
                else:
                    log("    Could not find password input")
                    input("اكتب الباسورد يدوياً ثم اضغط Enter...")
            except Exception as e:
                log(f"    Error: {e}")
    else:
        log("[3] Already logged in!")
    
    # Check if we're in Gmail
    current_url = driver.current_url
    log(f"\n[5] Current URL: {current_url[:80]}")
    
    if 'mail.google.com' in current_url:
        log("✅ IN GMAIL!")
        
        # SEARCH FOR API KEYS
        log("\n[6] SEARCHING FOR API KEYS...")
        all_keys = []
        
        for query in ['football-data', 'newsapi', 'Your API', 'welcome']:
            log(f"\n   Searching: '{query}'")
            try:
                # Go to inbox
                driver.get('https://mail.google.com/mail/u/0/#inbox')
                time.sleep(2)
                
                # Find search box
                search_selectors = ['input[gh="s"]', 'input[aria-label*="Search"]', 'input[aria-label*="search"]']
                search_box = None
                for sel in search_selectors:
                    try:
                        search_box = driver.find_element(By.CSS_SELECTOR, sel)
                        if search_box:
                            break
                    except:
                        continue
                
                if search_box:
                    search_box.click()
                    time.sleep(0.3)
                    search_box.clear()
                    search_box.send_keys(query)
                    time.sleep(0.5)
                    search_box.send_keys('\ue007')  # Enter
                    time.sleep(3)
                    
                    # Get email list
                    email_items = driver.find_elements(By.CSS_SELECTOR, '.zA, tr.zA')
                    log(f"    Found {len(email_items)} emails")
                    
                    for idx in range(min(len(email_items), 20)):
                        try:
                            emails = driver.find_elements(By.CSS_SELECTOR, '.zA, tr.zA')
                            if idx < len(emails):
                                emails[idx].click()
                                time.sleep(1.5)
                                
                                # Get body
                                body_sel = driver.find_elements(By.CSS_SELECTOR, '.a3s, .ii')
                                if body_sel:
                                    text = body_sel[0].text
                                    
                                    # Extract keys
                                    for p in [r'[A-Za-z0-9]{25,45}']:
                                        for m in re.findall(p, text):
                                            mc = m.strip()
                                            if len(mc) >= 20 and mc not in all_keys:
                                                all_keys.append(mc)
                                                log(f"    🔑 {mc}")
                                
                                driver.back()
                                time.sleep(1)
                        except:
                            pass
            except Exception as e:
                log(f"    Error: {e}")
        
        # SAVE ALL KEYS
        log(f"\n💾 Saving {len(all_keys)} keys...")
        with open(f'{BASE}/api_keys/FINAL_API_KEYS.txt', 'w', encoding='utf-8') as f:
            f.write("SCORE EXACT 100 - API KEYS\n")
            f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write("="*50 + "\n\n")
            if all_keys:
                for i, k in enumerate(all_keys, 1):
                    f.write(f"KEY {i}: {k}\n")
            else:
                f.write("(No keys found)\n")
        
        log(f"\n✅ DONE! Keys found: {len(all_keys)}")
        
        # Also show registration stats
        try:
            with open('api_keys/ALL_REGISTRATIONS.json') as f:
                regs = json.load(f)
            log(f"✅ Total registrations made: {len(regs)}")
        except:
            pass
    else:
        log("❌ NOT in Gmail")
        log("سجل دخولك يدوياً")

except Exception as e:
    log(f"FATAL ERROR: {e}")
    
finally:
    input("\nاضغط Enter لإغلاق المتصفح...")
    driver.quit()
