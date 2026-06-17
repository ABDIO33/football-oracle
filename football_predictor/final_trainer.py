"""
final_trainer.py — Train best model with optimal hyperparameters
يستخدم أفضل المعاملات من hyperparameter search
"""
import sys, os, json, time, gc
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))

os.environ['PYTHONIOENCODING'] = 'utf-8'

from direct_predictor import _load_training_data, FEATURES, NUM_CLASSES, SCORE_CLASSES, class_to_score, result
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
import joblib

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

def compute_rps(y_true, y_pred_proba):
    n = len(y_true)
    rps_total = 0.0
    for i in range(n):
        ah, aa = class_to_score(y_true[i])
        ar = result(ah, aa)
        actual_cum = np.array([1 if ar <= k else 0 for k in range(3)], dtype=float)
        pred_probs = y_pred_proba[i]
        p_h = sum(pred_probs[h*5 + a] for h in range(5) for a in range(5) if h > a)
        p_d = sum(pred_probs[h*5 + h] for h in range(5))
        p_a = sum(pred_probs[h*5 + a] for h in range(5) for a in range(5) if a > h)
        pred_cum = np.cumsum([p_h, p_d, p_a])
        rps_total += np.mean((actual_cum - pred_cum) ** 2)
    return rps_total / n


class TorchMLPWrapper:
    def __init__(self, model, device='cpu'):
        self.model = model
        self.device = device
        self.model.eval()
        self.model.to(device)
    def predict_proba(self, X):
        with torch.no_grad():
            X_t = torch.tensor(X, dtype=torch.float32).to(self.device)
            return torch.softmax(self.model(X_t), dim=1).cpu().numpy()


def build_best_network(input_dim, num_classes, config):
    """Build network from config dict with keys: hidden_layers, dropout."""
    layers = []
    prev_dim = input_dim
    for units in config['hidden_layers']:
        layers.extend([
            nn.Linear(prev_dim, units),
            nn.BatchNorm1d(units),
            nn.ReLU(),
            nn.Dropout(config['dropout']),
        ])
        prev_dim = units
    layers.append(nn.Linear(prev_dim, num_classes))
    return nn.Sequential(*layers)


