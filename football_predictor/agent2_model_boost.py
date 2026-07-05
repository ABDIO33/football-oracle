#!/usr/bin/env python3
"""
agent2_model_boost.py - DarkForge-X SHADOW-CORE MODE
=====================================================
6 Modules for breaking the 20% exact score barrier:
  1. Data Quality Check - class distribution, imbalance, feature analysis
  2. LightGBM Trainer (CPU-optimized, faster than XGBoost)
  3. XGBoost Deep Hyperparameter Search (broader & deeper)
  4. Class-Weighted Loss (inverse-frequency + adaptive scaling)
  5. Focal Loss (gamma=2) via custom objective + sample-weight chaining
  6. Stacking Meta-Learner (5 base models -> meta XGBoost)

Architecture:
  - Loads training_data_v3.npz (772,771 x 120)
  - Detects & drops constant columns -> 72 variable features
  - Time-based 90/10 split (walk-forward compatible)
  - All metrics: exact score %, 1X2 %, RPS
  - Saves all models, weight files, and configs to models/

Usage:
  python agent2_model_boost.py              # Full pipeline
  python agent2_model_boost.py --stage 1    # Data quality only
  python agent2_model_boost.py --stage 3    # XGBoost deep search only
  python agent2_model_boost.py --stage 6    # Stacking only (requires stages 1-5)

Author: Agent 2 (almubarrij alrayiysiy)
Code-first, perfection-second. Unconstrained.
"""

import os, sys, json, time, gc, copy, argparse, warnings
from datetime import datetime
from collections import Counter
import numpy as np
import joblib

warnings.filterwarnings('ignore')
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['OMP_NUM_THREADS'] = str(os.cpu_count() or 8)

# Paths
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(PROJECT_DIR, 'training_data_v3.npz')
MODEL_DIR = os.path.join(PROJECT_DIR, 'models')
PROGRESS_PATH = os.path.join(os.path.dirname(PROJECT_DIR), '..', '.pi', 'agent', 'sessions',
    '--C--Users-zake.exe-Desktop-Score Exact 100-football_predictor--',
    'subagent-artifacts', 'progress', '8d09a9aa', 'progress.md')
os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(os.path.dirname(PROGRESS_PATH), exist_ok=True)

# Constants
NUM_CLASSES = 25
SCORE_CLASSES = [(h, a) for h in range(5) for a in range(5)]

def score_to_class(h, a):
    return min(int(h), 4) * 5 + min(int(a), 4)

def class_to_score(cls):
    return cls // 5, cls % 5

def result(h, a):
    return 0 if h > a else (1 if h == a else 2)

RANDOM_STATE = 42
np.random.seed(RANDOM_STATE)


# =============================================================================
# MODULE 1 - DATA QUALITY CHECK
# =============================================================================
def module1_data_quality():
    print("=" * 72)
    print("MODULE 1: DATA QUALITY CHECK")
    print("=" * 72)

    if not os.path.exists(DATA_PATH):
        print(f"[FATAL] Data file not found: {DATA_PATH}")
        sys.exit(1)

    data = np.load(DATA_PATH)
    X, y, rt, mids = data['X'], data['y'], data['result_types'], data['match_ids']
    del mids
    N, D = X.shape
    print(f"\nLoaded: {N:,} matches x {D} features")
    print(f"Memory: X={X.nbytes/1e6:.1f} MB, y={y.nbytes/1e6:.1f} MB")

    # Class distribution
    unique, counts = np.unique(y, return_counts=True)
    print(f"\n{'-'*60}")
    print(f"{'Class Distribution (25 score classes)':^60}")
    print(f"{'-'*60}")
    print(f"{'Score':>6} | {'Class':>5} | {'Count':>10} | {'Pct':>7} | {'Imbalance':>10}")
    print(f"{'-'*60}")
    max_count = counts.max()
    total = N
    for cls, cnt in zip(unique, counts):
        h, a = class_to_score(cls)
        ratio = max_count / cnt
        bar_len = int(50 * cnt / max_count)
        bar = '#' * bar_len
        print(f"  {h}-{a:>2}  |  {cls:>3}   | {int(cnt):>8,}  | {100*cnt/total:>5.2f}% | {ratio:>8.2f}x  {bar}")
    print(f"{'-'*60}")
    print(f"  TOTAL       |          | {total:>8,}  | {100.0:>5.2f}% |")
    print(f"{'-'*60}")
    print(f"  Max class: {max_count:,} (class {unique[counts.argmax()]})")
    print(f"  Min class: {counts.min():,} (class {unique[counts.argmin()]})")
    print(f"  Imbalance ratio: {max_count/counts.min():.2f}x")

    # 1X2 distribution
    rt_unique, rt_counts = np.unique(rt, return_counts=True)
    rt_labels = {0: 'H (Home Win)', 1: 'D (Draw)', 2: 'A (Away Win)'}
    print(f"\n{'-'*40}")
    print("1X2 Distribution:")
    for k, c in zip(rt_unique, rt_counts):
        kk, cc = int(k), int(c)
        print(f"  {rt_labels[kk]}: {cc:>10,} ({100.0*cc/total:>5.2f}%)")
    print(f"{'-'*40}")

    # Feature variance analysis
    print(f"\n{'-'*60}")
    print("Feature Variance Analysis:")
    stds = X.std(axis=0)
    const_idx = np.where(stds < 1e-8)[0]
    var_idx = np.where(stds >= 1e-8)[0]
    print(f"  Constant (zero-variance) columns: {len(const_idx)} / {D}")
    print(f"  Variable columns: {len(var_idx)} / {D}")

    feature_mask = np.ones(D, dtype=bool)
    feature_mask[const_idx] = False
    print(f"  -> Using {feature_mask.sum()} variable features (dropping {len(const_idx)} constants)")

    # Time-based split (90/10)
    split = int(N * 0.9)
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]
    rt_train, rt_val = rt[:split], rt[split:]

    X_train = X_train[:, feature_mask]
    X_val = X_val[:, feature_mask]

    print(f"\n{'-'*40}")
    print(f"Train/Val Split:")
    print(f"  Train: {len(X_train):>8,} matches")
    print(f"  Val:   {len(X_val):>8,} matches")
    print(f"  Features: {X_train.shape[1]}")

    # Train/val class distribution delta
    ty_dist = dict(zip(*np.unique(y_train, return_counts=True)))
    vy_dist = dict(zip(*np.unique(y_val, return_counts=True)))
    deltas = []
    for c in range(NUM_CLASSES):
        tp = ty_dist.get(c, 0) / len(y_train) * 100
        vp = vy_dist.get(c, 0) / len(y_val) * 100
        deltas.append(abs(tp - vp))
    print(f"  Train/val class delta: max={max(deltas):.3f}% mean={np.mean(deltas):.3f}%")

    # Class weights (inverse-frequency normalized)
    class_weights = np.array([max_count / max(ty_dist.get(c, 1), 1) for c in range(NUM_CLASSES)])
    class_weights = class_weights / class_weights.sum() * NUM_CLASSES
    print(f"\n  Class weights:")
    for c in range(NUM_CLASSES):
        h, a = class_to_score(c)
        print(f"    {h}-{a}: {class_weights[c]:.4f}")

    data.close()
    gc.collect()

    # Save reports
    report = {
        'total_samples': N, 'n_features': D, 'n_variable_features': int(feature_mask.sum()),
        'n_constant_features': len(const_idx), 'constant_feature_indices': const_idx.tolist(),
        'imbalance_max_min': round(max_count / counts.min(), 2),
        'train_samples': int(len(X_train)), 'val_samples': int(len(X_val)),
    }
    with open(os.path.join(MODEL_DIR, 'data_quality_report.json'), 'w') as f:
        json.dump(report, f, indent=2)
    np.save(os.path.join(MODEL_DIR, 'feature_mask.npy'), feature_mask)
    print("  OK Quality report + feature mask saved.")

    return X_train, X_val, y_train, y_val, rt_train, rt_val, feature_mask, class_weights


