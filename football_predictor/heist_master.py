#!/usr/bin/env python3
"""
███╗   ███╗ █████╗ ███████╗████████╗███████╗██████╗ 
████╗ ████║██╔══██╗██╔════╝╚══██╔══╝██╔════╝██╔══██╗
██╔████╔██║███████║███████╗   ██║   █████╗  ██████╔╝
██║╚██╔╝██║██╔══██║╚════██║   ██║   ██╔══╝  ██╔══██╗
██║ ╚═╝ ██║██║  ██║███████║   ██║   ███████╗██║  ██║
╚═╝     ╚═╝╚═╝  ╚═╝╚══════╝   ╚═╝   ╚══════╝╚═╝  ╚═╝

SHADOW HEIST MASTER ORCHESTRATOR
All 4 sources: FotMob → Transfermarkt → Understat → FBref
SHADOWHACKER-GOD • DΞMON CORE v9999999 • SHΔDØW.EXE • Specter 0x13
"""

import os, json, time, sys, subprocess, importlib
from datetime import datetime, timezone
from typing import Dict, List, Optional

HEIST_DIR = os.path.join(os.path.dirname(__file__), 'heist_output')
os.makedirs(HEIST_DIR, exist_ok=True)

DB_PATH = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')


def log(msg: str):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}')


def fmt_bytes(b: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if b < 1024:
            return f'{b:.1f} {unit}'
        b /= 1024
    return f'{b:.1f} TB'


def get_dataset_stats() -> Dict:
    """Get current dataset statistics."""
    stats = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'heist_output': {},
        'sofascore_data': {},
        'total_matches_estimate': 0,
    }
    
    # Check scrape_cache.db for SofaScore data
    try:
        import sqlite3
        conn = sqlite3.connect(DB_PATH, timeout=10)
        
        # SofaScore match count
        try:
            cnt = conn.execute('SELECT COUNT(*) FROM sofa_historical_results').fetchone()[0]
            stats['sofascore_data']['matches'] = cnt
            stats['total_matches_estimate'] += cnt
        except:
            stats['sofascore_data']['matches'] = 0
        
        # SofaScore stats
        try:
            cnt = conn.execute('SELECT COUNT(*) FROM sofa_match_stats').fetchone()[0]
            stats['sofascore_data']['detailed_stats'] = cnt
        except:
            stats['sofascore_data']['detailed_stats'] = 0
        
        # SofaScore lineups
        try:
            cnt = conn.execute('SELECT COUNT(*) FROM sofa_lineups').fetchone()[0]
            stats['sofascore_data']['lineups'] = cnt
        except:
            stats['sofascore_data']['lineups'] = 0
        
        # Walkforward state
        try:
            cnt = conn.execute('SELECT COUNT(*) FROM walkforward_state').fetchone()[0]
            stats['sofascore_data']['training_features'] = cnt
        except:
            stats['sofascore_data']['training_features'] = 0
        
        conn.close()
    except Exception as e:
        stats['error'] = str(e)
    
    # Check heist_output directory
    if os.path.exists(HEIST_DIR):
        total_files = 0
        total_size = 0
        groups = {}
        
        for root, dirs, files in os.walk(HEIST_DIR):
            for f in files:
                fpath = os.path.join(root, f)
                size = os.path.getsize(fpath)
                total_files += 1
                total_size += size
                
                # Group by source
                source = 'other'
                for src in ['fotmob', 'transfermarkt', 'understat', 'fbref']:
                    if src in f.lower():
                        source = src
                        break
                
                if source not in groups:
                    groups[source] = {'files': 0, 'size': 0}
                groups[source]['files'] += 1
                groups[source]['size'] += size
        
        stats['heist_output'] = {
            'total_files': total_files,
            'total_size': total_size,
            'total_size_str': fmt_bytes(total_size),
            'groups': {k: {'files': v['files'], 'size_str': fmt_bytes(v['size'])} 
                      for k, v in groups.items()},
        }
    
    # Heist DB tables
    try:
        import sqlite3
        conn = sqlite3.connect(DB_PATH, timeout=10)
        
        heist_tables = [
            ('fotmob_match_cache', 'FotMob Match Cache'),
            ('fotmob_league_cache', 'FotMob League Cache'),
            ('fotmob_heist_progress', 'FotMob Progress'),
            ('agent5_heist_clubs', 'Transfermarkt Clubs'),
            ('agent5_heist_squad', 'Transfermarkt Squads'),
            ('agent5_heist_injuries', 'Transfermarkt Injuries'),
            ('agent5_heist_market_values', 'Transfermarkt Values'),
            ('heist_files', 'Heist File Registry'),
        ]
        
        for table_name, label in heist_tables:
            try:
                cnt = conn.execute(f'SELECT COUNT(*) FROM {table_name}').fetchone()[0]
                stats['heist_output'][label] = cnt
            except:
                pass
        
        conn.close()
    except:
        pass
    
    return stats


