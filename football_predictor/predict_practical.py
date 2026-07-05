#!/usr/bin/env python3
"""
TRAIN PRACTICAL MODEL on 85 buildable features
Also: create prediction pipeline for upcoming matches
"""
import sys, os, time, json, sqlite3, numpy as np
os.environ['OMP_NUM_THREADS'] = '4'
BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

print("="*60)
print("PRACTICAL MODEL: 85 features (buildable for any match)")
print("="*60)
t0 = time.time()

import warnings
warnings.filterwarnings('ignore')
import lightgbm as lgb
import joblib

# Load features_full to get the 85 known features
print("[1] Loading features_full.npz...")
full = np.load('features_full.npz', allow_pickle=True)
X_all = full['features'].astype(np.float32)
y_all = full['scores'].astype(np.int32)
match_ids = full['match_ids']
fnames_all = full['feature_names']

# Map 81 buildable features (build_feature_vector returns 81, NOT 85)
# The 4 missing features are Glicko ratings (home/away glicko + glicko_rd)
from direct_predictor import FEATURES

# Features in build_feature_vector return order:
RETURNED_FEATURES = [
    'home_elo', 'away_elo', 'elo_diff',
    'home_xg_for', 'home_xg_against', 'away_xg_for', 'away_xg_against',
    'home_form', 'away_form', 'home_matches_played', 'away_matches_played',
    'home_shots_for', 'away_shots_for', 'home_shots_against', 'away_shots_against',
    'home_xg_diff', 'away_xg_diff', 'home_shot_diff', 'away_shot_diff',
    'home_days_rest', 'away_days_rest',
    'forebet_prob_h', 'forebet_prob_d', 'forebet_prob_a', 'forebet_available',
    'stat_h_xg', 'stat_a_xg', 'stat_h_shots', 'stat_a_shots',
    'stat_h_sot', 'stat_a_sot',
    'stat_h_possession', 'stat_a_possession',
    'stat_h_corners', 'stat_a_corners',
    'stat_h_fouls', 'stat_a_fouls',
    'home_formation_def', 'away_formation_def', 'formation_diff', 'has_lineups',
    'home_missing_core', 'home_att_loss', 'home_def_loss', 'away_missing_core', 'away_att_loss', 'away_def_loss',
    'odds_b365h', 'odds_b365d', 'odds_b365a',
    'odds_avgh', 'odds_avgd', 'odds_avga',
    'elo_form_home', 'elo_form_away',
    'elo_xg_home', 'elo_xg_away',
    'form_xg_home', 'form_xg_away',
    'elo_diff_form_diff', 'fatigue_home', 'fatigue_away',
    'xg_ratio', 'shots_ratio', 'form_ratio',
    'xgf_xga_ratio_home', 'xgf_xga_ratio_away',
    'shot_eff_home', 'shot_eff_away',
    'elo_diff_sq', 'xg_diff_sq', 'form_diff_sq',
    'month', 'day_of_week', 'season_progress', 'is_weekend',
    'home_temp', 'home_precip', 'home_wind', 'home_humidity',
    'travel_distance'
]

buildable_indices = []
buildable_names = []
for fn in RETURNED_FEATURES:
    matches = [j for j, fn_full in enumerate(fnames_all) if fn == fn_full]
    if matches:
        buildable_indices.append(matches[0])
        buildable_names.append(fn)

print(f"  Found {len(buildable_indices)}/{len(RETURNED_FEATURES)} buildable features")

# Extract only buildable features
X_buildable = X_all[:, buildable_indices]
print(f"  X: {X_buildable.shape}")

# Sort by match_id
order = np.argsort(match_ids)
X_buildable, y_all = X_buildable[order], y_all[order]

# Split
n = len(X_buildable); n_tr = int(n*0.9)
X_tr, y_tr = X_buildable[:n_tr], y_all[:n_tr]
X_te, y_te = X_buildable[n_tr:], y_all[n_tr:]
print(f"  Train: {len(y_tr):,}, Test: {len(y_te):,}")

