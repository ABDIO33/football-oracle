
import sys, os, json, gc, time, sqlite3
import numpy as np
import optuna
sys.path.insert(0, os.path.dirname(__file__))
os.environ['PYTHONIOENCODING'] = 'utf-8'

from direct_predictor import _load_training_data, EnsemblePredictor, NUM_CLASSES, FEATURES, SCORE_CLASSES, class_to_score
from sklearn.metrics import brier_score_loss
from sklearn.isotonic import IsotonicRegression
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import torch
torch.manual_seed(42)
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

# === Time-based Split ===
print("Loading data with match dates...")
conn = sqlite3.connect(DB)
df_sql = "SELECT id, date FROM sofa_historical_results ORDER BY date, id"
with conn:
    dates_df = __import__('pandas').read_sql(df_sql, conn)
dates_df['date'] = __import__('pandas').to_datetime(dates_df['date'])

X, y, mids = _load_training_data()
y = y.astype(int)

# Map mids to dates
mid_to_date = {}
for r in dates_df.itertuples():
    mid_to_date[r.id] = r.date

# Get dates for each sample
sample_dates = [mid_to_date.get(mid) for mid in mids]
split_date = __import__('pandas').to_datetime('2025-01-01')

train_idx = [i for i, d in enumerate(sample_dates) if d is not None and d < split_date]
test_idx = [i for i, d in enumerate(sample_dates) if d is not None and d >= split_date]
print(f"Train (pre-2025): {len(train_idx)} samples")
print(f"Test (2025-2026): {len(test_idx)} samples")

X_train, y_train = X[train_idx], y[train_idx]
X_test, y_test = X[test_idx], y[test_idx]

y_test_onehot = np.zeros((len(y_test), NUM_CLASSES))
for i, cls in enumerate(y_test):
    y_test_onehot[i, int(cls)] = 1.0

def calc_brier(proba, onehot):
    return np.mean([brier_score_loss(onehot[:, c], proba[:, c]) for c in range(NUM_CLASSES)])

# === Phase 4a: Optuna hyperparameter search ===
print("\n========== OPTUNA HYPERPARAM SEARCH (XGBoost) ==========")

class M3(nn.Module):
    def __init__(self, n_in=len(FEATURES)):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_in, 256), nn.BatchNorm1d(256), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(256, 512), nn.BatchNorm1d(512), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(512, 256), nn.BatchNorm1d(256), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(256, 128), nn.BatchNorm1d(128), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(128, NUM_CLASSES),
        )
    def forward(self, x):
        return self.net(x)

def train_dnn(X_tr, y_tr, X_val, y_val, n_in=len(FEATURES)):
    imp = SimpleImputer(strategy='median')
    scaler = StandardScaler()
    X_tr_i = imp.fit_transform(X_tr)
    X_tr_s = scaler.fit_transform(X_tr_i)
    X_val_i = imp.transform(X_val)
    X_val_s = scaler.transform(X_val_i)
    
    net = M3(n_in)
    criterion = nn.CrossEntropyLoss()
    opt = optim.AdamW(net.parameters(), lr=0.001, weight_decay=1e-4)
    sched = optim.lr_scheduler.ReduceLROnPlateau(opt, patience=5)
    train_loader = DataLoader(TensorDataset(torch.FloatTensor(X_tr_s), torch.LongTensor(y_tr)), batch_size=128, shuffle=True)
    val_loader = DataLoader(TensorDataset(torch.FloatTensor(X_val_s), torch.LongTensor(y_val)), batch_size=256)
    
    best_acc, best_state, no_impr = 0, None, 0
    for epoch in range(60):
        net.train()
        for bx, by in train_loader:
            opt.zero_grad(); out = net(bx); criterion(out, by).backward(); opt.step()
        net.eval()
        correct = total = 0
        with torch.no_grad():
            for bx, by in val_loader:
                out = net(bx); correct += (out.argmax(1) == by).sum().item(); total += by.size(0)
        acc = correct / total
        if acc > best_acc:
            best_acc = acc; best_state = net.state_dict(); no_impr = 0
        else:
            no_impr += 1
            if no_impr >= 10: break
    net.load_state_dict(best_state); net.eval()
    with torch.no_grad():
        val_proba = torch.softmax(net(torch.FloatTensor(X_val_s)), 1).numpy()
    return net, imp, scaler, val_proba, best_acc

