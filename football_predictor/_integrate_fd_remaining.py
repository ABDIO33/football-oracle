"""
Integrate remaining 13K football-data.co.uk matches into sofa_historical_results
"""
import sqlite3, os, sys
sys.path.insert(0, os.path.dirname(__file__))
DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
conn = sqlite3.connect(DB)

# Get FD matches not in sofa (exact team name + date match)
missing = conn.execute('''
    SELECT f.id, f.home_team, f.away_team, f.home_goals, f.away_goals, 
           f.date, f.league, f.league_code
    FROM football_data_matches f
    WHERE NOT EXISTS (
        SELECT 1 FROM sofa_historical_results s
        WHERE s.date = f.date
        AND s.home_team = f.home_team
        AND s.away_team = f.away_team
    )
    AND f.home_goals IS NOT NULL AND f.away_goals IS NOT NULL
    ORDER BY f.date
''').fetchall()

print(f'FD matches not in sofa: {len(missing):,}')

# Try to map team names using team_name_mapping
mappings = dict(conn.execute(
    'SELECT fd_name, sofa_name FROM team_name_mapping WHERE confidence >= 0.85'
).fetchall())

inserted = 0
skipped = 0
for row in missing:
    fid, ht, at, hs, aws, date_str, league, lc = row
    
    # Try mapping
    ht_mapped = mappings.get(ht.lower().strip(), ht)
    at_mapped = mappings.get(at.lower().strip(), at)
    
    try:
        conn.execute('''
            INSERT OR IGNORE INTO sofa_historical_results
            (id, home_team, away_team, home_score, away_score, tournament, date, status_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'finished')
        ''', (-fid - 1000000, ht_mapped, at_mapped, int(hs), int(aws), league, date_str))
        if conn.total_changes:
            inserted += 1
    except:
        skipped += 1

conn.commit()
total = conn.execute('SELECT COUNT(*) FROM sofa_historical_results').fetchone()[0]
conn.close()

print(f'Inserted: {inserted:,}')
print(f'Skipped: {skipped}')
print(f'Total DB now: {total:,}')
print(f'\nNEXT: Rebuild walkforward for new matches')
