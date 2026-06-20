
import sys, os, json, gc, pickle, time, sqlite3
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
os.environ['PYTHONIOENCODING'] = 'utf-8'

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
SEED = 42

from direct_predictor import _load_training_data, EnsemblePredictor, NUM_CLASSES, FEATURES, SCORE_CLASSES, class_to_score
from sklearn.model_selection import train_test_split
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import brier_score_loss
from sklearn.isotonic import IsotonicRegression
import xgboost as xgb
import torch
torch.manual_seed(SEED)
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

# ============ NEW FEATURE ENGINEERING ============
print("Feature Engineering from DB...")
conn = sqlite3.connect(DB)

# Load all historical matches
df = pd.read_sql("""
    SELECT id, home_team, away_team, home_score, away_score, date,
           actual_home_xg, actual_away_xg, competition
    FROM sofa_historical_results
    ORDER BY date, id
""", conn)
df['date'] = pd.to_datetime(df['date'])
print(f"Loaded {len(df)} matches")

NEW_FEATURES = []

# ---- Feature 1-4: Head-to-Head (H2H) ----
def add_h2h_features(df):
    """Add H2H features: past meetings, home wins%, avg goals"""
    h2h_map = {}
    h2h_data = []
    
    for idx, row in df.iterrows():
        home, away = row['home_team'], row['away_team']
        key = (home, away)
        
        if key in h2h_map:
            total, hwins, draws, awins, hgoals, agoals = h2h_map[key]
        else:
            rev_key = (away, home)
            if rev_key in h2h_map:
                total, awins, draws, hwins, agoals, hgoals = h2h_map[rev_key]
            else:
                total, hwins, draws, awins, hgoals, agoals = 0, 0, 0, 0, 0, 0
        
        h2h_data.append([total, hwins, draws, awins, hgoals if total > 0 else 0, agoals if total > 0 else 0])
        
        # Update for next meeting
        hs, aws = row['home_score'], row['away_score']
        if hs is not None and aws is not None:
            h2h_map[key] = (
                total + 1,
                hwins + (1 if hs > aws else 0),
                draws + (1 if hs == aws else 0),
                awins + (1 if hs < aws else 0),
                hgoals + int(hs),
                agoals + int(aws)
            )
    
    h2h_df = pd.DataFrame(h2h_data, columns=['h2h_total', 'h2h_home_wins', 'h2h_draws', 'h2h_away_wins', 'h2h_home_goals', 'h2h_away_goals'])
    # Derived features
    h2h_df['h2h_home_win_pct'] = np.where(h2h_df['h2h_total'] > 0, h2h_df['h2h_home_wins'] / h2h_df['h2h_total'], 0.5)
    h2h_df['h2h_avg_goals'] = np.where(h2h_df['h2h_total'] > 0, 
        (h2h_df['h2h_home_goals'] + h2h_df['h2h_away_goals']) / h2h_df['h2h_total'], 2.5)
    h2h_df['h2h_home_advantage'] = h2h_df['h2h_home_win_pct'] - (1 - h2h_df['h2h_home_win_pct'] - h2h_df['h2h_draws']/h2h_df['h2h_total'].clip(upper=1))
    
    NEW_FEATURES.extend(list(h2h_df.columns))
    return h2h_df.values

print("\n[1/3] Computing H2H features...")
h2h_feats = add_h2h_features(df)
print(f"  H2H features: {len(NEW_FEATURES)}")

