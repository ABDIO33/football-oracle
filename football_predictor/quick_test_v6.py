"""
quick_test_v6.py — Quick V6 test on 50K matches
يقيس الأداء الأولي لـ 132 feature على عينة

البناء: DeepSeek V4 Flash Free الأول
"""
import sys, os, json, time, numpy as np, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))

import torch, torch.nn as nn, torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score
import xgboost as xgb
import joblib

BASE = os.path.dirname(__file__)
MODEL_DIR = os.path.join(BASE, 'models')

def _cs(c): return (c // 5, c % 5)

def rps_score(y_true, y_pred_proba):
    rps = 0.0
    for i in range(len(y_true)):
        ah, aa = _cs(y_true[i])
        ar = 0 if ah > aa else 1 if ah == aa else 2
        p = y_pred_proba[i]
        cp = np.zeros(3)
        for hh in range(5):
            for aa2 in range(5):
                if hh > aa2: cp[0] += p[hh*5+aa2]
                elif hh == aa2: cp[1] += p[hh*5+aa2]
                else: cp[2] += p[hh*5+aa2]
        ca = np.zeros(3); ca[ar:] = 1.0
        rps += float(np.mean((ca - np.cumsum(cp))**2))
    return rps / len(y_true)

def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] {msg}')

log('='*50)
log('Quick V6 Test - 50K matches, 132 features')
log('='*50)

# Load data
log('\n[1/4] Loading 50K matches with 132 features...')
import sqlite3, pandas as pd
from expand_features import expand_features_row, get_new_feature_names, BASE_FEATURES

conn = sqlite3.connect(os.path.join(BASE, 'scrape_cache.db'))
df = pd.read_sql_query('''
    SELECT r.id, r.home_team, r.away_team, r.home_score, r.away_score,
           r.date, r.tournament,
           COALESCE(wf_h.elo,1500) as home_elo, COALESCE(wf_a.elo,1500) as away_elo,
           COALESCE(wf_h.rolling_xg_for,1.0) as hxgf, COALESCE(wf_h.rolling_xg_against,0.8) as hxga,
           COALESCE(wf_a.rolling_xg_for,0.8) as axgf, COALESCE(wf_a.rolling_xg_against,1.0) as axga,
           COALESCE(wf_h.form_points,0.5) as hf, COALESCE(wf_a.form_points,0.5) as af,
           COALESCE(wf_h.matches_played,10) as hmp, COALESCE(wf_a.matches_played,10) as amp
    FROM sofa_historical_results r
    JOIN walkforward_state wf_h ON r.home_team = wf_h.team_name AND r.date = wf_h.date
    JOIN walkforward_state wf_a ON r.away_team = wf_a.team_name AND r.date = wf_a.date
    WHERE r.date >= '2018-01-01' AND r.date < '2025-01-01'
    ORDER BY r.start_timestamp
    LIMIT 50000
''', conn)

ALL_F = BASE_FEATURES + get_new_feature_names()
log(f'Loaded {len(df)} matches, {len(ALL_F)} features')

# Pre-load match stats + lineups
stats = {}
try:
    cur = conn.execute('SELECT event_id, home_xg, away_xg, home_shots, away_shots, home_sot, away_sot FROM sofa_match_stats')
    for row in cur.fetchall(): stats[row[0]] = row[1:]
except: pass

lineups = {}
try:
    cur = conn.execute('SELECT event_id, home_formation, away_formation FROM sofa_lineups')
    for row in cur.fetchall(): lineups[row[0]] = (row[1], row[2])
except: pass

# Build matrix
t0 = time.time()
X = np.zeros((len(df), len(ALL_F)), dtype=np.float32)
y = np.zeros(len(df), dtype=np.int32)
errors = 0

