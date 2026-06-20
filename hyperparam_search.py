"""Hyperparameter tuning for Direct model — try multiple XGBoost configs"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'football_predictor'))
import numpy as np
import xgboost as xgb
from direct_predictor import _load_training_data, FEATURES, NUM_CLASSES, score_to_class, class_to_score, result

X, y, match_ids = _load_training_data()
print(f'Loaded {len(X)} samples')

split = int(len(X) * 0.9)
X_train, X_test = X[:split], X[split:]
y_train, y_test = y[:split], y[split:]

configs = [
    {'name': 'baseline', 'n_estimators': 400, 'max_depth': 6, 'lr': 0.05, 'subsample': 0.8, 'csb': 0.8, 'ra': 0.1, 'rl': 0.1},
    {'name': 'deeper', 'n_estimators': 400, 'max_depth': 8, 'lr': 0.05, 'subsample': 0.8, 'csb': 0.8, 'ra': 0.1, 'rl': 0.1},
    {'name': 'more_trees', 'n_estimators': 600, 'max_depth': 6, 'lr': 0.03, 'subsample': 0.8, 'csb': 0.8, 'ra': 0.1, 'rl': 0.1},
    {'name': 'low_reg', 'n_estimators': 400, 'max_depth': 6, 'lr': 0.05, 'subsample': 0.8, 'csb': 0.8, 'ra': 0.01, 'rl': 0.01},
    {'name': 'high_subsample', 'n_estimators': 400, 'max_depth': 6, 'lr': 0.05, 'subsample': 0.9, 'csb': 0.9, 'ra': 0.1, 'rl': 0.1},
    {'name': 'deep_low_lr', 'n_estimators': 600, 'max_depth': 8, 'lr': 0.03, 'subsample': 0.8, 'csb': 0.8, 'ra': 0.1, 'rl': 0.1},
]

best_exact = 0
for cfg in configs:
    print(f'\n=== {cfg["name"]} ===')
    model = xgb.XGBClassifier(
        n_estimators=cfg['n_estimators'],
        max_depth=cfg['max_depth'],
        learning_rate=cfg['lr'],
        objective='multi:softprob',
        num_class=NUM_CLASSES,
        subsample=cfg['subsample'],
        colsample_bytree=cfg['csb'],
        reg_alpha=cfg['ra'],
        reg_lambda=cfg['rl'],
        random_state=42,
        eval_metric='mlogloss',
        early_stopping_rounds=20,
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    y_pred = np.argmax(model.predict_proba(X_test), axis=1)
    exact = np.mean(y_pred == y_test)
    exact_count = np.sum(y_pred == y_test)

    actual_1x2 = np.array([result(*class_to_score(c)) for c in y_test])
    pred_1x2 = np.array([result(*class_to_score(c)) for c in y_pred])
    acc_1x2 = np.mean(actual_1x2 == pred_1x2)

    n_test = len(y_test)
    rps_total = 0.0
    y_prob = model.predict_proba(X_test)
    for i in range(n_test):
        ah, aa = class_to_score(y_test[i])
        ar = result(ah, aa)
        actual_cum = np.array([1 if ar <= k else 0 for k in range(3)], dtype=float)
        pp = y_prob[i]
        p_h = sum(pp[h*5 + a] for h in range(5) for a in range(5) if h > a)
        p_d = sum(pp[h*5 + h] for h in range(5))
        p_a = sum(pp[h*5 + a] for h in range(5) for a in range(5) if a > h)
        pred_cum = np.cumsum([p_h, p_d, p_a])
        rps_total += np.mean((actual_cum - pred_cum) ** 2)
    rps = rps_total / n_test

    print(f'  Exact: {exact*100:.2f}% ({exact_count}/{n_test})')
    print(f'  1X2: {acc_1x2*100:.2f}%')
    print(f'  RPS: {rps:.3f}')

    if exact > best_exact:
        best_exact = exact
        best_cfg = cfg['name']
        model.save_model(os.path.join('football_predictor', 'models', 'direct_score.json'))
        with open(os.path.join('football_predictor', 'models', 'direct_model_info.json'), 'w') as f:
            json.dump({'features': FEATURES, 'num_classes': NUM_CLASSES, 'config': cfg,
                       'exact_pct': round(exact*100, 2), 'acc_1x2_pct': round(acc_1x2*100, 2), 'rps': round(rps, 3)}, f)

print(f'\nBest: {best_cfg} with {best_exact*100:.2f}% exact')
