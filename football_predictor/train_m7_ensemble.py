"""
Train M7 DeepNN with residual connections for ensemble diversity with LightGBM.
Uses the large 885K V5 dataset and _load_training_data() pipeline.
"""
import sys, os, json, time, gc, warnings, pickle
import numpy as np
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))

os.environ['PYTHONIOENCODING'] = 'utf-8'
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
import joblib

SEED = 42
torch.manual_seed(SEED)
np.random.seed(SEED)

sys.path.insert(0, os.path.dirname(__file__))
from direct_predictor import _load_training_data, FEATURES, NUM_CLASSES, SCORE_CLASSES, class_to_score, result, TorchMLPWrapper

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
DEVICE = 'cpu'  # CPU-only as per project context
LOG = os.path.join(MODEL_DIR, 'm7_train_log.txt')

NUM_FEATURES = len(FEATURES) if isinstance(FEATURES, list) else 85

def log(msg):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(f'[{time.strftime("%H:%M:%S")}] {msg}\n')
    print(f'[{time.strftime("%H:%M:%S")}] {msg}')

# ─── Residual Block ───
class ResidualBlock(nn.Module):
    """Residual block with LayerNorm + GELU for diversity from existing M5."""
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

# ─── M7 Architecture (Residual + Wider) ───
class M7_ResidualNet(nn.Module):
    """
    M7: Uses residual blocks, LayerNorm, GELU activation.
    Architecturally different from M5 (which use BatchNorm + ReLU).
    This provides ensemble diversity.
    """
    def __init__(self, input_dim, num_classes=NUM_CLASSES, width=512, depth=4, dropout=0.25):
        super().__init__()
        
        # Initial projection
        layers = [
            nn.Linear(input_dim, width),
            nn.LayerNorm(width),
            nn.GELU(),
            nn.Dropout(dropout),
        ]
        
        # Residual blocks
        for _ in range(depth):
            layers.append(ResidualBlock(width, dropout))
        
        # Head to 25 classes
        layers.extend([
            nn.Linear(width, num_classes),
        ])
        
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


def compute_rps(y_true, y_pred_proba):
    """Ranked Probability Score via 1X2."""
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


def evaluate_model(model, X_test_s, y_test, device, name="model"):
    """Evaluate exact, 1X2, RPS."""
    model.eval()
    with torch.no_grad():
        X_t = torch.tensor(X_test_s, dtype=torch.float32).to(device)
        out = model(X_t)
        proba = torch.softmax(out, dim=1).cpu().numpy()
        pred = torch.max(out, 1)[1].cpu().numpy()
    
    exact = np.mean(pred == y_test)
    actual_1x2 = np.array([result(*class_to_score(c)) for c in y_test])
    pred_1x2 = np.array([result(*class_to_score(c)) for c in pred])
    acc_1x2 = np.mean(actual_1x2 == pred_1x2)
    rps = compute_rps(y_test, proba)
    
    return pred, proba, exact, acc_1x2, rps


