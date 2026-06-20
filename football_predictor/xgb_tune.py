"""
xgb_tune.py — Optuna hyperparameter search for XGBoost on 264K data
"""
import sys, os, numpy as np, optuna, json, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))
from direct_predictor import _load_training_data, SCORE_CLASSES
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.impute import SimpleImputer
import xgboost as xgb

print("Loading data...")
X, y, ids = _load_training_data()
print(f"  {len(X)} samples, {X.shape[1]} features")

# Stratified 20% subset for fast tuning
X_sub, _, y_sub, _ = train_test_split(X, y, test_size=0.8, random_state=42, stratify=y)
X_tune, X_val, y_tune, y_val = train_test_split(X_sub, y_sub, test_size=0.2, random_state=42, stratify=y_sub)
print(f"  Tune: {len(X_tune)}, Val: {len(X_val)}")

imp = SimpleImputer(strategy='median')
X_tune_i = imp.fit_transform(X_tune)
X_val_i = imp.transform(X_val)

le = LabelEncoder()
y_tune_e = le.fit_transform(y_tune)
y_val_e = le.transform(y_val)

def objective(trial):
    params = {
        'n_estimators': trial.suggest_int('n_estimators', 300, 800, step=100),
        'max_depth': trial.suggest_int('max_depth', 4, 10),
        'learning_rate': trial.suggest_float('learning_rate', 0.005, 0.1, log=True),
        'subsample': trial.suggest_float('subsample', 0.6, 1.0),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),
        'min_child_weight': trial.suggest_int('min_child_weight', 1, 15),
        'gamma': trial.suggest_float('gamma', 0, 3.0),
        'reg_alpha': trial.suggest_float('reg_alpha', 0, 3.0),
        'reg_lambda': trial.suggest_float('reg_lambda', 0.5, 5.0),
        'objective': 'multi:softprob',
        'num_class': 25,
        'eval_metric': 'mlogloss',
        'random_state': 42,
        'n_jobs': -1,
    }
    model = xgb.XGBClassifier(**params)
    model.fit(X_tune_i, y_tune_e,
              eval_set=[(X_val_i, y_val_e)],
              verbose=False)
    probs = model.predict_proba(X_val_i)
    preds = np.argmax(probs, axis=1)
    exact = (preds == y_val_e).mean()
    return exact

print("\nStarting Optuna search (100 trials)...")
study = optuna.create_study(direction='maximize',
                            sampler=optuna.samplers.TPESampler(seed=42),
                            pruner=optuna.pruners.MedianPruner())
study.optimize(objective, n_trials=100, show_progress_bar=True)

print(f"\nBest trial: {study.best_trial.value:.4f} exact")
print(f"Best params:")
for k, v in study.best_trial.params.items():
    print(f"  {k}: {v}")

# Save results
best = study.best_trial.params
best['exact_val'] = round(float(study.best_trial.value), 4)
with open('models/xgb_best_params.json', 'w') as f:
    json.dump(best, f, indent=2)

# Show top 5
print("\nTop 5 trials:")
for t in sorted(study.trials, key=lambda t: t.value or 0, reverse=True)[:5]:
    print(f"  Exact={t.value:.4f} | {t.params}")

print("\nDONE")
