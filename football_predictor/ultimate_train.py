"""
ultimate_train.py -- ????? XGBoost + Stacking Ensemble ?????? ?? 30%
?????? training_data_v3.npz (772K x 120 feature)
"""

import os, sys, time, gc, json, warnings
import numpy as np
warnings.filterwarnings('ignore')
os.environ['PYTHONWARNINGS'] = 'ignore'
os.environ['OMP_NUM_THREADS'] = '8'

MODEL_DIR = 'C:/Users/zake.exe/Desktop/Score Exact 100/football_predictor/models'

# Load data
t0 = time.time()
print("="*60)
print("ULTIMATE TRAINER - Score Exact 100 -> 30%")
print("="*60)

data = np.load(os.path.join(os.path.dirname(__file__), 'training_data_v3.npz'), allow_pickle=True)
X = data['X'].astype(np.float32)
y = data['y'].astype(np.int32)
match_ids = data['match_ids']
print(f"Loaded: {X.shape}, {len(np.unique(y))} classes, {time.time()-t0:.1f}s")
print(f"Home wins: {(y < 5).sum()}, Draws: {(y % 5 == y // 5).sum()}, Away wins: {(y % 5 < y // 5).sum()}")

# Walk-forward split: chronologically
# Sort by match_ids (chronological)
order = np.argsort(match_ids)
X = X[order]
y = y[order]
match_ids = match_ids[order]

# Split: 80% train, 10% val, 10% test (walk-forward)
n = len(X)
n_train = int(n * 0.8)
n_val = int(n * 0.1)

X_train = X[:n_train]
y_train = y[:n_train]
X_val = X[n_train:n_train+n_val]
y_val = y[n_train:n_train+n_val]
X_test = X[n_train+n_val:]
y_test = y[n_train+n_val:]

print(f"\nSplit: train={len(y_train):,} | val={len(y_val):,} | test={len(y_test):,}")
print(f"Train: HW={((y_train<5).sum()):,} D={((y_train%5==y_train//5).sum()):,} AW={((y_train%5<y_train//5).sum()):,}")
print(f"Test:  HW={((y_test<5).sum()):,} D={((y_test%5==y_test//5).sum()):,} AW={((y_test%5<y_test//5).sum()):,}")

def accuracy_exact(y_true, y_pred):
    return np.mean(y_true == y_pred)

def accuracy_1x2(y_true, y_pred):
    true_h = y_true // 5
    true_a = y_true % 5
    pred_h = y_pred // 5  
    pred_a = y_pred % 5
    true_r = np.where(true_h > true_a, 0, np.where(true_h == true_a, 1, 2))
    pred_r = np.where(pred_h > pred_a, 0, np.where(pred_h == pred_a, 1, 2))
    return np.mean(true_r == pred_r)

