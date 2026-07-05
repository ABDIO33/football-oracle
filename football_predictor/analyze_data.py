"""Analyze existing data to plan bulk collection"""
import sqlite3, os, json
from sofascore_scraper import _get

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
conn = sqlite3.connect(DB)

# 1. What tournaments do we have?
print("=== Existing Tournament Analysis ===")
cur = conn.execute('''
    SELECT unique_tournament_id, COUNT(*) as cnt, 
           MIN(season_id) as min_s, MAX(season_id) as max_s,
           COUNT(DISTINCT season_id) as seasons
    FROM sofa_historical_results 
    WHERE unique_tournament_id IS NOT NULL
    GROUP BY unique_tournament_id
    ORDER BY cnt DESC
    LIMIT 30
''')
print(f"{'Tournament ID':<15} {'Matches':<10} {'Seasons':<10}")
print("-"*35)
for r in cur.fetchall():
    print(f"{r[0]:<15} {r[1]:<10} {r[4]:<10}")

# 2. Total tournamnents and seasons
cur = conn.execute('SELECT COUNT(DISTINCT unique_tournament_id) FROM sofa_historical_results')
print(f'\nTotal unique tournaments: {cur.fetchone()[0]}')
cur = conn.execute('SELECT COUNT(DISTINCT season_id) FROM sofa_historical_results WHERE season_id IS NOT NULL')
print(f'Total unique seasons: {cur.fetchone()[0]}')

# 3. Date range
cur = conn.execute('SELECT MIN(date), MAX(date) FROM sofa_historical_results')
r = cur.fetchone()
print(f'\nDate range: {r[0]} to {r[1]}')

# 4. Teams
cur = conn.execute('SELECT COUNT(DISTINCT home_team) as t FROM sofa_historical_results')
print(f'Unique teams: {cur.fetchone()[0]}')

# 5. Check if we already have full seasons or just partial
print("\n=== Top 10 Tournaments Coverage ===")
cur = conn.execute('''
    SELECT unique_tournament_id, season_id, COUNT(*) as cnt, 
           MIN(date) as min_d, MAX(date) as max_d
    FROM sofa_historical_results 
    WHERE unique_tournament_id IS NOT NULL AND season_id IS NOT NULL
    GROUP BY unique_tournament_id, season_id
    HAVING cnt > 100
    ORDER BY cnt DESC
    LIMIT 20
''')
for r in cur.fetchall():
    print(f'  Tournament {r[0]}, Season {r[1]}: {r[2]} matches ({r[3]} to {r[4]})')

conn.close()
