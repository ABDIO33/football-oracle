"""
_preprocess_v62.py — Builds 194-feature dataset for V6.2 training
Uses expand_features_v2.py for full feature expansion.
دمج 194 ميزة من قاعدة البيانات مع walkforward data

البناء: DeepSeek V4 Flash Free الأول
"""
import sys, os, json, time, numpy as np, pandas as pd, sqlite3, gc, math
from datetime import datetime
sys.path.insert(0, os.path.dirname(__file__))
from expand_features_v2 import (
    expand_features_row_v2, get_v2_feature_names,
    BASE_FEATURES, ALL_V2_FEATURES, SCORE_PROBS
)
import joblib
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
os.makedirs(MODEL_DIR, exist_ok=True)


def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f'[{ts}] {msg}', flush=True)
    with open(os.path.join(MODEL_DIR, 'v62_preprocess_log.txt'), 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] {msg}\n')


def build_v62_dataset(start_year=2010, test_cutoff='2025-01-01',
                       sample_pct=1.0, use_nvidia=True):
    """
    Build full 194-feature dataset from database
    
    Parameters:
    - start_year: filter matches >= this year
    - test_cutoff: date split for train/test
    - sample_pct: 0.0-1.0 for testing (1.0 = all data)
    - use_nvidia: if False, skip GPU-dependent features
    """
    t0 = time.time()
    ALL_FEATURES = get_v2_feature_names()
    log(f'Building V6.2 dataset ({len(ALL_FEATURES)} features, from {start_year})...')
    log(f'Sample: {sample_pct*100:.0f}% of data')
    
    conn = sqlite3.connect(DB)
    
    # ─── Load all finished matches ───
    log('Loading matches with walkforward state...')
    t_load = time.time()
    
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
        log('ERROR: No matches loaded!')
        conn.close()
        return None, None, None, None, None
    
    # Apply sampling
    if sample_pct < 1.0:
        n_orig = len(df)
        df = df.sample(frac=sample_pct, random_state=42).sort_index()
        log(f'Sampled: {n_orig} -> {len(df)} matches')
    
    log(f'Loaded {len(df):,} matches in {time.time()-t_load:.0f}s')
    
    # ─── Pre-load match stats ───
    t_load = time.time()
    stats = {}
    try:
        cur = conn.execute('''
            SELECT event_id, home_xg, away_xg, home_shots, away_shots, 
                   home_sot, away_sot, home_possession, away_possession,
                   home_corners, away_corners, home_fouls, away_fouls 
            FROM sofa_match_stats
        ''')
        for row in cur.fetchall():
            stats[row[0]] = row[1:]
        log(f'Loaded {len(stats):,} match stats in {time.time()-t_load:.0f}s')
    except Exception as e:
        log(f'Warning: stats table not available: {e}')
    
    # ─── Pre-load lineups ───
    t_load = time.time()
    lineups = {}
    try:
        cur = conn.execute('SELECT event_id, home_formation, away_formation FROM sofa_lineups')
        for row in cur.fetchall():
            lineups[row[0]] = (row[1], row[2])
        log(f'Loaded {len(lineups):,} lineups in {time.time()-t_load:.0f}s')
    except Exception as e:
        log(f'Warning: lineups table not available: {e}')
    
    # ─── Pre-load Glicko ───
    t_load = time.time()
    glicko = {}
    try:
        cur = conn.execute('SELECT team_name, date, glicko_rating, glicko_rd FROM glicko_state')
        for row in cur.fetchall():
            glicko[(row[0], row[1])] = (row[2], row[3])
        log(f'Loaded {len(glicko):,} glicko states in {time.time()-t_load:.0f}s')
    except Exception as e:
        log(f'Warning: glicko not available: {e}')
    
    # ─── Pre-load weather ───
    t_load = time.time()
    weather = {}
    try:
        cur = conn.execute('SELECT date, temp_max, precip, wind, humidity FROM venue_weather')
        # venue_weather uses lat/lon not team, so store by date only as fallback
        for row in cur.fetchall():
            weather[('__global__', row[0])] = (row[1], row[2], row[3], row[4])
        log(f'Loaded {len(weather):,} weather records in {time.time()-t_load:.0f}s')
    except Exception as e:
        log(f'Warning: weather not available: {e}')
    
    # ─── Build feature matrix (keep conn open for V2 feature DB queries) ───
    log('Building feature matrix...')
    t_build = time.time()
    
    X = np.zeros((len(df), len(ALL_FEATURES)), dtype=np.float32)
    y = np.zeros(len(df), dtype=np.int32)
    
    n_errors = 0
    for idx, (_, row) in enumerate(df.iterrows()):
        if idx % 25000 == 0 and idx > 0:
            pct = idx * 100 / len(df)
            elapsed = time.time() - t_build
            rate = idx / max(elapsed, 0.1)
            eta = (len(df) - idx) / max(rate, 1)
            log(f'  Progress: {idx:,}/{len(df):,} ({pct:.0f}%) | {rate:.0f} rows/s | ETA: {eta:.0f}s')
        
        # Score -> class (25 classes: 5x5 grid)
        hs, aw = int(row['home_score']), int(row['away_score'])
        hs = min(max(hs, 0), 4)
        aw = min(max(aw, 0), 4)
        y[idx] = hs * 5 + aw
        
        # ─── Build base feature dict ───
        feat = {
            # Core match features
            'home_elo': row['home_elo'], 'away_elo': row['away_elo'],
            'elo_diff': row['home_elo'] - row['away_elo'],
            'home_xg_for': row['home_xg_for'], 'home_xg_against': row['home_xg_against'],
            'away_xg_for': row['away_xg_for'], 'away_xg_against': row['away_xg_against'],
            'home_form': row['home_form'], 'away_form': row['away_form'],
            'home_matches_played': row['home_matches_played'], 'away_matches_played': row['away_matches_played'],
            'home_shots_for': row['home_shots_for'], 'away_shots_for': row['away_shots_for'],
            'home_shots_against': row['home_shots_against'], 'away_shots_against': row['away_shots_against'],
            
            # Derived xG/shots
            'home_xg_diff': row['home_xg_for'] - row['home_xg_against'],
            'away_xg_diff': row['away_xg_for'] - row['away_xg_against'],
            'home_shot_diff': row['home_shots_for'] - row['home_shots_against'],
            'away_shot_diff': row['away_shots_for'] - row['away_shots_against'],
            
            # Default placeholders (filled below when available)
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
            
            # Calendar (rough from date)
            'month': 6, 'day_of_week': 3, 'season_progress': 0.5, 'is_weekend': 1,
            
            # Weather defaults
            'home_temp': 15, 'home_precip': 0, 'home_wind': 5, 'home_humidity': 60,
            'travel_distance': 0,
            
            # Identity
            'home_team': row['home_team'], 'away_team': row['away_team'],
            'date': row['date'], 'tournament': row['tournament'],
        }
        
        # ─── Derived base features ───
        feat['elo_form_home'] = feat['home_elo'] * feat['home_form']
        feat['elo_form_away'] = feat['away_elo'] * feat['away_form']
        feat['elo_xg_home'] = feat['home_elo'] * feat['home_xg_for']
        feat['elo_xg_away'] = feat['away_elo'] * feat['away_xg_for']
        feat['form_xg_home'] = feat['home_form'] * feat['home_xg_for']
        feat['form_xg_away'] = feat['away_form'] * feat['away_xg_for']
        feat['elo_diff_form_diff'] = feat['elo_diff'] * (feat['home_form'] - feat['away_form'])
        hxg = max(feat['home_xg_for'], 0.01)
        axg = max(feat['away_xg_for'], 0.01)
        feat['xg_ratio'] = hxg / axg
        feat['shots_ratio'] = max(feat['home_shots_for'], 0.1) / max(feat['away_shots_for'], 0.1)
        feat['form_ratio'] = max(feat['home_form'], 0.01) / max(feat['away_form'], 0.01)
        feat['xgf_xga_ratio_home'] = hxg / max(feat['home_xg_against'], 0.1)
        feat['xgf_xga_ratio_away'] = axg / max(feat['away_xg_against'], 0.1)
        feat['elo_diff_sq'] = feat['elo_diff'] ** 2
        feat['xg_diff_sq'] = feat['home_xg_diff'] ** 2
        feat['form_diff_sq'] = (feat['home_form'] - feat['away_form']) ** 2
        feat['shot_eff_home'] = feat['home_shots_for'] / max(feat['home_shots_for'] + feat['home_shots_against'], 0.1)
        feat['shot_eff_away'] = feat['away_shots_for'] / max(feat['away_shots_for'] + feat['away_shots_against'], 0.1)
        feat['fatigue_home'] = 7 - feat['home_days_rest']
        feat['fatigue_away'] = 7 - feat['away_days_rest']
        
        # ─── Match stats ───
        eid = row['id']
        if eid in stats:
            s = stats[eid]
            feat['stat_h_xg'] = s[0] or 0
            feat['stat_a_xg'] = s[1] or 0
            feat['stat_h_shots'] = s[2] or 0
            feat['stat_a_shots'] = s[3] or 0
            feat['stat_h_sot'] = s[4] or 0
            feat['stat_a_sot'] = s[5] or 0
            feat['stat_h_possession'] = s[6] or 50
            feat['stat_a_possession'] = s[7] or 50
            feat['stat_h_corners'] = s[8] or 0
            feat['stat_a_corners'] = s[9] or 0
            feat['stat_h_fouls'] = s[10] or 0
            feat['stat_a_fouls'] = s[11] or 0
        
        # ─── Lineups ───
        if eid in lineups:
            hf, af = lineups[eid]
            if hf and hf.split('-')[0].isdigit():
                feat['home_formation_def'] = int(hf.split('-')[0])
            if af and af.split('-')[0].isdigit():
                feat['away_formation_def'] = int(af.split('-')[0])
            feat['formation_diff'] = feat['home_formation_def'] - feat['away_formation_def']
            feat['has_lineups'] = 1
        
        # ─── Glicko ───
        gkey_h = (row['home_team'], row['date'])
        gkey_a = (row['away_team'], row['date'])
        if gkey_h in glicko:
            feat['home_glicko'], feat['home_glicko_rd'] = glicko[gkey_h]
        if gkey_a in glicko:
            feat['away_glicko'], feat['away_glicko_rd'] = glicko[gkey_a]
        
        # ─── Weather (keyed by date since venue_weather uses lat/lon not team) ───
        wkey_global = ('__global__', row['date'])
        if wkey_global in weather:
            wt = weather[wkey_global]
            # wt = (temp_max, precip, wind, humidity)
            feat['home_temp'] = float(wt[0]) if wt[0] is not None else 15
            feat['home_precip'] = float(wt[1]) if wt[1] is not None else 0
            feat['home_wind'] = float(wt[2]) if wt[2] is not None else 5
            feat['home_humidity'] = float(wt[3]) if wt[3] is not None else 60
        
        # ─── Calendar ───
        try:
            dt = datetime.strptime(str(row['date'])[:10], '%Y-%m-%d')
            feat['month'] = dt.month
            feat['day_of_week'] = dt.weekday()
            feat['is_weekend'] = 1 if dt.weekday() >= 5 else 0
            # Approximate season progress
            if dt.month >= 8:
                sp = (dt.month - 8 + dt.day/30) / 10
            else:
                sp = (dt.month + 4 + dt.day/30) / 10
            feat['season_progress'] = max(0, min(1, sp))
        except:
            pass
        
        # ─── V2 FEATURE EXPANSION ───
        try:
            expanded = expand_features_row_v2(conn, feat, row['tournament'])
            # Copy only new keys
            for k, v in expanded.items():
                if k not in feat:
                    feat[k] = v
        except Exception as e:
            n_errors += 1
            if n_errors <= 5:
                log(f'  Expansion error at idx {idx}: {e}')
        
        # ─── Fill feature vector ───
        for fi, fname in enumerate(ALL_FEATURES):
            val = feat.get(fname)
            if val is None:
                val = 0.0
            X[idx, fi] = float(val)
        
        if n_errors > 0 and n_errors % 100 == 0:
            log(f'  WARNING: {n_errors} total expansion errors')
    
    build_time = time.time() - t_build
    log(f'Built matrix: {X.shape} in {build_time:.0f}s ({build_time/60:.1f}min)')
    log(f'Errors: {n_errors}')
    
    # ─── Chronological split ───
    test_mask = df['date'] >= test_cutoff
    train_mask = ~test_mask
    
    X_train, X_test = X[train_mask], X[test_mask]
    y_train, y_test = y[train_mask], y[test_mask]
    
    # Also save original dates for stacking
    dates_train = df['date'][train_mask].values
    dates_test = df['date'][test_mask].values
    
    log(f'Train: {len(X_train):,} | Test: {len(X_test):,}')
    log(f'Features: {len(ALL_FEATURES)}')
    
    # ─── Impute + Scale ───
    log('Imputing...')
    imp = SimpleImputer(strategy='median')
    X_train_imp = imp.fit_transform(X_train)
    X_test_imp = imp.transform(X_test)
    
    log('Scaling...')
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train_imp)
    X_test_s = scaler.transform(X_test_imp)
    
    # Check for NaN/Inf
    n_nan = np.isnan(X_train_s).sum() + np.isnan(X_test_s).sum()
    n_inf = np.isinf(X_train_s).sum() + np.isinf(X_test_s).sum()
    if n_nan > 0:
        log(f'WARNING: {n_nan} NaN values found, replacing with 0')
        X_train_s = np.nan_to_num(X_train_s, nan=0.0, posinf=0.0, neginf=0.0)
        X_test_s = np.nan_to_num(X_test_s, nan=0.0, posinf=0.0, neginf=0.0)
    if n_inf > 0:
        log(f'WARNING: {n_inf} Inf values found, replacing with 0')
        X_train_s = np.nan_to_num(X_train_s, nan=0.0, posinf=0.0, neginf=0.0)
        X_test_s = np.nan_to_num(X_test_s, nan=0.0, posinf=0.0, neginf=0.0)
    
    conn.close()
    
    total_time = (time.time() - t0) / 60
    log(f'Total preprocessing time: {total_time:.1f} min')
    
    return X_train_s, X_test_s, y_train, y_test, ALL_FEATURES, imp, scaler


