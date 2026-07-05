"""Check sofa_historical_results schema and indexes"""
import sqlite3, sys
sys.path.insert(0, '.')
DB = 'scrape_cache.db'
conn = sqlite3.connect(DB)

# Get table schema
schema = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='sofa_historical_results'").fetchone()
print(f'Schema: {schema[0]}')

# Check constraints/triggers
triggers = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger' AND tbl_name='sofa_historical_results'").fetchall()
print(f'Triggers: {triggers}')

# Try inserting a test row
try:
    conn.execute("INSERT INTO sofa_historical_results (id, home_team, away_team, home_score, away_score, tournament, date, status_type) VALUES (-999999999, 'TEST_TEAM', 'TEST_TEAM2', 1, 1, 'TEST', '2000-01-01', 'finished')")
    conn.commit()
    print('Test insert SUCCEEDED')
    # Clean up
    conn.execute("DELETE FROM sofa_historical_results WHERE id = -999999999")
    conn.commit()
    print('Cleanup done')
except Exception as e:
    conn.rollback()
    print(f'Test insert FAILED: {e}')

conn.close()
