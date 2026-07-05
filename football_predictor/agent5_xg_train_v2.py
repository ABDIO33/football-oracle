#!/usr/bin/env python3
"""Train xG model from saved shots data (v2 - corrected column names)."""
import sys, os, json, warnings, numpy as np, pandas as pd
from pathlib import Path
from datetime import datetime

warnings.filterwarnings('ignore')
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8')

MODELS_DIR = Path('models')
DATA_DIR = Path('statsbomb_data')

print("Loading shots data...")
df = pd.read_csv(DATA_DIR / 'shots_raw.csv', low_memory=False)
print(f"Loaded {len(df)} shots from {df['match_id'].nunique()} matches")
print(f"Columns: {list(df.columns)}")

# Convert ALL numeric-ish columns to proper numeric
all_numeric = ['distance','angle','is_header','is_right_foot','is_left_foot','is_other_body',
               'shot_type_Open_Play','shot_type_Free_Kick','shot_type_Penalty','shot_type_Corner',
               'shot_type_Throw_In','shot_type_Set_Piece','first_time','one_on_one',
               'deflected','redirected','under_pressure','n_defenders','n_attackers',
               'gk_distance','big_chance','dist_bin','angle_bin','xg_target','is_goal','half']
for col in all_numeric:
    if col in df.columns:
        # Map string true/false first
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str).str.strip().map({
                'True': 1, 'False': 0, 'true': 1, 'false': 0, '1': 1, '0': 0,
                'Blocked': 0, 'Regular Play': 0, 'Normal': 0, '': 0
            }).fillna(0)
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        print(f"  Cleaned {col}: min={df[col].min()}, max={df[col].max()}, mean={df[col].mean():.2f}")

print("\nEngineering features...")

# Base features (using actual column names from CSV)
base = ['distance', 'angle', 'is_header', 'is_right_foot', 'is_left_foot',
        'shot_type_Open_Play', 'shot_type_Free_Kick', 'shot_type_Penalty',
        'shot_type_Corner', 'first_time', 'one_on_one', 'deflected',
        'under_pressure', 'n_defenders', 'half']

# Engineered features
df['dist_sq'] = df['distance'] ** 2
df['angle_sq'] = df['angle'] ** 2
df['log_dist'] = np.log1p(df['distance'])
df['x_centered'] = abs(df['x'].fillna(60) - 60)
df['y_centered'] = abs(df['y'].fillna(40) - 40)
df['danger'] = np.exp(-df['distance'] / 20) * (1 + abs(df['angle']) / 1.5)
df['def_pressure'] = df['n_defenders'] / (df['distance'] + 1)
df['header_pressure'] = df['is_header'] * df['under_pressure']
df['x_norm'] = df['x'].fillna(60) / 120.0
df['y_norm'] = df['y'].fillna(40) / 80.0

extended = ['dist_sq', 'angle_sq', 'log_dist', 'x_centered', 'y_centered',
            'danger', 'def_pressure', 'header_pressure', 'x_norm', 'y_norm']

features = base + extended
print(f"Features ({len(features)}): {features}")

# Ensure ALL features (including engineered) are cleaned
df[features] = df[features].apply(pd.to_numeric, errors='coerce').fillna(0)

# Target: is_goal
target = 'is_goal'
print(f"Goal rate: {df[target].mean()*100:.2f}%")

# Train/test split by match
from sklearn.model_selection import train_test_split
matches = df['match_id'].unique()
train_m, test_m = train_test_split(matches, test_size=0.2, random_state=42)

X_train = df[df['match_id'].isin(train_m)][features].values.astype(np.float32)
y_train = df[df['match_id'].isin(train_m)][target].values.astype(np.int32)
X_test = df[df['match_id'].isin(test_m)][features].values.astype(np.float32)
y_test = df[df['match_id'].isin(test_m)][target].values.astype(np.int32)

print(f"Train: {len(X_train)} shots ({len(train_m)} matches)")
print(f"Test:  {len(X_test)} shots ({len(test_m)} matches)")
print(f"Goal rate: train={y_train.mean()*100:.2f}%, test={y_test.mean()*100:.2f}%")

# Train XGBoost
import xgboost as xgb
pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)
print(f"Pos weight: {pos_weight:.2f}")

model = xgb.XGBClassifier(
    n_estimators=500, max_depth=6, learning_rate=0.05,
    subsample=0.8, colsample_bytree=0.8,
    min_child_weight=5, gamma=0.1,
    reg_alpha=0.1, reg_lambda=1.0,
    scale_pos_weight=pos_weight,
    objective='binary:logistic',
    eval_metric=['logloss', 'auc'],
    random_state=42, n_jobs=-1,
)

print("Training XGBoost...")
model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

# Save raw model
model.save_model(str(MODELS_DIR / 'xg_model.json'))
print(f"Saved: models/xg_model.json")

# Evaluate
from sklearn.metrics import roc_auc_score, brier_score_loss, log_loss
y_pred = model.predict_proba(X_test)[:, 1]

