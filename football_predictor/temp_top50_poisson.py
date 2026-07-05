"""Run Poisson MLE on top 50 teams for DeepSeek #2"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))
from poisson_model import FastPoisson
import sqlite3, pandas as pd
from collections import Counter

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

conn = sqlite3.connect(DB)
df = pd.read_sql_query("""
    SELECT date, home_team, away_team, home_score, away_score 
    FROM sofa_historical_results 
    WHERE home_score IS NOT NULL AND away_score IS NOT NULL
    ORDER BY start_timestamp DESC
    LIMIT 150000
""", conn)
conn.close()

matches = [{'date': r['date'], 'home_team': r['home_team'], 'away_team': r['away_team'],
    'home_score': int(r['home_score']), 'away_score': int(r['away_score'])}
    for _, r in df.iterrows()]

print(f'Training Poisson on {len(matches)} matches...')
model = FastPoisson(decay_halflife=180, rho=-0.07)
model.estimate_params(matches)
print(f'Teams in model: {len(model.teams)}')

team_counts = Counter(m['home_team'] for m in matches)
team_counts.update(m['away_team'] for m in matches)
top50 = [t for t, c in team_counts.most_common(50)]

results = []
for team in top50:
    att, dfn = model.get_params(team)
    if att is not None:
        results.append({'team': team, 'attack': round(float(att), 4),
                        'defense': round(float(dfn), 4), 'matches': team_counts[team]})

with open('models/top50_poisson_params.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f'Saved {len(results)} teams')
print(f'Home advantage: {model.home_adv:.4f}')
print()
print('Top 10 by attack:')
for r in sorted(results, key=lambda x: -x['attack'])[:10]:
    print(f'  {r["team"]:30s} att={r["attack"]:.4f} def={r["defense"]:.4f}')

print('Top 10 by defense:')
for r in sorted(results, key=lambda x: x['defense'])[:10]:
    print(f'  {r["team"]:30s} att={r["attack"]:.4f} def={r["defense"]:.4f}')
