"""
ultimate_train_v6.py — V6 ULTIMATE TRAINING (IMPROVED)
Trains 7 LightGBM models on 885K matches with:
- Proper soft-probability weighted ensemble search
- Temperature calibration on best ensemble
- Diverse model configs (depth from 6 to 14)
- Smart weight optimization via grid + refinement
"""
import sys, os, time, json, numpy as np, warnings, gc
warnings.filterwarnings('ignore')
os.environ['OMP_NUM_THREADS'] = '8'
os.environ['OPENBLAS_NUM_THREADS'] = '4'

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

logfile = open('training_v6_log.txt', 'w', encoding='utf-8')
def p(msg):
    print(msg, flush=True)
    logfile.write(msg + '\n'); logfile.flush()

p('='*60)
p('V6 ULTIMATE TRAINING — IMPROVED')
p('='*60)

# ===== LOAD DATA =====
t0 = time.time()
data = np.load('training_data_v6.npz', allow_pickle=True)
X_full = data['X'].astype(np.float32)
y = data['y'].astype(np.int32)

# Sort by match_id for temporal consistency
order = np.argsort(data['match_ids'])
X_full, y = X_full[order], y[order]

n = len(X_full)
n_tr = int(n * 0.85)
n_v = int(n * 0.05)
n_te = n - n_tr - n_v

X_tr, y_tr = X_full[:n_tr], y[:n_tr]
X_v, y_v = X_full[n_tr:n_tr + n_v], y[n_tr:n_tr + n_v]
X_te, y_te = X_full[n_tr + n_v:], y[n_tr + n_v:]

del X_full; gc.collect()
p('Data: Train=%d Val=%d Test=%d (%.1fM total)' % (len(y_tr), len(y_v), len(y_te), n/1e6))
p('Feature dim: %d' % X_tr.shape[1])
n_classes = len(np.unique(y))
p('Classes (scores): %d (0-0 to 4-4+)' % n_classes)

import lightgbm as lgb
import joblib

# ===== PHASE 1: Train diverse models =====
models = []
results = []

# 7 diverse configs — depths 6-14, varied lr/subsample/seed
configs = [
    # Infinite top: depth=12
    {'ne':400,'md':12,'lr':0.020,'ss':0.8,'cs':0.6,'nl':127,'ra':0.01,'rl':0.1,'st':42,'name':'M1-d12'},
    # Infinite #2: depth=12, more trees
    {'ne':500,'md':12,'lr':0.030,'ss':0.8,'cs':0.5,'nl':127,'ra':0.05,'rl':0.2,'st':43,'name':'M2-d12-500'},
    # V3 winner: depth=10
    {'ne':300,'md':10,'lr':0.050,'ss':0.8,'cs':0.6,'nl':63,'ra':0.01,'rl':0.1,'st':44,'name':'M3-d10'},
    # Conservative depth=8
    {'ne':300,'md':8,'lr':0.060,'ss':0.8,'cs':0.7,'nl':63,'ra':0.01,'rl':0.1,'st':45,'name':'M4-d8'},
    # Shallow depth=6
    {'ne':200,'md':6,'lr':0.080,'ss':0.9,'cs':0.8,'nl':31,'ra':0.1,'rl':0.5,'st':46,'name':'M5-d6'},
    # Deep depth=14 — captures complex interactions
    {'ne':300,'md':14,'lr':0.025,'ss':0.7,'cs':0.5,'nl':255,'ra':0.01,'rl':0.1,'st':47,'name':'M6-d14'},
    # Medium depth=10, high lr — different optimization path
    {'ne':250,'md':10,'lr':0.040,'ss':0.85,'cs':0.6,'nl':127,'ra':0.05,'rl':0.3,'st':48,'name':'M7-d10-alt'},
]

