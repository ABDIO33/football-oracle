"""Extract xG stats and key prediction data from FotMob"""
import requests, json, re

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.6099.230',
}

def get_match_pageprops(mid):
    r = requests.get(f'https://www.fotmob.com/match/{mid}', headers=headers, timeout=15)
    nd = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
    return json.loads(nd.group(1))['props']['pageProps']

mid = 4813374
pp = get_match_pageprops(mid)
c = pp.get('content', {})
general = pp.get('general', {})

# 1. xG from shotmap
shotmap = c.get('shotmap', {})
shots = shotmap.get('shots', [])
print(f'=== Shotmap: {len(shots)} shots ===')
home_xg = sum(s.get('expectedGoals', 0) for s in shots if s.get('isHome'))
away_xg = sum(s.get('expectedGoals', 0) for s in shots if not s.get('isHome'))
print(f'  Home xG: {home_xg:.2f} ({sum(1 for s in shots if s.get("isHome"))} shots)')
print(f'  Away xG: {away_xg:.2f} ({sum(1 for s in shots if not s.get("isHome"))} shots)')
for s in shots[:5]:
    player = s.get('player', {}).get('name', '?')
    xg = s.get('expectedGoals', 0)
    is_home = s.get('isHome', False)
    minute = s.get('minute', '?')
    print(f'  {minute}\' {player} xG={xg:.3f} {"HOME" if is_home else "AWAY"}')

# 2. Match stats
stats = c.get('stats', {})
periods = stats.get('Periods', {})
print(f'\n=== Match Stats ===')
for period_name, period_data in periods.items():
    print(f'\n  Period: {period_name}')
    for stat_group in period_data.get('stats', []):
        title = stat_group.get('title', '?')
        print(f'    {title}:')
        for s in stat_group.get('stats', []):
            stitle = s.get('title', '?')
            sstats = s.get('stats', [])
            if len(sstats) == 2:
                print(f'      {stitle}: {sstats[0]} - {sstats[1]}')

# 3. Team form
match_facts = c.get('matchFacts', {})
team_form = match_facts.get('teamForm', {})
print(f'\n=== Team Form ===')
for team_key, form_data in team_form.items():
    form = form_data.get('form', [])
    name = form_data.get('name', '?')
    matches = form_data.get('matches', [])
    print(f'  {name}: form={form}')
    if matches:
        for m in matches[:3]:
            opp = m.get('opponent', {}).get('name', '?')
            res = m.get('result', '?')
            score = f'{m.get("score",{}).get("home","?")}-{m.get("score",{}).get("away","?")}'
            date = m.get('matchDateUTC', '?')
            print(f'    vs {opp}: {res} {score} ({date})')

# 4. Expected goals from players  
print(f'\n=== Player xG ===')
player_stats = c.get('playerStats', {})
for team_id, team_players in player_stats.items():
    if isinstance(team_players, dict) and 'players' in team_players:
        players = team_players['players']
    elif isinstance(team_players, list):
        players = team_players
    else:
        continue
    for p in players:
        if isinstance(p, dict):
            name = p.get('name', p.get('player', {}).get('name', '?'))
            xg = p.get('expectedGoals', p.get('stats', {}).get('expectedGoals', None))
            if xg is not None:
                print(f'  {name}: xG={xg}')

# 5. H2H
h2h = c.get('h2h', {})
print(f'\n=== H2H ===')
summary = h2h.get('summary', {})
print(f'  Total matches: {summary.get("totalMatches","?")}')
print(f'  Home wins: {summary.get("homeWins","?")}')
print(f'  Away wins: {summary.get("awayWins","?")}')
print(f'  Draws: {summary.get("draws","?")}')
matches_h2h = h2h.get('matches', [])
print(f'  Last {len(matches_h2h)} matches:')
for m in matches_h2h[:5]:
    home = m.get('home', {}).get('name', '?')
    away = m.get('away', {}).get('name', '?')
    hs = m.get('home', {}).get('score', '?')
    aws = m.get('away', {}).get('score', '?')
    league = m.get('leagueName', m.get('tournament', {}).get('name', '?'))
    date = m.get('matchDateUTC', '?')
    print(f'    {date} {home} {hs}-{aws} {away} ({league})')

# 6. Momentum (win probability)
momentum = c.get('momentum', {})
print(f'\n=== Momentum ===')
main = momentum.get('main', {})
if main:
    print(f'  homeWin: {main.get("homeWin","?")}')
    print(f'  awayWin: {main.get("awayWin","?")}')
    print(f'  draw: {main.get("draw","?")}')
    xg_momentum = main.get('xgMomentum', [])
    print(f'  xgMomentum: {len(xg_momentum)} points')
    if xg_momentum:
        print(f'    first: {json.dumps(xg_momentum[0])[:100]}')
