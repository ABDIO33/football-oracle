"""
FD Direct Score Predictor — trains XGBoost on Football-Data.co.uk matches.
Features: market odds (B365, Avg), implied probabilities.
19k matches, 2012-2026. Separate from SofaScore model.
"""
import sqlite3, json, os, sys
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.metrics import accuracy_score
from collections import OrderedDict

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
MODEL_PATH = os.path.join(MODEL_DIR, 'fd_direct_score.json')

SCORE_CLASSES = [(h, a) for h in range(5) for a in range(5)] + [(4, 4)]  # 0-0..4-4, then 5+ mapped to (4,4)

def score_to_class(h, a):
    h = min(h, 4)
    a = min(a, 4)
    return h * 5 + a

def class_to_score(cls):
    return SCORE_CLASSES[cls]

def load_data():
    conn = sqlite3.connect(DB)
    df = pd.read_sql("""
        SELECT date, home_team, away_team,
               home_goals as home_score, away_goals as away_score,
               b365h, b365d, b365a, avgh, avgd, avga, maxh, maxd, maxa,
               league
        FROM football_data_matches
        WHERE home_goals IS NOT NULL AND away_goals IS NOT NULL
          AND b365h IS NOT NULL
    """, conn)
    conn.close()
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    print(f'Loaded {len(df)} FD matches with scores + odds')
    return df

def build_features(df):
    """Build feature matrix from FD match data."""
    rows = []
    for _, r in df.iterrows():
        features = OrderedDict()
        features['b365h'] = r['b365h']
        features['b365d'] = r['b365d']
        features['b365a'] = r['b365a']
        features['avgh'] = r['avgh']
        features['avgd'] = r['avgd']
        features['avga'] = r['avga']
        # Implied probabilities
        inv_sum = 1.0/r['avgh'] + 1.0/r['avgd'] + 1.0/r['avga']
        features['implied_h'] = (1.0/r['avgh']) / inv_sum if inv_sum > 0 else 0
        features['implied_d'] = (1.0/r['avgd']) / inv_sum if inv_sum > 0 else 0
        features['implied_a'] = (1.0/r['avga']) / inv_sum if inv_sum > 0 else 0
        # Overround
        features['overround'] = inv_sum
        # Log odds
        features['log_odds_h'] = np.log(r['b365h'])
        features['log_odds_d'] = np.log(r['b365d'])
        features['log_odds_a'] = np.log(r['b365a'])
        
        target = score_to_class(int(r['home_score']), int(r['away_score']))
        rows.append((features, target, r['date'], r['league']))
    
    return rows

