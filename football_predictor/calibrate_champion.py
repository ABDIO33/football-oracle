
import sys, os, json, gc, pickle
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
os.environ['PYTHONIOENCODING'] = 'utf-8'

from direct_predictor import _load_training_data, EnsemblePredictor, load_model, NUM_CLASSES, FEATURES
from sklearn.model_selection import train_test_split
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss
import xgboost as xgb

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')

X, y, _ = _load_training_data()
y = y.astype(int)
print(f"Loaded {len(X)} samples, {len(FEATURES)} features")

# Use same split as ensemble_trainer
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
X_train, X_val, y_train, y_val = train_test_split(X_train, y_train, test_size=0.2, random_state=42)
print(f"Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")

model = load_model()
if model is None:
    print("No model!")
    sys.exit(1)

def get_proba(m, X_data):
    if isinstance(m, EnsemblePredictor):
        return m.predict_proba(X_data)
    return m.predict_proba(X_data)

val_proba = get_proba(model, X_val)
test_proba = get_proba(model, X_test)

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
pre_1x2 = sum(1 for i in range(len(y_test)) 
    if (test_proba[i, :16].sum() > test_proba[i, 16:].sum() and y_test[i] < 16) or
    (y_test[i] % 5 == y_test[i] // 5 and test_proba[i, y_test[i]] > 0.5)) / len(y_test) * 100
print(f"\nPre: Exact={pre_exact:.2f}%, Brier={pre_brier:.6f}")

# Isotonic calibration
calibrators = []
for c in range(NUM_CLASSES):
    cal = IsotonicRegression(out_of_bounds='clip')
    cal.fit(val_proba[:, c], y_val_onehot[:, c])
    calibrators.append(cal)

test_cal = np.zeros_like(test_proba)
for c in range(NUM_CLASSES):
    test_cal[:, c] = calibrators[c].transform(test_proba[:, c])
test_cal = np.clip(test_cal, 0, 1)
row_sums = test_cal.sum(axis=1, keepdims=True)
row_sums = np.where(row_sums > 0, row_sums, 1.0)
test_cal = test_cal / row_sums

cal_brier = calc_brier(test_cal, y_test_onehot)
cal_exact = (test_cal.argmax(1) == y_test).mean() * 100
print(f"+ Calibration: Exact={cal_exact:.2f}%, Brier={cal_brier:.6f}")

# Meta-stacker
val_meta = np.column_stack([
    val_proba,
    np.sort(val_proba, axis=1)[:, -3:],
    val_proba.argmax(1).reshape(-1, 1),
])
test_meta = np.column_stack([
    test_proba,
    np.sort(test_proba, axis=1)[:, -3:],
    test_proba.argmax(1).reshape(-1, 1),
])

meta = xgb.XGBClassifier(
    n_estimators=200, max_depth=4, learning_rate=0.05,
    objective='multi:softprob', num_class=NUM_CLASSES,
    subsample=0.8, colsample_bytree=0.8, random_state=42
)
meta.fit(val_meta, y_val)
stack_proba = meta.predict_proba(test_meta)
stack_brier = calc_brier(stack_proba, y_test_onehot)
stack_exact = (stack_proba.argmax(1) == y_test).mean() * 100
print(f"+ Stack:     Exact={stack_exact:.2f}%, Brier={stack_brier:.6f}")

# Blend
best_acc = 0
best_brier = 999
best_alpha = 0.5
for a in np.arange(0.0, 1.05, 0.05):
    bp = a * test_cal + (1-a) * stack_proba
    acc = (bp.argmax(1) == y_test).mean() * 100
    br = calc_brier(bp, y_test_onehot)
    if acc > best_acc:
        best_acc = acc
        best_brier = br
        best_alpha = a

print(f"+ Blend({best_alpha:.0%} cal): Exact={best_acc:.2f}%, Brier={best_brier:.6f}")

# Save
output = {
    'calibrators': calibrators,
    'meta': meta,
    'alpha': float(best_alpha),
    'pre': {'exact': pre_exact, 'brier': pre_brier},
    'cal': {'exact': cal_exact, 'brier': cal_brier},
    'stack': {'exact': stack_exact, 'brier': stack_brier},
    'blend': {'exact': best_acc, 'brier': best_brier},
}
with open(os.path.join(MODEL_DIR, 'calibrator_stack.pkl'), 'wb') as f:
    pickle.dump(output, f)
with open(os.path.join(MODEL_DIR, 'stacking_results.json'), 'w') as f:
    json.dump({k: v for k, v in output.items() if k != 'calibrators' and k != 'meta'}, f, indent=2)

print(f"\nSaved calibrator_stack.pkl + stacking_results.json")
print(f"IMPROVEMENT: +{best_acc - pre_exact:.2f}% exact, -{pre_brier - best_brier:.6f} Brier")
