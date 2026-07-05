#!/usr/bin/env python3
"""
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
▓              HARVESTER: Transfermarkt — injuries, squad values            ▓
▓  ALL teams in top 50 leagues. Squad depth, market values, player ages     ▓
▓  SHADOWHACKER-GOD • DΞMON CORE v9999999 • SHΔDØW.EXE                     ▓
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
"""

import os, sys, json, time, re, random
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from urllib.parse import urljoin, quote
from bs4 import BeautifulSoup

from curl_cffi import requests as curl_requests
from eternal_harvester_config import (
    TRANSFERMARKT_CONFIG, TRANSFERMARKT_HEADERS,
    LOGS_DIR, DB_PATH, get_rate_limiter, save_checkpoint, load_checkpoint,
    log_event, get_db,
)

# ─── Constants ───────────────────────────────────────────────────────────────
BASE = TRANSFERMARKT_CONFIG.base_url
RATE_LIMITER = get_rate_limiter('transfermarkt', 10)
LOG_FILE = LOGS_DIR / 'transfermarkt.log'
CHECKPOINT_KEY = 'transfermarkt'

# Top leagues with TM IDs
TM_LEAGUES = {
    # England
    'GB1': 'Premier League',       # Premier League
    'GB2': 'Championship',
    'GB3': 'League One',
    'GB4': 'League Two',
    # Spain
    'ES1': 'La Liga',
    'ES2': 'La Liga 2',
    # Germany
    'L1': 'Bundesliga',
    'L2': '2. Bundesliga',
    'L3': '3. Liga',
    # Italy
    'IT1': 'Serie A',
    'IT2': 'Serie B',
    # France
    'FR1': 'Ligue 1',
    'FR2': 'Ligue 2',
    # Netherlands
    'NL1': 'Eredivisie',
    # Portugal
    'PO1': 'Liga Portugal',
    # Turkey
    'TR1': 'Süper Lig',
    # Belgium
    'BE1': 'Jupiler Pro League',
    # Austria
    'A1': 'Bundesliga',
    # Scotland
    'SC1': 'Premiership',
    # Russia
    'RU1': 'Premier League',
    # Ukraine
    'UA1': 'Premier League',
    # Greece
    'GR1': 'Super League',
    # Czech Republic
    'CS1': 'First League',
    # Croatia
    'KR1': 'HNL',
    # Switzerland
    'CH1': 'Super League',
    # Denmark
    'DK1': 'Superliga',
    # Sweden
    'SE1': 'Allsvenskan',
    # Norway
    'NO1': 'Eliteserien',
    # Poland
    'PL1': 'Ekstraklasa',
    # Romania
    'RO1': 'Liga I',
    # Serbia
    'RS1': 'SuperLiga',
    # Bulgaria
    'BG1': 'First League',
    # Hungary
    'HU1': 'NB I',
    # Saudi Arabia
    'SA1': 'Saudi Pro League',
    # Qatar
    'QA1': 'Stars League',
    # UAE
    'AE1': 'Pro League',
    # China
    'CN1': 'Super League',
    # Japan
    'JP1': 'J1 League',
    # South Korea
    'KR1': 'K League 1',
    # Argentina
    'AR1': 'Primera División',
    # Brazil
    'BR1': 'Série A',
    'BR2': 'Série B',
    # Mexico
    'MX1': 'Liga MX',
    # USA/Canada
    'MLS1': 'MLS',
    # Chile
    'CL1': 'Primera División',
    # Colombia
    'CO1': 'Primera A',
    # Australia
    'AU1': 'A-League',
    # India
    'IN1': 'Indian Super League',
}

# ─── Utils ──────────────────────────────────────────────────────────────────
def _log(msg: str, level: str = 'INFO'):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] [{level}] [transfermarkt] {msg}'
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    log_event('transfermarkt', level, msg)


