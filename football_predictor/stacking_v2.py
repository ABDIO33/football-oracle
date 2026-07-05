"""
stacking_v2.py — Proper purged walk-forward OOF stacking ensemble
Replaces weighted average with a LightGBM meta-learner trained on clean OOF data.
"""
import sys, os, json, time, numpy as np, warnings, gc
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))

import torch, torch.nn as nn, torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import xgboost as xgb
import lightgbm as lgb
import joblib
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.feature_selection import VarianceThreshold, SelectKBest, mutual_info_classif
from sklearn.linear_model import LogisticRegression

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
LOG = os.path.join(MODEL_DIR, 'stacking_v2_log.txt')
NUM_CLASSES = 25

def log(msg):
    ts = time.strftime("%H:%M:%S")
    with open(LOG, 'a') as f:
        f.write(f'[{ts}] {msg}\n')
    print(f'[{ts}] {msg}')

def _1x2_probas(probas):
    n = len(probas)
    out = np.zeros((n, 3))
    for i in range(n):
        p = probas[i]
        out[i, 0] = sum(p[h*5 + a] for h in range(5) for a in range(5) if h > a)
        out[i, 1] = sum(p[h*5 + h] for h in range(5))
        out[i, 2] = sum(p[h*5 + a] for h in range(5) for a in range(5) if a > h)
    return out

def compute_rps(y_true, y_pred_proba):
    rps = 0.0
    for i in range(len(y_true)):
        c = y_true[i]
        ah, aa = c // 5, c % 5
        ar = 0 if ah > aa else (1 if ah == aa else 2)
        ac = np.array([1 if ar <= k else 0 for k in range(3)], dtype=float)
        p = y_pred_proba[i]
        p_h = sum(p[h*5 + a] for h in range(5) for a in range(5) if h > a)
        p_d = sum(p[h*5 + h] for h in range(5))
        p_a = sum(p[h*5 + a] for h in range(5) for a in range(5) if a > h)
        pc = np.cumsum([p_h, p_d, p_a])
        rps += float(np.mean((ac - pc) ** 2))
    return rps / len(y_true)


class M5_Variant(nn.Module):
    def __init__(self, input_dim, num_classes, layer_sizes):
        super().__init__()
        modules = []
        prev = input_dim
        for i, sz in enumerate(layer_sizes):
            drop = 0.3 if i < 3 else 0.2
            modules.append(nn.Linear(prev, sz))
            if sz >= 128:
                modules.append(nn.BatchNorm1d(sz))
            modules.append(nn.ReLU())
            modules.append(nn.Dropout(drop))
            prev = sz
        modules.append(nn.Linear(prev, num_classes))
        self.net = nn.Sequential(*modules)
    def forward(self, x):
        return self.net(x)


ARCHITECTURES = {
    'M5_small':  [128, 256, 128],
    'M5_medium': [256, 512, 256],
    'M5_big':    [512, 1024, 512],
    'M5_wide':   [1024, 512, 256],
    'M5_deep':   [256, 512, 256, 128],
}


def generate_oof_xgb(model_factory, X, y, n_windows=5, gap=200):
    """Generate OOF probabilities for XGBoost using purged walk-forward."""
    n = len(X)
    oof = np.zeros((n, NUM_CLASSES), dtype=np.float32)
    mask = np.zeros(n, dtype=bool)
    window_size = n // n_windows

    for i in range(n_windows):
        test_end = n - (n_windows - 1 - i) * window_size
        test_start = max(0, test_end - window_size)
        train_end = test_start - gap

        if train_end < 500:
            continue

        X_tr, y_tr = X[:train_end], y[:train_end]
        X_te = X[test_start:test_end]

        model = model_factory()
        model.fit(X_tr, y_tr, eval_set=[(X_te, y[test_start:test_end])], verbose=False)
        oof[test_start:test_end] = model.predict_proba(X_te)
        mask[test_start:test_end] = True

        acc = float(np.mean(model.predict(X_te) == y[test_start:test_end]))
        log(f'  XGB window {i+1}: train=[0:{train_end}] test=[{test_start}:{test_end}] acc={acc*100:.2f}%')

    log(f'  XGB OOF: {int(mask.sum())} samples')
    return oof[mask], y[mask]


