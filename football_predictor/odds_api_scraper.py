"""The Odds API scraper — market odds, implied probabilities, overround removal"""
import os, json, time, sqlite3, requests

ODDS_API_KEY = os.environ.get('ODDS_API_KEY', '')
ODDS_API_BASE = 'https://api.the-odds-api.com/v4'
_cache = {}
_cache_time = {}
_CACHE_DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

def _init_db():
    try:
        conn = sqlite3.connect(_CACHE_DB, timeout=5)
        conn.execute('''CREATE TABLE IF NOT EXISTS odds_cache
            (url TEXT PRIMARY KEY, data TEXT, updated REAL)''')
        conn.commit()
        conn.close()
    except:
        pass

_init_db()

def _cached_or_fetch(url, cache_minutes=30):
    now = time.time()
    cache_ttl = cache_minutes * 60
    if url in _cache and (now - _cache_time.get(url, 0)) < cache_ttl:
        return _cache[url]
    try:
        conn = sqlite3.connect(_CACHE_DB, timeout=3)
        cur = conn.execute('SELECT data, updated FROM odds_cache WHERE url = ?', (url,))
        row = cur.fetchone()
        conn.close()
        if row:
            data = json.loads(row[0])
            age = now - row[1]
            if age < min(cache_ttl, 86400):
                _cache[url] = data
                _cache_time[url] = now
                return data
    except:
        pass
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            _cache[url] = data
            _cache_time[url] = now
            try:
                conn = sqlite3.connect(_CACHE_DB, timeout=3)
                conn.execute('INSERT OR REPLACE INTO odds_cache VALUES (?, ?, ?)',
                             (url, json.dumps(data, default=str), now))
                conn.commit()
                conn.close()
            except:
                pass
            return data
        elif r.status_code == 422:
            return []
    except:
        pass
    return None

def get_remaining_requests():
    """Check how many API requests are left this month"""
    if not ODDS_API_KEY:
        return 0
    url = f"{ODDS_API_BASE}/sports/?apiKey={ODDS_API_KEY}"
    try:
        r = requests.get(url, timeout=10)
        return int(r.headers.get('x-requests-remaining', 0))
    except:
        return 0

def list_sports():
    """List all available sports"""
    if not ODDS_API_KEY:
        return []
    url = f"{ODDS_API_BASE}/sports/?apiKey={ODDS_API_KEY}"
    data = _cached_or_fetch(url, 1440)
    return data if data else []

def list_active_soccer_leagues():
    """List soccer leagues that have upcoming matches"""
    sports = list_sports()
    soccer = [s for s in sports if "soccer" in s["key"] and not s.get("has_outrights")]
    active = []
    for s in soccer:
        url = f"{ODDS_API_BASE}/sports/{s['key']}/odds/?apiKey={ODDS_API_KEY}&regions=uk&markets=h2h"
        data = _cached_or_fetch(url, 10)
        if data and len(data) > 0:
            active.append({'key': s['key'], 'title': s.get('title', s['key']), 'match_count': len(data)})
    return active

_LEAGUE_ALIASES = {
    'allsvenskan': 'soccer_sweden_allsvenskan',
    'sweden': 'soccer_sweden_allsvenskan',
    'premier league': 'soccer_epl',
    'epl': 'soccer_epl',
    'la liga': 'soccer_spain_la_liga',
    'bundesliga': 'soccer_germany_bundesliga',
    'serie a': 'soccer_italy_serie_a',
    'ligue 1': 'soccer_france_ligue_one',
    'brazil': 'soccer_brazil_serie_a',
    'mls': 'soccer_usa_mls',
    'eredivisie': 'soccer_netherlands_eredivisie',
    'norway': 'soccer_norway_eliteserien',
    'eliteserien': 'soccer_norway_eliteserien',
    'finland': 'soccer_finland_veikkausliiga',
    'veikkausliiga': 'soccer_finland_veikkausliiga',
    'chile': 'soccer_chile_campeonato',
    'china': 'soccer_china_superleague',
    'libertadores': 'soccer_conmebol_copa_libertadores',
    'sudamericana': 'soccer_conmebol_copa_sudamericana',
    'world cup': 'soccer_fifa_world_cup',
    'ireland': 'soccer_league_of_ireland',
    'spain segunda': 'soccer_spain_segunda_division',
    'superettan': 'soccer_sweden_superettan',
}

