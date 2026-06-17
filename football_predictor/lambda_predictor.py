"""
XGBoost λ-regressor — predicts λ_home and λ_away from walkforward features
Then feeds λ into Dixon-Coles for proper exact score distribution
"""
import sqlite3, os, sys, json, numpy as np, joblib
from datetime import datetime
try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    from sklearn.ensemble import GradientBoostingRegressor
    HAS_XGB = False

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
os.makedirs(MODEL_DIR, exist_ok=True)

FEATURES = [
    'home_elo', 'away_elo', 'elo_diff',
    'home_xg_for', 'home_xg_against',
    'away_xg_for', 'away_xg_against',
    'home_form', 'away_form',
    'home_matches_played', 'away_matches_played',
    'home_shots_for', 'away_shots_for',
    'home_shots_against', 'away_shots_against',
    'home_xg_diff', 'away_xg_diff',
    'home_shot_diff', 'away_shot_diff',
    'home_days_rest', 'away_days_rest',
    'forebet_prob_h', 'forebet_prob_d', 'forebet_prob_a',
    'forebet_available',
]

def _load_training_data(start_date='2024-06-15', end_date='2026-06-14'):
    """Load walkforward features + actual goals for training."""
    conn = sqlite3.connect(DB)
    cur = conn.execute('''
        SELECT r.id, r.date, r.home_team, r.away_team,
               r.home_score, r.away_score, r.start_timestamp as r_ts,
               wf_h.elo, wf_a.elo,
               wf_h.rolling_xg_for, wf_h.rolling_xg_against,
               wf_a.rolling_xg_for, wf_a.rolling_xg_against,
               wf_h.form_points, wf_a.form_points,
               wf_h.matches_played, wf_a.matches_played,
               wf_h.rolling_shots_for, wf_a.rolling_shots_for,
               wf_h.rolling_shots_against, wf_a.rolling_shots_against,
               COALESCE(fp_h.prob_h, fp_ah.prob_h, 0) AS fp_h,
               COALESCE(fp_h.prob_d, fp_ah.prob_d, 0) AS fp_d,
               COALESCE(fp_h.prob_a, fp_ah.prob_a, 0) AS fp_a,
               CASE WHEN fp_h.match_key IS NOT NULL OR fp_ah.match_key IS NOT NULL THEN 1 ELSE 0 END AS fp_avail,
               prev_h.start_timestamp AS h_last_ts,
               prev_a.start_timestamp AS a_last_ts
        FROM sofa_historical_results r
        JOIN walkforward_state wf_h ON r.home_team = wf_h.team_name AND r.date = wf_h.date
        JOIN walkforward_state wf_a ON r.away_team = wf_a.team_name AND r.date = wf_a.date
        LEFT JOIN forebet_predictions fp_h ON r.date = fp_h.date
            AND (LOWER(r.home_team) LIKE '%' || LOWER(fp_h.home_team) || '%'
                 OR LOWER(fp_h.home_team) LIKE '%' || LOWER(r.home_team) || '%')
            AND (LOWER(r.away_team) LIKE '%' || LOWER(fp_h.away_team) || '%'
                 OR LOWER(fp_h.away_team) LIKE '%' || LOWER(r.away_team) || '%')
        LEFT JOIN forebet_predictions fp_ah ON r.date = fp_ah.date
            AND (LOWER(r.home_team) LIKE '%' || LOWER(fp_ah.away_team) || '%'
                 OR LOWER(fp_ah.away_team) LIKE '%' || LOWER(r.home_team) || '%')
            AND (LOWER(r.away_team) LIKE '%' || LOWER(fp_ah.home_team) || '%'
                 OR LOWER(fp_ah.home_team) LIKE '%' || LOWER(r.away_team) || '%')
        LEFT JOIN sofa_historical_results prev_h ON prev_h.id = (
            SELECT r2.id FROM sofa_historical_results r2
            WHERE (r2.home_team = r.home_team OR r2.away_team = r.home_team)
              AND r2.start_timestamp < r.start_timestamp
              AND r2.status_type = 'finished'
            ORDER BY r2.start_timestamp DESC LIMIT 1
        )
        LEFT JOIN sofa_historical_results prev_a ON prev_a.id = (
            SELECT r3.id FROM sofa_historical_results r3
            WHERE (r3.home_team = r.away_team OR r3.away_team = r.away_team)
              AND r3.start_timestamp < r.start_timestamp
              AND r3.status_type = 'finished'
            ORDER BY r3.start_timestamp DESC LIMIT 1
        )
        WHERE r.date >= ? AND r.date <= ?
          AND r.status_type = 'finished'
          AND r.home_score IS NOT NULL AND r.away_score IS NOT NULL
        ORDER BY r.start_timestamp ASC
    ''', (start_date, end_date))
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return np.array([]), np.array([]), np.array([])
    X_list, y_home, y_away = [], [], []
    DAY_SEC = 86400
    for row in rows:
        eid, date_str, home, away, hs, aws, r_ts, h_elo, a_elo, h_xgf, h_xga, a_xgf, a_xga, h_f, a_f, h_mp, a_mp, h_shots, a_shots, h_shots_a, a_shots_a, fp_h, fp_d, fp_a, fp_avail, h_last_ts, a_last_ts = row
        elo_diff = h_elo - a_elo
        h_xg_diff = (h_xgf or 1.2) - (h_xga or 1.2)
        a_xg_diff = (a_xgf or 1.2) - (a_xga or 1.2)
        h_shot_diff = (h_shots or 10) - (h_shots_a or 10)
        a_shot_diff = (a_shots or 10) - (a_shots_a or 10)
        h_days_rest = max(1, int((r_ts - (h_last_ts or r_ts - 7*DAY_SEC)) / DAY_SEC))
        a_days_rest = max(1, int((r_ts - (a_last_ts or r_ts - 7*DAY_SEC)) / DAY_SEC))
        features = [
            h_elo or 1600, a_elo or 1600, elo_diff,
            h_xgf or 1.2, h_xga or 1.2,
            a_xgf or 1.2, a_xga or 1.2,
            h_f or 0.5, a_f or 0.5,
            h_mp or 0, a_mp or 0,
            h_shots or 10, a_shots or 10,
            h_shots_a or 10, a_shots_a or 10,
            h_xg_diff, a_xg_diff,
            h_shot_diff, a_shot_diff,
            h_days_rest, a_days_rest,
            fp_h or 0, fp_d or 0, fp_a or 0,
            fp_avail or 0,
        ]
        X_list.append(features)
        y_home.append(int(hs))
        y_away.append(int(aws))
    return np.array(X_list), np.array(y_home), np.array(y_away)