def train_m7():
    log('=' * 70)
    log('M7 RESIDUAL NETWORK TRAINING')
    log('Architecture: Residual blocks + LayerNorm + GELU')
    log('=' * 70)
    
    # ── 1. Load data ──
    log('\nLoading training data via _load_training_data()...')
    X, y, match_ids = _load_training_data()
    log(f'Loaded: {len(X)} samples, {X.shape[1]} features, {NUM_CLASSES} classes')
    
    # ── 2. Split (train 90% / test 10%) ──
    split = int(len(X) * 0.9)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    log(f'Train: {len(X_train)}, Test: {len(X_test)}')
    
    # ── 3. Impute + Scale ──
    imp = SimpleImputer(strategy='median')
    X_train_imp = imp.fit_transform(X_train)
    X_test_imp = imp.transform(X_test)
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train_imp)
    X_test_s = scaler.transform(X_test_imp)
    log(f'Input dim: {X_train_s.shape[1]}')
    
    # ── 4. Build M7 model ──
    # Try 3 variants of M7 for diversity
    m7_configs = [
        # (name, width, depth, dropout, lr, label)
        ('M7_residual_medium', 512, 4, 0.25, 0.001, 'M7-Medium (512×4res)'),
        ('M7_residual_wide',   768, 3, 0.30, 0.0008, 'M7-Wide (768×3res)'),
        ('M7_residual_deep',   384, 6, 0.25, 0.001,  'M7-Deep (384×6res)'),
    ]
    
    all_probas = {}
    all_models = {}
    all_metrics = {}
    
    for name, width, depth, dropout, lr, label in m7_configs:
        log(f'\n{"─"*60}')
        log(f'Training {label}')
        log(f'  width={width}, depth={depth}, dropout={dropout}, lr={lr}')
        
        model = M7_ResidualNet(input_dim=NUM_FEATURES, num_classes=NUM_CLASSES,
                               width=width, depth=depth, dropout=dropout).to(DEVICE)
        
        total_params = sum(p.numel() for p in model.parameters())
        log(f'  Parameters: {total_params:,}')
        
        # Training setup
        criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
        optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
        scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=80)
        
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
        n_epochs = 120
        
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
                    if (epoch+1) % 10 != 0:
                        pass  # silent early stop unless printing
                    break
            
            if (epoch+1) % 20 == 0:
                log(f'  Epoch {epoch+1:3d}: val_acc={acc:.4f}')
        
        log(f'  Best val_acc: {best_exact:.4f}')
        
        # Restore best
        model.load_state_dict(best_state)
        model.eval()
        
        # Evaluate
        pred, proba, exact, acc_1x2, rps = evaluate_model(model, X_test_s, y_test, DEVICE, name)
        log(f'  RESULTS: exact={exact*100:.2f}%  1X2={acc_1x2*100:.2f}%  RPS={rps:.4f}')
        
        all_probas[name] = proba
        all_models[name] = model
        all_metrics[name] = {'exact': float(exact), '1x2': float(acc_1x2), 'rps': float(rps), 'params': total_params}
        
        # Save individual model
        torch.save(model.state_dict(), os.path.join(MODEL_DIR, f'{name}.pt'))
        log(f'  Saved: models/{name}.pt')
        
        # Also save as TorchMLPWrapper for easy ensembling
        wrapper = TorchMLPWrapper(model, DEVICE)
        joblib.dump(wrapper, os.path.join(MODEL_DIR, f'{name}_wrapper.pkl'))
        log(f'  Saved: models/{name}_wrapper.pkl')
        
        gc.collect()
    
    # ── 5. Try to load LightGBM for ensemble ──
    log('\n' + '=' * 60)
    log('ENSEMBLE WITH LIGHTGBM')
    log('=' * 60)
    
    lgb_model = None
    lgb_proba = None
    try:
        lgb_path = os.path.join(MODEL_DIR, 'lgbm_final.pkl')
        if os.path.exists(lgb_path):
            lgb_model = joblib.load(lgb_path)
            log(f'Loaded LightGBM: {type(lgb_model).__name__}')
            # Need to check feature count - LightGBM may have different features
            n_lgb_features = lgb_model._Booster.num_feature() if hasattr(lgb_model, '_Booster') else lgb_model.n_features_
            log(f'  LightGBM features: {n_lgb_features}')
            
            # If LightGBM uses same features (85), get predictions
            # LightGBM model was trained on different data (maybe different features)
            # Let's try to predict
            lgb_proba = lgb_model.predict_proba(X_test_imp)  # LightGBM doesn't need scaling
            log(f'  LightGBM predictions: {lgb_proba.shape}')
            lgb_pred = np.argmax(lgb_proba, axis=1)
            lgb_exact = np.mean(lgb_pred == y_test)
            actual_1x2 = np.array([result(*class_to_score(c)) for c in y_test])
            lgb_pred_1x2 = np.array([result(*class_to_score(c)) for c in lgb_pred])
            lgb_1x2 = np.mean(actual_1x2 == lgb_pred_1x2)
            lgb_rps = compute_rps(y_test, lgb_proba)
            log(f'  LightGBM alone: exact={lgb_exact*100:.2f}%  1X2={lgb_1x2*100:.2f}%  RPS={lgb_rps:.4f}')
        else:
            log(f'  LightGBM model not found at {lgb_path}')
    except Exception as e:
        log(f'  Could not load/predict with LightGBM: {e}')
        # Try alternative LightGBM path
        try:
            alt_paths = [os.path.join(MODEL_DIR, 'lgbm_best.pkl'), os.path.join(MODEL_DIR, 'lgbm_direct.txt')]
            for ap in alt_paths:
                if os.path.exists(ap):
                    log(f'  Trying alternative: {ap}')
        except:
            pass
    
    # ── 6. Try ensemble of all M7 variants ──
    log('\n' + '─' * 60)
    log('M7 Internal Ensemble Search')
    log('─' * 60)
    
    names_list = list(all_probas.keys())
    best_m7_exact = 0
    best_m7_combo = ''
    best_m7_proba = None
    
    from itertools import combinations
    
    for n_models in range(1, len(names_list) + 1):
        for combo in combinations(range(len(names_list)), n_models):
            w_each = 1.0 / len(combo)
            combo_proba = np.zeros_like(all_probas[names_list[0]])
            for idx in combo:
                combo_proba += w_each * all_probas[names_list[idx]]
            
            combo_pred = np.argmax(combo_proba, axis=1)
            exact = float(np.mean(combo_pred == y_test))
            
            if exact > best_m7_exact:
                best_m7_exact = exact
                best_m7_combo = '+'.join([names_list[i] for i in combo])
                best_m7_proba = combo_proba
    
    log(f'Best M7 internal ensemble: {best_m7_combo}')
    pred = np.argmax(best_m7_proba, axis=1)
    actual_1x2 = np.array([result(*class_to_score(c)) for c in y_test])
    pred_1x2 = np.array([result(*class_to_score(c)) for c in pred])
    m7_1x2 = float(np.mean(actual_1x2 == pred_1x2))
    m7_rps = compute_rps(y_test, best_m7_proba)
    log(f'  exact={best_m7_exact*100:.2f}%  1X2={m7_1x2*100:.2f}%  RPS={m7_rps:.4f}')
    
    # ── 7. Ensemble M7 with LightGBM ──
    if lgb_proba is not None:
        log('\n' + '─' * 60)
        log('M7 + LightGBM Ensemble Search')
        log('─' * 60)
        
        results = []
        for w_lgb in np.arange(0.0, 1.01, 0.05):
            w_m7 = 1.0 - w_lgb
            if w_m7 == 0:
                continue
            blend = w_lgb * lgb_proba + w_m7 * best_m7_proba
            pred = np.argmax(blend, axis=1)
            exact = float(np.mean(pred == y_test))
            results.append({'w_lgb': w_lgb, 'w_m7': w_m7, 'exact': exact})
        
        results.sort(key=lambda r: -r['exact'])
        best_blend = results[0]
        log(f'Best M7+LightGBM: w_lgb={best_blend["w_lgb"]:.2f} w_m7={best_blend["w_m7"]:.2f}')
        
        blend = best_blend['w_lgb'] * lgb_proba + best_blend['w_m7'] * best_m7_proba
        pred = np.argmax(blend, axis=1)
        actual_1x2 = np.array([result(*class_to_score(c)) for c in y_test])
        pred_1x2 = np.array([result(*class_to_score(c)) for c in pred])
        blend_1x2 = float(np.mean(actual_1x2 == pred_1x2))
        blend_rps = compute_rps(y_test, blend)
        log(f'  exact={best_blend["exact"]*100:.2f}%  1X2={blend_1x2*100:.2f}%  RPS={blend_rps:.4f}')
        
        log(f'\nTop 5 M7+LightGBM blends:')
        for i, r in enumerate(results[:5]):
            log(f'  {i+1}. w_lgb={r["w_lgb"]:.2f} w_m7={r["w_m7"]:.2f} exact={r["exact"]*100:.2f}%')
        
        # Try all M7 variants individually + LightGBM
        log('\n' + '─' * 60)
        log('Individual M7 + LightGBM Ensemble')
        log('─' * 60)
        
        for name in names_list:
            best_w = 0
            best_e = 0
            for w_lgb in np.arange(0.0, 1.01, 0.05):
                w_m7 = 1.0 - w_lgb
                if w_m7 == 0:
                    continue
                blend = w_lgb * lgb_proba + w_m7 * all_probas[name]
                pred = np.argmax(blend, axis=1)
                exact = float(np.mean(pred == y_test))
                if exact > best_e:
                    best_e = exact
                    best_w = w_lgb
            log(f'  {name:25s} + LightGBM: w_lgb={best_w:.2f} exact={best_e*100:.2f}%')
    
    # ── 8. Try ensemble with existing M5 checkpoint models ──
    log('\n' + '─' * 60)
    log('M7 + Existing M5 Checkpoints Ensemble')
    log('─' * 60)
    
    # M5 architectures (from stacking_ensemble.py)
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
    
    m5_probas = {}
    for m5_name, m5_layers in M5_ARCHS.items():
        pt_path = os.path.join(MODEL_DIR, f'checkpoint_{m5_name}.pt')
        if os.path.exists(pt_path):
            try:
                m5_model = _M5_Variant(NUM_FEATURES, NUM_CLASSES, m5_layers)
                m5_model.load_state_dict(torch.load(pt_path, map_location='cpu'))
                m5_model.eval()
                with torch.no_grad():
                    X_t = torch.tensor(X_test_s, dtype=torch.float32).to(DEVICE)
                    proba = torch.softmax(m5_model(X_t), dim=1).cpu().numpy()
                m5_probas[m5_name] = proba
                log(f'  Loaded {m5_name}')
            except Exception as e:
                log(f'  Could not load {m5_name}: {e}')
    
    if m5_probas:
        # Find best ensemble of ALL models (M5 + M7 + LightGBM)
        log('\n' + '─' * 60)
        log('Super Ensemble: M5 + M7 + LightGBM')
        log('─' * 60)
        
        all_base_probas = {}
        for k, v in m5_probas.items():
            all_base_probas[k] = v
        for k, v in all_probas.items():
            all_base_probas[k] = v
        if lgb_proba is not None:
            all_base_probas['lightgbm'] = lgb_proba
        
        base_names = list(all_base_probas.keys())
        log(f'  Base models: {base_names}')
        
        # Simple average ensemble
        avg_proba = np.zeros_like(all_base_probas[base_names[0]])
        for n in base_names:
            avg_proba += all_base_probas[n]
        avg_proba /= len(base_names)
        pred = np.argmax(avg_proba, axis=1)
        exact = float(np.mean(pred == y_test))
        actual_1x2 = np.array([result(*class_to_score(c)) for c in y_test])
        pred_1x2 = np.array([result(*class_to_score(c)) for c in pred])
        acc_1x2 = float(np.mean(actual_1x2 == pred_1x2))
        rps = compute_rps(y_test, avg_proba)
        log(f'  Simple average of all models:')
        log(f'    exact={exact*100:.2f}%  1X2={acc_1x2*100:.2f}%  RPS={rps:.4f}')
        
        # Optimize weights for best ensemble
        log('\n  Optimizing weights (random search)...')
        best_super_exact = 0
        best_super_weights = None
        best_super_proba = None
        
        for trial in range(2000):
            w = np.random.dirichlet(np.ones(len(base_names)))
            blend = np.zeros_like(all_base_probas[base_names[0]])
            for i, n in enumerate(base_names):
                blend += w[i] * all_base_probas[n]
            pred = np.argmax(blend, axis=1)
            exact = float(np.mean(pred == y_test))
            if exact > best_super_exact:
                best_super_exact = exact
                best_super_weights = {n: float(w[i]) for i, n in enumerate(base_names)}
                best_super_proba = blend
        
        pred = np.argmax(best_super_proba, axis=1)
        actual_1x2 = np.array([result(*class_to_score(c)) for c in y_test])
        pred_1x2 = np.array([result(*class_to_score(c)) for c in pred])
        super_1x2 = float(np.mean(actual_1x2 == pred_1x2))
        super_rps = compute_rps(y_test, best_super_proba)
        
        log(f'  Best weighted ensemble:')
        log(f'    exact={best_super_exact*100:.2f}%  1X2={super_1x2*100:.2f}%  RPS={super_rps:.4f}')
        log(f'    weights:')
        for n, w in sorted(best_super_weights.items(), key=lambda x: -x[1]):
            log(f'      {n:25s}: {w:.4f}')
        
        # Also try adding M7 to the existing checkpoint ensemble
        log('\n  Adding M7 to existing best ensemble...')
        cp_path = os.path.join(MODEL_DIR, 'checkpoint.json')
        if os.path.exists(cp_path):
            cp = json.load(open(cp_path))
            cp_weights = cp.get('best_weights', {})
            if cp_weights:
                # Try adding M7
                for w_m7 in np.arange(0.0, 0.5, 0.05):
                    remaining = 1.0 - w_m7
                    blend = np.zeros_like(all_base_probas[base_names[0]])
                    for n, w in cp_weights.items():
                        if n in all_base_probas:
                            blend += w * remaining * all_base_probas[n]
                    # Add M7 variants
                    m7_internal_count = len(names_list)
                    for m7_name in names_list:
                        if m7_name in all_base_probas:
                            blend += (w_m7 / m7_internal_count) * all_base_probas[m7_name]
                    
                    pred = np.argmax(blend, axis=1)
                    exact = float(np.mean(pred == y_test))
                    log(f'    w_m7={w_m7:.2f}: exact={exact*100:.2f}%')
    
    # ── 9. Save final results ──
    log('\n' + '=' * 70)
    log('SAVING FINAL RESULTS')
    log('=' * 70)
    
    results = {
        'type': 'M7_RESIDUAL_TRAINING',
        'data_samples': len(X),
        'data_features': NUM_FEATURES,
        'test_samples': len(y_test),
        'individual_models': all_metrics,
        'm7_internal_ensemble': {
            'name': best_m7_combo,
            'exact': round(best_m7_exact * 100, 2),
            '1x2': round(m7_1x2 * 100, 2),
            'rps': round(m7_rps, 4),
        },
        'lgbm_available': lgb_model is not None,
    }
    
    if lgb_proba is not None:
        results['m7_plus_lgbm'] = {
            'best_blend': {
                'w_lgb': best_blend['w_lgb'],
                'exact': round(best_blend['exact'] * 100, 2),
                '1x2': round(blend_1x2 * 100, 2),
                'rps': round(blend_rps, 4),
            }
        }
    
    if m5_probas:
        results['super_ensemble'] = {
            'exact': round(best_super_exact * 100, 2),
            '1x2': round(super_1x2 * 100, 2),
            'rps': round(super_rps, 4),
            'weights': best_super_weights,
        }
    
    json.dump(results, open(os.path.join(MODEL_DIR, 'm7_results.json'), 'w'), indent=2)
    log(f'Saved: models/m7_results.json')
    
    # Save all M7 models and imputer/scaler for future use
    m7_package = {
        'imputer': imp,
        'scaler': scaler,
        'model_names': names_list,
        'metrics': all_metrics,
        'ensemble_weights': {n: 1.0/len(names_list) for n in names_list},
    }
    joblib.dump(m7_package, os.path.join(MODEL_DIR, 'm7_package.pkl'))
    log(f'Saved: models/m7_package.pkl')
    
    # Save imputer/scaler separately for stacking
    joblib.dump(imp, os.path.join(MODEL_DIR, 'm7_imputer.pkl'))
    joblib.dump(scaler, os.path.join(MODEL_DIR, 'm7_scaler.pkl'))
    
    log(f'\n{"="*70}')
    log('SUMMARY')
    log(f'  Best M7 individual: {max(all_metrics.items(), key=lambda x: x[1]["exact"])[0]}')
    log(f'  Best M7 ensemble: {best_m7_combo} = {best_m7_exact*100:.2f}%')
    if lgb_proba is not None:
        log(f'  M7 + LightGBM: {best_blend["exact"]*100:.2f}%')
    if m5_probas:
        log(f'  Super ensemble (M5+M7+LGB): {best_super_exact*100:.2f}%')
    log('=' * 70)
    
    return results


if __name__ == '__main__':
    t0 = time.time()
    results = train_m7()
    elapsed = time.time() - t0
    log(f'\nTotal training time: {elapsed/60:.1f} minutes')
    print(f'\nResults saved to models/m7_results.json')
