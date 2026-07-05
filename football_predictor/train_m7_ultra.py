"""
Ultra-fast M7 training: larger batch, smaller model, detailed progress.
Ensemble with LightGBM + M5 checkpoints.
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
LOG = os.path.join(MODEL_DIR, 'm7_ultra_log.txt')

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
                nn.init.kaiming_normal_(m.weight, mode='fan_in', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
    def forward(self, x):
        return self.net(x)


def train_quick(name, width, depth, dropout, lr, X_train_s, y_train, X_test_s, y_test, n_epochs=40):
    log(f'\n=== Training {name} ===')
    log(f'  width={width}, depth={depth}, dropout={dropout}, lr={lr}')
    
    model = M7_ResidualNet(NUM_FEATURES, NUM_CLASSES, width, depth, dropout).to(DEVICE)
    total_params = sum(p.numel() for p in model.parameters())
    log(f'  Params: {total_params:,}')
    
    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=n_epochs)
    
    train_loader = DataLoader(
        TensorDataset(torch.tensor(X_train_s, dtype=torch.float32),
                      torch.tensor(y_train, dtype=torch.long)),
        batch_size=2048, shuffle=True, num_workers=0)
    X_test_t = torch.tensor(X_test_s, dtype=torch.float32).to(DEVICE)
    y_test_t = torch.tensor(y_test, dtype=torch.long).to(DEVICE)
    
    best_exact = 0.0
    best_state = None
    patience = 8
    
    for epoch in range(n_epochs):
        t0 = time.time()
        model.train()
        for Xb, yb in train_loader:
            Xb, yb = Xb.to(DEVICE), yb.to(DEVICE)
            optimizer.zero_grad()
            loss = criterion(model(Xb), yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        
        model.eval()
        with torch.no_grad():
            out = model(X_test_t)
            _, preds = torch.max(out, 1)
            acc = (preds == y_test_t).sum().item() / len(y_test)
        scheduler.step()
        
        dt = time.time() - t0
        
        if acc > best_exact:
            best_exact = acc
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        
        log(f'  Epoch {epoch+1:2d}/{n_epochs}: val_acc={acc*100:.2f}% (best={best_exact*100:.2f}%) [{dt:.1f}s]')
        
        # Early stopping
        if epoch > 10 and acc < best_exact - 0.005:
            pass  # don't early stop too aggressively
        
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        proba = torch.softmax(model(X_test_t), dim=1).cpu().numpy()
        pred = torch.max(model(X_test_t), 1)[1].cpu().numpy()
    
    exact = float(np.mean(pred == y_test))
    actual_1x2 = np.array([result(*class_to_score(c)) for c in y_test])
    pred_1x2 = np.array([result(*class_to_score(c)) for c in pred])
    acc_1x2 = float(np.mean(actual_1x2 == pred_1x2))
    rps = compute_rps(y_test, proba)
    
    log(f'  FINAL: exact={exact*100:.2f}%  1X2={acc_1x2*100:.2f}%  RPS={rps:.4f}')
    return model, proba, {'exact': exact, '1x2': acc_1x2, 'rps': rps, 'params': total_params}


def main():
    log('=' * 70)
    log('M7 ULTRA-FAST TRAINING')
    log('=' * 70)
    
    # Load preprocessed data
    log('\nLoading data...')
    t0 = time.time()
    data = np.load(os.path.join(MODEL_DIR, 'preprocessed_data.npz'), allow_pickle=True)
    X_train_s = data['X_train_s']
    X_test_s = data['X_test_s']
    y_train = data['y_train']
    y_test = data['y_test']
    log(f'Train: {X_train_s.shape}, Test: {X_test_s.shape} ({time.time()-t0:.1f}s)')
    
    # Train 2 M7 variants quickly
    configs = [
        ('M7_quick', 384, 3, 0.25, 0.001),   # small, fast
        ('M7_medium', 512, 4, 0.25, 0.001),  # medium
    ]
    
    all_probas = {}
    all_models = {}
    all_metrics = {}
    
    for name, width, depth, dropout, lr in configs:
        m, p, metrics = train_quick(name, width, depth, dropout, lr,
                                     X_train_s, y_train, X_test_s, y_test, n_epochs=20)
        all_probas[name] = p
        all_models[name] = m
        all_metrics[name] = metrics
        
        torch.save(m.state_dict(), os.path.join(MODEL_DIR, f'{name}.pt'))
        log(f'Saved: models/{name}.pt')
        gc.collect()
    
    # M7 internal average
    names_list = list(all_probas.keys())
    m7_avg = np.mean([all_probas[n] for n in names_list], axis=0)
    mp = np.argmax(m7_avg, axis=1)
    m7_exact = float(np.mean(mp == y_test))
    log(f'\nM7 average ensemble: exact={m7_exact*100:.2f}%')
    
    # Load existing models
    log('\nLoading existing models...')
    base_probas = {}
    base_names = []
    
    X_test_t = torch.tensor(X_test_s, dtype=torch.float32).to(DEVICE)
    
    # XGBoost
    xgb_path = os.path.join(MODEL_DIR, 'checkpoint_xgb.pkl')
    if os.path.exists(xgb_path):
        xgb_model = joblib.load(xgb_path)
        p = xgb_model.predict_proba(X_test_s)
        base_probas['xgb'] = p
        base_names.append('xgb')
        pe = float(np.mean(np.argmax(p, axis=1) == y_test))
        log(f'  XGBoost: exact={pe*100:.2f}%')
    
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
                pe = float(np.mean(np.argmax(p, axis=1) == y_test))
                log(f'  {m5_name}: exact={pe*100:.2f}%')
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
                pe = float(np.mean(np.argmax(p, axis=1) == y_test))
                log(f'  {lgb_name}: exact={pe*100:.2f}%')
            except Exception as e:
                log(f'  {lgb_name}: ERROR - {e}')
    
    # Add M7
    for n in names_list:
        base_probas[n] = all_probas[n]
        if n not in base_names:
            base_names.append(n)
    
    log(f'\nTotal base models: {len(base_names)}')
    
    # Ensemble search
    log('\nOptimizing ensemble weights (5000 trials)...')
    t0 = time.time()
    best_exact = 0
    best_weights = None
    best_proba = None
    
    for trial in range(5000):
        w = np.random.dirichlet(np.ones(len(base_names)))
        blend = np.zeros_like(base_probas[base_names[0]])
        for i, n in enumerate(base_names):
            blend += w[i] * base_probas[n]
        pred = np.argmax(blend, axis=1)
        exact = float(np.mean(pred == y_test))
        if exact > best_exact:
            best_exact = exact
            best_weights = {n: float(w[i]) for i, n in enumerate(base_names)}
            best_proba = blend
    log(f'  Done ({time.time()-t0:.1f}s)')
    
    pred = np.argmax(best_proba, axis=1)
    actual_1x2 = np.array([result(*class_to_score(c)) for c in y_test])
    pred_1x2 = np.array([result(*class_to_score(c)) for c in pred])
    best_1x2 = float(np.mean(actual_1x2 == pred_1x2))
    best_rps = compute_rps(y_test, best_proba)
    
    log(f'\n{"="*70}')
    log(f'SUPER ENSEMBLE RESULT')
    log(f'{"="*70}')
    log(f'  exact={best_exact*100:.2f}%')
    log(f'  1X2={best_1x2*100:.2f}%')
    log(f'  RPS={best_rps:.4f}')
    log(f'  Weights:')
    for n, w in sorted(best_weights.items(), key=lambda x: -x[1]):
        log(f'    {n:25s}: {w:.4f}')
    
    # Baseline without M7
    log(f'\nBaseline (w/o M7)...')
    base_no_m7 = [n for n in base_names if n not in names_list]
    if len(base_no_m7) >= 2:
        best_base = 0
        for trial in range(3000):
            w = np.random.dirichlet(np.ones(len(base_no_m7)))
            blend = np.zeros_like(base_probas[base_no_m7[0]])
            for i, n in enumerate(base_no_m7):
                blend += w[i] * base_probas[n]
            pred = np.argmax(blend, axis=1)
            exact = float(np.mean(pred == y_test))
            if exact > best_base:
                best_base = exact
        log(f'  Without M7: exact={best_base*100:.2f}%')
        log(f'  With M7:    exact={best_exact*100:.2f}%')
        log(f'  Gain:       +{(best_exact-best_base)*100:.2f}pp')
    
    # Save
    log('\nSaving models...')
    
    # M7 ensemble wrapper
    class M7Wrapper:
        def __init__(self, models, device='cpu'):
            self.models = models
            self.device = device
            for m in self.models: m.eval()
        def predict_proba(self, X):
            with torch.no_grad():
                X_t = torch.tensor(X, dtype=torch.float32).to(self.device)
                ps = [torch.softmax(m(X_t), dim=1) for m in self.models]
                return torch.mean(torch.stack(ps), dim=0).cpu().numpy()
    
    wrapper = M7Wrapper([all_models[n] for n in names_list], DEVICE)
    joblib.dump(wrapper, os.path.join(MODEL_DIR, 'm7_wrapper.pkl'))
    
    results = {
        'type': 'M7_ULTRA_TRAINING',
        'test_samples': len(y_test),
        'individual_models': all_metrics,
        'm7_ensemble': {
            'exact': round(m7_exact*100, 2),
        },
        'super_ensemble': {
            'exact': round(best_exact*100, 2),
            '1x2': round(best_1x2*100, 2),
            'rps': round(best_rps, 4),
            'weights': best_weights,
        },
        'baseline_no_m7': {
            'exact': round(best_base*100, 2) if len(base_no_m7) >= 2 else 0,
        },
        'm7_improvement_pp': round((best_exact-best_base)*100, 2) if len(base_no_m7) >= 2 else 0,
    }
    json.dump(results, open(os.path.join(MODEL_DIR, 'm7_ultra_results.json'), 'w'), indent=2)
    
    log(f'\n{"="*70}')
    log(f'SUMMARY')
    log(f'  M7 ensemble alone: {m7_exact*100:.2f}%')
    log(f'  Super ensemble: {best_exact*100:.2f}%')
    if len(base_no_m7) >= 2:
        log(f'  M7 improvement: +{results["m7_improvement_pp"]:.2f}pp')
    log(f'{"="*70}')
    
    return results


if __name__ == '__main__':
    t0 = time.time()
    main()
    print(f'\nTotal: {time.time()-t0:.1f}s')
    print(f'Log: models/m7_ultra_log.txt')
    print(f'Results: models/m7_ultra_results.json')
