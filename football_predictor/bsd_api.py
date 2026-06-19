"""BSD (Bzzoiro Sports Data) API — replaces The Odds API entirely. No rate limits."""
import os, json, time, sqlite3
import requests as _requests

def _load_key():
    k = os.environ.get('BSD_API_KEY', '')
    if k:
        return k
    try:
        from dotenv import load_dotenv
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        if os.path.exists(env_path):
            load_dotenv(env_path)
            k = os.environ.get('BSD_API_KEY', '')
    except:
        pass
    return k

API_KEY = _load_key()
BASE = 'https://sports.bzzoiro.com/api'
_cache = {}
_cache_time = {}
_CACHE_DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

def _init_db():
    try:
        conn = sqlite3.connect(_CACHE_DB, timeout=5)
        conn.execute('''CREATE TABLE IF NOT EXISTS bsd_cache
            (key TEXT PRIMARY KEY, data TEXT, updated REAL)''')
        conn.commit()
        conn.close()
    except:
        pass
_init_db()

def _cached_or_fetch(key, url, cache_minutes=30):
    now = time.time()
    ttl = cache_minutes * 60
    if key in _cache and (now - _cache_time.get(key, 0)) < ttl:
        return _cache[key]
    try:
        conn = sqlite3.connect(_CACHE_DB, timeout=3)
        cur = conn.execute('SELECT data, updated FROM bsd_cache WHERE key = ?', (key,))
        row = cur.fetchone()
        conn.close()
        if row:
            data = json.loads(row[0])
            age = now - row[1]
            if age < min(ttl, 86400):
                _cache[key] = data
                _cache_time[key] = now
                return data
    except:
        pass
    if not API_KEY:
        return None
    try:
        r = _requests.get(url, headers={"Authorization": f"Token {API_KEY}"}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            _cache[key] = data
            _cache_time[key] = now
            try:
                conn = sqlite3.connect(_CACHE_DB, timeout=3)
                conn.execute('INSERT OR REPLACE INTO bsd_cache VALUES (?, ?, ?)',
                             (key, json.dumps(data, default=str), now))
                conn.commit()
                conn.close()
            except:
                pass
            return data
    except:
        pass
    return None

def search_events(home_team, away_team, date=None):
    """Find a BSD event by team names. Returns event dict or None."""
    key = f"ev_{home_team}_{away_team}_{date or ''}"
    limit = 50 if not date else 10
    for offset in range(0, 200, limit):
        url = f"{BASE}/events/?limit={limit}&offset={offset}"
        if date:
            url += f"&date_from={date}&date_to={date}"
        data = _cached_or_fetch(f"{key}_o{offset}", url, 5)
        if not data or 'results' not in data:
            break
        h_lower = home_team.lower().strip()
        a_lower = away_team.lower().strip()
        for e in data['results']:
            eh = e.get('home_team', '').lower().strip()
            ea = e.get('away_team', '').lower().strip()
            if (h_lower in eh or eh in h_lower) and (a_lower in ea or ea in a_lower):
                return e
            if (h_lower in ea or ea in h_lower) and (a_lower in eh or eh in a_lower):
                return e
        if not data.get('next'):
            break
    return None

def get_odds_for_match(home_team, away_team, date=None):
    """Fetch BSD event + odds-comparison. Returns BSD event dict with enriched odds."""
    event = search_events(home_team, away_team, date)
    if not event:
        return None
    eid = event['id']
    odds_data = _cached_or_fetch(f"odds_{eid}",
        f"{BASE}/odds/compare/?event={eid}", 5)
    result = dict(event)
    result['bsd_odds_comparison'] = odds_data
    return result

def extract_market_probabilities(bsd_event):
    """Convert BSD event odds to fair probabilities. Compatible with prediction_engine."""
    if not bsd_event:
        return None
    odds = bsd_event.get('odds_home')
    if odds is None:
        odds_comp = bsd_event.get('bsd_odds_comparison', {})
        mkts = odds_comp.get('markets', {})
        mkt_1x2 = mkts.get('1x2', {})
        if mkt_1x2:
            home_data = mkt_1x2.get(bsd_event.get('home_team', ''), {}) or mkt_1x2.get('Home', {})
            draw_data = mkt_1x2.get('Draw', {})
            away_data = mkt_1x2.get(bsd_event.get('away_team', ''), {}) or mkt_1x2.get('Away', {})
            b = home_data.get('best_odds')
            d = draw_data.get('best_odds')
            a = away_data.get('best_odds')
        else:
            return None
    else:
        b = float(bsd_event['odds_home'])
        d = float(bsd_event['odds_draw'])
        a = float(bsd_event['odds_away'])
    if not all([b, d, a]) or b <= 0 or d <= 0 or a <= 0:
        return None
    inv_sum = 1.0/b + 1.0/d + 1.0/a
    if inv_sum <= 0:
        return None
    fair_h = (1.0/b) / inv_sum * 100
    fair_d = (1.0/d) / inv_sum * 100
    fair_a = (1.0/a) / inv_sum * 100
    overround = (inv_sum - 1.0) * 100
    return {
        'implied_probs': {'home': fair_h, 'draw': fair_d, 'away': fair_a},
        'fair_probs': {'home': round(fair_h, 2), 'draw': round(fair_d, 2), 'away': round(fair_a, 2)},
        'avg_overround': round(overround, 2),
        'bookmaker_count': 1,
        'available': True,
    }