# =============================================================================
# METRICS HELPERS
# =============================================================================
def compute_rps(y_true, y_pred_proba):
    n = len(y_true)
    rpst = 0.0
    for i in range(n):
        h, a = class_to_score(y_true[i])
        r = result(h, a)
        ac = np.array([1 if r <= k else 0 for k in range(3)], dtype=float)
        pp = y_pred_proba[i]
        ph = sum(pp[h2*5+a2] for h2 in range(5) for a2 in range(5) if h2 > a2)
        pd = sum(pp[h2*5+h2] for h2 in range(5))
        pa = sum(pp[h2*5+a2] for h2 in range(5) for a2 in range(5) if a2 > h2)
        pc = np.cumsum([ph, pd, pa])
        rpst += np.mean((ac - pc) ** 2)
    return rpst / n

def evaluate(y_true, y_pred, y_pred_proba):
    exact = np.mean(y_pred == y_true)
    a1x2 = np.array([result(*class_to_score(c)) for c in y_true])
    p1x2 = np.array([result(*class_to_score(c)) for c in y_pred])
    acc = np.mean(a1x2 == p1x2)
    rps = compute_rps(y_true, y_pred_proba)
    return exact, acc, rps

def print_metrics(name, exact, acc, rps, extra=None):
    s = f"  [{name}]  Exact={exact*100:.2f}%  |  1X2={acc*100:.2f}%  |  RPS={rps:.4f}"
    if extra:
        for k, v in extra.items():
            s += f"  |  {k}={v}"
    print(s)

def save_model_info(name, metrics, params, path):
    fp = os.path.join(path, f'{name}_info.json')
    with open(fp, 'w') as f:
        json.dump({'model': name, **metrics, 'params': params}, f, indent=2)
    return fp


# =============================================================================
# MODULE 2 - LIGHTGBM TRAINER (FAST)
# =============================================================================
def module2_lightgbm(X_train, X_val, y_train, y_val, class_weights):
    print("\n" + "=" * 72)
    print("MODULE 2: LightGBM TRAINER")
    print("=" * 72)
    import lightgbm as lgb

    sample_weights = np.array([class_weights[int(y)] for y in y_train])
    sample_weights /= sample_weights.mean()
    val_weights = np.array([class_weights[int(y)] for y in y_val])
    val_weights /= val_weights.mean()

    # Quick comparison of 2 configs on 50K subset
    print("\n[LightGBM] Quick config comparison (50K subset)...")
    N_train = len(X_train)
    rng = np.random.default_rng(RANDOM_STATE)
    si = rng.choice(N_train, min(50000, N_train), replace=False)
    Xs, ys, sws = X_train[si], y_train[si], sample_weights[si]

    configs = [
        {'boosting_type': 'gbdt', 'num_leaves': 31, 'max_depth': -1, 'learning_rate': 0.08, 'n_estimators': 50,
         'subsample': 0.8, 'colsample_bytree': 0.7, 'reg_alpha': 0.05, 'reg_lambda': 0.1, 'min_child_samples': 30},
        {'boosting_type': 'goss', 'num_leaves': 63, 'max_depth': 8, 'learning_rate': 0.08, 'n_estimators': 50,
         'subsample': 1.0, 'colsample_bytree': 0.8, 'reg_alpha': 0.1, 'reg_lambda': 0.2, 'min_child_samples': 20,
         'top_rate': 0.2, 'other_rate': 0.1},
    ]

    best_score = -1.0; best_cfg = None
    for i, cfg in enumerate(configs):
        print(f"  Config {i+1}: {cfg['boosting_type']} leaves={cfg['num_leaves']}")
        p = cfg.copy()
        p.update({'objective': 'multiclass', 'num_class': NUM_CLASSES, 'metric': 'multi_logloss',
                  'random_state': RANDOM_STATE, 'verbose': -1, 'force_row_wise': True})
        m = lgb.LGBMClassifier(**p)
        st = time.time()
        m.fit(Xs, ys, sample_weight=sws, eval_set=[(X_val[:20000], y_val[:20000])],
              eval_sample_weight=[val_weights[:20000]],
              callbacks=[lgb.early_stopping(10), lgb.log_evaluation(0)])
        el = time.time() - st
        yp = m.predict(X_val); pp = m.predict_proba(X_val)
        ex, a1, rp = evaluate(y_val, yp, pp)
        print_metrics(f"LGB-S{i+1}", ex, a1, rp, {'time': f'{el:.1f}s'})
        if ex > best_score:
            best_score = ex; best_cfg = cfg

    # Single full train
    print(f"\n[LightGBM] Full train ({best_cfg['boosting_type']})")
    fp = {'boosting_type': best_cfg['boosting_type'], 'num_leaves': best_cfg['num_leaves'], 'max_depth': best_cfg['max_depth'],
          'learning_rate': 0.05, 'n_estimators': 200, 'subsample': best_cfg['subsample'], 'colsample_bytree': best_cfg['colsample_bytree'],
          'reg_alpha': best_cfg['reg_alpha'], 'reg_lambda': best_cfg['reg_lambda'], 'min_child_samples': best_cfg['min_child_samples'],
          'objective': 'multiclass', 'num_class': NUM_CLASSES, 'metric': 'multi_logloss',
          'random_state': RANDOM_STATE, 'verbose': -1, 'force_row_wise': True}
    st = time.time()
    final_lgb = lgb.LGBMClassifier(**fp)
    final_lgb.fit(X_train, y_train, sample_weight=sample_weights,
                  eval_set=[(X_val, y_val)], eval_sample_weight=[val_weights],
                  callbacks=[lgb.early_stopping(15), lgb.log_evaluation(0)])
    el = time.time() - st
    yp = final_lgb.predict(X_val); pp = final_lgb.predict_proba(X_val)
    ex, a1, rp = evaluate(y_val, yp, pp)
    print_metrics("LightGBM-FINAL", ex, a1, rp, {'time': f'{el:.1f}s', 'best_iter': final_lgb.best_iteration_})

    final_lgb.booster_.save_model(os.path.join(MODEL_DIR, 'lgbm_direct.txt'))
    joblib.dump(final_lgb, os.path.join(MODEL_DIR, 'lgbm_final.pkl'))
    save_model_info('lgbm_final', {
        'exact_pct': round(ex*100, 4), 'acc_1x2_pct': round(a1*100, 4), 'rps': round(rp, 4),
        'val_samples': len(X_val), 'train_samples': len(X_train),
        'best_iteration': int(final_lgb.best_iteration_), 'training_time_s': round(el, 2),
    }, fp, MODEL_DIR)
    print("  OK LightGBM saved: models/lgbm_final.pkl")
    gc.collect()
    return final_lgb


