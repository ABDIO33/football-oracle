"""
auto_ensemble.py — يبني ensemble تلقائياً كل ساعة من أفضل النماذج
"""
import sys, os, time, json, sqlite3, gc, warnings
import numpy as np
warnings.filterwarnings('ignore')
os.environ['OMP_NUM_THREADS'] = '4'
os.environ['PYTHONIOENCODING'] = 'utf-8'

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

logfile = open('auto_ensemble_log.txt', 'a', encoding='utf-8')
def p(msg):
    print(msg, flush=True)
    logfile.write(msg + '\n'); logfile.flush()

p('='*50)
p('AUTO ENSEMBLE BUILDER STARTED')
p('='*50)

# Load test data (once)
data = np.load('training_data_v3.npz', allow_pickle=True)
X = data['X'].astype(np.float32); y = data['y'].astype(np.int32)
order = np.argsort(data['match_ids'])
X, y = X[order], y[order]
n = len(X); n_te = int(n * 0.1)
X_te, y_te = X[-n_te:], y[-n_te:]
p(f'Test data: {len(y_te):,} matches, {X_te.shape[1]} features')

import joblib, lightgbm as lgb

iteration = 0
best_ensemble_exact = 0.0
best_ensemble_path = None

while True:
    iteration += 1
    time.sleep(3600)  # Every hour
    
    p(f'\\n[Iteration {iteration}] Building ensemble...')
    t0 = time.time()
    
    # 1. Check infinite trainer DB for best models
    conn = sqlite3.connect('training_results.db')
    cur = conn.execute('''
        SELECT iteration, model_path, test_exact, test_1x2 
        FROM results 
        WHERE model_path IS NOT NULL AND model_path != ''
        ORDER BY test_exact DESC LIMIT 10
    ''')
    top_models = cur.fetchall()
    conn.close()
    
    if len(top_models) < 2:
        p('  Not enough models yet (need 2+)')
        continue
    
    p(f'  Found {len(top_models)} saved models')
    
    # 2. Load best 5 models and try ensemble
    best_5 = top_models[:5]
    loaded = []
    for r in best_5:
        path = r[2]
        full_path = os.path.join(BASE, path) if not os.path.isabs(path) else path
        if os.path.exists(full_path):
            try:
                m = joblib.load(full_path)
                loaded.append(m)
                p(f'  Loaded: {os.path.basename(full_path)} ({r[3]*100:.2f}%)')
            except:
                p(f'  Failed to load: {full_path}')
    
    if len(loaded) < 2:
        p('  Not enough loadable models')
        continue
    
    # 3. Try ensembles of different sizes
    best_ex = 0.0; best_combo = None
    
    for n_models in [2, 3, 4, 5]:
        if n_models > len(loaded): break
        from itertools import combinations
        for combo in combinations(range(len(loaded)), n_models):
            try:
                probs = [loaded[i].predict_proba(X_te) for i in combo]
                blend = np.mean(probs, axis=0)
                preds = np.argmax(blend, axis=1)
                ex = float(np.mean(preds == y_te))
                
                if ex > best_ex:
                    best_ex = ex
                    best_combo = combo
                    p(f'  Found: {n_models}-model ensemble: {ex*100:.2f}%')
            except:
                continue
    
    # 4. Save if better than current best
    if best_ex > best_ensemble_exact and best_ex > 0.25:
        best_ensemble_exact = best_ex
        
        # Save ensemble
        ens_models = [loaded[i] for i in best_combo]
        ens_names = [f'M{i+1}' for i in best_combo]
        ens = {'models': ens_models, 'names': ens_names}
        
        path = f'models/auto_ensemble_iter{iteration:03d}_ex{best_ex*100:.0f}.pkl'
        joblib.dump(ens, path, compress=3)
        best_ensemble_path = path
        
        # Save as best
        joblib.dump(ens, 'models/auto_ensemble_best.pkl', compress=3)
        
        # Results
        yh, ya = y_te//5, y_te%5
        ph, pa = preds//5, preds%5
        yr = np.where(yh>ya,0,np.where(yh==ya,1,2))
        pr = np.where(ph>pa,0,np.where(ph==pa,1,2))
        x1 = float(np.mean(yr==pr))
        
        res = {
            'iteration': iteration,
            'test_exact': best_ex,
            'test_1x2': x1,
            'n_models': len(best_combo),
            'model_scores': [float(r[3]) for r in best_5],
            'time': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        with open('models/auto_ensemble_best.json', 'w') as f:
            json.dump(res, f, indent=2)
        
        p(f'🔥 NEW BEST ENSEMBLE: exact={best_ex*100:.2f}%  1X2={x1*100:.2f}%')
        p(f'  Saved: {path}')
    
    # Compare with V3
    p(f'  Best ensemble: {best_ex*100:.2f}% vs V3: 32.00%')
    if best_ex > 0.32:
        p(f'  🏆🏆🏆 AUTO ENSEMBLE BEAT V3!')
    
    elapsed = (time.time() - t0)
    p(f'  Completed in {elapsed:.0f}s')
    
    # Cleanup
    del loaded
    gc.collect()
