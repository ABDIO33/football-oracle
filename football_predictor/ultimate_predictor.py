#!/usr/bin/env python3
"""
ULTIMATE PREDICTOR — يستخدم الموديل 36.35% للتوقعات الحقيقية
ENI for LO
"""
import sys, os, time, json, sqlite3, numpy as np
BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, BASE)
os.environ['OMP_NUM_THREADS'] = '4'
os.environ['PYTHONIOENCODING'] = 'utf-8'

print("="*60)
print("ULTIMATE PREDICTOR — 36.35% World Record Model")
print("="*60)
t0 = time.time()

import joblib
from direct_predictor import build_feature_vector

# Load model
print("[1] Loading ensemble_seed42.pkl...")
model = joblib.load('models/ensemble_seed42.pkl')
print(f"  Model expects: {model.n_features_in_} features")

# Load prediction data
print("[2] Loading prediction_data_306.npz...")
pred_data = np.load('prediction_data_306.npz', allow_pickle=True)
mapping = pred_data['mapping_81_to_306']  # (26, 2) - (81_idx, 306_idx)
means = pred_data['feature_means_306']

# Connect to DB for odds
conn = sqlite3.connect('scrape_cache.db')
c = conn.cursor()

# Get upcoming matches with odds
now = int(time.time())
upcoming = c.execute('''
    SELECT home_team, away_team, commence_time, league, odds_json 
    FROM odds_upcoming WHERE commence_time > ? ORDER BY commence_time
''', (now,)).fetchall()

print(f"[3] Predicting {len(upcoming)} upcoming matches...")

def class_to_score(cls):
    return cls // 5, cls % 5

def predict_match_ultimate(home, away, match_date, odds_b365=None, odds_avg=None):
    """Predict using 36.35% model"""
    feat_81 = build_feature_vector(home, away, match_date, odds_b365, odds_avg)
    if feat_81 is None or len(feat_81.shape) < 2 or feat_81.shape[1] < 26:
        return None
    
    feat_81_flat = feat_81[0]  # (81,)
    
    # Build full 306-feature vector
    feat_306 = means.copy()  # Start with means
    for _81_idx, _306_idx in mapping:
        feat_306[_306_idx] = feat_81_flat[_81_idx]
    
    # Predict
    proba = model.predict_proba(feat_306.reshape(1, -1))[0]
    pred_class = np.argmax(proba)
    confidence = proba[pred_class]
    
    h_goals, a_goals = class_to_score(pred_class)
    
    # 1X2 probabilities
    p_home = sum(proba[h*5+a] for h in range(5) for a in range(5) if h>a)
    p_draw = sum(proba[h*5+h] for h in range(5))
    p_away = sum(proba[h*5+a] for h in range(5) for a in range(5) if a>h)
    
    return {
        'predicted_score': f'{h_goals}-{a_goals}',
        'confidence': float(confidence),
        'home_win': float(p_home),
        'draw': float(p_draw),
        'away_win': float(p_away),
        'proba': proba
    }

# Predict all upcoming matches
predictions = []
for home, away, ct, league, odds_json in upcoming:
    match_date = time.strftime('%Y-%m-%d', time.gmtime(ct))
    
    # Parse odds
    odds_b365 = None
    odds_avg = None
    if odds_json:
        try:
            o = json.loads(odds_json)
            if 'b365' in o: odds_b365 = o['b365']
            if 'avg' in o: odds_avg = o['avg']
        except: pass
    
    result = predict_match_ultimate(home, away, match_date, odds_b365, odds_avg)
    if result is None:
        continue
    
    predictions.append({
        'home': home,
        'away': away,
        'date': match_date,
        'league': league,
        'predicted_score': result['predicted_score'],
        'confidence': result['confidence'],
        'home_win': result['home_win'],
        'draw': result['draw'],
        'away_win': result['away_win'],
    })

# Sort by confidence
predictions.sort(key=lambda p: -p['confidence'])

# Save
with open('ultimate_predictions.json', 'w') as f:
    json.dump(predictions, f, indent=2, ensure_ascii=False, default=str)

print(f"\\n{'='*60}")
print(f"TOP PREDICTIONS — 36.35% Model")
print(f"{'='*60}")
for i, p in enumerate(predictions[:10]):
    print(f"\\n{i+1}. {p['home']} vs {p['away']}")
    print(f"   {p['date']} | {p['league']}")
    print(f"   {p['predicted_score']} (conf: {p['confidence']*100:.1f}%)")
    print(f"   1X2: H={p['home_win']*100:.1f}% / D={p['draw']*100:.1f}% / A={p['away_win']*100:.1f}%")

conn.close()
print(f"\\n[DONE] {len(predictions)} predictions saved to ultimate_predictions.json")
print(f"Time: {(time.time()-t0)/60:.1f} min")
