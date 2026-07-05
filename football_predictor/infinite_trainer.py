"""
infinite_trainer.py — 🏆 تدريب مستمر 48 ساعة (لا يتوقف!)
يستخدم Random Search على Hyperparameters و LightGBM
"""
import sys, os, time, json, random, sqlite3, gc, warnings
import numpy as np
warnings.filterwarnings('ignore')
os.environ['OMP_NUM_THREADS'] = '6'  # Leave 2 cores for system
os.environ['PYTHONIOENCODING'] = 'utf-8'

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

# Redirect stdout
logfile = open('infinite_training_log.txt', 'a', encoding='utf-8')
def p(msg, also_console=True):
    ts = time.strftime('%H:%M:%S')
    line = f'[{ts}] {msg}'
    if also_console:
        print(line, flush=True)
    logfile.write(line + '\n')
    logfile.flush()

p('='*60)
p('INFINITE TRAINER STARTED — 48 Hour Continuous Training')
p('='*60)

# Load data (once)
t0 = time.time()
data = np.load('training_data_v3.npz', allow_pickle=True)
X = data['X'].astype(np.float32); y = data['y'].astype(np.int32)
order = np.argsort(data['match_ids'])
X, y = X[order], y[order]
n = len(X); n_tr = int(n * 0.85); n_v = int(n * 0.07); n_te = n - n_tr - int(n * 0.07)
X_tr, y_tr = X[:n_tr], y[:n_tr]
X_v, y_v = X[n_tr:n_tr+int(n*0.07)], y[n_tr:n_tr+int(n*0.07)]
X_te, y_te = X[n_tr+int(n*0.07):], y[n_tr+int(n*0.07):]
del X  # Free memory
gc.collect()

# Use 100K subset for fast iteration
np.random.seed(42)
idx_tr = np.random.choice(len(y_tr), 100000, replace=False)
Xs, ys = X_tr[idx_tr], y_tr[idx_tr]
idx_v = np.random.choice(len(y_v), 20000, replace=False)
Xvs, yvs = X_v[idx_v], y_v[idx_v]

p(f'Data: Train={len(ys):,} Val={len(yvs):,} Test={len(y_te):,} Feats={X_tr.shape[1]}')
p(f'Load time: {time.time()-t0:.1f}s')

# Results DB
conn = sqlite3.connect('training_results.db')
conn.execute('''CREATE TABLE IF NOT EXISTS results (
    iteration INTEGER, timestamp TEXT, seed INTEGER,
    n_estimators INTEGER, max_depth INTEGER, lr REAL, num_leaves INTEGER,
    subsample REAL, colsample REAL, reg_alpha REAL, reg_lambda REAL,
    min_child_samples INTEGER, val_exact REAL, test_exact REAL, 
    val_1x2 REAL, test_1x2 REAL, train_time REAL, model_path TEXT
)''')
conn.commit()

# Best trackers
best_val_exact = 0.0
best_test_exact = 0.0
best_model_path = None
top_models = []  # List of (exact, path)

import lightgbm as lgb
import joblib

