#!/usr/bin/env python3
"""
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
▓              HARVESTER: OpenWeatherMap — match weather data               ▓
▓  1000/day free tier. Fetches historical & future match weather.           ▓
▓  SHADOWHACKER-GOD • DΞMON CORE v9999999 • SHΔDØW.EXE                     ▓
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
"""

import os, sys, json, time, sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from curl_cffi import requests as curl_requests
from eternal_harvester_config import (
    OPENWEATHERMAP_CONFIG, API_KEYS,
    LOGS_DIR, DB_PATH, get_rate_limiter, save_checkpoint, load_checkpoint,
    log_event, get_db,
)

# ─── Constants ───────────────────────────────────────────────────────────────
BASE = OPENWEATHERMAP_CONFIG.base_url
RATE_LIMITER = get_rate_limiter('openweathermap', 60)
LOG_FILE = LOGS_DIR / 'weather.log'
CHECKPOINT_KEY = 'weather'
API_KEY = API_KEYS.get('openweathermap')

LOG_FILE_PATH = LOGS_DIR / 'weather.log'


def _log(msg: str, level: str = 'INFO'):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] [{level}] [weather] {msg}'
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    log_event('weather', level, msg)


# ─── DB ─────────────────────────────────────────────────────────────────────
def _ensure_tables():
    """Ensure weather tables exist."""
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS weather_cache (
            lat REAL, lon REAL, date TEXT,
            temp_max REAL, temp_min REAL, precip REAL,
            wind REAL, humidity REAL,
            PRIMARY KEY (lat, lon, date)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS venue_weather (
            venue_name TEXT,
            lat REAL,
            lon REAL,
            country TEXT,
            timezone TEXT,
            PRIMARY KEY (venue_name)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS team_venue (
            team_name TEXT,
            venue_name TEXT,
            PRIMARY KEY (team_name)
        )
    ''')
    conn.commit()
    conn.close()


# ─── Known stadium coordinates ──────────────────────────────────────────────
# 102 stadiums from the existing project — expand with more
KNOWN_STADIUMS: Dict[str, Dict] = {
    # Premier League
    'Old Trafford': {'lat': 53.4631, 'lon': -2.2913, 'team': 'Manchester United'},
    'Etihad Stadium': {'lat': 53.4830, 'lon': -2.2002, 'team': 'Manchester City'},
    'Anfield': {'lat': 53.4308, 'lon': -2.9608, 'team': 'Liverpool'},
    'Emirates Stadium': {'lat': 51.5550, 'lon': -0.1084, 'team': 'Arsenal'},
    'Stamford Bridge': {'lat': 51.4817, 'lon': -0.1910, 'team': 'Chelsea'},
    'Tottenham Hotspur Stadium': {'lat': 51.6033, 'lon': -0.0658, 'team': 'Tottenham'},
    'London Stadium': {'lat': 51.5383, 'lon': -0.0166, 'team': 'West Ham'},
    'Villa Park': {'lat': 52.5092, 'lon': -1.8847, 'team': 'Aston Villa'},
    'St. James Park': {'lat': 54.9756, 'lon': -1.6218, 'team': 'Newcastle'},
    'Goodison Park': {'lat': 53.4388, 'lon': -2.9664, 'team': 'Everton'},
    'Amex Stadium': {'lat': 50.8618, 'lon': -0.0833, 'team': 'Brighton'},
    'Molineux Stadium': {'lat': 52.5902, 'lon': -2.1304, 'team': 'Wolves'},
    'King Power Stadium': {'lat': 52.6200, 'lon': -1.1421, 'team': 'Leicester'},
    'Craven Cottage': {'lat': 51.4749, 'lon': -0.2216, 'team': 'Fulham'},
    'Selhurst Park': {'lat': 51.3983, 'lon': -0.0855, 'team': 'Crystal Palace'},
    'Bramall Lane': {'lat': 53.3703, 'lon': -1.4708, 'team': 'Sheffield United'},
    'Vitality Stadium': {'lat': 50.7350, 'lon': -1.8382, 'team': 'Bournemouth'},
    'City Ground': {'lat': 52.9400, 'lon': -1.1328, 'team': 'Nottingham Forest'},
    'Portman Road': {'lat': 52.0550, 'lon': 1.1450, 'team': 'Ipswich'},
    'Gtech Community Stadium': {'lat': 51.4882, 'lon': -0.2878, 'team': 'Brentford'},
    # Championship
    'Elland Road': {'lat': 53.7770, 'lon': -1.5720, 'team': 'Leeds United'},
    'The Hawthorns': {'lat': 52.5086, 'lon': -1.9632, 'team': 'West Bromwich'},
    'Carrow Road': {'lat': 52.6221, 'lon': 1.3094, 'team': 'Norwich'},
    'Hillsborough': {'lat': 53.4114, 'lon': -1.5007, 'team': 'Sheffield Wednesday'},
    'Stadium of Light': {'lat': 54.9144, 'lon': -1.3882, 'team': 'Sunderland'},
    # La Liga
    'Camp Nou': {'lat': 41.3809, 'lon': 2.1228, 'team': 'Barcelona'},
    'Santiago Bernabeu': {'lat': 40.4531, 'lon': -3.6883, 'team': 'Real Madrid'},
    'Wanda Metropolitano': {'lat': 40.4362, 'lon': -3.5994, 'team': 'Atletico Madrid'},
    'Benito Villamarin': {'lat': 37.3566, 'lon': -5.9815, 'team': 'Real Betis'},
    'Mestalla': {'lat': 39.4746, 'lon': -0.3581, 'team': 'Valencia'},
    'San Mames': {'lat': 43.2644, 'lon': -2.9492, 'team': 'Athletic Bilbao'},
    'Ramón Sánchez Pizjuán': {'lat': 37.3840, 'lon': -5.9705, 'team': 'Sevilla'},
    # Bundesliga
    'Allianz Arena': {'lat': 48.2188, 'lon': 11.6248, 'team': 'Bayern Munich'},
    'Signal Iduna Park': {'lat': 51.4926, 'lon': 7.4519, 'team': 'Borussia Dortmund'},
    'Red Bull Arena': {'lat': 51.3453, 'lon': 12.3485, 'team': 'RB Leipzig'},
    'BayArena': {'lat': 51.0390, 'lon': 7.0021, 'team': 'Bayer Leverkusen'},
    'Waldstadion': {'lat': 50.0686, 'lon': 8.6454, 'team': 'Eintracht Frankfurt'},
    'Olympiastadion Berlin': {'lat': 52.5147, 'lon': 13.2394, 'team': 'Hertha Berlin'},
    'Volksparkstadion': {'lat': 53.5865, 'lon': 9.8992, 'team': 'Hamburger SV'},
    'MHP Arena': {'lat': 48.8596, 'lon': 9.2314, 'team': 'VfB Stuttgart'},
    'Borussia-Park': {'lat': 51.1746, 'lon': 6.3854, 'team': 'Borussia Mönchengladbach'},
    # Serie A
    'San Siro': {'lat': 45.4781, 'lon': 9.1240, 'team': 'AC Milan'},
    'Juventus Stadium': {'lat': 45.1094, 'lon': 7.6411, 'team': 'Juventus'},
    'Stadio Olimpico': {'lat': 41.9340, 'lon': 12.4547, 'team': 'Roma'},
    'Stadio Diego Armando Maradona': {'lat': 40.8279, 'lon': 14.1933, 'team': 'Napoli'},
    'Stadio Artemio Franchi': {'lat': 43.7808, 'lon': 11.2821, 'team': 'Fiorentina'},
    # Ligue 1
    'Parc des Princes': {'lat': 48.8414, 'lon': 2.2531, 'team': 'Paris Saint-Germain'},
    'Stade Vélodrome': {'lat': 43.2697, 'lon': 5.3959, 'team': 'Marseille'},
    'Groupama Stadium': {'lat': 45.7640, 'lon': 4.9786, 'team': 'Lyon'},
    'Allianz Riviera': {'lat': 43.7068, 'lon': 7.1929, 'team': 'Nice'},
    # Eredivisie
    'Johan Cruijff ArenA': {'lat': 52.3114, 'lon': 4.9376, 'team': 'Ajax'},
    'De Kuip': {'lat': 51.8939, 'lon': 4.5233, 'team': 'Feyenoord'},
    'Philips Stadion': {'lat': 51.4417, 'lon': 5.4667, 'team': 'PSV'},
    # Primeira Liga
    'Estádio da Luz': {'lat': 38.7527, 'lon': -9.1844, 'team': 'Benfica'},
    'Estádio do Dragão': {'lat': 41.1617, 'lon': -8.5839, 'team': 'FC Porto'},
    'José Alvalade': {'lat': 38.7611, 'lon': -9.1608, 'team': 'Sporting CP'},
    # Other
    'Celtic Park': {'lat': 55.8497, 'lon': -4.2056, 'team': 'Celtic'},
    'Ibrox Stadium': {'lat': 55.8532, 'lon': -4.3092, 'team': 'Rangers'},
    'Ramón Sánchez Pizjuán': {'lat': 37.3840, 'lon': -5.9705, 'team': 'Sevilla'},
    'Estádio do Maracanã': {'lat': -22.9121, 'lon': -43.2302, 'team': 'Flamengo'},
    'Estádio Mineirão': {'lat': -19.8657, 'lon': -43.9719, 'team': 'Cruzeiro'},
    'La Bombonera': {'lat': -34.6354, 'lon': -58.3641, 'team': 'Boca Juniors'},
    'Estadio Monumental': {'lat': -34.5453, 'lon': -58.4498, 'team': 'River Plate'},
    'Estadio Azteca': {'lat': 19.3030, 'lon': -99.1505, 'team': 'Club América'},
    'Mercedes-Benz Stadium': {'lat': 33.7553, 'lon': -84.4009, 'team': 'Atlanta United'},
    'BMO Field': {'lat': 43.6329, 'lon': -79.4186, 'team': 'Toronto FC'},
    'Saitama Stadium': {'lat': 35.9030, 'lon': 139.7170, 'team': 'Urawa Reds'},
    'Nissan Stadium': {'lat': 35.5095, 'lon': 139.6065, 'team': 'Yokohama F. Marinos'},
    'Seoul World Cup Stadium': {'lat': 37.5683, 'lon': 126.8972, 'team': 'FC Seoul'},
}

# Additional team→venue mapping for DB import
TEAM_VENUE_MAP = {v['team']: k for k, v in KNOWN_STADIUMS.items()}


# ─── Fetching weather ──────────────────────────────────────────────────────
def _fetch_weather_onecall(lat: float, lon: float, dt: int) -> Optional[Dict]:
    """Fetch weather for a specific timestamp using One Call API 3.0.

    Args:
        lat: Latitude
        lon: Longitude
        dt: Unix timestamp (for historical data)

    Returns:
        Weather data dict or None
    """
    if not API_KEY:
        _log('No OpenWeatherMap API key set', 'ERROR')
        return None

    # Try One Call API 3.0 (timemachine endpoint for historical)
    url = f'{BASE}/onecall/timemachine'
    params = {
        'lat': lat,
        'lon': lon,
        'dt': dt,
        'appid': API_KEY,
        'units': 'metric',
    }

    with RATE_LIMITER:
        try:
            r = curl_requests.get(url, params=params, timeout=OPENWEATHERMAP_CONFIG.timeout)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 429:
                _log('Rate limit reached (429)', 'WARN')
                time.sleep(60)
                return None
            elif r.status_code == 401:
                _log('Invalid API key', 'ERROR')
                return None
            else:
                _log(f'HTTP {r.status_code} for weather: {lat},{lon} @ {dt}', 'WARN')
                return None
        except Exception as e:
            _log(f'Weather fetch error: {e}', 'ERROR')
            return None


def _fetch_weather_current(lat: float, lon: float) -> Optional[Dict]:
    """Fetch current weather."""
    if not API_KEY:
        return None

    url = f'{BASE}/weather'
    params = {
        'lat': lat,
        'lon': lon,
        'appid': API_KEY,
        'units': 'metric',
    }

    with RATE_LIMITER:
        try:
            r = curl_requests.get(url, params=params, timeout=OPENWEATHERMAP_CONFIG.timeout)
            if r.status_code == 200:
                return r.json()
            return None
        except Exception as e:
            _log(f'Current weather fetch error: {e}', 'ERROR')
            return None


def get_weather_for_match(team: str, venue_name: str, match_date: str) -> Optional[Dict]:
    """Get weather data for a specific match.

    Args:
        team: Home team name
        venue_name: Venue/stadium name
        match_date: Date string (YYYY-MM-DD)

    Returns:
        Weather dict or None
    """
    # Look up coordinates
    venue = KNOWN_STADIUMS.get(venue_name)
    if not venue:
        # Try TEAM_VENUE_MAP
        mapped_venue = TEAM_VENUE_MAP.get(team)
        if mapped_venue:
            venue = KNOWN_STADIUMS.get(mapped_venue)
        if not venue:
            _log(f'No coordinates for venue={venue_name} team={team}', 'WARN')
            return None

    lat, lon = venue['lat'], venue['lon']

    # Check cache first
    conn = get_db()
    cached = conn.execute(
        'SELECT temp_max, temp_min, precip, wind, humidity FROM weather_cache WHERE lat=? AND lon=? AND date=?',
        (lat, lon, match_date)
    ).fetchone()
    conn.close()

    if cached:
        return {
            'temp_max': cached[0], 'temp_min': cached[1],
            'precip': cached[2], 'wind': cached[3],
            'humidity': cached[4], 'source': 'cache',
        }

    # Need to fetch
    try:
        match_dt = datetime.strptime(match_date, '%Y-%m-%d')
    except ValueError:
        _log(f'Invalid date: {match_date}', 'WARN')
        return None

    unix_ts = int(match_dt.timestamp())

    # For recent dates, current weather may be acceptable
    now = datetime.now()
    days_diff = abs((match_dt - now).days)

    weather_data = None
    if days_diff <= 2:
        # Use current weather
        data = _fetch_weather_current(lat, lon)
        if data and 'main' in data:
            weather_data = {
                'temp_max': data['main'].get('temp_max'),
                'temp_min': data['main'].get('temp_min'),
                'precip': data.get('rain', {}).get('1h', 0) or data.get('rain', {}).get('3h', 0),
                'wind': data.get('wind', {}).get('speed'),
                'humidity': data['main'].get('humidity'),
            }
    elif days_diff <= 7 and match_dt > now:
        # For future matches within a week, use forecast
        url = f'{BASE}/forecast'
        params = {'lat': lat, 'lon': lon, 'appid': API_KEY, 'units': 'metric'}
        with RATE_LIMITER:
            try:
                r = curl_requests.get(url, params=params, timeout=30)
                if r.status_code == 200:
                    data = r.json()
                    for item in data.get('list', []):
                        item_dt = datetime.fromtimestamp(item.get('dt', 0))
                        if item_dt.date() == match_dt.date():
                            weather_data = {
                                'temp_max': item['main'].get('temp_max'),
                                'temp_min': item['main'].get('temp_min'),
                                'precip': item.get('rain', {}).get('3h', 0) if 'rain' in item else 0,
                                'wind': item.get('wind', {}).get('speed'),
                                'humidity': item['main'].get('humidity'),
                            }
                            break
            except Exception as e:
                _log(f'Forecast error: {e}', 'WARN')
    elif days_diff <= 365 * 5:
        # Historical — use One Call timemachine
        data = _fetch_weather_onecall(lat, lon, unix_ts)
        if data and 'data' in data and len(data['data']) > 0:
            day_data = data['data'][0]
            weather_data = {
                'temp_max': day_data.get('temp') if isinstance(day_data.get('temp'), (int, float)) else None,
                'temp_min': None,
                'precip': day_data.get('rain', 0) if day_data.get('rain') else 0,
                'wind': day_data.get('wind_speed'),
                'humidity': day_data.get('humidity'),
            }
    else:
        _log(f'Date too far in past/future: {match_date}', 'WARN')
        return None

    if weather_data:
        # Save to cache
        conn = get_db()
        conn.execute('''
            INSERT OR REPLACE INTO weather_cache
                (lat, lon, date, temp_max, temp_min, precip, wind, humidity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            lat, lon, match_date,
            weather_data.get('temp_max'),
            weather_data.get('temp_min'),
            weather_data.get('precip'),
            weather_data.get('wind'),
            weather_data.get('humidity'),
        ))
        conn.commit()
        conn.close()
        weather_data['source'] = 'api'

    return weather_data


# ─── Bulk weather for matches ──────────────────────────────────────────────
def harvest_for_matches(matches: List[Dict], checkpoint: bool = True) -> Dict:
    """Fetch weather for a list of matches.

    Args:
        matches: List of dicts with 'team' (home), 'date' fields
        checkpoint: Save checkpoint

    Returns:
        Stats dict
    """
    _ensure_tables()

    start_time = time.time()
    total = len(matches)
    fetched = 0
    cached = 0
    skipped = 0
    errors = 0

    _log(f'Weather harvest for {total} matches')

    # Pre-populate known venues
    conn = get_db()
    for venue_name, vi in KNOWN_STADIUMS.items():
        conn.execute('''
            INSERT OR IGNORE INTO venue_weather (venue_name, lat, lon)
            VALUES (?, ?, ?)
        ''', (venue_name, vi['lat'], vi['lon']))
    for team, venue in TEAM_VENUE_MAP.items():
        conn.execute('''
            INSERT OR IGNORE INTO team_venue (team_name, venue_name)
            VALUES (?, ?)
        ''', (team, venue))
    conn.commit()
    conn.close()

    for i, match in enumerate(matches):
        team = match.get('team', match.get('home_team', ''))
        date = match.get('date', '')
        venue = match.get('venue', '')

        if not date or not team:
            skipped += 1
            continue

        weather = get_weather_for_match(team, venue, date)
        if weather:
            if weather.get('source') == 'cache':
                cached += 1
            else:
                fetched += 1
        else:
            errors += 1

        if (i + 1) % 50 == 0:
            _log(f'Progress: {i+1}/{total} matches ({fetched} fetched, {cached} cached, {errors} errors)')

    duration = time.time() - start_time
    _log(f'Weather complete: {fetched} fetched, {cached} cached, '
         f'{errors} errors, {duration:.1f}s')

    if checkpoint:
        save_checkpoint(CHECKPOINT_KEY, {
            'total_processed': total,
        }, fetched + cached, errors)

    return {
        'source': 'weather',
        'total_matches': total,
        'fetched_from_api': fetched,
        'from_cache': cached,
        'errors': errors,
        'duration_seconds': duration,
    }


def harvest_all_historical(limit: int = None, checkpoint: bool = True) -> Dict:
    """Fetch weather for all historical matches in the DB.

    Args:
        limit: Max matches to process
        checkpoint: Save checkpoint

    Returns:
        Stats dict
    """
    conn = get_db()

    # Get matches that don't have weather data yet
    query = '''
        SELECT DISTINCT r.home_team, r.date
        FROM sofa_historical_results r
        LEFT JOIN team_venue tv ON r.home_team = tv.team_name
        WHERE r.date IS NOT NULL
    '''
    if limit:
        query += f' LIMIT {limit}'

    rows = conn.execute(query).fetchall()
    conn.close()

    matches = [
        {'team': r[0], 'date': r[1][:10] if r[1] else ''}
        for r in rows if r[1]
    ]

    return harvest_for_matches(matches, checkpoint=checkpoint)


# ─── CLI ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Weather data harvester')
    parser.add_argument('--limit', type=int, default=1000, help='Max matches')
    parser.add_argument('--team', type=str, help='Single team')
    parser.add_argument('--date', type=str, help='Single date (YYYY-MM-DD)')
    parser.add_argument('--venue', type=str, help='Single venue')
    args = parser.parse_args()

    _ensure_tables()

    if args.team and args.date:
        weather = get_weather_for_match(args.team, args.venue or '', args.date)
        print(json.dumps(weather, indent=2))
    else:
        result = harvest_all_historical(limit=args.limit)
        print(json.dumps(result, indent=2))
