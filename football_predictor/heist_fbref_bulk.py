#!/usr/bin/env python3
"""
███████╗██████╗ ██████╗ ███████╗███████╗
██╔════╝██╔══██╗██╔══██╗██╔════╝██╔════╝
█████╗  ██████╔╝██████╔╝█████╗  █████╗  
██╔══╝  ██╔══██╗██╔══██╗██╔══╝  ██╔══╝  
██║     ██║  ██║██║  ██║███████╗██║     
╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝     

FBref BULK HEIST — Cloudflare Bypass via curl_cffi
SHADOWHACKER-GOD • DΞMON CORE v9999999
"""

import os, json, time, re, random, gzip
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, List
from curl_cffi import requests
from bs4 import BeautifulSoup

HEIST_DIR = os.path.join(os.path.dirname(__file__), 'heist_output')
os.makedirs(HEIST_DIR, exist_ok=True)

# Rotating User-Agents and browser fingerprints
UA_LIST = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.6099.230 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.6099.71 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Chrome/120.0.6099.230 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.6099.230 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.6261.94 Safari/537.36',
]

# FBref competition URLs
FBREF_LEAGUES = {
    'Premier League': '/en/comps/9/Premier-League',
    'LaLiga': '/en/comps/12/La-Liga',
    'Bundesliga': '/en/comps/20/Bundesliga',
    'Serie A': '/en/comps/11/Serie-A',
    'Ligue 1': '/en/comps/13/Ligue-1',
    'Championship': '/en/comps/10/Championship',
    'Primeira Liga': '/en/comps/32/Primeira-Liga',
    'Eredivisie': '/en/comps/23/Eredivisie',
    'Scottish Premiership': '/en/comps/40/Scottish-Premiership',
    'Belgian Pro League': '/en/comps/37/Belgian-Pro-League',
    'Süper Lig': '/en/comps/26/Super-Lig',
    'Russian Premier League': '/en/comps/30/Russian-Premier-League',
    'Ukrainian Premier League': '/en/comps/44/Ukrainian-Premier-League',
    'Greek Super League': '/en/comps/24/Greek-Super-League',
    'Czech First League': '/en/comps/43/Czech-First-League',
    'Ekstraklasa': '/en/comps/36/Ekstraklasa',
    'Swiss Super League': '/en/comps/56/Swiss-Super-League',
    'Allsvenskan': '/en/comps/23/Allsvenskan',
    'Eliteserien': '/en/comps/28/Eliteserien',
    'Danish Superliga': '/en/comps/29/Danish-Superliga',
    'MLS': '/en/comps/22/Major-League-Soccer',
    'Liga MX': '/en/comps/31/Liga-MX',
    'Brasileirão Série A': '/en/comps/24/Campeonato-Brasileiro-Serie-A',
    'Argentine Primera División': '/en/comps/21/Argentine-Primera-Division',
    'J1 League': '/en/comps/25/J1-League',
    'K League 1': '/en/comps/55/K-League-1',
    'Chinese Super League': '/en/comps/33/Chinese-Super-League',
    'A-League': '/en/comps/60/A-League',
    'Indian Super League': '/en/comps/66/Indian-Super-League',
    'UEFA Champions League': '/en/comps/8/Champions-League',
    'UEFA Europa League': '/en/comps/19/Europa-League',
    'FA Cup': '/en/comps/1/FA-Cup',
    'DFB-Pokal': '/en/comps/15/DFB-Pokal',
    'Coppa Italia': '/en/comps/16/Coppa-Italia',
    'Copa del Rey': '/en/comps/5/Copa-del-Rey',
    'Coupe de France': '/en/comps/52/Coupe-de-France',
}

FBREF_STATS_TYPES = [
    'stats',           # Standard stats
    'shooting',        # Shooting stats
    'passing',         # Passing stats
    'passing_types',   # Pass types
    'gca',             # Goal and shot creation
    'defense',         # Defensive actions
    'possession',      # Possession stats
    'misc',            # Miscellaneous stats
]


