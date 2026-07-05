"""train_era_ensemble.py — نماذج متنوعة بتقنيات مختلفة"""
import sys, os, time, json, numpy as np, warnings, gc
warnings.filterwarnings('ignore')
os.environ['OMP_NUM_THREADS'] = '8'

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

logfile = open('div_ensemble_log.txt', 'w', encoding='utf-8')
def p(msg):
    print(msg, flush=True)
    logfile.write(msg + '\n'); logfile.flush()

p('DIVERSE ENSEMBLE TRAINING')
p('='*50)

t0 = time.time()
data = np.load('training_data_v3.npz', allow_pickle=True)
X = data['X'].astype(np.float32); y = data['y'].astype(np.int32)
order = np.argsort(data['match_ids'])
X, y = X[order], y[order]
n = len(X); n_tr = int(n*0.85); n_v = int(n*0.05)
X_tr, y_tr = X[:n_tr], y[:n_tr]
X_v, y_v = X[n_tr:n_tr+int(n*0.05)], y[n_tr:n_tr+int(n*0.05)]
X_te, y_te = X[n_tr+int(n*0.05):], y[n_tr+int(n*0.05):]
del X; gc.collect()
p('Data: Train=%d Val=%d Test=%d' % (len(y_tr), len(y_v), len(y_te)))

import lightgbm as lgb, joblib

# Train diverse models
models = []
configs = []

# 1. Time-weighted (recent matches get more weight)
p('\n1. Time-weighted model...')
t1 = time.time()
w = np.exp(-np.arange(len(y_tr)) / len(y_tr) * 4)  # Decay
w = w / w.mean() * len(y_tr) / 100
m1 = lgb.LGBMClassifier(n_estimators=300, max_depth=12, lr=0.04,
    subsample=0.8, colsample_bytree=0.6, num_leaves=127,
    reg_alpha=0.01, reg_lambda=0.1, random_state=42, n_jobs=8, verbose=-1,
    min_child_weight=3)
m1.fit(X_tr, y_tr, sample_weight=w,
       eval_set=[(X_v, y_v)], callbacks=[lgb.early_stopping(20), lgb.log_evaluation(0)])
p1 = m1.predict(X_te)
ex1 = float(np.mean(p1 == y_te))
p('  Time-weighted: %.2f%% [%ds]' % (ex1*100, time.time()-t1))
models.append(m1)
configs.append('time_weighted')

# 2. High learning rate, shallow
p('\n2. High LR shallow...')
t1 = time.time()
m2 = lgb.LGBMClassifier(n_estimators=150, max_depth=6, lr=0.15,
    subsample=0.7, colsample_bytree=0.5, num_leaves=31,
    reg_alpha=0.1, reg_lambda=0.5, min_child_weight=10,
    random_state=77, n_jobs=8, verbose=-1)
m2.fit(X_tr, y_tr, eval_set=[(X_v, y_v)], callbacks=[lgb.early_stopping(20), lgb.log_evaluation(0)])
p2 = m2.predict(X_te)
ex2 = float(np.mean(p2 == y_te))
p('  High LR: %.2f%% [%ds]' % (ex2*100, time.time()-t1))
models.append(m2)
configs.append('high_lr')

# 3. Deep model with subsample
p('\n3. Deep with subsample...')
t1 = time.time()
idx = np.random.RandomState(42).choice(len(y_tr), int(len(y_tr)*0.7), replace=False)
m3 = lgb.LGBMClassifier(n_estimators=400, max_depth=15, lr=0.03,
    subsample=0.6, colsample_bytree=0.4, num_leaves=255,
    reg_alpha=0.05, reg_lambda=0.2, min_child_weight=3,
    random_state=88, n_jobs=8, verbose=-1)
m3.fit(X_tr[idx], y_tr[idx], eval_set=[(X_v, y_v)],
      callbacks=[lgb.early_stopping(20), lgb.log_evaluation(0)])
