"""Debug FotMob league page"""
import urllib.request, json, re

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.6099.230',
}

url = 'https://www.fotmob.com/leagues/47'
req = urllib.request.Request(url, headers=headers)
resp = urllib.request.urlopen(req, timeout=15)
html = resp.read().decode('utf-8')

print(f'URL: {url}')
print(f'Status: {resp.status}')
print(f'HTML length: {len(html)}')
print(f'Contains __NEXT_DATA__: {"__NEXT_DATA__" in html}')

# Find __NEXT_DATA__
match = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
if match:
    nd = json.loads(match.group(1))
    pp = nd.get('props', {}).get('pageProps', {})
    print(f'\npageProps keys: {list(pp.keys())}')
    
    ov = pp.get('overview', {})
    print(f'overview keys: {list(ov.keys())[:10]}')
    
    league_matches = ov.get('leagueOverviewMatches', [])
    print(f'leagueOverviewMatches: {len(league_matches)}')
    
    # Also check matches key
    matches_dict = pp.get('matches', {})
    if isinstance(matches_dict, dict):
        am = matches_dict.get('allMatches', [])
        print(f'matches.allMatches: {len(am) if isinstance(am, list) else type(am).__name__}')
    
    # Check the next data route
    build_id = nd.get('buildId', '')
    print(f'\nBuild ID: {build_id}')
    
    url2 = f'https://www.fotmob.com/_next/data/{build_id}/leagues/47.json?tab=overview&type=league&timeZone=UTC'
    req2 = urllib.request.Request(url2, headers=headers)
    resp2 = urllib.request.urlopen(req2, timeout=15)
    data2 = json.loads(resp2.read().decode('utf-8'))
    pp2 = data2.get('pageProps', {})
    print(f'\nNext.js data route pageProps keys: {list(pp2.keys())}')
    
    ov2 = pp2.get('overview', {})
    print(f'overview keys: {list(ov2.keys())[:10]}')
    
    league_matches2 = ov2.get('leagueOverviewMatches', [])
    print(f'leagueOverviewMatches: {len(league_matches2)}')
    if league_matches2:
        print(f'First match: {json.dumps(league_matches2[0], indent=2)[:500]}')
else:
    print('No __NEXT_DATA__ found')
    # Check what's in the page
    if 'FotMob' in html:
        print('Page contains FotMob text')
    # Look for any script tags with data
    scripts = re.findall(r'<script[^>]*id="([^"]*)"[^>]*>', html)
    print(f'Script IDs: {scripts[:10]}')
