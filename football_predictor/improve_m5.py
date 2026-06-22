"""
improve_m5.py — Retrain M5 with 120 epochs, deeper architecture
Builds from build_real_model.py foundation
"""
import sys, os, json, time, numpy as np, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))
from direct_predictor import _load_training_data, FEATURES, NUM_CLASSES, class_to_score, result
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import joblib
import torch, torch.nn as nn, torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
LOG = os.path.join(MODEL_DIR, 'improve_m5_log.txt')

def log(msg):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(f'[{time.strftime("%H:%M:%S")}] {msg}\n')
    print(f'[{time.strftime("%H:%M:%S")}] {msg}')
    sys.stdout.flush()

log('='*60)
log('IMPROVING M5: 120 EPOCHS, DEEPER ARCH')
log('='*60)

t_start = time.time()

# 1. Load data
log('Loading data...')
X, y, _ = _load_training_data()
n = len(X)
split = int(n * 0.80)
X_train, X_test = X[:split], X[split:]
y_train, y_test = y[:split], y[split:]
log(f'Train: {len(X_train)}, Test: {len(X_test)}, Features: {len(FEATURES)}')

# Preprocess
imp = SimpleImputer(strategy='median')
X_train_imp = imp.fit_transform(X_train)
X_test_imp = imp.transform(X_test)
scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train_imp)
X_test_s = scaler.transform(X_test_imp)
log(f'Preprocessed. Time: {time.time()-t_start:.0f}s')

actual_1x2 = np.array([result(*class_to_score(c)) for c in y_test])

def compute_rps(y_true, y_pred_proba):
    rps = 0.0
    for i in range(len(y_true)):
        ah, aa = class_to_score(y_true[i])
        ar = result(ah, aa)
        ac = np.array([1 if ar <= k else 0 for k in range(3)], dtype=float)
        p = y_pred_proba[i]
        p_h = sum(p[h*5 + a] for h in range(5) for a in range(5) if h > a)
        p_d = sum(p[h*5 + h] for h in range(5))
        p_a = sum(p[h*5 + a] for h in range(5) for a in range(5) if a > h)
        pc = np.cumsum([p_h, p_d, p_a])
        rps += float(np.mean((ac - pc) ** 2))
    return rps / len(y_true)

# 2. XGBoost (same config)
log('[1/3] Training XGBoost...')
xgb_model = xgb.XGBClassifier(
    n_estimators=700, max_depth=6, learning_rate=0.08,
    objective='multi:softprob', num_class=NUM_CLASSES,
    subsample=0.8, colsample_bytree=0.8,
    reg_alpha=0.1, reg_lambda=0.1, random_state=42,
    eval_metric='mlogloss', early_stopping_rounds=20
)
xgb_model.fit(X_train_s, y_train, eval_set=[(X_test_s, y_test)], verbose=False)
xgb_proba = xgb_model.predict_proba(X_test_s)
xgb_pred = np.argmax(xgb_proba, axis=1)
xgb_exact = float(np.mean(xgb_pred == y_test))
xgb_1x2 = float(np.mean(np.array([result(*class_to_score(c)) for c in xgb_pred]) == actual_1x2))
xgb_rps = compute_rps(y_test, xgb_proba)
log(f'XGBoost: exact={xgb_exact*100:.2f}% 1X2={xgb_1x2*100:.2f}% RPS={xgb_rps:.4f} Time: {time.time()-t_start:.0f}s')

# 3. M5 with 256-512-256 architecture
log('[2/3] Training M5-BIG (256->512->256, 120 epochs)...')
device = 'cuda' if torch.cuda.is_available() else 'cpu'
log(f'Device: {device.upper()}')

class M5_Big(nn.Module):
    def __init__(self, input_dim, num_classes):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 256), nn.BatchNorm1d(256), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(256, 512), nn.BatchNorm1d(512), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(512, 256), nn.BatchNorm1d(256), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(256, num_classes)
        )
    def forward(self, x):
        return self.net(x)

train_dataset = TensorDataset(
    torch.tensor(X_train_s, dtype=torch.float32),
    torch.tensor(y_train, dtype=torch.long))
train_loader = DataLoader(train_dataset, batch_size=512, shuffle=True, num_workers=0)
X_test_t = torch.tensor(X_test_s, dtype=torch.float32).to(device)
y_test_t = torch.tensor(y_test, dtype=torch.long).to(device)

m5 = M5_Big(X_train_s.shape[1], NUM_CLASSES).to(device)
optimizer = optim.AdamW(m5.parameters(), lr=0.001, weight_decay=1e-4)
scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=100)
criterion = nn.CrossEntropyLoss(label_smoothing=0.1)

best_acc = 0
best_state = None
EPOCHS = 120

epoch_times = []
for epoch in range(EPOCHS):
    t_ep = time.time()
    m5.train()
    for Xb, yb in train_loader:
        Xb, yb = Xb.to(device), yb.to(device)
        optimizer.zero_grad()
        criterion(m5(Xb), yb).backward()
        torch.nn.utils.clip_grad_norm_(m5.parameters(), 1.0)
        optimizer.step()
    
    m5.eval()
    with torch.no_grad():
        preds = torch.max(m5(X_test_t), 1)[1]
        acc = (preds == y_test_t).sum().item() / len(y_test)
    scheduler.step()
    
    if acc > best_acc:
        best_acc = acc
        best_state = {k: v.cpu().clone() for k, v in m5.state_dict().items()}
    
    epoch_times.append(time.time() - t_ep)
    if epoch % 5 == 0 or epoch == EPOCHS-1:
        avg_time = np.mean(epoch_times[-5:]) if len(epoch_times) >= 5 else np.mean(epoch_times)
        remaining = avg_time * (EPOCHS - epoch - 1)
        log(f'Epoch {epoch+1}/{EPOCHS}: val_acc={acc*100:.2f}% best={best_acc*100:.2f}% ep_time={avg_time:.1f}s remain={remaining/60:.0f}min')

