"""
Continue walkforward from 2024-12 to catch remaining matches
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from walkforward import WalkForwardProcessor, DB
import sqlite3

# Only clear progress AFTER the last processed state date
conn = sqlite3.connect(DB)
last_date = conn.execute('SELECT MAX(date) FROM walkforward_state').fetchone()[0]
print("Last walkforward state date:", last_date)

# Get IDs of matches AFTER this date that we need to process
remaining = conn.execute('''
    SELECT COUNT(*) FROM sofa_historical_results r
    WHERE r.status_type = 'finished' AND r.home_score IS NOT NULL AND r.away_score IS NOT NULL
    AND r.date > ?
    AND r.id NOT IN (SELECT event_id FROM walkforward_progress)
''', (last_date,)).fetchone()[0]

print(f"Remaining matches to process: {remaining}")

# Delete walkforward_progress for remaining matches ONLY
conn.execute('''
    DELETE FROM walkforward_progress WHERE event_id IN (
        SELECT r.id FROM sofa_historical_results r
        WHERE r.status_type = 'finished' AND r.home_score IS NOT NULL AND r.away_score IS NOT NULL
        AND r.date > ?
    )
''', (last_date,))
conn.commit()

deleted = conn.total_changes
conn.close()
print(f"Cleared progress for {deleted} remaining matches")

# Run walkforward from the last date
print("\nProcessing remaining matches...")
wf = WalkForwardProcessor()
# Start from last_date minus a buffer
from datetime import datetime, timedelta
start = (datetime.strptime(last_date, '%Y-%m-%d') - timedelta(days=30)).strftime('%Y-%m-%d')
processed = wf.run_historical(start_date=start)
wf.close()

conn2 = sqlite3.connect(DB)
total_snapshots = conn2.execute('SELECT COUNT(*) FROM walkforward_state').fetchone()[0]
total_progress = conn2.execute('SELECT COUNT(*) FROM walkforward_progress').fetchone()[0]
min_d = conn2.execute('SELECT MIN(date) FROM walkforward_state').fetchone()[0]
max_d = conn2.execute('SELECT MAX(date) FROM walkforward_state').fetchone()[0]
conn2.close()

print(f"\nResults: {total_snapshots} snapshots")
print(f"Dates: {min_d} to {max_d}")
print(f"Progress: {total_progress}")
print("DONE")
