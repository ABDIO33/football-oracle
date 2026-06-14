"""Try all FotMob approaches"""
import requests, json, re

BASE = 'https://www.fotmob.com'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

# 1. Try npm package via subprocess (if node is available)
import subprocess
try:
    r = subprocess.run(['node', '-e', 'const f = require("fotmob"); f.getMatches("20260613").then(console.log).catch(console.error)'], 
                       capture_output=True, text=True, timeout=15)
    print(f'npm fotmob: {r.stdout[:500] if r.stdout else r.stderr[:500]}')
except Exception as e:
    print(f'npm fotmob: not available ({e})')

# 2. Try fetching homepage and extracting __NEXT_DATA__ for API info
print('\n=== Homepage check ===')
r = requests.get(BASE, headers=HEADERS, timeout=15)
scripts = re.findall(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
if scripts:
    next_data = json.loads(scripts[0])
    print(f'Next.js buildId: {next_data.get("buildId","?")}')
    print(f'Props keys: {list(next_data.get("props",{}).keys())[:5]}')

# 3. Try known third-party fotmob API endpoints (community documented)
print('\n=== Community API endpoints ===')
api_tests = [
    ('https://api.fotmob.com/v1/matches', {'date': '20260613'}, 'v1 matches'),
    ('https://api.fotmob.com/v1/match', {'id': '4216652'}, 'v1 match'),
    ('https://apigw.fotmob.com/v1/matches', {'date': '20260613'}, 'apigw matches'),
    ('https://apigw.fotmob.com/v1/match', {'id': '4216652'}, 'apigw match'),
    ('https://www.fotmob.com/_next/data/.../matches.json', {}, 'next data'),
]

for url, params, desc in api_tests:
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        ct = r.headers.get('Content-Type', '')
        print(f'{desc:30s} {r.status_code} json={"json" in ct}', end='')
        if r.status_code == 200:
            print(f'  ({len(r.text)} bytes)', end='')
        print()
    except Exception as e:
        print(f'{desc:30s} ERROR {e}')

# 4. Try with x-fm-req header (value from DeepSeek)
print('\n=== x-fm-req header test ===')
for val in ['1', 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9']:
    h = HEADERS.copy()
    h['x-fm-req'] = val
    try:
        r = requests.get(f'{BASE}/api/matches', headers=h, params={'date': '20260613'}, timeout=10)
        print(f'x-fm-req={val[:20]}...  {r.status_code} ({len(r.text)} bytes)')
        if r.status_code == 200:
            try:
                d = r.json()
                print(f'  keys={list(d.keys())[:5]}')
            except:
                print(f'  HTML: {r.text[:100]}')
    except Exception as e:
        print(f'x-fm-req={val[:20]}...  ERROR {e}')

# 5. Try the mobile app API endpoints
print('\n=== Mobile app API ===')
mobile_tests = [
    ('https://www.fotmob.com/api/matchDetails', {'matchId': 4216652}, 'web matchDetails'),
    ('https://www.fotmob.com/api/getMatches', {'date': '20260613'}, 'web getMatches'),
    ('https://www.fotmob.com/api/standings', {'leagueId': 47}, 'web standings'),
]
for url, params, desc in mobile_tests:
    for xfm in ['1', 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9']:
        h = HEADERS.copy()
        h['x-fm-req'] = xfm
        try:
            r = requests.get(url, headers=h, params=params, timeout=10)
            ct = r.headers.get('Content-Type', '')
            if r.status_code == 200:
                try:
                    d = r.json()
                    print(f'{desc:30s} xfm={xfm[:15]}  200 JSON keys={list(d.keys())[:3]}')
                except:
                    print(f'{desc:30s} xfm={xfm[:15]}  200 (not json)')
            elif r.status_code == 404:
                pass  # Skip 404s
            else:
                print(f'{desc:30s} xfm={xfm[:15]}  {r.status_code}')
        except Exception as e:
            print(f'{desc:30s} xfm={xfm[:15]}  ERROR {e}')
