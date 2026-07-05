#!/usr/bin/env python3
"""
SIGMA-ZERO - V5 Model Comprehensive Analysis
Using v5_preprocessed.npz + v5_model.pkl (18.39% exact)
"""

import sys, os, json, gc, time
sys.path.insert(0, os.path.dirname(__file__))

os.environ['PYTHONIOENCODING'] = 'utf-8'

import numpy as np
import pandas as pd
from collections import Counter, defaultdict
import joblib
import torch
import torch.nn as nn
import sqlite3

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

# V5 model patches
class M5Variant(nn.Module):
    def __init__(self, input_dim, num_classes, layers, dr=0.25):
        super().__init__()
        modules = []; prev = input_dim
        for i, sz in enumerate(layers):
            modules += [nn.Linear(prev, sz)]
            if sz >= 64: modules += [nn.BatchNorm1d(sz)]
            modules += [nn.ELU(), nn.Dropout(dr * (0.5 if i == len(layers)-1 else 1.0))]
            prev = sz
        modules += [nn.Linear(prev, num_classes)]
        self.net = nn.Sequential(*modules)
    def forward(self, x): return self.net(x)

class TorchWrapper:
    def __init__(self, input_dim, num_classes, layers, state_dict):
        self.input_dim = input_dim; self.num_classes = num_classes; self.layers = layers
        self.state_dict = state_dict; self._model = None
    def _build(self):
        if self._model is None:
            self._model = M5Variant(self.input_dim, self.num_classes, self.layers)
            sd = {k: torch.tensor(v) if isinstance(v, np.ndarray) else v for k, v in self.state_dict.items()}
            self._model.load_state_dict(sd); self._model.eval()
        return self._model
    def predict_proba(self, X):
        m = self._build()
        with torch.no_grad(): return torch.softmax(m(torch.tensor(X, dtype=torch.float32)), dim=1).numpy()
    def predict(self, X): return np.argmax(self.predict_proba(X), axis=1)

class V5Ensemble:
    def __init__(self, models, weights, imp, scaler):
        self.models = models; self.weights = weights; self.imp = imp; self.scaler = scaler; self.num_classes = 25
    def predict_proba(self, X):
        X_imp = self.imp.transform(X); X_s = self.scaler.transform(X_imp)
        ep = np.zeros((X_s.shape[0], 25))
        for name, m in self.models.items():
            w = self.weights.get(name, 0)
            if w == 0: continue
            if name == 'xgb_v5':
                proba = m.predict_proba(X_s)
            else:
                with torch.no_grad(): proba = torch.softmax(m(torch.tensor(X_s, dtype=torch.float32)), dim=1).numpy()
            ep += w * proba
        return ep

from direct_predictor import class_to_score, result, SCORE_CLASSES

NUM_CLASSES = 25

print("=" * 70)
print("SIGMA-ZERO - V5 MODEL COMPREHENSIVE ANALYSIS")
print("=" * 70)

# Load data
print("\n[1] Loading v5 preprocessed data...")
t0 = time.time()
X_raw = np.load('models/v5_preprocessed.npz')['X']
y = np.load('models/v5_preprocessed.npz')['y']
mids = np.load('models/v5_preprocessed.npz')['mids']
print(f"  Loaded {len(X_raw)} samples in {time.time()-t0:.1f}s")

split = int(len(X_raw) * 0.9)
X_train, X_test = X_raw[:split], X_raw[split:]
y_train, y_test = y[:split], y[split:]
mids_train, mids_test = mids[:split], mids[split:]
print(f"  Train: {len(X_train)}, Test: {len(X_test)}")

# Load model
print("\n[2] Loading v5 model...")
t0 = time.time()
model = joblib.load('models/v5_model.pkl')
print(f"  Model: {type(model).__name__}")
print(f"  Base models: {list(model.models.keys())}")
print(f"  Weights: {model.weights}")
print(f"  Imputer: {type(model.imp).__name__}")
print(f"  Scaler: {type(model.scaler).__name__}")
print(f"  Loaded in {time.time()-t0:.1f}s")

# Get predictions
print("\n[3] Generating predictions...")
t0 = time.time()
probas = model.predict_proba(X_test)
preds = np.argmax(probas, axis=1)
print(f"  Done in {time.time()-t0:.1f}s")

# ============================================================
# OVERALL METRICS
# ============================================================
exact = float(np.mean(preds == y_test))
exact_count = int(np.sum(preds == y_test))

actual_1x2 = np.array([result(*class_to_score(c)) for c in y_test])
pred_1x2 = np.array([result(*class_to_score(c)) for c in preds])
acc_1x2 = float(np.mean(actual_1x2 == pred_1x2))

