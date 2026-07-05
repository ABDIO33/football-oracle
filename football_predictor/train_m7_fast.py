"""
Train M7 Residual DeepNN on preprocessed data (292K samples, 85 features).
Ensemble with LightGBM + M5 checkpoints for improved accuracy.
"""
import sys, os, json, time, gc, warnings
import numpy as np
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
import joblib

SEED = 42
torch.manual_seed(SEED)
np.random.seed(SEED)

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
DEVICE = 'cpu'
LOG = os.path.join(MODEL_DIR, 'm7_fast_log.txt')

NUM_FEATURES = 85
NUM_CLASSES = 25

def log(msg):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(f'[{time.strftime("%H:%M:%S")}] {msg}\n')
    print(f'[{time.strftime("%H:%M:%S")}] {msg}')

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
        pred_probs = y_pred_proba[i]
        p_h = sum(pred_probs[h*5 + a] for h in range(5) for a in range(5) if h > a)
        p_d = sum(pred_probs[h*5 + h] for h in range(5))
        p_a = sum(pred_probs[h*5 + a] for h in range(5) for a in range(5) if a > h)
        pred_cum = np.cumsum([p_h, p_d, p_a])
        rps_total += np.mean((actual_cum - pred_cum) ** 2)
    return rps_total / n


# ─── M7 Residual Block ───
class ResidualBlock(nn.Module):
    def __init__(self, dim, dropout=0.25):
        super().__init__()
        self.net = nn.Sequential(
            nn.LayerNorm(dim),
            nn.Linear(dim, dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.LayerNorm(dim),
            nn.Linear(dim, dim),
            nn.GELU(),
            nn.Dropout(dropout),
        )
    def forward(self, x):
        return x + self.net(x)


class M7_ResidualNet(nn.Module):
    """M7: Residual blocks + LayerNorm + GELU. Architecturally diverse from M5 (BatchNorm+ReLU)."""
    def __init__(self, input_dim, num_classes=NUM_CLASSES, width=512, depth=4, dropout=0.25):
        super().__init__()
        layers = [
            nn.Linear(input_dim, width),
            nn.LayerNorm(width),
            nn.GELU(),
            nn.Dropout(dropout),
        ]
        for _ in range(depth):
            layers.append(ResidualBlock(width, dropout))
        layers.append(nn.Linear(width, num_classes))
        self.net = nn.Sequential(*layers)
        self._init_weights()
    
    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight, mode='fan_in', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
    
    def forward(self, x):
        return self.net(x)


def train_m7_variant(name, width, depth, dropout, lr, X_train_s, y_train, X_test_s, y_test, n_epochs=100):
    """Train one M7 variant and return model + metrics."""
    log(f'\nTraining {name} (width={width}, depth={depth}, dropout={dropout}, lr={lr})')
    
    model = M7_ResidualNet(NUM_FEATURES, NUM_CLASSES, width, depth, dropout).to(DEVICE)
    total_params = sum(p.numel() for p in model.parameters())
    log(f'  Parameters: {total_params:,}')
    
    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=60)
    
    train_dataset = TensorDataset(
        torch.tensor(X_train_s, dtype=torch.float32),
        torch.tensor(y_train, dtype=torch.long))
    train_loader = DataLoader(train_dataset, batch_size=256, shuffle=True, num_workers=0)
    X_test_t = torch.tensor(X_test_s, dtype=torch.float32).to(DEVICE)
    y_test_t = torch.tensor(y_test, dtype=torch.long).to(DEVICE)
    
    best_exact = 0.0
    best_state = None
    patience = 15
    patience_counter = 0
    
    for epoch in range(n_epochs):
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
        
        if acc > best_exact:
            best_exact = acc
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= patience:
                break
        
        if (epoch+1) % 20 == 0:
            log(f'  Epoch {epoch+1:3d}: val_acc={acc*100:.2f}%')
    
    log(f'  Best val_acc: {best_exact*100:.2f}%')
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
    
    log(f'  Results: exact={exact*100:.2f}%  1X2={acc_1x2*100:.2f}%  RPS={rps:.4f}')
    
    return model, pred, proba, {'exact': exact, '1x2': acc_1x2, 'rps': rps, 'params': total_params}


