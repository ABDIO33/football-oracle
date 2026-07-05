"""Analyze actual training data size and plan improvements"""
import sys, os, sqlite3

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
conn = sqlite3.connect(DB)

# Check walkforward + training data
print("=== TRAINING DATA ANALYSIS ===")

# 1. Walkforward state size
cur = conn.execute('SELECT COUNT(*) FROM walkforward_state')
wf = cur.fetchone()[0]
print(f'Walkforward state rows: {wf:,}')

# 2. Walkforward progress (processed matches)
cur = conn.execute('SELECT COUNT(*) FROM walkforward_progress')
wp = cur.fetchone()[0]
print(f'Walkforward progress: {wp:,}')

# 3. Glicko state size
cur = conn.execute('SELECT COUNT(*) FROM glicko_state')
gs = cur.fetchone()[0]
print(f'Glicko state rows: {gs:,}')

# 4. Sofa historical results
cur = conn.execute('SELECT COUNT(*) FROM sofa_historical_results')
hr = cur.fetchone()[0]
print(f'Historical results: {hr:,}')

# 5. How many walkforward rows have elo (non-null)?
cur = conn.execute('SELECT COUNT(*) FROM walkforward_state WHERE elo IS NOT NULL')
elo = cur.fetchone()[0]
print(f'Walkforward with Elo: {elo:,}')

# 6. Date range in walkforward
cur = conn.execute('SELECT MIN(date), MAX(date) FROM walkforward_state')
dr = cur.fetchone()
print(f'Walkforward date range: {dr[0]} to {dr[1]}')

# 7. Unique teams in walkforward
cur = conn.execute('SELECT COUNT(DISTINCT team_name) FROM walkforward_state')
teams = cur.fetchone()[0]
print(f'Unique teams: {teams}')

# 8. Check training data structure (from direct_predictor)
from direct_predictor import FEATURES
print(f'\nCurrent features: {len(FEATURES)}')
for f in FEATURES:
    print(f'  - {f}')

print(f'\n=== SUMMARY ===')
print(f'Current training samples: ~{min(wf, elo):,}')
print(f'Target: 500K-1M samples')
print(f'Status: {"✅ AT 500K TARGET" if min(wf, elo) >= 500000 else f"❌ Need {500000 - min(wf, elo):,} more"}')
print(f'Focus: Model QUALITY improvement')

conn.close()