def train(save=True):
    X, y_home, y_away = _load_training_data()
    if len(X) < 100:
        print(f'[Lambda] Not enough data: {len(X)} samples (need 100)')
        return None
    n_train = int(len(X) * 0.8)
    X_tr, X_te = X[:n_train], X[n_train:]
    yh_tr, yh_te = y_home[:n_train], y_home[n_train:]
    ya_tr, ya_te = y_away[:n_train], y_away[n_train:]
    if HAS_XGB:
        model_h = xgb.XGBRegressor(n_estimators=200, max_depth=4, learning_rate=0.1,
                                    subsample=0.8, colsample_bytree=0.8,
                                    random_state=42, n_jobs=-1)
        model_a = xgb.XGBRegressor(n_estimators=200, max_depth=4, learning_rate=0.1,
                                    subsample=0.8, colsample_bytree=0.8,
                                    random_state=42, n_jobs=-1)
    else:
        model_h = GradientBoostingRegressor(n_estimators=200, max_depth=4, learning_rate=0.1,
                                            subsample=0.8, random_state=42)
        model_a = GradientBoostingRegressor(n_estimators=200, max_depth=4, learning_rate=0.1,
                                            subsample=0.8, random_state=42)
    model_h.fit(X_tr, yh_tr)
    model_a.fit(X_tr, ya_tr)
    # Evaluate
    pred_h = model_h.predict(X_te)
    pred_a = model_a.predict(X_te)
    mae_h = np.mean(np.abs(pred_h - yh_te))
    mae_a = np.mean(np.abs(pred_a - ya_te))
    print(f'[Lambda] Trained on {len(X_tr)} matches')
    print(f'[Lambda] Test MAE: home={mae_h:.3f}, away={mae_a:.3f}')
    if save:
        path_h = os.path.join(MODEL_DIR, 'lambda_home' + ('.json' if HAS_XGB else '.pkl'))
        path_a = os.path.join(MODEL_DIR, 'lambda_away' + ('.json' if HAS_XGB else '.pkl'))
        if HAS_XGB:
            model_h.save_model(path_h)
            model_a.save_model(path_a)
        else:
            joblib.dump(model_h, path_h)
            joblib.dump(model_a, path_a)
        with open(os.path.join(MODEL_DIR, 'model_info.json'), 'w') as f:
            json.dump({'features': FEATURES, 'trained_on': len(X_tr), 'mae_home': float(mae_h), 'mae_away': float(mae_a)}, f)
        print(f'[Lambda] Saved models to {MODEL_DIR}')
    return model_h, model_a

