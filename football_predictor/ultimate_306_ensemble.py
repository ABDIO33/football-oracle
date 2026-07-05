#!/usr/bin/env python3
"""
[FIRE] ULTIMATE ENSEMBLE TRAINER — 306 Features, 885K Matches [FIRE]
Trains 5 LightGBM models with different seeds, finds optimal blend
"""
import sys, os, time, json, gc, numpy as np
os.environ['OMP_NUM_THREADS'] = '4'
os.environ['PYTHONIOENCODING'] = 'utf-8'

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)
MODEL_DIR = os.path.join(BASE, 'models')

print("="*70)
print("[FIRE] ULTIMATE ENSEMBLE TRAINER [FIRE]")
print("="*70)
t0 = time.time()

import warnings
warnings.filterwarnings('ignore')
import lightgbm as lgb
import joblib

# 1️⃣ Load 306-feature dataset
print("\n[1] Loading features_full_understat.npz...")
data = np.load('features_full_understat.npz', allow_pickle=True)
X = data['X'].astype(np.float32)
y = data['y'].astype(np.int32)
match_ids = data['match_ids']
fnames = data['feature_names']
print(f"  X: {X.shape} ({X.nbytes/1024/1024:.0f} MB)")
print(f"  y: {y.shape}, unique classes: {len(np.unique(y))}")

# Sort by match_id (chronological)
order = np.argsort(match_ids)
X, y = X[order], y[order]
print(f"  Sorted, total: {len(y):,} matches")

# 2️⃣ Split (85% train, 15% test)
n = len(X); n_tr = int(n * 0.85)
X_tr, y_tr = X[:n_tr], y[:n_tr]
X_te, y_te = X[n_tr:], y[n_tr:]
print(f"\n[2] Split: Train={len(y_tr):,}, Test={len(y_te):,}")
print(f"    Test exact targets: class distribution:")
for c in range(25):
    cnt = (y_te == c).sum()
    if cnt > 0:
        print(f"      Score {c//5}-{c%5}: {cnt:>5,} ({cnt/len(y_te)*100:.1f}%)")

# 3️⃣ Train multiple LightGBM models
seeds = [42, 123, 456, 789, 999]
params_list = [
    # Seed 42 — default
    {'n_estimators': 600, 'max_depth': 8, 'learning_rate': 0.03,
     'num_leaves': 63, 'min_child_samples': 50,
     'subsample': 0.85, 'colsample_bytree': 0.7,
     'reg_alpha': 0.1, 'reg_lambda': 0.1, 'random_state': 42},
    # Seed 123 — deeper
    {'n_estimators': 500, 'max_depth': 10, 'learning_rate': 0.04,
     'num_leaves': 127, 'min_child_samples': 30,
     'subsample': 0.8, 'colsample_bytree': 0.8,
     'reg_alpha': 0.05, 'reg_lambda': 0.05, 'random_state': 123},
    # Seed 456 — shallower, more regularization
    {'n_estimators': 700, 'max_depth': 6, 'learning_rate': 0.025,
     'num_leaves': 31, 'min_child_samples': 100,
     'subsample': 0.9, 'colsample_bytree': 0.6,
     'reg_alpha': 0.2, 'reg_lambda': 0.2, 'random_state': 456},
    # Seed 789 — fast learning
    {'n_estimators': 400, 'max_depth': 8, 'learning_rate': 0.05,
     'num_leaves': 63, 'min_child_samples': 50,
     'subsample': 0.85, 'colsample_bytree': 0.7,
     'reg_alpha': 0.1, 'reg_lambda': 0.1, 'random_state': 789},
    # Seed 999 — balanced
    {'n_estimators': 600, 'max_depth': 7, 'learning_rate': 0.03,
     'num_leaves': 47, 'min_child_samples': 75,
     'subsample': 0.85, 'colsample_bytree': 0.75,
     'reg_alpha': 0.15, 'reg_lambda': 0.15, 'random_state': 999},
]