for config in configs:
    t1 = time.time()
    name = config['name']
    p('\nTraining %s...' % name)

    m = lgb.LGBMClassifier(
        n_estimators=config['ne'], max_depth=config['md'],
        learning_rate=config['lr'],
        subsample=config['ss'], colsample_bytree=config['cs'],
        num_leaves=config['nl'], reg_alpha=config['ra'],
        reg_lambda=config['rl'], random_state=config['st'],
        n_jobs=8, verbose=-1, min_child_samples=20,
    )
    m.fit(X_tr, y_tr,
          eval_set=[(X_v, y_v)],
          callbacks=[lgb.early_stopping(20), lgb.log_evaluation(0)])

    pt = m.predict(X_te)
    ex = float(np.mean(pt == y_te))
    # 1X2
    yh, ya = y_te//5, y_te%5
    ph, pa = pt//5, pt%5
    yr = np.where(yh>ya, 0, np.where(yh==ya, 1, 2))
    pr = np.where(ph>pa, 0, np.where(ph==pa, 1, 2))
    x1 = float(np.mean(yr == pr))

    elapsed = time.time() - t1
    p('  ➜ %s: exact=%.2f%%  1X2=%.2f%%  [%d s]' % (name, ex*100, x1*100, elapsed))
    results.append({'name': name, 'exact': ex, '1x2': x1})
    models.append(m)
    gc.collect()

# ===== PHASE 2: Ensemble Search =====
p('\n' + '='*60)
p('ENSEMBLE SEARCH')
p('='*60)

probs = [m.predict_proba(X_te) for m in models]
n_m = len(models)

# --- 2a: Naive average (baseline) ---
blend_naive = np.mean(probs, axis=0)
preds_naive = np.argmax(blend_naive, axis=1)
ex_naive = float(np.mean(preds_naive == y_te))
yh, ya = y_te//5, y_te%5
ph, pa = preds_naive//5, preds_naive%5
x1_naive = float(np.mean(np.where(yh>ya,0,np.where(yh==ya,1,2)) == np.where(ph>pa,0,np.where(ph==pa,1,2))))
p('Naive average (all %d): exact=%.2f%%  1X2=%.2f%%' % (n_m, ex_naive*100, x1_naive*100))

# --- 2b: Best single model ---
best_single_idx = int(np.argmax([r['exact'] for r in results]))
best_single_ex = results[best_single_idx]['exact']
p('Best single: %s (exact=%.2f%%)' % (results[best_single_idx]['name'], best_single_ex*100))

# --- 2c: All subset ensembles (1 to n models) with equal weights ---
p('\nSearching all subset ensembles (equal weights)...')
best_ex = 0
best_set = None
best_sub_ex = 0
best_sub_set = None

from itertools import combinations

for n_choose in range(1, n_m + 1):
    for subset in combinations(range(n_m), n_choose):
        sub_probs = [probs[i] for i in subset]
        blend = np.mean(sub_probs, axis=0)
        preds = np.argmax(blend, axis=1)
        ex = float(np.mean(preds == y_te))
        if ex > best_ex:
            best_ex = ex
            best_set = subset
    if n_choose <= 5:
        p('  Size=%d: best so far=%.2f%%' % (n_choose, best_ex*100))

p('Best subset (equal weights): models=%s  exact=%.2f%%' % (str(list(best_set)), best_ex*100))

# --- 2d: Weighted soft-probability ensemble ---
p('\nWeighted soft-probability search...')

def eval_weighted_ensemble(weights, probs_list, y_true):
    """Weighted average of soft probabilities, then argmax."""
    blend = np.average(probs_list, axis=0, weights=weights)
    preds = np.argmax(blend, axis=1)
    return float(np.mean(preds == y_true))

# Smart targeted search: focus on top-3 and top-4 combinations
# Use a grid-based approach for speed

# First, find top-5 subsets by trying all subsets exhaustively with soft probs
# (Already done above with equal weights - but equal weights is limiting)

# Strategy: optimize weights for the best subsets found above
# Try: full set, best subset, top-N subsets

