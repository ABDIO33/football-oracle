import os
base = os.path.join(os.path.dirname(__file__), 'models')
for f in ['stacking_log.txt', 'v3_log.txt', 'phase4_log.txt', 'pipeline_log.txt', 'checkpointed_log.txt']:
    p = os.path.join(base, f)
    if os.path.exists(p):
        text = open(p).read().strip()
        lines = text.split('\n')
        last = lines[-1][:100] if lines else 'empty'
        print(f'{f}: {len(lines)} lines')
        print(f'  Last: {last}')
    else:
        print(f'{f}: NOT FOUND')
    print()
