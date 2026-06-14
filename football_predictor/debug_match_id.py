"""Check match ID mapping"""
import urllib.request, json, re

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.6099.230'}

# Match 4813374 from league overview
print('=== Match 4813374 ===')
html = urllib.request.urlopen(urllib.request.Request('https://www.fotmob.com/match/4813374', headers=headers), timeout=15).read().decode('utf-8')
nd = json.loads(re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL).group(1))
general1 = nd['props']['pageProps']['general']
content1 = nd['props']['pageProps']['content']
print(f'general.matchId: {general1.get("matchId")}')
print(f'general.matchRound: {general1.get("matchRound")}')
print(f'home: {general1.get("homeTeam",{}).get("name")}')
print(f'away: {general1.get("awayTeam",{}).get("name")}')

# Try Next.js data route for 4813374
build_id = nd.get('buildId', '')
print(f'\n=== Next.js data route for 4813374 ===')
try:
    r = urllib.request.urlopen(urllib.request.Request(
        f'https://www.fotmob.com/_next/data/{build_id}/matches/4813374.json',
        headers=headers), timeout=10)
    d = json.loads(r.read().decode('utf-8'))
    pp = d.get('pageProps', {})
    print(f'pageProps keys: {list(pp.keys())[:10]}')
    g = pp.get('general', {})
    print(f'matchId: {g.get("matchId")}')
except Exception as e:
    print(f'Error: {e}')

# Try the h2h slug from the league page
print(f'\n=== League page first match pageUrl ===')
html2 = urllib.request.urlopen(urllib.request.Request('https://www.fotmob.com/leagues/47', headers=headers), timeout=15).read().decode('utf-8')
nd2 = json.loads(re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html2, re.DOTALL).group(1))
first_match = nd2['props']['pageProps']['overview']['leagueOverviewMatches'][0]
page_url = first_match.get('pageUrl', '?')
print(f'pageUrl: {page_url}')
# Remove hash
if '#' in page_url:
    slug = page_url.split('#')[0]
    print(f'slug: {slug}')
    actual_url = f'https://www.fotmob.com{slug}'
    print(f'actual URL: {actual_url}')
    html3 = urllib.request.urlopen(urllib.request.Request(actual_url, headers=headers), timeout=15).read().decode('utf-8')
    nd3 = json.loads(re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html3, re.DOTALL).group(1))
    g3 = nd3['props']['pageProps']['general']
    c3 = nd3['props']['pageProps']['content']
    print(f'general.matchId: {g3.get("matchId")}')
    print(f'home: {g3.get("homeTeam",{}).get("name")}')
    print(f'away: {g3.get("awayTeam",{}).get("name")}')
    # Find score
    events = c3.get('matchFacts', {}).get('events', {}).get('events', [])
    if events:
        print(f'Events: {len(events)}')
        last_event = events[-1]
        print(f'Last event newScore: {last_event.get("newScore")}')
        # Find goals to count
        goals_home = sum(1 for e in events if e.get('type') == 'Goal' and e.get('isHome'))
        goals_away = sum(1 for e in events if e.get('type') == 'Goal' and not e.get('isHome'))
        print(f'Goals: {goals_home} - {goals_away}')
        # Also check topScorers
        # topScorers = c3.get('matchFacts', {}).get('topScorers', {})
        # print(f'topScorers: {topScorers}')
