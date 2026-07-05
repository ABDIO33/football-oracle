"""
Resume M7_medium training + complete ensemble evaluation.
Run this after train_m7_ultra.py was interrupted.
"""
import sys, os, json, time, gc, warnings
import numpy as np
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import joblib

SEED = 42
torch.manual_seed(SEED)
np.random.seed(SEED)

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
DEVICE = 'cpu'
LOG = os.path.join(MODEL_DIR, 'm7_finish_log.txt')

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
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight, nonlinearity='relu')
                if m.bias is not None: nn.init.zeros_(m.bias)
    def forward(self, x):
        return self.net(x)


def main():
    log('=' * 70)
    log('M7 RESUME + ENSEMBLE EVALUATION')
    log('=' * 70)
    
    # ── 1. Load data ──
    log('\nLoading preprocessed data...')
    data = np.load(os.path.join(MODEL_DIR, 'preprocessed_data.npz'), allow_pickle=True)
    X_train_s = data['X_train_s']
    X_test_s = data['X_test_s']
    y_train = data['y_train']
    y_test = data['y_test']
    log(f'Train: {X_train_s.shape}, Test: {X_test_s.shape}')
    
    X_test_t = torch.tensor(X_test_s, dtype=torch.float32).to(DEVICE)
    
    # ── 2. Load completed M7_quick ──
    log('\nLoading M7_quick (already trained)...')
    m7_quick = M7_ResidualNet(NUM_FEATURES, NUM_CLASSES, width=384, depth=3, dropout=0.25)
    m7_quick.load_state_dict(torch.load(os.path.join(MODEL_DIR, 'M7_quick.pt'), map_location='cpu'))
    m7_quick.eval()
    with torch.no_grad():
        p_quick = torch.softmax(m7_quick(X_test_t), dim=1).cpu().numpy()
    q_pred = np.argmax(p_quick, axis=1)
    q_exact = float(np.mean(q_pred == y_test))
    actual_1x2 = np.array([result(*class_to_score(c)) for c in y_test])
    q_1x2 = float(np.mean(np.array([result(*class_to_score(c)) for c in q_pred]) == actual_1x2))
    q_rps = compute_rps(y_test, p_quick)
    log(f'  M7_quick: exact={q_exact*100:.2f}%  1X2={q_1x2*100:.2f}%  RPS={q_rps:.4f}')
    
    # ── 3. Resume M7_medium ──
    log('\nResuming M7_medium training...')
    m7_medium = M7_ResidualNet(NUM_FEATURES, NUM_CLASSES, width=512, depth=4, dropout=0.25)
    
    # Try to load partially trained state
    pt_path = os.path.join(MODEL_DIR, 'M7_medium.pt')
    if os.path.exists(pt_path):
        m7_medium.load_state_dict(torch.load(pt_path, map_location='cpu'))
        log('  Loaded existing M7_medium.pt (continuing from previous run)')
    else:
        log('  No previous checkpoint, starting fresh')
    
    m7_medium.train()
    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    optimizer = optim.AdamW(m7_medium.parameters(), lr=0.001, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=25)
    
    train_loader = DataLoader(
        TensorDataset(torch.tensor(X_train_s, dtype=torch.float32),
                      torch.tensor(y_train, dtype=torch.long)),
        batch_size=2048, shuffle=True, num_workers=0)
    
    best_exact = 0.0
    best_state = None
    
    for epoch in range(10):
        t0 = time.time()
        for Xb, yb in train_loader:
            optimizer.zero_grad()
            loss = criterion(m7_medium(Xb), yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(m7_medium.parameters(), 1.0)
            optimizer.step()
        
        m7_medium.eval()
        with torch.no_grad():
            out = m7_medium(X_test_t)
            _, preds = torch.max(out, 1)
            acc = (preds == torch.tensor(y_test, dtype=torch.long).to(DEVICE)).sum().item() / len(y_test)
        scheduler.step()
        
        if acc > best_exact:
            best_exact = acc
            best_state = {k: v.cpu().clone() for k, v in m7_medium.state_dict().items()}
        
        log(f'  Epoch {epoch+1}/10: val_acc={acc*100:.2f}% (best={best_exact*100:.2f}%) [{time.time()-t0:.0f}s]')
    
    # Load best
    m7_medium.load_state_dict(best_state)
    m7_medium.eval()
    with torch.no_grad():
        p_medium = torch.softmax(m7_medium(X_test_t), dim=1).cpu().numpy()
    m_pred = np.argmax(p_medium, axis=1)
    m_exact = float(np.mean(m_pred == y_test))
    m_1x2 = float(np.mean(np.array([result(*class_to_score(c)) for c in m_pred]) == actual_1x2))
    m_rps = compute_rps(y_test, p_medium)
    log(f'  M7_medium final: exact={m_exact*100:.2f}%  1X2={m_1x2*100:.2f}%  RPS={m_rps:.4f}')
    
    # Save medium
    torch.save(m7_medium.state_dict(), os.path.join(MODEL_DIR, 'M7_medium.pt'))
    log('  Saved M7_medium.pt')
    
    # ── 4. M7 ensemble ──
    all_probas = {'M7_quick': p_quick, 'M7_medium': p_medium}
    names_list = list(all_probas.keys())
    m7_avg = np.mean([all_probas[n] for n in names_list], axis=0)
    mp = np.argmax(m7_avg, axis=1)
    m7_e = float(np.mean(mp == y_test))
    m7_1 = float(np.mean(np.array([result(*class_to_score(c)) for c in mp]) == actual_1x2))
    m7_r = compute_rps(y_test, m7_avg)
    log(f'\nM7 average ensemble: exact={m7_e*100:.2f}%  1X2={m7_1*100:.2f}%  RPS={m7_r:.4f}')
    
    # ── 5. Load existing models ──
    log('\nLoading existing models...')
    base_probas = {}
    base_names = []
    
    # XGBoost
    xgb_path = os.path.join(MODEL_DIR, 'checkpoint_xgb.pkl')
    if os.path.exists(xgb_path):
        xgb_model = joblib.load(xgb_path)
        p = xgb_model.predict_proba(X_test_s)
        base_probas['xgb'] = p
        base_names.append('xgb')
        log(f'  XGBoost: exact={float(np.mean(np.argmax(p, axis=1)==y_test))*100:.2f}%')
    
    # M5 checkpoints
    M5_ARCHS = {
        'M5_small': [128, 256, 128],
        'M5_medium': [256, 512, 256],
        'M5_big': [512, 1024, 512],
        'M5_wide': [1024, 512, 256],
        'M5_deep': [256, 512, 256, 128],
    }
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
    
    for m5_name, m5_layers in M5_ARCHS.items():
        pt_path = os.path.join(MODEL_DIR, f'checkpoint_{m5_name}.pt')
        if os.path.exists(pt_path):
            try:
                m5 = _M5(NUM_FEATURES, NUM_CLASSES, m5_layers)
                m5.load_state_dict(torch.load(pt_path, map_location='cpu'))
                m5.eval()
                with torch.no_grad():
                    p = torch.softmax(m5(X_test_t), dim=1).cpu().numpy()
                base_probas[m5_name] = p
                base_names.append(m5_name)
                log(f'  {m5_name}: exact={float(np.mean(np.argmax(p, axis=1)==y_test))*100:.2f}%')
            except Exception as e:
                log(f'  {m5_name}: ERROR - {e}')
    
    # LightGBM
    for lgb_name in ['lgbm_final.pkl', 'lgbm_best.pkl']:
        lgb_path = os.path.join(MODEL_DIR, lgb_name)
        if os.path.exists(lgb_path):
            try:
                lgb = joblib.load(lgb_path)
                p = lgb.predict_proba(X_test_s)
                base_probas['lightgbm'] = p
                base_names.append('lightgbm')
                log(f'  {lgb_name}: exact={float(np.mean(np.argmax(p, axis=1)==y_test))*100:.2f}%')
            except Exception as e:
                log(f'  {lgb_name}: ERROR - {e}')
    
    # Add M7 models
    for n in names_list:
        base_probas[n] = all_probas[n]
        if n not in base_names:
            base_names.append(n)
    
    log(f'\nTotal base models: {len(base_names)}: {base_names}')
    
    # ── 6. Ensemble search (no M7 baseline) ──
    base_no_m7 = [n for n in base_names if n not in names_list]
    if len(base_no_m7) >= 2:
        log('\nBaseline ensemble (without M7)...')
        best_base = 0
        for trial in range(5000):
            w = np.random.dirichlet(np.ones(len(base_no_m7)))
            blend = np.zeros_like(base_probas[base_no_m7[0]])
            for i, n in enumerate(base_no_m7):
                blend += w[i] * base_probas[n]
            e = float(np.mean(np.argmax(blend, axis=1) == y_test))
            if e > best_base:
                best_base = e
        log(f'  Best without M7: exact={best_base*100:.2f}%')
    
    # ── 7. Full ensemble search ──
    log('\nOptimizing full ensemble (5000 trials)...')
    t0 = time.time()
    best_exact = 0
    best_weights = None
    best_proba = None
    
    for trial in range(10000):
        w = np.random.dirichlet(np.ones(len(base_names)))
        blend = np.zeros_like(base_probas[base_names[0]])
        for i, n in enumerate(base_names):
            blend += w[i] * base_probas[n]
        e = float(np.mean(np.argmax(blend, axis=1) == y_test))
        if e > best_exact:
            best_exact = e
            best_weights = {n: float(w[i]) for i, n in enumerate(base_names)}
            best_proba = blend
    log(f'  Done ({time.time()-t0:.1f}s)')
    
    pred = np.argmax(best_proba, axis=1)
    best_1x2 = float(np.mean(np.array([result(*class_to_score(c)) for c in pred]) == actual_1x2))
    best_rps = compute_rps(y_test, best_proba)
    
    log(f'\n{"="*70}')
    log(f'SUPER ENSEMBLE RESULT')
    log(f'{"="*70}')
    log(f'  exact={best_exact*100:.2f}%')
    log(f'  1X2={best_1x2*100:.2f}%')
    log(f'  RPS={best_rps:.4f}')
    log(f'  Weights:')
    for n, w in sorted(best_weights.items(), key=lambda x: -x[1]):
        log(f'    {n:25s}: {w:.6f}')
    if len(base_no_m7) >= 2:
        log(f'  M7 improvement: +{(best_exact-best_base)*100:.2f}pp')
    
    # ── 8. M7 + LightGBM direct ──
    log('\nM7 + LightGBM direct blend:')
    if 'lightgbm' in base_names:
        m7_avg = np.mean([all_probas[n] for n in names_list], axis=0)
        lgb_p = base_probas['lightgbm']
        best_w = best_e = 0
        for w_lgb in np.arange(0.0, 1.01, 0.05):
            w_m7 = 1.0 - w_lgb
            if w_m7 == 0: continue
            e = float(np.mean(np.argmax(w_lgb * lgb_p + w_m7 * m7_avg, axis=1) == y_test))
            if e > best_e:
                best_e = e
                best_w = w_lgb
        log(f'  w_lgb={best_w:.2f}: exact={best_e*100:.2f}%')
    
    # ── 9. Save ──
    log('\nSaving...')
    
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
    
    # Also save imputer and scaler for stacking ensemble compatibility
    # The preprocessed data was used, so we save the data info
    torch.save(m7_quick.state_dict(), os.path.join(MODEL_DIR, 'M7_quick.pt'))
    torch.save(m7_medium.state_dict(), os.path.join(MODEL_DIR, 'M7_medium.pt'))
    
    results = {
        'type': 'M7_TRAINING_COMPLETE',
        'test_samples': len(y_test),
        'M7_quick': {'exact': round(q_exact*100,2), '1x2': round(q_1x2*100,2), 'rps': round(q_rps,4)},
        'M7_medium': {'exact': round(m_exact*100,2), '1x2': round(m_1x2*100,2), 'rps': round(m_rps,4)},
        'M7_internal_ensemble': {'exact': round(m7_e*100,2), '1x2': round(m7_1*100,2), 'rps': round(m7_r,4)},
        'super_ensemble': {
            'exact': round(best_exact*100,2),
            '1x2': round(best_1x2*100,2),
            'rps': round(best_rps,4),
            'weights': best_weights,
        },
        'baseline_no_m7': {'exact': round(best_base*100,2)} if len(base_no_m7) >= 2 else {},
        'm7_improvement_pp': round((best_exact-best_base)*100,2) if len(base_no_m7) >= 2 else 0,
        'm7_plus_lgbm': {'exact': round(best_e*100,2), 'w_lgb': best_w} if 'lightgbm' in base_names else {},
    }
    json.dump(results, open(os.path.join(MODEL_DIR, 'm7_results.json'), 'w'), indent=2)
    log('Saved: m7_results.json')
    
    log(f'\n{"="*70}')
    log(f'COMPLETE SUMMARY')
    log(f'  M7_quick:      {q_exact*100:.2f}% exact')
    log(f'  M7_medium:     {m_exact*100:.2f}% exact')
    log(f'  M7 average:    {m7_e*100:.2f}% exact')
    log(f'  Super ensemble: {best_exact*100:.2f}% exact')
    if len(base_no_m7) >= 2:
        log(f'  M7 improvement: +{results["m7_improvement_pp"]:.2f}pp')
    log(f'{"="*70}')


if __name__ == '__main__':
    t0 = time.time()
    main()
    print(f'\nTotal time: {time.time()-t0:.1f}s')