def rps_score(y_true, y_pred_proba):
    """Ranked Probability Score"""
    n = len(y_true)
    rps = 0.0
    # Convert to 3-class (1X2) cumulative distribution
    for i in range(n):
        probs = y_pred_proba[i]
        # Home win: scores where home > away
        home_prob = sum(probs[h*5+a] for h in range(5) for a in range(5) if h > a)
        draw_prob = sum(probs[h*5+h] for h in range(5))
        away_prob = sum(probs[h*5+a] for h in range(5) for a in range(5) if h < a)
        
        actual_h = 1 if y_true[i] < 5 or (y_true[i] // 5 > y_true[i] % 5) else 0
        actual_d = 1 if y_true[i] // 5 == y_true[i] % 5 else 0
        actual_a = 1 if y_true[i] // 5 < y_true[i] % 5 else 0
        
        cum_pred = np.array([home_prob, home_prob+draw_prob, 1.0]) 
        cum_actual = np.array([actual_h, actual_h+actual_d, 1.0])
        
        rps += np.sum((cum_pred - cum_actual)**2) / 2
    return rps / n

# ============ TRAINING ============
print("\n" + "="*60)
print("TRAINING XGBOOST MODELS")
print("="*60)

import xgboost as xgb

models = []
model_names = []

# Model 1: Standard XGBoost
print("\n[1/5] XGB-v1 (depth=6, lr=0.05, hist)...")
t1 = time.time()
m1 = xgb.XGBClassifier(
    n_estimators=2000, max_depth=6, learning_rate=0.05,
    subsample=0.8, colsample_bytree=0.6,
    reg_alpha=0.01, reg_lambda=0.1,
    tree_method='hist', random_state=42,
    n_jobs=8, eval_metric='mlogloss',
    early_stopping_rounds=50
)
m1.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
pred1 = m1.predict(X_val)
ex1 = accuracy_exact(y_val, pred1)
x1 = accuracy_1x2(y_val, pred1)
print(f"  XGB-v1: Exact={ex1:.4f} 1X2={x1:.4f} ({time.time()-t1:.1f}s)")
models.append(m1)
model_names.append('XGB-v1')

# Model 2: Deeper XGBoost
print("\n[2/5] XGB-v2 (depth=8, lr=0.03)...")
t1 = time.time()
m2 = xgb.XGBClassifier(
    n_estimators=1500, max_depth=8, learning_rate=0.03,
    subsample=0.7, colsample_bytree=0.5,
    reg_alpha=0.05, reg_lambda=0.2,
    tree_method='hist', random_state=43,
    n_jobs=8, eval_metric='mlogloss',
    early_stopping_rounds=50
)
m2.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
pred2 = m2.predict(X_val)
ex2 = accuracy_exact(y_val, pred2)
x2 = accuracy_1x2(y_val, pred2)
print(f"  XGB-v2: Exact={ex2:.4f} 1X2={x2:.4f} ({time.time()-t1:.1f}s)")
models.append(m2)
model_names.append('XGB-v2')

# Model 3: Fast XGBoost (shallow, many trees)
print("\n[3/5] XGB-v3 (depth=4, lr=0.08)...")
t1 = time.time()
m3 = xgb.XGBClassifier(
    n_estimators=3000, max_depth=4, learning_rate=0.08,
    subsample=0.9, colsample_bytree=0.8,
    reg_alpha=0, reg_lambda=0.05,
    tree_method='hist', random_state=44,
    n_jobs=8, eval_metric='mlogloss',
    early_stopping_rounds=50
)
m3.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
pred3 = m3.predict(X_val)
ex3 = accuracy_exact(y_val, pred3)
x3 = accuracy_1x2(y_val, pred3)
print(f"  XGB-v3: Exact={ex3:.4f} 1X2={x3:.4f} ({time.time()-t1:.1f}s)")
models.append(m3)
model_names.append('XGB-v3')

# Model 4: High regularization XGBoost
print("\n[4/5] XGB-v4 (depth=6, lr=0.02, high reg)...")
t1 = time.time()
m4 = xgb.XGBClassifier(
    n_estimators=1000, max_depth=6, learning_rate=0.02,
    subsample=0.6, colsample_bytree=0.4,
    reg_alpha=0.1, reg_lambda=0.5, gamma=0.1,
    tree_method='hist', random_state=45,
    n_jobs=8, eval_metric='mlogloss',
    early_stopping_rounds=50
)
m4.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
pred4 = m4.predict(X_val)
ex4 = accuracy_exact(y_val, pred4)
x4 = accuracy_1x2(y_val, pred4)
print(f"  XGB-v4: Exact={ex4:.4f} 1X2={x4:.4f} ({time.time()-t1:.1f}s)")
models.append(m4)
model_names.append('XGB-v4')

# Model 5: XGBoost with class weights
print("\n[5/5] XGB-v5 (class_weight=balanced)...")
t1 = time.time()
# Calculate class weights
classes, counts = np.unique(y_train, return_counts=True)
weight = {int(c): float(len(y_train)) / (len(classes) * float(counts[i])) 
          for i, c in enumerate(classes)}
m5 = xgb.XGBClassifier(
    n_estimators=2000, max_depth=6, learning_rate=0.05,
    subsample=0.8, colsample_bytree=0.6,
    reg_alpha=0.01, reg_lambda=0.1,
    tree_method='hist', random_state=46,
    n_jobs=8, eval_metric='mlogloss',
    sample_weight=np.array([weight.get(int(yi), 1.0) for yi in y_train]),
    early_stopping_rounds=50
)
m5.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
pred5 = m5.predict(X_val)
ex5 = accuracy_exact(y_val, pred5)
x5 = accuracy_1x2(y_val, pred5)
print(f"  XGB-v5: Exact={ex5:.4f} 1X2={x5:.4f} ({time.time()-t1:.1f}s)")
models.append(m5)
model_names.append('XGB-v5')

# ============ ENSEMBLE ============
print("\n" + "="*60)
print("ENSEMBLE BLENDING")
print("="*60)

# Get val predictions from all models
val_preds_proba = []
for m in models:
    p = m.predict_proba(X_val)
    val_preds_proba.append(p)

test_preds_proba = []
for m in models:
    p = m.predict_proba(X_test)
    test_preds_proba.append(p)

# Try different blend weights
print("\nSearching optimal blend weights...")
best_exact = 0
best_weights = None
best_val_pred = None

# Grid search weights
for w1 in np.arange(0, 1.1, 0.1):
    for w2 in np.arange(0, 1.1, 0.1):
        w3 = max(0, 1.0 - w1 - w2)
        if w3 < 0: continue
        
        # Remaining weight for models 3,4,5
        remaining = w3
        if remaining <= 0: continue
        
        # Distribute remaining among models 3,4,5 equally
        ws = [w1, w2, remaining * 0.33, remaining * 0.33, remaining * 0.34]
        
        blend = np.zeros((len(y_val), 25))
        for mi in range(5):
            blend += ws[mi] * val_preds_proba[mi]
        
        preds = np.argmax(blend, axis=1)
        ex = accuracy_exact(y_val, preds)
        x1x2 = accuracy_1x2(y_val, preds)
        
        if ex > best_exact:
            best_exact = ex
            best_weights = ws.copy()
            best_val_pred = preds

print(f"\nBest blend weights:")
for i, name in enumerate(model_names):
    print(f"  {name}: {best_weights[i]:.3f}")
print(f"  Val Exact: {best_exact:.4f}")

# Evaluate best blend on test set
blend_test = np.zeros((len(y_test), 25))
for mi in range(5):
    blend_test += best_weights[mi] * test_preds_proba[mi]
test_preds = np.argmax(blend_test, axis=1)
test_exact = accuracy_exact(y_test, test_preds)
test_1x2 = accuracy_1x2(y_test, test_preds)
rps = rps_score(y_test, blend_test)

print(f"\n{'='*60}")
print(f"TEST SET RESULTS")
print(f"{'='*60}")
print(f"  Exact Score: {test_exact*100:.2f}%")
print(f"  1X2 Accuracy: {test_1x2*100:.2f}%")
print(f"  RPS: {rps:.4f}")
print(f"  Test samples: {len(y_test):,}")

# ============ SAVE ============
print("\n" + "="*60)
print("SAVING ENSEMBLE")
print("="*60)

import joblib

ensemble = {
    'models': models,
    'weights': best_weights,
    'model_names': model_names,
    'imputer': None,
    'scaler': None,
}
out_path = os.path.join(MODEL_DIR, 'ultimate_30pct.pkl')
joblib.dump(ensemble, out_path, compress=3)
print(f"Saved: {out_path}")

# Save results
results = {
    'test_exact': float(test_exact),
    'test_1x2': float(test_1x2),
    'test_rps': float(rps),
    'val_exact': float(best_exact),
    'weights': best_weights,
    'n_train': len(y_train),
    'n_val': len(y_val),
    'n_test': len(y_test),
    'features': 120,
    'time_minutes': (time.time()-t0)/60,
}
with open(os.path.join(MODEL_DIR, 'ultimate_results.json'), 'w') as f:
    json.dump(results, f, indent=2)
print(f"Results saved to ultimate_results.json")

# ============ INDIVIDUAL MODEL EVALUATION ============
print("\n" + "="*60)
print("INDIVIDUAL MODEL PERFORMANCE ON TEST")
print("="*60)
for mi, name in enumerate(model_names):
    preds = np.argmax(test_preds_proba[mi], axis=1)
    ex = accuracy_exact(y_test, preds)
    x1 = accuracy_1x2(y_test, preds)
    print(f"  {name}: Exact={ex:.4f} 1X2={x1:.4f}")

print(f"\nTotal time: {(time.time()-t0)/60:.1f} minutes")
print("DONE!")