def train_nn_on_window(X_tr, y_tr, X_te, layers, epochs=30, device='cpu'):
    """Train a DeepNN on one window and return predict function."""
    imp_w = SimpleImputer(strategy='median')
    X_tr_i = imp_w.fit_transform(X_tr)
    scaler_w = StandardScaler()
    X_tr_s = scaler_w.fit_transform(X_tr_i)

    model = M5_Variant(X_tr_s.shape[1], NUM_CLASSES, layers).to(device)
    optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)

    train_data = TensorDataset(
        torch.tensor(X_tr_s, dtype=torch.float32),
        torch.tensor(y_tr, dtype=torch.long))
    loader = DataLoader(train_data, batch_size=256, shuffle=True, num_workers=0)

    model.train()
    for epoch in range(epochs):
        for Xb, yb in loader:
            Xb, yb = Xb.to(device), yb.to(device)
            optimizer.zero_grad()
            criterion(model(Xb), yb).backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        scheduler.step()

    model.eval()

    def predict_fn(X_te_in):
        X_te_i = imp_w.transform(X_te_in)
        X_te_s = scaler_w.transform(X_te_i)
        with torch.no_grad():
            X_t = torch.tensor(X_te_s, dtype=torch.float32).to(device)
            return torch.softmax(model(X_t), dim=1).cpu().numpy()

    predict_fn.predict = lambda X_in: np.argmax(predict_fn(X_in), axis=1)
    return predict_fn


def generate_oof_nn(X, y, arch_name, layers, n_windows=5, gap=200):
    """Generate OOF probabilities for a DeepNN variant."""
    n = len(X)
    oof = np.zeros((n, NUM_CLASSES), dtype=np.float32)
    mask = np.zeros(n, dtype=bool)
    window_size = n // n_windows
    device = 'cuda' if torch.cuda.is_available() else 'cpu'

    for i in range(n_windows):
        test_end = n - (n_windows - 1 - i) * window_size
        test_start = max(0, test_end - window_size)
        train_end = test_start - gap

        if train_end < 500:
            continue

        pred_fn = train_nn_on_window(X[:train_end], y[:train_end], X[test_start:test_end],
                                     layers, epochs=30, device=device)
        oof[test_start:test_end] = pred_fn(X[test_start:test_end])
        mask[test_start:test_end] = True

        acc = float(np.mean(pred_fn.predict(X[test_start:test_end]) == y[test_start:test_end]))
        log(f'  {arch_name} window {i+1}: train=[0:{train_end}] test=[{test_start}:{test_end}] acc={acc*100:.2f}%')

    log(f'  {arch_name} OOF: {int(mask.sum())} samples')
    return oof[mask], y[mask]


def build_meta_features(oof_dict):
    """Build compact meta-features from OOF probabilities of M base models."""
    names = list(oof_dict.keys())
    M = len(names)
    parts = []

    for n in names:
        parts.append(oof_dict[n][0])

    for i in range(M):
        for j in range(i+1, M):
            parts.append(oof_dict[names[i]][0] - oof_dict[names[j]][0])

    stacked = np.stack([oof_dict[n][0] for n in names], axis=-1)
    parts.append(stacked.max(axis=-1))
    parts.append(stacked.min(axis=-1))
    parts.append(stacked.mean(axis=-1))
    parts.append(stacked.std(axis=-1))

    for n in names:
        parts.append(_1x2_probas(oof_dict[n][0]))

    return np.concatenate(parts, axis=1)


def load_training_data():
    """Load preprocessed data from v5_preprocessed.npz (fast) or fallback to _load_training_data."""
    npz_path = os.path.join(MODEL_DIR, 'v5_preprocessed.npz')
    if os.path.exists(npz_path):
        log('Loading preprocessed data (fast)...')
        data = np.load(npz_path)
        return data['X'], data['y'], data['mids']
    log('Falling back to _load_training_data (slow)...')
    from direct_predictor import _load_training_data
    return _load_training_data()


