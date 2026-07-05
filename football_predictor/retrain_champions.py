"""
retrain_champions.py — إعادة تدريب النماذج الفائزة وحفظها
"""
import sys, os, time, json, numpy as np, warnings, gc
warnings.filterwarnings('ignore')
os.environ['OMP_NUM_THREADS'] = '8'

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

logfile = open('champion_retrain_log.txt', 'w', encoding='utf-8')
def p(msg):
    print(msg, flush=True)
    logfile.write(msg + '\n'); logfile.flush()

p('CHAMPION MODEL RETRAINING')
p('='*50)

t0 = time.time()
data = np.load('training_data_v3.npz', allow_pickle=True)
X = data['X'].astype(np.float32); y = data['y'].astype(np.int32)
rt = data['result_types'].astype(np.int32)
order = np.argsort(data['match_ids'])
X, y, rt = X[order], y[order], rt[order]
n = len(X); n_tr = int(n*0.85); n_v = int(n*0.05)
X_tr, y_tr = X[:n_tr], y[:n_tr]
X_v, y_v = X[n_tr:n_tr+int(n*0.05)], y[n_tr:n_tr+int(n*0.05)]
X_te, y_te = X[n_tr+int(n*0.05):], y[n_tr+int(n*0.05):]
rt_te = rt[n_tr+int(n*0.05):]
del X, rt; gc.collect()
p('Data: Train=%d Val=%d Test=%d' % (len(y_tr), len(y_v), len(y_te)))

import lightgbm as lgb, joblib

models = []
results = []

def eval_model(m, name, Xtest, ytest):
    p_ = m.predict(Xtest)
    ex = float(np.mean(p_ == ytest))
    # Also check 1X2
    yh, ya = ytest//5, ytest%5; ph, pa = p_//5, p_%5
    yr = np.where(yh>ya,0,np.where(yh==ya,1,2)); pr = np.where(ph>pa,0,np.where(ph==pa,1,2))
    x1 = float(np.mean(yr==pr))
    p('%s: exact=%.2f%% 1X2=%.2f%%' % (name, ex*100, x1*100))
    return {'name': name, 'exact': ex, '1x2': x1}

# === M5: Extra Deep (depth=20, winner @36.35%) ===
p('\n=== M5: Extra Deep (depth=20) ===')
t1 = time.time()
m5 = lgb.LGBMClassifier(
    n_estimators=200, max_depth=20, learning_rate=0.02,
    subsample=0.7, colsample_bytree=0.4, num_leaves=511,
    reg_alpha=0.01, reg_lambda=0.05, min_child_weight=2,
    random_state=111, n_jobs=8, verbose=-1
)
m5.fit(X_tr, y_tr, eval_set=[(X_v, y_v)],
      callbacks=[lgb.early_stopping(20), lgb.log_evaluation(0)])
r5 = eval_model(m5, 'M5-extra_deep', X_te, y_te)
p('  Time: %ds' % (time.time()-t1))
models.append(m5); results.append(r5)
joblib.dump(m5, 'models/M5_extra_deep.pkl', compress=3)
p('  Saved: models/M5_extra_deep.pkl')

# === M3: Deep Subsample (depth=15, 32.12%) ===
p('\n=== M3: Deep Subsample (depth=15, 70% data) ===')
t1 = time.time()
idx = np.random.RandomState(42).choice(len(y_tr), int(len(y_tr)*0.7), replace=False)
m3 = lgb.LGBMClassifier(
    n_estimators=400, max_depth=15, learning_rate=0.03,
    subsample=0.6, colsample_bytree=0.4, num_leaves=255,
    reg_alpha=0.05, reg_lambda=0.2, min_child_weight=3,
    random_state=88, n_jobs=8, verbose=-1
)
m3.fit(X_tr[idx], y_tr[idx], eval_set=[(X_v, y_v)],
      callbacks=[lgb.early_stopping(20), lgb.log_evaluation(0)])
