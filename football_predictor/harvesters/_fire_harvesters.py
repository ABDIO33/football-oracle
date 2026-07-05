#!/usr/bin/env python3
"""
FIRE ALL HARVESTERS ONE BY ONE — Proper async handling for football-data-uk
"""
import asyncio
import importlib.util
import json
import os
import sys
import time
import traceback

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARVESTERS = os.path.join(PROJECT_ROOT, 'harvesters')
sys.path.insert(0, HARVESTERS)
os.chdir(PROJECT_ROOT)

def import_module(name):
    path = os.path.join(HARVESTERS, f'{name}.py')
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

results = {}

# ─── 1. FOOTBALL-DATA-UK (async - needs special handling) ───
print('='*60)
print('[1/8] football-data.co.uk harvester (async)')
print('='*60)
results['football_data_uk'] = {'source': 'football-data.co.uk', 'status': 'RUNNING'}
try:
    mod = import_module('harvester_football_data_uk')
    # Patch the module to properly use asyncio
    import types
    # Create a sync wrapper
    async def run_harvest():
        result = await mod.harvest_all(checkpoint=True, force_refresh=False)
        return result
    result = asyncio.run(run_harvest())
    rows = result.get('total_rows', result.get('matches', 0))
    errors = result.get('errors', 0)
    print(f'  + Completed. Rows: {rows}, Errors: {errors}')
    results['football_data_uk'] = {'source': 'football-data.co.uk', 'status': 'SUCCESS', 'rows': rows, 'errors': errors, 'result_keys': list(result.keys())[:10]}
except Exception as e:
    tb = traceback.format_exc()
    print(f'  - FAILED: {e}')
    results['football_data_uk'] = {'source': 'football-data.co.uk', 'status': 'FAILED', 'error': str(e)[:300], 'traceback': tb[-500:]}
sys.stdout.flush()

# ─── 2. UNDERSTAT ───
print('='*60)
print('[2/8] Understat xG harvester')
print('='*60)
results['understat'] = {'source': 'Understat', 'status': 'RUNNING'}
try:
    mod = import_module('harvester_understat')
    result = mod.harvest_all(force_refresh=False)
    print(f'  + Completed: matches={result.get("matches",0)}, shots={result.get("shots",0)}, errors={result.get("errors",0)}')
    results['understat'] = {'source': 'Understat', 'status': 'SUCCESS', 'matches': result.get('matches',0), 'shots': result.get('shots',0), 'errors': result.get('errors',0)}
except Exception as e:
    tb = traceback.format_exc()
    print(f'  - FAILED: {e}')
    results['understat'] = {'source': 'Understat', 'status': 'FAILED', 'error': str(e)[:300]}
sys.stdout.flush()

# ─── 3. FBREF ───
print('='*60)
print('[3/8] FBref advanced stats harvester')
print('='*60)
results['fbref'] = {'source': 'FBref', 'status': 'RUNNING'}
try:
    mod = import_module('harvester_fbref')
    result = mod.harvest_all(force_refresh=False, max_leagues=5)
    print(f'  + Completed: {json.dumps({k: str(v)[:80] for k, v in result.items()}, indent=2)}')
    results['fbref'] = {'source': 'FBref', 'status': 'SUCCESS', 'result': str(result)[:200]}
except Exception as e:
    tb = traceback.format_exc()
    print(f'  - FAILED: {e}')
    results['fbref'] = {'source': 'FBref', 'status': 'FAILED', 'error': str(e)[:300]}
sys.stdout.flush()

# ─── 4. TRANSFERMARKT ───
print('='*60)
print('[4/8] Transfermarkt data harvester')
print('='*60)
results['transfermarkt'] = {'source': 'Transfermarkt', 'status': 'RUNNING'}
try:
    mod = import_module('harvester_transfermarkt')
    result = mod.harvest_all(force_refresh=False, max_leagues=5)
    print(f'  + Completed: {json.dumps({k: str(v)[:80] for k, v in result.items()}, indent=2)}')
    results['transfermarkt'] = {'source': 'Transfermarkt', 'status': 'SUCCESS', 'result': str(result)[:200]}
except Exception as e:
    tb = traceback.format_exc()
    print(f'  - FAILED: {e}')
    results['transfermarkt'] = {'source': 'Transfermarkt', 'status': 'FAILED', 'error': str(e)[:300]}