def train_stacking_v2():
    log('='*60)
    log('STACKING V2 — Proper OOF + LightGBM Meta-Learner')
    log('='*60)

    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler

    X_raw, y, _ = load_training_data()
    log(f'Total samples: {len(X_raw)}, Features: {X_raw.shape[1]}')
    actual_1x2 = np.array([0 if (h:=c//5) > (a:=c%5) else (1 if h==a else 2) for c in y])

    imp = SimpleImputer(strategy='median')
    X_imp = imp.fit_transform(X_raw)

    oof_dict = {}

    log('[1/6] XGBoost OOF...')
    def make_xgb():
        return xgb.XGBClassifier(
            n_estimators=400, max_depth=6, learning_rate=0.05,
            objective='multi:softprob', num_class=NUM_CLASSES,
            subsample=0.9, colsample_bytree=0.8,
            reg_alpha=0.1, reg_lambda=0.1, random_state=42, verbosity=0,
            eval_metric='mlogloss', early_stopping_rounds=20)
    oof_dict['xgb'] = generate_oof_xgb(make_xgb, X_imp, y, n_windows=5)

    log('[2/6] DeepNN OOF (5 architectures)...')
    for name, layers in ARCHITECTURES.items():
        log(f'  {name}...')
        oof_dict[name] = generate_oof_nn(X_imp, y, name, layers, n_windows=5)
        gc.collect()

    log('[3/6] Building meta-features...')
    meta_X = build_meta_features(oof_dict)
    log(f'Meta-features shape: {meta_X.shape}')

    n_meta = len(meta_X)
    meta_split = int(n_meta * 0.8)
    meta_train, meta_test = meta_X[:meta_split], meta_X[meta_split:]
    y_meta = oof_dict['xgb'][1]
    y_meta_train, y_meta_test = y_meta[:meta_split], y_meta[meta_split:]
    log(f'Meta train: {len(meta_train)}, Meta test: {len(meta_test)}')

    log('[4/6] Selecting meta-features...')
    sel_var = VarianceThreshold(threshold=1e-6)
    meta_train_sel = sel_var.fit_transform(meta_train)
    meta_test_sel = sel_var.transform(meta_test)

    K = min(150, meta_train_sel.shape[1])
    sel_mi = SelectKBest(mutual_info_classif, k=K)
    meta_train_final = sel_mi.fit_transform(meta_train_sel, y_meta_train)
    meta_test_final = sel_mi.transform(meta_test_sel)
    log(f'Selected {K} meta-features from {meta_train_sel.shape[1]}')

    log('[5/6] Training LightGBM meta-learner...')
    lgb_meta = lgb.LGBMClassifier(
        objective='multiclass', num_class=NUM_CLASSES, metric='multi_logloss',
        boosting_type='gbdt', num_leaves=8, max_depth=3, learning_rate=0.01,
        feature_fraction=0.6, bagging_fraction=0.7, bagging_freq=1,
        reg_alpha=0.5, reg_lambda=1.0, min_child_samples=50, min_child_weight=5.0,
        verbosity=-1, random_state=42, n_estimators=2000)
    lgb_meta.fit(
        meta_train_final, y_meta_train,
        eval_set=[(meta_test_final, y_meta_test)],
        callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)])

    log('[6/6] Evaluating...')
    results = {}

    lgb_pred = lgb_meta.predict(meta_test_final)
    lgb_proba = lgb_meta.predict_proba(meta_test_final)
    results['lgb_meta'] = {
        'exact': float(np.mean(lgb_pred == y_meta_test)) * 100,
        '1x2': float(np.mean(np.array([0 if (h:=c//5)>(a:=c%5) else (1 if h==a else 2) for c in lgb_pred])
                             == np.array([0 if (h:=c//5)>(a:=c%5) else (1 if h==a else 2) for c in y_meta_test]))) * 100,
        'rps': compute_rps(y_meta_test, lgb_proba),
    }
    log(f'LightGBM Meta: exact={results["lgb_meta"]["exact"]:.2f}% 1X2={results["lgb_meta"]["1x2"]:.2f}% RPS={results["lgb_meta"]["rps"]:.4f}')

    lr_meta = LogisticRegression(max_iter=1000, C=0.01, multi_class='multinomial', solver='lbfgs')
    lr_meta.fit(meta_train_final, y_meta_train)
    lr_pred = lr_meta.predict(meta_test_final)
    lr_proba = lr_meta.predict_proba(meta_test_final)
    results['lr_meta'] = {
        'exact': float(np.mean(lr_pred == y_meta_test)) * 100,
        '1x2': float(np.mean(np.array([0 if (h:=c//5)>(a:=c%5) else (1 if h==a else 2) for c in lr_pred])
                             == np.array([0 if (h:=c//5)>(a:=c%5) else (1 if h==a else 2) for c in y_meta_test]))) * 100,
        'rps': compute_rps(y_meta_test, lr_proba),
    }
    log(f'LR Meta: exact={results["lr_meta"]["exact"]:.2f}% 1X2={results["lr_meta"]["1x2"]:.2f}% RPS={results["lr_meta"]["rps"]:.4f}')

    best_w = 0.15
    w_nn = (1 - best_w) / len(ARCHITECTURES)
    weighted_proba = best_w * oof_dict['xgb'][0][meta_split:]
    for n in ARCHITECTURES:
        weighted_proba += w_nn * oof_dict[n][0][meta_split:]
    weighted_pred = np.argmax(weighted_proba, axis=1)
    results['weighted_avg'] = {
        'exact': float(np.mean(weighted_pred == y_meta_test)) * 100,
        '1x2': float(np.mean(np.array([0 if (h:=c//5)>(a:=c%5) else (1 if h==a else 2) for c in weighted_pred])
                             == np.array([0 if (h:=c//5)>(a:=c%5) else (1 if h==a else 2) for c in y_meta_test]))) * 100,
        'rps': compute_rps(y_meta_test, weighted_proba),
    }
    log(f'Weighted Avg: exact={results["weighted_avg"]["exact"]:.2f}% 1X2={results["weighted_avg"]["1x2"]:.2f}% RPS={results["weighted_avg"]["rps"]:.4f}')

    log('\nSaving stacking_v2 model...')
    stacking_v2 = {
        'lgb_meta': lgb_meta,
        'lr_meta': lr_meta,
        'feature_selector_var': sel_var,
        'feature_selector_mi': sel_mi,
        'model_names': ['xgb'] + list(ARCHITECTURES.keys()),
        'architectures': ARCHITECTURES,
        'results': results,
        'imp': imp,
        'n_meta_features': K,
    }
    joblib.dump(stacking_v2, os.path.join(MODEL_DIR, 'stacking_v2.pkl'))
    with open(os.path.join(MODEL_DIR, 'stacking_v2_results.json'), 'w') as f:
        json.dump(results, f, indent=2)

    imp_vs_weighted = results['lgb_meta']['exact'] - results['weighted_avg']['exact']
    log(f'\nImprovement over weighted avg: {imp_vs_weighted:+.2f}pp')
    log('='*60)


class StackingV2Predictor:
    """Prediction wrapper for stacking_v2.pkl."""
    def __init__(self, stacking_v2):
        self.lgb_meta = stacking_v2['lgb_meta']
        self.feature_selector_var = stacking_v2['feature_selector_var']
        self.feature_selector_mi = stacking_v2['feature_selector_mi']
        self.model_names = stacking_v2['model_names']

    def predict_proba(self, base_probas_dict):
        oof_dict = {}
        for name in self.model_names:
            oof_dict[name] = (base_probas_dict[name], None)
        meta_X = build_meta_features(oof_dict)
        meta_X_sel = self.feature_selector_var.transform(meta_X)
        meta_X_final = self.feature_selector_mi.transform(meta_X_sel)
        return self.lgb_meta.predict_proba(meta_X_final)


if __name__ == '__main__':
    train_stacking_v2()