for idx, row in df.iterrows():
    if idx % 10000 == 0: log(f'  {idx}/{len(df)}')
    
    hs, aw = int(row['home_score']), int(row['away_score'])
    y[idx] = min(max(hs,0),4) * 5 + min(max(aw,0),4)
    
    eid = row['id']
    s = stats.get(eid, (0,0,0,0,0,0))
    
    feat = {
        'home_elo': row['home_elo'], 'away_elo': row['away_elo'],
        'elo_diff': row['home_elo'] - row['away_elo'],
        'home_xg_for': row['hxgf'], 'home_xg_against': row['hxga'],
        'away_xg_for': row['axgf'], 'away_xg_against': row['axga'],
        'home_form': row['hf'], 'away_form': row['af'],
        'home_matches_played': row['hmp'], 'away_matches_played': row['amp'],
        'home_shots_for': s[2] or 0, 'away_shots_for': s[3] or 0,
        'home_shots_against': 0, 'away_shots_against': 0,
        'home_xg_diff': row['hxgf']-row['hxga'],
        'away_xg_diff': row['axgf']-row['axga'],
        'home_shot_diff': 0, 'away_shot_diff': 0,
        'home_days_rest': 5, 'away_days_rest': 5,
        'forebet_prob_h': 0, 'forebet_prob_d': 0, 'forebet_prob_a': 0, 'forebet_available': 0,
        'home_glicko': 1500, 'away_glicko': 1500, 'home_glicko_rd': 350, 'away_glicko_rd': 350,
        'stat_h_xg': s[0] or 0, 'stat_a_xg': s[1] or 0,
        'stat_h_shots': s[2] or 0, 'stat_a_shots': s[3] or 0,
        'stat_h_sot': s[4] or 0, 'stat_a_sot': s[5] or 0,
        'stat_h_possession': 50, 'stat_a_possession': 50,
        'stat_h_corners': 0, 'stat_a_corners': 0,
        'stat_h_fouls': 0, 'stat_a_fouls': 0,
        'home_formation_def': 4, 'away_formation_def': 4, 'formation_diff': 0, 'has_lineups': 0,
        'home_missing_core': 0, 'away_missing_core': 0,
        'home_att_loss': 0, 'away_att_loss': 0, 'home_def_loss': 0, 'away_def_loss': 0,
        'odds_b365h': 2.0, 'odds_b365d': 3.5, 'odds_b365a': 3.5,
        'odds_avgh': 2.0, 'odds_avgd': 3.5, 'odds_avga': 3.5,
        'elo_form_home': row['home_elo']*row['hf'],
        'elo_form_away': row['away_elo']*row['af'],
        'elo_xg_home': row['home_elo']*row['hxgf'],
        'elo_xg_away': row['away_elo']*row['axgf'],
        'form_xg_home': row['hf']*row['hxgf'],
        'form_xg_away': row['af']*row['axgf'],
        'elo_diff_form_diff': (row['home_elo']-row['away_elo'])*(row['hf']-row['af']),
        'fatigue_home': 3, 'fatigue_away': 3,
        'xg_ratio': (row['hxgf']+0.1)/(row['axgf']+0.1),
        'shots_ratio': 1.0, 'form_ratio': (row['hf']+0.01)/(row['af']+0.01),
        'xgf_xga_ratio_home': (row['hxgf']+0.1)/(row['hxga']+0.1),
        'xgf_xga_ratio_away': (row['axgf']+0.1)/(row['axga']+0.1),
        'shot_eff_home': 0.5, 'shot_eff_away': 0.5,
        'elo_diff_sq': (row['home_elo']-row['away_elo'])**2,
        'xg_diff_sq': (row['hxgf']-row['hxga'])**2,
        'form_diff_sq': (row['hf']-row['af'])**2,
        'month': 6, 'day_of_week': 3, 'season_progress': 0.5, 'is_weekend': 1,
        'home_temp': 20, 'home_precip': 0, 'home_wind': 5, 'home_humidity': 60,
        'travel_distance': 0,
        'home_team': row['home_team'], 'away_team': row['away_team'],
        'date': row['date'],
    }
    
    # Lineups
    if eid in lineups:
        hf, af = lineups[eid]
        if hf: feat['home_formation_def'] = int(hf.split('-')[0]) if hf.split('-')[0].isdigit() else 4
        if af: feat['away_formation_def'] = int(af.split('-')[0]) if af.split('-')[0].isdigit() else 4
        feat['formation_diff'] = feat['home_formation_def'] - feat['away_formation_def']
        feat['has_lineups'] = 1
    
    try:
        expanded = expand_features_row(conn, feat, row['tournament'])
        for fi, fn in enumerate(ALL_F):
            X[idx, fi] = float(expanded.get(fn, 0))
    except: errors += 1