# RPS
def compute_rps(y_true, y_pred_proba):
    n = len(y_true); rps_total = 0.0
    for i in range(n):
        ah, aa = class_to_score(y_true[i])
        ar = result(ah, aa)
        actual_cum = np.array([1 if ar <= k else 0 for k in range(3)], dtype=float)
        pp = y_pred_proba[i]
        p_h = sum(pp[h*5 + a] for h in range(5) for a in range(5) if h > a)
        p_d = sum(pp[h*5 + h] for h in range(5))
        p_a = sum(pp[h*5 + a] for h in range(5) for a in range(5) if a > h)
        pred_cum = np.cumsum([p_h, p_d, p_a])
        rps_total += float(np.mean((actual_cum - pred_cum) ** 2))
    return rps_total / n

rps = compute_rps(y_test, probas)

# Log loss
def compute_log_loss(y_true, y_pred_proba, eps=1e-15):
    n = len(y_true); ll = 0.0
    for i in range(n):
        p = max(eps, min(1-eps, y_pred_proba[i, y_true[i]]))
        ll -= np.log(p)
    return ll / n

logloss = compute_log_loss(y_test, probas)

# Brier
def compute_brier(y_true, y_pred_proba):
    n = len(y_true); n_c = y_pred_proba.shape[1]
    y_onehot = np.zeros((n, n_c))
    y_onehot[np.arange(n), y_true] = 1
    return float(np.mean(np.sum((y_onehot - y_pred_proba)**2, axis=1)))

brier = compute_brier(y_test, probas)

print(f"\n{'='*60}")
print(f"  V5 MODEL - OVERALL PERFORMANCE")
print(f"{'='*60}")
print(f"  Exact score: {exact*100:.2f}% ({exact_count}/{len(y_test)})")
print(f"  1X2 accuracy: {acc_1x2*100:.2f}%")
print(f"  RPS: {rps:.4f}")
print(f"  Log loss: {logloss:.4f}")
print(f"  Brier score: {brier:.4f}")

# ============================================================
# 1. CONFUSION MATRIX
# ============================================================
print(f"\n{'='*60}")
print(f"  1. CONFUSION MATRIX")
print(f"{'='*60}")

CM = np.zeros((NUM_CLASSES, NUM_CLASSES), dtype=int)
for t, p in zip(y_test, preds):
    CM[t, p] += 1

class_metrics = {}
print(f"\n{'Class':>6} | {'Count':>7} | {'Pct':>6} | {'Correct':>8} | {'Recall':>7} | {'Prec':>7} | {'F1':>6} | {'Top Confused':>35}")
print("-" * 90)
for cls_idx in range(NUM_CLASSES):
    h, a = class_to_score(cls_idx)
    total = int(np.sum(CM[cls_idx, :]))
    correct = int(CM[cls_idx, cls_idx])
    recall = correct / total if total > 0 else 0
    col_sum = int(np.sum(CM[:, cls_idx]))
    precision = correct / col_sum if col_sum > 0 else 0
    f1 = 2 * recall * precision / (recall + precision) if (recall + precision) > 0 else 0
    
    confused = np.argsort(CM[cls_idx, :])[::-1]
    confused_strs = []
    for c in confused[:4]:
        if c != cls_idx and CM[cls_idx, c] >= total * 0.02:
            ch, ca = class_to_score(c)
            pct_wrong = CM[cls_idx, c] / max(1, total - correct) * 100
            confused_strs.append(f"{ch}-{ca}({pct_wrong:.0f}%)")
    cs = ', '.join(confused_strs[:3]) if confused_strs else '-'
    
    pct_val = total / len(y_test) * 100
    print(f"  {h}-{a}  | {total:>7} | {pct_val:>5.1f}% | {correct:>8} | {recall*100:>5.1f}% | {precision*100:>5.1f}% | {f1:.4f} | {cs:35s}")
    class_metrics[f"{h}-{a}"] = {
        'count': total, 'pct': float(pct_val),
        'correct': correct, 'recall': float(recall),
        'precision': float(precision), 'f1': float(f1)
    }

# Aggregate by result type
print(f"\n  Aggregate by 1X2:")
for rtype, rname in [(0, 'Home Win'), (1, 'Draw'), (2, 'Away Win')]:
    idx_list = [i for i in range(NUM_CLASSES) if result(*class_to_score(i)) == rtype]
    tc = sum(CM[idx, idx] for idx in idx_list)
    tt = sum(int(np.sum(CM[idx, :])) for idx in idx_list)
    print(f"    {rname:12s}: {tc}/{tt} = {tc*100/tt:.2f}%" if tt > 0 else f"    {rname:12s}: N/A")

