"""Test fast Poisson model"""
import sys, os, time, numpy as np, sqlite3
sys.path.insert(0, os.path.dirname(__file__))
from poisson_model import FastPoisson, score_to_class, result, class_to_score, log
import pandas as pd
import warnings
warnings.filterwarnings('ignore')
log_enabled = True

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

print('Loading test data...')
conn = sqlite3.connect(DB)
df = pd.read_sql_query('''
    SELECT date, home_team, away_team, home_score, away_score 
    FROM sofa_historical_results 
    WHERE home_score IS NOT NULL AND away_score IS NOT NULL
      AND date >= '2020-01-01'
    ORDER BY start_timestamp
    LIMIT 3000
''', conn)
conn.close()
print(f'Loaded {len(df)} matches')

split = int(len(df) * 0.80)
train_df = df.iloc[:split]
test_df = df.iloc[split:]

train_matches = [{'date':r['date'],'home_team':r['home_team'],'away_team':r['away_team'],
    'home_score':int(r['home_score']),'away_score':int(r['away_score'])} 
    for _, r in train_df.iterrows()]

print(f'Training on {len(train_matches)} matches...')
t0 = time.time()
poisson = FastPoisson(decay_halflife=180, rho=-0.07)
poisson.estimate_params(train_matches)
print(f'Total time: {time.time()-t0:.1f}s')

# Test prediction
home, away = test_df.iloc[0]['home_team'], test_df.iloc[0]['away_team']
pred = poisson.predict_match(home, away)
if pred:
    print(f'\nSample: {home} vs {away}')
    print(f'Predicted: {pred["score"][0]}-{pred["score"][1]}')
    print(f'1X2: H={pred["home_win"]:.2%} D={pred["draw"]:.2%} A={pred["away_win"]:.2%}')

# Quick eval
print(f'\nQuick eval on {len(test_df)} matches...')
y_true, y_proba = [], []
skip = 0
t0 = time.time()
for _, r in test_df.iterrows():
    pred = poisson.predict_match(r['home_team'], r['away_team'])
    if pred is None:
        skip += 1
        continue
    y_true.append(score_to_class(int(r['home_score']), int(r['away_score'])))
    y_proba.append(pred['probs'])
    
y_arr = np.array(y_true)
p_arr = np.array(y_proba)
p_pred = np.argmax(p_arr, axis=1)
exact = np.mean(p_pred == y_arr) * 100

actual_1x2 = np.array([result(*class_to_score(c)) for c in y_arr])
pred_1x2 = np.array([result(*class_to_score(c)) for c in p_pred])
onex2 = np.mean(actual_1x2 == pred_1x2) * 100

print(f'Results: exact={exact:.2f}% 1X2={onex2:.2f}% skip={skip} time={time.time()-t0:.1f}s')
print('\nSUCCESS! FastPoisson works correctly.')