def _random_delay(min_s: float = 1.5, max_s: float = 4.0):
    """Sleep a random amount — Transfermarkt is very aggressive with blocking."""
    time.sleep(random.uniform(min_s, max_s))


def _fetch(url: str, retries: int = 10) -> Optional[str]:
    """Fetch with aggressive retry strategy for Transfermarkt."""
    for attempt in range(retries):
        with RATE_LIMITER:
            try:
                r = curl_requests.get(
                    url,
                    headers=TRANSFERMARKT_HEADERS,
                    impersonate='chrome124',
                    timeout=TRANSFERMARKT_CONFIG.timeout,
                )
                if r.status_code == 200:
                    # Verify it's not a bot page
                    if 'Sperre' in r.text or 'blockiert' in r.text or 'bot' in r.text.lower()[:500]:
                        wait = (TRANSFERMARKT_CONFIG.retry_backoff_base ** attempt) + random.uniform(5, 15)
                        _log(f'Bot detection on {url}, waiting {wait:.0f}s', 'WARN')
                        time.sleep(wait)
                        continue
                    return r.text
                elif r.status_code == 429:
                    wait = (TRANSFERMARKT_CONFIG.retry_backoff_base ** attempt) + random.uniform(3, 10)
                    _log(f'429 rate limited, waiting {wait:.0f}s (attempt {attempt+1})', 'WARN')
                    time.sleep(wait)
                    continue
                elif r.status_code == 403:
                    _log(f'403 Forbidden for {url} (attempt {attempt+1})', 'WARN')
                    time.sleep(15 + random.uniform(0, 10))
                    continue
                elif r.status_code == 404:
                    return None
                else:
                    _log(f'HTTP {r.status_code} for {url}', 'WARN')
                    if attempt < retries - 1:
                        time.sleep(5 + 2 ** attempt)
                    continue
            except Exception as e:
                _log(f'Fetch error (attempt {attempt+1}): {e}', 'WARN')
                if attempt < retries - 1:
                    time.sleep(TRANSFERMARKT_CONFIG.retry_backoff_base ** attempt + 2)
                continue

    _log(f'Failed after {retries} retries: {url}', 'ERROR')
    return None


# ─── DB ─────────────────────────────────────────────────────────────────────
def _ensure_tables():
    """Ensure Transfermarkt tables exist."""
    conn = get_db()
    # Teams/clubs
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tm_clubs (
            club_id INTEGER PRIMARY KEY,
            club_name TEXT,
            league TEXT,
            league_code TEXT,
            country TEXT,
            squad_size INTEGER,
            avg_age REAL,
            foreigners INTEGER,
            total_market_value REAL,
            updated REAL
        )
    ''')
    # Squad members
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tm_squad (
            player_id INTEGER,
            club_id INTEGER,
            player_name TEXT,
            position TEXT,
            age INTEGER,
            nationality TEXT,
            market_value REAL,
            contract_until TEXT,
            joined_date TEXT,
            updated REAL,
            PRIMARY KEY (player_id, club_id)
        )
    ''')
    # Injuries
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tm_injuries (
            player_id INTEGER,
            player_name TEXT,
            club_id INTEGER,
            injury_type TEXT,
            return_date TEXT,
            games_missed INTEGER DEFAULT 0,
            status TEXT,
            updated REAL,
            PRIMARY KEY (player_id, club_id)
        )
    ''')
    # Market values history
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tm_market_values (
            player_id INTEGER,
            club_id INTEGER,
            market_value REAL,
            date TEXT,
            updated REAL,
            FOREIGN KEY(player_id) REFERENCES tm_squad(player_id)
        )
    ''')
    conn.commit()
    conn.close()