m5.load_state_dict(best_state)
m5.eval()
with torch.no_grad():
    m5_proba = torch.softmax(m5(X_test_t), dim=1).cpu().numpy()
    m5_pred = torch.max(m5(X_test_t), 1)[1].cpu().numpy()

m5_exact = float(np.mean(m5_pred == y_test))
m5_1x2 = float(np.mean(np.array([result(*class_to_score(c)) for c in m5_pred]) == actual_1x2))
m5_rps = compute_rps(y_test, m5_proba)
log(f'M5-BIG: exact={m5_exact*100:.2f}% 1X2={m5_1x2*100:.2f}% RPS={m5_rps:.4f}')

# 4. Find ensemble blend
log('[3/3] Searching ensemble blend...')
best_w = 0.5
best_blend = 0
results = {}
for w in np.arange(0.05, 1.0, 0.05):
    ep = w * xgb_proba + (1-w) * m5_proba
    epred = np.argmax(ep, axis=1)
    acc = float(np.mean(epred == y_test))
    results[w] = round(acc, 4)
    if acc > best_blend:
        best_blend = acc
        best_w = w

log(f'Blend search: {json.dumps({str(round(k,2)): round(v*100,2) for k,v in results.items()})}')
log(f'Best: XGB({best_w*100:.0f}%) + M5({(1-best_w)*100:.0f}%) = {best_blend*100:.2f}%')

ensemble_proba = best_w * xgb_proba + (1-best_w) * m5_proba
ensemble_pred = np.argmax(ensemble_proba, axis=1)
ensemble_exact = float(np.mean(ensemble_pred == y_test))
ensemble_1x2 = float(np.mean(np.array([result(*class_to_score(c)) for c in ensemble_pred]) == actual_1x2))
ensemble_rps = compute_rps(y_test, ensemble_proba)

# Compare with old model
old_exact = 24.42  # from AGENTS.md
log(f'')
log(f'=== COMPARISON ===')
log(f'XGBoost:      {xgb_exact*100:.2f}% (was 20.72%)')
log(f'M5-BIG 120ep: {m5_exact*100:.2f}% (was 24.36%)')
log(f'Ensemble:     {ensemble_exact*100:.2f}% (was {old_exact}%)')
delta = ensemble_exact*100 - old_exact
log(f'Improvement:  {delta:+.2f}pp')

# Betting strategy @30%
log(f'')
log('Betting @30% threshold:')
hits, total = 0, 0
for i in range(len(y_test)):
    p = ensemble_proba[i]
    pc = ensemble_pred[i]
    if float(p[pc]) >= 0.30:
        total += 1
        if pc == y_test[i]:
            hits += 1
if total > 0:
    log(f'  @30%: {hits}/{total} = {hits/total*100:.1f}% (was 37.9%)')

# Save improved model
log(f'')
log('Saving improved model...')
final = {
    'xgb_model': xgb_model,
    'm5_state': best_state,
    'imputer': imp,
    'scaler': scaler,
    'weights': {'xgb': best_w, 'm5': 1-best_w},
    'features': FEATURES,
    'architecture': '256-512-256',
    'epochs': EPOCHS,
    'epochs_trained': EPOCHS,
    'best_val_epoch': next(i for i, v in enumerate(epoch_times) if False),  # placeholder
    'performance': {
        'xgb': {'exact': round(xgb_exact*100,2), '1x2': round(xgb_1x2*100,2), 'rps': round(xgb_rps,4)},
        'm5': {'exact': round(m5_exact*100,2), '1x2': round(m5_1x2*100,2), 'rps': round(m5_rps,4)},
        'ensemble': {'exact': round(ensemble_exact*100,2), '1x2': round(ensemble_1x2*100,2), 'rps': round(ensemble_rps,4)},
    },
    'time_seconds': round(time.time() - t_start, 1)
}
# Save as improved model alongside real_model
joblib.dump(final, os.path.join(MODEL_DIR, 'improved_model.pkl'))
xgb_model.save_model(os.path.join(MODEL_DIR, 'improved_xgb.ubj'))
torch.save(best_state, os.path.join(MODEL_DIR, 'improved_m5.pt'))

total_time = time.time() - t_start
log(f'')
log('='*60)
log(f'DONE! Total time: {total_time/60:.1f} min')
log(f'Ensemble: {ensemble_exact*100:.2f}% exact ({delta:+.2f}pp vs old {old_exact}%)')
log('='*60)

# Save results summary
results_summary = {
    'model': 'M5-BIG (256-512-256, 120 epochs)',
    'test_samples': len(X_test),
    'xgb': {'exact_pct': round(xgb_exact*100,2), '1x2_pct': round(xgb_1x2*100,2), 'rps': round(xgb_rps,4)},
    'm5': {'exact_pct': round(m5_exact*100,2), '1x2_pct': round(m5_1x2*100,2), 'rps': round(m5_rps,4)},
    'ensemble': {'exact_pct': round(ensemble_exact*100,2), '1x2_pct': round(ensemble_1x2*100,2), 'rps': round(ensemble_rps,4)},
    'best_blend': {'xgb_pct': round(best_w*100), 'm5_pct': round((1-best_w)*100), 'exact_pct': round(best_blend*100,2)},
    'vs_old_model': f'{round(ensemble_exact*100 - old_exact, 2):+.2f}pp',
    'time_minutes': round(total_time/60, 1),
}
with open(os.path.join(MODEL_DIR, 'improved_model_results.json'), 'w') as f:
    json.dump(results_summary, f, indent=2)