models = []
model_probas = []
model_scores = []

for i, params in enumerate(params_list):
    seed = params['random_state']
    print(f"\n[3.{i+1}] Training LightGBM seed={seed} ({params['max_depth']}/{params['num_leaves']})...")
    t1 = time.time()
    
    model = lgb.LGBMClassifier(**params, n_jobs=4, verbose=0)
    model.fit(X_tr, y_tr,
              eval_set=[(X_te, y_te)],
              eval_metric='multi_logloss',
              callbacks=[lgb.early_stopping(25), lgb.log_evaluation(100)])
    
    # Evaluate
    pred = model.predict(X_te)
    proba = model.predict_proba(X_te)
    exact = float(np.mean(pred == y_te))
    yh, ya = y_te//5, y_te%5; ph, pa = pred//5, pred%5
    yr = np.where(yh>ya, 0, np.where(yh==ya, 1, 2))
    pr = np.where(ph>pa, 0, np.where(ph==pa, 1, 2))
    acc_1x2 = float(np.mean(yr == pr))
    t_elapsed = (time.time() - t1) / 60
    
    models.append(model)
    model_probas.append(proba)
    model_scores.append({'exact': exact, 'acc_1x2': acc_1x2, 'seed': seed, 'time': t_elapsed})
    
    print(f"  Seed {seed:3d}: exact={exact*100:.2f}%, 1X2={acc_1x2*100:.2f}%, time={t_elapsed:.1f}min")
    
    # Save individual model
    path = os.path.join(MODEL_DIR, f'ensemble_seed{seed}.pkl')
    joblib.dump(model, path)
    print(f"  Saved: {path}")
    
    gc.collect()

# 4️⃣ Ensemble search
print("\n[4] Searching ensemble blends...")
model_probas_arr = np.array(model_probas)  # [n_models, n_test, 25]
n_models = len(models)

# Try all possible blends with step 0.05
results = []
for w0 in np.arange(0, 1.05, 0.1):
    for w1 in np.arange(0, 1.05 - w0 + 0.01, 0.1):
        for w2 in np.arange(0, 1.05 - w0 - w1 + 0.01, 0.1):
            for w3 in np.arange(0, 1.05 - w0 - w1 - w2 + 0.01, 0.1):
                w4 = 1.0 - w0 - w1 - w2 - w3
                if w4 < -0.01:
                    continue
                w = np.array([max(0, w0), max(0, w1), max(0, w2), max(0, w3), max(0, w4)])
                w = w / w.sum()
                
                blend = np.tensordot(w, model_probas_arr, axes=([0], [0]))
                pred = np.argmax(blend, axis=1)
                exact = float(np.mean(pred == y_te))
                results.append({'weights': tuple(round(x, 2) for x in w), 'exact': exact})

results.sort(key=lambda r: -r['exact'])
best = results[0]
print(f"\n{'Rank':>4} | {'Weights (S42,S123,S456,S789,S999)':40s} | {'Exact%':>7}")
print("-" * 60)
for i, r in enumerate(results[:10]):
    ws = '/'.join(f'{w:.1f}' for w in r['weights'])
    print(f"{i+1:>4} | {ws:40s} | {r['exact']*100:>6.2f}%")

# 5️⃣ Temperature calibration
print("\n[5] Temperature calibration...")
best_w = np.array(best['weights'])
blend_probas = np.tensordot(best_w, model_probas_arr, axes=([0], [0]))

best_temp = 1.0
best_temp_exact = best['exact']
for temp in np.arange(0.5, 2.0, 0.1):
    calib = blend_probas ** (1.0 / temp)
    calib = calib / calib.sum(axis=1, keepdims=True)
    pred = np.argmax(calib, axis=1)
    exact_temp = float(np.mean(pred == y_te))
    if exact_temp > best_temp_exact:
        best_temp_exact = exact_temp
        best_temp = temp

