#!/usr/bin/env python3
"""Phase 2: FBref Cloudflare Bypass - All 3 layers."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
print('PHASE 2: FBref - 3-Layer Cloudflare Bypass')
print('=' * 60)

import os, time, json, hashlib, socket, sqlite3, urllib.request, ssl
from datetime import datetime

BASE = r'C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor'
DB_PATH = os.path.join(BASE, 'scrape_cache.db')

# ── LAYER 1: Origin IP Discovery ──
print('\n--- Layer 1: Origin IP Discovery ---')

# Try direct DNS + known historical IPs
candidates = []
for sub in ['fbref.com', 'www.fbref.com', 'stats.fbref.com', 'data.fbref.com']:
    try:
        ips = set()
        for info in socket.getaddrinfo(sub, 443):
            ips.add(info[4][0])
        for ip in sorted(ips):
            if ip not in candidates:
                candidates.append(ip)
                print(f'  DNS: {sub} -> {ip}')
    except:
        pass

# Known historical Sports-Reference IPs
historical = ['198.58.118.167', '198.58.118.168', '45.33.32.156', '45.33.32.157',
              '72.14.178.100', '72.14.178.101', '104.16.0.0']
for ip in historical:
    if ip not in candidates:
        candidates.append(ip)
        print(f'  Historical: {ip}')

# Test candidates
print('\nTesting origin IPs...')
paths = ['/', '/en/comps/9/stats/Premier-League-Stats']
found_ip = None

for ip in candidates[:10]:
    for path in paths[:1]:
        for proto_port in [('http', 80), ('https', 443)]:
            proto, port = proto_port
            url = f'{proto}://{ip}:{port}{path}'
            try:
                ctx = ssl._create_unverified_context() if proto == 'https' else None
                req = urllib.request.Request(url, headers={
                    'Host': 'fbref.com',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
                    'Accept': 'text/html,*/*',
                })
                with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                    body = resp.read(2000)
                    if b'sports-reference' in body.lower() or b'fbref' in body.lower():
                        print(f'  *** ORIGIN FOUND: {ip}:{port} ***')
                        found_ip = ip
                        break
            except:
                pass
        if found_ip:
            break
    if found_ip:
        break

if not found_ip:
    print('  No origin IP found via direct connection.')

# ── LAYER 2a: curl_cffi impersonation ──
print('\n--- Layer 2a: curl_cffi Chrome impersonation ---')

try:
    from curl_cffi import requests as curl_requests
    
    urls_to_try = [
        'https://fbref.com/en/comps/9/stats/Premier-League-Stats',
        'https://fbref.com/en/comps/12/stats/La-Liga-Stats',
        'https://fbref.com/',
    ]
    
    impersonates = ['chrome120', 'chrome131', 'chrome110', 'safari15_5', 'edge101']
    
    for url in urls_to_try:
        for imp in impersonates:
            try:
                session = curl_requests.Session()
                resp = session.get(url, impersonate=imp, timeout=15,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
                        'Accept': 'text/html,application/xhtml+xml,*/*',
                    })
                
                if resp.status_code == 200:
                    html = resp.text
                    if 'sports-reference' in html.lower() and len(html) > 5000:
                        print(f'  *** curl_cffi {imp} SUCCESS for {url.split('/')[-1]} ***')
                        print(f'      HTML size: {len(html)} bytes')
                        
                        # Save to file
                        safe_name = url.replace('https://', '').replace('/', '_')[:50]
                        with open(os.path.join(BASE, 'heist_output', f'fbref_{safe_name}.html'), 'w', encoding='utf-8') as f:
                            f.write(html)
                        print(f'      Saved to heist_output/fbref_{safe_name}.html')
                        found_ip = 'curl_cffi'
                        break
                    else:
                        print(f'  curl_cffi {imp}: got 200 but suspicious content ({len(html)} bytes)')
                elif resp.status_code == 403:
                    print(f'  curl_cffi {imp}: HTTP 403 (Cloudflare)')
                else:
                    print(f'  curl_cffi {imp}: HTTP {resp.status_code}')
                
                time.sleep(1)
            except Exception as e:
                print(f'  curl_cffi {imp}: {str(e)[:60]}')
        
        if found_ip == 'curl_cffi':
            break
    
except ImportError:
    print('  curl_cffi not available')

# ── LAYER 2b: tls_client ──
if not found_ip:
    print('\n--- Layer 2b: tls_client JA3 spoof ---')
    try:
        import tls_client
        
        session = tls_client.Session(client_identifier='chrome_131', random_tls_extension_order=True)
        session.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'text/html,*/*',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        url = 'https://fbref.com/en/comps/9/stats/Premier-League-Stats'
        resp = session.get(url, timeout_seconds=20)
        
        if resp.status_code == 200:
            html = resp.text if hasattr(resp, 'text') else resp.content
            if 'sports-reference' in str(html).lower():
                print(f'  *** tls_client SUCCESS! HTML size: {len(str(html))} ***')
                found_ip = 'tls_client'
            else:
                print(f'  tls_client: got 200 but suspicious content')
        else:
            print(f'  tls_client: HTTP {resp.status_code}')
            
    except ImportError:
        print('  tls_client not available')
    except Exception as e:
        print(f'  tls_client error: {e}')

# ── LAYER 3: Google Translate Proxy ──
if not found_ip:
    print('\n--- Layer 3: Google Translate Proxy ---')
    try:
        translate_url = 'https://translate.google.com/translate?hl=en&sl=en&tl=en&u=https://fbref.com/en/comps/9/stats/Premier-League-Stats&sandbox=1'
        req = urllib.request.Request(translate_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='replace')
            if 'sports-reference' in html.lower() and len(html) > 5000:
                print(f'  *** Google Translate PROXY SUCCESS! ***')
                # Save
                with open(os.path.join(BASE, 'heist_output', 'fbref_google_translate.html'), 'w', encoding='utf-8') as f:
                    f.write(html)
                found_ip = 'proxy'
            else:
                print(f'  Google Translate: got response but content suspicious ({len(html)} bytes)')
    except Exception as e:
        print(f'  Google Translate proxy: {e}')

# ── SUMMARY ──
print(f'\n=== FBref Bypass Result ===')
if found_ip:
    print(f'  ✅ SUCCESS via: {found_ip}')
    print(f'  FBref is now accessible!')
else:
    print(f'  ❌ All bypass layers failed.')
    print(f'  💡 Recommended: Deploy Cloudflare Worker proxy:')
    print(f'     wrangler deploy heist_output/fbref_worker.js --name fbref-proxy')

# Write result for the calling process
result = {'success': bool(found_ip), 'method': found_ip, 'timestamp': datetime.now().isoformat()}
with open(os.path.join(BASE, 'heist_output', 'fbref_bypass_result.json'), 'w') as f:
    json.dump(result, f)

print(f'\nResult saved to heist_output/fbref_bypass_result.json')