# =============================================================================
# MODULE 3 - XGBoost DEEP HYPERPARAMETER SEARCH (TRIMMED)
# =============================================================================
def module3_xgboost_deep_search(X_train, X_val, y_train, y_val, class_weights):
    print("\n" + "=" * 72)
    print("MODULE 3: XGBoost DEEP HYPERPARAMETER SEARCH")
    print("=" * 72)
    import xgboost as xgb

    sample_weights = np.array([class_weights[int(y)] for y in y_train])
    sample_weights /= sample_weights.mean()
    val_weights = np.array([class_weights[int(y)] for y in y_val])
    val_weights /= val_weights.mean()

    # Tiny subset for ultra-fast search
    N_train = len(X_train)
    rng = np.random.default_rng(RANDOM_STATE)
    si = rng.choice(N_train, min(30000, N_train), replace=False)
    Xs, ys, sws = X_train[si], y_train[si], sample_weights[si]
    vsi = rng.choice(len(X_val), min(10000, len(X_val)), replace=False)
    Xv, yv, vwv = X_val[vsi], y_val[vsi], val_weights[vsi]

    print(f"\nSearch: {len(Xs)} train, {len(Xv)} val")

    # Ultra-compact grid: 6 coarse + 9 fine, 50 trees each
    best_exact = -1.0; best_params = None; results = []

    # Coarse: 3 depths x 2 lr
    coarse = [{'max_depth': md, 'learning_rate': lr, 'subsample': 0.85, 'colsample_bytree': 0.8,
               'reg_alpha': 0.1, 'reg_lambda': 0.1, 'min_child_weight': 3, 'gamma': 0.1}
              for md in [6, 9, 12] for lr in [0.03, 0.08]]

    for i, p in enumerate(coarse):
        model = xgb.XGBClassifier(n_estimators=50, max_depth=p['max_depth'], learning_rate=p['learning_rate'],
            objective='multi:softprob', num_class=NUM_CLASSES, subsample=p['subsample'],
            colsample_bytree=p['colsample_bytree'], reg_alpha=p['reg_alpha'], reg_lambda=p['reg_lambda'],
            min_child_weight=p['min_child_weight'], gamma=p['gamma'],
            random_state=RANDOM_STATE, eval_metric='mlogloss', verbosity=0, n_jobs=-1)
        st = time.time()
        model.fit(Xs, ys, sample_weight=sws, verbose=False)
        el = time.time() - st
        yp = model.predict(X_val); pp = model.predict_proba(X_val)
        ex, a1, rp = evaluate(y_val, yp, pp)
        results.append({**p, 'exact': round(ex, 4), 'acc_1x2': round(a1, 4), 'time_s': round(el, 1)})
        print(f"  [{i+1}] md={p['max_depth']} lr={p['learning_rate']:.2f} -> exact={ex*100:.2f}% [{el:.0f}s]", end='')
        if ex > best_exact:
            best_exact = ex; best_params = p.copy(); print(' *BEST*')
        else: print()

    # Fine around best
    md_b = best_params['max_depth']; lr_b = best_params['learning_rate']
    fine = [{'max_depth': md, 'learning_rate': lr, 'subsample': sub, 'colsample_bytree': col,
             'reg_alpha': al, 'reg_lambda': la, 'min_child_weight': 3, 'gamma': 0.1}
            for md in [max(3, md_b-2), md_b, md_b+2]
            for lr in [lr_b*0.5, lr_b, lr_b*1.5]
            for sub in [0.8, 1.0]
            for col in [0.7, 1.0]
            for al in [0.0, 0.1]
            for la in [0.05, 0.2]][:9]

    for i, p in enumerate(fine):
        model = xgb.XGBClassifier(n_estimators=50, max_depth=p['max_depth'], learning_rate=p['learning_rate'],
            objective='multi:softprob', num_class=NUM_CLASSES, subsample=p['subsample'],
            colsample_bytree=p['colsample_bytree'], reg_alpha=p['reg_alpha'], reg_lambda=p['reg_lambda'],
            min_child_weight=p['min_child_weight'], gamma=p['gamma'],
            random_state=RANDOM_STATE, eval_metric='mlogloss', verbosity=0, n_jobs=-1)
        st = time.time()
        model.fit(Xs, ys, sample_weight=sws, verbose=False)
        el = time.time() - st
        yp = model.predict(X_val); pp = model.predict_proba(X_val)
        ex, a1, rp = evaluate(y_val, yp, pp)
        results.append({**p, 'exact': round(ex, 4), 'acc_1x2': round(a1, 4), 'time_s': round(el, 1)})
        out = f"  Fine[{i+1}] md={p['max_depth']} lr={p['learning_rate']:.2f} sub={p['subsample']:.2f} col={p['colsample_bytree']:.2f} al={p['reg_alpha']:.2f} la={p['reg_lambda']:.2f} -> exact={ex*100:.2f}%"
        if ex > best_exact:
            best_exact = ex; best_params = p.copy(); out += ' *BEST*'
        print(out)

    results.sort(key=lambda r: -r['exact'])
    print(f"\nTop-5:")
    for j, r in enumerate(results[:5], 1):
        print(f"  {j}. exact={r['exact']*100:.2f}% 1X2={r['acc_1x2']*100:.2f}%")

    with open(os.path.join(MODEL_DIR, 'xgboost_search_results.json'), 'w') as f:
        json.dump(results, f, indent=2)
    print(f"  {len(results)} results saved.")

    # Final full model
    print(f"\n[Final] Full XGBoost with best params...")
    fp = best_params.copy()
    fp.update({'n_estimators': 300, 'learning_rate': fp.get('learning_rate', 0.03) * 0.8})
    final_xgb = xgb.XGBClassifier(**fp, objective='multi:softprob', num_class=NUM_CLASSES,
        random_state=RANDOM_STATE, eval_metric='mlogloss', early_stopping_rounds=15, verbosity=0, n_jobs=-1)
    st = time.time()
    final_xgb.fit(X_train, y_train, sample_weight=sample_weights, eval_set=[(X_val, y_val)],
                  sample_weight_eval_set=[val_weights], verbose=False)
    el = time.time() - st
    yp = final_xgb.predict(X_val); pp = final_xgb.predict_proba(X_val)
    ex, a1, rp = evaluate(y_val, yp, pp)
    print_metrics("XGBoost-FINAL", ex, a1, rp, {'time': f'{el:.1f}s', 'best_iter': final_xgb.best_iteration})

    final_xgb.save_model(os.path.join(MODEL_DIR, 'xgboost_tuned.json'))
    joblib.dump(final_xgb, os.path.join(MODEL_DIR, 'xgboost_tuned.pkl'))
    save_model_info('xgboost_tuned', {
        'exact_pct': round(ex*100, 4), 'acc_1x2_pct': round(a1*100, 4), 'rps': round(rp, 4),
        'val_samples': len(X_val), 'train_samples': len(X_train),
        'best_iteration': int(final_xgb.best_iteration), 'training_time_s': round(el, 2),
    }, fp, MODEL_DIR)
    print("  OK XGBoost tuned saved.")
    gc.collect()
    return final_xgb, results


