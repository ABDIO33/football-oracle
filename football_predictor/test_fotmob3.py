"""Test fotmob Python library"""
from fotmob import FotMob

f = FotMob()

# 1. Get matches by date
try:
    matches = f.get_matches_by_date('20260613')
    print(f'Matches by date ({len(matches)}):')
    if isinstance(matches, dict):
        leagues = matches.get('leagues', [])
        print(f'  leagues={len(leagues)}')
        for l in leagues[:3]:
            name = l.get('leagueName', l.get('name', '?'))
            m_count = len(l.get('matches', []))
            print(f'  {name}: {m_count} matches')
except Exception as e:
    print(f'get_matches_by_date: ERROR {e}')

# 2. Get match details
try:
    md = f.get_match_details(4216652)
    print(f'\nMatch details keys: {list(md.keys())[:10]}')
    general = md.get('general', {})
    print(f'  {general.get("homeTeam",{}).get("name","?")} vs {general.get("awayTeam",{}).get("name","?")}')
    content = md.get('content', {})
    print(f'  content keys: {list(content.keys())[:5]}')
except Exception as e:
    print(f'get_match_details: ERROR {e}')

# 3. Get league standings
try:
    standings = f.get_standings(47)  # Premier League
    print(f'\nStandings type: {type(standings)}')
    if isinstance(standings, dict):
        tables = standings.get('standings', [])
        print(f'  tables={len(tables)}')
        if tables:
            table = tables[0].get('table', [])
            for t in table[:5]:
                print(f'  {t.get("rank","?")}. {t.get("name","?")} - {t.get("points","?")} pts')
except Exception as e:
    print(f'get_standings: ERROR {e}')

# 4. Get team info
try:
    team = f.get_team_info(9851)  # Barcelona
    print(f'\nTeam: {team.get("name","?")}')
except Exception as e:
    print(f'get_team_info: ERROR {e}')

# 5. Search
try:
    results = f.search('Barcelona')
    print(f'\nSearch: {len(results)} results')
    for r in results[:3]:
        print(f'  {r.get("name","?")} ({r.get("type","?")})')
except Exception as e:
    print(f'search: ERROR {e}')

# 6. Get league matches
try:
    league = f.get_league(47, '2025/2026')
    print(f'\nLeague keys: {list(league.keys())[:5]}')
except Exception as e:
    print(f'get_league: ERROR {e}')
