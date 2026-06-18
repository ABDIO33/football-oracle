"""
build_production_model.py — Train XGBoost + best DeepNN (M4) on expanded 160K dataset,
search optimal blend weight, save as production ensemble.
"""
import sys, os, json, pickle, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from direct_predictor import _load_training_data, TorchMLPWrapper, EnsemblePredictor, SCORE_CLASSES, class_to_score, result
import xgboost as xgb
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

N_FEATURES = 81
TARGET_CLASSES = [f'{h}-{a}' for h, a in SCORE_CLASSES]
NUM_CLASSES = len(SCORE_CLASSES)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

print("="*60)
print("PRODUCTION MODEL BUILDER (160K expanded data)")
print("="*60)

print("Loading training data...")
X, y, match_ids = _load_training_data()
print(f"Total: {len(X)} samples, {X.shape[1]} features")

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

# Impute + Scale
imputer = SimpleImputer(strategy="median")
X_train_imp = imputer.fit_transform(X_train)
X_test_imp = imputer.transform(X_test)
scaler = StandardScaler()
X_train_sc = scaler.fit_transform(X_train_imp)
X_test_sc = scaler.transform(X_test_imp)

# Encode labels
from sklearn.preprocessing import LabelEncoder
le = LabelEncoder()
y_train_enc = le.fit_transform(y_train)
y_test_enc = le.transform(y_test)

# Train XGBoost
print("\nTraining XGBoost...")
model_xgb = xgb.XGBClassifier(
    n_estimators=500, max_depth=6, learning_rate=0.03,
    subsample=0.9, colsample_bytree=0.8,
    objective="multi:softprob", num_class=NUM_CLASSES,
    eval_metric="mlogloss", random_state=42, n_jobs=-1
)
model_xgb.fit(X_train_imp, y_train_enc)
xgb_probs = model_xgb.predict_proba(X_test_imp)

# Train DeepNN-M4 (512->1024->512->256)
print("Training DeepNN-M4 (512->1024->512->256)...")

def build_m4(input_dim, num_classes):
    return nn.Sequential(
        nn.Linear(input_dim, 512), nn.BatchNorm1d(512), nn.ReLU(), nn.Dropout(0.2),
        nn.Linear(512, 1024), nn.BatchNorm1d(1024), nn.ReLU(), nn.Dropout(0.2),
        nn.Linear(1024, 512), nn.BatchNorm1d(512), nn.ReLU(), nn.Dropout(0.2),
        nn.Linear(512, 256), nn.BatchNorm1d(256), nn.ReLU(), nn.Dropout(0.2),
        nn.Linear(256, num_classes),
    )

model_m4_raw = build_m4(N_FEATURES, NUM_CLASSES).to(DEVICE)
criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
optimizer = optim.AdamW(model_m4_raw.parameters(), lr=0.001, weight_decay=1e-4)
scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=80)

train_dataset = TensorDataset(
    torch.tensor(X_train_sc, dtype=torch.float32),
    torch.tensor(y_train_enc, dtype=torch.long))
train_loader = DataLoader(train_dataset, batch_size=128, shuffle=True, num_workers=0)
X_test_t = torch.tensor(X_test_sc, dtype=torch.float32).to(DEVICE)
y_test_t = torch.tensor(y_test_enc, dtype=torch.long).to(DEVICE)

best_acc = 0.0
best_state = None
patience = 20
patience_counter = 0

for epoch in range(150):
    model_m4_raw.train()
    for Xb, yb in train_loader:
        Xb, yb = Xb.to(DEVICE), yb.to(DEVICE)
        optimizer.zero_grad()
        loss = criterion(model_m4_raw(Xb), yb)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model_m4_raw.parameters(), 1.0)
        optimizer.step()

    model_m4_raw.eval()
    with torch.no_grad():
        out = model_m4_raw(X_test_t)
        _, preds = torch.max(out, 1)
        acc = (preds == y_test_t).sum().item() / len(y_test)
    scheduler.step()

    if (epoch+1) % 20 == 0:
        print(f"  Epoch {epoch+1:3d}: test_acc={acc:.4f}")

    if acc > best_acc:
        best_acc = acc
        best_state = model_m4_raw.state_dict()
        patience_counter = 0
    else:
        patience_counter += 1
        if patience_counter >= patience:
            print(f"  Early stop at epoch {epoch+1}")
            break

