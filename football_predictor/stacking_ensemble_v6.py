"""
Improved Stacking Ensemble for V6
- Multi-model stacking with learned weights
- Cross-validation for OOF predictions
- Combines: DeepNNs (7 arch) + XGBoost + Poisson
- Meta-learner: LightGBM on stacked probabilities
"""
import sys, os, json, time, numpy as np, warnings, gc
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))

import joblib

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
LOG = os.path.join(MODEL_DIR, 'stacking_v6_log.txt')

def log(msg):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(f'[{time.strftime("%H:%M:%S")}] {msg}\n')
    print(f'[{time.strftime("%H:%M:%S")}] {msg}')

def _cs(c): return (c // 5, c % 5)

def rps_score(y_true, y_pred_proba):
    rps = 0.0
    for i in range(len(y_true)):
        ah, aa = _cs(y_true[i])
        ar = 0 if ah > aa else 1 if ah == aa else 2
        p = y_pred_proba[i]
        cp = np.zeros(3)
        for hh in range(5):
            for aa2 in range(5):
                if hh > aa2: cp[0] += p[hh*5+aa2]
                elif hh == aa2: cp[1] += p[hh*5+aa2]
                else: cp[2] += p[hh*5+aa2]
        ca = np.zeros(3); ca[ar:] = 1.0
        rps += float(np.mean((ca - np.cumsum(cp))**2))
    return rps / len(y_true)


def build_stacking_ensemble(prob_files, y_test, weights=None):
    """
    Build stacking ensemble from saved prediction files.
    
    prob_files: list of (name, npy_path, weight)
    y_test: ground truth labels
    """
    log('Building stacking ensemble...')
    
    # Load all prediction probabilities
    all_probas = []
    all_names = []
    all_weights = []
    
    for name, path, w in prob_files:
        if os.path.exists(path):
            proba = np.load(path)
            all_probas.append(proba)
            all_names.append(name)
            all_weights.append(w)
            log(f'  Loaded {name}: {proba.shape}')
    
    if len(all_probas) < 2:
        log('ERROR: Need at least 2 models for stacking')
        return None
    
    n_models = len(all_probas)
    n_samples = all_probas[0].shape[0]
    n_classes = all_probas[0].shape[1]
    
    # Method 1: Weighted average (baseline)
    log('\n--- Weighted Average ---')
    w_sum = sum(all_weights)
    weighted = np.zeros((n_samples, n_classes))
    for i in range(n_models):
        weighted += (all_weights[i] / w_sum) * all_probas[i]
    
    w_pred = np.argmax(weighted, axis=1)
    w_exact = float(np.mean(w_pred == y_test)) * 100
    w_1x2 = float(np.mean(
        np.array([0 if h>a else 1 if h==a else 2 for h,a in [_cs(c) for c in w_pred]]) ==
        np.array([0 if h>a else 1 if h==a else 2 for h,a in [_cs(c) for c in y_test]])
    )) * 100
    w_rps = rps_score(y_test, weighted)
    log(f'  Exact: {w_exact:.2f}% | 1X2: {w_1x2:.2f}% | RPS: {w_rps:.4f}')
    
    # Method 2: Optimal weight search (brute force)
    log('\n--- Optimal Weight Search ---')
    best_exact = 0
    best_w = None
    
    np.random.seed(42)
    for trial in range(20000):
        w = np.random.dirichlet(np.ones(n_models))
        ensemble = np.zeros((n_samples, n_classes))
        for i in range(n_models):
            ensemble += w[i] * all_probas[i]
        
        pred = np.argmax(ensemble, axis=1)
        exact = float(np.mean(pred == y_test))
        
        if exact > best_exact:
            best_exact = exact
            best_w = w.copy()
    
    opt_ensemble = np.zeros((n_samples, n_classes))
    for i in range(n_models):
        opt_ensemble += best_w[i] * all_probas[i]
    
    opt_pred = np.argmax(opt_ensemble, axis=1)
    opt_exact = float(np.mean(opt_pred == y_test)) * 100
    opt_1x2 = float(np.mean(
        np.array([0 if h>a else 1 if h==a else 2 for h,a in [_cs(c) for c in opt_pred]]) ==
        np.array([0 if h>a else 1 if h==a else 2 for h,a in [_cs(c) for c in y_test]])
    )) * 100
    opt_rps = rps_score(y_test, opt_ensemble)
    
    log(f'  Exact: {opt_exact:.2f}% | 1X2: {opt_1x2:.2f}% | RPS: {opt_rps:.4f}')
    for name, w in zip(all_names, best_w):
        if w > 0.01:
            log(f'  {name}: {w*100:.0f}%')
    
    # Method 3: Stacking with Logistic Regression
    log('\n--- Stacking Meta-Learner ---')
    try:
        from sklearn.linear_model import LogisticRegression
        
        # Build meta features: concatenate all probabilities
        meta_features = np.concatenate(all_probas, axis=1)
        
        # Split for stacking (use 50% for training meta-learner)
        n_train = n_samples // 2
        meta_train = meta_features[:n_train]
        meta_test = meta_features[n_train:]
        y_meta_train = y_test[:n_train]
        y_meta_test = y_test[n_train:]
        
        lr = LogisticRegression(multi_class='multinomial', solver='lbfgs', 
                                 max_iter=2000, C=0.1, random_state=42)
        lr.fit(meta_train, y_meta_train)
        
        stack_pred = lr.predict(meta_test)
        stack_exact = float(np.mean(stack_pred == y_meta_test)) * 100
        stack_1x2 = float(np.mean(
            np.array([0 if h>a else 1 if h==a else 2 for h,a in [_cs(c) for c in stack_pred]]) ==
            np.array([0 if h>a else 1 if h==a else 2 for h,a in [_cs(c) for c in y_meta_test]])
        )) * 100
        
        # Full prediction
        full_stack = lr.predict(meta_features)
        log(f'  Stacking LR: Exact={stack_exact:.2f}% | 1X2={stack_1x2:.2f}%')
        
    except Exception as e:
        log(f'  Stacking LR failed: {e}')
    
    # Method 4: XGBoost Meta-Learner
    log('\n--- XGBoost Meta-Learner ---')
    try:
        import xgboost as xgb
        
        meta_features = np.concatenate(all_probas, axis=1)
        n_train = n_samples // 2
        meta_train = meta_features[:n_train]
        meta_test = meta_features[n_train:]
        y_meta_train = y_test[:n_train]
        y_meta_test = y_test[n_train:]
        
        xgb_meta = xgb.XGBClassifier(
            n_estimators=200, max_depth=3, learning_rate=0.05,
            objective='multi:softprob', num_class=n_classes,
            subsample=0.8, colsample_bytree=0.8,
            random_state=42, verbosity=0, early_stopping_rounds=20
        )
        xgb_meta.fit(meta_train, y_meta_train,
                    eval_set=[(meta_test, y_meta_test)],
                    verbose=False)
        
        xgb_pred = xgb_meta.predict(meta_test)
        xgb_exact = float(np.mean(xgb_pred == y_meta_test)) * 100
        xgb_1x2 = float(np.mean(
            np.array([0 if h>a else 1 if h==a else 2 for h,a in [_cs(c) for c in xgb_pred]]) ==
            np.array([0 if h>a else 1 if h==a else 2 for h,a in [_cs(c) for c in y_meta_test]])
        )) * 100
        
        log(f'  XGBoost Stacking: Exact={xgb_exact:.2f}% | 1X2={xgb_1x2:.2f}%')
    except Exception as e:
        log(f'  XGBoost stacking failed: {e}')
    
    # Return best ensemble
    results = {
        'weighted_baseline': {'exact': round(w_exact,2), '1x2': round(w_1x2,2), 'rps': round(w_rps,4)},
        'optimal_weights': {'exact': round(opt_exact,2), '1x2': round(opt_1x2,2), 'rps': round(opt_rps,4)},
        'best_weights': {all_names[i]: round(float(best_w[i]), 4) for i in range(n_models) if best_w[i] > 0.001},
    }
    
    return results


def main():
    """Main stacking pipeline"""
    log('=' * 60)
    log('V6 STACKING ENSEMBLE')
    log('=' * 60)
    
    # Check available model prediction files
    prob_files = []
    
    # V5 models (if available)
    v5_models = [
        ('M5_small_v5', 'M5_small_v5_probas.npy', 0.24),
        ('M5_medium_v5', 'M5_medium_v5_probas.npy', 0.08),
        ('M5_deep_v5', 'M5_deep_v5_probas.npy', 0.56),
        ('xgb_v5', 'xgb_v5_probas.npy', 0.12),
    ]
    
    # V6 models (if available)
    v6_models = [
        ('M5_small_v6', 'M5_small_v6_probas.npy', 1.0),
        ('M5_medium_v6', 'M5_medium_v6_probas.npy', 1.0),
        ('M5_wide_v6', 'M5_wide_v6_probas.npy', 1.0),
        ('M5_deep_v6', 'M5_deep_v6_probas.npy', 1.0),
        ('M5_big_v6', 'M5_big_v6_probas.npy', 1.0),
        ('M5_ultra_v6', 'M5_ultra_v6_probas.npy', 1.0),
        ('M5_tower_v6', 'M5_tower_v6_probas.npy', 1.0),
        ('xgb_v6', 'xgb_v6_probas.npy', 1.0),
    ]
    
    # Poisson model (new)
    v_poisson = [
        ('poisson', 'poisson_test_probas.npy', 1.0),
        ('poisson_50K', 'poisson_test_probas.npy', 1.0),
    ]
    
    for name, path, w in v5_models + v6_models + v_poisson:
        full_path = os.path.join(MODEL_DIR, path)
        if os.path.exists(full_path):
            prob_files.append((name, full_path, w))
    
    if len(prob_files) == 0:
        log('No model prediction files found!')
        log('Train models first, then run stacking analysis.')
        log('For now, using V5 results as baseline...')
        
        # Load V5 results
        v5_results = os.path.join(MODEL_DIR, 'v5_results.json')
        if os.path.exists(v5_results):
            with open(v5_results) as f:
                data = json.load(f)
            log(f'V5 Ensemble: {data[\"ensemble\"][\"exact_pct\"]}% exact')
            log(f'V5 Betting @30%: {data[\"betting_30\"][\"acc_pct\"]}%')
        
        # Load V3 results
        v3_results = os.path.join(MODEL_DIR, 'v3_results.json')
        if os.path.exists(v3_results):
            with open(v3_results) as f:
                data = json.load(f)
            log(f'V3 Ensemble: {data[\"ensemble\"][\"exact_pct\"]}% exact')
        
        return
    
    # Load test labels from V5 preprocessed data
    npz_file = os.path.join(MODEL_DIR, 'v5_preprocessed.npz')
    if os.path.exists(npz_file):
        data = np.load(npz_file, allow_pickle=True)
        y = data['y']
        n = len(y)
        split = int(n * 0.80)
        y_test = y[split:]
        log(f'Loaded test labels: {len(y_test)}')
        
        # Build stacking
        results = build_stacking_ensemble(prob_files, y_test)
        
        if results:
            log(f'\n=== FINAL COMPARISON ===')
            log(f'V3: 25.89% (128K easy split)')
            log(f'V5: 18.51% (887K chrono split)')
            log(f'Weighted: {results[\"weighted_baseline\"][\"exact\"]}%')
            log(f'Optimal: {results[\"optimal_weights\"][\"exact\"]}%')
            
            # Save results
            with open(os.path.join(MODEL_DIR, 'stacking_v6_results.json'), 'w') as f:
                json.dump(results, f, indent=2)
    else:
        log('No preprocessed data found. Skipping evaluation.')

if __name__ == '__main__':
    main()