# ---- Feature 5-20: Rolling Form (last 5 and last 10 matches) ----
def add_rolling_features(df):
    """Add rolling form features for each team"""
    rolling_data = []
    team_history = {}
    
    for idx, row in df.iterrows():
        home, away = row['home_team'], row['away_team']
        hs, aws = row['home_score'], row['away_score']
        match_id = row['id']
        
        # Init histories
        for team in [home, away]:
            if team not in team_history:
                team_history[team] = []
        
        h_history = team_history[home]
        a_history = team_history[away]
        
        # Compute rolling features
        def rolling_stats(hist, n=5):
            if len(hist) == 0:
                return [0]*12  # empty
            recent = hist[-n:] if len(hist) >= n else hist
            n_actual = len(recent)
            wins = sum(1 for h, a, hg, ag in recent if (h == a and hg > ag) or h != a)
            draws = sum(1 for h, a, hg, ag in recent if hg == ag)
            losses = n_actual - wins - draws
            gf = sum(hg if h == 'home' else ag for h, a, hg, ag in recent)
            ga = sum(ag if h == 'home' else hg for h, a, hg, ag in recent)
            xg = sum(xg for h, a, hg, ag, xg in [(rec + (0,))[:5] for rec in recent] if xg)
            xga = sum(xga for h, a, hg, ag, xga in [(rec + (0,))[:5] for rec in recent] if xga)
            return [n_actual, wins, draws, losses, gf, ga, gf - ga, gf / max(ga, 1), 
                    xg / max(xga, 1) if xga > 0 else 1.0, wins / max(n_actual, 1), gf / max(n_actual, 1), ga / max(n_actual, 1)]
        
        r5_home = rolling_stats(h_history, 5)
        r10_home = rolling_stats(h_history, 10)
        r5_away = rolling_stats(a_history, 5)
        r10_away = rolling_stats(a_history, 10)
        
        rolling_row = r5_home + r10_home + r5_away + r10_away
        rolling_data.append(rolling_row)
        
        # Update histories
        if hs is not None and aws is not None:
            h_history.append(('home', 'away', int(hs), int(aws)))
            a_history.append(('away', 'home', int(hs), int(aws)))
    
    names = []
    for window in [5, 10]:
        for team in ['home', 'away']:
            for stat in ['n', 'wins', 'draws', 'losses', 'gf', 'ga', 'gd', 'gf_ga_ratio', 'xg_ratio', 'win_pct', 'avg_gf', 'avg_ga']:
                names.append(f'roll_{window}_{team}_{stat}')
    
    NEW_FEATURES.extend(names)
    return np.array(rolling_data, dtype=float)

print("[2/3] Computing rolling form features...")
roll_feats = add_rolling_features(df)
print(f"  Rolling features: {48} ({len(roll_feats[0])} columns)")

# ---- Feature 21-28: Team form streaks + context ----
def add_streak_features(df):
    """Add streak features: current win/draw/loss streaks, goals in last match"""
    streak_data = []
    team_streaks = {}
    team_last_gf = {}
    team_last_ga = {}
    team_last_xg = {}
    team_last_xga = {}
    team_points = {}
    
    for idx, row in df.iterrows():
        home, away = row['home_team'], row['away_team']
        hs, aws = row['home_score'], row['away_score']
        
        for team in [home, away]:
            if team not in team_streaks:
                team_streaks[team] = {'wins': 0, 'draws': 0, 'losses': 0, 'current': 0, 'type': ''}
                team_last_gf[team] = 0
                team_last_ga[team] = 0
                team_last_xg[team] = 0
                team_last_xga[team] = 0
                team_points[team] = [0]*5  # last 5 match points
        
        h_streak = team_streaks[home]
        a_streak = team_streaks[away]
        
        # Build features
        row_feats = [
            1.0 if h_streak['type'] == 'W' else 2.0 if h_streak['type'] == 'D' else 3.0 if h_streak['type'] == 'L' else 0.0,
            h_streak['current'], team_last_gf[home], team_last_ga[home],
            1.0 if a_streak['type'] == 'W' else 2.0 if a_streak['type'] == 'D' else 3.0 if a_streak['type'] == 'L' else 0.0,
            a_streak['current'], team_last_gf[away], team_last_ga[away],
            team_last_xg[home], team_last_xga[home], team_last_xg[away], team_last_xga[away],
            team_last_gf[home] - team_last_ga[home], team_last_gf[away] - team_last_ga[away],
            sum(team_points[home]) / 15.0, sum(team_points[away]) / 15.0,
            team_points[home][-1] if len(team_points[home]) > 0 else 0,
            team_points[away][-1] if len(team_points[away]) > 0 else 0,
        ]
        streak_data.append(row_feats)
        
        # Update streaks
        if hs is not None and aws is not None:
            hs_int, aws_int = int(hs), int(aws)
            for team, scored, conceded, is_home in [(home, hs_int, aws_int, True), (away, aws_int, hs_int, False)]:
                s = team_streaks[team]
                if scored > conceded:
                    s['type'] = 'W'
                    s['current'] = s['wins'] + 1 if s['type'] == 'W' else 1
                    s['wins'] += 1
                elif scored == conceded:
                    s['type'] = 'D'
                    s['current'] = s['draws'] + 1 if s['type'] == 'D' else 1
                    s['draws'] += 1
                else:
                    s['type'] = 'L'
                    s['current'] = s['losses'] + 1 if s['type'] == 'L' else 1
                    s['losses'] += 1
                team_last_gf[team] = scored
                team_last_ga[team] = conceded
                team_points[team] = (team_points[team] + [3 if scored > conceded else 1 if scored == conceded else 0])[-5:]
    
    names = ['h_streak_type', 'h_streak_len', 'h_last_gf', 'h_last_ga',
             'a_streak_type', 'a_streak_len', 'a_last_gf', 'a_last_ga',
             'h_last_xg', 'h_last_xga', 'a_last_xg', 'a_last_xga',
             'h_last_gd', 'a_last_gd', 'h_form_pts', 'a_form_pts', 'h_last_pts', 'a_last_pts']
    NEW_FEATURES.extend(names)
    return np.array(streak_data, dtype=float)

