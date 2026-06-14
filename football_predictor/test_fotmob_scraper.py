"""Test full FotMob scraper"""
from fotmob_scraper import *

import sys
sys.stdout.reconfigure(encoding='utf-8')

# 1. Test match data extraction on a finished match
mid = 4813374
print(f'=== Testing match {mid} ===')
md = get_match_data(mid)
if md:
    print(f'Teams: {md["home_team"]} vs {md["away_team"]}')
    print(f'IDs: {md["home_id"]} vs {md["away_id"]}')
    
    # Stats
    stats = extract_match_stats(md['content'])
    print(f'\n=== Stats (All period) ===')
    for k, v in stats.items():
        if k.startswith('All_'):
            print(f'  {k[4:]}: {v}')
    
    # xG
    xg = extract_xg(md['content'])
    print(f'\n=== xG ===')
    for k, v in xg.items():
        print(f'  {k}: {v}')
    
    # H2H
    h2h = extract_h2h(md['content'])
    print(f'\n=== H2H ===')
    print(f'  Total: {h2h["total_matches"]} (H: {h2h["home_wins"]}, D: {h2h["draws"]}, A: {h2h["away_wins"]})')
    for m in h2h['recent_matches'][:3]:
        print(f'  {m["date"]} {m["home"]} {m["home_score"]}-{m["away_score"]} {m["away"]}')
    
    # Form
    form = extract_team_form(md['content'])
    print(f'\n=== Form ===')
    for team, fdata in form.items():
        print(f'  {team}: {fdata["form"]}')
    
    # Momentum
    mom = extract_momentum(md['content'])
    print(f'\n=== Momentum ===')
    print(f'  Home win: {mom["home_win"]}, Draw: {mom["draw"]}, Away win: {mom["away_win"]}')

# 2. Test league data
print(f'\n=== League 47 (EPL) ===')
data = get_league_data(47)
if data:
    overview = data.get('overview', {})
    season = overview.get('season', '?')
    matches = overview.get('leagueOverviewMatches', [])
    print(f'Season: {season}, Matches: {len(matches)}')
    
    # Table
    table_data = data.get('table', [])
    if table_data and isinstance(table_data, list):
        for tbl in table_data[:1]:
            rows = tbl.get('rows', [])
            print(f'League table ({len(rows)} teams):')
            for row in rows[:5]:
                t = row.get('team', {})
                print(f'  {row.get("position","?")}. {t.get("name","?")} - {row.get("pts","?")} pts')

# 3. Test finished matches
print(f'\n=== Recent finished matches ===')
finished = get_finished_matches(limit=5)
print(f'Found {len(finished)} finished matches')
for m in finished[:5]:
    print(f'  {m["id"]} {m["home"]["name"]} {m["home"]["score"]}-{m["away"]["score"]} {m["away"]["name"]}')
