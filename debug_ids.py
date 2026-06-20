"""Debug: check match_id alignment"""
import sys; sys.path.insert(0, 'football_predictor')
import sqlite3
from direct_predictor import _load_training_data
import numpy as np

X, y, match_ids = _load_training_data()
print(f'X: {len(X)}, y: {len(y)}, match_ids: {len(match_ids)}')
print(f'First 5 match_ids: {match_ids[:5]}')
print(f'Types: {type(match_ids[0]) if match_ids else "empty"}')

conn = sqlite3.connect('football_predictor/scrape_cache.db')
# Check first 5
for mid in match_ids[:5]:
    cur = conn.execute(f"SELECT id, home_score, away_score FROM sofa_historical_results WHERE id = {mid}")
    r = cur.fetchone()
    if r:
        print(f'  match_id={mid}: found -> score {r[1]}-{r[2]}')
    else:
        print(f'  match_id={mid}: NOT FOUND in DB')

# Check a random sample in middle
import random
random.seed(42)
for mid in random.sample(match_ids, 10):
    cur = conn.execute(f"SELECT id, home_score, away_score FROM sofa_historical_results WHERE id = {mid}")
    r = cur.fetchone()
    if not r:
        print(f'  match_id={mid}: NOT FOUND in DB (random sample)')

conn.close()
print('Done debugging')
