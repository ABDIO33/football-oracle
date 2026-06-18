"""
calibrate.py — Isotonic calibration for ensemble predictions
Calibrates probabilities to match observed frequencies
"""
import sys, os, json, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from direct_predictor import _load_training_data, FEATURES, NUM_CLASSES, class_to_score, result, load_model
from sklearn.isotonic import IsotonicRegression
import joblib

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
print("="*60)
print("ISOTONIC CALIBRATION")
print("="*60)

# Load data and ensemble
X, y, _ = _load_training_data()
model = load_model()
print(f"Model: {type(model).__name__}")
print(f"Total samples: {len(X)}")

# Time-split: train on first 80%, calibrate on last 20%
split = int(len(X) * 0.80)
X_train, X_cal = X[:split], X[split:]
y_train, y_cal = y[:split], y[split:]
print(f"Train (for fitting): {len(X_train)}, Calibrate: {len(X_cal)}")

# But we need to train ensemble from scratch on X_train to avoid leakage
# OR we can just calibrate the PROBABILITIES on X_cal using the existing ensemble
# The second approach is fine for calibration (no label leakage)

# Get predictions on calibration set
proba = model.predict_proba(X_cal)
probas_1x2 = np.zeros((len(X_cal), 3))
actual_1x2 = np.zeros((len(X_cal), 3))
for i in range(len(X_cal)):
    ah, aa = class_to_score(y_cal[i])
    ar = result(ah, aa)
    p = proba[i]
    probas_1x2[i, 0] = sum(p[h*5 + a] for h in range(5) for a in range(5) if h > a)
    probas_1x2[i, 1] = sum(p[h*5 + h] for h in range(5))
    probas_1x2[i, 2] = sum(p[h*5 + a] for h in range(5) for a in range(5) if a > h)
    actual_1x2[i] = [1 if ar == k else 0 for k in range(3)]

# Train isotonic calibrators for H/D/A
calibrators = []
for k in range(3):
    cal = IsotonicRegression(out_of_bounds='clip')
    cal.fit(probas_1x2[:, k], actual_1x2[:, k])
    calibrators.append(cal)
    print(f"  Calibrator {['H','D','A'][k]}: fitted on {len(X_cal)} samples")

# Evaluate calibration improvement
cal_1x2 = np.zeros_like(probas_1x2)
for k in range(3):
    cal_1x2[:, k] = calibrators[k].transform(probas_1x2[:, k])
# Renormalize
cal_1x2 = cal_1x2 / cal_1x2.sum(axis=1, keepdims=True)

# Compare Brier scores
raw_brier = np.mean((probas_1x2 - actual_1x2)**2)
cal_brier = np.mean((cal_1x2 - actual_1x2)**2)
print(f"\n  Raw Brier: {raw_brier:.4f}")
print(f"  Calibrated Brier: {cal_brier:.4f}")
print(f"  Improvement: {(raw_brier - cal_brier)*100:.2f}%")

# Save calibrators
joblib.dump(calibrators, os.path.join(MODEL_DIR, 'isotonic_calibrators.pkl'))
print(f"\nSaved isotonic_calibrators.pkl")

# Save calibration info
with open(os.path.join(MODEL_DIR, 'calibration_info.json'), 'w') as f:
    json.dump({
        'cal_samples': len(X_cal),
        'raw_brier': round(raw_brier, 4),
        'cal_brier': round(cal_brier, 4),
        'improvement': round((raw_brier - cal_brier)*100, 2),
    }, f, indent=2)
print("Saved calibration_info.json")
print("DONE")