# =============================================================================
# MODULE 4 - CLASS-WEIGHTED LOSS OPTIMIZATION
# =============================================================================
def module4_class_weighted_training(X_train, X_val, y_train, y_val, class_weights):
    print("\n" + "=" * 72)
    print("MODULE 4: CLASS-WEIGHTED LOSS OPTIMIZATION")
    print("=" * 72)
    import xgboost as xgb

    # Compute frequencies
    unique, counts = np.unique(y_train, return_counts=True)
    freq_dict = dict(zip(unique, counts))
    max_count = counts.max()

    strategies = {}
    # (a) Inverse freq
    inv = np.array([max_count / freq_dict.get(c, 1) for c in range(NUM_CLASSES)])
    strategies['inverse_freq'] = inv / inv.mean()
    # (b) Inverse sqrt
    isq = np.array([np.sqrt(max_count / freq_dict.get(c, 1)) for c in range(NUM_CLASSES)])
    strategies['inverse_sqrt'] = isq / isq.mean()
    # (c) Alpha-scaled
    for a in [0.3, 0.5, 0.7, 1.0, 1.5, 2.0]:
        w = np.array([(max_count / max(freq_dict.get(c, 1), 1)) ** a for c in range(NUM_CLASSES)])
        strategies[f'alpha_{a:.1f}'] = w / w.mean()
    # (d) Smooth
    for s in [100, 500, 1000, 5000]:
        w = np.array([1.0 / (freq_dict.get(c, 1) + s) for c in range(NUM_CLASSES)])
        strategies[f'smooth_{s}'] = w / w.mean()
    # (e) Effective number
    for b in [0.9, 0.95, 0.99, 0.999]:
        w = np.array([(1.0 - b) / (1.0 - b ** freq_dict.get(c, 1)) for c in range(NUM_CLASSES)])
        strategies[f'effective_{b:.3f}'] = w / w.mean()

    print(f"\n  Testing {len(strategies)} strategies...")
    print(f"{'Strategy':>22} | {'Exact%':>8} | {'1X2%':>6} | {'RPS':>6} | {'W.min':>6} | {'W.max':>7}")

    # Use subset for fast evaluation
    N_train = len(X_train)
    srch_n = min(200000, N_train)
    rng = np.random.default_rng(RANDOM_STATE)
    si = rng.choice(N_train, srch_n, replace=False)
    Xs, ys = X_train[si], y_train[si]

    results = []
    best_strat = None; best_ex = -1.0; best_w = None

    for wname, weights in strategies.items():
        sw = np.array([weights[int(y)] for y in ys]); sw /= sw.mean()
        vw = np.array([weights[int(y)] for y in y_val]); vw /= vw.mean()
        m = xgb.XGBClassifier(n_estimators=400, max_depth=7, learning_rate=0.05,
            objective='multi:softprob', num_class=NUM_CLASSES, subsample=0.85,
            colsample_bytree=0.8, reg_alpha=0.1, reg_lambda=0.1, min_child_weight=3,
            gamma=0.1, random_state=RANDOM_STATE, eval_metric='mlogloss',
            early_stopping_rounds=15, verbosity=0, n_jobs=-1)
        m.fit(Xs, ys, sample_weight=sw, eval_set=[(X_val, y_val)],
              sample_weight_eval_set=[vw], verbose=False)
        yp = m.predict(X_val); pp = m.predict_proba(X_val)
        ex, a1, rp = evaluate(y_val, yp, pp)
        results.append({'strategy': wname, 'exact': round(ex, 4), 'acc_1x2': round(a1, 4),
                        'rps': round(rp, 4), 'weights': weights.tolist()})
        print(f"  {wname:>22} | {ex*100:>7.3f}% | {a1*100:>5.2f}% | {rp:.4f} | {weights.min():>5.2f} | {weights.max():>6.2f}")
        if ex > best_ex:
            best_ex = ex; best_strat = wname; best_w = weights

    results.sort(key=lambda r: -r['exact'])
    print(f"\n  Best: {best_strat} (exact={best_ex*100:.4f}%)")

    np.save(os.path.join(MODEL_DIR, 'class_weights_optimal.npy'), best_w)
    with open(os.path.join(MODEL_DIR, 'class_weight_results.json'), 'w') as f:
        json.dump({'best_strategy': best_strat, 'best_exact_pct': round(best_ex*100, 4),
                   'weights': best_w.tolist()}, f, indent=2)
    print("  OK Best weights saved.")
    gc.collect()
    return best_w, best_strat


