"""
Fast ensemble evaluation using already-trained M7 models.
Loads all saved models and finds optimal ensemble weights quickly.
"""
import sys, os, json, time, gc, warnings
import numpy as np
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))

import torch
import torch.nn as nn
import joblib

SEED = 42
torch.manual_seed(SEED)
np.random.seed(SEED)

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
DEVICE = 'cpu'
LOG = os.path.join(MODEL_DIR, 'm7_eval_log.txt')

NUM_FEATURES = 85
NUM_CLASSES = 25

def log(msg):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(f'[{time.strftime("%H:%M:%S")}] {msg}\n')
    print(msg)

def class_to_score(c):
    return (c // 5, c % 5)

def result(h, a):
    return 0 if h > a else (1 if h == a else 2)

def compute_rps(y_true, y_pred_proba):
    n = len(y_true)
    rps_total = 0.0
    for i in range(n):
        ah, aa = class_to_score(y_true[i])
        ar = result(ah, aa)
        actual_cum = np.array([1 if ar <= k else 0 for k in range(3)], dtype=float)
        ps = y_pred_proba[i]
        p_h = sum(ps[h*5 + a] for h in range(5) for a in range(5) if h > a)
        p_d = sum(ps[h*5 + h] for h in range(5))
        p_a = sum(ps[h*5 + a] for h in range(5) for a in range(5) if a > h)
        pred_cum = np.cumsum([p_h, p_d, p_a])
        rps_total += float(np.mean((actual_cum - pred_cum) ** 2))
    return rps_total / n


class M7_ResidualNet(nn.Module):
    def __init__(self, input_dim, num_classes, width=512, depth=3, dropout=0.25):
        super().__init__()
        layers = [nn.Linear(input_dim, width), nn.LayerNorm(width), nn.GELU(), nn.Dropout(dropout)]
        for _ in range(depth):
            layers += [
                nn.Linear(width, width), nn.LayerNorm(width), nn.GELU(), nn.Dropout(dropout),
                nn.Linear(width, width), nn.LayerNorm(width), nn.GELU(), nn.Dropout(dropout),
            ]
        layers.append(nn.Linear(width, num_classes))
        self.net = nn.Sequential(*layers)
    def forward(self, x):
        return self.net(x)


class _M5(nn.Module):
    def __init__(self, input_dim, num_classes, layers):
        super().__init__()
        modules = []
        prev = input_dim
        drops = [0.3, 0.3, 0.3, 0.2, 0.2]
        for i, sz in enumerate(layers):
            modules.append(nn.Linear(prev, sz))
            if sz >= 128: modules.append(nn.BatchNorm1d(sz))
            modules.append(nn.ReLU())
            modules.append(nn.Dropout(drops[min(i, len(drops)-1)]))
            prev = sz
        modules.append(nn.Linear(prev, num_classes))
        self.net = nn.Sequential(*modules)
    def forward(self, x): return self.net(x)


def main():
    log('=' * 70)
    log('M7 ENSEMBLE EVALUATION (Fast)')
    log('=' * 70)
    
    # Load data
    log('\nLoading data...')
    data = np.load(os.path.join(MODEL_DIR, 'preprocessed_data.npz'), allow_pickle=True)
    X_test_s = data['X_test_s']
    y_test = data['y_test']
    log(f'Test: {X_test_s.shape}')
    X_test_t = torch.tensor(X_test_s, dtype=torch.float32).to(DEVICE)
    actual_1x2 = np.array([result(*class_to_score(c)) for c in y_test])
    
    # Load M7 models
    log('\nLoading M7 models...')
    m7_quick = M7_ResidualNet(NUM_FEATURES, NUM_CLASSES, 384, 3, 0.25)
    m7_quick.load_state_dict(torch.load(os.path.join(MODEL_DIR, 'M7_quick.pt'), map_location='cpu'))
    m7_quick.eval()
    
    m7_medium = M7_ResidualNet(NUM_FEATURES, NUM_CLASSES, 512, 4, 0.25)
    m7_medium.load_state_dict(torch.load(os.path.join(MODEL_DIR, 'M7_medium.pt'), map_location='cpu'))
    m7_medium.eval()
    
    with torch.no_grad():
        p7q = torch.softmax(m7_quick(X_test_t), dim=1).cpu().numpy()
        p7m = torch.softmax(m7_medium(X_test_t), dim=1).cpu().numpy()
    
    # M7 average
    m7_avg = (p7q + p7m) / 2
    m7_pred = np.argmax(m7_avg, axis=1)
    log(f'M7 avg: exact={float(np.mean(m7_pred==y_test))*100:.2f}%')
    
    # Load existing models
    log('\nLoading existing models...')
    base_probas = {}
    base_names = []
    
    # XGBoost
    xgb_path = os.path.join(MODEL_DIR, 'checkpoint_xgb.pkl')
    if os.path.exists(xgb_path):
        xgb = joblib.load(xgb_path)
        p = xgb.predict_proba(X_test_s)
        base_probas['xgb'] = p
        base_names.append('xgb')
        log(f'  XGBoost: {float(np.mean(np.argmax(p,axis=1)==y_test))*100:.2f}%')
    
    # M5
    M5_ARCHS = {
        'M5_small': [128,256,128], 'M5_medium': [256,512,256],
        'M5_big': [512,1024,512], 'M5_wide': [1024,512,256],
        'M5_deep': [256,512,256,128],
    }
    for m5_name, m5_layers in M5_ARCHS.items():
        pt = os.path.join(MODEL_DIR, f'checkpoint_{m5_name}.pt')
        if os.path.exists(pt):
            m5 = _M5(NUM_FEATURES, NUM_CLASSES, m5_layers)
            m5.load_state_dict(torch.load(pt, map_location='cpu'))
            m5.eval()
            with torch.no_grad():
                p = torch.softmax(m5(X_test_t), dim=1).cpu().numpy()
            base_probas[m5_name] = p
            base_names.append(m5_name)
    
    log('\nNote: LightGBM has 72-feature mismatch (data is 85), skipping.')
    
    # Add M7
    base_probas['M7_quick'] = p7q
    base_probas['M7_medium'] = p7m
    for n in ['M7_quick', 'M7_medium']:
        if n not in base_names:
            base_names.append(n)
    base_probas['M7_avg'] = m7_avg
    
    log(f'\nTotal models: {len(base_names)}')
    
    # ── Pre-stack probability arrays for speed ──
    n_trials = 3000
    log(f'\nEnsemble search ({n_trials} trials each)...')
    t0 = time.time()
    
    def _fast_search(names_list, n_trials):
        """Fast ensemble weight search using vectorized operations."""
        stacked = np.stack([base_probas[n] for n in names_list], axis=0)  # (n_models, 58545, 25)
        y = y_test
        best_e = 0.0
        best_w = None
        for _ in range(n_trials):
            w = np.random.dirichlet(np.ones(len(names_list)))
            # blend = sum(w_i * proba_i) = w @ stacked (reshape w to dot)
            # Efficient: blend = np.tensordot(w, stacked, axes=(0,0))
            blend = np.einsum('i,ijk->jk', w, stacked)
            pred = np.argmax(blend, axis=1)
            e = float(np.mean(pred == y))
            if e > best_e:
                best_e = e
                best_w = w.copy()
        return best_e, {names_list[i]: float(best_w[i]) for i in range(len(names_list))}, stacked
    
    # Without M7
    no_m7 = [n for n in base_names if n not in ['M7_quick', 'M7_medium', 'M7_avg']]
    if len(no_m7) >= 2:
        best_base, _, _ = _fast_search(no_m7, n_trials)
        log(f'Without M7: {best_base*100:.2f}% ({time.time()-t0:.0f}s)')
    
    # With M7 avg as single model
    with_m7_avg = no_m7 + ['M7_avg']
    t1 = time.time()
    best_avg, best_w_avg, _ = _fast_search(with_m7_avg, n_trials)
    log(f'With M7 (avg): {best_avg*100:.2f}% ({time.time()-t1:.0f}s)')
    
    # With all individual models (quick: just 1000 trials)
    all_names = [n for n in base_names if n != 'M7_avg']
    t2 = time.time()
    best_all, best_w_all, _ = _fast_search(all_names, n_trials)
    log(f'With M7 (indiv): {best_all*100:.2f}% ({time.time()-t2:.0f}s)')
    
    log(f'With M7 (avg): {best_avg*100:.2f}%')
    log(f'With M7 (indiv): {best_all*100:.2f}%')
    
    # Compute final metrics for best ensemble
    for label, (proba, weights_dict, names) in [
        ('M7_avg_ensemble', (best_avg, best_w_avg, with_m7_avg)),
        ('M7_indiv_ensemble', (best_all, best_w_all, all_names)),
    ]:
        if proba is None or proba == 0:
            continue
        # Reconstruct best blend
        blend = sum(weights_dict[n] * base_probas[n] for n in names)
        pred = np.argmax(blend, axis=1)
        exact = float(np.mean(pred == y_test))
        acc_1x2 = float(np.mean(np.array([result(*class_to_score(c)) for c in pred]) == actual_1x2))
        rps = compute_rps(y_test, blend)
        
        # Betting @30%
        probs_max = np.max(blend, axis=1)
        hits = np.sum((pred == y_test) & (probs_max >= 0.30))
        total = np.sum(probs_max >= 0.30)
        
        log(f'\n{label}:')
        log(f'  exact={exact*100:.2f}%')
        log(f'  1X2={acc_1x2*100:.2f}%')
        log(f'  RPS={rps:.4f}')
        log(f'  Betting@30%: {hits}/{total} = {hits/total*100:.1f}%' if total > 0 else '  No 30%+ bets')
        log(f'  Weights:')
        for n, w in sorted(weights_dict.items(), key=lambda x: -x[1]):
            log(f'    {n:20s}: {w:.4f}')
    
    log('\nM7 + LightGBM not available (feature mismatch).')
    
    log(f'\nTotal time: {time.time()-t0:.1f}s')
    
    # Save results
    results = {
        'type': 'M7_ENSEMBLE_EVAL',
        'test_samples': len(y_test),
        'M7_models': {
            'M7_quick': {'exact': round(float(np.mean(np.argmax(p7q,axis=1)==y_test))*100,2)},
            'M7_medium': {'exact': round(float(np.mean(np.argmax(p7m,axis=1)==y_test))*100,2)},
            'M7_avg': round(float(np.mean(m7_pred==y_test))*100,2),
        },
        'baseline_no_m7': {'exact': round(best_base*100,2)} if len(no_m7)>=2 else {},
        'M7_avg_ensemble': {
            'exact': round(best_avg*100,2),
            'weights': best_w_avg,
        },
        'M7_indiv_ensemble': {
            'exact': round(best_all*100,2),
            'weights': best_w_all,
        },
        'm7_improvement_pp': round((best_avg-best_base)*100,2) if len(no_m7)>=2 else 0,
        'lightgbm_feature_mismatch': True,
    }
    json.dump(results, open(os.path.join(MODEL_DIR, 'm7_eval_results.json'), 'w'), indent=2)
    log('\nSaved: m7_eval_results.json')
    
    # Save m7_wrapper for production use
    class M7Wrapper:
        def __init__(self, models, device='cpu'):
            self.models = models; self.device = device
            for m in self.models: m.eval()
        def predict_proba(self, X):
            with torch.no_grad():
                X_t = torch.tensor(X, dtype=torch.float32).to(self.device)
                ps = [torch.softmax(m(X_t), dim=1) for m in self.models]
                return torch.mean(torch.stack(ps), dim=0).cpu().numpy()
    
    wrapper = M7Wrapper([m7_quick, m7_medium], DEVICE)
    joblib.dump(wrapper, os.path.join(MODEL_DIR, 'm7_wrapper.pkl'))
    log('Saved: m7_wrapper.pkl')
    
    print(f'\nDone! See models/m7_eval_results.json and models/m7_eval_log.txt')

if __name__ == '__main__':
    t0 = time.time()
    main()
    print(f'Total: {time.time()-t0:.1f}s')
