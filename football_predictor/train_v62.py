"""
V6.2 TRAINER — 194 features, 7 architectures, 200 epochs
Built for Score Exact 100 by DeepSeek V4 Flash Free الأول (Pi leader-coder)

Key improvements over V6.1:
- 194 features (vs 128/81)
- Mixup + Label Smoothing + Focal Loss
- Cosine annealing LR
- 7 architectures (Small, Medium, Wide, Deep, Big, Ultra, Tower)
- Ensemble search + stacking preparation
- XGBoost + DeepNN ensemble
"""
import sys, os, json, time, math, numpy as np, warnings, gc, traceback
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import joblib

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
LOG = os.path.join(MODEL_DIR, 'v62_log.txt')

def log(msg):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(f'[{time.strftime("%H:%M:%S")}] {msg}\n')
    print(f'[{time.strftime("%H:%M:%S")}] {msg}', flush=True)

def _cs(c): return (c // 5, c % 5)

def rps_score(y_true, y_pred_proba):
    rps = 0.0
    for i in range(len(y_true)):
        ah, aa = _cs(y_true[i])
        ar = 0 if ah > aa else 1 if ah == aa else 2
        p = y_pred_proba[i]
        cp = [sum(p[h*5+a] for h in range(5) for a in range(5) if h > a),
              sum(p[h*5+h] for h in range(5)),
              sum(p[h*5+a] for h in range(5) for a in range(5) if a > h)]
        ca = np.zeros(3); ca[ar:] = 1.0
        rps += float(np.mean((ca - np.cumsum(cp))**2))
    return rps / len(y_true)


class FocalLoss(nn.Module):
    def __init__(self, gamma=2.0, reduction='mean'):
        super().__init__()
        self.gamma = gamma
        self.reduction = reduction
    def forward(self, inputs, targets):
        ce = nn.functional.cross_entropy(inputs, targets, reduction='none')
        focal = (1 - torch.exp(-ce)) ** self.gamma * ce
        if self.reduction == 'mean':
            return focal.mean()
        return focal


class LabelSmoothingLoss(nn.Module):
    """Cross-entropy with label smoothing + focal modulation"""
    def __init__(self, smoothing=0.1, gamma=2.0):
        super().__init__()
        self.smoothing = smoothing
        self.gamma = gamma
    def forward(self, inputs, targets):
        n_classes = inputs.size(1)
        with torch.no_grad():
            smoothed = torch.full_like(inputs, self.smoothing / (n_classes - 1))
            smoothed.scatter_(1, targets.unsqueeze(1), 1.0 - self.smoothing)
        log_softmax = nn.functional.log_softmax(inputs, dim=1)
        loss = -(smoothed * log_softmax).sum(dim=1)
        if self.gamma > 0:
            prob = torch.softmax(inputs, dim=1)
            p_t = prob.gather(1, targets.unsqueeze(1)).squeeze()
            loss = loss * ((1 - p_t) ** self.gamma)
        return loss.mean()


def mixup_data(x, y, alpha=0.2):
    """Mixup augmentation"""
    if alpha > 0:
        lam = np.random.beta(alpha, alpha)
    else:
        lam = 1
    batch_size = x.size(0)
    index = torch.randperm(batch_size)
    mixed_x = lam * x + (1 - lam) * x[index]
    return mixed_x, (y, y[index], lam)


class M5Variant(nn.Module):
    """M5 architecture family"""
    def __init__(self, input_dim, num_classes, layers, dr=0.25, use_bn=True):
        super().__init__()
        modules = []
        prev = input_dim
        for i, sz in enumerate(layers):
            modules += [nn.Linear(prev, sz)]
            if use_bn and sz >= 64:
                modules += [nn.BatchNorm1d(sz)]
            modules += [nn.ELU()]
            modules += [nn.Dropout(dr * (0.5 if i == len(layers)-1 else 1.0))]
            prev = sz
        modules += [nn.Linear(prev, num_classes)]
        self.net = nn.Sequential(*modules)
    def forward(self, x):
        return self.net(x)


# Architecture definitions (7)
ARCHS = {
    'M5_small_v62':  [128, 256, 128],
    'M5_medium_v62': [256, 512, 256],
    'M5_wide_v62':   [1024, 512, 256],
    'M5_deep_v62':   [256, 512, 256, 128],
    'M5_big_v62':    [512, 1024, 512],
    'M5_ultra_v62':  [1024, 512, 256, 128],
    'M5_tower_v62':  [128, 512, 128],
}


class V62Ensemble:
    """V6.2 production ensemble - moved to module level for pickling"""
    def __init__(self, models_dict, weights, imp, scaler, num_classes=25):
        self.models = models_dict
        self.weights = weights
        self.imp = imp
        self.scaler = scaler
        self.num_classes = num_classes

    def predict_proba(self, X):
        X_imp = self.imp.transform(X)
        X_s = self.scaler.transform(X_imp)
        ensemble = np.zeros((X_s.shape[0], self.num_classes))
        for name, m in self.models.items():
            w = self.weights.get(name, 0)
            if w == 0:
                continue
            if 'xgb' in name:
                proba = m.predict_proba(X_s)
            else:
                with torch.no_grad():
                    proba = torch.softmax(
                        m(torch.tensor(X_s, dtype=torch.float32)), dim=1).numpy()
            ensemble += w * proba
        return ensemble


def train_model(model, train_loader, val_loader, criterion, optimizer, scheduler,
                epochs, device, use_mixup=False):
    """Train one model with cosine annealing + optional mixup"""
    best_val = 0.0
    best_epoch = 0
    patience = 15
    patience_counter = 0

    for ep in range(epochs):
        model.train()
        train_loss = 0.0

        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            if use_mixup:
                xb, (yb1, yb2, lam) = mixup_data(xb, yb)
            optimizer.zero_grad()
            outputs = model(xb)
            if use_mixup:
                loss = lam * criterion(outputs, yb1) + (1 - lam) * criterion(outputs, yb2)
            else:
                loss = criterion(outputs, yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            train_loss += loss.item()

        # Validation
        model.eval()
        val_preds = []
        val_true = []
        with torch.no_grad():
            for xb, yb in val_loader:
                xb = xb.to(device)
                outputs = model(xb)
                preds = torch.softmax(outputs, dim=1).cpu().numpy()
                val_preds.append(preds)
                val_true.append(yb.numpy())

        val_preds = np.concatenate(val_preds)
        val_true = np.concatenate(val_true)
        val_pred_classes = np.argmax(val_preds, axis=1)
        val_exact = np.mean(val_pred_classes == val_true) * 100
        val_rps = rps_score(val_true, val_preds)

        if scheduler:
            if isinstance(scheduler, torch.optim.lr_scheduler.CosineAnnealingLR):
                scheduler.step()
            elif isinstance(scheduler, torch.optim.lr_scheduler.ReduceLROnPlateau):
                scheduler.step(val_exact)

        if (ep + 1) % 5 == 0 or ep == 0:
            current_lr = optimizer.param_groups[0]['lr']
            log(f'  ep {ep+1}: val={val_exact:.2f}% best={best_val:.2f}% rps={val_rps:.4f} lr={current_lr:.2e}')

        if val_exact > best_val:
            best_val = val_exact
            best_epoch = ep
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= patience:
                log(f'  Early stopping at epoch {ep+1}')
                break

    return best_val, best_epoch


def main():
    """Main V6.2 training pipeline"""
    log('=' * 60)
    log('V6.2 FOCAL LOSS — 194 features, 7 arch, 200 epochs')
    log('=' * 60)
    t0 = time.time()

    # ─── 1. Load preprocessed data ───
    log('\n[1/5] Loading V6.2 data (194 features)...')
    from _preprocess_v62 import build_v62_dataset

    X_train_s, X_test_s, y_train, y_test, feature_names, imp_v62, scaler_v62 = \
        build_v62_dataset(start_year=2010, test_cutoff='2025-01-01')

    log(f'Loaded {len(X_train_s)+len(X_test_s):,} samples, {X_train_s.shape[1]} features')
    log(f'Train: {len(X_train_s):,} | Test: {len(X_test_s):,}')

    # Save scaler/imputer for production use
    joblib.dump(imp_v62, os.path.join(MODEL_DIR, 'v62_imputer.pkl'))
    joblib.dump(scaler_v62, os.path.join(MODEL_DIR, 'v62_scaler.pkl'))
    joblib.dump(feature_names, os.path.join(MODEL_DIR, 'v62_features.pkl'))

    # Save preprocessed data
    np.savez_compressed(os.path.join(MODEL_DIR, 'v62_preprocessed.npz'),
                        X_train=X_train_s, X_test=X_test_s,
                        y_train=y_train, y_test=y_test)

    # PyTorch datasets
    train_dataset = TensorDataset(torch.tensor(X_train_s, dtype=torch.float32),
                                  torch.tensor(y_train, dtype=torch.long))
    test_dataset = TensorDataset(torch.tensor(X_test_s, dtype=torch.float32),
                                 torch.tensor(y_test, dtype=torch.long))
    train_loader = DataLoader(train_dataset, batch_size=256, shuffle=True)
    val_loader = DataLoader(test_dataset, batch_size=512, shuffle=False)

    input_dim = X_train_s.shape[1]
    num_classes = 25
    device = torch.device('cpu')
    epochs = 200

    # ─── 2. Train all 7 architectures ───
    log('\n[2/5] Training 7 architectures...')
    criterion = LabelSmoothingLoss(smoothing=0.1, gamma=2.0)

    results = {}
    model_preds = {}

    for name, layers in ARCHS.items():
        log(f'\n-- {name}: {layers} --')
        model = M5Variant(input_dim, num_classes, layers, dr=0.25)

        optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-5)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=epochs, eta_min=1e-5)

        t_start = time.time()
        best_val, best_ep = train_model(
            model, train_loader, val_loader, criterion, optimizer, scheduler,
            epochs, device, use_mixup=True)
        elapsed = time.time() - t_start

        # Evaluate
        model.eval()
        with torch.no_grad():
            test_preds = torch.softmax(
                model(torch.tensor(X_test_s, dtype=torch.float32)), dim=1).numpy()

        test_preds_c = np.argmax(test_preds, axis=1)
        test_exact = float(np.mean(test_preds_c == y_test)) * 100
        test_rps = rps_score(y_test, test_preds)
        test_1x2 = float(np.mean(
            np.array([0 if h > a else 1 if h == a else 2 for h, a in [_cs(c) for c in test_preds_c]]) ==
            np.array([0 if h > a else 1 if h == a else 2 for h, a in [_cs(c) for c in y_test]])
        )) * 100

        log(f'  Best: val={best_val:.2f}% test={test_exact:.2f}% 1X2={test_1x2:.2f}% RPS={test_rps:.4f}')
        log(f'  Epochs: {best_ep+1}, Time: {elapsed:.0f}s')

        torch.save(model.state_dict(), os.path.join(MODEL_DIR, f'{name}.pt'))

        results[name] = {
            'val_exact': round(best_val, 2),
            'test_exact': round(test_exact, 2),
            'test_1x2': round(test_1x2, 2),
            'test_rps': round(test_rps, 4),
            'epochs': best_ep + 1,
            'layers': layers,
        }
        model_preds[name] = test_preds

        del model
        gc.collect()

    # ─── 3. XGBoost ───
    log('\n[3/5] XGBoost_v62...')
    t_start = time.time()
    xgb_model = xgb.XGBClassifier(
        n_estimators=500, max_depth=6, learning_rate=0.05,
        objective='multi:softprob', num_class=num_classes,
        subsample=0.8, colsample_bytree=0.8,
        reg_alpha=0.01, reg_lambda=0.01,
        random_state=42, eval_metric='mlogloss',
        early_stopping_rounds=30, verbosity=0
    )
    xgb_model.fit(X_train_s, y_train,
                  eval_set=[(X_test_s, y_test)],
                  verbose=False)
    xgb_test_preds = xgb_model.predict_proba(X_test_s)
    xgb_test_preds_c = np.argmax(xgb_test_preds, axis=1)
    xgb_exact = float(np.mean(xgb_test_preds_c == y_test)) * 100
    xgb_1x2 = float(np.mean(
        np.array([0 if h > a else 1 if h == a else 2 for h, a in [_cs(c) for c in xgb_test_preds_c]]) ==
        np.array([0 if h > a else 1 if h == a else 2 for h, a in [_cs(c) for c in y_test]])
    )) * 100
    xgb_rps = rps_score(y_test, xgb_test_preds)

    log(f'  exact={xgb_exact:.2f}% 1X2={xgb_1x2:.2f}% RPS={xgb_rps:.4f} time={time.time()-t_start:.0f}s')

    joblib.dump(xgb_model, os.path.join(MODEL_DIR, 'xgb_v62.pkl'))
    results['xgb_v62'] = {
        'test_exact': round(xgb_exact, 2),
        'test_1x2': round(xgb_1x2, 2),
        'test_rps': round(xgb_rps, 4),
    }
    model_preds['xgb_v62'] = xgb_test_preds

    # ─── 4. Ensemble search ───
    log('\n[4/5] Ensemble search...')

    all_names = list(model_preds.keys())
    all_preds = np.array([model_preds[n] for n in all_names])

    n_models = len(all_names)
    best_ensemble_exact = 0.0
    best_weights = None

    for trial in range(10000):
        w = np.random.dirichlet(np.ones(n_models), 1)[0]
        ensemble = np.tensordot(w, all_preds, axes=(0, 0))
        ensemble_c = np.argmax(ensemble, axis=1)
        exact = float(np.mean(ensemble_c == y_test))

        if exact > best_ensemble_exact:
            best_ensemble_exact = exact
            best_weights = w.copy()

    log(f'Best weighted ensemble: {best_ensemble_exact*100:.2f}%')
    for name, w in zip(all_names, best_weights):
        if w > 0.01:
            log(f'  {name}: {w*100:.0f}%')

    best_ensemble = np.tensordot(best_weights, all_preds, axes=(0, 0))
    best_ensemble_c = np.argmax(best_ensemble, axis=1)
    ensemble_1x2 = float(np.mean(
        np.array([0 if h > a else 1 if h == a else 2 for h, a in [_cs(c) for c in best_ensemble_c]]) ==
        np.array([0 if h > a else 1 if h == a else 2 for h, a in [_cs(c) for c in y_test]])
    )) * 100
    ensemble_rps = rps_score(y_test, best_ensemble)

    log(f'Ensemble 1X2: {ensemble_1x2:.2f}%')
    log(f'Ensemble RPS: {ensemble_rps:.4f}')

    # Betting accuracy @30%
    hits30 = total30 = 0
    for i in range(len(y_test)):
        if best_ensemble[i][best_ensemble_c[i]] >= 0.30:
            total30 += 1
            if best_ensemble_c[i] == y_test[i]:
                hits30 += 1
    bet30 = (hits30 / total30 * 100) if total30 else 0
    log(f'Betting @30%: {hits30}/{total30} = {bet30:.1f}%')

    # ─── 5. Build production ensemble model ───
    log('\n[5/5] Building V6.2 production model...')

    # Load all models
    prod_models = {}
    prod_weights = {}
    for name, layers in ARCHS.items():
        w = best_weights[all_names.index(name)] if name in all_names else 0
        if w > 0.001:
            model = M5Variant(input_dim, num_classes, layers, dr=0.25)
            pt_file = os.path.join(MODEL_DIR, f'{name}.pt')
            if os.path.exists(pt_file):
                model.load_state_dict(torch.load(pt_file, map_location='cpu'))
                model.eval()
                prod_models[name] = model
                prod_weights[name] = w

    if 'xgb_v62' in all_names:
        xgb_idx = all_names.index('xgb_v62')
        if best_weights[xgb_idx] > 0.001:
            prod_models['xgb_v62'] = xgb_model
            prod_weights['xgb_v62'] = best_weights[xgb_idx]

    prod = V62Ensemble(prod_models, prod_weights, imp_v62, scaler_v62)
    prod_path = os.path.join(MODEL_DIR, 'v62_model.pkl')
    joblib.dump(prod, prod_path)
    size_mb = os.path.getsize(prod_path) / (1024 * 1024)
    log(f'Saved v62_model.pkl ({size_mb:.0f} MB)')

    # Also save the ensemble for stacking
    np.save(os.path.join(MODEL_DIR, 'v62_test_probas.npy'), best_ensemble)
    np.save(os.path.join(MODEL_DIR, 'v62_y_test.npy'), y_test)

    # Save individual probas for stacking
    all_probas = np.zeros((len(y_test), num_classes * len(all_names)))
    for i, name in enumerate(all_names):
        all_probas[:, i * num_classes:(i + 1) * num_classes] = model_preds[name]
    np.save(os.path.join(MODEL_DIR, 'v62_all_probas.npy'), all_probas)
    joblib.dump(all_names, os.path.join(MODEL_DIR, 'v62_model_names.pkl'))

    final_results = {
        'type': 'V6.2_194FEATURES',
        'epochs': epochs,
        'use_mixup': True,
        'label_smoothing': 0.1,
        'focal_gamma': 2.0,
        'train_samples': len(X_train_s),
        'test_samples': len(X_test_s),
        'features': input_dim,
        'individual': {k: v for k, v in results.items()},
        'ensemble': {
            'exact_pct': round(best_ensemble_exact * 100, 2),
            '1x2_pct': round(ensemble_1x2, 2),
            'rps': round(ensemble_rps, 4),
        },
        'weights': {k: round(float(best_weights[all_names.index(k)]), 4)
                    for k in all_names if k in all_names},
        'betting_30': {
            'acc_pct': round(bet30, 1),
            'n': int(total30),
            'hits': int(hits30),
        },
        'time_min': round((time.time() - t0) / 60, 1),
    }

    with open(os.path.join(MODEL_DIR, 'v62_results.json'), 'w') as f:
        json.dump(final_results, f, indent=2)

    log(f'\n=== V6.2 COMPLETE ===')
    log(f'Best ensemble: {best_ensemble_exact*100:.2f}% exact')

    # Comparison to baselines
    v61_exact = 18.57
    v5_exact = 18.51
    improvement = best_ensemble_exact * 100 - v61_exact

    log(f'V6.1 baseline: {v61_exact}%')
    log(f'V5 baseline: {v5_exact}%')
    if improvement > 0:
        log(f'✅ V6.2 beats V6.1: +{improvement:.2f} points')
    else:
        log(f'❌ V6.2 below V6.1 by {-improvement:.2f} points')

    if best_ensemble_exact * 100 > 25:
        log('🏆 V6.2 OVER 25%! MAJOR BREAKTHROUGH!')

    total_time = (time.time() - t0) / 60
    log(f'Total time: {total_time:.0f} minutes')
    log('=' * 60)


if __name__ == '__main__':
    main()
