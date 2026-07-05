#!/usr/bin/env python3
"""
SIGMA-ZERO + DEMON CORE - Comprehensive Model Analysis
Full system audit: confusion matrix, calibration, feature importance, error analysis
"""

import sys, os, json, gc, time
sys.path.insert(0, os.path.dirname(__file__))
os.environ['PYTHONIOENCODING'] = 'utf-8'

import numpy as np
import pandas as pd
from collections import Counter, defaultdict
from datetime import datetime

import sqlite3
DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

from direct_predictor import (
    FEATURES, NUM_CLASSES, SCORE_CLASSES,
    class_to_score, score_to_class, result,
    _load_training_data, EnsemblePredictor
)
import joblib

print("=" * 70)
print("SIGMA-ZERO + DEMON CORE - COMPREHENSIVE ANALYSIS")
print("=" * 70)

model_path = os.path.join(os.path.dirname(__file__), 'models', 'mlp_blend.pkl')
print(f"\n[1] Loading model from {model_path}...")
model = joblib.load(model_path)
print(f"  Type: {type(model).__name__}")
print(f"  XGB weight: {model.xgb_weight:.2f}")
print(f"  NN models: {len(model.models)}")

if hasattr(model.xgb_model, 'feature_importances_'):
    fi = model.xgb_model.feature_importances_
    n_feats = len(fi)
    print(f"  Features: {n_feats} (FEATURES in code: {len(FEATURES)})")

print(f"\n[2] Loading training data...")
t0 = time.time()
X, y, mids = _load_training_data()
print(f"  Loaded {len(X)} samples in {time.time()-t0:.1f}s")
if len(X) == 0:
    print("  ERROR: No training data loaded!")
    sys.exit(1)

split = int(len(X) * 0.9)
X_train, X_test = X[:split], X[split:]
y_train, y_test = y[:split], y[split:]
mids_train, mids_test = mids[:split], mids[split:]
print(f"  Train: {len(X_train)}, Test: {len(X_test)}")

print(f"\n[3] Generating predictions on test set...")
t0 = time.time()
probas = model.predict_proba(X_test)
preds = np.argmax(probas, axis=1)
print(f"  Done in {time.time()-t0:.1f}s")

exact = np.mean(preds == y_test)
exact_count = np.sum(preds == y_test)

actual_1x2 = np.array([result(*class_to_score(c)) for c in y_test])
pred_1x2 = np.array([result(*class_to_score(c)) for c in preds])
acc_1x2 = np.mean(actual_1x2 == pred_1x2)

def compute_rps(y_true, y_pred_proba):
    n = len(y_true)
    rps_total = 0.0
    for i in range(n):
        ah, aa = class_to_score(y_true[i])
        ar = result(ah, aa)
        actual_cum = np.array([1 if ar <= k else 0 for k in range(3)], dtype=float)
        pp = y_pred_proba[i]
        p_h = sum(pp[h*5 + a] for h in range(5) for a in range(5) if h > a)
        p_d = sum(pp[h*5 + h] for h in range(5))
        p_a = sum(pp[h*5 + a] for h in range(5) for a in range(5) if a > h)
        pred_cum = np.cumsum([p_h, p_d, p_a])
        rps_total += np.mean((actual_cum - pred_cum) ** 2)
    return rps_total / n

rps = compute_rps(y_test, probas)

def compute_log_loss(y_true, y_pred_proba, eps=1e-15):
    n = len(y_true)
    ll = 0.0
    for i in range(n):
        p = max(eps, min(1-eps, y_pred_proba[i, y_true[i]]))
        ll -= np.log(p)
    return ll / n

logloss = compute_log_loss(y_test, probas)

def compute_brier(y_true, y_pred_proba):
    n = len(y_true)
    n_classes = y_pred_proba.shape[1]
    y_onehot = np.zeros((n, n_classes))
    y_onehot[np.arange(n), y_true] = 1
    return np.mean(np.sum((y_onehot - y_pred_proba)**2, axis=1))

brier = compute_brier(y_test, probas)

print(f"\n{'='*60}")
print(f"  OVERALL PERFORMANCE")
print(f"{'='*60}")
print(f"  Exact score: {exact*100:.2f}% ({exact_count}/{len(y_test)})")
print(f"  1X2 accuracy: {acc_1x2*100:.2f}%")
print(f"  RPS: {rps:.4f}")
print(f"  Log loss: {logloss:.4f}")
print(f"  Brier score: {brier:.4f}")