auc = roc_auc_score(y_test, y_pred)
brier = brier_score_loss(y_test, y_pred)
ll = log_loss(y_test, y_pred)
naive_ll = log_loss(y_test, np.full_like(y_test, y_test.mean()))

print(f"\n=== XGBoost xG Results ===")
print(f"AUC-ROC:   {auc:.4f}")
print(f"Brier:     {brier:.4f}")
print(f"Log Loss:  {ll:.4f} (naive: {naive_ll:.4f})")

# Feature importance
imp = pd.DataFrame({'feature': features, 'importance': model.feature_importances_})
imp = imp.sort_values('importance', ascending=False)
print(f"\nTop 10 features:")
for i, (_, r) in enumerate(imp.head(10).iterrows()):
    print(f"  {i+1}. {r['feature']}: {r['importance']:.4f}")

# Calibrate
from sklearn.calibration import CalibratedClassifierCV
import joblib

print("\nCalibrating with Platt scaling...")
cal = CalibratedClassifierCV(model, method='sigmoid', cv=3)
cal.fit(X_train, y_train)
y_pred_cal = cal.predict_proba(X_test)[:, 1]
cal_brier = brier_score_loss(y_test, y_pred_cal)
cal_ll = log_loss(y_test, y_pred_cal)

print(f"Calibrated: Brier={cal_brier:.4f} (was {brier:.4f})")
print(f"           LogLoss={cal_ll:.4f} (was {ll:.4f})")

joblib.dump(cal, str(MODELS_DIR / 'xg_model_calibrated.pkl'))
print(f"Saved: models/xg_model_calibrated.pkl")

# Per-match analysis
df_test = df[df['match_id'].isin(test_m)].copy()
df_test['pred_xg'] = cal.predict_proba(df_test[features].values.astype(np.float32))[:, 1]

match_stats = df_test.groupby('match_id').agg({
    'xg_target': 'sum', 'pred_xg': 'sum', target: 'sum', 'match_id': 'count'
}).rename(columns={'match_id': 'shots', target: 'goals', 'xg_target': 'statsbomb_xg'})

print(f"\nPer-match (test set, {len(match_stats)} matches):")
print(f"  Mean xG (StatsBomb): {match_stats['statsbomb_xg'].mean():.3f}")
print(f"  Mean xG (Ours):      {match_stats['pred_xg'].mean():.3f}")
print(f"  Mean goals:          {match_stats['goals'].mean():.3f}")
print(f"  MAE vs StatsBomb:    {abs(match_stats['pred_xg'] - match_stats['statsbomb_xg']).mean():.3f}")
print(f"  MAE vs Goals:        {abs(match_stats['pred_xg'] - match_stats['goals']).mean():.3f}")

# Save match analysis
match_stats.to_csv(DATA_DIR / 'match_xg_analysis.csv')

# Calibration curve
from sklearn.calibration import calibration_curve
prob_true, prob_pred = calibration_curve(y_test, y_pred_cal, n_bins=10)

# Feature importance JSON
imp_json = []
for _, r in imp.iterrows():
    imp_json.append({'feature': r['feature'], 'importance': round(float(r['importance']), 4)})

results = {
    'n_matches_total': int(len(matches)),
    'n_shots_total': int(len(df)),
    'n_train': int(len(X_train)),
    'n_test': int(len(X_test)),
    'n_train_matches': int(len(train_m)),
    'n_test_matches': int(len(test_m)),
    'auc_roc': round(float(auc), 4),
    'brier': round(float(brier), 4),
    'brier_calibrated': round(float(cal_brier), 4),
    'log_loss': round(float(ll), 4),
    'log_loss_calibrated': round(float(cal_ll), 4),
    'log_loss_naive': round(float(naive_ll), 4),
    'goal_rate_train': round(float(y_train.mean()), 4),
    'goal_rate_test': round(float(y_test.mean()), 4),
    'pos_weight': round(float(pos_weight), 2),
    'feature_importance': imp_json,
    'top_features': features[:10],
    'calibration_curve': {
        'prob_true': [round(float(p), 4) for p in prob_true],
        'prob_pred': [round(float(p), 4) for p in prob_pred],
    },
    'per_match_mae_vs_goals': round(float(abs(match_stats['pred_xg'] - match_stats['goals']).mean()), 4),
    'per_match_mae_vs_statsbomb': round(float(abs(match_stats['pred_xg'] - match_stats['statsbomb_xg']).mean()), 4),
    'timestamp': datetime.now().isoformat(),
}

with open(MODELS_DIR / 'xg_model_results.json', 'w') as f:
    json.dump(results, f, indent=2)

print(f"\nResults saved to models/xg_model_results.json")
print(f"Raw data: statsbomb_data/shots_raw.csv ({len(df)} rows)")
print(f"Per-match: statsbomb_data/match_xg_analysis.csv")
print(f"\n{'='*60}")
print(f"  DONE! AUC: {auc:.4f} | Brier: {brier:.4f} | Brier(cal): {cal_brier:.4f}")
print(f"{'='*60}")
