"""Check progress of data collection and model results"""
import os, json, sqlite3

model_dir = 'models'
print('=== MODEL RESULTS ===')
result_files = [f for f in os.listdir(model_dir) if 'result' in f.lower() and f.endswith('.json')]
for rf in sorted(result_files):
    path = os.path.join(model_dir, rf)
    try:
        with open(path) as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            exact_vals = []
            def find_exact(d, path=''):
                if isinstance(d, dict):
                    for k, v in d.items():
                        if 'exact' in k.lower():
                            if isinstance(v, (int, float)):
                                exact_vals.append((path + '.' + k, v))
                        find_exact(v, path + '.' + k)
                elif isinstance(d, list):
                    for i, v in enumerate(d):
                        find_exact(v, f'{path}[{i}]')
            find_exact(data)
            if exact_vals:
                print(f'{rf}:')
                for k, v in exact_vals[:5]:
                    print(f'  {k} = {v}')
            else:
                print(f'{rf}: (no exact found, keys={list(data.keys())[:5]})')
        else:
            print(f'{rf}: (list, {len(data)} items)')
    except Exception as e:
        print(f'{rf}: {e}')

print()
print('=== DATABASE PROGRESS ===')
DB = 'scrape_cache.db'
conn = sqlite3.connect(DB)
cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cur.fetchall()]
print(f'Total tables: {len(tables)}')

for t in tables:
    try:
        cur = conn.execute(f'SELECT COUNT(*) FROM "{t}"')
        count = cur.fetchone()[0]
        print(f'  {t}: {count:,} rows')
    except:
        pass

conn.close()