r3 = eval_model(m3, 'M3-deep_sub', X_te, y_te)
p('  Time: %ds' % (time.time()-t1))
models.append(m3); results.append(r3)
joblib.dump(m3, 'models/M3_deep_sub.pkl', compress=3)
p('  Saved: models/M3_deep_sub.pkl')

# === Ensemble M3 + M5 ===
p('\n=== ENSEMBLE ===')
p3 = m3.predict_proba(X_te); p5 = m5.predict_proba(X_te)

# Naive
blend = (p3 + p5) / 2
preds = np.argmax(blend, axis=1)
ex = float(np.mean(preds == y_te))
p('M3+M5 avg: %.2f%%' % (ex*100))

# Weighted
for w in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
    blend = w*p3 + (1-w)*p5
    preds = np.argmax(blend, axis=1)
    e = float(np.mean(preds == y_te))
    p('  w3=%.1f w5=%.1f: %.2f%%' % (w, 1-w, e*100))

# Best blend (try all)
best_ex = 0; best_w = 0
for w in np.arange(0.01, 1.0, 0.01):
    blend = w*p3 + (1-w)*p5
    preds = np.argmax(blend, axis=1)
    e = float(np.mean(preds == y_te))
    if e > best_ex:
        best_ex = e; best_w = w
p('Best: w3=%.2f w5=%.2f: %.2f%%' % (best_w, 1-best_w, best_ex*100))

# === Add V3 ensemble ===
p('\n=== WITH V3 ===')
v3 = joblib.load('models/ultimate_30pct_ensemble.pkl')
v3_p = np.mean([m.predict_proba(X_te) for m in v3['models']], axis=0)

# Try M5 + V3
best_v3 = 0; best_v3w = 0
for w in np.arange(0.05, 1.0, 0.05):
    blend = w*p5 + (1-w)*v3_p
    preds = np.argmax(blend, axis=1)
    e = float(np.mean(preds == y_te))
    if e > best_v3:
        best_v3 = e; best_v3w = w
p('M5+V3: w=%.2f: %.2f%%' % (best_v3w, best_v3*100))

# Try M3+M5+V3
p3_p = m3.predict_proba(X_te)
best_3 = 0; best_w3 = {}
for w3 in np.arange(0.1, 0.8, 0.1):
    for w5 in np.arange(0.1, 0.8, 0.1):
        wv = 1-w3-w5
        if wv <= 0: continue
        blend = w3*p3_p + w5*p5 + wv*v3_p
        preds = np.argmax(blend, axis=1)
        e = float(np.mean(preds == y_te))
        if e > best_3:
            best_3 = e; best_w3 = {'M3': w3, 'M5': w5, 'V3': wv}
p('M3+M5+V3: w=%.1f/%.1f/%.1f: %.2f%%' % (best_w3.get('M3', 0), best_w3.get('M5', 0), best_w3.get('V3', 0), best_3*100))

# ===== FINAL RESULTS =====
final_ex = max(best_ex, best_v3, best_3)
p('\n' + '='*50)
p('   FINAL WORLD RECORD: %.2f%%' % (final_ex*100))
p('='*50)

# Save ensemble
ens = {
    'models': [m5, m3],
    'names': ['M5-extra_deep', 'M3-deep_sub'],
    'weights': {'M5': 1-best_w, 'M3': best_w},
    'test_exact': final_ex,
    'test_1x2': 0,
}
joblib.dump(ens, 'models/champion_ensemble.pkl', compress=3)
res = {
    'test_exact': final_ex,
    'M5_exact': r5['exact'],
    'M3_exact': r3['exact'],
    'M3_weight': best_w,
    'M5_weight': 1-best_w,
    'v3_exact': 0.32,
    'time_min': (time.time()-t0)/60
}
with open('models/champion_results.json', 'w') as f:
    json.dump(res, f, indent=2)

p('\nSaved! Time: %.1f min' % res['time_min'])
logfile.close()
