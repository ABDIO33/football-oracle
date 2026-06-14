"""Find match data API from FotMob HTML"""
import requests, json, re

headers = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 14; Pixel 9 Pro) Chrome/120 Mobile',
}

# 1. Get match HTML page
mid = 4813374
r = requests.get(f'https://www.fotmob.com/matches/{mid}', headers=headers, timeout=15)
html = r.text

# Find all API calls embedded in the page
# Look for fetch/axios calls
api_calls = re.findall(r'["\'](https?://[^"\']*api[^"\']*)["\']', html)
print(f'API calls found: {len(api_calls)}')
for api in set(api_calls[:20]):
    print(f'  {api}')

# Find __NEXT_DATA__
next_matches = re.findall(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
if next_matches:
    nd = json.loads(next_matches[0])
    build_id = nd.get('buildId', '')
    page = nd.get('page', '')
    query = nd.get('query', {})
    props = nd.get('props', {})
    print(f'\nNext.js: page={page} buildId={build_id}')
    print(f'query={query}')
    print(f'props keys={list(props.keys())[:10]}')
    
    # Check for matchId or slug in props
    for k in props:
        v = props[k]
        if isinstance(v, dict):
            print(f'  props.{k}: {list(v.keys())[:10]}')
        elif isinstance(v, list):
            print(f'  props.{k}: len={len(v)}')
        else:
            print(f'  props.{k}: {str(v)[:80]}')

# 2. Try the match detail API that the Next.js page calls
print('\n=== Client-side API calls ===')
# Try common patterns
apis = [
    f'https://www.fotmob.com/api/matchDetails?matchId={mid}',
    f'https://www.fotmob.com/api/matchData?id={mid}',
    f'https://www.fotmob.com/api/getMatchDetail?matchId={mid}',
    f'https://www.fotmob.com/api/match?matchId={mid}',
    f'https://www.fotmob.com/api/v1/match/{mid}',
]

for api in apis:
    try:
        r = requests.get(api, headers=headers, timeout=10)
        if r.status_code == 200:
            d = r.json()
            print(f'200 {api}')
            if isinstance(d, dict):
                print(f'  keys={list(d.keys())[:10]}')
        elif r.status_code == 404:
            pass
        else:
            print(f'{r.status_code} {api}')
    except Exception as e:
        print(f'ERR {api}: {e}')

# 3. Check JavaScript files for API endpoints
scripts = re.findall(r'src=["\'](/_next/static/chunks/[^"\']+)["\']', html)
print(f'\n=== Checking JS chunks for API patterns ({len(scripts[:5])}) ===')
for s in scripts[:3]:
    url = f'https://www.fotmob.com{s}'
    try:
        js = requests.get(url, headers=headers, timeout=10).text
        # Find API route patterns
        apis = set(re.findall(r'["\']/api/([^"\']+)["\']', js))
        if apis:
            print(f'  {s.split("/")[-1][:30]}: {apis}')
    except:
        pass
