"""
meta_learner_ensemble.py — Train LogisticRegression to learn optimal blend weights
Uses existing trained models (no re-training needed)
"""
import sys, os, json, gc, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
os.environ['PYTHONIOENCODING'] = 'utf-8'

from direct_predictor import _load_training_data, FEATURES, NUM_CLASSES, class_to_score, result
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
import joblib
import xgboost as xgb

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
print("="*60)
print("META-LEARNER: Learning optimal blend weights")
print("="*60)

# Load data
X, y, _ = _load_training_data()
split = int(len(X) * 0.85)
X_train, X_val = X[:split], X[split:]
y_train, y_val = y[:split], y[split:]

print(f"Train: {len(X_train)}, Validation: {len(X_val)}")

# Preprocess
imp = SimpleImputer(strategy='median')
X_train_imp = imp.fit_transform(X_train)
X_val_imp = imp.transform(X_val)
scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train_imp)
X_val_s = scaler.transform(X_val_imp)

# Load XGBoost
print("\n[1/3] Loading XGBoost...")
xgb_path = os.path.join(MODEL_DIR, 'direct_score.json')
xgb_model = xgb.XGBClassifier()
xgb_model.load_model(xgb_path)
xgb_val = xgb_model.predict_proba(X_val)
print(f"  XGBoost validation probs: {xgb_val.shape}")

# Load DeepNN models from ensemble
print("\n[2/3] Loading DeepNN models from ensemble...")
blend_path = os.path.join(MODEL_DIR, 'mlp_blend.pkl')
ensemble = joblib.load(blend_path)
print(f"  Ensemble has {len(ensemble.models)} DeepNN models")

# Get individual DeepNN predictions on validation set
nn_val_probas = []
for i, m in enumerate(ensemble.models):
    X_imp = imp.transform(X_val)
    X_s = scaler.transform(X_imp)
    p = m.predict_proba(X_s)
    nn_val_probas.append(p)
    print(f"  Model {i}: probs shape {p.shape}")

# Build meta-features
X_meta = np.hstack([xgb_val] + nn_val_probas)
print(f"\nMeta features shape: {X_meta.shape} (25 × {1+len(nn_val_probas)} models = {X_meta.shape[1]} features)")

# Train meta-learner (LogisticRegression with strong regularization)
print("\n[3/3] Training meta-learner...")
meta = LogisticRegression(
    max_iter=1000,
    C=0.1,
    solver='lbfgs',
    random_state=42,
)
meta.fit(X_meta, y_val)

# Evaluate
y_pred = meta.predict(X_meta)
exact = np.mean(y_pred == y_val)
actual_1x2 = np.array([result(*class_to_score(c)) for c in y_val])
pred_1x2 = np.array([result(*class_to_score(c)) for c in y_pred])
acc_1x2 = np.mean(actual_1x2 == pred_1x2)
print(f"\n  Meta-learner exact: {exact*100:.2f}%")
print(f"  Meta-learner 1X2: {acc_1x2*100:.2f}%")

# Compare with current blend
X_val_blend = X_val.copy()
blend_val = ensemble.predict_proba(X_val_blend)
blend_pred = np.argmax(blend_val, axis=1)
blend_exact = np.mean(blend_pred == y_val)
print(f"\n  Current ensemble exact: {blend_exact*100:.2f}%")
print(f"  Improvement: {(exact - blend_exact)*100:.2f}%")

# Extract learned weights from meta-learner coefficients
coef = meta.coef_  # (25, 75) for 3 models
coef_abs = np.abs(coef).mean(axis=0)

# Each group of 25 corresponds to a model
n_models = 1 + len(nn_val_probas)
model_weights = []
for i in range(n_models):
    w = coef_abs[i*25:(i+1)*25].mean()
    model_weights.append(w)

total_w = sum(model_weights)
print(f"\nLearned weights:")
for i, w in enumerate(model_weights):
    name = 'XGBoost' if i == 0 else f'DeepNN-{i}'
    print(f"  {name}: {w/total_w:.1%}")

# Save meta-learner
os.makedirs(MODEL_DIR, exist_ok=True)
joblib.dump(meta, os.path.join(MODEL_DIR, 'meta_learner.pkl'))
print(f"\nSaved meta_learner.pkl")

# Update ensemble with learned weights
# Reconstruct with optimal blend
import torch
import torch.nn as nn

model_weights_norm = [w/total_w for w in model_weights]
ensemble.xgb_weight = model_weights_norm[0]
print(f"\nUpdated ensemble weights:")
print(f"  XGBoost: {ensemble.xgb_weight:.1%}")
for i, m in enumerate(ensemble.models):
    print(f"  DeepNN-{i+1}: {model_weights_norm[i+1]:.1%}")

joblib.dump(ensemble, blend_path)
print(f"\nSaved updated ensemble with learned weights to {blend_path}")

# Save meta-learner info
info_path = os.path.join(MODEL_DIR, 'meta_learner_info.json')
with open(info_path, 'w') as f:
    json.dump({
        'val_samples': len(X_val),
        'meta_exact_pct': round(exact*100, 2),
        'meta_1x2_pct': round(acc_1x2*100, 2),
        'blend_exact_pct': round(blend_exact*100, 2),
        'improvement_pct': round((exact - blend_exact)*100, 2),
        'learned_weights': {('XGBoost' if i==0 else f'DeepNN-{i}'): float(round(w/total_w, 4)) 
                           for i, w in enumerate(model_weights)},
    }, f, indent=2)
print(f"Saved meta_learner_info.json")

print("\n" + "="*60)
print("META-LEARNER COMPLETE")
print("="*60)