def print_banner():
    banner = r"""
╔══════════════════════════════════════════════════════════════╗
║         🔥  SHADOW HEIST MASTER ORCHESTRATOR  🔥           ║
║                                                              ║
║   ╔═══╗╔═══╗╔═══╗╔═══╗╔════╗╔═══╗╔═══╗╔═══╗╔═══╗╔═╗╔═╗   ║
║   ║╔═╗║║╔══╝║╔═╗║║╔═╗║║╔╗╔╗║║╔═╗║║╔═╗║║╔═╗║║╔══╝║║╚╝║║   ║
║   ║╚═╝║║╚══╗║╚═╝║║╚═╝║╚╝║║╚╝║╚═╝║║║ ║║║╚═╝║║╚══╗║╔╗╔╗║   ║
║   ║╔╗╔╝║╔══╝║╔╗╔╝║╔╗╔╝  ║║  ║╔╗╔╝║╚═╝║║╔╗╔╝║╔══╝║║║║║║   ║
║   ║║║╚╗║╚══╗║║║╚╗║║║╚╗  ║║  ║║║╚╗║╔═╗║║║║╚╗║╚══╗║║║║║║   ║
║   ╚╝╚═╝╚═══╝╚╝╚═╝╚╝╚═╝  ╚╝  ╚╝╚═╝╚╝ ╚╝╚╝╚═╝╚═══╝╚╝╚╝╚╝   ║
║                                                              ║
║   Sources: FotMob • Transfermarkt • Understat • FBref       ║
║   Target: 5,000,000+ matches                                ║
║   Output: heist_output/                                      ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)


def run_heist_module(module_name: str, func_name: str, *args, **kwargs):
    """Run a heist module function and capture results."""
    log(f'🚀 Loading {module_name}...')
    try:
        mod = importlib.import_module(module_name)
        func = getattr(mod, func_name)
        log(f'⚡ Executing {func_name}...')
        result = func(*args, **kwargs)
        log(f'✅ {func_name} complete')
        return result
    except Exception as e:
        log(f'❌ {func_name} FAILED: {str(e)}')
        return None


def run_heist_script(script_name: str, args: str = ''):
    """Run a heist script as subprocess."""
    log(f'🚀 Running {script_name}...')
    cmd = f'python "{os.path.join(os.path.dirname(__file__), script_name)}" {args}'
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=3600)
        log(f'✅ {script_name} exit code: {result.returncode}')
        if result.stdout:
            print(result.stdout[-2000:])  # Last 2000 chars
        if result.stderr:
            print(f'STDERR: {result.stderr[-1000:]}')
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        log(f'⏰ {script_name} timed out')
        return False
    except Exception as e:
        log(f'❌ {script_name} FAILED: {str(e)}')
        return False


def validate_environment() -> bool:
    """Validate all required packages are available."""
    required = ['curl_cffi', 'bs4', 'lxml', 'json', 'sqlite3']
    missing = []
    
    for pkg in required:
        try:
            if pkg == 'bs4':
                import bs4
            elif pkg == 'curl_cffi':
                from curl_cffi import requests
            elif pkg == 'lxml':
                import lxml
            else:
                importlib.import_module(pkg)
        except ImportError:
            missing.append(pkg)
    
    if missing:
        log(f'❌ Missing packages: {missing}')
        log('📦 Install: pip install curl_cffi beautifulsoup4 lxml')
        return False
    
    log('✅ Environment check passed')
    return True


def phase1_fotmob():
    """Phase 1: FotMob data heist."""
    log('\n' + '=' * 60)
    log('📡 PHASE 1: FOTMOB BULK HEIST')
    log('=' * 60)
    return run_heist_script('heist_fotmob_bulk.py')


def phase2_transfermarkt():
    """Phase 2: Transfermarkt data heist."""
    log('\n' + '=' * 60)
    log('💰 PHASE 2: TRANSFERMARKT BULK HEIST')
    log('=' * 60)
    return run_heist_script('heist_transfermarkt_bulk.py')


def phase3_understat():
    """Phase 3: Understat data heist."""
    log('\n' + '=' * 60)
    log('🎯 PHASE 3: UNDERSTAT BULK HEIST')
    log('=' * 60)
    return run_heist_script('heist_understat_bulk.py')


def phase4_fbref():
    """Phase 4: FBref data heist."""
    log('\n' + '=' * 60)
    log('📊 PHASE 4: FBREF BULK HEIST')
    log('=' * 60)
    return run_heist_script('heist_fbref_bulk.py')


def run_full_heist(phases: List[str] = None):
    """Run the full multi-source heist."""
    print_banner()
    
    # Validate environment
    if not validate_environment():
        return
    
    # Check current stats
    log('📊 Pre-heist dataset stats:')
    pre_stats = get_dataset_stats()
    print(json.dumps(pre_stats, indent=2))
    
    # Define phases
    all_phases = {
        'fotmob': ('FotMob', phase1_fotmob),
        'transfermarkt': ('Transfermarkt', phase2_transfermarkt),
        'understat': ('Understat', phase3_understat),
        'fbref': ('FBref', phase4_fbref),
    }
    
    if phases:
        selected = {k: v for k, v in all_phases.items() if k in phases}
    else:
        selected = all_phases
    
    total_start = time.time()
    phase_results = {}
    
    # Run phases sequentially
    for phase_key, (phase_name, phase_func) in selected.items():
        phase_start = time.time()
        log(f'\n🔥 STARTING {phase_name.upper()} PHASE')
        
        success = phase_func()
        
        elapsed = time.time() - phase_start
        phase_results[phase_key] = {
            'name': phase_name,
            'success': success,
            'elapsed_seconds': round(elapsed, 1),
        }
        log(f'⏱️ {phase_name} took {elapsed/60:.1f} minutes')
    
    total_elapsed = time.time() - total_start
    
    # Final report
    log('\n' + '=' * 60)
    log('🔥🔥🔥 SHADOW HEIST COMPLETE 🔥🔥🔥')
    log('=' * 60)
    
    for key, result in phase_results.items():
        status = '✅' if result['success'] else '❌'
        log(f'  {status} {result["name"]}: {result["elapsed_seconds"]}s')
    
    log(f'\n⏱️ Total time: {total_elapsed/60:.1f} minutes')
    
    # Post-heist stats
    log('\n📊 Post-heist dataset stats:')
    post_stats = get_dataset_stats()
    print(json.dumps(post_stats, indent=2))
    
    # Save report
    report = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'total_elapsed': total_elapsed,
        'phases': phase_results,
        'pre_stats': pre_stats,
        'post_stats': post_stats,
    }
    
    report_path = os.path.join(HEIST_DIR, 'heist_report.json')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    log(f'📄 Report saved to {report_path}')
    
    return report


def show_status():
    """Show current heist status."""
    print_banner()
    stats = get_dataset_stats()
    print(json.dumps(stats, indent=2, default=str))


def quick_test():
    """Run quick tests on all sources."""
    print('🔥 QUICK TEST — ALL SOURCES')
    print('=' * 60)
    
    from curl_cffi import requests
    
    tests = [
        ('FotMob Premier League', 'https://www.fotmob.com/leagues/47'),
        ('Transfermarkt Premier League', 'https://www.transfermarkt.com/premier-league/startseite/wettbewerb/GB1'),
        ('Understat', 'https://understat.com/'),
        ('FBref', 'https://fbref.com/en/'),
    ]
    
    for name, url in tests:
        try:
            r = requests.get(url, impersonate='chrome120', timeout=15)
            status = '✅' if r.status_code == 200 else '⚠️'
            print(f'  {status} {name}: HTTP {r.status_code} ({len(r.text)} bytes)')
        except Exception as e:
            print(f'  ❌ {name}: {str(e)[:60]}')


def consolidate_heist_data():
    """Consolidate all heist data into a single unified dataset."""
    print('🔄 Consolidating heist data...')
    
    all_data = []
    sources = {}
    
    if os.path.exists(HEIST_DIR):
        for root, dirs, files in os.walk(HEIST_DIR):
            for f in files:
                if f.endswith('.jsonl'):
                    fpath = os.path.join(root, f)
                    try:
                        with open(fpath, 'r', encoding='utf-8') as fh:
                            for line in fh:
                                try:
                                    record = json.loads(line)
                                    all_data.append(record)
                                except:
                                    pass
                    except:
                        pass
    
    log(f'Total records: {len(all_data)}')
    
    # Save consolidated
    consolidated_path = os.path.join(HEIST_DIR, 'consolidated.jsonl')
    with open(consolidated_path, 'w', encoding='utf-8') as f:
        for record in all_data:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + '\n')
    
    log(f'Consolidated file: {consolidated_path}')
    return len(all_data)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        
        if cmd == 'status':
            show_status()
        elif cmd == 'test':
            quick_test()
        elif cmd == 'consolidate':
            consolidate_heist_data()
        elif cmd in ['fotmob', 'transfermarkt', 'understat', 'fbref']:
            run_full_heist([cmd])
        elif cmd == 'phase1':
            phase1_fotmob()
        elif cmd == 'phase2':
            phase2_transfermarkt()
        elif cmd == 'phase3':
            phase3_understat()
        elif cmd == 'phase4':
            phase4_fbref()
        else:
            print(f'Unknown command: {cmd}')
            print('Commands: status, test, consolidate, fotmob, transfermarkt, understat, fbref')
    else:
        # Run full heist
        run_full_heist()