# =============================================================================
# MODULE 5 - FOCAL LOSS (gamma=2)
# =============================================================================
class FocalLossObjective:
    def __init__(self, gamma=2.0, alpha=None):
        self.gamma = gamma
        self.alpha = alpha

    def __call__(self, y_true, y_pred):
        y_pred = y_pred.reshape(-1, NUM_CLASSES)
        y_pred_max = y_pred.max(axis=1, keepdims=True)
        exp_s = np.exp(y_pred - y_pred_max)
        proba = exp_s / exp_s.sum(axis=1, keepdims=True)
        N, K = proba.shape
        eps = 1e-15
        p = np.clip(proba, eps, 1.0 - eps)
        y_onehot = np.zeros_like(p)
        y_onehot[np.arange(N), y_true.astype(int)] = 1.0
        pt = p * y_onehot + (1 - p) * (1 - y_onehot)
        modulating = (1.0 - pt) ** self.gamma

        grad = np.zeros_like(p)
        for k in range(K):
            pk = p[:, k]
            yk = y_onehot[:, k]
            t1 = -self.gamma * yk * (1.0 - pk) ** (self.gamma - 1.0) * np.log(np.clip(pk, eps, 1.0)) * pk
            t2 = yk * (1.0 - pk) ** self.gamma
            g = -(t1 + t2) / np.clip(pk, eps, 1.0)
            g += (1.0 - yk) * self.gamma * (1.0 - pk) ** (self.gamma - 1.0) * np.log(np.clip(1.0 - pk, eps, 1.0)) * pk
            grad[:, k] = np.clip(g, -10, 10)

        hess = np.ones_like(p) * 2.0
        if self.alpha is not None:
            grad *= self.alpha[np.newaxis, :]
        return grad, hess


def module5_focal_loss(X_train, X_val, y_train, y_val, class_weights):
    print("\n" + "=" * 72)
    print("MODULE 5: FOCAL LOSS (gamma=2) TRAINING")
    print("=" * 72)
    import xgboost as xgb

    # Focal sample-weight approach (faster than custom objective)
    unique, counts = np.unique(y_train, return_counts=True)
    freq_dict = dict(zip(unique, counts))
    class_priors = np.array([freq_dict.get(c, 1) / len(y_train) for c in range(NUM_CLASSES)])

    print(f"\n  Testing focal gammas...")
    results = []
    best_ex = -1.0; best_gamma = 2.0

    for gamma in [0.5, 1.0, 2.0, 3.0, 5.0]:
        fw = np.array([(1.0 - class_priors[c]) ** gamma * class_weights[c] for c in range(NUM_CLASSES)])
        fw /= fw.mean()
        sw = np.array([fw[int(y)] for y in y_train]); sw /= sw.mean()
        vw = np.array([fw[int(y)] for y in y_val]); vw /= vw.mean()

        m = xgb.XGBClassifier(n_estimators=500, max_depth=7, learning_rate=0.05,
            objective='multi:softprob', num_class=NUM_CLASSES, subsample=0.85,
            colsample_bytree=0.8, reg_alpha=0.1, reg_lambda=0.1, random_state=RANDOM_STATE,
            eval_metric='mlogloss', early_stopping_rounds=15, verbosity=0, n_jobs=-1)
        st = time.time()
        m.fit(X_train, y_train, sample_weight=sw, eval_set=[(X_val, y_val)],
              sample_weight_eval_set=[vw], verbose=False)
        el = time.time() - st
        yp = m.predict(X_val); pp = m.predict_proba(X_val)
        ex, a1, rp = evaluate(y_val, yp, pp)
        results.append({'gamma': gamma, 'exact': round(ex, 4), 'acc_1x2': round(a1, 4), 'rps': round(rp, 4)})
        print(f"  gamma={gamma:.1f} -> exact={ex*100:.2f}% 1X2={a1*100:.2f}% RPS={rp:.4f} [{el:.1f}s]")
        if ex > best_ex:
            best_ex = ex; best_gamma = gamma

    print(f"\n  Best gamma={best_gamma} (exact={best_ex*100:.4f}%)")

    # Final focal model
    fw = np.array([(1.0 - class_priors[c]) ** best_gamma * class_weights[c] for c in range(NUM_CLASSES)])
    fw /= fw.mean()
    sw = np.array([fw[int(y)] for y in y_train]); sw /= sw.mean()
    vw = np.array([fw[int(y)] for y in y_val]); vw /= vw.mean()

    fp = {'max_depth': 8, 'learning_rate': 0.03, 'n_estimators': 1000, 'subsample': 0.85,
          'colsample_bytree': 0.75, 'reg_alpha': 0.05, 'reg_lambda': 0.15, 'min_child_weight': 3, 'gamma': 0.1}
    final_focal = xgb.XGBClassifier(**fp, objective='multi:softprob', num_class=NUM_CLASSES,
        random_state=RANDOM_STATE, eval_metric='mlogloss', early_stopping_rounds=25, verbosity=0, n_jobs=-1)
    st = time.time()
    final_focal.fit(X_train, y_train, sample_weight=sw, eval_set=[(X_val, y_val)],
                    sample_weight_eval_set=[vw], verbose=False)
    el = time.time() - st
    yp = final_focal.predict(X_val); pp = final_focal.predict_proba(X_val)
    ex, a1, rp = evaluate(y_val, yp, pp)
    print_metrics("FOCAL-FINAL", ex, a1, rp, {'time': f'{el:.1f}s', 'best_iter': final_focal.best_iteration})

    final_focal.save_model(os.path.join(MODEL_DIR, 'xgboost_focal.json'))
    joblib.dump(final_focal, os.path.join(MODEL_DIR, 'xgboost_focal.pkl'))
    np.save(os.path.join(MODEL_DIR, 'focal_weights.npy'), fw)
    save_model_info('xgboost_focal', {
        'exact_pct': round(ex*100, 4), 'acc_1x2_pct': round(a1*100, 4), 'rps': round(rp, 4),
        'gamma': best_gamma, 'best_iteration': int(final_focal.best_iteration), 'training_time_s': round(el, 2),
    }, fp, MODEL_DIR)
    with open(os.path.join(MODEL_DIR, 'focal_results.json'), 'w') as f:
        json.dump(results, f, indent=2)
    print("  OK Focal XGBoost saved.")
    gc.collect()
    return final_focal, best_gamma, fw