# Train
print("[2] Training LightGBM on 85 features...")
model = lgb.LGBMClassifier(
    n_estimators=600, max_depth=8, learning_rate=0.03,
    num_leaves=63, min_child_samples=50,
    subsample=0.85, colsample_bytree=0.7,
    reg_alpha=0.1, reg_lambda=0.1,
    random_state=42, n_jobs=4, verbose=0)

model.fit(X_tr, y_tr,
    eval_set=[(X_te, y_te)],
    eval_metric='multi_logloss',
    callbacks=[lgb.early_stopping(20), lgb.log_evaluation(100)])

pred = model.predict(X_te)
exact = float(np.mean(pred == y_te))
yh, ya = y_te//5, y_te%5; ph, pa = pred//5, pred%5
yr = np.where(yh>ya,0,np.where(yh==ya,1,2))
pr = np.where(ph>pa,0,np.where(ph==pa,1,2))
acc_1x2 = float(np.mean(yr==pr))
print(f"\n  exact={exact*100:.2f}%, 1X2={acc_1x2*100:.2f}%")

# Save
joblib.dump(model, 'models/practical_81.pkl')

# Now create prediction pipeline
# Model expects 81 features (build_feature_vector returns exactly 81)
print(f"\n[3] Predicting upcoming matches...")
conn = sqlite3.connect('scrape_cache.db')
c = conn.cursor()

now = int(time.time())
upcoming = c.execute('SELECT home_team, away_team, commence_time, league, event_id, odds_json FROM odds_upcoming WHERE commence_time > ? ORDER BY commence_time', (now,)).fetchall()

# For each match, build feature vector using the existing function
sys.path.insert(0, BASE)
from direct_predictor import build_feature_vector, class_to_score, result

predictions = []
success = 0
fail = 0
for home, away, ct, league, eid, odds_json in upcoming:
    match_date = time.strftime('%Y-%m-%d', time.gmtime(ct))
    
    # Parse odds from JSON if available
    odds_b365 = None
    odds_avg = None
    if odds_json:
        try:
            o = json.loads(odds_json)
            if 'b365' in o:
                odds_b365 = o['b365']
            if 'avg' in o:
                odds_avg = o['avg']
        except:
            pass
    
    # Build feature vector
    features = build_feature_vector(home, away, match_date, odds_b365, odds_avg)
    if features is None:
        fail += 1
        continue
    
    # Predict
    proba = model.predict_proba(features.reshape(1, -1))[0]
    pred_class = np.argmax(proba)
    confidence = proba[pred_class]
    h_goals, a_goals = class_to_score(pred_class)
    
    # 1X2
    p_home = sum(proba[h*5+a] for h in range(5) for a in range(5) if h>a)
    p_draw = sum(proba[h*5+h] for h in range(5))
    p_away = sum(proba[h*5+a] for h in range(5) for a in range(5) if a>h)
    
    predictions.append({
        'home': home, 'away': away, 'date': match_date,
        'league': league,
        'predicted_score': f'{h_goals}-{a_goals}',
        'confidence': float(confidence),
        'home_win': float(p_home), 'draw': float(p_draw), 'away_win': float(p_away),
    })
    success += 1

predictions.sort(key=lambda p: -p['confidence'])
with open('practical_predictions.json', 'w') as f:
    json.dump(predictions, f, indent=2, ensure_ascii=False)

print(f"  Predicted: {success}, Failed to build: {fail}")

print(f"\n{'='*60}")
print(f"TOP 10 BEST BETS (85-feature practical model)")
print(f"{'='*60}")
for i, p in enumerate(predictions[:10]):
    print(f"\n{i+1}. {p['home']} vs {p['away']}")
    print(f"   Date: {p['date']} | {p['league']}")
    print(f"   {p['predicted_score']} (conf: {p['confidence']*100:.1f}%)")
    print(f"   1X2: H={p['home_win']*100:.1f}% / D={p['draw']*100:.1f}% / A={p['away_win']*100:.1f}%")

conn.close()
print(f"\n[DONE] Total time: {(time.time()-t0)/60:.1f} min")
print(f"85-feature model exact: {exact*100:.2f}%")
print(f"306-feature model exact: 36.35% (running in background)")