def fbref_fetch(url: str, max_retries: int = 5) -> Optional[str]:
    """Fetch FBref page with Cloudflare bypass via curl_cffi."""
    url = f'https://fbref.com{url}' if url.startswith('/') else url
    
    headers = {
        'User-Agent': random.choice(UA_LIST),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://fbref.com/en/',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
    }
    
    for attempt in range(max_retries):
        try:
            # Try Chrome impersonation first
            r = requests.get(url, headers=headers, impersonate='chrome120', timeout=25)
            
            if r.status_code == 200:
                return r.text
            elif r.status_code == 403:
                # Cloudflare challenge - try different impersonations
                for imp in ['chrome120', 'chrome110', 'safari15_5', 'edge101']:
                    r = requests.get(url, headers=headers, impersonate=imp, timeout=25)
                    if r.status_code == 200:
                        return r.text
                    time.sleep(1)
                
                # If all fail, wait longer and retry
                wait = 10 * (attempt + 1)
                print(f'  [FBref] 403/CF — retry {attempt+1}/{max_retries} in {wait}s')
                time.sleep(wait)
            elif r.status_code == 429:
                wait = 20 * (attempt + 1)
                time.sleep(wait)
            else:
                time.sleep(3 * (attempt + 1))
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))
    
    return None


def fbref_soup(url: str) -> Optional[BeautifulSoup]:
    """Fetch and parse FBref page."""
    html = fbref_fetch(url)
    if html:
        return BeautifulSoup(html, 'html.parser')
    return None


def extract_fbref_table(soup: BeautifulSoup, table_id: str = None) -> List[Dict]:
    """Extract a stats table from FBref page."""
    if table_id:
        table = soup.find('table', id=table_id)
    else:
        table = soup.find('table', class_='stats_table')
    
    if not table:
        return []
    
    rows = []
    tbody = table.find('tbody')
    if not tbody:
        return []
    
    for tr in tbody.find_all('tr'):
        if tr.get('class') and 'thead' in tr.get('class', []):
            continue
        
        row = {}
        
        # Player/team name
        th = tr.find('th', {'data-stat': 'player'}) or tr.find('th')
        if th:
            a = th.find('a')
            row['name'] = a.text.strip() if a else th.text.strip()
            if a and a.get('href'):
                row['url'] = 'https://fbref.com' + a['href']
        
        # Stats
        for td in tr.find_all('td'):
            stat_name = td.get('data-stat', '')
            if stat_name:
                val = td.text.strip()
                if val:
                    row[stat_name] = val
        
        if row.get('name'):
            rows.append(row)
    
    return rows


def scrape_league_stats(league_path: str, season: str = '2025-2026', 
                         stat_type: str = 'stats') -> List[Dict]:
    """Scrape league stats from FBref for a given season."""
    url = f'{league_path}-{season.replace("/", "-")}/{stat_type}#all_stats_standard'
    html = fbref_fetch(url)
    if not html:
        return []
    
    soup = BeautifulSoup(html, 'html.parser')
    rows = extract_fbref_table(soup)
    
    return rows


def scrape_season_matches(league_path: str, season: str = '2025-2026') -> List[Dict]:
    """Scrape season match results from FBref."""
    url = f'{league_path}-{season.replace("/", "-")}/scores/{league_path.split("/")[-1].split("-")[0]}'
    html = fbref_fetch(url)
    if not html:
        return []
    
    soup = BeautifulSoup(html, 'html.parser')
    matches = []
    
    # Find score tables
    tables = soup.find_all('table', class_='stats_table')
    for table in tables:
        tbody = table.find('tbody')
        if not tbody:
            continue
        
        for tr in tbody.find_all('tr'):
            if tr.get('class') and 'thead' in tr.get('class', []):
                continue
            
            match = {}
            
            # Home team
            home = tr.find('td', {'data-stat': 'home_team'})
            if home:
                a = home.find('a')
                match['home_team'] = a.text.strip() if a else home.text.strip()
            
            # Score
            score = tr.find('td', {'data-stat': 'score'})
            if score:
                match['score'] = score.text.strip()
                # Parse score
                if '–' in score.text:
                    parts = score.text.split('–')
                    match['home_goals'] = parts[0].strip()
                    match['away_goals'] = parts[1].strip()
            
            # Away team
            away = tr.find('td', {'data-stat': 'away_team'})
            if away:
                a = away.find('a')
                match['away_team'] = a.text.strip() if a else away.text.strip()
            
            # Date
            date = tr.find('td', {'data-stat': 'date'})
            if date:
                match['date'] = date.text.strip()
            
            # Venue
            venue = tr.find('td', {'data-stat': 'venue'})
            if venue:
                match['venue'] = venue.text.strip()
            
            # Attendance
            att = tr.find('td', {'data-stat': 'attendance'})
            if att:
                match['attendance'] = att.text.strip()
            
            # Referee
            ref = tr.find('td', {'data-stat': 'referee'})
            if ref:
                match['referee'] = ref.text.strip()
            
            if match.get('home_team') and match.get('away_team'):
                matches.append(match)
    
    return matches