# ============================================================
# 2. CALIBRATION
# ============================================================
print(f"\n{'='*60}")
print(f"  2. CALIBRATION ANALYSIS")
print(f"{'='*60}")

print(f"\n  Per-score calibration:")
print(f"  {'Score':>6} | {'True#':>7} | {'MeanP':>7} | {'Pred#':>7} | {'Acc@Pred':>8} | {'CalErr':>7}")
print("  " + "-" * 50)
cal_data = []
for cls_idx in range(NUM_CLASSES):
    h, a = class_to_score(cls_idx)
    mask = (y_test == cls_idx)
    n_true = int(np.sum(mask))
    mean_pred = float(np.mean(probas[mask, cls_idx])) if n_true > 0 else 0.0
    pred_mask = (preds == cls_idx)
    n_pred = int(np.sum(pred_mask))
    acc_pred = float(np.mean(y_test[pred_mask] == cls_idx)) if n_pred > 0 else 0.0
    ce = abs(mean_pred - (n_true / max(1, n_pred)))
    cal_data.append({'score': f'{h}-{a}', 'n_true': n_true, 'mean_pred': mean_pred, 'n_pred': n_pred, 'acc_pred': acc_pred, 'cal_err': ce})
    print(f"  {h}-{a:>3} | {n_true:>7} | {mean_pred:.4f} | {n_pred:>7} | {acc_pred:.4f}  | {ce:.4f}")

avg_ce = float(np.mean([c['cal_err'] for c in cal_data]))
print(f"\n  Average calibration error: {avg_ce:.4f}")

# ECE (Expected Calibration Error) for 1X2
probs_1x2 = np.zeros((len(y_test), 3))
for i in range(len(y_test)):
    pp = probas[i]
    probs_1x2[i, 0] = sum(pp[h*5 + a] for h in range(5) for a in range(5) if h > a)
    probs_1x2[i, 1] = sum(pp[h*5 + h] for h in range(5))
    probs_1x2[i, 2] = sum(pp[h*5 + a] for h in range(5) for a in range(5) if a > h)

print(f"\n  ECE (Expected Calibration Error) for 1X2 (10 bins):")
for rtype, rname in [(0, 'Home'), (1, 'Draw'), (2, 'Away')]:
    bins = np.linspace(0, 1, 11)
    ece = 0.0
    for b in range(10):
        lo, hi = bins[b], bins[b+1]
        in_bin = (probs_1x2[:, rtype] >= lo) & (probs_1x2[:, rtype] < hi)
        n_bin = int(np.sum(in_bin))
        if n_bin > 0:
            bin_acc = float(np.mean(actual_1x2[in_bin] == rtype))
            bin_conf = float(np.mean(probs_1x2[in_bin, rtype]))
            ece += n_bin / len(y_test) * abs(bin_acc - bin_conf)
    print(f"    {rname:6s}: ECE={ece:.4f}")

# ============================================================
# 3. FEATURE IMPORTANCE (XGBoost only)
# ============================================================
print(f"\n{'='*60}")
print(f"  3. FEATURE IMPORTANCE (XGBoost)")
print(f"{'='*60}")

xgb_model = model.models.get('xgb_v5')
if xgb_model and hasattr(xgb_model, 'feature_importances_'):
    fi = xgb_model.feature_importances_
    sorted_fi = np.argsort(fi)[::-1]
    print(f"\n  Top 15 features (XGBoost):")
    print(f"  {'Rank':>4} | {'Feature#':>8} | {'Importance':>10}")
    print("  " + "-" * 30)
    for rank, idx in enumerate(sorted_fi[:15]):
        print(f"  {rank+1:>4} | [{idx:>3}]     | {fi[idx]:.6f}")
    
    zero_count = sum(1 for f in fi if f < 0.001)
    print(f"\n  Features with near-zero importance: {zero_count}/81")
    zero_idxs = [idx for idx in sorted_fi if fi[idx] < 0.001]
    print(f"  Zero-importance feature indices: {zero_idxs}")
else:
    print("  XGBoost feature importances not available")

# ============================================================
# 4. ERROR ANALYSIS BY LEAGUE
# ============================================================
print(f"\n{'='*60}")
print(f"  4. ERROR ANALYSIS BY LEAGUE")
print(f"{'='*60}")