def load_models():
    model_h = None; model_a = None
    path_h = os.path.join(MODEL_DIR, 'lambda_home.json')
    path_a = os.path.join(MODEL_DIR, 'lambda_away.json')
    path_h_pkl = os.path.join(MODEL_DIR, 'lambda_home.pkl')
    path_a_pkl = os.path.join(MODEL_DIR, 'lambda_away.pkl')
    if os.path.exists(path_h) and HAS_XGB:
        model_h = xgb.XGBRegressor()
        model_h.load_model(path_h)
        model_a = xgb.XGBRegressor()
        model_a.load_model(path_a)
    elif os.path.exists(path_h_pkl):
        model_h = joblib.load(path_h_pkl)
        model_a = joblib.load(path_a_pkl)
    return model_h, model_a

def _resolve_team_name_sql(conn, team_name, match_date):
    """Find a team in walkforward_state with fuzzy name matching."""
    import difflib
    # Exact match first
    cur = conn.execute('SELECT DISTINCT team_name FROM walkforward_state')
    all_teams = [r[0] for r in cur.fetchall()]
    if team_name in all_teams:
        return team_name
    # Normalize and try
    def norm(s):
        return s.lower().replace(' fc', '').replace(' cf', '').replace(' afc', '').replace(' fc ',
                ' ').replace(' cf ', ' ').replace('  ', ' ').strip()
    nteam = norm(team_name)
    for t in all_teams:
        if norm(t) == nteam:
            return t
    # Fuzzy match
    matches = difflib.get_close_matches(team_name, all_teams, n=1, cutoff=0.5)
    if matches:
        return matches[0]
    return None