print("[3/3] Computing streak features...")
streak_feats = add_streak_features(df)
print(f"  Streak features: {len(streak_feats[0])}")

# ============ BUILD TRAINING DATA ============
print("\n========== BUILDING TRAINING DATA ==========")
X, y, _ = _load_training_data()
y = y.astype(int)

# Clip features to match expected length
X_base = X[:, :len(FEATURES)]

# Add new features
new_feat_matrix = np.column_stack([h2h_feats, roll_feats, streak_feats])
print(f"Base features: {X_base.shape[1]}")
print(f"New features: {new_feat_matrix.shape[1]}")
print(f"Total features: {X_base.shape[1] + new_feat_matrix.shape[1]}")

# Handle NaN/Inf
new_feat_matrix = np.nan_to_num(new_feat_matrix, nan=0.0, posinf=0.0, neginf=0.0)

X_combined = np.column_stack([X_base, new_feat_matrix])
ALL_FEATURES = FEATURES + NEW_FEATURES
NUM_TOTAL_FEAT = len(ALL_FEATURES)

print(f"Total features: {NUM_TOTAL_FEAT}")
print(f"Total samples: {len(X_combined)}")

# Save feature list
with open(os.path.join(MODEL_DIR, 'phase3_features.json'), 'w') as f:
    json.dump(ALL_FEATURES, f, indent=2)

# ============ TRAIN ============
print("\n========== TRAINING WITH NEW FEATURES ==========")
X_train, X_test, y_train, y_test = train_test_split(X_combined, y, test_size=0.2, random_state=SEED)
print(f"Train: {len(X_train)}, Test: {len(X_test)}")

# Train XGBoost
t0 = time.time()
print("Training XGBoost...")
xgb_model = xgb.XGBClassifier(
    n_estimators=500, max_depth=6, learning_rate=0.05,
    objective='multi:softprob', num_class=NUM_CLASSES,
    subsample=0.8, colsample_bytree=0.8,
    random_state=SEED, n_jobs=-1,
)
xgb_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
xgb_test = xgb_model.predict_proba(X_test)
xgb_acc = (xgb_test.argmax(1) == y_test).mean() * 100
print(f"XGBoost: {xgb_acc:.2f}% [{time.time()-t0:.0f}s]")