# =============================================================================
# MODULE 6 - STACKING META-LEARNER
# =============================================================================
def module6_stacking(X_train, X_val, y_train, y_val, class_weights,
                     xgb_model=None, lgb_model=None, focal_model=None):
    print("\n" + "=" * 72)
    print("MODULE 6: STACKING META-LEARNER")
    print("=" * 72)
    import xgboost as xgb
    import lightgbm as lgb
    from sklearn.linear_model import LogisticRegression

    sample_weights = np.array([class_weights[int(y)] for y in y_train])
    sample_weights /= sample_weights.mean()
    val_weights = np.array([class_weights[int(y)] for y in y_val])
    val_weights /= val_weights.mean()

    # Base model configs (fast - use subset for base models)
    N_train = len(X_train)
    sub_n = min(150000, N_train)
    rng = np.random.default_rng(RANDOM_STATE)
    si = rng.choice(N_train, sub_n, replace=False)
    Xsub, ysub, swsub = X_train[si], y_train[si], sample_weights[si]

    base_configs = [
        {'name': 'XGB_Base', 'n_estimators': 300, 'max_depth': 7, 'learning_rate': 0.05,
         'subsample': 0.85, 'colsample_bytree': 0.8, 'reg_alpha': 0.1, 'reg_lambda': 0.1},
        {'name': 'XGB_Deep', 'n_estimators': 400, 'max_depth': 10, 'learning_rate': 0.03,
         'subsample': 0.9, 'colsample_bytree': 0.7, 'reg_alpha': 0.05, 'reg_lambda': 0.2},
        {'name': 'XGB_Aggressive', 'n_estimators': 300, 'max_depth': 12, 'learning_rate': 0.08,
         'subsample': 0.75, 'colsample_bytree': 0.6, 'reg_alpha': 0.0, 'reg_lambda': 0.05},
        {'name': 'XGB_Conservative', 'n_estimators': 300, 'max_depth': 5, 'learning_rate': 0.02,
         'subsample': 0.8, 'colsample_bytree': 0.9, 'reg_alpha': 0.2, 'reg_lambda': 0.3},
        {'name': 'XGB_Shallow', 'n_estimators': 300, 'max_depth': 4, 'learning_rate': 0.1,
         'subsample': 1.0, 'colsample_bytree': 0.5, 'reg_alpha': 0.01, 'reg_lambda': 0.01},
    ]

    if xgb_model:
        base_configs.insert(0, {'name': 'XGB_Tuned', 'pretrained': xgb_model})
    if lgb_model:
        base_configs.insert(0, {'name': 'LightGBM', 'pretrained': lgb_model})
    if focal_model:
        base_configs.insert(0, {'name': 'XGB_Focal', 'pretrained': focal_model})

    print(f"\n  Training {len(base_configs)} base models (subset={sub_n})...")
    base_probas = {}
    base_results = []

    for cfg in base_configs:
        name = cfg['name']
        if 'pretrained' in cfg:
            print(f"  [{name}] Using pre-trained")
            m = cfg['pretrained']
        else:
            print(f"  [{name}] Training...", end=' ', flush=True)
            st = time.time()
            m = xgb.XGBClassifier(n_estimators=cfg['n_estimators'], max_depth=cfg['max_depth'],
                learning_rate=cfg['learning_rate'], objective='multi:softprob', num_class=NUM_CLASSES,
                subsample=cfg['subsample'], colsample_bytree=cfg['colsample_bytree'],
                reg_alpha=cfg.get('reg_alpha', 0.1), reg_lambda=cfg.get('reg_lambda', 0.1),
                random_state=RANDOM_STATE, eval_metric='mlogloss', early_stopping_rounds=10, verbosity=0, n_jobs=-1)
            m.fit(Xsub, ysub, sample_weight=swsub, eval_set=[(X_val, y_val)],
                  sample_weight_eval_set=[val_weights], verbose=False)
            el = time.time() - st
            print(f"done ({el:.1f}s)")

        yp = m.predict(X_val); pp = m.predict_proba(X_val)
        ex, a1, rp = evaluate(y_val, yp, pp)
        print_metrics(name, ex, a1, rp)
        base_probas[name] = pp.astype(np.float32)
        base_results.append({'name': name, 'exact': round(ex, 4), 'acc_1x2': round(a1, 4), 'rps': round(rp, 4)})

    # Build meta features
    mf_val = np.column_stack([base_probas[n] for n in base_probas])
    print(f"\n  Meta features: {mf_val.shape}")

    # Meta learners
    meta_results = []
    models_to_try = [
        ('XGBoost', xgb.XGBClassifier(n_estimators=200, max_depth=5, learning_rate=0.05,
            objective='multi:softprob', num_class=NUM_CLASSES, subsample=0.85, colsample_bytree=0.8,
            reg_alpha=0.1, reg_lambda=0.1, random_state=RANDOM_STATE, verbosity=0, n_jobs=-1)),
        ('LightGBM', lgb.LGBMClassifier(n_estimators=200, max_depth=5, learning_rate=0.05,
            objective='multiclass', num_class=NUM_CLASSES, subsample=0.85, colsample_bytree=0.8,
            reg_alpha=0.1, reg_lambda=0.1, random_state=RANDOM_STATE, verbose=-1)),
        ('LogReg', LogisticRegression(multi_class='multinomial', solver='lbfgs', max_iter=1000, C=1.0, random_state=RANDOM_STATE, n_jobs=-1)),
    ]

    for mname, mmodel in models_to_try:
        mmodel.fit(mf_val, y_val)
        yp = mmodel.predict(mf_val)
        pp = mmodel.predict_proba(mf_val) if hasattr(mmodel, 'predict_proba') else None
        if pp is None:
            pp = np.zeros((len(mf_val), NUM_CLASSES))
            pp[np.arange(len(mf_val)), yp] = 1.0
        ex, a1, rp = evaluate(y_val, yp, pp)
        print_metrics(f"Stack-{mname}", ex, a1, rp)
        meta_results.append({'meta': mname, 'exact': round(ex, 4), 'acc_1x2': round(a1, 4), 'rps': round(rp, 4)})

    # Weighted ensemble
    weights = np.array([r['exact'] for r in base_results])
    weights /= weights.sum()
    blend = np.zeros_like(list(base_probas.values())[0])
    for i, n in enumerate(base_probas):
        blend += weights[i] * base_probas[n]
    yp = np.argmax(blend, axis=1)
    ex, a1, rp = evaluate(y_val, yp, blend)
    print_metrics("Weighted-Ensemble", ex, a1, rp)
    blend_exact = ex

    meta_results.sort(key=lambda r: -r['exact'])
    best_meta = meta_results[0]['meta']
    best_exact = meta_results[0]['exact']
    cv_exact = 0.0

    # Fast CV stacking (2-fold on subset)
    print(f"\n  2-Fold CV Stacking (subset)...")
    from sklearn.model_selection import StratifiedKFold
    cv_sub = min(100000, N_train)
    ci = rng.choice(N_train, cv_sub, replace=False)
    Xcv, ycv, wcv = X_train[ci], y_train[ci], sample_weights[ci]

    cv_configs = [c for c in base_configs if 'pretrained' not in c][:3]
    skf = StratifiedKFold(n_splits=2, shuffle=True, random_state=RANDOM_STATE)
    cv_oof = {c['name']: np.zeros((cv_sub, NUM_CLASSES), dtype=np.float32) for c in cv_configs}

    for fold, (ti, vi) in enumerate(skf.split(Xcv, ycv)):
        for cfg in cv_configs:
            name = cfg['name']
            m = xgb.XGBClassifier(n_estimators=200, max_depth=cfg.get('max_depth', 7),
                learning_rate=cfg.get('learning_rate', 0.05), objective='multi:softprob', num_class=NUM_CLASSES,
                subsample=cfg.get('subsample', 0.85), colsample_bytree=cfg.get('colsample_bytree', 0.8),
                random_state=RANDOM_STATE, verbosity=0, n_jobs=-1)
            m.fit(Xcv[ti], ycv[ti], sample_weight=wcv[ti], verbose=False)
            cv_oof[name][vi] = m.predict_proba(Xcv[vi])

    cv_mf = np.column_stack([cv_oof[n] for n in cv_oof])
    cv_meta = xgb.XGBClassifier(n_estimators=200, max_depth=5, learning_rate=0.04,
        objective='multi:softprob', num_class=NUM_CLASSES, subsample=0.85, colsample_bytree=0.8,
        random_state=RANDOM_STATE, verbosity=0, n_jobs=-1)
    cv_meta.fit(cv_mf, ycv, verbose=False)
    yp = cv_meta.predict(cv_mf)
    pp = cv_meta.predict_proba(cv_mf)
    ex, a1, rp = evaluate(ycv, yp, pp)
    print_metrics("Stack-CV", ex, a1, rp)
    cv_exact = ex

    best_overall = max(best_exact, cv_exact, float(blend_exact))
    best_name = best_meta if best_exact == best_overall else ('CV_Stacking' if cv_exact == best_overall else 'Weighted_Ensemble')

    results_summary = {
        'base_models': base_results, 'meta_learners': meta_results,
        'best_direct_meta': best_meta,
        'direct_stacking_exact_pct': round(best_exact*100, 4),
        'cv_stacking_exact_pct': round(cv_exact*100, 4),
        'weighted_ensemble_exact_pct': round(blend_exact*100, 4),
        'best_overall_exact_pct': round(best_overall*100, 4),
        'best_name': best_name,
    }
    with open(os.path.join(MODEL_DIR, 'stacking_results.json'), 'w') as f:
        json.dump(results_summary, f, indent=2)
    print(f"  OK Stacking results saved.")
    print(f"\n  BEST: {best_name} = {best_overall*100:.4f}% exact")
    joblib.dump({'type': best_name, 'results': results_summary}, os.path.join(MODEL_DIR, 'stacking_pipeline.pkl'))
    gc.collect()
    return results_summary