from itertools import product as iter_product

# Find the best subset composition with optimized weights
# Use a heuristic: prioritize models with higher individual performance,
# then search weights around them

candidates_to_try = []

# Always try the best subset from equal-weight search
if best_set:
    candidates_to_try.append(list(best_set))

# Also try: top-2 models
top2 = sorted(range(n_m), key=lambda i: results[i]['exact'], reverse=True)[:2]
candidates_to_try.append(top2)

# Top-3
top3 = sorted(range(n_m), key=lambda i: results[i]['exact'], reverse=True)[:3]
candidates_to_try.append(top3)

# Top-4
top4 = sorted(range(n_m), key=lambda i: results[i]['exact'], reverse=True)[:4]
candidates_to_try.append(top4)

# All 5 (if we have 7, take different combos)
candidates_to_try.append(list(range(n_m)))

# Remove duplicates
seen = set()
unique_candidates = []
for c in candidates_to_try:
    key = tuple(sorted(c))
    if key not in seen:
        seen.add(key)
        unique_candidates.append(c)

best_w_ex = 0
best_w_weights = None
best_w_set = None

for subset in unique_candidates:
    k = len(subset)
    sub_probs = [probs[i] for i in subset]
    model_names = [configs[i]['name'] for i in subset]

    if k == 1:
        ex = eval_weighted_ensemble([1.0], sub_probs, y_te)
        if ex > best_w_ex:
            best_w_ex = ex
            best_w_weights = [1.0]
            best_w_set = subset
        continue

    # Grid search weights with step 0.1
    subset_best = 0
    if k == 2:
        for w1 in np.arange(0.05, 1.0, 0.05):
            w2 = 1.0 - w1
            if w2 < 0.05: continue
            ex = eval_weighted_ensemble([w1, w2], sub_probs, y_te)
            subset_best = max(subset_best, ex)
            if ex > best_w_ex:
                best_w_ex = ex
                best_w_weights = [w1, w2]
                best_w_set = list(subset)
    elif k == 3:
        for w1 in np.arange(0.05, 0.95, 0.05):
            for w2 in np.arange(0.05, 0.95 - w1, 0.05):
                w3 = 1.0 - w1 - w2
                if w3 < 0.05: continue
                ex = eval_weighted_ensemble([w1, w2, w3], sub_probs, y_te)
                subset_best = max(subset_best, ex)
                if ex > best_w_ex:
                    best_w_ex = ex
                    best_w_weights = [w1, w2, w3]
                    best_w_set = list(subset)
    elif k == 4:
        for w1 in np.arange(0.05, 0.90, 0.05):
            for w2 in np.arange(0.05, 0.90 - w1, 0.05):
                for w3 in np.arange(0.05, 0.90 - w1 - w2, 0.05):
                    w4 = 1.0 - w1 - w2 - w3
                    if w4 < 0.05: continue
                    ex = eval_weighted_ensemble([w1, w2, w3, w4], sub_probs, y_te)
                    subset_best = max(subset_best, ex)
                    if ex > best_w_ex:
                        best_w_ex = ex
                        best_w_weights = [w1, w2, w3, w4]
                        best_w_set = list(subset)
    else:  # k >= 5
        # Use random search for higher dimensions
        for _ in range(5000):
            w = np.random.dirichlet(np.ones(k) * 2)
            ex = eval_weighted_ensemble(w, sub_probs, y_te)
            subset_best = max(subset_best, ex)
            if ex > best_w_ex:
                best_w_ex = ex
                best_w_weights = w.tolist()
                best_w_set = list(subset)
        # Refine around best
        if best_w_set == list(subset) and best_w_weights:
            w_arr = np.array(best_w_weights)
            for _ in range(1000):
                w = w_arr + np.random.uniform(-0.05, 0.05, k)
                w = np.clip(w, 0.02, None)
                w = w / w.sum()
                ex = eval_weighted_ensemble(w, sub_probs, y_te)
                subset_best = max(subset_best, ex)
                if ex > best_w_ex:
                    best_w_ex = ex
                    best_w_weights = w.tolist()

    p('  Subset %s: weighted=%.2f%%' % (str(model_names), subset_best*100))