print(f"\n{'='*60}")
print(f"  1. CONFUSION MATRIX")
print(f"{'='*60}")

CM = np.zeros((NUM_CLASSES, NUM_CLASSES), dtype=int)
for t, p in zip(y_test, preds):
    CM[t, p] += 1

class_metrics = {}
print(f"\n{'Class':>6} | {'Count':>6} | {'Pct':>6} | {'Correct':>7} | {'Rec%':>5} | {'Prec%':>5} | {'F1':>5} | {'Most Confused With':>30}")
print("-" * 85)
for cls_idx in range(NUM_CLASSES):
    h, a = class_to_score(cls_idx)
    total = int(np.sum(CM[cls_idx, :]))
    correct = int(CM[cls_idx, cls_idx])
    recall = correct / total if total > 0 else 0
    col_sum = int(np.sum(CM[:, cls_idx]))
    precision = correct / col_sum if col_sum > 0 else 0
    f1 = 2 * recall * precision / (recall + precision) if (recall + precision) > 0 else 0
    
    confused = np.argsort(CM[cls_idx, :])[::-1]
    confused_str = ""
    for c in confused[:3]:
        if c != cls_idx and CM[cls_idx, c] > 0:
            ch, ca = class_to_score(c)
            confused_str += f"{ch}-{ca}({CM[cls_idx,c]}) "
    if not confused_str:
        confused_str = "-"
    
    pct = total / len(y_test) * 100
    print(f"  {h}-{a}  | {total:>6} | {pct:>5.1f}% | {correct:>7} | {recall*100:>4.1f}% | {precision*100:>4.1f}% | {f1:.3f} | {confused_str:30s}")
    
    class_metrics[f"{h}-{a}"] = {
        'count': total, 'pct': float(pct),
        'correct': correct, 'recall': float(recall),
        'precision': float(precision), 'f1': float(f1)
    }

print(f"\nAggregate by result type:")
for rtype, rname in [(0, 'Home'), (1, 'Draw'), (2, 'Away')]:
    indices = [i for i in range(NUM_CLASSES) if result(*class_to_score(i)) == rtype]
    total_correct = sum(CM[idx, idx] for idx in indices)
    total_count = sum(int(np.sum(CM[idx, :])) for idx in indices)
    acc_val = total_correct / total_count * 100 if total_count > 0 else 0
    print(f"  {rname:6s}: {total_correct}/{total_count} = {acc_val:.2f}%")

print(f"\n{'='*60}")
print(f"  2. CALIBRATION PER SCORE")
print(f"{'='*60}")

calibration_table = []
for cls_idx in range(NUM_CLASSES):
    h, a = class_to_score(cls_idx)
    mask = (y_test == cls_idx)
    n_true = int(np.sum(mask))
    mean_pred = float(np.mean(probas[mask, cls_idx])) if n_true > 0 else 0
    pred_mask = (preds == cls_idx)
    n_pred = int(np.sum(pred_mask))
    acc_pred = float(np.mean(y_test[pred_mask] == cls_idx)) if n_pred > 0 else 0
    
    calibration_table.append({
        'score': f'{h}-{a}',
        'true_count': n_true,
        'mean_pred_prob': mean_pred,
        'pred_count': n_pred,
        'acc_when_predicted': acc_pred,
        'calib_error': float(abs(mean_pred - (n_true / max(1, n_pred))))
    })

print(f"{'Score':>6} | {'True#':>6} | {'MeanP':>6} | {'Pred#':>6} | {'Acc@P':>6} | {'CalErr':>6}")
print("-" * 50)
total_cal_err = 0.0
for c in calibration_table:
    print(f"  {c['score']:>4} | {c['true_count']:>6} | {c['mean_pred_prob']:.4f} | {c['pred_count']:>6} | {c['acc_when_predicted']:.4f} | {c['calib_error']:.4f}")
    total_cal_err += c['calib_error']
avg_cal_err = total_cal_err / NUM_CLASSES
print(f"\n  Average calibration error: {avg_cal_err:.4f}")

