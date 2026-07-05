"""Create composite indexes for fast walkforward lookups"""
import sqlite3, os, time
DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
conn = sqlite3.connect(DB)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=OFF")

t0 = time.time()
print("Creating idx_wf_team_date on walkforward_state(team_name, date)...")
conn.execute("CREATE INDEX IF NOT EXISTS idx_wf_team_date ON walkforward_state(team_name, date)")
conn.commit()
print(f"  Done in {time.time()-t0:.0f}s")

t0 = time.time()
print("Creating idx_glicko_team_date on glicko_state(team_name, date)...")
conn.execute("CREATE INDEX IF NOT EXISTS idx_glicko_team_date ON glicko_state(team_name, date)")
conn.commit()
print(f"  Done in {time.time()-t0:.0f}s")

conn.close()
print("Indexes created!")
