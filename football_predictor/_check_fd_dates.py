"""Check FD historical match dates"""
import sqlite3, sys
sys.path.insert(0, '.')
conn = sqlite3.connect('scrape_cache.db')

# Check FD historical matches (id < -2500000)
samples = conn.execute('''
    SELECT id, date, home_team, away_team, home_score, away_score, tournament
    FROM sofa_historical_results
    WHERE id < -2500000
    ORDER BY id ASC LIMIT 5
''').fetchall()
print('First 5 FD historical matches:')
for s in samples:
    print(f'  id={s[0]} date={s[1]} {s[2]} {s[3]} {s[4]}:{s[5]} ({s[6]})')

print()
# Check a date sample
dates = conn.execute('''
    SELECT DISTINCT date FROM sofa_historical_results
    WHERE id < -2500000 AND date LIKE "%/%"
    LIMIT 5
''').fetchall()
print(f'Dates with "/": {[d[0] for d in dates]}')

# Check dates with hyphens
dates2 = conn.execute('''
    SELECT DISTINCT date FROM sofa_historical_results
    WHERE id < -2500000 AND date LIKE "%-%"
    LIMIT 5
''').fetchall()
print(f'Dates with "-": {[d[0] for d in dates2]}')

# Full range
rng = conn.execute('''
    SELECT MIN(date), MAX(date) FROM sofa_historical_results
    WHERE id < -2500000
''').fetchone()
print(f'FD historical date range: {rng[0]} to {rng[1]}')

total = conn.execute('SELECT COUNT(*) FROM sofa_historical_results WHERE id < -2500000').fetchone()[0]
print(f'FD historical count: {total:,}')

conn.close()