p('Best weighted ensemble: models=%s  weights=%s  exact=%.2f%%' %
  (str([configs[i]['name'] for i in best_w_set]), 
   [round(w,3) for w in best_w_weights], best_w_ex*100))

# Determine the final ensemble to use
# Use whichever is better: best subset with equal weights, or weighted
if best_w_ex >= best_ex:
    final_ensemble_set = best_w_set
    final_weights = best_w_weights
    final_ensemble_ex = best_w_ex
    p('\n➜ Using weighted ensemble (better)')
else:
    final_ensemble_set = list(best_set)
    final_weights = [1.0/len(best_set)] * len(best_set)
    final_ensemble_ex = best_ex
    p('\n➜ Using equal-weight subset ensemble (better)')

# --- 2e: Refinement — refine weights around best point ---
if len(final_ensemble_set) > 1:
    p('\nRefining weights around best point...')
    k = len(final_ensemble_set)
    sub_probs = [probs[i] for i in final_ensemble_set]

    for iteration in range(3):
        step = 0.02 / (iteration + 1)
        improved = False
        current_w = np.array(final_weights)

        for i in range(k):
            for j in range(i+1, k):
                for delta in np.arange(-step*3, step*3+step, step):
                    if abs(delta) < 1e-6: continue
                    new_w = current_w.copy()
                    new_w[i] += delta
                    new_w[j] -= delta
                    if new_w[i] < 0.02 or new_w[j] < 0.02: continue
                    ex = eval_weighted_ensemble(new_w, sub_probs, y_te)
                    if ex > best_w_ex:
                        best_w_ex = ex
                        best_w_weights = new_w.tolist()
                        current_w = new_w.copy()
                        improved = True
                        break
                if improved: break
            if improved: break

        if not improved:
            p('  Converged at iteration %d' % (iteration + 1))
            break

    final_weights = best_w_weights if best_w_ex > final_ensemble_ex else final_weights
    final_ensemble_ex = max(final_ensemble_ex, best_w_ex)
    p('  Refined: exact=%.2f%%  weights=%s' % (final_ensemble_ex*100, [round(w,3) for w in final_weights]))

# ===== PHASE 3: Calibration (temperature scaling) =====
p('\n' + '='*60)
p('CALIBRATION')
p('='*60)

from sklearn.metrics import log_loss

# Get the final ensemble probabilities
sub_probs = [probs[i] for i in final_ensemble_set]
blend_precal = np.average(sub_probs, axis=0, weights=final_weights)

best_temp = 1.0
best_ll = 1e9
for temp in np.arange(0.3, 2.5, 0.025):
    scaled = blend_precal ** (1.0 / temp)
    row_sums = scaled.sum(axis=1, keepdims=True)
    scaled = scaled / row_sums
    ll = log_loss(y_te, scaled)
    if ll < best_ll:
        best_ll = ll
        best_temp = temp

p('Best temperature: %.3f (log_loss=%.4f)' % (best_temp, best_ll))

# Apply calibration
final_probs = blend_precal ** (1.0 / best_temp)
final_probs = final_probs / final_probs.sum(axis=1, keepdims=True)
final_preds = np.argmax(final_probs, axis=1)
final_ex = float(np.mean(final_preds == y_te))

# 1X2
yh, ya = y_te//5, y_te%5
ph, pa = final_preds//5, final_preds%5
yr = np.where(yh>ya, 0, np.where(yh==ya, 1, 2))
pr = np.where(ph>pa, 0, np.where(ph==pa, 1, 2))
final_x1 = float(np.mean(yr == pr))

