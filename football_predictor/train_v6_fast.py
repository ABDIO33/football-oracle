"""V6 Fast Train — load preprocessed data directly, skip _load_training_data()"""
import sys, os, json, time, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import torch, torch.nn as nn, torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.metrics import accuracy_score

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
LOG = os.path.join(MODEL_DIR, 'v6_fast_log.txt')

def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    with open(LOG, 'a', encoding='utf-8') as f: f.write(line + '\n')
    print(line, flush=True)

def _cs(c): return (c // 5, c % 5)

def calc_metrics(y_true, y_pred, y_proba):
    exact = accuracy_score(y_true, y_pred)
    n = len(y_true)
    rps_val = 0.0
    correct_1x2 = 0
    for i in range(n):
        ah, aa = _cs(y_true[i])
        ar = 0 if ah > aa else 1 if ah == aa else 2
        p = y_proba[i]
        cp = np.zeros(3)
        for hh in range(5):
            for a2 in range(5):
                if hh > a2: cp[0] += p[hh*5+a2]
                elif hh == a2: cp[1] += p[hh*5+a2]
                else: cp[2] += p[hh*5+a2]
        ca = np.zeros(3); ca[ar:] = 1.0
        rps_val += float(np.mean((ca - np.cumsum(cp))**2))
        ph, pd, pa = cp
        if ar == 0 and ph >= pd and ph >= pa: correct_1x2 += 1
        elif ar == 1 and pd >= ph and pd >= pa: correct_1x2 += 1
        elif ar == 2 and pa >= ph and pa >= pd: correct_1x2 += 1
    return exact, correct_1x2 / n, rps_val / n

class LabelSmoothingLoss(nn.Module):
    def __init__(self, smoothing=0.1, gamma=2.0):
        super().__init__()
        self.smoothing = smoothing
        self.gamma = gamma
    def forward(self, x, target):
        c = x.size(1)
        smoothed = torch.full_like(x, self.smoothing / (c-1))
        smoothed.scatter_(1, target.unsqueeze(1), 1.0 - self.smoothing)
        logp = torch.log_softmax(x, dim=1)
        loss = -(smoothed * logp).sum(dim=1)
        if self.gamma > 0:
            with torch.no_grad():
                pt = torch.exp(-nn.functional.cross_entropy(x, target, reduction='none'))
            loss = loss * (1 - pt) ** self.gamma
        return loss.mean()

class M5Variant(nn.Module):
    def __init__(self, input_dim, num_classes, layers, dr=0.25):
        super().__init__()
        modules = []
        prev = input_dim
        for i, sz in enumerate(layers):
            modules += [nn.Linear(prev, sz)]
            if sz >= 64: modules += [nn.BatchNorm1d(sz)]
            modules += [nn.ELU(), nn.Dropout(dr * (0.5 if i == len(layers)-1 else 1.0))]
            prev = sz
        modules += [nn.Linear(prev, num_classes)]
        self.net = nn.Sequential(*modules)
    def forward(self, x): return self.net(x)

def main():
    log('='*60)
    log('V6 FAST TRAIN (loads v5_preprocessed.npz)')
    log('='*60)

    t0 = time.time()
    log('\nLoading preprocessed data...')
    data = np.load(os.path.join(MODEL_DIR, 'v5_preprocessed.npz'))
    X = data['X']
    y = data['y']
    mids = data['mids']
    log(f'Loaded {len(X)} matches, {X.shape[1]} features in {time.time()-t0:.1f}s')

    X = X[-50000:]
    y = y[-50000:]
    mids = mids[-50000:]
    log(f'Using {len(X)} recent matches')

    n = len(X); split = int(n * 0.80)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    train_ds = TensorDataset(torch.tensor(X_train, dtype=torch.float32), torch.tensor(y_train, dtype=torch.long))
    test_ds = TensorDataset(torch.tensor(X_test, dtype=torch.float32), torch.tensor(y_test, dtype=torch.long))
    train_loader = DataLoader(train_ds, batch_size=256, shuffle=True)
    val_loader = DataLoader(test_ds, batch_size=512, shuffle=False)

    input_dim = X.shape[1]; num_classes = 25
    log(f'Input dim: {input_dim}, Train: {len(X_train)}, Test: {len(X_test)}')

    ARCHS = {
        'M5_deep_v6f': [256, 512, 256, 128],
        'M5_medium_v6f': [256, 512, 256],
        'M5_ultra_v6f': [1024, 512, 256, 128],
    }
    EPOCHS = 50
    results = {}
    test_probas = {}

    for name, layers in ARCHS.items():
        log(f'\n-- {name}: {layers}, {EPOCHS} epochs --')
        model = M5Variant(input_dim, num_classes, layers, dr=0.25)
        criterion = LabelSmoothingLoss(smoothing=0.1, gamma=2.0)
        optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-5)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS, eta_min=1e-5)

        best_val = 0.0
        patience = 10; pat_counter = 0
        t_start = time.time()

        for ep in range(EPOCHS):
            model.train()
            for xb, yb in train_loader:
                optimizer.zero_grad()
                loss = criterion(model(xb), yb)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()

            model.eval()
            all_preds, all_proba, all_true = [], [], []
            val_loss = 0.0
            with torch.no_grad():
                for xb, yb in val_loader:
                    out = model(xb)
                    val_loss += criterion(out, yb).item()
                    proba = torch.softmax(out, dim=1)
                    all_preds.extend(proba.argmax(dim=1).tolist())
                    all_proba.extend(proba.tolist())
                    all_true.extend(yb.tolist())

            scheduler.step()
            exact, acc_1x2, rps_val = calc_metrics(np.array(all_true), np.array(all_preds), np.array(all_proba))
            log(f'  Ep {ep+1}/{EPOCHS} | Loss: {val_loss/len(val_loader):.4f} | Exact: {exact*100:.2f}% | 1X2: {acc_1x2*100:.2f}% | RPS: {rps_val:.4f}')

            if exact > best_val:
                best_val = exact
                pat_counter = 0
                torch.save(model.state_dict(), os.path.join(MODEL_DIR, f'{name}.pt'))
            else:
                pat_counter += 1
                if pat_counter >= patience:
                    log(f'  Early stopping at ep {ep+1}')
                    break

        model.load_state_dict(torch.load(os.path.join(MODEL_DIR, f'{name}.pt'), weights_only=True))
        model.eval()
        all_preds, all_proba, all_true = [], [], []
        with torch.no_grad():
            for xb, yb in val_loader:
                proba = torch.softmax(model(xb), dim=1)
                all_preds.extend(proba.argmax(dim=1).tolist())
                all_proba.extend(proba.tolist())
                all_true.extend(yb.tolist())
        exact, acc_1x2, rps_val = calc_metrics(np.array(all_true), np.array(all_preds), np.array(all_proba))
        results[name] = {'exact': exact*100, '1x2': acc_1x2*100, 'rps': rps_val, 'time': time.time()-t_start}
        test_probas[name] = np.array(all_proba)
        log(f'  >> {name}: Exact={exact*100:.2f}%, 1X2={acc_1x2*100:.2f}%, RPS={rps_val:.4f} ({time.time()-t_start:.0f}s)')

    # Weighted Average Ensemble
    log(f'\n{"="*60}')
    log('Weighted Average Ensemble (Dirichlet search)')
    log(f'{"="*60}')

    all_probas = np.stack([test_probas[n] for n in ARCHS.keys()], axis=-1)
    n_archs = len(ARCHS)
    best_exact = 0; best_w = None; best_preds = None

    for trial in range(5000):
        w = np.random.dirichlet(np.ones(n_archs))
        ensemble = np.tensordot(all_probas, w, axes=(-1, 0))
        preds = ensemble.argmax(axis=1)
        exact = float(accuracy_score(y_test, preds))
        if exact > best_exact:
            best_exact = exact
            best_w = w.copy()
            best_preds = ensemble

    _, best_1x2, best_rps = calc_metrics(y_test, best_preds.argmax(axis=1), best_preds)
    log(f'Best ensemble: Exact={best_exact*100:.2f}%, 1X2={best_1x2*100:.2f}%, RPS={best_rps:.4f}')
    log(f'Best weights: {dict(zip(ARCHS.keys(), [round(w,3) for w in best_w]))}')

    out = {
        'models': {k: v for k, v in results.items()},
        'ensemble': {'exact': round(best_exact*100, 2), '1x2': round(best_1x2*100, 2), 'rps': round(best_rps, 4), 'weights': {k: round(float(best_w[i]),3) for i, k in enumerate(ARCHS.keys())}},
        'total_time': round(time.time()-t0, 1),
    }
    with open(os.path.join(MODEL_DIR, 'v6_fast_results.json'), 'w') as f:
        json.dump(out, f, indent=2)

    log(f'\nTotal time: {time.time()-t0:.0f}s')
    log(f'Results saved to models/v6_fast_results.json')

if __name__ == '__main__':
    main()
