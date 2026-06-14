"""Direct FotMob API test - all known patterns"""
import requests, json, re

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 14; Pixel 9 Pro) AppleWebKit/537.36 Chrome/120.0.6099.230 Mobile Safari/537.36',
    'Accept': 'application/json',
    'Accept-Language': 'en-US,en;q=0.9',
}

# Get homepage first to find buildId for Next.js data routes
print('=== Homepage ===')
r = requests.get('https://www.fotmob.com', headers=HEADERS, timeout=15)
# Find Next.js build id
next_data = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
if next_data:
    nd = json.loads(next_data.group(1))
    build_id = nd.get('buildId', '')
    print(f'Build ID: {build_id}')
else:
    build_id = ''
    print('No __NEXT_DATA__')

# Test multiple API URL patterns
print('\n=== API endpoint tests ===')
tests = []

# Mobile API patterns (commonly documented)
for domain in ['api.fotmob.com', 'apigw.fotmob.com', 'www.fotmob.com']:
    for path in ['/v1/matches', '/api/matches', '/api/getMatches']:
        tests.append((f'https://{domain}{path}', {'date': '20260613'}))

# Next.js data routes
if build_id:
    tests.append((f'https://www.fotmob.com/_next/data/{build_id}/matches.json', {'date': '20260613'}))

# League data
for domain in ['api.fotmob.com', 'www.fotmob.com']:
    for path in ['/v1/league', '/api/league', '/api/standings']:
        tests.append((f'https://{domain}{path}', {'id': '47'}))

for url, params in tests:
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        ct = r.headers.get('Content-Type', '')
        if r.status_code in [200, 401, 403]:
            try:
                d = r.json()
                keys = list(d.keys())[:5]
                print(f'200 {url[:60]:60s} keys={keys}')
            except:
                print(f'{r.status_code} {url[:60]:60s} ({len(r.text)} bytes) not-json')
    except Exception as e:
        pass  # skip errors

# Try curl_cffi on the web API
print('\n=== curl_cffi test ===')
try:
    from curl_cffi import requests as curl_requests
    r = curl_requests.get(
        'https://www.fotmob.com/api/matchDetails',
        params={'matchId': 4216652},
        headers=HEADERS,
        impersonate='chrome120',
        timeout=15
    )
    print(f'curl_cffi matchDetails: {r.status_code}')
    if r.status_code == 200:
        d = r.json()
        print(f'  keys={list(d.keys())[:5]}')
except Exception as e:
    print(f'curl_cffi: {e}')