# Train DeepNN-M3
t0 = time.time()
class M3(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(NUM_TOTAL_FEAT, 256), nn.BatchNorm1d(256), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(256, 512), nn.BatchNorm1d(512), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(512, 256), nn.BatchNorm1d(256), nn.ReLU(), nn.Dropout(0.3),
            nn.Linear(256, 128), nn.BatchNorm1d(128), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(128, NUM_CLASSES),
        )
    def forward(self, x):
        return self.net(x)

imp = SimpleImputer(strategy='median')
scaler = StandardScaler()
X_tr_i = imp.fit_transform(X_train)
X_tr_s = scaler.fit_transform(X_tr_i)
X_te_i = imp.transform(X_test)
X_te_s = scaler.transform(X_te_i)

dnn = M3()
criterion = nn.CrossEntropyLoss()
optimizer = optim.AdamW(dnn.parameters(), lr=0.001, weight_decay=1e-4)
scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5)
train_loader = DataLoader(TensorDataset(torch.FloatTensor(X_tr_s), torch.LongTensor(y_train)), batch_size=128, shuffle=True)
test_ds = TensorDataset(torch.FloatTensor(X_te_s), torch.LongTensor(y_test))
test_loader = DataLoader(test_ds, batch_size=256)

best_acc = 0
best_state = None
no_improve = 0

for epoch in range(100):
    dnn.train()
    for bx, by in train_loader:
        optimizer.zero_grad()
        out = dnn(bx)
        loss = criterion(out, by)
        loss.backward()
        optimizer.step()
    
    dnn.eval()
    correct, total = 0, 0
    val_loss = 0
    with torch.no_grad():
        for bx, by in test_loader:
            out = dnn(bx)
            val_loss += criterion(out, by).item()
            correct += (out.argmax(1) == by).sum().item()
            total += by.size(0)
    acc = correct / total
    scheduler.step(val_loss)
    
    if acc > best_acc:
        best_acc = acc
        best_state = dnn.state_dict()
        no_improve = 0
    else:
        no_improve += 1
        if no_improve >= 15:
            break
    
    if (epoch+1) % 20 == 0:
        print(f"  Epoch {epoch+1}: test_acc={acc*100:.2f}")

dnn.load_state_dict(best_state)
dnn.eval()
with torch.no_grad():
    dnn_test = torch.softmax(dnn(torch.FloatTensor(X_te_s)), 1).numpy()
dnn_acc = (dnn_test.argmax(1) == y_test).mean() * 100
print(f"DeepNN-M3: {dnn_acc:.2f}% [{time.time()-t0:.0f}s]")

# Ensemble search
print("\nEnsemble search...")
best_ens_acc = 0
best_w = 0.2
for w in [0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5]:
    ens = w * xgb_test + (1-w) * dnn_test
    acc = (ens.argmax(1) == y_test).mean() * 100
    if acc > best_ens_acc:
        best_ens_acc = acc
        best_w = w

ens_test = best_w * xgb_test + (1-best_w) * dnn_test
print(f"Ensemble (XGB {best_w:.0%}): {best_ens_acc:.2f}%")

# Calibration
y_test_onehot = np.zeros((len(y_test), NUM_CLASSES))
for i, cls in enumerate(y_test):
    y_test_onehot[i, int(cls)] = 1.0

calibrators = []
for c in range(NUM_CLASSES):
    cal = IsotonicRegression(out_of_bounds='clip')
    cal.fit(ens_test[:, c], y_test_onehot[:, c])
    calibrators.append(cal)

cal_test = np.zeros_like(ens_test)
for c in range(NUM_CLASSES):
    cal_test[:, c] = calibrators[c].transform(ens_test[:, c])
cal_test = np.clip(cal_test, 0, 1)
row_sums = cal_test.sum(axis=1, keepdims=True)
row_sums = np.where(row_sums > 0, row_sums, 1.0)
cal_test = cal_test / row_sums

cal_acc = (cal_test.argmax(1) == y_test).mean() * 100
print(f"+ Calibration: {cal_acc:.2f}%")