print(f"\n  ECE for 1X2 (10 bins):")
for rtype, rname in [(0, 'Home'), (1, 'Draw'), (2, 'Away')]:
    probs_1x2 = np.zeros((len(y_test), 3))
    for i in range(len(y_test)):
        pp = probas[i]
        probs_1x2[i, 0] = sum(pp[h*5 + a] for h in range(5) for a in range(5) if h > a)
        probs_1x2[i, 1] = sum(pp[h*5 + h] for h in range(5))
        probs_1x2[i, 2] = sum(pp[h*5 + a] for h in range(5) for a in range(5) if a > h)
    
    actual_r = actual_1x2
    bins = np.linspace(0, 1, 11)
    ece = 0.0
    for b in range(10):
        lo, hi = bins[b], bins[b+1]
        in_bin = (probs_1x2[:, rtype] >= lo) & (probs_1x2[:, rtype] < hi)
        n_bin = int(np.sum(in_bin))
        if n_bin > 0:
            bin_acc = float(np.mean(actual_r[in_bin] == rtype))
            bin_conf = float(np.mean(probs_1x2[in_bin, rtype]))
            ece += n_bin / len(y_test) * abs(bin_acc - bin_conf)
    print(f"  {rname:6s}: ECE={ece:.4f}")

print(f"\n{'='*60}")
print(f"  3. FEATURE IMPORTANCE ANALYSIS")
print(f"{'='*60}")

sorted_idx = np.argsort(fi)[::-1]
print(f"\n  TOP 10 MOST IMPORTANT FEATURES:")
print(f"  {'Rank':>4} | {'Feature':35s} | {'Importance':>10}")
print("  " + "-" * 55)
for rank, idx in enumerate(sorted_idx[:10]):
    print(f"  {rank+1:>4} | {FEATURES[idx]:35s} | {fi[idx]:.6f}")

feature_groups = {
    'walkforward': ['elo', 'xg_for', 'xg_against', 'form', 'matches_played', 'shots_for', 'shots_against', 'xg_diff', 'shot_diff', 'days_rest'],
    'glicko': ['glicko'],
    'stat': ['stat_'],
    'lineups': ['formation', 'has_lineup', 'missing_core', 'att_loss', 'def_loss'],
    'odds': ['odds_'],
    'forebet': ['forebet'],
    'interaction': ['elo_form', 'elo_xg', 'form_xg', 'elo_diff_form', 'fatigue'],
    'ratio': ['xg_ratio', 'shots_ratio', 'form_ratio', 'xgf_xga_ratio', 'shot_eff'],
    'polynomial': ['_sq'],
    'time': ['month', 'day', 'season', 'weekend'],
    'weather': ['temp', 'precip', 'wind', 'humidity'],
    'travel': ['travel'],
}

def classify_feature(fname):
    if 'elo' in fname and ('form' in fname or 'xg' in fname or 'diff' in fname):
        return 'interaction'
    if '_ratio' in fname or 'xgf_xga' in fname or 'shot_eff' in fname:
        return 'ratio'
    if fname.endswith('_sq'):
        return 'polynomial'
    if fname in ['month', 'day_of_week', 'season_progress', 'is_weekend']:
        return 'time'
    if fname in ['home_temp', 'home_precip', 'home_wind', 'home_humidity']:
        return 'weather'
    if fname == 'travel_distance':
        return 'travel'
    if fname.startswith('stat_'):
        return 'stat'
    if fname.startswith('odds_'):
        return 'odds'
    if fname.startswith('forebet'):
        return 'forebet'
    if 'formation' in fname or 'lineups' in fname or 'missing_core' in fname or 'loss' in fname:
        return 'lineups'
    if 'glicko' in fname:
        return 'glicko'
    return 'walkforward'

fi_sorted = [(FEATURES[idx], fi[idx]) for idx in sorted_idx]

print(f"\n  FEATURE GROUP IMPORTANCE:")
group_imp = defaultdict(float)
for fname, imp_val in fi_sorted:
    group = classify_feature(fname)
    group_imp[group] += imp_val
for group, total in sorted(group_imp.items(), key=lambda x: -x[1]):
    print(f"    {group:15s}: {total:.4f} ({total*100:.1f}%)")

print(f"\n  4. ZERO-IMPORTANCE / REDUNDANT FEATURES (XGBoost side):")
zero_count = sum(1 for idx in sorted_idx if fi[idx] < 0.001)
zero_feats = [(FEATURES[idx], fi[idx]) for idx in sorted_idx if fi[idx] < 0.001]
print(f"    Found {zero_count} features with near-zero importance:")
for fname, imp_val in zero_feats:
    print(f"    ELIMINATE: {fname}: {imp_val:.6f}")