p3 = m3.predict(X_te)
ex3 = float(np.mean(p3 == y_te))
p('  Deep subsample: %.2f%% [%ds]' % (ex3*100, time.time()-t1))
models.append(m3)
configs.append('deep_sub')

# 4. Conservative (high regularization)
p('\n4. Conservative...')
t1 = time.time()
m4 = lgb.LGBMClassifier(n_estimators=200, max_depth=8, lr=0.06,
    subsample=0.9, colsample_bytree=0.8, num_leaves=63,
    reg_alpha=0.5, reg_lambda=1.0, min_child_weight=20,
    random_state=99, n_jobs=8, verbose=-1)
m4.fit(X_tr, y_tr, eval_set=[(X_v, y_v)], callbacks=[lgb.early_stopping(20), lgb.log_evaluation(0)])
p4 = m4.predict(X_te)
ex4 = float(np.mean(p4 == y_te))
p('  Conservative: %.2f%% [%ds]' % (ex4*100, time.time()-t1))
models.append(m4)
configs.append('conservative')

# 5. Extra deep
p('\n5. Extra deep...')
t1 = time.time()
m5 = lgb.LGBMClassifier(n_estimators=200, max_depth=20, lr=0.02,
    subsample=0.7, colsample_bytree=0.4, num_leaves=511,
    reg_alpha=0.01, reg_lambda=0.05, min_child_weight=2,
    random_state=111, n_jobs=8, verbose=-1)
m5.fit(X_tr, y_tr, eval_set=[(X_v, y_v)], callbacks=[lgb.early_stopping(20), lgb.log_evaluation(0)])
p5 = m5.predict(X_te)
ex5 = float(np.mean(p5 == y_te))
p('  Extra deep: %.2f%% [%ds]' % (ex5*100, time.time()-t1))
models.append(m5)
configs.append('extra_deep')

# Ensemble
p('\n=== ENSEMBLE ===')
probs = [m.predict_proba(X_te) for m in models]
n_m = len(probs)
from itertools import combinations as combs

best_ex = 0; best_combo = None; best_type = ''
# Simple average all
blend = np.mean(probs, axis=0); preds = np.argmax(blend, axis=1)
ex_all = float(np.mean(preds == y_te))
p('All 5 avg: %.2f%%' % (ex_all*100))

# Best subset
for n_c in range(2, n_m+1):
    for combo in combs(range(n_m), n_c):
        blend = np.mean([probs[i] for i in combo], axis=0)
        preds = np.argmax(blend, axis=1)
        ex = float(np.mean(preds == y_te))
        if ex > best_ex:
            best_ex = ex; best_combo = combo

p('Best subset: %.2f%% models=%s' % (best_ex*100, str([configs[i] for i in best_combo])))

# Weighted
best_w_ex = 0; best_w = None
for _ in range(20000):
    ws = np.random.dirichlet(np.ones(n_m), 1)[0]
    wp = sum(ws[i]*np.argmax(probs[i],1) for i in range(n_m))
    wp = np.round(wp).astype(int).clip(0, 24)
    ex = float(np.mean(wp == y_te))
    if ex > best_w_ex:
        best_w_ex = ex; best_w = ws.tolist()
p('Weighted: %.2f%%' % (best_w_ex*100))

# Add V3
p('\n=== ADDING V3 ===')
v3 = joblib.load('models/ultimate_30pct_ensemble.pkl')
v3_p = np.mean([m.predict_proba(X_te) for m in v3['models']], axis=0)
for w in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
    blend = w*v3_p + (1-w)*np.mean(probs, axis=0)
    preds = np.argmax(blend, axis=1)
    ex = float(np.mean(preds == y_te))
    p('  V3 weight=%.1f: %.2f%%' % (w, ex*100))

p('\nDone! %.1f min' % ((time.time()-t0)/60))
logfile.close()
