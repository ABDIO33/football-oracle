"""
rebuild_walkforward.py — Reset and rebuild walkforward state from scratch
Processes ALL matches chronologically (2012-2026) with zero lookahead
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from walkforward import WalkForwardProcessor, DB
import sqlite3

print("="*60)
print("REBUILD WALKFORWARD FROM SCRATCH")
print("="*60)

# 1. Check current state
conn = sqlite3.connect(DB)
old_count = conn.execute('SELECT COUNT(*) FROM walkforward_state').fetchone()[0]
old_teams = conn.execute('SELECT COUNT(DISTINCT team_name) FROM walkforward_state').fetchone()[0]
print(f"Current: {old_count} snapshots for {old_teams} teams")

# 2. Clear state and progress tables (full reset)
print("\nResetting walkforward state...")
conn.execute('DELETE FROM walkforward_state')
conn.execute('DELETE FROM walkforward_progress')
conn.commit()
conn.close()
print("  walkforward_state and walkforward_progress cleared")

# 3. Process ALL matches chronologically
print("\nProcessing ALL matches from 2012-2026...")
wf = WalkForwardProcessor()
processed = wf.run_historical()
wf.close()

# 4. Verify
conn2 = sqlite3.connect(DB)
new_count = conn2.execute('SELECT COUNT(*) FROM walkforward_state').fetchone()[0]
new_teams = conn2.execute('SELECT COUNT(DISTINCT team_name) FROM walkforward_state').fetchone()[0]
conn2.close()

print(f"\nNew: {new_count} snapshots for {new_teams} teams")
print(f"Total matches processed: {processed}")
print("WALKFORWARD REBUILD COMPLETE")
