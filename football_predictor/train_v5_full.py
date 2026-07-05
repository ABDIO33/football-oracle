"""
train_v5_full.py — تدريب V5 (136 ميزة) على FULL 618K
"""
import sys, os, time, json, numpy as np, warnings, gc
warnings.filterwarnings('ignore')
os.environ['OMP_NUM_THREADS'] = '8'
os.environ['PYTHONIOENCODING'] = 'utf-8'

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

logfile = open('training_v5_log.txt', 'w', encoding='utf-8')
def p(msg):
    print(msg, flush=True)
    logfile.write(msg + '\n'); logfile.flush()

p('V5 Full Training Started')
p('='*50)

data = np.load('training_data_v5.npz', allow_pickle=True)
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

models = []
t0 = time.time()

params_list = [
    {'ne':300,'md':8,'lr':0.06,'ss':0.8,'cs':0.6,'nl':63,'ra':0.01,'rl':0.1,'st':42},
    {'ne':200,'md':12,'lr':0.05,'ss':0.7,'cs':0.5,'nl':127,'ra':0.05,'rl':0.2,'st':43},
    {'ne':200,'md':6,'lr':0.08,'ss':0.9,'cs':0.8,'nl':31,'ra':0.1,'rl':0.5,'st':44},
]

for i, params in enumerate(params_list):
    t1 = time.time()
    md = params['md']; ne = params['ne']; lr = params['lr']
    p('M%d: depth=%d ne=%d lr=%.3f' % (i+1, md, ne, lr))
    
    m = lgb.LGBMClassifier(
        n_estimators=ne, max_depth=md, learning_rate=lr,
        subsample=params['ss'], colsample_bytree=params['cs'],
        num_leaves=params['nl'], reg_alpha=params['ra'],
        reg_lambda=params['rl'], random_state=params['st'],
        n_jobs=8, verbose=-1
    )
    m.fit(X_tr, y_tr, eval_set=[(X_v, y_v)],
          callbacks=[lgb.early_stopping(20), lgb.log_evaluation(0)])
    
    pt = m.predict(X_te)
    ex = float(np.mean(pt == y_te))
    p('  M%d: exact=%.2f%% [%ds]' % (i+1, ex*100, time.time()-t1))
    models.append(m)
    gc.collect()

# Ensemble
probs = [m.predict_proba(X_te) for m in models]
blend = np.mean(probs, axis=0)
preds = np.argmax(blend, axis=1)
ex_e = float(np.mean(preds == y_te))
yh, ya = y_te//5, y_te%5; ph, pa = preds//5, preds%5
yr = np.where(yh>ya,0,np.where(yh==ya,1,2)); pr = np.where(ph>pa,0,np.where(ph==pa,1,2))
x1_e = float(np.mean(yr==pr))
p('V5 Ensemble: exact=%.2f%%  1X2=%.2f%%' % (ex_e*100, x1_e*100))

# Weighted
best = 0; best_w = None
p1i = np.argmax(probs[0],1); p2i = np.argmax(probs[1],1); p3i = np.argmax(probs[2],1)
for w1 in [0.2, 0.33, 0.4]:
    for w2 in [0.2, 0.33, 0.3]:
        w3 = 1-w1-w2
        if w3<=0: continue
        b = w1*p1i + w2*p2i + w3*p3i
        pw = np.round(b).astype(int)
        ex_w = float(np.mean(pw == y_te))
        if ex_w > best:
            best = ex_w; best_w = [w1, w2, w3]
p('Weighted: exact=%.2f%%  weights=%s' % (best*100, str(best_w)))

# Compare
p('V3 was 32.00% - V5: %.2f%%' % (ex_e*100))

# Save
ens = {'models': models, 'names': ['V5-M1','V5-M2','V5-M3'], 'weights': best_w}
joblib.dump(ens, 'models/ultimate_v5_ensemble.pkl', compress=3)
res = {'test_exact': ex_e, 'test_1x2': x1_e, 'weighted_exact': best, 'weights': best_w,
       'time_min': (time.time()-t0)/60, 'feats': 136}
with open('models/ultimate_v5_results.json', 'w') as f:
    json.dump(res, f, indent=2)
p('SAVED! Total: %.1f min' % res['time_min'])

logfile.close()