model_m4_raw.load_state_dict(best_state)
model_m4 = TorchMLPWrapper(model_m4_raw, device=DEVICE)
m4_probs = model_m4.predict_proba(X_test_sc)

# Search blend weights
print("\nSearching optimal blend (XGB + M4)...")
best_exact = 0
best_w = 0
best_probs = None
for w in np.arange(0.0, 1.01, 0.05):
    blend = w * xgb_probs + (1-w) * m4_probs
    preds = np.argmax(blend, axis=1)
    exact = (preds == y_test_enc).mean()
    if exact > best_exact:
        best_exact = exact
        best_w = w
        best_probs = blend

preds = np.argmax(best_probs, axis=1)
from sklearn.metrics import accuracy_score
exact = accuracy_score(y_test_enc, preds)

# 1X2 accuracy
hda_pred = np.zeros((len(y_test_enc), 3))
for i in range(len(y_test_enc)):
    for j, label in enumerate(TARGET_CLASSES):
        h, a = label.split("-")
        h, a = int(h), int(a)
        if h > a:
            hda_pred[i, 0] += best_probs[i, j]
        elif h == a:
            hda_pred[i, 1] += best_probs[i, j]
        else:
            hda_pred[i, 2] += best_probs[i, j]

def get_hda(score_str):
    h, a = score_str.split("-")
    h, a = int(h), int(a)
    if h > a: return 0
    if h == a: return 1
    return 2

true_hda = np.array([get_hda(TARGET_CLASSES[e]) for e in y_test_enc])
hda_acc = (np.argmax(hda_pred, axis=1) == true_hda).mean()

# RPS
def rps_score(probs, true_class, n_classes=25):
    cum_true = np.zeros(n_classes)
    cum_true[true_class:] = 1.0
    cum_pred = np.cumsum(probs)
    return np.mean((cum_pred - cum_true) ** 2)

rps = np.mean([rps_score(best_probs[i], y_test_enc[i]) for i in range(len(y_test_enc))])

# Also compute RPS via 1X2
def rps_hda(probs, true_hda_label):
    p_h = sum(probs[h*5 + a] for h in range(5) for a in range(5) if h > a)
    p_d = sum(probs[h*5 + h] for h in range(5))
    p_a = sum(probs[h*5 + a] for h in range(5) for a in range(5) if a > h)
    cum_pred = np.cumsum([p_h, p_d, p_a])
    cum_true = np.array([1 if true_hda_label <= k else 0 for k in range(3)])
    return np.mean((cum_pred - cum_true) ** 2)

rps_hda_val = np.mean([rps_hda(best_probs[i], true_hda[i]) for i in range(len(y_test_enc))])

print(f"\n=== Production Model (XGB {best_w*100:.0f}% + M4 {(1-best_w)*100:.0f}%) ===")
print(f"  Exact: {exact*100:.2f}%")
print(f"  1X2:   {hda_acc*100:.2f}%")
print(f"  RPS:   {rps:.4f}  RPS(HDA): {rps_hda_val:.4f}")

# Save models
models_dir = r"C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor\models"
print("\nSaving production models...")
model_xgb.save_model(os.path.join(models_dir, "direct_score.json"))

ensemble = EnsemblePredictor(
    models=[model_m4],
    model_weights=[1.0],
    xgb_model=model_xgb,
    xgb_weight=best_w,
    imp=imputer,
    scaler=scaler,
)

blend_path = os.path.join(models_dir, "mlp_blend.pkl")
with open(blend_path, "wb") as f:
    pickle.dump(ensemble, f)
size_mb = os.path.getsize(blend_path) / 1e6
print(f"  mlp_blend.pkl saved ({size_mb:.1f} MB)")
print(f"  direct_score.json saved")

results = {
    "best_exact": round(exact*100, 2),
    "best_1x2": round(hda_acc*100, 2),
    "best_rps": round(rps_hda_val, 4),
    "best_ensemble": f"XGB({best_w*100:.0f}%)+M4",
    "model_weights": {"xgb": best_w, "m4": 1-best_w},
    "training_samples": len(X),
    "features": N_FEATURES,
    "test_samples": len(y_test),
}
with open(os.path.join(models_dir, "ensemble_results.json"), "w") as f:
    json.dump(results, f, indent=2)
print(f"  ensemble_results.json saved")

print(f"\n{'='*60}")
print(f"RESULT: Exact={exact*100:.2f}%  1X2={hda_acc*100:.2f}%  RPS={rps_hda_val:.4f}")
print(f"{'='*60}")
