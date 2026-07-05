"""
master_orchestrator.py — يدير كل شيء لمدة 48 ساعة
"""
import sys, os, time, subprocess, json, gc, warnings
warnings.filterwarnings('ignore')
os.environ['OMP_NUM_THREADS'] = '4'

BASE = r"C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor"
os.chdir(BASE)

logfile = open('master_log.txt', 'w', encoding='utf-8')
def p(msg):
    print(msg, flush=True)
    logfile.write(msg + '\n'); logfile.flush()

p('='*50)
p('MASTER ORCHESTRATOR STARTED')
p('='*50)

start_time = time.time()
ensemble_count = 0

def is_running(pid):
    """Check if process exists"""
    try:
        r = subprocess.run(['wmic', 'process', 'where', f'processid={pid}', 'get', 'ProcessId'],
                          capture_output=True, text=True, timeout=5)
        return str(pid) in r.stdout
    except:
        return False

def run_bg(script):
    """Run script in background"""
    p_ = subprocess.Popen(
        [sys.executable, '-X', 'utf8', script],
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        cwd=BASE,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    return p_.pid

# Track PIDs
dashboard_pid = None
tunnel_pid = None
infinite_pid = None

# Find running processes
r = subprocess.run(['wmic','process','where',"name='python.exe'",'get','ProcessId,CommandLine'],
                   capture_output=True, text=True, timeout=10)
for line in r.stdout.split('\n'):
    if 'infinite_trainer' in line.lower():
        parts = line.strip().split()
        infinite_pid = int(parts[0]) if parts[0].isdigit() else None
    elif 'streamlit' in line.lower() or 'dashboard' in line.lower():
        parts = line.strip().split()
        dashboard_pid = int(parts[0]) if parts[0].isdigit() else None
    elif 'localhost.run' in line.lower() or 'nokey@localhost' in line.lower():
        try:
            tunnel_pid = int(line.strip().split()[0])
        except:
            pass

p(f'Found processes: infinite={infinite_pid} dashboard={dashboard_pid} tunnel={tunnel_pid}')

iteration = 0
while True:
    iteration += 1
    elapsed = (time.time() - start_time) / 3600
    
    if elapsed > 48:
        p('48 HOURS REACHED! Shutting down...')
        break
    
    p(f'\n[{iteration}] Elapsed: {elapsed:.1f}h / 48h')
    
    # 1. Check dashboard
    if dashboard_pid and not is_running(dashboard_pid):
        p('  Dashboard DOWN. Restarting...')
        dashboard_pid = run_bg('dashboard.py')  # will restart via streamlit
        p(f'  Dashboard restarted PID: {dashboard_pid}')
    elif dashboard_pid:
        pass
        # Check if actually serving
        # try: urllib.request.urlopen('http://127.0.0.1:8501',timeout=3) ... 
    
    # 2. Check tunnel
    if tunnel_pid and not is_running(tunnel_pid):
        p('  Tunnel DOWN. Restarting...')
        tunnel_p = subprocess.Popen(
            ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ServerAliveInterval=30',
             '-R', '80:localhost:8501', 'nokey@localhost.run'],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
            stdout=open('tunnel_log.txt','w'), stderr=open('tunnel_err.txt','w')
        )
        tunnel_pid = tunnel_p.pid
        p(f'  Tunnel restarted PID: {tunnel_pid}')
    
    # 3. Check infinite trainer
    if infinite_pid and not is_running(infinite_pid):
        p('  Infinite Trainer DOWN. Restarting...')
        infinite_pid = run_bg('infinite_trainer.py')
        p(f'  Infinite Trainer restarted PID: {infinite_pid}')
    
    # 4. Every 2 hours: run auto-ensemble
    if iteration % 4 == 0:  # every ~2 hours
        p('  Running auto-ensemble check...')
        try:
            r = subprocess.run([sys.executable, '-c', '''
import sqlite3, numpy as np, warnings, joblib, time
warnings.filterwarnings("ignore")
cnt = __import__("sqlite3").connect("training_results.db").execute("SELECT COUNT(*) FROM results").fetchone()[0]
print("DB has %d models" % cnt)
'''], cwd=BASE, capture_output=True, text=True, timeout=30)
            p(f'    {r.stdout.strip()}')
        except Exception as e:
            p(f'    Error: {str(e)[:50]}')
    
    # 5. Every 6 hours: build ultimate ensemble
    if iteration % 12 == 0:
        ensemble_count += 1
        p(f'  Building ultimate ensemble #{ensemble_count}...')
        try:
            r = subprocess.run([sys.executable, '-X', 'utf8', 'build_ultimate_ensemble.py'],
                              cwd=BASE, capture_output=True, text=True, timeout=1800)
            for line in r.stdout.split('\n'):
                if any(x in line for x in ['exact=', 'Best', 'NEW', 'SAVED']):
                    p(f'    {line.strip()}')
            if r.stderr:
                p(f'    Stderr: {r.stderr[:200]}')
        except subprocess.TimeoutExpired:
            p('    Ensemble builder timed out')
        except Exception as e:
            p(f'    Error: {str(e)[:50]}')
    
    # 6. Log checkpoint
    try:
        import sqlite3
        conn = sqlite3.connect('training_results.db')
        cnt = conn.execute('SELECT COUNT(*) FROM results').fetchone()[0]
        best = conn.execute('SELECT MAX(test_exact) FROM results').fetchone()[0]
        conn.close()
        p(f'  Stats: {cnt} models, best={best*100:.2f}%')
    except:
        pass
    
    p(f'  Sleep 30 min...')
    time.sleep(1800)  # 30 min

p('='*50)
p('MASTER ORCHESTRATOR COMPLETED')
logfile.close()