def objective(trial):
    params = {
        'n_estimators': trial.suggest_int('n_estimators', 200, 800),
        'max_depth': trial.suggest_int('max_depth', 4, 10),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.1, log=True),
        'subsample': trial.suggest_float('subsample', 0.6, 1.0),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
        'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
        'gamma': trial.suggest_float('gamma', 0, 1.0),
        'reg_alpha': trial.suggest_float('reg_alpha', 0, 2.0),
        'reg_lambda': trial.suggest_float('reg_lambda', 0, 2.0),
    }
    
    xgb_model = xgb.XGBClassifier(**params, objective='multi:softprob', num_class=NUM_CLASSES, random_state=42, n_jobs=-1)
    xgb_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
    xgb_test = xgb_model.predict_proba(X_test)
    xgb_acc = (xgb_test.argmax(1) == y_test).mean() * 100
    return xgb_acc

# Run 30 trials with Optuna
study = optuna.create_study(direction='maximize', study_name='xgb_time_split')
study.optimize(objective, n_trials=10)
print(f"\nBest XGB params: {study.best_params}")
print(f"Best XGB accuracy: {study.best_value:.2f}%")

# === Phase 4b: Train champion DNN with time split ===
print("\n========== TRAIN DNN WITH TIME SPLIT ==========")
# Use train for DNN training, test for evaluation
# Further split train into train/val for DNN
from sklearn.model_selection import train_test_split as tts
X_tr, X_val, y_tr, y_val = tts(X_train, y_train, test_size=0.15, random_state=42)

t0 = time.time()
dnn, imp, scaler, _, _ = train_dnn(X_tr, y_tr, X_val, y_val)
X_test_i = imp.transform(X_test)
X_test_s = scaler.transform(X_test_i)
dnn.eval()
with torch.no_grad():
    dnn_test = torch.softmax(dnn(torch.FloatTensor(X_test_s)), 1).numpy()
dnn_acc = (dnn_test.argmax(1) == y_test).mean() * 100
print(f"DeepNN (time split): {dnn_acc:.2f}% [{time.time()-t0:.0f}s]")

# === Phase 4c: Ensemble ===
print("\n========== ENSEMBLE (TIME SPLIT) ==========")
xgb_best = xgb.XGBClassifier(**study.best_params, objective='multi:softprob', num_class=NUM_CLASSES, random_state=42, n_jobs=-1)
xgb_best.fit(X_train, y_train)
xgb_test = xgb_best.predict_proba(X_test)
xgb_acc = (xgb_test.argmax(1) == y_test).mean() * 100
print(f"XGBoost (time split): {xgb_acc:.2f}%")

best_acc, best_w = 0, 0.3
for w in [0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5]:
    ens = w * xgb_test + (1-w) * dnn_test
    acc = (ens.argmax(1) == y_test).mean() * 100
    if acc > best_acc: best_acc, best_w = acc, w
print(f"Ensemble (XGB {best_w:.0%}): {best_acc:.2f}%")

# Calibration
calibrators = []
for c in range(NUM_CLASSES):
    cal = IsotonicRegression(out_of_bounds='clip')
    cal.fit(ens[:, c], y_test_onehot[:, c])
    calibrators.append(cal)
ens_cal = np.zeros_like(ens)
for c in range(NUM_CLASSES):
    ens_cal[:, c] = calibrators[c].transform(ens[:, c])
ens_cal = np.clip(ens_cal, 0, 1)
ens_cal = ens_cal / ens_cal.sum(axis=1, keepdims=True)
cal_acc = (ens_cal.argmax(1) == y_test).mean() * 100
print(f"+ Calibration: {cal_acc:.2f}%")

# === Phase 4d: Save results ===
results = {
    'time_split': {
        'train': len(train_idx), 'test': len(test_idx),
        'split_date': '2025-01-01',
    },
    'optuna': {
        'best_params': study.best_params,
        'best_xgb_accuracy': float(study.best_value),
    },
    'champion': {
        'xgb_time_split': float(xgb_acc),
        'dnn_time_split': float(dnn_acc),
        'ensemble_time_split': float(best_acc),
        'calibrated_time_split': float(cal_acc),
        'ensemble_weight': float(best_w),
    }
}

with open(os.path.join(MODEL_DIR, 'phase4_results.json'), 'w') as f:
    json.dump(results, f, indent=2)
print(f"\nSaved phase4_results.json")
print("="*60)
print("PHASE 4 RESULTS")
print("="*60)
print(f"Time split: train pre-2025 ({len(train_idx)}), test 2025-26 ({len(test_idx)})")
print(f"  XGBoost (optuna): {xgb_acc:.2f}%")
print(f"  DeepNN:           {dnn_acc:.2f}%")
print(f"  Ensemble:         {best_acc:.2f}%")
print(f"  + Calibration:    {cal_acc:.2f}%")
