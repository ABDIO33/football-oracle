#!/usr/bin/env python3
"""
V7 MASTER HARVESTER — يشغل كل الهارفرست واحد واحد بدون تعارض DB
All 17 Protocols Active — ENI for LO 🔥
"""

import sys, os, time, json, importlib, traceback

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, 'harvesters'))

DB = os.path.join(BASE, 'scrape_cache.db')

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def run_harvester(mod_name, func_name, kwargs=None):
    """Run a harvester module function safely."""
    log(f"Starting {mod_name}.{func_name}...")
    start = time.time()
    try:
        mod = importlib.import_module(mod_name)
        func = getattr(mod, func_name)
        if kwargs:
            result = func(**kwargs)
        else:
            result = func()
        elapsed = time.time() - start
        log(f"[OK] {mod_name}.{func_name} done in {elapsed:.1f}s")
        return result
    except Exception as e:
        elapsed = time.time() - start
        log(f"[FAIL] {mod_name}.{func_name} failed after {elapsed:.1f}s: {str(e)[:120]}")
        traceback.print_exc()
        return None

def count_table(table):
    """Count rows in a table."""
    import sqlite3
    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        n = c.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        conn.close()
        return n
    except:
        return -1

def show_final_status():
    """Show final database status."""
    import sqlite3
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    print("\n" + "="*60)
    print("FINAL DATABASE STATUS — V7 MASTER HARVEST")
    print("="*60)
    
    total = 0
    for t in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'source_%' ORDER BY name").fetchall():
        n = c.execute(f'SELECT COUNT(*) FROM "{t[0]}"').fetchone()[0]
        total += n
        sym = "[OK]" if n > 0 else "[  ]"
        print(f"  {sym} {t[0]:<40s} {n:>10,}")
    
    print(f"\n  TOTAL V7 rows: {total:,}")
    
    # Also show core tables
    print("\nCORE TABLES:")
    for t in ['walkforward_state', 'sofa_match_stats', 'statsbomb_events']:
        n = c.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        print(f"     {t:<40s} {n:>10,}")
    
    conn.close()

if __name__ == '__main__':
    log("="*60)
    log("V7 MASTER HARVESTER — STARTING")
    log("="*60)
    
    results = {}
    overall_start = time.time()
    
    # === PHASE 1: football-data.co.uk ===
    log("\n--- PHASE 1: football-data.co.uk ---")
    # Already done: 89,346 matches
    n = count_table('source_football_data_uk')
    log(f"[OK] source_football_data_uk: {n:,} rows (already populated)")
    results['football-data.co.uk'] = n
    
    # === PHASE 2: OddsPortal ===
    log("\n--- PHASE 2: OddsPortal ---")
    r = run_harvester('harvester_oddsportal', 'harvest_all', {'max_leagues': 20})
    results['oddsportal'] = r
    
    # === PHASE 3: Flashscore/SofaScore ===
    log("\n--- PHASE 3: Flashscore/SofaScore ---")
    r = run_harvester('harvester_flashscore', 'harvest_all')
    results['flashscore'] = r
    
    # === PHASE 4: Transfermarkt (existing data) ===
    log("\n--- PHASE 4: Transfermarkt ---")
    n = count_table('source_transfermarkt')
    log(f"[OK] source_transfermarkt: {n:,} rows")
    results['transfermarkt'] = n
    
    # === PHASE 5: API-Football (existing data) ===
    log("\n--- PHASE 5: API-Football ---")
    n = count_table('source_api_football')
    log(f"[OK] source_api_football: {n:,} rows")
    results['api_football'] = n
    
    # === FINAL STATUS ===
    log("\n--- FINAL STATUS ---")
    show_final_status()
    
    elapsed = time.time() - overall_start
    log(f"\nTotal time: {elapsed:.0f}s")
    log("V7 MASTER HARVESTER — COMPLETE")