sys.stdout.flush()

# ─── 5. BETFAIR ───
print('='*60)
print('[5/8] Betfair Exchange odds harvester')
print('='*60)
results['betfair'] = {'source': 'Betfair', 'status': 'RUNNING'}
try:
    mod = import_module('harvester_betfair_odds')
    result = mod.harvest_live_markets()
    print(f'  + Completed: {json.dumps({k: str(v)[:80] for k, v in result.items()}, indent=2)}')
    results['betfair'] = {'source': 'Betfair', 'status': 'SUCCESS', 'result': str(result)[:200]}
except Exception as e:
    tb = traceback.format_exc()
    print(f'  - FAILED: {e}')
    results['betfair'] = {'source': 'Betfair', 'status': 'FAILED', 'error': str(e)[:300]}
sys.stdout.flush()

# ─── 6. ODDS PORTAL ───
print('='*60)
print('[6/8] OddsPortal odds movement harvester')
print('='*60)
results['oddsportal'] = {'source': 'OddsPortal', 'status': 'RUNNING'}
try:
    mod = import_module('harvester_oddsportal')
    result = mod.harvest_all(force_refresh=False, max_leagues=5)
    print(f'  + Completed: {json.dumps({k: str(v)[:80] for k, v in result.items()}, indent=2)}')
    results['oddsportal'] = {'source': 'OddsPortal', 'status': 'SUCCESS', 'result': str(result)[:200]}
except Exception as e:
    tb = traceback.format_exc()
    print(f'  - FAILED: {e}')
    results['oddsportal'] = {'source': 'OddsPortal', 'status': 'FAILED', 'error': str(e)[:300]}
sys.stdout.flush()

# ─── 7. WEATHER ───
print('='*60)
print('[7/8] Weather data harvester')
print('='*60)
results['weather'] = {'source': 'Weather (OpenWeatherMap)', 'status': 'RUNNING'}
try:
    mod = import_module('harvester_weather')
    result = mod.harvest_all_historical(limit=500)
    print(f'  + Completed: {json.dumps({k: str(v)[:80] for k, v in result.items()}, indent=2)}')
    results['weather'] = {'source': 'Weather', 'status': 'SUCCESS', 'result': str(result)[:200]}
except Exception as e:
    tb = traceback.format_exc()
    print(f'  - FAILED: {e}')
    results['weather'] = {'source': 'Weather', 'status': 'FAILED', 'error': str(e)[:300]}
sys.stdout.flush()

# ─── 8. FLASHSCORE ───
print('='*60)
print('[8/8] Flashscore data harvester')
print('='*60)
results['flashscore'] = {'source': 'Flashscore', 'status': 'RUNNING'}
try:
    mod = import_module('harvester_flashscore')
    result = mod.harvest_all(force_refresh=False, max_leagues=5)
    print(f'  + Completed: {json.dumps({k: str(v)[:80] for k, v in result.items()}, indent=2)}')
    results['flashscore'] = {'source': 'Flashscore', 'status': 'SUCCESS', 'result': str(result)[:200]}
except Exception as e:
    tb = traceback.format_exc()
    print(f'  - FAILED: {e}')
    results['flashscore'] = {'source': 'Flashscore', 'status': 'FAILED', 'error': str(e)[:300]}
sys.stdout.flush()

# ─── SUMMARY ───
print('\n' + '='*60)
print('HARVEST SUMMARY')
print('='*60)
success = sum(1 for r in results.values() if r['status'] == 'SUCCESS' or r['status'] == 'RUNNING')
failed = sum(1 for r in results.values() if r['status'] == 'FAILED')
print(f'Total: {len(results)} | SUCCESS: {success} | FAILED: {failed}')
for name, r in results.items():
    status_icon = '+' if r['status'] in ('SUCCESS','RUNNING') else '-'
    print(f'  {status_icon} {r["source"]}: {r["status"]}')
    if r.get('error'):
        print(f'     Error: {r["error"]}')

report_path = os.path.join(HARVESTERS, 'harvest_logs', 'harvest_report.json')
os.makedirs(os.path.dirname(report_path), exist_ok=True)
with open(report_path, 'w') as f:
    json.dump(results, f, indent=2, default=str)
print(f'\nReport: {report_path}')