def get_odds_for_match(home_team, away_team, league_key=None):
    """Fetch odds for a specific match. Returns list of bookmaker odds."""
    if not ODDS_API_KEY:
        return None
    keys_to_try = []
    if league_key:
        lk = league_key.lower().strip()
        if lk in _LEAGUE_ALIASES:
            keys_to_try = [_LEAGUE_ALIASES[lk]]
        else:
            keys_to_try = [lk]
    if not keys_to_try:
        keys_to_try = list(_LEAGUE_ALIASES.values())
    # Deduplicate while preserving order
    seen = set()
    keys_to_try = [x for x in keys_to_try if not (x in seen or seen.add(x))]
    h_lower = home_team.lower().strip()
    a_lower = away_team.lower().strip()
    for sk in keys_to_try:
        url = (f"{ODDS_API_BASE}/sports/{sk}/odds/"
               f"?apiKey={ODDS_API_KEY}&regions=uk,eu,us&markets=h2h&oddsFormat=decimal")
        events = _cached_or_fetch(url, 10)
        if not events:
            continue
        for event in events:
            eh = event.get('home_team', '').lower().strip()
            ea = event.get('away_team', '').lower().strip()
            if (h_lower in eh or eh in h_lower) and (a_lower in ea or ea in a_lower):
                return event
            if (h_lower in ea or ea in h_lower) and (a_lower in eh or eh in a_lower):
                return event
    return None

def extract_market_probabilities(event):
    """Convert bookmaker odds to fair (overround-removed) probabilities.
    Returns dict with home/draw/away probabilities + edge info."""
    if not event or 'bookmakers' not in event:
        return None
    all_probs = []
    for bk in event.get('bookmakers', []):
        for mkt in bk.get('markets', []):
            if mkt['key'] != 'h2h':
                continue
            outcomes = {o['name'].lower(): o['price'] for o in mkt.get('outcomes', [])}
            if len(outcomes) < 3:
                continue
            inv_sum = sum(1.0 / v for v in outcomes.values())
            fair = {k: (1.0 / v) / inv_sum * 100 for k, v in outcomes.items()}
            fair['bookmaker'] = bk['title']
            fair['overround_pct'] = round((inv_sum - 1.0) * 100, 2)
            all_probs.append(fair)
    if not all_probs:
        return None
    avg = {'home': 0.0, 'draw': 0.0, 'away': 0.0}
    total_overround = 0.0
    for p in all_probs:
        h_key = event.get('home_team', '').lower()
        a_key = event.get('away_team', '').lower()
        avg['home'] += p.get(h_key, p.get('home', 0))
        avg['draw'] += p.get('draw', 0)
        avg['away'] += p.get(a_key, p.get('away', 0))
        total_overround += p.get('overround_pct', 0)
    count = len(all_probs)
    avg = {k: round(v / count, 2) for k, v in avg.items()}
    avg_overround = round(total_overround / count, 2) if count > 0 else 0.0
    # Find the best value: outcome with highest true_prob vs market_prob
    best = None
    for outcome in ['home', 'draw', 'away']:
        market_prob = avg.get(outcome, 0)
        if best is None or market_prob > best['market_prob']:
            best = {'outcome': outcome, 'market_prob': market_prob}
    return {
        'implied_probs': avg,
        'fair_probs': {k: round(v, 2) for k, v in avg.items()},
        'best_value': best,
        'avg_overround': avg_overround,
        'bookmaker_count': count,
        'bookmakers': all_probs[:5],
    }

def find_value_bets(match_predictions, odds_data, min_edge_pct=5.0):
    """Compare true probabilities (from prediction engine) vs market implied probabilities.
    Returns list of value bet opportunities."""
    if not odds_data or not match_predictions:
        return []
    results = []
    for outcome, true_prob_key in [('home', 'home_prob'), ('draw', 'draw_prob'), ('away', 'away_prob')]:
        true_prob = match_predictions.get(true_prob_key, 0)
        market_prob = odds_data['fair_probs'].get(outcome, 0)
        if true_prob <= 0 or market_prob <= 0:
            continue
        edge = ((true_prob - market_prob) / market_prob) * 100
        if edge > min_edge_pct:
            odds_value = round(100.0 / true_prob, 2) if true_prob > 0 else 0
            results.append({
                'outcome': outcome,
                'true_prob': round(true_prob, 2),
                'market_prob': round(market_prob, 2),
                'edge_pct': round(edge, 2),
                'fair_odds': round(100.0 / market_prob, 2),
                'suggested_odds_cutoff': round(100.0 / true_prob, 2),
                'kelly_fraction': round(kelly_criterion(true_prob, 100.0 / market_prob), 4),
                'verdict': 'STRONG' if edge > 15 else ('MODERATE' if edge > 10 else 'WEAK'),
            })
    return sorted(results, key=lambda x: x['edge_pct'], reverse=True)

def kelly_criterion(prob_pct, odds_dec):
    p = prob_pct / 100.0
    b = odds_dec - 1.0
    if b <= 0:
        return 0.0
    f = (b * p - (1 - p)) / b
    return round(max(0.0, min(f, 0.25)), 4)