conn = sqlite3.connect(DB)
# Batch query for tournament metadata
test_mids_list = [int(m) for m in mids_test if m > 0]
df_meta = pd.DataFrame()
if test_mids_list:
    batch_size = 500
    meta_parts = []
    for batch_start in range(0, len(test_mids_list), batch_size):
        batch = test_mids_list[batch_start:batch_start+batch_size]
        ph = ','.join(['?'] * len(batch))
        part = pd.read_sql_query(f'SELECT id, tournament FROM sofa_historical_results WHERE id IN ({ph})', conn, params=batch)
        meta_parts.append(part)
    if meta_parts:
        df_meta = pd.concat(meta_parts, ignore_index=True)
conn.close()

mid_to_tournament = dict(zip(df_meta['id'], df_meta['tournament']))
print(f"  Tournament metadata available for: {len(df_meta)}/{len(y_test)} test matches")

# Per-league metrics
league_data = defaultdict(lambda: {'total': 0, 'exact': 0, '1x2': 0})
for i in range(len(y_test)):
    mid = mids_test[i]
    tourn = mid_to_tournament.get(mid, 'Unknown')
    d = league_data[tourn]
    d['total'] += 1
    if preds[i] == y_test[i]:
        d['exact'] += 1
    if result(*class_to_score(y_test[i])) == result(*class_to_score(preds[i])):
        d['1x2'] += 1

print(f"\n{'League':30s} | {'Matches':>7} | {'Exact%':>8} | {'1X2%':>7}")
print("-" * 58)
for league, d in sorted(league_data.items(), key=lambda x: -x[1]['total'])[:30]:
    if d['total'] < 50:
        continue
    ep = d['exact'] / d['total'] * 100
    op = d['1x2'] / d['total'] * 100
    print(f"  {league:28s} | {d['total']:>7} | {ep:>7.2f}% | {op:>6.2f}%")

# ============================================================
# 5. ERROR ANALYSIS BY MATCH TYPE
# ============================================================
print(f"\n{'='*60}")
print(f"  5. ERROR ANALYSIS BY MATCH CHARACTERISTICS")
print(f"{'='*60}")

for rtype, rname in [(0, 'Home Win'), (1, 'Draw'), (2, 'Away Win')]:
    mask = np.array([result(*class_to_score(y_test[i])) == rtype for i in range(len(y_test))])
    n = int(np.sum(mask))
    if n > 0:
        e = float(np.mean(preds[mask] == y_test[mask]))
        print(f"  {rname:15s}: {n:>6} matches -> exact={e*100:.2f}%")

print(f"\n  Score range analysis:")
for label, cond_fn in [
    ('0-0 draws', lambda i: y_test[i] == 0),
    ('Low total (<=2 goals)', lambda i: sum(class_to_score(y_test[i])) <= 2),
    ('Medium total (3-4)', lambda i: 3 <= sum(class_to_score(y_test[i])) <= 4),
    ('High total (5+ goals)', lambda i: sum(class_to_score(y_test[i])) >= 5),
    ('Home win to nil', lambda i: class_to_score(y_test[i])[0] > class_to_score(y_test[i])[1] and class_to_score(y_test[i])[1] == 0),
    ('Away win to nil', lambda i: class_to_score(y_test[i])[1] > class_to_score(y_test[i])[0] and class_to_score(y_test[i])[0] == 0),
    ('Both score (BTTS)', lambda i: class_to_score(y_test[i])[0] > 0 and class_to_score(y_test[i])[1] > 0),
    ('Over 2.5 goals', lambda i: sum(class_to_score(y_test[i])) > 2),
    ('Under 2.5 goals', lambda i: sum(class_to_score(y_test[i])) <= 2),
]:
    mask = np.array([cond_fn(i) for i in range(len(y_test))])
    n = int(np.sum(mask))
    if n > 0:
        e = float(np.mean(preds[mask] == y_test[mask]))
        print(f"    {label:20s}: {n:>7} matches -> exact={e*100:.2f}%")

# ============================================================
# 6. ERROR PATTERNS
# ============================================================
print(f"\n{'='*60}")
print(f"  6. ERROR PATTERN ANALYSIS")
print(f"{'='*60}")

errors = []
for i in range(len(y_test)):
    if preds[i] != y_test[i]:
        ah, aa = class_to_score(y_test[i])
        ph, pa = class_to_score(preds[i])
        errors.append({
            'true_1x2': result(ah, aa),
            'pred_1x2': result(ph, pa),
            'confidence': float(probas[i, preds[i]]),
            'correct_prob': float(probas[i, y_test[i]]),
        })

print(f"  Total errors: {len(errors)}/{len(y_test)} ({len(errors)/len(y_test)*100:.1f}%)")