def predict_lambda(home_team, away_team, match_date):
    """Predict λ_home and λ_away using trained model + walkforward features."""
    model_h, model_a = load_models()
    if model_h is None:
        return None, None
    conn = sqlite3.connect(DB)
    try:
        home_resolved = _resolve_team_name_sql(conn, home_team, match_date)
        away_resolved = _resolve_team_name_sql(conn, away_team, match_date)
        if not home_resolved or not away_resolved:
            conn.close()
            return None, None
        cur = conn.execute('''
            SELECT wf.elo, wf.rolling_xg_for, wf.rolling_xg_against,
                   wf.form_points, wf.matches_played, wf.rolling_shots_for,
                   wf.rolling_shots_against
            FROM walkforward_state wf
            WHERE wf.team_name = ? AND wf.date <= ?
            ORDER BY wf.date DESC LIMIT 1
        ''', (home_resolved, match_date))
        h = cur.fetchone()
        cur.execute('''
            SELECT wf.elo, wf.rolling_xg_for, wf.rolling_xg_against,
                   wf.form_points, wf.matches_played, wf.rolling_shots_for,
                   wf.rolling_shots_against
            FROM walkforward_state wf
            WHERE wf.team_name = ? AND wf.date <= ?
            ORDER BY wf.date DESC LIMIT 1
        ''', (away_resolved, match_date))
        a = cur.fetchone()
    except:
        conn.close()
        return None, None
    conn.close()
    if not h or not a:
        return None, None
    h_elo, h_xgf, h_xga, h_f, h_mp, h_shots, h_shots_a = h
    a_elo, a_xgf, a_xga, a_f, a_mp, a_shots, a_shots_a = a
    elo_diff = h_elo - a_elo
    h_xg_diff = (h_xgf or 1.2) - (h_xga or 1.2)
    a_xg_diff = (a_xgf or 1.2) - (a_xga or 1.2)
    h_shot_diff = (h_shots or 10) - (h_shots_a or 10)
    a_shot_diff = (a_shots or 10) - (a_shots_a or 10)
    h_days_rest = 7
    a_days_rest = 7
    fp_h = fp_d = fp_a = 0.0
    fp_avail = 0
    try:
        import forebet_scraper as forebets
        fp = forebets.find_prediction_for_match(home_team, away_team, match_date)
        if fp:
            fp_h = fp.get('prob_h', 0) / 100.0
            fp_d = fp.get('prob_d', 0) / 100.0
            fp_a = fp.get('prob_a', 0) / 100.0
            fp_avail = 1
    except:
        pass
    DAY_SEC = 86400
    try:
        conn2 = sqlite3.connect(DB)
        cur = conn2.execute('''
            SELECT start_timestamp FROM sofa_historical_results
            WHERE (home_team = ? OR away_team = ?)
              AND start_timestamp < (SELECT COALESCE(MIN(start_timestamp), 0) FROM sofa_historical_results WHERE id = ?)
            ORDER BY start_timestamp DESC LIMIT 1
        ''', (home_resolved, home_resolved, 0))
        h_last = cur.fetchone()
        cur.execute('''
            SELECT start_timestamp FROM sofa_historical_results
            WHERE (home_team = ? OR away_team = ?)
              AND start_timestamp < (SELECT COALESCE(MIN(start_timestamp), 0) FROM sofa_historical_results WHERE id = ?)
            ORDER BY start_timestamp DESC LIMIT 1
        ''', (away_resolved, away_resolved, 0))
        a_last = cur.fetchone()
        conn2.close()
        if h_last and h_last[0]:
            h_days_rest = max(1, int((int(datetime.strptime(match_date, '%Y-%m-%d').timestamp()) - h_last[0]) / DAY_SEC))
        if a_last and a_last[0]:
            a_days_rest = max(1, int((int(datetime.strptime(match_date, '%Y-%m-%d').timestamp()) - a_last[0]) / DAY_SEC))
    except:
        pass
    features = np.array([[
        h_elo or 1600, a_elo or 1600, elo_diff,
        h_xgf or 1.2, h_xga or 1.2,
        a_xgf or 1.2, a_xga or 1.2,
        h_f or 0.5, a_f or 0.5,
        h_mp or 0, a_mp or 0,
        h_shots or 10, a_shots or 10,
        h_shots_a or 10, a_shots_a or 10,
        h_xg_diff, a_xg_diff,
        h_shot_diff, a_shot_diff,
        h_days_rest, a_days_rest,
        fp_h, fp_d, fp_a,
        fp_avail,
    ]])
    lam_h = max(0.25, min(4.5, float(model_h.predict(features)[0])))
    lam_a = max(0.25, min(4.5, float(model_a.predict(features)[0])))
    return lam_h, lam_a

if __name__ == '__main__':
    print('=== XGBoost Lambda-Regressor ===')
    train()
