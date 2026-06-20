"""
Night Run — full pipeline for 8-hour overnight execution.
1. Backfill lineups until productive competitions exhausted
2. Rebuild Player Impact DB
3. Retrain Direct model
4. Save results
"""
import sys, os, time, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'football_predictor'))

LOG = []
def log(msg):
    ts = time.strftime('%H:%M:%S')
    print(f'[{ts}] {msg}')
    LOG.append(f'[{ts}] {msg}')

log('=== NIGHT RUN START ===')
log(f'Time: {time.strftime("%Y-%m-%d %H:%M:%S")}')
log(f'Python: {sys.version}')

from backfill import collect_lineups
import sqlite3

DB = 'football_predictor/scrape_cache.db'

# Phase 1: Backfill — run multiple batches until productive exhausted
batch_size = 500
total_batches = 0
max_batches = 60  # 500 * 60 = 30,000 max new this session

log(f'Phase 1: Lineups backfill (batches of {batch_size}, max {max_batches})')

for b in range(max_batches):
    prev = sqlite3.connect(DB).execute('SELECT COUNT(*) FROM sofa_lineups').fetchone()[0]
    if prev >= 55000:
        log(f'Target reached: {prev} lineups')
        break
    
    n = collect_lineups(limit_events=batch_size)
    total_batches += 1
    curr = sqlite3.connect(DB).execute('SELECT COUNT(*) FROM sofa_lineups').fetchone()[0]
    new_this_batch = curr - prev
    log(f'Batch {total_batches}: +{new_this_batch} new, {curr} total')
    
    # Check if hit rate dropped below 10% — means productive exhausted
    if new_this_batch < batch_size * 0.1 and b > 3:
        log(f'Low hit rate ({new_this_batch}/{batch_size}) — productive competitions probably exhausted')
        break
    
    if total_batches >= max_batches:
        log(f'Max batches ({max_batches}) reached')
        break

final_lineups = sqlite3.connect(DB).execute('SELECT COUNT(*) FROM sofa_lineups').fetchone()[0]
log(f'Phase 1 done: {final_lineups} total lineups')

# Phase 2: Rebuild Player Impact DB
log('Phase 2: Rebuilding Player Impact DB...')
from player_impact import build
build()
log('Phase 2 done')

# Phase 3: Retrain Direct model
log('Phase 3: Retraining Direct model...')
from direct_predictor import train, FEATURES
train(save=True)
log(f'Phase 3 done: {len(FEATURES)} features')

# Log results
with open('night_run_results.json', 'w') as f:
    json.dump({
        'lineups_before': 4804,
        'lineups_after': final_lineups,
        'batches_run': total_batches,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'features': len(FEATURES),
    }, f, indent=2)

log('=== NIGHT RUN COMPLETE ===')
print('\n'.join(LOG))
