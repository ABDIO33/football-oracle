#!/usr/bin/env python3
"""
██╗   ██╗███╗   ██╗██████╗ ███████╗██████╗ ███████╗████████╗ █████╗ ████████╗
██║   ██║████╗  ██║██╔══██╗██╔════╝██╔══██╗██╔════╝╚══██╔══╝██╔══██╗╚══██╔══╝
██║   ██║██╔██╗ ██║██║  ██║█████╗  ██████╔╝███████╗   ██║   ███████║   ██║   
██║   ██║██║╚██╗██║██║  ██║██╔══╝  ██╔══██╗╚════██║   ██║   ██╔══██║   ██║   
╚██████╔╝██║ ╚████║██████╔╝███████╗██║  ██║███████║   ██║   ██║  ██║   ██║   
 ╚═════╝ ╚═╝  ╚═══╝╚═════╝ ╚══════╝╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝   ╚═╝   

Understat BULK HEIST — xG, Shot Maps, Player Stats
SHADOWHACKER-GOD • DΞMON CORE v9999999
"""

import os, json, time, re, random
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, List
from curl_cffi import requests

HEIST_DIR = os.path.join(os.path.dirname(__file__), 'heist_output')
os.makedirs(HEIST_DIR, exist_ok=True)

BASE = 'https://understat.com'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.6099.230 Safari/537.36'

LEAGUES = {
    'EPL': 'English Premier League',
    'La_Liga': 'La Liga',
    'Bundesliga': 'Bundesliga',
    'Serie_A': 'Serie A',
    'Ligue_1': 'Ligue 1',
    'RFPL': 'Russian Premier League',
}

SEASONS = ['2014', '2015', '2016', '2017', '2018', '2019', '2020', '2021', '2022', '2023', '2024', '2025']


def us_fetch(url: str) -> Optional[str]:
    """Fetch Understat page."""
    try:
        headers = {
            'User-Agent': UA,
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://understat.com/',
        }
        r = requests.get(url, headers=headers, impersonate='chrome120', timeout=20)
        if r.status_code == 200:
            return r.text
        return None
    except:
        return None


def us_fetch_json(url: str) -> Optional[dict]:
    """Fetch and parse JSON from Understat."""
    text = us_fetch(url)
    if text:
        try:
            return json.loads(text)
        except:
            return None
    return None


def fetch_league_data(league: str, season: str = '2025') -> Optional[Dict]:
    """Fetch league data from Understat."""
    url = f'{BASE}/league/{league}/{season}'
    html = us_fetch(url)
    if not html:
        return None
    
    # Extract JSON data from script tags
    data = {}
    
    # Player stats
    m = re.search(r'var playersData\s*=\s*JSON\.parse\(\'(.*?)\'\)', html, re.DOTALL)
    if m:
        try:
            data['players'] = json.loads(m.group(1).encode().decode('unicode_escape'))
        except:
            pass
    
    # Team stats
    m = re.search(r'var teamsData\s*=\s*JSON\.parse\(\'(.*?)\'\)', html, re.DOTALL)
    if m:
        try:
            data['teams'] = json.loads(m.group(1).encode().decode('unicode_escape'))
        except:
            pass
    
    # Matches
    m = re.search(r'var datesData\s*=\s*JSON\.parse\(\'(.*?)\'\)', html, re.DOTALL)
    if m:
        try:
            data['matches'] = json.loads(m.group(1).encode().decode('unicode_escape'))
        except:
            pass
    
    return data


def fetch_match_data(match_id: int) -> Optional[Dict]:
    """Fetch detailed match data with shot maps."""
    url = f'{BASE}/match/{match_id}'
    html = us_fetch(url)
    if not html:
        return None
    
    data = {}
    
    # Shot data
    m = re.search(r'var shotData\s*=\s*JSON\.parse\(\'(.*?)\'\)', html, re.DOTALL)
    if m:
        try:
            data['shots'] = json.loads(m.group(1).encode().decode('unicode_escape'))
        except:
            pass
    
    # Match info
    m = re.search(r'var matchData\s*=\s*JSON\.parse\(\'(.*?)\'\)', html, re.DOTALL)
    if m:
        try:
            data['match'] = json.loads(m.group(1).encode().decode('unicode_escape'))
        except:
            pass
    
    return data