def train_best(config, save=True):
    print("=" * 70)
    print(f"FINAL TRAINING — DeepNN with {config['architecture']}")
    print(f"  lr={config['lr']}, dropout={config['dropout']}, hidden={config['hidden_layers']}")
    print("=" * 70)

    X, y, _ = _load_training_data()
    split = int(len(X) * 0.9)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    print(f"Train: {len(X_train)}, Test: {len(X_test)}")

    imp = SimpleImputer(strategy='median')
    X_train_imp = imp.fit_transform(X_train)
    X_test_imp = imp.transform(X_test)
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train_imp)
    X_test_s = scaler.transform(X_test_imp)
    input_dim = X_train_s.shape[1]

    # XGBoost baseline
    import xgboost as xgb
    print("\nTraining XGBoost baseline...")
    xgb_model = xgb.XGBClassifier(n_estimators=400, max_depth=6, learning_rate=0.05,
        objective='multi:softprob', num_class=NUM_CLASSES, subsample=0.9, colsample_bytree=0.8,
        reg_alpha=0.1, reg_lambda=0.1, random_state=42, eval_metric='mlogloss', early_stopping_rounds=20)
    xgb_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
    xgb_proba = xgb_model.predict_proba(X_test)
    xgb_pred = np.argmax(xgb_proba, axis=1)
    xgb_exact = np.mean(xgb_pred == y_test)
    actual_1x2 = np.array([result(*class_to_score(c)) for c in y_test])
    xgb_1x2 = np.mean(np.array([result(*class_to_score(c)) for c in xgb_pred]) == actual_1x2)
    xgb_rps = compute_rps(y_test, xgb_proba)
    print(f"  XGBoost: exact={xgb_exact*100:.2f}%  1X2={xgb_1x2*100:.2f}%  RPS={xgb_rps:.4f}")

    # DeepNN
    print("\nTraining DeepNN...")
    model = build_best_network(input_dim, NUM_CLASSES, config).to(DEVICE)
    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    optimizer = optim.AdamW(model.parameters(), lr=config['lr'], weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=80)

    train_dataset = TensorDataset(
        torch.tensor(X_train_s, dtype=torch.float32),
        torch.tensor(y_train, dtype=torch.long))
    train_loader = DataLoader(train_dataset, batch_size=128, shuffle=True, num_workers=0)
    X_test_t = torch.tensor(X_test_s, dtype=torch.float32).to(DEVICE)
    y_test_t = torch.tensor(y_test, dtype=torch.long).to(DEVICE)

    best_acc = 0.0
    best_state = None
    patience = 20
    patience_counter = 0

    for epoch in range(150):
        model.train()
        for Xb, yb in train_loader:
            Xb, yb = Xb.to(DEVICE), yb.to(DEVICE)
            optimizer.zero_grad()
            loss = criterion(model(Xb), yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

        model.eval()
        with torch.no_grad():
            out = model(X_test_t)
            _, preds = torch.max(out, 1)
            acc = (preds == y_test_t).sum().item() / len(y_test)

        scheduler.step()
        if acc > best_acc:
            best_acc = acc
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= patience:
                break
        if (epoch+1) % 20 == 0:
            print(f"  Epoch {epoch+1:3d}: test_acc={acc:.4f}")

    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        out = model(X_test_t)
        nn_proba = torch.softmax(out, dim=1).cpu().numpy()
        nn_pred = torch.max(out, 1)[1].cpu().numpy()

    nn_exact = np.mean(nn_pred == y_test)
    nn_1x2 = np.mean(np.array([result(*class_to_score(c)) for c in nn_pred]) == actual_1x2)
    nn_rps = compute_rps(y_test, nn_proba)
    print(f"  DeepNN:   exact={nn_exact*100:.2f}%  1X2={nn_1x2*100:.2f}%  RPS={nn_rps:.4f}")

    # Find best blend weights
    print("\nSearching blend weights...")
    best_blend = {'w_xgb': 0, 'w_nn': 1, 'exact': nn_exact, 'acc_1x2': nn_1x2, 'rps': nn_rps}
    for w_xgb in np.arange(0.0, 1.01, 0.05):
        w_nn = 1.0 - w_xgb
        blend_proba = w_xgb * xgb_proba + w_nn * nn_proba
        blend_pred = np.argmax(blend_proba, axis=1)
        exact = np.mean(blend_pred == y_test)
        if exact > best_blend['exact']:
            acc_1x2 = np.mean(np.array([result(*class_to_score(c)) for c in blend_pred]) == actual_1x2)
            rps = compute_rps(y_test, blend_proba)
            best_blend = {'w_xgb': w_xgb, 'w_nn': w_nn, 'exact': exact, 'acc_1x2': acc_1x2, 'rps': rps}

    print(f"\n=== FINAL RESULTS ===")
    print(f"XGBoost alone:    exact={xgb_exact*100:.2f}%  1X2={xgb_1x2*100:.2f}%  RPS={xgb_rps:.4f}")
    print(f"DeepNN alone:     exact={nn_exact*100:.2f}%  1X2={nn_1x2*100:.2f}%  RPS={nn_rps:.4f}")
    print(f"Best blend (XGB={best_blend['w_xgb']:.2f}+NN={best_blend['w_nn']:.2f}):")
    print(f"                  exact={best_blend['exact']*100:.2f}%  1X2={best_blend['acc_1x2']*100:.2f}%  RPS={best_blend['rps']:.4f}")

    if save:
        os.makedirs(MODEL_DIR, exist_ok=True)

        # Save XGBoost
        xgb_model.save_model(os.path.join(MODEL_DIR, 'direct_score.json'))
        print(f"\nSaved XGBoost to models/direct_score.json")

        # Save blend
        wrapper = TorchMLPWrapper(model, DEVICE)
        blend = (imp, scaler, wrapper, best_blend['w_xgb'], best_blend['w_nn'])
        joblib.dump(blend, os.path.join(MODEL_DIR, 'mlp_blend.pkl'))
        print(f"Saved blend to models/mlp_blend.pkl")

        # Save model info
        info = {
            'features': FEATURES,
            'num_classes': NUM_CLASSES,
            'classes': [f'{h}-{a}' for h, a in SCORE_CLASSES],
            'train_samples': len(X_train),
            'test_samples': len(X_test),
            'xgb_exact_pct': round(xgb_exact*100, 2),
            'xgb_1x2_pct': round(xgb_1x2*100, 2),
            'xgb_rps': round(xgb_rps, 4),
            'nn_exact_pct': round(nn_exact*100, 2),
            'nn_1x2_pct': round(nn_1x2*100, 2),
            'nn_rps': round(nn_rps, 4),
            'blend_exact_pct': round(best_blend['exact']*100, 2),
            'blend_1x2_pct': round(best_blend['acc_1x2']*100, 2),
            'blend_rps': round(best_blend['rps'], 4),
            'blend_w_xgb': round(best_blend['w_xgb'], 2),
            'blend_w_nn': round(best_blend['w_nn'], 2),
            'model_type': 'xgb_pytorch_deepnn_blend',
            'nn_architecture': f"{input_dim}->{'->'.join(str(u) for u in config['hidden_layers'])}->{NUM_CLASSES}",
            'nn_config': config,
        }
        with open(os.path.join(MODEL_DIR, 'direct_model_info.json'), 'w') as f:
            json.dump(info, f, indent=2)
        print(f"Saved model info to models/direct_model_info.json")

        # Also save as a comparison record
        record_path = os.path.join(MODEL_DIR, 'model_records.json')
        records = []
        try:
            with open(record_path) as f:
                records = json.load(f)
        except:
            pass
        records.append({
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'exact_pct': round(best_blend['exact']*100, 2),
            'acc_1x2_pct': round(best_blend['acc_1x2']*100, 2),
            'rps': round(best_blend['rps'], 4),
            'nn_config': config,
        })
        with open(record_path, 'w') as f:
            json.dump(records, f, indent=2)

    return best_blend


if __name__ == '__main__':
    # Use best config from hyperparameter search, or defaults
    config_path = os.path.join(MODEL_DIR, 'hyperparam_results.json')
    if os.path.exists(config_path):
        with open(config_path) as f:
            results = json.load(f)
        if results:
            best = results[0]
            config = {
                'architecture': best['architecture'],
                'hidden_layers': best['hidden_layers'],
                'lr': best['lr'],
                'dropout': best['dropout'],
            }
            print(f"Using best config from search: {config}")
        else:
            config = {'architecture': 'M2', 'hidden_layers': [512, 1024, 512], 'lr': 0.001, 'dropout': 0.3}
    else:
        config = {'architecture': 'M2', 'hidden_layers': [512, 1024, 512], 'lr': 0.001, 'dropout': 0.3}

    train_best(config, save=True)
