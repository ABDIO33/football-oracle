#!/usr/bin/env python3
"""
DISPATCH ALL 5 AGENTS + ALL 12 AGENT4 SCRIPTS — FULL PARALLEL ATTACK
ينفذ كل سكريبت اختراق في عملية منفصلة
"""
import os, sys, subprocess, json, time, warnings
from datetime import datetime
warnings.filterwarnings('ignore')
os.environ['PYTHONIOENCODING'] = 'utf-8'

BASE = r"C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor"
os.chdir(BASE)

LOG_DIR = os.path.join(BASE, "agent_logs")
os.makedirs(LOG_DIR, exist_ok=True)

def log(msg):
    t = datetime.now().strftime("%H:%M:%S")
    print(f"[{t}] {msg}", flush=True)

def run_agent(script_name, agent_label, timeout=300):
    """Run an agent script in a subprocess with timeout"""
    logfile = os.path.join(LOG_DIR, f"{agent_label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    cmd = [sys.executable, os.path.join(BASE, script_name)]
    
    log(f"🚀 Launching {agent_label}: {script_name}")
    
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=open(logfile, 'wb'),
            stderr=subprocess.STDOUT,
            cwd=BASE,
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        )
        log(f"   PID {proc.pid} — log: {os.path.basename(logfile)}")
        return proc
    except Exception as e:
        log(f"   ❌ Failed: {e}")
        return None

# ============================================================================
# AGENTS TO DISPATCH — كل القائمة
# ============================================================================

agents = [
    # AGENT 4 series (the 5 hacking agents)
    ("agent4_fbref_tls.py", "agent4_fbref", 3600),
    ("agent4_betexplorer_odds.py", "agent4_betexplorer", 3600),
    ("agent4_oddsportal_odds.py", "agent4_oddsportal", 3600),
    ("agent4_soccerway_flashscore.py", "agent4_soccerway", 3600),
    ("agent4_transfermarkt_values.py", "agent4_transfermarkt", 3600),
    ("agent4_whoscored_key_hunt.py", "agent4_whoscored", 3600),
    
    # Extra agents
    ("agent4_heist_advanced.py", "agent4_heist", 7200),
    ("agent4_premium_data.py", "agent4_premium", 3600),
    ("agent4_odds_scraper.py", "agent4_odds", 3600),
    ("agent4_alt_requests_html.py", "agent4_alt_html", 3600),
    
    # Exploit scripts
    ("exploit_all_sources.py", "exploit_all", 7200),
    ("fill_gaps.py", "fill_gaps", 3600),
    
    # FBref killer
    ("fbref_killer_v2.py", "fbref_killer", 3600),
]

# ============================================================================
# RUN ALL IN PARALLEL
# ============================================================================
log("="*70)
log("🔥 DISPATCHING ALL AGENTS — FULL PARALLEL ATTACK")
log("="*70)

processes = []
for script, label, timeout in agents:
    p = run_agent(script, label, timeout)
    if p:
        processes.append((label, p, timeout))
    time.sleep(1)  # stagger launches

log(f"\n✅ Launched {len(processes)} agents")
for label, proc, timeout in processes:
    log(f"   {label:30s} PID {proc.pid}  timeout={timeout}s")

log("\n📊 Agents running in background. Check agent_logs/ for results.")
log(f"📁 Logs: {LOG_DIR}")
