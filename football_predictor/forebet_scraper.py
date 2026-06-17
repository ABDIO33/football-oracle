"""Forebet scraper — mathematical football predictions + injury data"""
import os, re, json, sqlite3, time
from datetime import datetime, timedelta
from curl_cffi import requests
from bs4 import BeautifulSoup

BASE = 'https://www.forebet.com'
HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Linux; Android 14; Pixel 9 Pro) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.6099.230 Mobile Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-GB,en;q=0.9',
    'Referer': 'https://www.forebet.com/',
}
DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
_CACHE = {}
_LAST_REQ = 0

def _fetch(url, cache_minutes=30):
    global _LAST_REQ
    if url in _CACHE:
        entry = _CACHE[url]
        if time.time() - entry['time'] < cache_minutes * 60:
            return entry['data']
    now = time.time()
    if now - _LAST_REQ < 1.0:
        time.sleep(1.0 - (now - _LAST_REQ))
    try:
        r = requests.get(url, headers=HEADERS, impersonate="chrome120", timeout=60)
        _LAST_REQ = time.time()
        if r.status_code == 200:
            html = r.text
            _CACHE[url] = {'data': html, 'time': time.time()}
            return html
    except Exception as e:
        print(f'[Forebet] Fetch error: {e}')
    return None

def _parse_rcnt_div(rcnt):
    """Extract match prediction data from a single div.rcnt element."""
    try:
        league_el = rcnt.select_one('.shortTag')
        league = league_el.get_text(strip=True) if league_el else ''
        home_el = rcnt.select_one('.homeTeam span[itemprop="name"]')
        away_el = rcnt.select_one('.awayTeam span[itemprop="name"]')
        home_team = home_el.get_text(strip=True) if home_el else ''
        away_team = away_el.get_text(strip=True) if away_el else ''
        date_el = rcnt.select_one('.date_bah')
        date_str = date_el.get_text(strip=True) if date_el else ''
        time_el = rcnt.select_one('time[datetime]')
        dt_str = time_el.get('datetime', '') if time_el else ''
        probs = rcnt.select('.fprc span')
        prob_h = int(probs[0].get_text(strip=True)) if len(probs) > 0 else 0
        prob_d = int(probs[1].get_text(strip=True)) if len(probs) > 1 else 0
        prob_a = int(probs[2].get_text(strip=True)) if len(probs) > 2 else 0
        forepr_el = rcnt.select_one('.forepr span')
        forebet_pred = forepr_el.get_text(strip=True) if forepr_el else ''
        cs_el = rcnt.select_one('.ex_sc')
        correct_score = cs_el.get_text(strip=True) if cs_el else ''
        avg_el = rcnt.select_one('.avg_sc')
        avg_goals = avg_el.get_text(strip=True) if avg_el else ''
        weather_el = rcnt.select_one('.prwth .wnums')
        weather = weather_el.get_text(strip=True) if weather_el else ''
        score_el = rcnt.select_one('.l_scr')
        score = score_el.get_text(strip=True) if score_el else ''
        status_el = rcnt.select_one('.lmin_td')
        status = status_el.get_text(strip=True) if status_el else ''
        total_prob = prob_h + prob_d + prob_a
        if total_prob > 0:
            prob_h_pct = prob_h / total_prob
            prob_d_pct = prob_d / total_prob
            prob_a_pct = prob_a / total_prob
        else:
            prob_h_pct = prob_d_pct = prob_a_pct = 0.0
        avg_goals_val = 0.0
        if avg_goals:
            try:
                avg_goals_val = float(avg_goals)
            except:
                pass
        return {
            'league': league,
            'home_team': home_team,
            'away_team': away_team,
            'date_str': date_str,
            'datetime_iso': dt_str,
            'prob_h': prob_h,
            'prob_d': prob_d,
            'prob_a': prob_a,
            'prob_h_pct': round(prob_h_pct, 4),
            'prob_d_pct': round(prob_d_pct, 4),
            'prob_a_pct': round(prob_a_pct, 4),
            'forebet_pred': forebet_pred,
            'correct_score': correct_score,
            'avg_goals': avg_goals_val,
            'weather': weather,
            'score': score,
            'status': status.strip() if status else '',
        }
    except Exception as e:
        return None

def get_predictions(url='/en/football-tips-and-predictions-for-today', cache_minutes=15):
    """Fetch Forebet predictions page and parse all match rows."""
    full_url = f'{BASE}{url}'
    html = _fetch(full_url, cache_minutes)
    if not html:
        return []
    soup = BeautifulSoup(html, 'html.parser')
    matches = []
    for rcnt in soup.select('div.rcnt'):
        data = _parse_rcnt_div(rcnt)
        if data and data['home_team'] and data['away_team']:
            matches.append(data)
    return matches