print(f"\n  5. FEATURE REDUNDANCY CORRELATION ANALYSIS:")
sample_size = min(10000, len(X_train))
idx_sample = np.random.choice(len(X_train), sample_size, replace=False)
X_sample = X_train[idx_sample]
y_sample = y_train[idx_sample]
from sklearn.impute import SimpleImputer
imp_temp = SimpleImputer(strategy='median')
X_sample_i = imp_temp.fit_transform(X_sample)

corr_matrix = np.corrcoef(X_sample_i.T)
high_corr_pairs = []
for i in range(len(FEATURES)):
    for j in range(i+1, len(FEATURES)):
        r_val = abs(corr_matrix[i,j])
        if r_val > 0.85 and not np.isnan(r_val):
            high_corr_pairs.append((FEATURES[i], FEATURES[j], corr_matrix[i,j]))

print(f"    Found {len(high_corr_pairs)} highly correlated pairs (|r| > 0.85):")
for i, (f1, f2, r_val) in enumerate(high_corr_pairs[:20]):
    print(f"    {f1} <-> {f2}: r={r_val:.3f}")

# Error analysis by tournament
print(f"\n{'='*60}")
print(f"  6. ERROR ANALYSIS BY TOURNAMENT/LEAGUE")
print(f"{'='*60}")

conn = sqlite3.connect(DB)
test_mids_list = [int(m) for m in mids_test if m > 0]
df_meta = pd.DataFrame()
if test_mids_list:
    batch_size = 500
    batches = [test_mids_list[i:i+batch_size] for i in range(0, len(test_mids_list), batch_size)]
    meta_list = []
    for batch in batches:
        placeholders = ','.join(['?'] * len(batch))
        batch_df = pd.read_sql_query(f'''
            SELECT id, tournament, home_team, away_team
            FROM sofa_historical_results
            WHERE id IN ({placeholders})
        ''', conn, params=batch)
        meta_list.append(batch_df)
    if meta_list:
        df_meta = pd.concat(meta_list, ignore_index=True)
conn.close()

print(f"  Matches with tournament metadata: {len(df_meta)}")

if len(df_meta) > 0:
    mid_to_tournament = dict(zip(df_meta['id'], df_meta['tournament']))
    
    league_metrics = defaultdict(lambda: {'total': 0, 'exact': 0, '1x2': 0})
    
    for i in range(len(y_test)):
        mid = mids_test[i]
        tournament = mid_to_tournament.get(mid, 'Unknown')
        lm = league_metrics[tournament]
        lm['total'] += 1
        if preds[i] == y_test[i]:
            lm['exact'] += 1
        actual_r = result(*class_to_score(y_test[i]))
        pred_r = result(*class_to_score(preds[i]))
        if actual_r == pred_r:
            lm['1x2'] += 1
    
    league_sorted = sorted(league_metrics.items(), key=lambda x: -x[1]['total'])
    print(f"\n{'League':30s} | {'Matches':>7} | {'Exact%':>7} | {'1X2%':>7}")
    print("-" * 55)
    for league, lm in league_sorted[:30]:
        if lm['total'] < 100:
            continue
        exact_pct = lm['exact'] / lm['total'] * 100
        acc_1x2_l = lm['1x2'] / lm['total'] * 100
        print(f"{league:30s} | {lm['total']:>7} | {exact_pct:>6.2f}% | {acc_1x2_l:>6.2f}%")
    
    # Error by home/away
    print(f"\n{'='*60}")
    print(f"  7. ERROR ANALYSIS BY HOME/AWAY DIMENSION")
    print(f"{'='*60}")
    
    home_actuals = []
    home_preds = []
    for i in range(len(y_test)):
        ah, aa = class_to_score(y_test[i])
        ph, pa = class_to_score(preds[i])
        home_actuals.append(ah)
        home_preds.append(ph)
    
    home_exact_val = float(np.mean(np.array(home_actuals) == np.array(home_preds)))
    print(f"  Home goals exact: {home_exact_val*100:.2f}%")
    
    away_actuals = []
    away_preds = []
    for i in range(len(y_test)):
        ah, aa = class_to_score(y_test[i])
        ph, pa = class_to_score(preds[i])
        away_actuals.append(aa)
        away_preds.append(pa)
    
    away_exact_val = float(np.mean(np.array(away_actuals) == np.array(away_preds)))
    print(f"  Away goals exact: {away_exact_val*100:.2f}%")
    
    for rtype, rname in [(0, 'Home Win'), (1, 'Draw'), (2, 'Away Win')]:
        masks = []
        for i in range(len(y_test)):
            ah, aa = class_to_score(y_test[i])
            masks.append(result(ah, aa) == rtype)
        mask = np.array(masks)
        n_type = int(np.sum(mask))
        if n_type > 0:
            exact_type = float(np.mean(preds[mask] == y_test[mask]))
            print(f"  {rname:12s}: {n_type:>6} matches, exact={exact_type*100:.2f}%")
    
    print(f"\n  8. ERROR ANALYSIS BY SCORE TYPE:")
    for label, cond_fn in [
        ('0-0 only', lambda i: y_test[i] == 0),
        ('Low-scoring (<=2 total)', lambda i: sum(class_to_score(y_test[i])) <= 2),
        ('Medium (3-4 total)', lambda i: 3 <= sum(class_to_score(y_test[i])) <= 4),
        ('High-scoring (5+ total)', lambda i: sum(class_to_score(y_test[i])) >= 5),
        ('Home clean sheet', lambda i: class_to_score(y_test[i])[0] > class_to_score(y_test[i])[1] and class_to_score(y_test[i])[1] == 0),
        ('Away clean sheet', lambda i: class_to_score(y_test[i])[1] > class_to_score(y_test[i])[0] and class_to_score(y_test[i])[0] == 0)
    ]:
        mask = np.array([cond_fn(i) for i in range(len(y_test))])
        n_type = int(np.sum(mask))
        if n_type > 0:
            exact_type = float(np.mean(preds[mask] == y_test[mask]))
            print(f"    {label:25s}: {n_type:>6} matches, exact={exact_type*100:.2f}%")

