import os, json, sqlite3, time
import numpy as np
from scipy.optimize import minimize_scalar
from scipy.stats import poisson as sp_poisson
from sklearn.isotonic import IsotonicRegression

import understat_scraper as uss

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

LEAGUES = ['EPL', 'La_Liga', 'Bundesliga', 'Serie_A', 'Ligue_1']
SEASONS = ['2025', '2024', '2023', '2022', '2021', '2020', '2019', '2018', '2017', '2016', '2015']
XI_DECAY = 0.001

_TRAINED = None

def _ensure_db():
    conn = sqlite3.connect(DB, timeout=5)
    conn.execute("""CREATE TABLE IF NOT EXISTS model_params (
        param TEXT PRIMARY KEY, value TEXT, updated REAL
    )""")
    return conn

def collect_matches():
    matches = []
    for league in LEAGUES:
        for season in SEASONS:
            data = uss.get_league_data(league, season)
            if not data: continue
            teams = data.get('teams', {})
            for tid, td in teams.items():
                for m in td.get('history', []):
                    if m.get('h_a') != 'h': continue
                    hg = int(m.get('scored', 0))
                    ag = int(m.get('missed', 0))
                    hx = float(m.get('xG', 0) or 0)
                    ax = float(m.get('xGA', 0) or 0)
                    if hx <= 0 or ax <= 0: continue
                    matches.append({
                        'home_goals': hg, 'away_goals': ag,
                        'lambda_home': hx, 'lambda_away': ax,
                        'season': season, 'league': league,
                    })
    return matches

def _dc_tau(x, y, lam, mu, rho):
    if x == 0 and y == 0: return 1.0 - lam * mu * rho
    if x == 0 and y == 1: return 1.0 + lam * rho
    if x == 1 and y == 0: return 1.0 + mu * rho
    if x == 1 and y == 1: return 1.0 - rho
    return 1.0

def fit_rho_mle(matches, xi=XI_DECAY):
    hg = np.array([m['home_goals'] for m in matches], dtype=int)
    ag = np.array([m['away_goals'] for m in matches], dtype=int)
    lam = np.clip(np.array([m['lambda_home'] for m in matches], float), 0.01, None)
    mu = np.clip(np.array([m['lambda_away'] for m in matches], float), 0.01, None)
    max_season = max(int(m['season']) for m in matches) if matches else 2025
    days_ago = np.array([(max_season - int(m['season'])) * 365 for m in matches], float)
    w = np.exp(-xi * days_ago)
    w = w / w.sum() * len(matches)
    base = (sp_poisson.logpmf(hg, lam) + sp_poisson.logpmf(ag, mu))

    def neg_ll(rho):
        tau = np.array([_dc_tau(int(x), int(y), l, u, rho) for x, y, l, u in zip(hg, ag, lam, mu)])
        tau = np.clip(tau, 1e-12, None)
        ll = w * (base + np.log(tau))
        return -np.sum(ll)

    res = minimize_scalar(neg_ll, bounds=(-0.25, 0.10), method='bounded')
    rho = float(res.x) if res.success else -0.07
    return max(-0.25, min(0.10, rho))

def fit_per_league_rho():
    all_matches = collect_matches()
    result = {'global': -0.07}
    for league in LEAGUES:
        lm = [m for m in all_matches if m['league'] == league]
        if len(lm) > 100:
            result[league] = fit_rho_mle(lm)
    result['global'] = fit_rho_mle(all_matches)
    return result, all_matches

def save_params(rhos, matches):
    conn = _ensure_db()
    conn.execute('REPLACE INTO model_params VALUES (?,?,?)', ('rhos', json.dumps(rhos), time.time()))
    conn.execute('REPLACE INTO model_params VALUES (?,?,?)', ('n_matches', str(len(matches)), time.time()))
    conn.execute('REPLACE INTO model_params VALUES (?,?,?)', ('trained_at', str(time.time()), time.time()))
    conn.commit(); conn.close()

def load_params():
    conn = _ensure_db()
    rhos_row = conn.execute("SELECT value FROM model_params WHERE param='rhos'").fetchone()
    n_row = conn.execute("SELECT value FROM model_params WHERE param='n_matches'").fetchone()
    trained_row = conn.execute("SELECT value FROM model_params WHERE param='trained_at'").fetchone()
    conn.close()
    if rhos_row:
        return json.loads(rhos_row[0])
    return None

def get_rho(league=None, default=-0.07):
    global _TRAINED
    if _TRAINED is None:
        _TRAINED = load_params()
    if _TRAINED and league and league in _TRAINED:
        return _TRAINED[league]
    if _TRAINED and 'global' in _TRAINED:
        return _TRAINED['global']
    return default

def train_and_save():
    print('Collecting training data...')
    rhos, matches = fit_per_league_rho()
    print(f'  Total matches: {len(matches)}')
    for k, v in rhos.items():
        print(f'  rho [{k}] = {v:.4f}')
    save_params(rhos, matches)
    global _TRAINED
    _TRAINED = rhos
    return rhos

if __name__ == '__main__':
    train_and_save()