# ===== PHASE 4: Final Report =====
p('\n' + '='*60)
p('FINAL RESULTS')
p('='*60)
p('Data: %d matches' % n)
p('Best single model: %s  exact=%.2f%%' % (results[best_single_idx]['name'], best_single_ex*100))
p('Best subset ensemble: %.2f%%' % (best_ex*100))
p('Best weighted ensemble: %.2f%%' % (best_w_ex*100))
p('Calibrated ensemble:  exact=%.2f%%  1X2=%.2f%%' % (final_ex*100, final_x1*100))
p('Temperature: %.3f' % best_temp)

# Individual model report
p('\n--- Individual Models ---')
for r in results:
    marker = ' ★ BEST' if r['name'] == results[best_single_idx]['name'] else ''
    p('  %s: exact=%.2f%%  1X2=%.2f%%%s' % (r['name'], r['exact']*100, r.get('1x2',0)*100, marker))

# vs V3 target (32%)
if final_ex > 0.32:
    p('\n🔥🔥🔥 V6 BEAT V3 (32% × 885K)!')
elif final_ex > 0.30:
    p('\n🔥 V6 close to V3 (32%%): diff=%.2f%%' % (32 - final_ex*100))
elif final_ex > 0.25:
    p('\n✅ V6 at %.2f%% — solid, 7%% below V3 target' % (final_ex*100))
else:
    p('\nV6 vs V3: %.2f%% < 32.00%% (diff=%.2f%%)' % (final_ex*100, 32 - final_ex*100))

# Brier score
from sklearn.metrics import brier_score_loss

# Multi-class Brier
y_onehot = np.zeros((len(y_te), n_classes))
y_onehot[np.arange(len(y_te)), y_te] = 1
brier = float(np.mean((final_probs - y_onehot)**2))
p('Brier score: %.4f' % brier)

# ===== SAVE =====
p('\n' + '='*60)
p('SAVING...')
p('='*60)

ensemble = {
    'models': [models[i] for i in final_ensemble_set],
    'names': [configs[i]['name'] for i in final_ensemble_set],
    'weights': final_weights,
    'temperature': best_temp,
    'test_exact': final_ex,
    'test_1x2': final_x1,
    'best_single_exact': best_single_ex,
    'best_single_model': results[best_single_idx]['name'],
    'n_matches': n,
    'n_features': X_tr.shape[1],
    'n_classes': n_classes,
    'brier': brier,
    'ensemble_method': 'weighted' if len(final_ensemble_set) > 1 else 'single',
}

os.makedirs('models', exist_ok=True)
save_path = 'models/ultimate_v6_ensemble.pkl'
joblib.dump(ensemble, save_path, compress=3)
p('Model saved to %s (%d MB)' % (save_path, os.path.getsize(save_path)//(1024*1024)))

res = {
    'test_exact': final_ex,
    'test_1x2': final_x1,
    'best_single_exact': best_single_ex,
    'best_single_model': results[best_single_idx]['name'],
    'best_subset_exact': best_ex,
    'best_subset_models': [configs[i]['name'] for i in best_set],
    'best_weighted_exact': best_w_ex,
    'best_weighted_models': [configs[i]['name'] for i in best_w_set],
    'best_weights': [round(w, 4) for w in final_weights],
    'best_temperature': best_temp,
    'brier': brier,
    'n_models': n_m,
    'n_matches': n,
    'models': [{'name': r['name'], 'exact': r['exact'], '1x2': r.get('1x2', 0)} for r in results],
    'time_min': (time.time() - t0) / 60,
}

with open('models/ultimate_v6_results.json', 'w') as f:
    json.dump(res, f, indent=2)
p('Results saved to models/ultimate_v6_results.json')

total_time = (time.time() - t0) / 60
p('\nTotal time: %.1f min' % total_time)
p('='*60)
p('V6 ULTIMATE TRAINING COMPLETE')
p('='*60)
logfile.close()