print(f"\n{'='*60}")
print(f"  9. OPTIMAL ENSEMBLE BLENDING WEIGHTS")
print(f"{'='*60}")

print(f"  Current weights: XGB={model.xgb_weight:.2f}, NN={1-model.xgb_weight:.2f}")
print(f"  Current exact: {exact*100:.2f}%")

print(f"  Computing individual model probabilities...")
X_imp = model.imp.transform(X_test)
X_scaled = model.scaler.transform(X_imp)

xgb_proba = model.xgb_model.predict_proba(X_test)
nn_proba = model.models[0].predict_proba(X_scaled)

best_exact_w = 0.0
best_exact_val = 0.0
best_1x2_w = 0.0
best_1x2_val = 0.0

print(f"\n  Grid search over XGB weights:")
print(f"  {'XGB%':>6} | {'NN%':>6} | {'Exact%':>8} | {'1X2%':>8} | {'RPS':>6}")
print("  " + "-" * 45)

for w_xgb_pct in range(0, 101, 5):
    w_xgb = w_xgb_pct / 100.0
    w_nn = 1.0 - w_xgb
    blended = w_xgb * xgb_proba + w_nn * nn_proba
    blended_pred = np.argmax(blended, axis=1)
    exact_b = float(np.mean(blended_pred == y_test))
    r_actual = np.array([result(*class_to_score(c)) for c in y_test])
    r_pred = np.array([result(*class_to_score(c)) for c in blended_pred])
    acc_b = float(np.mean(r_actual == r_pred))
    rps_b = float(compute_rps(y_test, blended))
    
    marker = " <-- CURRENT" if abs(w_xgb_pct - model.xgb_weight * 100) < 3 else ""
    if exact_b > best_exact_val:
        best_exact_val = exact_b
        best_exact_w = w_xgb
    if acc_b > best_1x2_val:
        best_1x2_val = acc_b
        best_1x2_w = w_xgb
    
    print(f"  {w_xgb*100:>5.0f}% | {w_nn*100:>5.0f}% | {exact_b*100:>7.2f}% | {acc_b*100:>7.2f}% | {rps_b:.4f}{marker}")

print(f"\n  Best for Exact: XGB={best_exact_w*100:.0f}%, NN={(1-best_exact_w)*100:.0f}% -> {best_exact_val*100:.2f}%")
print(f"  Best for 1X2:   XGB={best_1x2_w*100:.0f}%, NN={(1-best_1x2_w)*100:.0f}% -> {best_1x2_val*100:.2f}%")