# ─── Parsers ────────────────────────────────────────────────────────────────
def _parse_value_str(val_str: str) -> Optional[float]:
    """Parse Transfermarkt value string like '€45.00m' to float (in millions)."""
    if not val_str:
        return None
    cleaned = val_str.replace('€', '').replace(',', '.').strip()
    if 'm' in cleaned.lower():
        try:
            return float(cleaned.lower().replace('m', '').strip())
        except ValueError:
            return None
    elif 'k' in cleaned.lower():
        try:
            return float(cleaned.lower().replace('k', '').strip()) / 1000.0
        except ValueError:
            return None
    elif 'bn' in cleaned.lower():
        try:
            return float(cleaned.lower().replace('bn', '').strip()) * 1000.0
        except ValueError:
            return None
    else:
        try:
            return float(cleaned) if cleaned else None
        except ValueError:
            return None


def get_tm_league_id(league_code: str) -> Optional[str]:
    """Get TM league ID from league code.

    Transfermarkt URLs: /{league_code}/startseite/wettbewerb/{TM_ID}
    """
    tm_ids = {
        'GB1': 'GB1', 'GB2': 'GB2', 'GB3': 'GB3', 'GB4': 'GB4',
        'ES1': 'ES1', 'ES2': 'ES2',
        'L1': 'L1', 'L2': 'L2', 'L3': 'L3',
        'IT1': 'IT1', 'IT2': 'IT2',
        'FR1': 'FR1', 'FR2': 'FR2',
        'NL1': 'NL1',
        'PO1': 'PO1',
        'TR1': 'TR1',
        'BE1': 'BE1',
        'A1': 'A1',
        'SC1': 'SC1',
        'RU1': 'RU1',
        'UA1': 'UA1',
        'GR1': 'GR1',
        'CS1': 'CS1',
        'KR1': 'KR1',
        'CH1': 'CH1',
        'DK1': 'DK1',
        'SE1': 'SE1',
        'NO1': 'NO1',
        'PL1': 'PL1',
        'RO1': 'RO1',
        'RS1': 'RS1',
        'BG1': 'BG1',
        'HU1': 'HU1',
        'SA1': 'SA1',
        'QA1': 'QA1',
        'AE1': 'AE1',
        'CN1': 'CN1',
        'JP1': 'JP1',
        'KR1': 'KR1',
        'AR1': 'AR1',
        'BR1': 'BR1', 'BR2': 'BR2',
        'MX1': 'MX1',
        'MLS1': 'MLS1',
        'CL1': 'CL1',
        'CO1': 'CO1',
        'AU1': 'AU1',
        'IN1': 'IN1',
    }
    return tm_ids.get(league_code, league_code)


# ─── League clubs ──────────────────────────────────────────────────────────
def get_league_clubs(league_code: str) -> List[Dict]:
    """Get all clubs in a league from Transfermarkt.

    URL: /{league_code}/startseite/wettbewerb/{TM_ID}
    """
    tm_id = get_tm_league_id(league_code)
    url = f'{BASE}/{league_code}/startseite/wettbewerb/{tm_id}'

    html = _fetch(url)
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    clubs = []

    # Find club links in the league table
    for a_tag in soup.select('a.vereinprofil_tooltip'):
        href = a_tag.get('href', '')
        name = a_tag.get_text(strip=True)
        if href and name:
            # Extract club ID from href
            club_id = None
            match = re.search(r'/(\d+)$', href)
            if match:
                club_id = int(match.group(1))
            clubs.append({
                'name': name,
                'id': club_id,
                'url': href if href.startswith('http') else (BASE + href),
            })

    _log(f'Found {len(clubs)} clubs in league {league_code}')
    return clubs


