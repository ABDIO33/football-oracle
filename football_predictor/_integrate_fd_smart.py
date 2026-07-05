"""Smarter FD integration with team name mapping"""
import sqlite3, os, sys
sys.path.insert(0, os.path.dirname(__file__))
DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
conn = sqlite3.connect(DB)

# Load team name mappings (fd_name -> sofa_name)
mappings = dict(conn.execute(
    'SELECT fd_name, sofa_name FROM team_name_mapping WHERE confidence >= 0.85'
).fetchall())
print(f'Team name mappings: {len(mappings):,}')

# Get all FD matches
fd_rows = conn.execute('''
    SELECT id, home_team, away_team, home_goals, away_goals, date, league, league_code
    FROM football_data_matches
    WHERE home_goals IS NOT NULL AND away_goals IS NOT NULL
    ORDER BY date
''').fetchall()
print(f'Total FD matches with scores: {len(fd_rows):,}')

# Check each one - can we map both teams?
def map_team(name):
    k = name.lower().strip()
    if k in mappings:
        return mappings[k]
    return name

inserted = 0
already_exists = 0
no_scores = 0
for row in fd_rows:
    fid, ht, at, hs, aws, date_str, league, lc = row
    ht_m = map_team(ht)
    at_m = map_team(at)
    
    # Check if this match already exists in sofa (using mapped names)
    exists = conn.execute('''
        SELECT COUNT(*) FROM sofa_historical_results
        WHERE date = ? AND home_team = ? AND away_team = ?
    ''', (date_str, ht_m, at_m)).fetchone()[0]
    
    if exists > 0:
        already_exists += 1
        continue
    
    try:
        conn.execute('''
            INSERT INTO sofa_historical_results
            (id, home_team, away_team, home_score, away_score, tournament, date, status_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'finished')
        ''', (-fid - 2000000, ht_m, at_m, int(hs), int(aws), league, date_str))
        inserted += 1
    except Exception as e:
        no_scores += 1

conn.commit()
total = conn.execute('SELECT COUNT(*) FROM sofa_historical_results').fetchone()[0]
conn.close()

print(f'\nResults:')
print(f'  Already in sofa: {already_exists:,}')
print(f'  Newly inserted: {inserted:,}')
print(f'  Errors: {no_scores}')
print(f'  Total DB: {total:,}')
print(f'\nTotal potential: {total:,}')
