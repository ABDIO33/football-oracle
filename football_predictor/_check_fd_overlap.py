"""Check and integrate missing football-data.co.uk matches"""
import sqlite3, os
DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
conn = sqlite3.connect(DB)

# Check overlap properly using exact match on team names AND date
overlap = conn.execute('''
    SELECT COUNT(*) FROM football_data_matches f
    WHERE EXISTS (
        SELECT 1 FROM sofa_historical_results s
        WHERE s.date = f.date
        AND s.home_team = f.home_team
        AND s.away_team = f.away_team
    )
''').fetchone()[0]

total_fd = conn.execute('SELECT COUNT(*) FROM football_data_matches').fetchone()[0]
print(f'Football-data matches: {total_fd:,}')
print(f'Overlap with sofa (exact name+date match): {overlap:,}')
print(f'Not in sofa: {total_fd - overlap:,}')

# Check date range of sofa data
s_min = conn.execute('SELECT MIN(date) FROM sofa_historical_results').fetchone()[0]
s_max = conn.execute('SELECT MAX(date) FROM sofa_historical_results').fetchone()[0]
print(f'Sofa date range: {s_min} to {s_max}')

# Check football-data.co.uk date range
fd_min = conn.execute('SELECT MIN(date) FROM football_data_matches').fetchone()[0]
fd_max = conn.execute('SELECT MAX(date) FROM football_data_matches').fetchone()[0]
print(f'FD date range: {fd_min} to {fd_max}')

# Check how many FD teams have mappings
mapped_fd_teams = conn.execute('''
    SELECT COUNT(DISTINCT f.home_team) FROM football_data_matches f
    INNER JOIN team_name_mapping m 
    ON LOWER(f.home_team) = LOWER(m.fd_name)
    WHERE m.confidence >= 0.85
''').fetchone()[0]
total_fd_teams = conn.execute('SELECT COUNT(DISTINCT home_team) FROM football_data_matches').fetchone()[0]
print(f'FD teams with mappings: {mapped_fd_teams:,} / {total_fd_teams:,}')

conn.close()