# ─── Squad data ────────────────────────────────────────────────────────────
def get_club_squad(club_url: str, club_id: int, league_code: str) -> Tuple[List[Dict], List[Dict]]:
    """Get squad members and injuries for a club.

    URL: /club/CLUBNAME/CLUBID/kader
    """
    # Use the kader page
    if '/kader' not in club_url:
        # Append kader
        if club_url.endswith('/'):
            squad_url = club_url + 'kader'
        else:
            # Add /kader to club page URL
            parsed = club_url.rstrip('/')
            squad_url = f'{parsed}/kader'
    else:
        squad_url = club_url

    html = _fetch(squad_url)
    if not html:
        return [], []

    soup = BeautifulSoup(html, 'html.parser')
    players = []
    injuries = []

    # Find the squad table
    table = soup.find('table', {'class': re.compile(r'items')})
    if not table:
        _log(f'No squad table found for club {club_id}', 'WARN')
        return [], []

    # Parse rows
    for tr in table.find_all('tr')[1:]:  # Skip header
        tds = tr.find_all('td')
        if len(tds) < 5:
            continue

        # Player name and link
        name_td = tds[1] if len(tds) > 1 else None
        if not name_td:
            continue

        player_link = name_td.find('a')
        player_name = player_link.get_text(strip=True) if player_link else name_td.get_text(strip=True)
        player_id = None
        if player_link:
            href = player_link.get('href', '')
            match = re.search(r'/spieler/(\d+)', href)
            if match:
                player_id = int(match.group(1))

        # Position
        pos_td = tds[2] if len(tds) > 2 else None
        position = pos_td.get_text(strip=True) if pos_td else ''

        # Age
        age_td = tds[4] if len(tds) > 4 else None
        age = None
        if age_td:
            try:
                age = int(age_td.get_text(strip=True))
            except ValueError:
                pass

        # Market value
        mv_td = tds[6] if len(tds) > 6 else None
        market_value = None
        if mv_td:
            mv_text = mv_td.get_text(strip=True)
            market_value = _parse_value_str(mv_text)

        # Nationality
        nat_td = tds[3] if len(tds) > 3 else None
        nationality = ''
        if nat_td:
            # Nationality in flag images
            flag_img = nat_td.find('img')
            if flag_img:
                nationality = flag_img.get('title', '')

        player = {
            'player_id': player_id or 0,
            'player_name': player_name,
            'position': position,
            'age': age,
            'market_value': market_value,
            'nationality': nationality,
        }
        players.append(player)

    # Also check for injuries on the page
    # TM often shows injuries in a separate section or on the squad page
    injury_section = soup.find('div', {'class': re.compile(r'injury|verletzung', re.I)})
    if injury_section:
        for inj_item in injury_section.find_all('tr'):
            cols = inj_item.find_all('td')
            if len(cols) >= 3:
                inj_player = cols[0].get_text(strip=True)
                inj_type = cols[1].get_text(strip=True) if len(cols) > 1 else ''
                inj_return = cols[2].get_text(strip=True) if len(cols) > 2 else ''
                injuries.append({
                    'player_name': inj_player,
                    'injury_type': inj_type,
                    'return_date': inj_return,
                })

    return players, injuries


