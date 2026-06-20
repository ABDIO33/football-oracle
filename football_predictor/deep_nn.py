"""
deep_nn.py — PyTorch Deep Neural Network for Direct Score Prediction
يحل محل sklearn MLPClassifier بشبكة عصبية عميقة (Dropout, BatchNorm, AdamW)
"""

import os, sys, json, warnings
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
import joblib

# Suppress non-critical warnings
warnings.filterwarnings('ignore')

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
sys.path.insert(0, os.path.dirname(__file__))

from direct_predictor import _load_training_data, FEATURES, NUM_CLASSES, SCORE_CLASSES, class_to_score, result

class DeepScoreNet(nn.Module):
    """Deep neural network for exact score prediction (25 classes)."""
    def __init__(self, input_dim, num_classes=NUM_CLASSES):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(512, 1024),
            nn.BatchNorm1d(1024),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(1024, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(512, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, num_classes),
        )
        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.kaiming_normal_(m.weight, mode='fan_in', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward(self, x):
        return self.net(x)


class TorchMLPWrapper:
    """Picklable wrapper around PyTorch model with sklearn-compatible API."""
    def __init__(self, model, device='cpu'):
        self.model = model
        self.device = device
        self.model.eval()
        self.model.to(device)

    def predict_proba(self, X):
        self.model.eval()
        with torch.no_grad():
            X_t = torch.tensor(X, dtype=torch.float32).to(self.device)
            outputs = self.model(X_t)
            probs = torch.softmax(outputs, dim=1).cpu().numpy()
        return probs


def compute_rps(y_true, y_pred_proba):
    """Ranked Probability Score."""
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


def train(save=True, find_lr=False):
    print("=" * 60)
    print("PyTorch Deep NN — Direct Score Predictor")
    print("=" * 60)

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Device: {device}")

    # ── Load data ──
    X, y, match_ids = _load_training_data()
    if len(X) == 0:
        print("[DeepNN] No training data")
        return

    print(f"\nLoaded {len(X)} samples, {X.shape[1]} features, {NUM_CLASSES} classes")

    # ── Time-split (last 10% as test) ──
    split = int(len(X) * 0.9)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    print(f"Train: {len(X_train)}, Test: {len(X_test)}, Split at index {split}")

    # ── Impute + Scale ──
    imp = SimpleImputer(strategy='median')
    X_train_imp = imp.fit_transform(X_train)
    X_test_imp = imp.transform(X_test)

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train_imp)
    X_test_s = scaler.transform(X_test_imp)

    input_dim = X_train_s.shape[1]
    print(f"Input dimension after scaling: {input_dim}")

    # ── Build PyTorch model ──
    model = DeepScoreNet(input_dim, NUM_CLASSES).to(device)
    total_params = sum(p.numel() for p in model.parameters())
    print(f"Model parameters: {total_params:,}")

    # ── Training setup ──
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=100)

    # Find optimal LR
    if find_lr:
        from torch.lr_scheduler import LambdaLR
        lr_finder_model = DeepScoreNet(input_dim, NUM_CLASSES).to(device)
        lr_optim = optim.AdamW(lr_finder_model.parameters(), lr=1e-7)
        lrs, losses = [], []
        X_ft = torch.tensor(X_train_s, dtype=torch.float32).to(device)
        y_ft = torch.tensor(y_train, dtype=torch.long).to(device)
        for step in range(300):
            lr_optim.zero_grad()
            out = lr_finder_model(X_ft)
            loss = criterion(out, y_ft)
            loss.backward()
            lr_optim.step()
            lr = 1e-7 * (100 / 1e-7) ** (step / 299)
            for pg in lr_optim.param_groups:
                pg['lr'] = lr
            lrs.append(lr)
            losses.append(loss.item())
            if step > 10 and losses[-1] > losses[-10] * 2:
                break
        best_lr = lrs[np.argmin(losses)]
        print(f"LR finder: best LR = {best_lr:.2e}")
        del lr_finder_model

    # ── Training loop ──
    batch_size = 128
    train_dataset = TensorDataset(
        torch.tensor(X_train_s, dtype=torch.float32),
        torch.tensor(y_train, dtype=torch.long)
    )
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)

    X_test_t = torch.tensor(X_test_s, dtype=torch.float32).to(device)
    y_test_t = torch.tensor(y_test, dtype=torch.long).to(device)

    best_test_loss = float('inf')
    best_state = None
    patience = 30
    patience_counter = 0
    n_epochs = 300

    print(f"\nTraining for up to {n_epochs} epochs (patience={patience})...")
    print(f"{'Epoch':>6} | {'Train Loss':>10} | {'Test Loss':>9} | {'Train Acc':>9} | {'Test Acc':>8} | {'Test 1X2':>8} | {'Test RPS':>8} | {'LR':>10}")
    print("-" * 80)

    for epoch in range(n_epochs):
        model.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0
        for Xb, yb in train_loader:
            Xb, yb = Xb.to(device), yb.to(device)
            optimizer.zero_grad()
            outputs = model(Xb)
            loss = criterion(outputs, yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            train_loss += loss.item() * len(Xb)
            _, preds = torch.max(outputs, 1)
            train_correct += (preds == yb).sum().item()
            train_total += len(yb)
        train_loss /= train_total
        train_acc = train_correct / train_total

        # Evaluate
        model.eval()
        with torch.no_grad():
            test_outputs = model(X_test_t)
            test_loss = criterion(test_outputs, y_test_t).item()
            _, test_preds = torch.max(test_outputs, 1)
            test_exact = (test_preds == y_test_t).sum().item() / len(y_test)
            test_probs = torch.softmax(test_outputs, dim=1).cpu().numpy()

            # 1X2 accuracy
            actual_1x2 = np.array([result(*class_to_score(c)) for c in y_test])
            pred_1x2 = np.array([result(*class_to_score(c)) for c in test_preds.cpu().numpy()])
            test_1x2 = np.mean(actual_1x2 == pred_1x2)

            # RPS
            test_rps = compute_rps(y_test, test_probs)

        current_lr = optimizer.param_groups[0]['lr']
        scheduler.step()

        if (epoch + 1) % 10 == 0 or epoch == 0:
            print(f"{epoch+1:>6} | {train_loss:>10.4f} | {test_loss:>9.4f} | {train_acc:>9.3f} | {test_exact:>8.3f} | {test_1x2:>8.3f} | {test_rps:>8.4f} | {current_lr:>.2e}")

        # Early stopping
        if test_loss < best_test_loss:
            best_test_loss = test_loss
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"\nEarly stopping at epoch {epoch+1}")
                break

    # Restore best model
    model.load_state_dict(best_state)
    model.eval()

    # ── Final evaluation ──
    with torch.no_grad():
        test_outputs = model(X_test_t)
        test_probs = torch.softmax(test_outputs, dim=1).cpu().numpy()
        _, test_preds = torch.max(test_outputs, 1)
        test_preds_np = test_preds.cpu().numpy()

    n_test = len(y_test)
    exact = np.mean(test_preds_np == y_test)
    exact_count = np.sum(test_preds_np == y_test)
    actual_1x2 = np.array([result(*class_to_score(c)) for c in y_test])
    pred_1x2 = np.array([result(*class_to_score(c)) for c in test_preds_np])
    acc_1x2 = np.mean(actual_1x2 == pred_1x2)
    rps = compute_rps(y_test, test_probs)

    print("\n" + "=" * 60)
    print("PyTorch Deep NN — Results")
    print("=" * 60)
    print(f"  Exact score: {exact*100:.2f}% ({exact_count}/{n_test})")
    print(f"  1X2: {acc_1x2*100:.2f}%")
    print(f"  RPS: {rps:.3f}")
    print(f"  Parameters: {total_params:,}")
    print(f"  Architecture: {input_dim}→512→1024→512→256→128→{NUM_CLASSES}")

    # ── Create blend wrapper ──
    wrapper = TorchMLPWrapper(model, device)

    if save:
        model_dir = os.path.join(os.path.dirname(__file__), 'models')
        os.makedirs(model_dir, exist_ok=True)

        # Try loading existing blend to reuse weights
        w_xgb = 0.7
        w_mlp = 0.3
        blend_path = os.path.join(model_dir, 'mlp_blend.pkl')
        try:
            old_blend = joblib.load(blend_path)
            if len(old_blend) == 5:
                w_xgb = float(old_blend[3])
                w_mlp = float(old_blend[4])
        except:
            pass

        blend = (imp, scaler, wrapper, w_xgb, w_mlp)
        joblib.dump(blend, blend_path)
        print(f"\nSaved PyTorch blend to {blend_path}")

        # Update model info
        info_path = os.path.join(model_dir, 'direct_model_info.json')
        old_info = {}
        try:
            with open(info_path) as f:
                old_info = json.load(f)
        except:
            pass
        old_info.update({
            'deep_nn_exact_pct': round(exact * 100, 2),
            'deep_nn_1x2_pct': round(acc_1x2 * 100, 2),
            'deep_nn_rps': round(rps, 3),
            'deep_nn_params': total_params,
            'deep_nn_architecture': f'{input_dim}→512→1024→512→256→128→{NUM_CLASSES}',
            'model_type': 'pytorch_deep_nn + xgboost_blend',
        })
        with open(info_path, 'w') as f:
            json.dump(old_info, f, indent=2)
        print(f"Updated {info_path}")

    # ── Compare with existing sklearn MLP ──
    print("\n" + "=" * 60)
    print("Comparison with old sklearn MLP:")
    try:
        old_blend = joblib.load(os.path.join(os.path.dirname(__file__), 'models', 'mlp_blend.pkl.bak'))
    except:
        old_blend = None
    if old_blend:
        old_imp, old_scaler, old_mlp, old_wxgb, old_wmlp = old_blend
        X_test_old_imp = old_imp.transform(X_test)
        X_test_old_s = old_scaler.transform(X_test_old_imp)
        old_mlp_proba = old_mlp.predict_proba(X_test_old_s)
        old_exact = np.mean(np.argmax(old_mlp_proba, axis=1) == y_test)
        old_1x2 = np.mean([result(*class_to_score(c)) for c in np.argmax(old_mlp_proba, axis=1)] == actual_1x2)
        old_rps = compute_rps(y_test, old_mlp_proba)
        print(f"  Sklearn MLP:  Exact={old_exact*100:.2f}%  1X2={old_1x2*100:.2f}%  RPS={old_rps:.3f}")
        print(f"  PyTorch Deep: Exact={exact*100:.2f}%  1X2={acc_1x2*100:.2f}%  RPS={rps:.3f}")
        print(f"  Δ:            Exact={exact*100 - old_exact*100:+.2f}pp  1X2={acc_1x2*100 - old_1x2*100:+.2f}pp  RPS={rps - old_rps:+.4f}")
    else:
        print("  (old sklearn MLP not available for comparison)")

    return exact, acc_1x2, rps


if __name__ == '__main__':
    train(save=True, find_lr=False)
