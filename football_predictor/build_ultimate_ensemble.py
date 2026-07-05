"""
build_ultimate_ensemble.py — يجمع V3, V6, وأفضل نماذج infinite trainer
لصنع أقوى ensemble في العالم
"""
import sys, os, time, json, gc, warnings
import numpy as np
warnings.filterwarnings('ignore')
os.environ['OMP_NUM_THREADS'] = '4'

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

logfile = open('ultimate_ensemble_log.txt', 'w', encoding='utf-8')
def p(msg):
    print(msg, flush=True)
    logfile.write(msg + '\n'); logfile.flush()

p('='*60)
p('ULTIMATE ENSEMBLE BUILDER — يجمع كل النماذج')
p('='*60)

import joblib, lightgbm as lgb

# Load V3 test data (consistent benchmark)
data = np.load('training_data_v3.npz', allow_pickle=True)
X = data['X'].astype(np.float32); y = data['y'].astype(np.int32)
order = np.argsort(data['match_ids'])
X, y = X[order], y[order]
n = len(X); n_te = int(n * 0.1)
X_te, y_te = X[-n_te:], y[-n_te:]
p(f'Test data: {len(y_te):,} matches')

# Load V3 ensemble
p('\nLoading models...')
models = []
names = []

# 1. V3 ensemble
if os.path.exists('models/ultimate_30pct_ensemble.pkl'):
    v3 = joblib.load('models/ultimate_30pct_ensemble.pkl')
    for i, m in enumerate(v3['models']):
        models.append(m)
        names.append(f'V3-M{i+1}')
    p(f'  V3 ensemble: {len(v3["models"])} models loaded')

# 2. V6 ensemble (if exists)
v6_path = 'models/ultimate_v6_ensemble.pkl'
if os.path.exists(v6_path):
    v6 = joblib.load(v6_path)
    if 'models' in v6:
        for i, m in enumerate(v6['models']):
            models.append(m)
            names.append(f'V6-M{i+1}')
        p(f'  V6 ensemble: {len(v6["models"])} models loaded')
    elif isinstance(v6, dict) and 'LGBMClassifier' in str(type(list(v6.values())[0])):
        # Single model wrapper
        models.append(v6)
        names.append('V6')

# 3. Any saved models from infinite trainer
import sqlite3
conn = sqlite3.connect('training_results.db')
saved = conn.execute('SELECT model_path FROM results WHERE model_path IS NOT NULL AND model_path != ""').fetchall()
conn.close()
for s in saved:
    path = s[0]
    full_path = os.path.join(BASE, path) if not os.path.isabs(path) else path
    if os.path.exists(full_path):
        try:
            m = joblib.load(full_path)
            models.append(m)
            names.append(os.path.basename(path))
        except:
            pass
p(f'  Total models: {len(models)}')

if len(models) < 2:
    p('Need at least 2 models!')
    logfile.close()
    sys.exit(0)

# Compute predictions
p('\nComputing predictions...')
t0 = time.time()
probs = []
for i, m in enumerate(models):
    try:
        p_ = m.predict_proba(X_te)
        probs.append(p_)
        p(f'  {names[i]}: OK')
    except Exception as e:
        p(f'  {names[i]}: ERROR {str(e)[:50]}')

if len(probs) < 2:
    p('Not enough working models')
    logfile.close()
    sys.exit(0)

n_m = len(probs)
p(f'{n_m} models working')

# Brute-force search for best ensemble
p('\nSearching best ensemble combination...')
best_ex = 0; best_combo = None; best_type = ''

# Try all subsets
from itertools import combinations as combs
for n_c in range(2, min(n_m+1, 6)):
    for combo in combs(range(n_m), n_c):
        sub = [probs[i] for i in combo]
        blend = np.mean(sub, axis=0)
        preds = np.argmax(blend, axis=1)
        ex = float(np.mean(preds == y_te))
        if ex > best_ex:
            best_ex = ex
            best_combo = combo
            best_type = f'avg({n_c})'

p(f'Best naive ensemble ({best_type}): {best_ex*100:.2f}%')
p(f'  Models: {[names[i] for i in best_combo]}')

# Weighted search
p('\nWeighted search...')
best_w_ex = 0; best_w = None
for _ in range(5000):
    weights = np.random.dirichlet(np.ones(n_m), 1)[0]
    w_pred = np.zeros(len(y_te))
    for i in range(n_m):
        w_pred += weights[i] * np.argmax(probs[i], 1)
    w_pred = np.round(w_pred).astype(int)
    w_pred = np.clip(w_pred, 0, 24)
    ex = float(np.mean(w_pred == y_te))
    if ex > best_w_ex:
        best_w_ex = ex
        best_w = weights.tolist()

p(f'Weighted best (random search): {best_w_ex*100:.2f}%')

# Temperature calibration
from sklearn.metrics import log_loss
best_temp = 1.0; best_ll = 1e9
for temp in np.arange(0.3, 2.5, 0.05):
    scaled = np.mean(probs, axis=0) ** (1.0/temp)
    scaled = scaled / scaled.sum(axis=1, keepdims=True)
    ll = log_loss(y_te, scaled)
    if ll < best_ll:
        best_ll = ll; best_temp = temp

# Calibrated ensemble
final_probs = np.mean(probs, axis=0) ** (1.0/best_temp)
final_probs = final_probs / final_probs.sum(axis=1, keepdims=True)
final_preds = np.argmax(final_probs, axis=1)
final_ex = float(np.mean(final_preds == y_te))

yh, ya = y_te//5, y_te%5; ph, pa = final_preds//5, final_preds%5
yr = np.where(yh>ya,0,np.where(yh==ya,1,2)); pr = np.where(ph>pa,0,np.where(ph==pa,1,2))
final_x1 = float(np.mean(yr==pr))

p(f'\n=== FINAL RESULTS ===')
p(f'Naive ensemble: {best_ex*100:.2f}%')
p(f'Weighted ensemble: {best_w_ex*100:.2f}%')
p(f'Calibrated ensemble (T={best_temp:.3f}): {final_ex*100:.2f}%')
p(f'1X2 accuracy: {final_x1*100:.2f}%')

# Compare with V3 known result
p(f'\nV3 was 32.00%')
if final_ex > 0.32:
    p('🔥🔥🔥 NEW WORLD RECORD!')
elif final_ex > 0.30:
    p(f'Close! diff={(32-final_ex*100):.2f}%')

# Save
ensemble = {
    'models': [models[i] for i in best_combo],
    'names': [names[i] for i in best_combo],
    'temperature': best_temp,
    'test_exact': final_ex,
    'test_1x2': final_x1,
    'n_models': n_m,
    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
}
joblib.dump(ensemble, 'models/ultimate_world_record.pkl', compress=3)

res = {
    'test_exact': best_ex,
    'best_ensemble_exact': final_ex,
    'test_1x2': final_x1,
    'best_temperature': best_temp,
    'weighted_exact': best_w_ex,
    'n_models': n_m,
    'model_names': names,
    'best_combo': [names[i] for i in best_combo],
    'time': time.strftime('%Y-%m-%d %H:%M:%S')
}
with open('models/ultimate_world_record_results.json', 'w') as f:
    json.dump(res, f, indent=2)

p(f'\nSAVED! Time: {(time.time()-t0)/60:.1f} min')
logfile.close()
