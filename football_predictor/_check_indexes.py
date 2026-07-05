"""Check what indexes exist on walkforward_state and create if needed"""
import sqlite3, os
DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
conn = sqlite3.connect(DB)
idx = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='walkforward_state'").fetchall()
if idx:
    print(f"Existing indexes on walkforward_state: {len(idx)}")
    for i in idx: print(f"  {i[0]}: {i[1]}")
else:
    print("NO INDEXES on walkforward_state! Creating...")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_wf_team_date ON walkforward_state(team_name, date)")
    conn.commit()
    print("Created idx_wf_team_date")

idx2 = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='sofa_historical_results'").fetchall()
if idx2:
    print(f"\nIndexes on sofa_historical_results:")
    for i in idx2: print(f"  {i[0]}: {i[1]}")
else:
    print("\nNO INDEXES on sofa_historical_results! Creating...")

idx3 = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='glicko_state'").fetchall()
print(f"\nIndexes on glicko_state: {[i[0] for i in idx3]}")
if not idx3:
    conn.execute("CREATE INDEX IF NOT EXISTS idx_glicko_team_date ON glicko_state(team_name, date)")
    conn.commit()
    print("Created idx_glicko_team_date")

conn.close()
print("Done")