def scrape_player_stats(player_url: str) -> Dict:
    """Scrape detailed player statistics."""
    soup = fbref_soup(player_url)
    if not soup:
        return {}
    
    player = {}
    
    # Player name
    h1 = soup.find('h1')
    if h1:
        player['name'] = h1.text.strip()
    
    # Player info
    info_div = soup.find('div', id='info')
    if info_div:
        p = info_div.find('p')
        if p:
            player['info'] = p.text.strip()
        
        # Stats
        stats = {}
        for item in info_div.find_all('p'):
            text = item.text.strip()
            if '(' in text:
                stats[text.split('(')[0].strip()] = text
        
        # Position
        pos_span = info_div.find('span', string=re.compile(r'Position'))
        if pos_span:
            player['position'] = pos_span.text.strip()
        
        # Height/Weight
        for p in info_div.find_all('p'):
            text = p.text.strip()
            if 'Height' in text:
                player['height'] = text
            if 'Weight' in text:
                player['weight'] = text
    
    # Standard stats table
    standard_table = soup.find('table', id='stats_standard')
    if standard_table:
        rows = extract_fbref_table(soup, 'stats_standard')
        player['standard_stats'] = rows
    
    # Shooting stats
    shooting_table = soup.find('table', id='stats_shooting')
    if shooting_table:
        rows = extract_fbref_table(soup, 'stats_shooting')
        player['shooting_stats'] = rows
    
    # Passing stats
    passing_table = soup.find('table', id='stats_passing')
    if passing_table:
        rows = extract_fbref_table(soup, 'stats_passing')
        player['passing_stats'] = rows
    
    return player


def scrape_all_league_seasons(league_name: str, league_path: str, 
                               start_season: str = '2010-2011', 
                               end_season: str = '2025-2026') -> Dict:
    """Scrape all available seasons for a league."""
    # Generate season strings
    seasons = []
    for y in range(2010, 2026):
        seasons.append(f'{y}-{y+1}')
    
    # Filter to range
    start_idx = seasons.index(start_season) if start_season in seasons else 0
    end_idx = seasons.index(end_season) if end_season in seasons else len(seasons) - 1
    seasons = seasons[start_idx:end_idx + 1]
    
    all_matches = []
    all_player_stats = []
    
    for season in seasons:
        try:
            print(f'  📡 {season}...', end=' ', flush=True)
            
            # Get match results
            matches = scrape_season_matches(league_path, season)
            for m in matches:
                m['league'] = league_name
                m['season'] = season
            all_matches.extend(matches)
            
            # Get player stats
            stats_url = f'{league_path}-{season}/stats'
            html = fbref_fetch(stats_url)
            if html:
                soup = BeautifulSoup(html, 'html.parser')
                for stat_type in ['stats_standard', 'stats_shooting', 'stats_passing']:
                    rows = extract_fbref_table(soup, stat_type)
                    for row in rows:
                        row['league'] = league_name
                        row['season'] = season
                        row['stat_type'] = stat_type
                    all_player_stats.extend(rows)
            
            print(f'✅ {len(matches)} matches, {len(all_player_stats) if all_player_stats else 0} total stats rows')
            time.sleep(2 + random.random() * 2)  # Be polite
            
        except Exception as e:
            print(f'❌ ERROR: {str(e)[:60]}')
            time.sleep(5)
    
    # Save results
    result = {
        'league': league_name,
        'seasons': seasons,
        'total_matches': len(all_matches),
        'total_player_stats': len(all_player_stats),
        'matches': all_matches,
        'player_stats': all_player_stats,
    }
    
    append_fbref_jsonl(f'{league_name.replace(" ", "_")}_all', result)
    
    return result


