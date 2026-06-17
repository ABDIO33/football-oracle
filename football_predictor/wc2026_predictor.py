import os, json, time, sqlite3, csv, io
from datetime import datetime, timedelta
from math import exp, factorial
import numpy as np
from scipy.stats import poisson as sp_poisson
from curl_cffi import requests as curl_requests

SOFA_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 14; Pixel 9 Pro) AppleWebKit/537.36 Chrome/120.0.6099.230 Mobile Safari/537.36',
    'Accept': 'application/json', 'Origin': 'https://www.sofascore.com',
    'Referer': 'https://www.sofascore.com/', 'x-requested-with': '721637',
}

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, 'scrape_cache.db')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
RHO = -0.070
MAX_GOALS = 9

def _fetch_weather(lat, lon, date):
    try:
        import urllib.request, json
        url = f'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,relative_humidity_2m_mean&timezone=auto&start_date={date}&end_date={date}'
        r = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=10)
        d = json.loads(r.read().decode())
        if 'daily' in d:
            day = d['daily']
            return {
                'temp_max_c': day.get('temperature_2m_max', [None])[0],
                'temp_min_c': day.get('temperature_2m_min', [None])[0],
                'precipitation_mm': day.get('precipitation_sum', [None])[0],
                'wind_speed_max': day.get('wind_speed_10m_max', [None])[0],
                'humidity_mean': day.get('relative_humidity_2m_mean', [None])[0],
            }
    except: pass
    return None

def _travel_adjustment(home_team, away_team, venue_lat, venue_lon):
    try:
        from travel import get_travel_distance
        h_dist = get_travel_distance(home_team, venue_lat, venue_lon)
        a_dist = get_travel_distance(away_team, venue_lat, venue_lon)
        if h_dist is not None and a_dist is not None:
            h_factor = max(0.85, 1.0 - (h_dist / 1000 * 0.02))
            a_factor = max(0.85, 1.0 - (a_dist / 1000 * 0.02))
            return h_factor, a_factor, h_dist, a_dist
    except: pass
    return 1.0, 1.0, 0, 0

def _fetch_referee(event_id):
    try:
        from curl_cffi import requests
        r = requests.get(f'https://api.sofascore.com/api/v1/event/{event_id}', headers={'x-requested-with': 'XMLHttpRequest'}, impersonate='chrome', timeout=10)
        if r.status_code == 200:
            d = r.json()
            ev = d.get('event', {})
            ref = ev.get('referee') or {}
            venue = ev.get('venue') or {}
            return {
                'referee_name': ref.get('name', ''),
                'referee_country': ref.get('country', {}).get('name', ''),
                'venue_name': venue.get('name', ''),
                'venue_city': venue.get('city', {}).get('name', ''),
            }
    except: pass
    return None

VENUE_COORDS = {
    'Estadio Azteca': (19.303, -99.150),
    'MetLife Stadium': (40.813, -74.074),
    'AT&T Stadium': (32.747, -97.093),
    'SoFi Stadium': (33.953, -118.339),
    'Arrowhead Stadium': (39.049, -94.484),
    "Levi's Stadium": (37.403, -121.970),
    'NRG Stadium': (29.685, -95.411),
    'Lincoln Financial Field': (39.901, -75.168),
    'Mercedes-Benz Stadium': (33.755, -84.401),
    'Lumen Field': (47.595, -122.332),
    'Hard Rock Stadium': (25.958, -80.239),
    'Gillette Stadium': (42.091, -71.264),
    'BC Place': (49.276, -123.112),
    'Estadio BBVA': (25.672, -100.245),
    'Estadio Akron': (20.715, -103.379),
    'BMO Field': (43.633, -79.418),
}