def train(save=True):
    df = load_data()
    data = build_features(df)
    
    feat_names = list(data[0][0].keys())
    print(f'Features ({len(feat_names)}): {feat_names}')
    
    # Time-split: train on 2012-2024, test on 2025-2026
    split_date = '2025-01-01'
    train_data = [d for d in data if str(d[2])[:10] < split_date]
    test_data = [d for d in data if str(d[2])[:10] >= split_date]
    
    print(f'Train: {len(train_data)}, Test: {len(test_data)} (split: {split_date})')
    
    X_train = np.array([[d[0][f] for f in feat_names] for d in train_data])
    y_train = np.array([d[1] for d in train_data])
    X_test = np.array([[d[0][f] for f in feat_names] for d in test_data])
    y_test = np.array([d[1] for d in test_data])
    
    model = xgb.XGBClassifier(
        n_estimators=400,
        max_depth=6,
        learning_rate=0.08,
        objective='multi:softprob',
        num_class=25,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=3,
        reg_lambda=1.0,
        reg_alpha=0.1,
        random_state=42,
        n_jobs=-1,
        eval_metric='mlogloss'
    )
    
    model.fit(X_train, y_train,
              eval_set=[(X_test, y_test)],
              verbose=False)
    
    # Evaluate
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)
    
    exact_acc = accuracy_score(y_test, y_pred)
    
    # 1X2 accuracy
    def get_1x2(cls):
        h, a = class_to_score(cls)
        return 0 if h > a else 1 if h == a else 2
    
    y_test_1x2 = np.array([get_1x2(c) for c in y_test])
    y_pred_1x2 = np.array([get_1x2(c) for c in y_pred])
    acc_1x2 = accuracy_score(y_test_1x2, y_pred_1x2)
    
    # RPS
    rps_total = 0
    n_classes = 25
    for i in range(len(y_test)):
        cum_pred = np.cumsum(y_proba[i])
        cum_true = np.zeros(n_classes)
        cum_true[y_test[i]] = 1
        cum_true = np.cumsum(cum_true)
        rps_total += np.mean((cum_pred - cum_true) ** 2)
    rps = rps_total / len(y_test)
    
    # Per-league breakdown
    leagues = {}
    for d in test_data:
        league = d[3] if d[3] else 'Unknown'
        if league not in leagues:
            leagues[league] = {'total': 0, 'exact': 0}
    
    for i, d in enumerate(test_data):
        league = d[3] if d[3] else 'Unknown'
        if league in leagues:
            leagues[league]['total'] += 1
            if y_pred[i] == y_test[i]:
                leagues[league]['exact'] += 1
    
    print(f'\n=== FD Direct Score Model Results ===')
    print(f'  Exact score: {exact_acc*100:.2f}%')
    print(f'  1X2:         {acc_1x2*100:.2f}%')
    print(f'  RPS:         {rps:.4f}')
    print(f'  Test size:   {len(y_test)}')
    
    print(f'\n=== Per-League ===')
    for league, stats in sorted(leagues.items(), key=lambda x: -x[1]['total']):
        if stats['total'] >= 30:
            pct = stats['exact'] / stats['total'] * 100
            print(f'  {league}: {pct:.1f}% ({stats["exact"]}/{stats["total"]})')
    
    if save:
        os.makedirs(MODEL_DIR, exist_ok=True)
        model.save_model(MODEL_PATH)
        
        info = {
            'features': feat_names,
            'exact_accuracy': float(exact_acc),
            'acc_1x2': float(acc_1x2),
            'rps': float(rps),
            'train_size': len(train_data),
            'test_size': len(test_data),
            'split_date': split_date,
            'model_type': 'XGBoost multi:softprob',
            'n_classes': 25,
            'per_league': {k: v for k, v in sorted(leagues.items(), key=lambda x: -x[1]['total']) if v['total'] >= 30}
        }
        info_path = os.path.join(MODEL_DIR, 'fd_direct_model_info.json')
        with open(info_path, 'w') as f:
            json.dump(info, f, indent=2)
        print(f'\nModel saved to {MODEL_PATH}')
        print(f'Info saved to {info_path}')
    
    return model

def predict_match(b365h, b365d, b365a, avgh=None, avgd=None, avga=None, model=None):
    """Predict match outcome from market odds."""
    if model is None:
        model = xgb.XGBClassifier()
        model.load_model(MODEL_PATH)
    
    if avgh is None:
        avgh, avgd, avga = b365h, b365d, b365a
    
    inv_sum = 1.0/avgh + 1.0/avgd + 1.0/avga
    
    features = OrderedDict()
    features['b365h'] = b365h
    features['b365d'] = b365d
    features['b365a'] = b365a
    features['avgh'] = avgh
    features['avgd'] = avgd
    features['avga'] = avga
    features['implied_h'] = (1.0/avgh) / inv_sum if inv_sum > 0 else 0
    features['implied_d'] = (1.0/avgd) / inv_sum if inv_sum > 0 else 0
    features['implied_a'] = (1.0/avga) / inv_sum if inv_sum > 0 else 0
    features['overround'] = inv_sum
    features['log_odds_h'] = np.log(b365h)
    features['log_odds_d'] = np.log(b365d)
    features['log_odds_a'] = np.log(b365a)
    
    X = np.array([[features[f] for f in features.keys()]])
    proba = model.predict_proba(X)[0]
    
    # Top scores
    top_indices = np.argsort(proba)[::-1][:5]
    top_scores = [(class_to_score(i), float(proba[i])) for i in top_indices]
    
    # 1X2 probs
    prob_1x2 = [0.0, 0.0, 0.0]
    for cls in range(25):
        h, a = class_to_score(cls)
        if h > a:
            prob_1x2[0] += proba[cls]
        elif h == a:
            prob_1x2[1] += proba[cls]
        else:
            prob_1x2[2] += proba[cls]
    
    # Expected goals
    exp_h = sum(class_to_score(cls)[0] * proba[cls] for cls in range(25))
    exp_a = sum(class_to_score(cls)[1] * proba[cls] for cls in range(25))
    
    return {
        'score_probs': {f'{h}-{a}': float(proba[h*5+a]) for h in range(5) for a in range(5)},
        'probs_1x2': {'1': float(prob_1x2[0]), 'X': float(prob_1x2[1]), '2': float(prob_1x2[2])},
        'expected_goals': {'home': float(exp_h), 'away': float(exp_a)},
        'top_scores': top_scores,
        'source': 'fd_direct_model'
    }

if __name__ == '__main__':
    train(save=True)
