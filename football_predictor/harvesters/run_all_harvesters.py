#!/usr/bin/env python3
"""
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
▓    RUN ALL HARVESTERS — Unified Launcher (sync + async)                    ▓
▓    SHADOWHACKER-GOD • DΞMON CORE v9999999 • WORM-AI💀🔥                    ▓
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
"""
import asyncio
import importlib
import json
import os
import sys
import time
import traceback

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARVESTERS_DIR = os.path.join(PROJECT_ROOT, 'harvesters')
sys.path.insert(0, HARVESTERS_DIR)

os.chdir(PROJECT_ROOT)
os.makedirs(os.path.join(HARVESTERS_DIR, 'harvest_logs'), exist_ok=True)

REPORT_PATH = os.path.join(HARVESTERS_DIR, 'harvest_logs', 'harvest_report.json')

def log(msg, level='INFO'):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] [{level}] {msg}'
    print(line)
    with open(REPORT_PATH.replace('.json', '.log'), 'a') as f:
        f.write(line + '\n')

HARVESTER_CONFIGS = [
    # (module_name, function_name, is_async, args, timeout_seconds)
    ('harvester_football_data_uk', 'harvest_recent_seasons', True, {'years_back': 3}, 120),
    ('harvester_understat', 'harvest_all', False, {'force_refresh': False}, 90),
    ('harvester_fbref', 'harvest_all', False, {'force_refresh': False, 'max_leagues': 5}, 90),
    ('harvester_transfermarkt', 'harvest_all', False, {'force_refresh': False, 'max_leagues': 5}, 90),
    ('harvester_betfair_odds', 'harvest_live_markets', False, {}, 60),
    ('harvester_oddsportal', 'harvest_all', False, {'force_refresh': False, 'max_leagues': 5}, 90),
    ('harvester_weather', 'harvest_all_historical', False, {'limit': 500}, 90),
    ('harvester_flashscore', 'harvest_all', False, {'force_refresh': False, 'max_leagues': 5}, 90),
]

def run_sync(func, kwargs, timeout):
    """Run a synchronous function with timeout."""
    import multiprocessing
    queue = multiprocessing.Queue()
    
    def target(q, fn_name, kw):
        try:
            mod_name, func_name = fn_name.rsplit('.', 1)
            mod = importlib.import_module(mod_name)
            fn = getattr(mod, func_name)
            result = fn(**kw)
            q.put(('success', result))
        except Exception as e:
            q.put(('error', f'{type(e).__name__}: {e}'))
    
    # Import the module first
    mod = importlib.import_module(func.__module__)
    fn = getattr(mod, func.__name__)
    result = fn(**kwargs)
    return result

async def run_async(func, kwargs, timeout):
    """Run an async function."""
    result = await func(**kwargs)
    return result

def main():
    results = {}
    
    for module_name, func_name, is_async, kwargs, timeout in HARVESTER_CONFIGS:
        print(f'\n{"="*70}')
        print(f'🔥 FIRING: {module_name}.{func_name}()')
        print(f'{"="*70}')
        
        start = time.time()
        harvester_result = None
        error = None
        
        try:
            # Import the module
            spec = importlib.util.spec_from_file_location(
                module_name, 
                os.path.join(HARVESTERS_DIR, f'{module_name}.py')
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            fn = getattr(mod, func_name)
            
            if is_async:
                # Run async function with asyncio
                harvester_result = asyncio.run(
                    asyncio.wait_for(fn(**kwargs), timeout=timeout)
                )
            else:
                # Run sync function
                harvester_result = fn(**kwargs)
                
            elapsed = time.time() - start
            log(f'✅ {module_name} completed in {elapsed:.1f}s')
            
        except asyncio.TimeoutError:
            elapsed = time.time() - start
            error = f'TIMEOUT after {timeout}s'
            log(f'❌ {module_name} TIMEOUT after {elapsed:.1f}s', 'ERROR')
        except Exception as e:
            elapsed = time.time() - start
            error = f'{type(e).__name__}: {str(e)[:300]}'
            log(f'❌ {module_name} FAILED: {error}', 'ERROR')
            traceback.print_exc()
        
        results[module_name] = {
            'function': func_name,
            'is_async': is_async,
            'timeout': timeout,
            'elapsed': round(time.time() - start, 1),
            'error': error,
            'result': harvester_result,
        }
        
        # Print summary of result
        if harvester_result:
            if isinstance(harvester_result, dict):
                print(f'📊 Result keys: {list(harvester_result.keys())[:10]}')
                for k, v in list(harvester_result.items())[:5]:
                    if isinstance(v, (int, float, str)):
                        print(f'   {k}: {v}')
                    elif isinstance(v, (list, tuple)):
                        print(f'   {k}: {len(v)} items')
                    elif isinstance(v, dict):
                        print(f'   {k}: {len(v)} keys')
                    else:
                        print(f'   {k}: {type(v).__name__}')
            elif isinstance(harvester_result, (int, float, str)):
                print(f'📊 Result: {harvester_result}')
            elif harvester_result is None:
                print(f'📊 Result: None')
            else:
                print(f'📊 Result type: {type(harvester_result).__name__}')
        
        if error:
            print(f'💥 ERROR: {error}')
    
    # Save report
    report = {
        'timestamp': time.time(),
        'total_sources': len(results),
        'successful': sum(1 for r in results.values() if not r['error']),
        'failed': sum(1 for r in results.values() if r['error']),
        'results': results,
    }
    
    with open(REPORT_PATH, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f'\n{"="*70}')
    print(f'📋 HARVEST SUMMARY')
    print(f'{"="*70}')
    print(f'Total sources: {report["total_sources"]}')
    print(f'✅ Successful: {report["successful"]}')
    print(f'❌ Failed: {report["failed"]}')
    print(f'\nReport saved to: {REPORT_PATH}')
    
    return report

if __name__ == '__main__':
    main()
