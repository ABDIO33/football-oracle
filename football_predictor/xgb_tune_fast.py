"""
xgb_tune_fast.py — Quick grid search for XGBoost hyperparams
"""
import sys, numpy as np, json, xgboost as xgb
sys.path.insert(0, '.')
from direct_predictor import _load_training_data
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.impute import SimpleImputer

X, y, ids = _load_training_data()
X_sub,_,y_sub,_ = train_test_split(X, y, test_size=0.92, random_state=42, stratify=y)
X_t, X_v, y_t, y_v = train_test_split(X_sub, y_sub, test_size=0.2, random_state=42, stratify=y_sub)
print(f'Train: {len(X_t)}, Val: {len(X_v)}')
imp = SimpleImputer(strategy='median')
X_t = imp.fit_transform(X_t); X_v = imp.transform(X_v)
le = LabelEncoder()
y_t = le.fit_transform(y_t); y_v = le.transform(y_v)

best = {'exact': 0, 'params': {}}
for md in [4, 6, 8, 10]:
    for lr in [0.01, 0.03, 0.05, 0.08]:
        for ne in [300, 500, 700]:
            for ss in [0.8, 1.0]:
                p = {
                    'n_estimators': ne, 'max_depth': md, 'learning_rate': lr,
                    'subsample': ss, 'colsample_bytree': 0.8,
                    'min_child_weight': 1, 'gamma': 0,
                    'reg_alpha': 0, 'reg_lambda': 1,
                    'objective': 'multi:softprob', 'num_class': 25,
                    'eval_metric': 'mlogloss', 'random_state': 42, 'n_jobs': -1
                }
                m = xgb.XGBClassifier(**p)
                m.fit(X_t, y_t, eval_set=[(X_v, y_v)], verbose=False)
                pr = np.argmax(m.predict_proba(X_v), axis=1)
                exact = (pr == y_v).mean()
                if exact > best['exact']:
                    best['exact'] = exact
                    best['params'] = p
                    print(f'New best: {exact*100:.2f}% | md={md} lr={lr} ne={ne} ss={ss}')

ex_val = best['exact']
print(f'\nBest exact: {ex_val*100:.2f}%')
print(json.dumps(best['params'], indent=2))
with open('models/xgb_best_params.json', 'w') as f:
    json.dump(best, f, indent=2)
print('Saved to models/xgb_best_params.json')