if __name__ == '__main__':
    import sys
    
    sample = 1.0
    if '--sample' in sys.argv:
        idx = sys.argv.index('--sample')
        sample = float(sys.argv[idx + 1])
    
    log('=== V6.2 Preprocessor (194 features) ===')
    log(f'Sample: {sample*100:.0f}%')
    
    result = build_v62_dataset(start_year=2010, test_cutoff='2025-01-01',
                                sample_pct=sample)
    
    Xtr, Xte, ytr, yte, features, imp, scaler = result
    
    if Xtr is not None:
        npz_path = os.path.join(MODEL_DIR, 'v62_preprocessed.npz')
        np.savez_compressed(npz_path,
            X_train=Xtr, X_test=Xte, y_train=ytr, y_test=yte,
            feature_names=features)
        log(f'SAVED: {npz_path}')
        log(f'  Train: {len(Xtr):,} x {Xtr.shape[1]}')
        log(f'  Test: {len(Xte):,} x {Xte.shape[1]}')
        
        # Save scaler and imputer for production
        joblib.dump(imp, os.path.join(MODEL_DIR, 'v62_imputer.pkl'))
        joblib.dump(scaler, os.path.join(MODEL_DIR, 'v62_scaler.pkl'))
        joblib.dump(features, os.path.join(MODEL_DIR, 'v62_features.pkl'))
        
        # Print class distribution
        classes, counts = np.unique(ytr, return_counts=True)
        log(f'Class distribution (top 10):')
        for c, cnt in sorted(zip(classes, counts), key=lambda x: -x[1])[:10]:
            log(f'  [{c//5}-{c%5}]: {cnt:,} ({cnt*100/len(ytr):.1f}%)')
        
        log(f'FEATURES: {len(features)} total')
    
    log('DONE')