def get_today_predictions():
    return get_predictions('/en/football-tips-and-predictions-for-today', cache_minutes=15)

def get_yesterday_predictions():
    return get_predictions('/en/football-predictions-from-yesterday', cache_minutes=60)

def get_tomorrow_predictions():
    return get_predictions('/en/football-tips-and-predictions-for-tomorrow', cache_minutes=15)

def _db():
    conn = sqlite3.connect(DB)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS forebet_predictions (
            match_key TEXT PRIMARY KEY,
            date TEXT, home_team TEXT, away_team TEXT,
            prob_h REAL, prob_d REAL, prob_a REAL,
            forebet_pred TEXT, correct_score TEXT, avg_goals REAL,
            weather TEXT, score TEXT,
            fetched_at TEXT
        )
    ''')
    conn.commit()
    return conn

def store_predictions(matches, date_label=None):
    """Store predictions in DB for later training use."""
    if not date_label:
        date_label = datetime.now().strftime('%Y-%m-%d')
    conn = _db()
    stored = 0
    for m in matches:
        key = f"{date_label}|{m['home_team']}|{m['away_team']}".lower()
        conn.execute('''
            INSERT OR REPLACE INTO forebet_predictions
            (match_key, date, home_team, away_team,
             prob_h, prob_d, prob_a, forebet_pred, correct_score, avg_goals,
             weather, score, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            key, date_label, m['home_team'], m['away_team'],
            m['prob_h_pct'], m['prob_d_pct'], m['prob_a_pct'],
            m['forebet_pred'], m['correct_score'], m['avg_goals'],
            m['weather'], m['score'],
            datetime.now().isoformat()
        ))
        stored += 1
    conn.commit()
    conn.close()
    return stored

def get_stored_predictions(date=None, home_team=None, away_team=None):
    """Retrieve stored Forebet predictions for training."""
    conn = _db()
    q = 'SELECT * FROM forebet_predictions WHERE 1=1'
    params = []
    if date:
        q += ' AND date = ?'
        params.append(date)
    if home_team:
        q += ' AND LOWER(home_team) LIKE ?'
        params.append(f'%{home_team.lower()}%')
    if away_team:
        q += ' AND LOWER(away_team) LIKE ?'
        params.append(f'%{away_team.lower()}%')
    q += ' ORDER BY date DESC'
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return rows

def find_prediction_for_match(home_team, away_team, match_date=None):
    """Find the best matching Forebet prediction for a given match.
    Tries the given date, then today, then yesterday, then any date."""
    conn = _db()
    match_date = match_date or datetime.now().strftime('%Y-%m-%d')
    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    dates_to_try = [match_date, today, yesterday]
    # Deduplicate while preserving order
    seen = set()
    dates_to_try = [d for d in dates_to_try if not (d in seen or seen.add(d))]
    dates_to_try.append(None)  # fallback: any date
    home_lower = home_team.lower()
    away_lower = away_team.lower()
    for dt in dates_to_try:
        if dt:
            rows = conn.execute('''
                SELECT * FROM forebet_predictions
                WHERE date = ? ORDER BY fetched_at DESC
            ''', (dt,)).fetchall()
        else:
            rows = conn.execute('''
                SELECT * FROM forebet_predictions
                ORDER BY date DESC, fetched_at DESC
            ''').fetchall()
        for row in rows:
            db_home = row[2].lower() if row[2] else ''
            db_away = row[3].lower() if row[3] else ''
            if (home_lower in db_home or db_home in home_lower) and \
               (away_lower in db_away or db_away in away_lower):
                conn.close()
                return {
                    'prob_h': row[4], 'prob_d': row[5], 'prob_a': row[6],
                    'forebet_pred': row[7], 'correct_score': row[8],
                    'avg_goals': row[9], 'weather': row[10], 'score': row[11],
                }
    conn.close()
    return None

if __name__ == '__main__':
    print('=== Forebet Scraper ===')
    preds = get_today_predictions()
    print(f'Today: {len(preds)} matches')
    for p in preds[:5]:
        print(f'  {p["home_team"]} vs {p["away_team"]} | '
              f'{p["prob_h"]}-{p["prob_d"]}-{p["prob_a"]} | '
              f'{p["forebet_pred"]} {p["correct_score"]} | ø{p["avg_goals"]} | {p["weather"]}')
    n = store_predictions(preds)
    print(f'Stored: {n} predictions')