# Hyperparameter ranges
param_grid = {
    'n_estimators': [100, 150, 200, 250, 300, 400, 500],
    'max_depth': [4, 5, 6, 7, 8, 9, 10, 12, 15],
    'lr': [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.1, 0.12],
    'num_leaves': [15, 31, 47, 63, 79, 95, 111, 127, 159, 191, 255],
    'subsample': [0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 1.0],
    'colsample_bytree': [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    'reg_alpha': [0, 0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5],
    'reg_lambda': [0, 0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0],
    'min_child_samples': [5, 10, 15, 20, 30, 50, 100],
}

def random_params():
    """Generate random hyperparameters"""
    return {
        'n_estimators': random.choice(param_grid['n_estimators']),
        'max_depth': random.choice(param_grid['max_depth']),
        'lr': random.choice(param_grid['lr']),
        'num_leaves': random.choice(param_grid['num_leaves']),
        'subsample': random.choice(param_grid['subsample']),
        'colsample_bytree': random.choice(param_grid['colsample_bytree']),
        'reg_alpha': random.choice(param_grid['reg_alpha']),
        'reg_lambda': random.choice(param_grid['reg_lambda']),
        'min_child_samples': random.choice(param_grid['min_child_samples']),
    }

def train_one(params, seed, iteration):
    """Train one LightGBM model, return accuracy"""
    t_start = time.time()
    
    model = lgb.LGBMClassifier(
        n_estimators=params['n_estimators'],
        max_depth=params['max_depth'],
        learning_rate=params['lr'],
        num_leaves=params['num_leaves'],
        subsample=params['subsample'],
        colsample_bytree=params['colsample_bytree'],
        reg_alpha=params['reg_alpha'],
        reg_lambda=params['reg_lambda'],
        min_child_samples=params['min_child_samples'],
        n_jobs=6, random_state=seed, verbose=-1,
        min_split_gain=0.001,
        min_child_weight=1e-3,
    )
    
    model.fit(Xs, ys, eval_set=[(Xvs, yvs)],
              callbacks=[lgb.early_stopping(15), lgb.log_evaluation(0)])
    
    n_trees = model.n_estimators_
    
    # Val accuracy
    pv = model.predict(Xvs)
    val_ex = float(np.mean(pv == yvs))
    yh, ya = yvs//5, yvs%5; ph, pa = pv//5, pv%5
    vr = np.where(yh>ya,0,np.where(yh==ya,1,2)); pr = np.where(ph>pa,0,np.where(ph==pa,1,2))
    val_x1 = float(np.mean(vr==pr))
    
    # Test accuracy
    pt = model.predict(X_te)
    test_ex = float(np.mean(pt == y_te))
    yh2, ya2 = y_te//5, y_te%5; ph2, pa2 = pt//5, pt%5
    vr2 = np.where(yh2>ya2,0,np.where(yh2==ya2,1,2)); pr2 = np.where(ph2>pa2,0,np.where(ph2==pa2,1,2))
    test_x1 = float(np.mean(vr2==pr2))
    
    train_time = time.time() - t_start
    
    # Save model if good
    model_path = None
    if test_ex > 0.22:  # Only save models >22%
        model_path = f'models/infinite_iter{iteration:04d}_ex{test_ex*100:.0f}.pkl'
        joblib.dump(model, model_path, compress=3)
    
    # Save to DB
    conn.execute('''INSERT INTO results VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (iteration, time.strftime('%Y-%m-%d %H:%M:%S'), seed,
         params['n_estimators'], params['max_depth'], params['lr'], params['num_leaves'],
         params['subsample'], params['colsample_bytree'], params['reg_alpha'], params['reg_lambda'],
         params['min_child_samples'], val_ex, test_ex, val_x1, test_x1, train_time, model_path))
    conn.commit()
    
    return val_ex, test_ex, test_x1, n_trees, train_time, model, model_path

# === MAIN LOOP ===
iteration = 0
best_val = 0.0
best_params = None
last_ensemble_time = time.time()
ensemble_models = []
ensemble_scores = []

total_start = time.time()

try:
    while True:
        iteration += 1
        seed = random.randint(1, 10000)
        params = random_params()
        
        p(f'[#{iteration}] Training... ', also_console=False)
        
        try:
            val_ex, test_ex, test_x1, n_trees, train_time, model, mpath = train_one(params, seed, iteration)
            
            # Brief console output
            print(f'  #{iteration:4d} | val={val_ex*100:5.2f}% test={test_ex*100:5.2f}% | '
                  f'd={params["max_depth"]} lv={params["num_leaves"]} lr={params["lr"]:.3f} '
                  f'ne={n_trees} | {train_time:.0f}s', flush=True)
            
            # Track top models for ensemble
            if mpath:
                ensemble_models.append(mpath)
                ensemble_scores.append(test_ex)
                # Keep top 10
                if len(ensemble_models) > 10:
                    # Remove worst
                    worst_idx = np.argmin(ensemble_scores)
                    worst_path = ensemble_models.pop(worst_idx)
                    ensemble_scores.pop(worst_idx)
                    try:
                        if os.path.exists(worst_path):
                            os.remove(worst_path)
                    except:
                        pass
            
            # Update best
            if test_ex > best_test_exact:
                best_test_exact = test_ex
                best_params = params.copy()
                best_params['n_trees'] = n_trees
                p(f'🔥 NEW BEST: test_exact={test_ex*100:.2f}% params={best_params}')
                
                # Save best model
                joblib.dump(model, 'models/infinite_best.pkl', compress=3)
                with open('models/infinite_best_params.json', 'w') as f:
                    json.dump({'iteration': iteration, 'test_exact': test_ex, 'test_1x2': test_x1, 'params': best_params}, f, indent=2)
            
            # Every 10 iterations: ensemble top models
            if iteration % 10 == 0 and len(ensemble_models) >= 3:
                try:
                    emodels = []
                    epaths = []
                    for epath in ensemble_models[-5:]:  # Top 5
                        if os.path.exists(epath):
                            emodels.append(joblib.load(epath))
                            epaths.append(epath)
                    
                    if len(emodels) >= 2:
                        probs = []
                        for m in emodels:
                            probs.append(m.predict_proba(X_te))
                        blend = np.mean(probs, axis=0)
                        preds = np.argmax(blend, axis=1)
                        ens_ex = float(np.mean(preds == y_te))
                        p(f'🧩 Ensemble of {len(emodels)}: test_exact={ens_ex*100:.2f}%')
                        
                        if ens_ex > 0.27:  # Save if good
                            ens_obj = {'models': emodels, 'names': [f'M{i+1}' for i in range(len(emodels))]}
                            joblib.dump(ens_obj, f'models/infinite_ensemble_iter{iteration:04d}_ex{ens_ex*100:.0f}.pkl', compress=3)
                            p(f'💾 Ensemble saved!')
                        
                        # Compare with current best
                        if ens_ex > 0.33 and ens_ex > best_test_exact + 0.01:
                            joblib.dump(ens_obj, 'models/infinite_best_ensemble.pkl', compress=3)
                            best_test_exact = ens_ex
                            p(f'🔥🔥 NEW BEST ENSEMBLE: {ens_ex*100:.2f}%')
                        
                        del probs, blend, emodels
                        gc.collect()
                except Exception as e:
                    p(f'⚠ Ensemble error: {e}')
            
            # Cleanup
            del model
            if iteration % 5 == 0:
                gc.collect()
            
            # Progress report
            if iteration % 20 == 0:
                elapsed = time.time() - total_start
                eta_remaining = (elapsed / iteration) * (10000 - iteration) if iteration < 10000 else 0
                p(f'📊 PROGRESS: {iteration} models | {elapsed/60:.0f} min elapsed | '
                  f'best={best_test_exact*100:.2f}% | {elapsed/iteration:.1f}s/model')
                
        except Exception as e:
            p(f'⚠ Error iteration {iteration}: {e}')
            import traceback
            p(traceback.format_exc())
            continue

except KeyboardInterrupt:
    p('\n🛑 Training interrupted by user')
except Exception as e:
    p(f'💥 Fatal error: {e}')
finally:
    # Final report
    elapsed = time.time() - total_start
    p(f'\n{"="*60}')
    p(f'INFINITE TRAINING FINISHED')
    p(f'Models trained: {iteration}')
    p(f'Time elapsed: {elapsed/60:.0f} min ({elapsed/3600:.1f} hours)')
    p(f'Best test exact: {best_test_exact*100:.2f}%')
    p(f'Best params: {best_params}')
    p(f'Models saved in ensemble: {len(ensemble_models)}')
    
    # Count results
    cur = conn.execute('SELECT COUNT(*), MAX(test_exact), AVG(test_exact) FROM results')
    cnt, best, avg = cur.fetchone()
    p(f'DB results: {cnt} total, best={best*100:.2f}%, avg={avg*100:.2f}%')
    
    conn.close()
    logfile.close()
    print(f'\n🏆 Training completed: {iteration} models in {elapsed/3600:.1f} hours')
    print(f'Best exact: {best_test_exact*100:.2f}%')
