import os, time, json

BASE = os.path.join(os.path.dirname(__file__), 'models')

def get_last_line(path):
    try:
        lines = open(path, errors='replace').read().strip().split('\n')
        return lines[-1][:80] if lines else 'empty'
    except Exception as e:
        return str(e)[:60]

def get_file_mtime(path):
    try:
        return time.strftime('%H:%M', time.localtime(os.path.getmtime(path)))
    except:
        return '?'

log_f = open(os.path.join(BASE, 'monitor_log.txt'), 'w')

for cycle in range(999):
    t = time.strftime('%H:%M:%S')
    
    v3_last = get_last_line(os.path.join(BASE, 'v3_log.txt'))
    p2_last = get_last_line(os.path.join(BASE, 'checkpointed_log.txt'))
    
    has_ultimate = os.path.exists(os.path.join(BASE, 'ultimate_results.json'))
    has_super = os.path.exists(os.path.join(BASE, 'super_ensemble_results.json'))
    has_v3_final = os.path.exists(os.path.join(BASE, 'v3_results.json'))
    
    v3_mtime = get_file_mtime(os.path.join(BASE, 'v3_log.txt'))
    p2_mtime = get_file_mtime(os.path.join(BASE, 'checkpointed_log.txt'))
    
    summary = f'[{t}] V3:{v3_mtime} P2:{p2_mtime} Ult={has_ultimate} Sup={has_super} V3R={has_v3_final}'
    print(summary)
    log_f.write(summary + '\n')
    log_f.flush()
    
    # Print latest logs periodically
    if cycle % 3 == 0:
        print('  V3: ' + v3_last)
        print('  P2: ' + p2_last)
    
    # Check if Phase 2 ultimate completed
    if has_ultimate and cycle > 0 and cycle % 3 == 0:
        try:
            r = json.load(open(os.path.join(BASE, 'ultimate_results.json')))
            e = r.get('ensemble', {})
            print(f'  >> P2 ENSEMBLE: {e.get("exact_pct","?")}% exact')
        except:
            pass
    
    if has_v3_final:
        try:
            r = json.load(open(os.path.join(BASE, 'v3_results.json')))
            e = r.get('ensemble', {})
            bt = r.get('betting_30', {})
            print(f'>> V3 ENSEMBLE: {e.get("exact_pct","?")}% exact')
            print(f'>> V3 Betting: {bt.get("accuracy_pct","?")}% @30%')
            
            # Compare with ultimate
            if has_ultimate:
                ult = json.load(open(os.path.join(BASE, 'ultimate_results.json')))
                u_ens = ult.get('ensemble', {})
                diff = e.get('exact_pct', 0) - u_ens.get('exact_pct', 0)
                print(f'>> Improvement over Ultimate: {diff:+.2f}pp')
        except Exception as ex:
            print(f'Error reading V3 results: {ex}')
        break
    
    time.sleep(600)  # Every 10 min

log_f.write('MONITOR COMPLETE\n')
log_f.close()

log_f.close()