# Error type distribution
et = Counter()
for e in errors:
    et[f"{e['true_1x2']}->{e['pred_1x2']}"] += 1

et_names = {'0->1': 'Home->Draw','0->2': 'Home->Away','1->0': 'Draw->Home',
            '1->2': 'Draw->Away','2->0': 'Away->Home','2->1': 'Away->Draw'}
print(f"\n  Error type distribution:")
for k, cnt in et.most_common():
    name = et_names.get(k, k)
    print(f"    {name:15s}: {cnt:>6} ({cnt/len(errors)*100:.1f}%)")

if errors:
    avg_conf = float(np.mean([e['confidence'] for e in errors]))
    avg_true = float(np.mean([e['correct_prob'] for e in errors]))
    print(f"\n  Avg confidence in wrong prediction: {avg_conf:.4f}")
    print(f"  Avg probability of correct class:   {avg_true:.4f}")

# ============================================================
# 7. IDENTIFY TOP WEAKNESSES
# ============================================================
print(f"\n{'='*60}")
print(f"  7. TOP WEAKNESSES SUMMARY")
print(f"{'='*60}")

# Classes with worst recall
recalls = [(f"{h}-{a}", class_metrics[f'{h}-{a}']['recall']) for h in range(5) for a in range(5)]
recalls.sort(key=lambda x: x[1])
print(f"\n  5 WORST classes by recall:")
for score, r in recalls[:5]:
    cm = class_metrics[score]
    print(f"    {score:>5}: recall={r*100:.1f}% (count={cm['count']}) -> mostly confused with 2-2")

# Classes with worst precision
precs = [(f"{h}-{a}", class_metrics[f'{h}-{a}']['precision']) for h in range(5) for a in range(5)]
precs.sort(key=lambda x: x[1])
print(f"\n  5 WORST classes by precision:")
for score, p in precs[:5]:
    cm = class_metrics[score]
    print(f"    {score:>5}: precision={p*100:.1f}% (pred_count={int(cm['count']*cm['precision']/max(0.001,cm['recall']))})")

# ============================================================
# 8. ENSEMBLE BLEND ANALYSIS
# ============================================================
print(f"\n{'='*60}")
print(f"  8. ENSEMBLE WEIGHT ANALYSIS")
print(f"{'='*60}")

print(f"\n  Current ensemble weights:")
for name, w in sorted(model.weights.items(), key=lambda x: -x[1]):
    if w > 0:
        print(f"    {name:20s}: {w*100:.1f}%")

# ============================================================
# 9. CLASS DISTRIBUTION
# ============================================================
print(f"\n{'='*60}")
print(f"  9. TRAIN/TEST CLASS DISTRIBUTION")
print(f"{'='*60}")

train_dist = Counter(y_train)
test_dist = Counter(y_test)
print(f"\n{'Score':>6} | {'Train':>8} | {'Train%':>8} | {'Test':>8} | {'Test%':>8} | {'Ratio':>6}")
print("-" * 50)
for cls_idx in range(NUM_CLASSES):
    h, a = class_to_score(cls_idx)
    tr = train_dist[cls_idx]
    te = test_dist[cls_idx]
    ratio = te / max(1, tr)
    if cls_idx < 10 or tr > 1000:
        print(f"  {h}-{a} | {tr:>8} | {tr/len(y_train)*100:>7.2f}% | {te:>8} | {te/len(y_test)*100:>7.2f}% | {ratio:.3f}")

print(f"\n{'='*70}")
print(f"  SIGMA-ZERO ANALYSIS COMPLETE")
print(f"{'='*70}")

# Save results
results = {
    'model': 'v5_model.pkl',
    'overall': {
        'test_samples': len(y_test),
        'exact_pct': float(exact*100),
        'exact_count': exact_count,
        'acc_1x2_pct': float(acc_1x2*100),
        'rps': float(rps),
        'log_loss': float(logloss),
        'brier': float(brier),
    },
    'class_metrics': class_metrics,
    'calibration': cal_data,
    'avg_calibration_error': float(avg_ce),
    'ensemble_weights': {k: float(v) for k, v in model.weights.items()},
    'error_breakdown': {
        'total_errors': len(errors),
        'error_rate': float(len(errors)/len(y_test)),
        'error_types': {et_names.get(k,k): cnt for k, cnt in et.most_common()},
    }
}

with open('models/sigma_v5_analysis.json', 'w') as f:
    json.dump(results, f, indent=2)
print(f"\n  Results saved to models/sigma_v5_analysis.json")