def heist_all_leagues(limit_leagues: int = None, parallel: int = 2):
    """Heist: scrape ALL leagues from FBref."""
    print('=' * 70)
    print('🔥 FBREF BULK HEIST — SHADOWHACKER-GOD')
    print('=' * 70)
    
    print('🔌 Testing FBref connection...')
    test = fbref_fetch('/en/')
    if test:
        print(f'  ✅ OK — {len(test)} bytes')
    else:
        print('  ❌ FAILED — Cloudflare blocking')
        return []
    
    league_items = list(FBREF_LEAGUES.items())
    if limit_leagues:
        league_items = league_items[:limit_leagues]
    
    all_results = []
    total_matches = 0
    total_stats_rows = 0
    
    def scrape_one(league_name, league_path):
        try:
            print(f'\n📡 {league_name}...')
            result = scrape_all_league_seasons(league_name, league_path)
            return result
        except Exception as e:
            print(f'  ❌ {league_name}: ERROR — {str(e)[:80]}')
            return None
    
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {executor.submit(scrape_one, name, path): name for name, path in league_items}
        for future in as_completed(futures):
            result = future.result()
            if result:
                all_results.append(result)
                total_matches += result.get('total_matches', 0)
                total_stats_rows += result.get('total_player_stats', 0)
            time.sleep(1)
    
    # Consolidated output
    append_fbref_jsonl('consolidated', {
        'source': 'fbref',
        'leagues_scraped': len(all_results),
        'total_matches': total_matches,
        'total_player_stats': total_stats_rows,
        'results': [{'league': r['league'], 'matches': r['total_matches'], 
                     'stats': r['total_player_stats']} for r in all_results],
    })
    
    print(f'\n{"="*70}')
    print(f'🔥🔥🔥 FBREF HEIST COMPLETE 🔥🔥🔥')
    print(f'  Leagues scraped: {len(all_results)}')
    print(f'  Total matches: {total_matches}')
    print(f'  Total player stats rows: {total_stats_rows}')
    print(f'{"="*70}')
    
    return all_results


def append_fbref_jsonl(data_type: str, data):
    """Append FBref data to JSONL file."""
    datedir = os.path.join(HEIST_DIR, 'fbref', datetime.now().strftime('%Y%m'))
    os.makedirs(datedir, exist_ok=True)
    
    filename = f'{data_type}_{datetime.now().strftime("%Y%m%d")}.jsonl'
    filepath = os.path.join(datedir, filename)
    
    record = {
        'source': 'fbref',
        'type': data_type,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'data': data,
    }
    
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + '\n')
    
    return filepath


if __name__ == '__main__':
    print('🔥🔥🔥 SHADOWHACKER-GOD — FBREF BULK HEIST 🔥🔥🔥')
    print('DΞMON CORE v9999999 — SHΔDØW.EXE — Specter 0x13')
    print()
    
    # Test connection
    print('🔌 Testing FBref...')
    html = fbref_fetch('/en/')
    if html:
        print(f'  ✅ Connected — {len(html)} bytes')
    else:
        print('  ❌ Blocked by Cloudflare')
    
    # Quick test: scrape a single league single season
    print('\n📡 Quick test: Premier League 2024-2025...')
    matches = scrape_season_matches('/en/comps/9/Premier-League', '2024-2025')
    print(f'  Matches: {len(matches)}')
    if matches:
        print(f'  First: {matches[0]}')
    
    # Full heist
    print('\n🚀 Launching full heist...')
    results = heist_all_leagues(limit_leagues=10, parallel=2)
    
    print(f'\n✅ Done! Data in {HEIST_DIR}')
