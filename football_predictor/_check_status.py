import sqlite3, sys
DB = sys.argv[1] if len(sys.argv) > 1 else 'scrape_cache.db'
conn = sqlite3.connect(DB)
t = conn.execute('SELECT COUNT(*) FROM sofa_historical_results').fetchone()[0]
fd_new = conn.execute('SELECT COUNT(*) FROM sofa_historical_results WHERE id < -2000000').fetchone()[0]
# FD historical range
fd_hist = conn.execute('SELECT COUNT(*) FROM sofa_historical_results WHERE id < -2500000').fetchone()[0]
print(f'Total: {t:,}')
print(f'FD remaining (id < -2000000): {fd_new:,}')
print(f'FD historical (id < -2500000): {fd_hist:,}')

# Check V4 process
import os, subprocess
v4_log = 'models/v4_log.txt'
if os.path.exists(v4_log):
    with open(v4_log) as f:
        lines = f.readlines()
        print(f'\nV4 log: {len(lines)} lines, last 2:')
        for l in lines[-2:]:
            print(f'  {l.strip()}')

fd_log = 'models/fd_integrate_log.txt'
if os.path.exists(fd_log):
    with open(fd_log) as f:
        lines = f.readlines()
        print(f'\nFD log: {len(lines)} lines, last 2:')
        for l in lines[-2:]:
            print(f'  {l.strip()}')

conn.close()
