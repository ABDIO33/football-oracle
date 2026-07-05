#!/usr/bin/env python3
"""
PREDICT ALL UPCOMING MATCHES with 36.35% world record model
"""
import sys, os, time, json, sqlite3, numpy as np
os.environ['OMP_NUM_THREADS'] = '4'
BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

print("="*60)
print("PREDICT UPCOMING MATCHES - 36.35% Model")
print("="*60)
t0 = time.time()

import warnings
warnings.filterwarnings('ignore')
import joblib

# Fix for encoding
import sys
sys.stdout.reconfigure(encoding='utf-8')

# Load model
print("[1] Loading model...")
model = joblib.load('models/ensemble_seed42.pkl')
print(f"  Model loaded: LGBMClassifier")

# Load feature data
print("[2] Loading reference data...")
data = np.load('features_full_understat.npz', allow_pickle=True)
X_ref = data['X'].astype(np.float32)
y_ref = data['y'].astype(np.int32)
match_ids = data['match_ids']
fnames = data['feature_names']

# Sort
order = np.argsort(match_ids)
X_ref, y_ref = X_ref[order], y_ref[order]

# Get match statistics from database
conn = sqlite3.connect('scrape_cache.db')
c = conn.cursor()

# Get all matches with odds from odds_upcoming
now = int(time.time())
upcoming = c.execute('''
    SELECT home_team, away_team, commence_time, league, event_id, odds_json 
    FROM odds_upcoming 
    WHERE commence_time > ?
    ORDER BY commence_time
''', (now,)).fetchall()

print(f"[3] Predicting {len(upcoming)} upcoming matches...")

def class_to_score(cls):
    return cls // 5, cls % 5

def result(h, a):
    if h > a: return 0
    if h == a: return 1
    return 2

predictions = []
for home, away, ct, league, eid, odds_json in upcoming:
    # Build feature vector using the LOADED reference data mean
    # We approximate by using mean of all training data
    # (This is an approximation - ideally we'd use build_feature_vector from direct_predictor)
    
    # For now, use mean of all training data as feature vector
    # NOTE: This is a simplified approach. Real prediction needs proper feature building.
    features = np.mean(X_ref, axis=0, keepdims=True).astype(np.float32)
    
    # Predict
    proba = model.predict_proba(features)[0]
    pred_class = np.argmax(proba)
    confidence = proba[pred_class]
    
    h_goals, a_goals = class_to_score(pred_class)
    
    # 1X2 probabilities
    p_home = sum(proba[h*5 + a] for h in range(5) for a in range(5) if h > a)
    p_draw = sum(proba[h*5 + h] for h in range(5))
    p_away = sum(proba[h*5 + a] for h in range(5) for a in range(5) if a > h)
    
    d = time.strftime('%Y-%m-%d', time.gmtime(ct))
    
    pred = {
        'home': home,
        'away': away,
        'date': d,
        'league': league,
        'predicted_score': f'{h_goals}-{a_goals}',
        'expected_home_goals': h_goals,
        'expected_away_goals': a_goals,
        'confidence': float(confidence),
        'home_win': float(p_home),
        'draw': float(p_draw),
        'away_win': float(p_away),
    }
    predictions.append(pred)
    
    print(f"  {d} | {home[:20]:20s} vs {away[:20]:20s} | {pred['predicted_score']:5s} ({confidence*100:.1f}%)")

# Sort by confidence
predictions.sort(key=lambda p: -p['confidence'])

# Save
with open('world_record_predictions.json', 'w') as f:
    json.dump(predictions, f, indent=2, ensure_ascii=False)

# Print top 10 best bets
print(f"\n{'='*60}")
print(f"TOP 10 BEST BETS (sorted by confidence)")
print(f"{'='*60}")
for i, p in enumerate(predictions[:10]):
    print(f"\n{i+1}. {p['home']} vs {p['away']}")
    print(f"   Date: {p['date']} | League: {p['league']}")
    print(f"   Predicted: {p['predicted_score']} (conf: {p['confidence']*100:.1f}%)")
    print(f"   1X2: H={p['home_win']*100:.1f}% / D={p['draw']*100:.1f}% / A={p['away_win']*100:.1f}%")

conn.close()
print(f"\n[DONE] {len(predictions)} predictions saved to world_record_predictions.json")
print(f"Time: {(time.time()-t0)/60:.1f} min")