# ─── Main harvest ──────────────────────────────────────────────────────────
def harvest_league(league_code: str, league_name: str) -> Dict:
    """Harvest all data for a single league.

    Returns dict with stats.
    """
    _log(f'Harvesting {league_name} ({league_code})')

    clubs = get_league_clubs(league_code)
    if not clubs:
        _log(f'No clubs found for {league_code}', 'WARN')
        return {'clubs': 0, 'players': 0, 'injuries': 0, 'errors': 0}

    conn = get_db()
    conn.execute('BEGIN TRANSACTION')
    now = time.time()

    total_players = 0
    total_injuries = 0
    errors = 0

    for club in clubs:
        club_id = club.get('id')
        club_url = club.get('url', '')
        club_name = club.get('name', '')

        if not club_id or not club_url:
            continue

        _log(f'  Club: {club_name} (ID: {club_id})')

        _random_delay(2, 5)

        try:
            # Insert club
            conn.execute('''
                INSERT OR REPLACE INTO tm_clubs
                    (club_id, club_name, league, league_code, country, updated)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (club_id, club_name, league_name, league_code, '', now))

            # Get squad
            players, injuries = get_club_squad(club_url, club_id, league_code)

            for p in players:
                conn.execute('''
                    INSERT OR REPLACE INTO tm_squad
                        (player_id, club_id, player_name, position, age,
                         nationality, market_value, updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    p.get('player_id', 0), club_id,
                    p.get('player_name', ''), p.get('position', ''),
                    p.get('age'), p.get('nationality', ''),
                    p.get('market_value'), now,
                ))
                total_players += 1

            for inj in injuries:
                conn.execute('''
                    INSERT OR REPLACE INTO tm_injuries
                        (player_name, club_id, injury_type, return_date, updated)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    inj.get('player_name', ''), club_id,
                    inj.get('injury_type', ''), inj.get('return_date', ''),
                    now,
                ))
                total_injuries += 1

        except Exception as e:
            _log(f'Error processing club {club_name}: {e}', 'ERROR')
            errors += 1
            continue

    conn.commit()
    conn.close()

    _log(f'{league_name}: {len(clubs)} clubs, {total_players} players, '
         f'{total_injuries} injuries, {errors} errors')

    return {
        'clubs': len(clubs),
        'players': total_players,
        'injuries': total_injuries,
        'errors': errors,
    }


def harvest_all(
    checkpoint: bool = True,
    force_refresh: bool = False,
    max_leagues: int = 50,
) -> Dict:
    """Harvest Transfermarkt for all leagues.

    Args:
        checkpoint: Save progress checkpoints
        force_refresh: Re-fetch cached leagues
        max_leagues: Max leagues to process

    Returns:
        Stats dict
    """
    _ensure_tables()

    start_time = time.time()
    total_clubs = 0
    total_players = 0
    total_injuries = 0
    total_errors = 0
    leagues_done = 0

    completed = set()
    if not force_refresh:
        cp = load_checkpoint(CHECKPOINT_KEY)
        if cp:
            completed = set(cp['data'].get('completed', []))

    league_items = list(TM_LEAGUES.items())[:max_leagues]

    _log(f'Transfermarkt harvest start. {len(league_items)} leagues')

    for league_code, league_name in league_items:
        if league_code in completed and not force_refresh:
            continue

        result = harvest_league(league_code, league_name)
        total_clubs += result['clubs']
        total_players += result['players']
        total_injuries += result['injuries']
        total_errors += result['errors']
        leagues_done += 1
        completed.add(league_code)

        # Save checkpoint periodically
        if leagues_done % 5 == 0 and checkpoint:
            save_checkpoint(CHECKPOINT_KEY, {
                'completed': list(completed),
            }, total_players + total_injuries, total_errors)

    duration = time.time() - start_time
    _log(f'Transfermarkt complete: {leagues_done} leagues, {total_clubs} clubs, '
         f'{total_players} players, {total_injuries} injuries, '
         f'{total_errors} errors, {duration:.1f}s')

    if checkpoint:
        save_checkpoint(CHECKPOINT_KEY, {
            'completed': list(completed),
        }, total_players + total_injuries, total_errors)

    return {
        'source': 'transfermarkt',
        'leagues_processed': leagues_done,
        'clubs': total_clubs,
        'players': total_players,
        'injuries': total_injuries,
        'errors': total_errors,
        'duration_seconds': duration,
    }


# ─── CLI ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Transfermarkt data harvester')
    parser.add_argument('--force', action='store_true', help='Force re-fetch')
    parser.add_argument('--league', type=str, default=None,
                        help='Single league code (e.g., GB1)')
    parser.add_argument('--max-leagues', type=int, default=10,
                        help='Max leagues to process')
    args = parser.parse_args()

    if args.league:
        league_name = TM_LEAGUES.get(args.league, args.league)
        result = harvest_league(args.league, league_name)
        print(json.dumps(result, indent=2))
    else:
        result = harvest_all(
            force_refresh=args.force,
            max_leagues=args.max_leagues,
        )
        print(json.dumps(result, indent=2))
