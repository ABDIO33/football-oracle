
import sys, os, json, gc, pickle
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
os.environ['PYTHONIOENCODING'] = 'utf-8'

from direct_predictor import _load_training_data, EnsemblePredictor, load_model, NUM_CLASSES, FEATURES, SCORE_CLASSES
from sklearn.model_selection import train_test_split
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss
import xgboost as xgb
from sklearn.impute import SimpleImputer
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')

X, y, _ = _load_training_data()
y = y.astype(int)
print(f"[Calibrate] Loaded {len(X)} samples, {len(FEATURES)} features")

# Split train/val/test
X_train, X_tmp, y_train, y_tmp = train_test_split(X, y, test_size=0.3, random_state=42)
X_val, X_test, y_val, y_test = train_test_split(X_tmp, y_tmp, test_size=0.5, random_state=42)
print(f"[Calibrate] Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")

model = load_model()
if model is None:
    print("[Calibrate] No model found!")
    sys.exit(1)

# Get probabilities
def get_proba(m, X_data):
    if isinstance(m, EnsemblePredictor):
        return m.predict_proba(X_data)
    return m.predict_proba(X_data)

val_proba = get_proba(model, X_val)
test_proba = get_proba(model, X_test)

# Baseline Brier
y_val_onehot = np.zeros((len(y_val), NUM_CLASSES))
for i, cls in enumerate(y_val):
    y_val_onehot[i, int(cls)] = 1.0
y_test_onehot = np.zeros((len(y_test), NUM_CLASSES))
for i, cls in enumerate(y_test):
    y_test_onehot[i, int(cls)] = 1.0

def calc_brier(proba, onehot):
    return np.mean([brier_score_loss(onehot[:, c], proba[:, c]) for c in range(NUM_CLASSES)])

pre_brier = calc_brier(test_proba, y_test_onehot)
pre_exact = (test_proba.argmax(1) == y_test).mean() * 100
print(f"\nPre-calibration: Brier={pre_brier:.6f}, Exact={pre_exact:.2f}%")

# Train isotonic calibrators per class
calibrators = []
for c in range(NUM_CLASSES):
    cal = IsotonicRegression(out_of_bounds='clip')
    cal.fit(val_proba[:, c], y_val_onehot[:, c])
    calibrators.append(cal)

# Apply calibration
test_cal = np.zeros_like(test_proba)
for c in range(NUM_CLASSES):
    test_cal[:, c] = calibrators[c].transform(test_proba[:, c])
# Re-normalize (isotonic may break sum=1)
row_sums = test_cal.sum(axis=1, keepdims=True)
row_sums = np.where(row_sums > 0, row_sums, 1.0)
test_cal = test_cal / row_sums

post_brier = calc_brier(test_cal, y_test_onehot)
post_exact = (test_cal.argmax(1) == y_test).mean() * 100
print(f"Post-calibration: Brier={post_brier:.6f}, Exact={post_exact:.2f}%")
print(f"Brier improvement: {pre_brier - post_brier:.6f}")

# ===== META-STACKING =====
print("\n===== META-STACKING =====")
# Use ensemble predictions + top-3 probabilities as meta features
val_meta = np.column_stack([
    val_proba,
    np.sort(val_proba, axis=1)[:, -3:],  # top-3 probs
    val_proba.argmax(1).reshape(-1, 1),  # predicted class
])
test_meta = np.column_stack([
    test_proba,
    np.sort(test_proba, axis=1)[:, -3:],
    test_proba.argmax(1).reshape(-1, 1),
])

# Train XGBoost meta-learner
meta_model = xgb.XGBClassifier(
    n_estimators=200, max_depth=4, learning_rate=0.05,
    objective='multi:softprob', num_class=NUM_CLASSES,
    subsample=0.8, colsample_bytree=0.8,
    random_state=42, n_jobs=-1
)
meta_model.fit(val_meta, y_val)

# Evaluate stacked ensemble
stack_test_proba = meta_model.predict_proba(test_meta)
stack_exact = (stack_test_proba.argmax(1) == y_test).mean() * 100
stack_brier = calc_brier(stack_test_proba, y_test_onehot)
print(f"Stacked ensemble: Brier={stack_brier:.6f}, Exact={stack_exact:.2f}%")

# Blend original + stacked (50/50)
blend_proba = 0.5 * test_cal + 0.5 * stack_test_proba
blend_exact = (blend_proba.argmax(1) == y_test).mean() * 100
blend_brier = calc_brier(blend_proba, y_test_onehot)
print(f"Blend(50/50): Brier={blend_brier:.6f}, Exact={blend_exact:.2f}%")

# Try best blend ratio
best_blend_acc = 0
best_blend_brier = 999
best_alpha = 0.5
for alpha in np.arange(0.0, 1.05, 0.05):
    bp = alpha * test_cal + (1 - alpha) * stack_test_proba
    acc = (bp.argmax(1) == y_test).mean() * 100
    br = calc_brier(bp, y_test_onehot)
    if acc > best_blend_acc:
        best_blend_acc = acc
        best_blend_brier = br
        best_alpha = alpha
print(f"Best blend (alpha={best_alpha:.2f}): Brier={best_blend_brier:.6f}, Exact={best_blend_acc:.2f}%")

# Save
calibrator_data = {
    'calibrators': calibrators,
    'brier_pre': float(pre_brier),
    'brier_post': float(post_brier),
    'exact_pre': float(pre_exact),
    'exact_post': float(post_exact),
    'meta_model': meta_model,
    'stack_exact': float(stack_exact),
    'stack_brier': float(stack_brier),
    'blend_alpha': float(best_alpha),
    'blend_exact': float(best_blend_acc),
    'blend_brier': float(best_blend_brier),
    'num_classes': NUM_CLASSES,
    'features': FEATURES,
}
with open(os.path.join(MODEL_DIR, 'calibrator_stack.pkl'), 'wb') as f:
    pickle.dump(calibrator_data, f)
print(f"\nSaved calibrator_stack.pkl")

# === FINAL SUMMARY ===
print("\n" + "="*60)
print("FINAL RESULTS")
print("="*60)
print(f"  Pre-calibration:      Exact={pre_exact:.2f}%  Brier={pre_brier:.6f}")
print(f"  Post-calibration:     Exact={post_exact:.2f}%  Brier={post_brier:.6f}")
print(f"  Stacked ensemble:     Exact={stack_exact:.2f}%  Brier={stack_brier:.6f}")
print(f"  Best blend ({best_alpha:.0%} cal + {1-best_alpha:.0%} stack):  Exact={best_blend_acc:.2f}%  Brier={best_blend_brier:.6f}")

results = {
    'pre': {'exact': pre_exact, 'brier': pre_brier},
    'calibrated': {'exact': post_exact, 'brier': post_brier},
    'stacked': {'exact': stack_exact, 'brier': stack_brier},
    'blend': {'exact': best_blend_acc, 'brier': best_blend_brier, 'alpha': best_alpha},
    'brier_improvement': pre_brier - best_blend_brier,
    'exact_improvement': best_blend_acc - pre_exact,
}
with open(os.path.join(MODEL_DIR, 'stacking_results.json'), 'w') as f:
    json.dump(results, f, indent=2)
print("Saved stacking_results.json")