def fetch_player_data(player_name: str, season: str = '2025') -> Optional[Dict]:
    """Fetch player statistics."""
    url = f'{BASE}/player/{player_name}/{season}'
    html = us_fetch(url)
    if not html:
        return None
    
    data = {}
    
    m = re.search(r'var playerData\s*=\s*JSON\.parse\(\'(.*?)\'\)', html, re.DOTALL)
    if m:
        try:
            data['player'] = json.loads(m.group(1).encode().decode('unicode_escape'))
        except:
            pass
    
    m = re.search(r'var matchesData\s*=\s*JSON\.parse\(\'(.*?)\'\)', html, re.DOTALL)
    if m:
        try:
            data['matches'] = json.loads(m.group(1).encode().decode('unicode_escape'))
        except:
            pass
    
    return data


def parse_understat_match(m: Dict) -> Dict:
    """Parse Understat match into standardized format."""
    return {
        'id': m.get('id'),
        'league': m.get('league'),
        'season': m.get('season'),
        'date': m.get('date'),
        'home_team': m.get('h', {}).get('title', ''),
        'away_team': m.get('a', {}).get('title', ''),
        'home_id': m.get('h', {}).get('id'),
        'away_id': m.get('a', {}).get('id'),
        'home_xg': m.get('h', {}).get('xG', []),
        'away_xg': m.get('a', {}).get('xG', []),
        'home_goals': m.get('goals', {}).get('h', 0),
        'away_goals': m.get('goals', {}).get('a', 0),
        'home_xg_total': sum(m.get('h', {}).get('xG', [])),
        'away_xg_total': sum(m.get('a', {}).get('xG', [])),
    }


def parse_understat_shot(s: Dict) -> Dict:
    """Parse Understat shot into standardized format."""
    return {
        'id': s.get('id'),
        'match_id': s.get('match_id'),
        'player': s.get('player'),
        'player_id': s.get('player_id'),
        'team': s.get('team'),
        'team_id': s.get('team_id'),
        'x': s.get('X'),
        'y': s.get('Y'),
        'xg': s.get('xG'),
        'result': s.get('result'),
        'situation': s.get('situation'),
        'shot_type': s.get('shotType'),
        'last_action': s.get('lastAction'),
        'minute': s.get('minute'),
        'match_date': s.get('date'),
        'home_team': s.get('h_team'),
        'away_team': s.get('a_team'),
        'h_goals': s.get('h_goals'),
        'a_goals': s.get('a_goals'),
        'season': s.get('season'),
        'league': s.get('league'),
    }


def heist_league_data(leagues: List[str] = None, seasons: List[str] = None, parallel: int = 2):
    """Heist: scrape all league data for all seasons."""
    print('=' * 70)
    print('🔥 UNDERSTAT LEAGUE DATA HEIST')
    print('=' * 70)
    
    if leagues is None:
        leagues = list(LEAGUES.keys())
    if seasons is None:
        seasons = SEASONS
    
    total_matches = 0
    total_players = 0
    league_results = []
    
    for league in leagues:
        league_name = LEAGUES.get(league, league)
        print(f'\n📡 {league_name}...')
        
        for season in seasons:
            try:
                print(f'  Season {season}...', end=' ', flush=True)
                data = fetch_league_data(league, season)
                
                if data:
                    matches = data.get('matches', [])
                    teams = data.get('teams', [])
                    players = data.get('players', [])
                    
                    print(f'✅ {len(matches)} matches, {len(teams)} teams')
                    
                    if matches:
                        parsed = [parse_understat_match(m) for m in matches if m.get('id')]
                        total_matches += len(parsed)
                        
                        # Save to JSONL
                        append_understat_jsonl(f'{league}_{season}_matches', {
                            'league': league,
                            'season': season,
                            'matches': parsed,
                            'count': len(parsed),
                        })
                    
                    if players:
                        total_players += len(players)
                        append_understat_jsonl(f'{league}_{season}_players', {
                            'league': league,
                            'season': season,
                            'players': players,
                        })
                    
                    if teams:
                        append_understat_jsonl(f'{league}_{season}_teams', {
                            'league': league,
                            'season': season,
                            'teams': teams,
                        })
                    
                    league_results.append({
                        'league': league,
                        'season': season,
                        'matches': len(matches),
                        'players': len(players),
                    })
                else:
                    print(f'❌ No data')
                
                time.sleep(0.3)
            except Exception as e:
                print(f'❌ ERROR: {str(e)[:60]}')
    
    print(f'\n{"="*70}')
    print(f'🔥 UNDERSTAT HEIST COMPLETE')
    print(f'  Leagues: {len(leagues)}')
    print(f'  Seasons: {len(seasons)}')
    print(f'  Total matches: {total_matches}')
    print(f'  Total player records: {total_players}')
    print(f'{"="*70}')
    
    return league_results