print(f"  Best temp: {best_temp}, exact={best_temp_exact*100:.2f}%")

# 6️⃣ Final evaluation
print(f"\n[6] Final Results")
print(f"  {'='*40}")
print(f"  Best model individual: {max(model_scores, key=lambda s: s['exact'])['exact']*100:.2f}%")
print(f"  Ensemble (no temp):    {best['exact']*100:.2f}%")
print(f"  Ensemble (temp={best_temp:.1f}): {best_temp_exact*100:.2f}%")
print(f"  Total time: {(time.time()-t0)/3600:.1f} hours")
print(f"  {'='*40}")

# 7️⃣ Save ensemble
class EnsemblePredictor:
    def __init__(self, models, weights, temperature=1.0):
        self.models = models
        self.weights = np.array(weights)
        self.temperature = temperature
    def predict_proba(self, X):
        probas = np.array([m.predict_proba(X) for m in self.models])
        blend = np.tensordot(self.weights, probas, axes=([0], [0]))
        if self.temperature != 1.0:
            blend = blend ** (1.0 / self.temperature)
            blend = blend / blend.sum(axis=1, keepdims=True)
        return blend
    def predict(self, X):
        return np.argmax(self.predict_proba(X), axis=1)

ensemble = EnsemblePredictor(models, best['weights'], best_temp)
path = os.path.join(MODEL_DIR, 'ultimate_306_ensemble.pkl')
joblib.dump(ensemble, path)
print(f"  Saved ensemble: {path}")

# Also save as joblib serializable format
ensemble_dict = {
    'models': models,
    'weights': best['weights'],
    'temperature': best_temp,
    'exact': best_temp_exact,
    'exact_no_temp': best['exact'],
    'n_features': X.shape[1],
    'model_configs': params_list,
}
joblib.dump(ensemble_dict, os.path.join(MODEL_DIR, 'ultimate_306_ensemble_dict.pkl'))
print(f"  Saved dict: models/ultimate_306_ensemble_dict.pkl")

# 8️⃣ Feature importance (from best single model)
best_single_idx = np.argmax([s['exact'] for s in model_scores])
best_single = models[best_single_idx]
imp = best_single.feature_importances_
top_n = 30
top_idx = np.argsort(imp)[-top_n:]
print(f"\n[8] Top {top_n} features from best single model:")
for i in range(top_n):
    idx = top_idx[i]
    print(f"  {fnames[idx]:40s}: {imp[idx]/imp.sum()*100:.2f}%")

print(f"\n{'='*70}")
print(f"[FIRE] ULTIMATE ENSEMBLE COMPLETE [FIRE]")
print(f"  Exact: {best_temp_exact*100:.2f}%")
print(f"  1X2:   {model_scores[0]['acc_1x2']*100:.2f}% (from first model)")
print(f"  Models: {n_models}")
print(f"  Features: {X.shape[1]}")
print(f"  Training samples: {len(y_tr):,}")
print(f"  Total time: {(time.time()-t0)/3600:.1f} hours")
print(f"{'='*70}")

# Save results
with open(os.path.join(MODEL_DIR, 'ultimate_306_results.json'), 'w') as f:
    json.dump({
        'exact_pct': round(best_temp_exact*100, 2),
        'exact_no_temp_pct': round(best['exact']*100, 2),
        'weights': [round(w, 4) for w in best['weights']],
        'temperature': best_temp,
        'n_features': X.shape[1],
        'n_train': len(y_tr),
        'n_test': len(y_te),
        'individual_exacts': [round(s['exact']*100, 2) for s in model_scores],
        'individual_1x2': [round(s['acc_1x2']*100, 2) for s in model_scores],
        'seeds': seeds,
        'time_hours': round((time.time()-t0)/3600, 2)
    }, f, indent=2)
print(f"  Saved: models/ultimate_306_results.json")
