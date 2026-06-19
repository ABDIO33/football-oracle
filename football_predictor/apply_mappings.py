"""Apply clean mappings to team_name_mapping table, then re-run integration"""
import sys, os, json, sqlite3, pandas as pd

SD = r'C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor\soccer_dataset'
DB = r'C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor\scrape_cache.db'

print("="*60)
print("APPLY CLEAN MAPPINGS + RE-INTEGRATE")
print("="*60)

# 1. Load clean mappings
print("\n[1] Loading clean mappings...")
with open(os.path.join(os.path.dirname(__file__), 'clean_mappings.json'), 'r', encoding='utf-8') as f:
    clean_maps = json.load(f)
print(f"  Clean mappings: {len(clean_maps)}")

# 2. Insert into team_name_mapping
print("\n[2] Inserting into team_name_mapping...")
conn = sqlite3.connect(DB)
inserted = 0
skipped = 0
for sd_name, our_name in clean_maps.items():
    try:
        conn.execute('INSERT OR IGNORE INTO team_name_mapping (api_name, sofa_name) VALUES (?, ?)',
                     (sd_name, our_name))
        if conn.total_changes > 0:
            inserted += 1
        else:
            skipped += 1
    except Exception as e:
        skipped += 1
conn.commit()
print(f"  Inserted: {inserted}, Skipped: {skipped}")

# 3. Now run the integration script's core logic again
print("\n[3] Running re-integration...")
# Import and run the integration logic
sys.path.insert(0, os.path.dirname(__file__))
# Execute the integration script programmatically
exec(open(os.path.join(os.path.dirname(__file__), 'integrate_soccer_dataset.py')).read())

print("\n[4] Done! Summary:")
conn2 = sqlite3.connect(DB)
total = conn2.execute('SELECT COUNT(*) FROM sofa_historical_results').fetchone()[0]
walkforward = conn2.execute('SELECT COUNT(*) FROM walkforward_state').fetchone()[0]
conn2.close()
print(f"  Total DB matches: {total}")
print(f"  Walkforward snapshots: {walkforward}")