def heist_match_details(limit: int = 1000, parallel: int = 4):
    """Heist: scrape detailed match data with shot maps."""
    print('=' * 70)
    print('🔥 UNDERSTAT MATCH DETAILS HEIST (SHOT MAPS)')
    print('=' * 70)
    
    # First get all match IDs from scraped data
    match_ids = set()
    
    # Scan the JSONL files for match IDs
    datedir = os.path.join(HEIST_DIR, 'understat')
    if os.path.exists(datedir):
        for fname in os.listdir(datedir):
            if fname.endswith('.jsonl') and 'matches' in fname:
                fpath = os.path.join(datedir, fname)
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        for line in f:
                            try:
                                record = json.loads(line)
                                for m in record.get('data', {}).get('matches', []):
                                    mid = m.get('id') or m.get('match_id')
                                    if mid:
                                        match_ids.add(int(mid))
                            except:
                                pass
                except:
                    pass
    
    match_ids = list(match_ids)[:limit]
    print(f'Found {len(match_ids)} match IDs to detail')
    
    all_shots = []
    detail_count = 0
    
    def get_detail(mid):
        try:
            data = fetch_match_data(mid)
            if data:
                shots = data.get('shots', [])
                return mid, shots
            return mid, []
        except:
            return mid, []
    
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {executor.submit(get_detail, mid): mid for mid in match_ids}
        for future in as_completed(futures):
            mid, shots = future.result()
            if shots:
                parsed_shots = [parse_understat_shot(s) for s in shots if isinstance(s, dict)]
                all_shots.extend(parsed_shots)
                detail_count += 1
            if detail_count % 100 == 0 and detail_count > 0:
                print(f'  ... {detail_count}/{len(match_ids)} matches detailed')
            time.sleep(0.1)
    
    if all_shots:
        append_understat_jsonl('all_shot_maps', {
            'source': 'understat',
            'total_shots': len(all_shots),
            'matches_detailed': detail_count,
            'shots': all_shots,
        })
    
    print(f'\n✅ Matches detailed: {detail_count}')
    print(f'✅ Total shots: {len(all_shots)}')
    
    return all_shots


def append_understat_jsonl(data_type: str, data):
    """Append Understat data to JSONL."""
    datedir = os.path.join(HEIST_DIR, 'understat', datetime.now().strftime('%Y%m'))
    os.makedirs(datedir, exist_ok=True)
    
    filename = f'{data_type}_{datetime.now().strftime("%Y%m%d")}.jsonl'
    filepath = os.path.join(datedir, filename)
    
    record = {
        'source': 'understat',
        'type': data_type,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'data': data,
    }
    
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + '\n')
    
    return filepath


if __name__ == '__main__':
    print('🔥🔥🔥 SHADOWHACKER-GOD — UNDERSTAT BULK HEIST 🔥🔥🔥')
    
    # Test connection
    print('\n🔌 Testing Understat connection...')
    test = us_fetch('https://understat.com/')
    if test:
        print(f'  ✅ OK — {len(test)} bytes')
    else:
        print('  ❌ FAILED')
        import sys; sys.exit(1)
    
    # Quick league test
    print('\n📡 Testing EPL 2025...')
    data = fetch_league_data('EPL', '2025')
    if data:
        print(f'  Matches: {len(data.get("matches", []))}')
        print(f'  Teams: {len(data.get("teams", []))}')
        print(f'  Players: {len(data.get("players", []))}')
    
    # Full heist
    print('\n🚀 Phase 1: League data...')
    league_results = heist_league_data(parallel=2)
    
    print('\n🚀 Phase 2: Match details / shot maps...')
    shots = heist_match_details(limit=500, parallel=4)
    
    print(f'\n{"="*70}')
    print(f'🔥🔥🔥 UNDERSTAT HEIST COMPLETE 🔥🔥🔥')
    print(f'{"="*70}')