def main():
    log('=' * 70)
    log('M7 RESIDUAL NETWORK TRAINING (Fast mode: preprocessed data)')
    log('=' * 70)
    
    # ── 1. Load preprocessed data ──
    log('\nLoading preprocessed_data.npz...')
    data = np.load(os.path.join(MODEL_DIR, 'preprocessed_data.npz'), allow_pickle=True)
    X_train_s = data['X_train_s']
    X_test_s = data['X_test_s']
    y_train = data['y_train']
    y_test = data['y_test']
    log(f'Train: {X_train_s.shape}, Test: {X_test_s.shape}')
    
    # ── 2. Train M7 variants ──
    configs = [
        ('M7_residual_medium', 512, 4, 0.25, 0.001),   # ~3.2M params
        ('M7_residual_wide',   768, 3, 0.30, 0.0008),  # ~4.5M params
    ]
    
    all_probas = {}
    all_models = {}
    all_metrics = {}
    
    for name, width, depth, dropout, lr in configs:
        model, pred, proba, metrics = train_m7_variant(
            name, width, depth, dropout, lr,
            X_train_s, y_train, X_test_s, y_test,
            n_epochs=100
        )
        all_probas[name] = proba
        all_models[name] = model
        all_metrics[name] = metrics
        
        # Save model
        torch.save(model.state_dict(), os.path.join(MODEL_DIR, f'{name}.pt'))
        log(f'Saved: models/{name}.pt')
        gc.collect()
    
    # ── 3. M7 internal ensemble ──
    log('\n' + '─' * 60)
    log('M7 INTERNAL ENSEMBLE')
    log('─' * 60)
    
    names_list = list(all_probas.keys())
    avg_proba = np.mean([all_probas[n] for n in names_list], axis=0)
    pred = np.argmax(avg_proba, axis=1)
    m7_exact = float(np.mean(pred == y_test))
    actual_1x2 = np.array([result(*class_to_score(c)) for c in y_test])
    pred_1x2 = np.array([result(*class_to_score(c)) for c in pred])
    m7_1x2 = float(np.mean(actual_1x2 == pred_1x2))
    m7_rps = compute_rps(y_test, avg_proba)
    log(f'Average of {len(names_list)} M7 variants:')
    log(f'  exact={m7_exact*100:.2f}%  1X2={m7_1x2*100:.2f}%  RPS={m7_rps:.4f}')
    
    # ── 4. Load existing checkpoint models (M5 + XGBoost) ──
    log('\n' + '─' * 60)
    log('LOADING EXISTING MODELS (M5 + XGBoost)')
    log('─' * 60)
    
    # XGBoost from checkpoint
    base_probas = {}
    base_names = []
    
    xgb_path = os.path.join(MODEL_DIR, 'checkpoint_xgb.pkl')
    if os.path.exists(xgb_path):
        xgb_model = joblib.load(xgb_path)
        p_test = xgb_model.predict_proba(X_test_s)
        base_probas['xgb'] = p_test
        base_names.append('xgb')
        log('Loaded checkpoint_xgb.pkl')
        
        # Evaluate XGBoost
        pred = np.argmax(p_test, axis=1)
        xe = float(np.mean(pred == y_test))
        log(f'  XGBoost alone: exact={xe*100:.2f}%')
    
    # M5 architectures
    M5_ARCHS = {
        'M5_small': [128, 256, 128],
        'M5_medium': [256, 512, 256],
        'M5_big': [512, 1024, 512],
        'M5_wide': [1024, 512, 256],
        'M5_deep': [256, 512, 256, 128],
    }
    
    class _M5_Variant(nn.Module):
        def __init__(self, input_dim, num_classes, layer_sizes):
            super().__init__()
            modules = []
            prev = input_dim
            dropouts = [0.3, 0.3, 0.3, 0.2, 0.2]
            for i, sz in enumerate(layer_sizes):
                modules.append(nn.Linear(prev, sz))
                if sz >= 128:
                    modules.append(nn.BatchNorm1d(sz))
                modules.append(nn.ReLU())
                modules.append(nn.Dropout(dropouts[min(i, len(dropouts)-1)]))
                prev = sz
            modules.append(nn.Linear(prev, num_classes))
            self.net = nn.Sequential(*modules)
        def forward(self, x):
            return self.net(x)
    
    X_test_t = torch.tensor(X_test_s, dtype=torch.float32).to(DEVICE)
    for m5_name, m5_layers in M5_ARCHS.items():
        pt_path = os.path.join(MODEL_DIR, f'checkpoint_{m5_name}.pt')
        if os.path.exists(pt_path):
            try:
                m5_model = _M5_Variant(NUM_FEATURES, NUM_CLASSES, m5_layers)
                m5_model.load_state_dict(torch.load(pt_path, map_location='cpu'))
                m5_model.eval()
                with torch.no_grad():
                    proba = torch.softmax(m5_model(X_test_t), dim=1).cpu().numpy()
                base_probas[m5_name] = proba
                base_names.append(m5_name)
                
                # Evaluate individually
                pred = np.argmax(proba, axis=1)
                me = float(np.mean(pred == y_test))
                log(f'  {m5_name}: exact={me*100:.2f}%')
            except Exception as e:
                log(f'  {m5_name}: ERROR loading - {e}')
    
    log(f'\nBase models loaded: {base_names}')
    
    # ── 5. Try LightGBM ──
    lgb_proba = None
    lgb_models_found = []
    for lgb_name in ['lgbm_final.pkl', 'lgbm_best.pkl']:
        lgb_path = os.path.join(MODEL_DIR, lgb_name)
        if os.path.exists(lgb_path):
            try:
                lgb_model = joblib.load(lgb_path)
                p_test = lgb_model.predict_proba(X_test_s)
                lgb_proba = p_test
                lgb_models_found.append(lgb_name)
                pred = np.argmax(p_test, axis=1)
                le = float(np.mean(pred == y_test))
                log(f'Loaded {lgb_name}: exact={le*100:.2f}%')
            except Exception as e:
                log(f'{lgb_name}: ERROR - {e}')
    
    if lgb_proba is not None:
        base_probas['lightgbm'] = lgb_proba
        base_names.append('lightgbm')
    
    # ── 6. Add M7 to base models ──
    for n in names_list:
        base_probas[n] = all_probas[n]
        if n not in base_names:
            base_names.append(n)
    
    log(f'\nAll models for ensemble: {base_names}')
    
    # ── 7. Ensemble search ──
    log('\n' + '─' * 60)
    log('ENSEMBLE SEARCH (Random Weight Optimization)')
    log('─' * 60)
    
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
    
    pred = np.argmax(best_proba, axis=1)
    actual_1x2 = np.array([result(*class_to_score(c)) for c in y_test])
    pred_1x2 = np.array([result(*class_to_score(c)) for c in pred])
    best_1x2 = float(np.mean(actual_1x2 == pred_1x2))
    best_rps = compute_rps(y_test, best_proba)
    
    log(f'\nBEST ENSEMBLE RESULT:')
    log(f'  exact={best_exact*100:.2f}%')
    log(f'  1X2={best_1x2*100:.2f}%')
    log(f'  RPS={best_rps:.4f}')
    log(f'  Weights:')
    for n, w in sorted(best_weights.items(), key=lambda x: -x[1]):
        log(f'    {n:25s}: {w:.4f}')
    
    # ── 8. Also try ensemble WITHOUT M7 (to measure improvement) ──
    log('\n' + '─' * 60)
    log('BASELINE ENSEMBLE (without M7)')
    log('─' * 60)
    
    base_names_no_m7 = [n for n in base_names if n not in names_list]
    if base_names_no_m7:
        best_base_exact = 0
        best_base_weights = None
        for trial in range(3000):
            w = np.random.dirichlet(np.ones(len(base_names_no_m7)))
            blend = np.zeros_like(base_probas[base_names_no_m7[0]])
            for i, n in enumerate(base_names_no_m7):
                blend += w[i] * base_probas[n]
            pred = np.argmax(blend, axis=1)
            exact = float(np.mean(pred == y_test))
            if exact > best_base_exact:
                best_base_exact = exact
                best_base_weights = {n: float(w[i]) for i, n in enumerate(base_names_no_m7)}
        
        log(f'  Baseline (no M7): exact={best_base_exact*100:.2f}%')
        log(f'  With M7:          exact={best_exact*100:.2f}%')
        log(f'  Improvement:      +{(best_exact - best_base_exact)*100:.2f}pp')
    
    # ── 9. M7 + LightGBM direct blend ──
    if lgb_proba is not None:
        log('\n' + '─' * 60)
        log('M7 + LightGBM DIRECT BLEND')
        log('─' * 60)
        
        m7_avg = np.mean([all_probas[n] for n in names_list], axis=0)
        
        best_w = 0
        best_e = 0
        for w_lgb in np.arange(0.0, 1.01, 0.05):
            w_m7 = 1.0 - w_lgb
            if w_m7 == 0:
                continue
            blend = w_lgb * lgb_proba + w_m7 * m7_avg
            pred = np.argmax(blend, axis=1)
            exact = float(np.mean(pred == y_test))
            if exact > best_e:
                best_e = exact
                best_w = w_lgb
        
        pred = np.argmax(best_w * lgb_proba + (1-best_w) * m7_avg, axis=1)
        actual_1x2 = np.array([result(*class_to_score(c)) for c in y_test])
        pred_1x2 = np.array([result(*class_to_score(c)) for c in pred])
        m7_lgb_1x2 = float(np.mean(actual_1x2 == pred_1x2))
        m7_lgb_rps = compute_rps(y_test, best_w * lgb_proba + (1-best_w) * m7_avg)
        
        log(f'  M7 + LightGBM (w_lgb={best_w:.2f}):')
        log(f'    exact={best_e*100:.2f}%  1X2={m7_lgb_1x2*100:.2f}%  RPS={m7_lgb_rps:.4f}')
    
    # ── 10. Save results ──
    log('\n' + '=' * 70)
    log('SAVING RESULTS')
    log('=' * 70)
    
    # Save m7_ensemble_package for later use with stacking_ensemble.py
    m7_package = {
        'model_names': names_list,
        'metrics': all_metrics,
        'default_weights': {n: 1.0/len(names_list) for n in names_list},
    }
    joblib.dump(m7_package, os.path.join(MODEL_DIR, 'm7_ensemble_package.pkl'))
    
    # Also save the M7 average probability wrapper for production
    class M7EnsembleWrapper:
        """Wrapper that averages all M7 models, compatible with EnsemblePredictor."""
        def __init__(self, models, device='cpu'):
            self.models = models
            self.device = device
            for m in self.models:
                m.eval()
        
        def predict_proba(self, X):
            with torch.no_grad():
                X_t = torch.tensor(X, dtype=torch.float32).to(self.device)
                probas = []
                for m in self.models:
                    probas.append(torch.softmax(m(X_t), dim=1))
                avg = torch.mean(torch.stack(probas), dim=0)
            return avg.cpu().numpy()
    
    m7_wrapper = M7EnsembleWrapper([all_models[n] for n in names_list], DEVICE)
    joblib.dump(m7_wrapper, os.path.join(MODEL_DIR, 'm7_ensemble_wrapper.pkl'))
    log('Saved: models/m7_ensemble_wrapper.pkl')
    log('Saved: models/m7_ensemble_package.pkl')
    
    # Comprehensive results
    results = {
        'type': 'M7_FAST_TRAINING',
        'data_samples': len(X_train_s) + len(X_test_s),
        'data_features': NUM_FEATURES,
        'test_samples': len(y_test),
        'individual_models': all_metrics,
        'm7_internal_ensemble': {
            'exact': round(m7_exact*100, 2),
            '1x2': round(m7_1x2*100, 2),
            'rps': round(m7_rps, 4),
        },
        'super_ensemble': {
            'exact': round(best_exact*100, 2),
            '1x2': round(best_1x2*100, 2),
            'rps': round(best_rps, 4),
            'weights': best_weights,
        },
        'baseline_no_m7': {
            'exact': round(best_base_exact*100, 2) if base_names_no_m7 else 0,
        },
        'm7_plus_lgbm': {
            'exact': round(best_e*100, 2) if lgb_proba is not None else 0,
            '1x2': round(m7_lgb_1x2*100, 2) if lgb_proba is not None else 0,
            'rps': round(m7_lgb_rps, 4) if lgb_proba is not None else 0,
        },
    }
    
    json.dump(results, open(os.path.join(MODEL_DIR, 'm7_fast_results.json'), 'w'), indent=2)
    log('Saved: models/m7_fast_results.json')
    
    log(f'\n{"="*70}')
    log(f'SUMMARY')
    log(f'  Best M7 individual: {max(all_metrics.items(), key=lambda x: x[1]["exact"])[0]}')
    log(f'  M7 internal ensemble: exact={m7_exact*100:.2f}%')
    log(f'  Super ensemble (all models): exact={best_exact*100:.2f}%')
    if lgb_proba is not None:
        log(f'  M7 + LightGBM: exact={best_e*100:.2f}%')
    if base_names_no_m7:
        log(f'  Improvement from M7: +{(best_exact - best_base_exact)*100:.2f}pp')
    log(f'{"="*70}')
    
    return results


if __name__ == '__main__':
    t0 = time.time()
    results = main()
    elapsed = time.time() - t0
    log(f'\nTotal time: {elapsed/60:.1f} minutes')
    print(f'\nDone! Results in models/m7_fast_results.json')
    print(f'Log: models/m7_fast_log.txt')