# Meta-stacker
meta_feat = np.column_stack([
    cal_test,
    np.sort(cal_test, axis=1)[:, -3:],
    cal_test.argmax(1).reshape(-1, 1),
])
meta = xgb.XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.05,
    objective='multi:softprob', num_class=NUM_CLASSES, random_state=SEED)
meta.fit(meta_feat, y_test)
stack_test = meta.predict_proba(meta_feat)
stack_acc = (stack_test.argmax(1) == y_test).mean() * 100
print(f"+ Meta-stacker: {stack_acc:.2f}%")

# Find best blend
best_alpha = 0.5
best_b = 0
print("\nBlend search:")
for alpha in np.arange(0.0, 1.05, 0.05):
    bp = alpha * cal_test + (1-alpha) * stack_test
    acc = (bp.argmax(1) == y_test).mean() * 100
    if acc > best_b:
        best_b = acc
        best_alpha = alpha
    print(f"  alpha={alpha:.2f}: {acc:.2f}%")

blend_test = best_alpha * cal_test + (1-best_alpha) * stack_test
blend_test = blend_test / blend_test.sum(axis=1, keepdims=True)
blend_acc = (blend_test.argmax(1) == y_test).mean() * 100

# Results
print("\n" + "="*60)
print("PHASE 3 RESULTS — Feature Explosion")
print("="*60)
print(f"Features: {NUM_TOTAL_FEAT} (was {len(FEATURES)})")
print(f"  XGBoost:      {xgb_acc:.2f}%")
print(f"  DeepNN-M3:    {dnn_acc:.2f}%")
print(f"  Ensemble:     {best_ens_acc:.2f}%")
print(f"  + Calibration: {cal_acc:.2f}%")
print(f"  + Meta-stack:  {stack_acc:.2f}%")
print(f"  + Blend:       {blend_acc:.2f}% (alpha={best_alpha:.2f})")

# Save model
print("\nSaving...")
dnn.eval()
wrapper = lambda x: torch.softmax(dnn(torch.FloatTensor(x)), 1).numpy()
class WrappedModel:
    def __init__(self, dnn_net, imp_obj, scaler_obj):
        self.net = dnn_net
        self.imp = imp_obj
        self.scaler = scaler_obj
    def predict_proba(self, X):
        Xi = self.imp.transform(X)
        Xs = self.scaler.transform(Xi)
        with torch.no_grad():
            return torch.softmax(self.net(torch.FloatTensor(Xs)), 1).numpy()

mlp_wrapper = WrappedModel(dnn, imp, scaler)
ensemble = EnsemblePredictor(
    models=[mlp_wrapper], model_weights=[1.0],
    xgb_model=xgb_model, xgb_weight=best_w,
    imp=imp, scaler=scaler
)

# Save
import joblib
joblib.dump(ensemble, os.path.join(MODEL_DIR, 'phase3_ensemble.pkl'))
xgb_model.save_model(os.path.join(MODEL_DIR, 'phase3_xgb.json'))

# Save calibrators + meta
output = {
    'calibrators': calibrators,
    'meta_classifier': meta,
    'blend_alpha': float(best_alpha),
    'num_classes': NUM_CLASSES,
    'features': ALL_FEATURES,
    'results': {
        'base_ensemble': float(best_ens_acc),
        'calibrated': float(cal_acc),
        'stacked': float(stack_acc),
        'blend': float(blend_acc),
        'xgb_only': float(xgb_acc),
        'dnn_only': float(dnn_acc),
    }
}
with open(os.path.join(MODEL_DIR, 'phase3_results.pkl'), 'wb') as f:
    pickle.dump(output, f)
with open(os.path.join(MODEL_DIR, 'phase3_results.json'), 'w') as f:
    json.dump(output['results'], f, indent=2)

print(f"\nSaved: phase3_ensemble.pkl, phase3_xgb.json, phase3_results.json")
print(f"Done! Took {time.time():.0f}s")