VENUES = {
    'Estadio Azteca':       {'city': 'Mexico City', 'country': 'Mexico', 'altitude_m': 2240, 'surface': 'grass'},
    'MetLife Stadium':      {'city': 'East Rutherford', 'country': 'USA', 'altitude_m': 3, 'surface': 'grass'},
    'AT&T Stadium':         {'city': 'Arlington/Dallas', 'country': 'USA', 'altitude_m': 155, 'surface': 'artificial+grass hybrid'},
    'SoFi Stadium':         {'city': 'Los Angeles/Inglewood', 'country': 'USA', 'altitude_m': 34, 'surface': 'artificial+bermuda'},
    'Arrowhead Stadium':    {'city': 'Kansas City', 'country': 'USA', 'altitude_m': 259, 'surface': 'bermuda grass'},
    "Levi's Stadium":       {'city': 'Santa Clara/SF', 'country': 'USA', 'altitude_m': 20, 'surface': 'grass'},
    'NRG Stadium':          {'city': 'Houston', 'country': 'USA', 'altitude_m': 15, 'surface': 'artificial+bermuda'},
    'Lincoln Financial Field': {'city': 'Philadelphia', 'country': 'USA', 'altitude_m': 21, 'surface': 'grass'},
    'Mercedes-Benz Stadium': {'city': 'Atlanta', 'country': 'USA', 'altitude_m': 302, 'surface': 'artificial+bermuda'},
    'Lumen Field':          {'city': 'Seattle', 'country': 'USA', 'altitude_m': 5, 'surface': 'artificial turf'},
    'Hard Rock Stadium':    {'city': 'Miami', 'country': 'USA', 'altitude_m': 2, 'surface': 'bermuda grass'},
    'Gillette Stadium':     {'city': 'Boston/Foxborough', 'country': 'USA', 'altitude_m': 73, 'surface': 'grass'},
    'BC Place':             {'city': 'Vancouver', 'country': 'Canada', 'altitude_m': 4, 'surface': 'artificial turf'},
    'Estadio BBVA':         {'city': 'Monterrey', 'country': 'Mexico', 'altitude_m': 530, 'surface': 'grass'},
    'Estadio Akron':        {'city': 'Guadalajara', 'country': 'Mexico', 'altitude_m': 1600, 'surface': 'grass'},
    'BMO Field':            {'city': 'Toronto', 'country': 'Canada', 'altitude_m': 87, 'surface': 'grass'},
}

SOFA_NAME_TO_COUNTRY = {
    'USA': 'United States', 'England': 'England', 'Spain': 'Spain', 'Germany': 'Germany',
    'France': 'France', 'Italy': 'Italy', 'Netherlands': 'Netherlands',
    'Portugal': 'Portugal', 'Belgium': 'Belgium', 'Croatia': 'Croatia',
    'Denmark': 'Denmark', 'Switzerland': 'Switzerland', 'Serbia': 'Serbia',
    'Poland': 'Poland', 'Ukraine': 'Ukraine', 'Austria': 'Austria',
    'Sweden': 'Sweden', 'Scotland': 'Scotland', 'Norway': 'Norway',
    'Czechia': 'Czech Republic', 'T\u00fcrkiye': 'Turkey',
    'Greece': 'Greece', 'Hungary': 'Hungary', 'Romania': 'Romania',
    'Slovakia': 'Slovakia', 'Slovenia': 'Slovenia', 'Bulgaria': 'Bulgaria',
    'Ireland': 'Ireland', 'Finland': 'Finland', 'Iceland': 'Iceland',
    'Montenegro': 'Montenegro', 'Bosnia & Herzegovina': 'Bosnia & Herzegovina',
    'Albania': 'Albania', 'North Macedonia': 'North Macedonia', 'Georgia': 'Georgia',
    'Brazil': 'Brazil', 'Argentina': 'Argentina', 'Uruguay': 'Uruguay',
    'Colombia': 'Colombia', 'Ecuador': 'Ecuador', 'Paraguay': 'Paraguay',
    'Chile': 'Chile', 'Peru': 'Peru', 'Bolivia': 'Bolivia', 'Venezuela': 'Venezuela',
    'Mexico': 'Mexico', 'Canada': 'Canada', 'Costa Rica': 'Costa Rica',
    'Jamaica': 'Jamaica', 'Honduras': 'Honduras', 'Panama': 'Panama',
    'Japan': 'Japan', 'South Korea': 'South Korea', 'Australia': 'Australia',
    'Iran': 'Iran', 'Saudi Arabia': 'Saudi Arabia', 'Qatar': 'Qatar',
    'Iraq': 'Iraq', 'United Arab Emirates': 'United Arab Emirates',
    'Oman': 'Oman', 'Bahrain': 'Bahrain', 'Jordan': 'Jordan',
    'Uzbekistan': 'Uzbekistan', 'China': 'China',
    'Morocco': 'Morocco', 'Senegal': 'Senegal', 'Nigeria': 'Nigeria',
    'Egypt': 'Egypt', 'Algeria': 'Algeria', 'Cameroon': 'Cameroon',
    'Ghana': 'Ghana', "C\u00f4te d'Ivoire": 'Ivory Coast',
    'Cabo Verde': 'Cape Verde', 'Tunisia': 'Tunisia',
    'Mali': 'Mali', 'DR Congo': 'DR Congo', 'South Africa': 'South Africa',
    'Burkina Faso': 'Burkina Faso', 'Guinea': 'Guinea', 'Zambia': 'Zambia',
    'New Zealand': 'New Zealand', 'Haiti': 'Haiti', 'Cura\u00e7ao': 'Cura\u00e7ao',
}