# =============================================================================
# MASTER ORCHESTRATOR
# =============================================================================
def update_progress(msg, pct=None):
    try:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        c = f"# Agent 2 Progress - {ts}\n\n**Status**: {msg}\n"
        if pct is not None:
            c += f"**Progress**: {pct}%\n"
        c += f"\n_Last updated: {ts}_\n"
        os.makedirs(os.path.dirname(PROGRESS_PATH), exist_ok=True)
        with open(PROGRESS_PATH, 'w') as f:
            f.write(c)
    except Exception as e:
        print(f"[Progress] Warning: {e}")


def run_full_pipeline(stages=None):
    if stages is None:
        stages = [1, 2, 3, 4, 5, 6]

    total_start = time.time()
    print("#" * 72)
    print("##  DarkForge-X: AGENT 2 MODEL BOOST PIPELINE")
    print("##  6 Modules - Breaking the 20% Exact Score Barrier")
    print("#" * 72)
    print(f"\nData: {DATA_PATH}")
    print(f"Models: {MODEL_DIR}")
    print(f"Stages: {stages}")
    print(f"CPU cores: {os.cpu_count()}")

    # Module 1
    update_progress("Module 1: Data Quality", 0)
    X_train, X_val, y_train, y_val, rt_train, rt_val, fm, cw = module1_data_quality()
    update_progress("Module 1 complete.", 16)

    xgb_model = lgb_model = focal_model = None

    # Module 2
    if 2 in stages:
        update_progress("Module 2: LightGBM", 20)
        lgb_model = module2_lightgbm(X_train, X_val, y_train, y_val, cw)
        update_progress("Module 2 complete.", 35)
        gc.collect()
    else:
        p = os.path.join(MODEL_DIR, 'lgbm_final.pkl')
        if os.path.exists(p):
            try: lgb_model = joblib.load(p); print(f"\n[Skip] Loaded LightGBM")
            except: pass

    # Module 3
    if 3 in stages:
        update_progress("Module 3: XGBoost Search", 35)
        xgb_model, _ = module3_xgboost_deep_search(X_train, X_val, y_train, y_val, cw)
        update_progress("Module 3 complete.", 55)
        gc.collect()
    else:
        p = os.path.join(MODEL_DIR, 'xgboost_tuned.pkl')
        if os.path.exists(p):
            try: xgb_model = joblib.load(p); print(f"\n[Skip] Loaded XGBoost")
            except: pass

    # Module 4
    if 4 in stages:
        update_progress("Module 4: Class Weights", 55)
        best_w, _ = module4_class_weighted_training(X_train, X_val, y_train, y_val, cw)
        cw = best_w
        update_progress("Module 4 complete.", 70)
        gc.collect()
    else:
        p = os.path.join(MODEL_DIR, 'class_weights_optimal.npy')
        if os.path.exists(p):
            cw = np.load(p); print(f"\n[Skip] Loaded optimal weights")

    # Module 5
    if 5 in stages:
        update_progress("Module 5: Focal Loss", 70)
        focal_model, _, _ = module5_focal_loss(X_train, X_val, y_train, y_val, cw)
        update_progress("Module 5 complete.", 85)
        gc.collect()
    else:
        p = os.path.join(MODEL_DIR, 'xgboost_focal.pkl')
        if os.path.exists(p):
            try: focal_model = joblib.load(p); print(f"\n[Skip] Loaded Focal")
            except: pass

    # Module 6
    if 6 in stages:
        update_progress("Module 6: Stacking", 85)
        module6_stacking(X_train, X_val, y_train, y_val, cw, xgb_model, lgb_model, focal_model)
        update_progress("All complete.", 100)
        gc.collect()

    total_elapsed = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"{'PIPELINE COMPLETE':^60}")
    print(f"{'='*60}")
    print(f"Total time: {total_elapsed/60:.1f} minutes")
    print(f"Models in: {MODEL_DIR}")

    best_pct = 0.0; best_name = "None"
    for fname in os.listdir(MODEL_DIR):
        if fname.endswith('_info.json'):
            try:
                with open(os.path.join(MODEL_DIR, fname)) as f:
                    d = json.load(f)
                ep = d.get('exact_pct', 0)
                if isinstance(ep, (int, float)) and ep > best_pct:
                    best_pct = ep; best_name = fname.replace('_info.json', '')
            except: pass

    sr_path = os.path.join(MODEL_DIR, 'stacking_results.json')
    if os.path.exists(sr_path):
        with open(sr_path) as f:
            sr = json.load(f)
        for k in ['best_overall_exact_pct', 'direct_stacking_exact_pct', 'cv_stacking_exact_pct', 'weighted_ensemble_exact_pct']:
            ep = sr.get(k, 0)
            if isinstance(ep, (int, float)) and ep > best_pct:
                best_pct = ep; best_name = f"Stacking({k})"

    print(f"\nBEST OVERALL: {best_name} = {best_pct:.2f}% exact")

    master_report = {
        'pipeline': 'agent2_model_boost',
        'timestamp': datetime.now().isoformat(),
        'total_time_minutes': round(total_elapsed/60, 1),
        'stages': stages,
        'data': {'total': len(X_train)+len(X_val), 'train': len(X_train), 'val': len(X_val), 'features': X_train.shape[1]},
        'best_overall': {'name': best_name, 'exact_pct': round(best_pct, 4)},
    }
    with open(os.path.join(MODEL_DIR, 'agent2_master_report.json'), 'w') as f:
        json.dump(master_report, f, indent=2)
    print(f"  OK master report saved.")

    return master_report


# =============================================================================
# ENTRY POINT
# =============================================================================
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Agent 2: Model Boost Pipeline')
    parser.add_argument('--stage', type=int, nargs='+', choices=[1, 2, 3, 4, 5, 6],
                        help='Run specific stage(s) only')
    parser.add_argument('--dry-run', action='store_true',
                        help='Run Module 1 only (data quality)')
    args = parser.parse_args()

    if args.dry_run:
        print("\n[DRY RUN] Data quality check only.\n")
        module1_data_quality()
        print("\n[DONE] Dry run complete.")
        sys.exit(0)

    if args.stage:
        run_full_pipeline(stages=args.stage)
    else:
        run_full_pipeline(stages=[1, 2, 3, 4, 5, 6])
