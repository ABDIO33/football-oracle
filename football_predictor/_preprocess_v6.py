"""
_preprocess_v6.py — Builds 126-feature dataset for V6 training
دمج expand_features.py مع walkforward data

البناء: DeepSeek V4 Flash Free الأول
"""
import sys, os, json, time, numpy as np, pandas as pd, sqlite3, gc
sys.path.insert(0, os.path.dirname(__file__))
from expand_features import expand_features_row, get_new_feature_names, BASE_FEATURES, SCORE_PROBS
import joblib
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
os.makedirs(MODEL_DIR, exist_ok=True)

def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] {msg}')

def build_v6_dataset(start_year=2005, test_cutoff='2025-01-01'):
    """Build full 126-feature dataset from database"""
    t0 = time.time()
    log(f'Building V6 dataset (126 features, from {start_year})...')

    conn = sqlite3.connect(DB)

    # Load all finished matches from start_year
    log('Loading matches...')
    df = pd.read_sql_query(f'''
        SELECT r.id, r.home_team, r.away_team, r.home_score, r.away_score,
               r.date, r.tournament, r.start_timestamp,
               wf_h.elo as home_elo, wf_a.elo as away_elo,
               wf_h.rolling_xg_for as home_xg_for, wf_h.rolling_xg_against as home_xg_against,
               wf_a.rolling_xg_for as away_xg_for, wf_a.rolling_xg_against as away_xg_against,
               wf_h.form_points as home_form, wf_a.form_points as away_form,
               wf_h.matches_played as home_matches_played, wf_a.matches_played as away_matches_played,
               wf_h.rolling_shots_for as home_shots_for, wf_a.rolling_shots_for as away_shots_for,
               wf_h.rolling_shots_against as home_shots_against, wf_a.rolling_shots_against as away_shots_against
        FROM sofa_historical_results r
        JOIN walkforward_state wf_h ON r.home_team = wf_h.team_name AND r.date = wf_h.date
        JOIN walkforward_state wf_a ON r.away_team = wf_a.team_name AND r.date = wf_a.date
        WHERE r.home_score IS NOT NULL AND r.away_score IS NOT NULL
          AND r.home_score >= 0 AND r.away_score >= 0
          AND r.status_type = 'finished'
          AND r.date >= '{start_year}-01-01'
        ORDER BY r.start_timestamp
    ''', conn)

    if len(df) == 0:
        log('ERROR: No matches loaded!'); return None, None, None, None

    log(f'Loaded {len(df):,} matches')

    # Also load match stats + lineups
    stats = {}
    try:
        cur = conn.execute('SELECT event_id, home_xg, away_xg, home_shots, away_shots, home_sot, away_sot, home_possession, away_possession, home_corners, away_corners, home_fouls, away_fouls FROM sofa_match_stats')
        for row in cur.fetchall(): stats[row[0]] = row[1:]
    except: pass

    lineups = {}
    try:
        cur = conn.execute('SELECT event_id, home_formation, away_formation FROM sofa_lineups')
        for row in cur.fetchall(): lineups[row[0]] = (row[1], row[2])
    except: pass

    # Pre-load Glicko
    glicko = {}
    try:
        cur = conn.execute('SELECT team_name, date, glicko, glicko_rd FROM glicko_state')
        for row in cur.fetchall():
            key = (row[0], row[1])
            glicko[key] = (row[2], row[3])
    except: pass

    # Pre-load weather
    weather = {}
    try:
        cur = conn.execute('SELECT team, date, temp, precip, wind, humidity FROM venue_weather')
        for row in cur.fetchall(): weather[(row[0], row[1])] = (row[2], row[3], row[4], row[5])
    except: pass

    # Build feature matrix
    NEW_FEATURE_NAMES = get_new_feature_names()
    ALL_FEATURES = BASE_FEATURES + NEW_FEATURE_NAMES

    X = np.zeros((len(df), len(ALL_FEATURES)), dtype=np.float32)
    y = np.zeros(len(df), dtype=np.int32)
    match_ids = np.zeros(len(df), dtype=np.int64)

    n_errors = 0
    for idx, row in df.iterrows():
        if idx % 50000 == 0 and idx > 0:
            log(f'  Progress: {idx:,}/{len(df):,} ({idx*100/len(df):.0f}%)')

        match_ids[idx] = row['id']

        # Score -> class
        hs, aw = int(row['home_score']), int(row['away_score'])
        hs = min(max(hs, 0), 4); aw = min(max(aw, 0), 4)
        y[idx] = hs * 5 + aw

        # Build base feature dict
        feat = {
            'home_elo': row['home_elo'], 'away_elo': row['away_elo'],
            'elo_diff': row['home_elo'] - row['away_elo'],
            'home_xg_for': row['home_xg_for'], 'home_xg_against': row['home_xg_against'],
            'away_xg_for': row['away_xg_for'], 'away_xg_against': row['away_xg_against'],
            'home_form': row['home_form'], 'away_form': row['away_form'],
            'home_matches_played': row['home_matches_played'], 'away_matches_played': row['away_matches_played'],
            'home_shots_for': row['home_shots_for'], 'away_shots_for': row['away_shots_for'],
            'home_shots_against': row['home_shots_against'], 'away_shots_against': row['away_shots_against'],
            'home_xg_diff': row['home_xg_for'] - row['home_xg_against'],
            'away_xg_diff': row['away_xg_for'] - row['away_xg_against'],
            'home_shot_diff': row['home_shots_for'] - row['home_shots_against'],
            'away_shot_diff': row['away_shots_for'] - row['away_shots_against'],
            'home_days_rest': 5, 'away_days_rest': 5,
            'forebet_prob_h': 0, 'forebet_prob_d': 0, 'forebet_prob_a': 0, 'forebet_available': 0,
            'home_glicko': 1500, 'away_glicko': 1500,
            'home_glicko_rd': 350, 'away_glicko_rd': 350,
            'stat_h_xg': 0, 'stat_a_xg': 0,
            'stat_h_shots': 0, 'stat_a_shots': 0,
            'stat_h_sot': 0, 'stat_a_sot': 0,
            'stat_h_possession': 50, 'stat_a_possession': 50,
            'stat_h_corners': 0, 'stat_a_corners': 0,
            'stat_h_fouls': 0, 'stat_a_fouls': 0,
            'home_formation_def': 4, 'away_formation_def': 4,
            'formation_diff': 0, 'has_lineups': 0,
            'home_missing_core': 0, 'away_missing_core': 0,
            'home_att_loss': 0, 'away_att_loss': 0,
            'home_def_loss': 0, 'away_def_loss': 0,
            'odds_b365h': 2.0, 'odds_b365d': 3.5, 'odds_b365a': 3.5,
            'odds_avgh': 2.0, 'odds_avgd': 3.5, 'odds_avga': 3.5,
            'elo_form_home': 0, 'elo_form_away': 0,
            'elo_xg_home': 0, 'elo_xg_away': 0,
            'form_xg_home': 0, 'form_xg_away': 0,
            'elo_diff_form_diff': 0, 'fatigue_home': 0, 'fatigue_away': 0,
            'xg_ratio': 1.0, 'shots_ratio': 1.0, 'form_ratio': 1.0,
            'xgf_xga_ratio_home': 1.0, 'xgf_xga_ratio_away': 1.0,
            'shot_eff_home': 0.3, 'shot_eff_away': 0.3,
            'elo_diff_sq': 0, 'xg_diff_sq': 0, 'form_diff_sq': 0,
            'month': 6, 'day_of_week': 3, 'season_progress': 0.5, 'is_weekend': 1,
            'home_temp': 15, 'home_precip': 0, 'home_wind': 5, 'home_humidity': 60,
            'travel_distance': 0,
            'home_team': row['home_team'], 'away_team': row['away_team'],
            'date': row['date'],
            'tournament': row['tournament'],
        }

        # Derived features
        feat['elo_form_home'] = feat['home_elo'] * feat['home_form']
        feat['elo_form_away'] = feat['away_elo'] * feat['away_form']
        feat['elo_xg_home'] = feat['home_elo'] * feat['home_xg_for']
        feat['elo_xg_away'] = feat['away_elo'] * feat['away_xg_for']
        feat['form_xg_home'] = feat['home_form'] * feat['home_xg_for']
        feat['form_xg_away'] = feat['away_form'] * feat['away_xg_for']
        feat['elo_diff_form_diff'] = feat['elo_diff'] * (feat['home_form'] - feat['away_form'])
        feat['xg_ratio'] = (feat['home_xg_for'] + 0.1) / (feat['away_xg_for'] + 0.1)
        feat['shots_ratio'] = (feat['home_shots_for'] + 0.1) / (feat['away_shots_for'] + 0.1)
        feat['form_ratio'] = (feat['home_form'] + 0.01) / (feat['away_form'] + 0.01)
        feat['xgf_xga_ratio_home'] = feat['home_xg_for'] / (feat['home_xg_against'] + 0.1)
        feat['xgf_xga_ratio_away'] = feat['away_xg_for'] / (feat['away_xg_against'] + 0.1)
        feat['elo_diff_sq'] = feat['elo_diff'] ** 2
        feat['xg_diff_sq'] = feat['home_xg_diff'] ** 2
        feat['form_diff_sq'] = (feat['home_form'] - feat['away_form']) ** 2
        feat['shot_eff_home'] = feat['home_shots_for'] / (feat['home_shots_for'] + feat['home_shots_against'] + 0.1)
        feat['shot_eff_away'] = feat['away_shots_for'] / (feat['away_shots_for'] + feat['away_shots_against'] + 0.1)
        feat['fatigue_home'] = 7 - feat['home_days_rest']
        feat['fatigue_away'] = 7 - feat['away_days_rest']

        # Match stats
        eid = row['id']
        if eid in stats:
            s = stats[eid]; feat['stat_h_xg'] = s[0] or 0; feat['stat_a_xg'] = s[1] or 0
            feat['stat_h_shots'] = s[2] or 0; feat['stat_a_shots'] = s[3] or 0
            feat['stat_h_sot'] = s[4] or 0; feat['stat_a_sot'] = s[5] or 0
            feat['stat_h_possession'] = s[6] or 50; feat['stat_a_possession'] = s[7] or 50
            feat['stat_h_corners'] = s[8] or 0; feat['stat_a_corners'] = s[9] or 0
            feat['stat_h_fouls'] = s[10] or 0; feat['stat_a_fouls'] = s[11] or 0

        # Lineups
        if eid in lineups:
            hf, af = lineups[eid]
            if hf: feat['home_formation_def'] = int(hf.split('-')[0]) if hf.split('-')[0].isdigit() else 4
            if af: feat['away_formation_def'] = int(af.split('-')[0]) if af.split('-')[0].isdigit() else 4
            feat['formation_diff'] = feat['home_formation_def'] - feat['away_formation_def']
            feat['has_lineups'] = 1

        # Glicko
        gkey_h = (row['home_team'], row['date'])
        gkey_a = (row['away_team'], row['date'])
        if gkey_h in glicko: feat['home_glicko'], feat['home_glicko_rd'] = glicko[gkey_h]
        if gkey_a in glicko: feat['away_glicko'], feat['away_glicko_rd'] = glicko[gkey_a]

        # Weather
        wkey_h = (row['home_team'], row['date'])
        wkey_a = (row['away_team'], row['date'])
        if wkey_h in weather: feat['home_temp'], feat['home_precip'], feat['home_wind'], feat['home_humidity'] = weather[wkey_h][:4]
        if wkey_a in weather:
            wt = weather[wkey_a]; feat['home_temp'] = feat['home_temp'] or wt[0] if not feat.get('home_temp') else (feat['home_temp'] + wt[0]) / 2

        # Expand features (add 41 new features)
        try:
            expanded = expand_features_row(conn, feat, row['tournament'])
            # Copy expanded features into feat
            for k, v in expanded.items():
                if k not in feat:  # only new keys
                    feat[k] = v
        except Exception as e:
            n_errors += 1

        # Fill feature vector in order
        for fi, fname in enumerate(ALL_FEATURES):
            X[idx, fi] = float(feat.get(fname, 0))

        if n_errors > 10:
            log(f'WARNING: {n_errors} expansion errors so far')

    log(f'Built matrix: {X.shape}, errors: {n_errors}')

    # Chronological split at test_cutoff
    test_mask = df['date'] >= test_cutoff
    train_mask = ~test_mask

    X_train, X_test = X[train_mask], X[test_mask]
    y_train, y_test = y[train_mask], y[test_mask]
    mid_train, mid_test = match_ids[train_mask], match_ids[test_mask]

    log(f'Train: {len(X_train):,}, Test: {len(X_test):,}')
    log(f'Features: {len(ALL_FEATURES)}')

    # Impute + Scale
    log('Imputing...')
    imp = SimpleImputer(strategy='median')
    X_train_imp = imp.fit_transform(X_train)
    X_test_imp = imp.transform(X_test)

    log('Scaling...')
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train_imp)
    X_test_s = scaler.transform(X_test_imp)

    conn.close()
    log(f'Total time: {(time.time()-t0)/60:.1f} min')
    return X_train_s, X_test_s, y_train, y_test, ALL_FEATURES

if __name__ == '__main__':
    log('=== V6 Preprocessor ===')
    Xtr, Xte, ytr, yte, features = build_v6_dataset(start_year=2005)

    if Xtr is not None:
        np.savez_compressed(os.path.join(MODEL_DIR, 'v6_preprocessed.npz'),
            X_train=Xtr, X_test=Xte, y_train=ytr, y_test=yte,
            feature_names=features)
        joblib.dump(features, os.path.join(MODEL_DIR, 'v6_features.pkl'))
        log(f'SAVED: v6_preprocessed.npz ({len(Xtr):,} train, {len(Xte):,} test)')
        log(f'FEATURES: {len(features)} total')
    log('DONE')