print(f"\n{'='*60}")
print(f"  10. ERROR PATTERN ANALYSIS")
print(f"{'='*60}")

errors_list = []
for i in range(len(y_test)):
    if preds[i] != y_test[i]:
        ah, aa = class_to_score(y_test[i])
        ph, pa = class_to_score(preds[i])
        ar = result(ah, aa)
        pr = result(ph, pa)
        errors_list.append({
            'true_score': f'{ah}-{aa}',
            'pred_score': f'{ph}-{pa}',
            'true_1x2': ar,
            'pred_1x2': pr,
            'confidence': float(probas[i, preds[i]]),
            'correct_confidence': float(probas[i, y_test[i]]),
        })

error_types = Counter()
for e in errors_list:
    et = f"{e['true_1x2']}->{e['pred_1x2']}"
    error_types[et] += 1

print(f"\n  Error types (1X2 direction):")
et_names = {'0->1': 'Home->Draw', '0->2': 'Home->Away', '1->0': 'Draw->Home',
            '1->2': 'Draw->Away', '2->0': 'Away->Home', '2->1': 'Away->Draw'}
for et, cnt in error_types.most_common():
    name = et_names.get(et, et)
    print(f"    {name:15s}: {cnt:>6} ({cnt/len(errors_list)*100:.1f}%)")

if errors_list:
    avg_conf = float(np.mean([e['confidence'] for e in errors_list]))
    avg_correct_conf = float(np.mean([e['correct_confidence'] for e in errors_list]))
    print(f"\n  Average confidence in WRONG prediction: {avg_conf:.4f}")
    print(f"  Average probability assigned to CORRECT class: {avg_correct_conf:.4f}")

print(f"\n{'='*60}")
print(f"  11. CLASS DISTRIBUTION (Train vs Test)")
print(f"{'='*60}")

train_dist = Counter(y_train)
test_dist = Counter(y_test)
print(f"{'Score':>6} | {'Train#':>7} | {'Train%':>8} | {'Test#':>7} | {'Test%':>8}")
print("-" * 45)
for cls_idx in range(NUM_CLASSES):
    h, a = class_to_score(cls_idx)
    tr = train_dist[cls_idx]
    te = test_dist[cls_idx]
    print(f"  {h}-{a} | {tr:>7} | {tr/len(y_train)*100:>7.2f}% | {te:>7} | {te/len(y_test)*100:>7.2f}%")

print(f"\n{'='*70}")
print(f"  SIGMA-ZERO + DEMON CORE - ANALYSIS COMPLETE")
print(f"{'='*70}")

results_dict = {
    'overall': {
        'model': 'mlp_blend.pkl (EnsemblePredictor)',
        'xgb_weight': model.xgb_weight,
        'n_nn': len(model.models),
        'test_samples': len(y_test),
        'exact_pct': float(exact * 100),
        'exact_count': int(exact_count),
        'acc_1x2_pct': float(acc_1x2 * 100),
        'rps': float(rps),
        'log_loss': float(logloss),
        'brier': float(brier),
    },
    'class_metrics': class_metrics,
    'calibration': calibration_table,
    'avg_calibration_error': float(avg_cal_err),
    'feature_importance_top20': [
        {'feature': FEATURES[idx], 'importance': float(fi[idx])}
        for idx in sorted_idx[:20]
    ],
    'zero_importance_features': [
        {'feature': FEATURES[idx], 'importance': float(fi[idx])}
        for idx in sorted_idx if fi[idx] < 0.001
    ],
    'feature_group_importance': dict(sorted(group_imp.items(), key=lambda x: -x[1])),
    'optimal_blend': {
        'best_for_exact': {'xgb_pct': float(best_exact_w * 100), 'exact_pct': float(best_exact_val * 100)},
        'best_for_1x2': {'xgb_pct': float(best_1x2_w * 100), '1x2_pct': float(best_1x2_val * 100)},
    },
    'error_breakdown': {
        'total_errors': len(errors_list),
        'error_rate': float(len(errors_list) / len(y_test)),
        'error_types': {et_names.get(k, k): v for k, v in error_types.most_common()},
    }
}

with open(os.path.join(os.path.dirname(__file__), 'models', 'sigma_analysis.json'), 'w') as f:
    json.dump(results_dict, f, indent=2)
print(f"\n  Detailed results saved to models/sigma_analysis.json")
print(f"\n  DONE.")