log(f'Built matrix: {X.shape} in {(time.time()-t0)/60:.1f}min')
log(f'Errors: {errors}, NaN: {np.isnan(X).sum()}')

# Chronological split (80/20)
n = len(df); split = int(n * 0.80)
log(f'\n[2/4] Training...')
log(f'Train: {split:,}, Test: {n-split:,}')

imp = SimpleImputer(strategy='median')
X_tr = imp.fit_transform(X[:split])
X_te = imp.transform(X[split:])

scaler = StandardScaler()
X_tr = scaler.fit_transform(X_tr)
X_te = scaler.transform(X_te)

y_tr, y_te = y[:split], y[split:]

# XGBoost first
t1 = time.time()
log('Training XGBoost (300 trees)...')
xgb_model = xgb.XGBClassifier(
    n_estimators=300, max_depth=6, learning_rate=0.03,
    objective='multi:softprob', num_class=25,
    subsample=0.8, colsample_bytree=0.8,
    reg_alpha=0.01, reg_lambda=0.01,
    random_state=42, verbosity=0,
    early_stopping_rounds=20
)
xgb_model.fit(X_tr, y_tr, eval_set=[(X_te, y_te)], verbose=False)

preds = xgb_model.predict(X_te)
probs = xgb_model.predict_proba(X_te)

exact = float(np.mean(preds == y_te)) * 100
# 1X2
actual_1x2 = np.array([0 if _cs(c)[0] > _cs(c)[1] else 1 if _cs(c)[0] == _cs(c)[1] else 2 for c in y_te])
pred_1x2 = np.array([0 if _cs(p)[0] > _cs(p)[1] else 1 if _cs(p)[0] == _cs(p)[1] else 2 for p in preds])
x1x2 = float(np.mean(pred_1x2 == actual_1x2)) * 100
rps = rps_score(y_te, probs)
t_train = time.time() - t1

log(f'\n{"="*50}')
log(f'🏆 QUICK V6 TEST RESULTS (50K matches, 132 features)')
log(f'{"="*50}')
log(f'Exact Score: {exact:.2f}%')
log(f'1X2: {x1x2:.2f}%')
log(f'RPS: {rps:.4f}')
log(f'Training time: {t_train:.0f}s')
log(f'XGBoost trees: {len(xgb_model.get_booster().get_dump())}')

# Compare to V5 baseline
log(f'\n📊 Comparison:')
log(f'  V5 (887K, 81 feat): 18.51% exact, 62.31% 1X2')
log(f'  V6 Quick (50K, 132 feat): {exact:.2f}% exact, {x1x2:.2f}% 1X2')
diff = exact - 18.51
log(f'  Difference: {diff:+.2f}%')

# Save results
results = {
    'date': time.strftime('%Y-%m-%d %H:%M'),
    'model': 'XGBoost V6 quick test',
    'samples': len(df),
    'features': len(ALL_F),
    'exact_score': round(exact, 2),
    '1x2': round(x1x2, 2),
    'rps': round(rps, 4),
    'train_time_sec': round(t_train, 0),
}

with open(os.path.join(MODEL_DIR, 'v6_quick_test.json'), 'w') as f:
    json.dump(results, f, indent=2)

log(f'\n✅ Results saved to v6_quick_test.json')
log(f'='*50)
conn.close()
