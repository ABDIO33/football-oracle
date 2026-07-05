import os, time
BASE = os.path.join(os.path.dirname(__file__), 'models')
has_ultimate = os.path.exists(os.path.join(BASE, 'ultimate_results.json'))
has_super = os.path.exists(os.path.join(BASE, 'super_ensemble_results.json'))
has_v3 = os.path.exists(os.path.join(BASE, 'v3_results.json'))
log_path = os.path.join(os.path.dirname(__file__), 'models', 'checkpointed_log.txt')
lines = []
if os.path.exists(log_path):
    log = open(log_path).read()
    lines = [l for l in log.strip().split('\n') if l]
print(f'Time: {time.strftime("%H:%M")}')
print(f'Ultimate model: {"OK" if has_ultimate else "WAIT"}')
print(f'Super ensemble: {"OK" if has_super else "WAIT"}')
print(f'V3 results: {"OK" if has_v3 else "WAIT"}')
if lines:
    print(f'Last log: {lines[-1][:80]}')
