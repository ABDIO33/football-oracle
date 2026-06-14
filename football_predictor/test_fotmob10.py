"""Extract fixtures from FotMob - fixed"""
import requests, json

headers = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 14; Pixel 9 Pro) Chrome/120 Mobile',
    'Accept': 'application/json',
}
build_id = 'UkUOCnsJno2QeGq1r_43R'

r = requests.get(
    f'https://www.fotmob.com/_next/data/{build_id}/leagues/47.json',
    params={'tab': 'overview', 'type': 'league'},
    headers=headers, timeout=15
)
data = r.json()
pp = data.get('pageProps', {})

# 1. Fixtures
fixtures = pp.get('fixtures', {})
all_matches = fixtures.get('allMatches', [])
first_unplayed = fixtures.get('firstUnplayedMatch')
print(f'=== Fixtures ===')
print(f'firstUnplayedMatch: {first_unplayed}')
print(f'allMatches type: {type(all_matches).__name__} len={len(all_matches) if isinstance(all_matches, list) else "?"}')

if isinstance(all_matches, list):
    for i, m in enumerate(all_matches[:5]):
        home = m.get('home', {}).get('name', '?')
        away = m.get('away', {}).get('name', '?')
        status = m.get('status', {}).get('reason', '?')
        home_score = m.get('home', {}).get('score', '')
        away_score = m.get('away', {}).get('score', '')
        mid = m.get('id', '?')
        date = m.get('matchDateUTC', m.get('dateUTC', '?'))
        print(f'  {i}: {date} {home} vs {away} {home_score}-{away_score} ({mid}) status={status}')
elif isinstance(all_matches, dict):
    for round_key, matches in list(all_matches.items())[:3]:
        print(f'  Round {round_key}: {len(matches)} matches')
        for m in matches[:3]:
            home = m.get('home', {}).get('name', '?')
            away = m.get('away', {}).get('name', '?')
            print(f'    {home} vs {away}')

# 2. Match details
if first_unplayed:
    print(f'\n\n=== Match {first_unplayed} ===')
    r = requests.get(
        f'https://www.fotmob.com/_next/data/{build_id}/matches/{first_unplayed}.json',
        headers=headers, timeout=15
    )
    md = r.json()
    pp2 = md.get('pageProps', {})
    print(f'pageProps keys: {list(pp2.keys())[:15]}')
    for k in pp2:
        v = pp2[k]
        if isinstance(v, dict):
            vkeys = list(v.keys())[:10]
            vsize = len(json.dumps(v))
            print(f'  {k}: dict keys={vkeys} size={vsize}')
            # Check if it has match data
            if 'general' in v:
                g = v['general']
                home = g.get('homeTeam', {}).get('name', '?')
                away = g.get('awayTeam', {}).get('name', '?')
                print(f'    --> {home} vs {away}')
        elif isinstance(v, list):
            print(f'  {k}: list len={len(v)}')

# 3. Overview data
overview = pp.get('overview', {})
print(f'\n=== Overview ===')
for k in overview:
    v = overview[k]
    if isinstance(v, dict):
        print(f'  {k}: dict keys={list(v.keys())[:5]}')
    elif isinstance(v, list):
        print(f'  {k}: list len={len(v)}')
    else:
        print(f'  {k}: {type(v).__name__}={v}')

# Extract table from overview
ov_table = overview.get('table', {})
if ov_table:
    print(f'\n  Table keys: {list(ov_table.keys())[:5]}')
    all_t = ov_table.get('allTables', [])
    if all_t:
        for tbl in all_t[:2]:
            rows = tbl.get('rows', tbl.get('table', []))
            print(f'    League {tbl.get("id","?")}: {len(rows)} teams')
            for row in rows[:5]:
                t = row.get('team', {})
                name = t.get('name', row.get('name', '?'))
                pts = row.get('pts', '?')
                print(f'      {name}: {pts} pts')

# 4. Check top players
top_players = overview.get('topPlayers', {})
if top_players:
    print(f'\n  TopPlayers keys: {list(top_players.keys())[:5]}')
    for k in ['goals', 'assists', 'rating']:
        players = top_players.get(k, [])
        if players:
            print(f'    {k}: {len(players)} players')
            for p in players[:3]:
                name = p.get('name', p.get('player', {}).get('name', '?'))
                val = p.get('stat', p.get('value', '?'))
                team = p.get('teamName', p.get('team', {}).get('name', '?'))
                print(f'      {name} ({team}): {val}')