_HOME_ADV = 1.15
_ALTITUDE_FACTOR_PER_M = 0.00004
_CACHE = {}
_CACHE_TIME = {}

def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS wc_fixtures (
        event_id INTEGER PRIMARY KEY,
        date TEXT, home_team TEXT, away_team TEXT, group_name TEXT,
        venue TEXT, home_elo REAL, away_elo REAL,
        predicted_home_xg REAL, predicted_away_xg REAL,
        pred_home_win REAL, pred_draw REAL, pred_away_win REAL,
        surface TEXT, altitude INTEGER, has_weather INTEGER DEFAULT 0
    )''')
    conn.commit()
    return conn

def _fetch_sofascore(path, retries=2):
    url = f'https://www.sofascore.com{path}'
    if url in _CACHE:
        entry = _CACHE[url]
        if time.time() - entry['time'] < 3600:
            return entry['data']
    for attempt in range(retries):
        try:
            time.sleep(0.35)
            r = curl_requests.get(url, headers=SOFA_HEADERS, impersonate='chrome120', timeout=15)
            if r.status_code == 200:
                data = r.json()
                _CACHE[url] = {'data': data, 'time': time.time()}
                return data
        except Exception:
            if attempt < retries - 1:
                time.sleep(1)
    return None

def get_venue(name):
    if not name:
        return None
    name_lower = name.strip().lower()
    for vname, info in VENUES.items():
        if vname.lower() == name_lower or name_lower in vname.lower() or vname.lower() in name_lower:
            return {**info, 'sofascore_name': vname}
    for vname, info in VENUES.items():
        city = info['city'].lower().split('/')[0].strip()
        if city in name_lower or name_lower in city:
            return {**info, 'sofascore_name': vname}
    return None

def fetch_wc_fixtures():
    conn = _db()
    conn.execute('DELETE FROM wc_fixtures')
    conn.commit()
    start = datetime(2026, 6, 15)
    end = datetime(2026, 7, 19)
    fixtures = []
    current = start
    while current <= end:
        date_str = current.strftime('%Y-%m-%d')
        data = _fetch_sofascore(f'/api/v1/sport/football/scheduled-events/{date_str}')
        if data and 'events' in data:
            for e in data['events']:
                tourn = e.get('tournament', {})
                utourn = tourn.get('uniqueTournament', {})
                if utourn.get('id') != 16:
                    continue
                eid = e.get('id')
                home = (e.get('homeTeam') or {}).get('name', '')
                away = (e.get('awayTeam') or {}).get('name', '')
                if not home or not away:
                    continue
                group = tourn.get('name', '')
                venue_name = ''
                venue_obj = None
                if e.get('roundInfo') and e['roundInfo'].get('venue'):
                    venue_name = e['roundInfo']['venue'].get('name', '')
                if not venue_name:
                    detail = _fetch_sofascore(f'/api/v1/event/{eid}')
                    if detail and 'event' in detail:
                        ev = detail['event']
                        v = ev.get('venue') or {}
                        venue_name = v.get('name', '') or (v.get('stadium') or {}).get('name', '')
                if venue_name:
                    venue_obj = get_venue(venue_name)
                alt = venue_obj['altitude_m'] if venue_obj else 0
                surface = venue_obj['surface'] if venue_obj else ''
                fixtures.append({
                    'event_id': eid, 'date': date_str,
                    'home_team': home, 'away_team': away,
                    'group_name': group, 'venue': venue_name,
                    'altitude': alt, 'surface': surface,
                })
        current += timedelta(days=1)
    for f in fixtures:
        conn.execute('''INSERT OR REPLACE INTO wc_fixtures
            (event_id, date, home_team, away_team, group_name, venue, surface, altitude, has_weather)
            VALUES (?,?,?,?,?,?,?,?,0)''',
            (f['event_id'], f['date'], f['home_team'], f['away_team'],
             f['group_name'], f['venue'], f['surface'], f['altitude']))
    conn.commit()
    conn.close()
    return fixtures

def get_elo_ratings():
    today = datetime.now().strftime('%Y-%m-%d')
    cache_key = f'clubelo_{today}'
    if cache_key in _CACHE:
        entry = _CACHE[cache_key]
        if time.time() - entry['time'] < 86400:
            return entry['data']
    ratings = {}
    for elo_date in [today, '2026-06-01', '2025-12-01', '2025-08-01']:
        try:
            time.sleep(0.5)
            r = curl_requests.get(f'https://api.clubelo.com/{elo_date}',
                headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            if r.status_code != 200:
                continue
            reader = csv.DictReader(io.StringIO(r.text))
            for row in reader:
                club = row.get('Club', '')
                country = row.get('Country', '')
                elo_str = row.get('Elo', '')
                if not elo_str:
                    continue
                elo_val = float(elo_str)
                country_clean = country.strip()
                sofa_name = SOFA_NAME_TO_COUNTRY.get(country_clean)
                if sofa_name:
                    if sofa_name not in ratings or elo_val > ratings.get(sofa_name, 0):
                        ratings[sofa_name] = elo_val
                if club:
                    if club not in ratings or elo_val > ratings.get(club, 0):
                        ratings[club] = elo_val
            if ratings:
                break
        except Exception:
            continue
    try:
        import soccerdata as sd
        clubelo = sd.ClubElo()
        df = clubelo.read_by_date(today)
        if df is not None:
            for idx in df.index:
                club = idx if isinstance(idx, str) else idx[0]
                country = str(df.loc[idx, 'country']) if 'country' in df.columns else ''
                elo_val = float(df.loc[idx, 'elo'])
                sofa_name = SOFA_NAME_TO_COUNTRY.get(country.strip())
                if sofa_name:
                    if sofa_name not in ratings or elo_val > ratings.get(sofa_name, 0):
                        ratings[sofa_name] = elo_val
                if club not in ratings or elo_val > ratings.get(club, 0):
                    ratings[club] = elo_val
    except Exception:
        pass
    known_teams = {
        'Brazil': 1920, 'Argentina': 1910, 'England': 1890, 'France': 1900,
        'Spain': 1880, 'Germany': 1850, 'Portugal': 1850, 'Netherlands': 1840,
        'Belgium': 1830, 'Croatia': 1790, 'Italy': 1840, 'Denmark': 1780,
        'Switzerland': 1760, 'Uruguay': 1830, 'Colombia': 1800, 'Mexico': 1770,
        'United States': 1760, 'Canada': 1730, 'Japan': 1750, 'South Korea': 1740,
        'Morocco': 1780, 'Senegal': 1760, 'Nigeria': 1750, 'Egypt': 1740,
        'Algeria': 1740, 'Ivory Coast': 1730, 'Ghana': 1700, 'Cameroon': 1700,
        'Tunisia': 1700, 'Australia': 1720, 'Iran': 1730, 'Saudi Arabia': 1680,
        'Ecuador': 1760, 'Paraguay': 1700, 'Sweden': 1720, 'Austria': 1720,
        'Poland': 1730, 'Ukraine': 1730, 'Serbia': 1740, 'Scotland': 1700,
        'Norway': 1710, 'Czech Republic': 1720, 'Turkey': 1710,
        'Cape Verde': 1640, 'Panama': 1630, 'Haiti': 1580,
        'Qatar': 1660, 'Iraq': 1650, 'Jordan': 1640, 'Uzbekistan': 1650,
        'DR Congo': 1660, 'Mali': 1660, 'South Africa': 1650,
        'New Zealand': 1650, 'Bosnia & Herzegovina': 1670,
        'Cura\u00e7ao': 1550,
    }
    for team, elo_val in known_teams.items():
        if team not in ratings:
            ratings[team] = elo_val
    _CACHE[cache_key] = {'data': ratings, 'time': time.time()}
    return ratings

def _dc_tau(x, y, lam, mu, rho):
    if x == 0 and y == 0:
        return 1.0 - lam * mu * rho
    if x == 0 and y == 1:
        return 1.0 + lam * rho
    if x == 1 and y == 0:
        return 1.0 + mu * rho
    if x == 1 and y == 1:
        return 1.0 - rho
    return 1.0

def _score_matrix(lam, mu, rho, max_goals=MAX_GOALS):
    lam = max(0.01, float(lam))
    mu = max(0.01, float(mu))
    h = sp_poisson.pmf(np.arange(max_goals + 1), lam)
    a = sp_poisson.pmf(np.arange(max_goals + 1), mu)
    M = np.outer(h, a)
    for i in (0, 1):
        for j in (0, 1):
            M[i, j] *= _dc_tau(i, j, lam, mu, rho)
    M = np.clip(M, 1e-15, None)
    return M / M.sum()

def _is_host(team, venue_obj):
    if not venue_obj:
        return False
    country = venue_obj['country']
    return ((country == 'USA' and 'united states' in team.lower()) or
            (country == 'Mexico' and 'mexico' in team.lower()) or
            (country == 'Canada' and 'canada' in team.lower()))

def predict_match(home_team, away_team, venue_name=None, date=None, elo_ratings=None, event_id=None):
    if elo_ratings is None:
        elo_ratings = get_elo_ratings()
    home_elo = elo_ratings.get(home_team, 1600)
    away_elo = elo_ratings.get(away_team, 1600)
    avg_elo = 1700
    atk_h = max(0.5, home_elo / avg_elo)
    atk_a = max(0.5, away_elo / avg_elo)
    def_h = max(0.5, avg_elo / home_elo)
    def_a = max(0.5, avg_elo / away_elo)
    league_avg = 1.3
    lam_h = league_avg * atk_h * def_a
    lam_a = league_avg * atk_a * def_h
    venue_obj = get_venue(venue_name) if venue_name else None
    alt = venue_obj['altitude_m'] if venue_obj else 0
    altitude_factor = 1.0 - (alt * _ALTITUDE_FACTOR_PER_M)
    home_adv = _HOME_ADV if _is_host(home_team, venue_obj) else 1.0
    lam_h *= home_adv * altitude_factor
    lam_a *= altitude_factor
    vname = venue_obj['sofascore_name'] if venue_obj else (venue_name or '')
    travel_h = travel_a = 1.0
    travel_h_km = travel_a_km = 0
    if vname and vname in VENUE_COORDS:
        vlats, vlons = VENUE_COORDS[vname]
        travel_h, travel_a, travel_h_km, travel_a_km = _travel_adjustment(home_team, away_team, vlats, vlons)
        lam_h *= travel_h
        lam_a *= travel_a
    lam_h = max(0.1, min(5.0, lam_h))
    lam_a = max(0.1, min(5.0, lam_a))
    probs = _score_matrix(lam_h, lam_a, RHO)
    home_win = float(np.tril(probs, -1).sum())
    draw = float(np.trace(probs))
    away_win = float(np.triu(probs, 1).sum())
    idx = np.arange(MAX_GOALS + 1)
    flat = [(i, j) for i in range(MAX_GOALS + 1) for j in range(MAX_GOALS + 1)]
    flat.sort(key=lambda s: -probs[s[0], s[1]])
    top_scores = [{'score': f'{i}-{j}', 'prob': round(float(probs[i, j]) * 100, 2)} for i, j in flat[:10]]
    total = idx[:, None] + idx[None, :]
    score_probs = {}
    for i in range(6):
        for j in range(6):
            score_probs[f'{i}-{j}'] = float(probs[i, j])
    weather = None
    ref_info = None
    if vname and vname in VENUE_COORDS and date:
        lat, lon = VENUE_COORDS[vname]
        weather = _fetch_weather(lat, lon, date)
    if event_id:
        ref_info = _fetch_referee(event_id)
    return {
        'home_team': home_team, 'away_team': away_team,
        'venue': vname,
        'home_elo': home_elo, 'away_elo': away_elo,
        'lambda_home': round(lam_h, 4), 'lambda_away': round(lam_a, 4),
        'home_win_prob': round(home_win * 100, 2),
        'draw_prob': round(draw * 100, 2),
        'away_win_prob': round(away_win * 100, 2),
        'most_likely_score': top_scores[0]['score'],
        'exact_score_prob': top_scores[0]['prob'],
        'top_scores': top_scores,
        'score_probs': score_probs,
        'probs_1x2': {'home': round(home_win * 100, 2), 'draw': round(draw * 100, 2), 'away': round(away_win * 100, 2)},
        'over_2_5': round(float(probs[total > 2].sum()) * 100, 2),
        'under_2_5': round(float(probs[total <= 2].sum()) * 100, 2),
        'btts_yes': round(float(probs[1:, 1:].sum()) * 100, 2),
        'btts_no': round(float((probs[0, 0] + probs[0, 1:] + probs[1:, 0]).sum()) * 100, 2),
        'expected_goals_home': round(lam_h, 3),
        'expected_goals_away': round(lam_a, 3),
        'altitude': alt,
        'home_adv_applied': home_adv,
        'altitude_factor': altitude_factor,
        'travel_home_km': round(travel_h_km, 1),
        'travel_away_km': round(travel_a_km, 1),
        'travel_home_factor': round(travel_h, 4),
        'travel_away_factor': round(travel_a, 4),
        'weather': weather,
        'referee': ref_info,
    }

def predict_all():
    conn = _db()
    cur = conn.execute('SELECT event_id, date, home_team, away_team, group_name, venue, surface, altitude FROM wc_fixtures ORDER BY date')
    rows = cur.fetchall()
    conn.close()
    elo_ratings = get_elo_ratings()
    results = []
    for row in rows:
        eid, date_str, home, away, group_name, venue_name, surface, alt = row
        pred = predict_match(home, away, venue_name, date_str, elo_ratings, event_id=eid)
        pred['event_id'] = eid
        pred['date'] = date_str
        pred['group_name'] = group_name
        pred['surface'] = surface
        results.append(pred)
        conn2 = _db()
        conn2.execute('''UPDATE wc_fixtures SET
            home_elo=?, away_elo=?, predicted_home_xg=?, predicted_away_xg=?,
            pred_home_win=?, pred_draw=?, pred_away_win=?
            WHERE event_id=?''',
            (pred['home_elo'], pred['away_elo'], pred['lambda_home'], pred['lambda_away'],
             pred['home_win_prob'], pred['draw_prob'], pred['away_win_prob'], eid))
        conn2.commit()
        conn2.close()
    # Also save to JSON
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, 'wc_predictions.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    return results

def analyze_match_deep(home_team, away_team, competition='World Cup', **kwargs):
    venue_name = kwargs.get('venue_name', '')
    date = kwargs.get('date', datetime.now().strftime('%Y-%m-%d'))
    pred = predict_match(home_team, away_team, venue_name, date)
    return {
        'home_win_prob': pred['home_win_prob'],
        'draw_prob': pred['draw_prob'],
        'away_win_prob': pred['away_win_prob'],
        'most_likely_score': pred['most_likely_score'],
        'exact_score_prob': pred['exact_score_prob'],
        'expected_goals_home': pred['expected_goals_home'],
        'expected_goals_away': pred['expected_goals_away'],
        'top_scores': pred['top_scores'],
        'top_3': pred['top_scores'][:3],
        'over_2_5': pred['over_2_5'],
        'under_2_5': pred['under_2_5'],
        'btts_yes': pred['btts_yes'],
        'lambda_home': pred['lambda_home'],
        'lambda_away': pred['lambda_away'],
        'probs_1x2': pred['probs_1x2'],
        'score_probs': pred['score_probs'],
        'competition': 'World Cup',
        'source': 'wc2026_predictor',
    }

if __name__ == '__main__':
    print('=== WC2026 Predictor ===')
    print('Fetching fixtures from SofaScore...')
    fixtures = fetch_wc_fixtures()
    print(f'Found {len(fixtures)} WC2026 fixtures')
    print('Fetching Elo ratings...')
    elos = get_elo_ratings()
    print(f'Got Elo ratings for {len(elos)} teams')
    print('Predicting all matches...')
    predictions = predict_all()
    print(f'\n{"Date":<12} {"Home":<22} {"Away":<22} {"Score":<8} {"Home%":<8} {"Draw%":<8} {"Away%":<8} {"Venue":<25}')
    print('-' * 115)
    for p in predictions[:30]:
        venue_short = p['venue'][:25] if p['venue'] else 'N/A'
        print(f'{p["date"]:<12} {p["home_team"]:<22} {p["away_team"]:<22} {p["most_likely_score"]:<8} {p["home_win_prob"]:<8} {p["draw_prob"]:<8} {p["away_win_prob"]:<8} {venue_short:<25}')
    if len(predictions) > 30:
        print(f'... and {len(predictions) - 30} more')
    print(f'\nSaved predictions to output/wc_predictions.json')
    print('Done.')
