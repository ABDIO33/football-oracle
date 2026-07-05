#!/usr/bin/env python3
"""
KAGGLE DATA DOWNLOAD — DATASETS
"""
import os, sys, warnings, json, time
warnings.filterwarnings('ignore')
os.environ['PYTHONIOENCODING'] = 'utf-8'

BASE = r"C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor"
os.chdir(BASE)

import sqlite3, requests
from datetime import datetime

LOG = os.path.join(BASE, "agent_logs")
os.makedirs(LOG, exist_ok=True)

def log(msg):
    t = datetime.now().strftime("%H:%M:%S")
    print(f"[{t}] {msg}", flush=True)

# ============================================================
# Try Kaggle datasets
# ============================================================
datasets = [
    "hugomathien/soccer",  # European Soccer Database (25K+ matches)
    "martjell/international-football-results-from-1872-to-2017",  # Intl results
    "adam-brunt/english-football-league-match-data-2005-to-2018",  # EFL data
    "davidbmx/football-match-probability",  # Match probability
]

# Method 1: Use kagglehub
try:
    import kagglehub
    log("✅ kagglehub available")
    for ds in datasets:
        log(f"Downloading {ds}...")
        try:
            path = kagglehub.dataset_download(ds)
            log(f"   Downloaded to: {path}")
            for root, dirs, files in os.walk(path):
                for f in files:
                    if f.endswith('.csv'):
                        fpath = os.path.join(root, f)
                        size = os.path.getsize(fpath)
                        log(f"   CSV: {f} ({size:,} bytes)")
        except Exception as e:
            log(f"   ❌ {ds}: {e}")
except ImportError:
    log("kagglehub not installed")
    
# Method 2: Direct download from GitHub (StatsBomb clone)
log("\nCloning StatsBomb open-data...")
try:
    import subprocess
    sb_dir = os.path.join(BASE, "statsbomb_data")
    if not os.path.exists(sb_dir):
        subprocess.run(['git', 'clone', '--depth', '1', 
                       'https://github.com/statsbomb/open-data.git', sb_dir],
                       capture_output=True, timeout=60)
        log("✅ StatsBomb cloned!")
    else:
        log("StatsBomb already exists")
    # Check files
    for root, dirs, files in os.walk(sb_dir):
        for f in files:
            if f.endswith('.json') and 'event' in f.lower():
                log(f"   Event file: {os.path.join(root, f)}")
except Exception as e:
    log(f"❌ StatsBomb clone: {e}")

# Method 3: Direct CSV URLs
log("\nDirect CSV downloads...")
csv_urls = [
    ("https://www.football-data.co.uk/mmz4281/2324/data_final.csv", "fd_23_24.csv"),
    ("https://projects.fivethirtyeight.com/soccer-api/club/spi_matches.csv", "538_spi.csv"),
]
for url, fname in csv_urls:
    try:
        r = requests.get(url, timeout=30)
        fpath = os.path.join(BASE, "downloads", fname)
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        with open(fpath, 'wb') as f:
            f.write(r.content)
        log(f"✅ Downloaded {fname} ({len(r.content):,} bytes)")
    except Exception as e:
        log(f"❌ {fname}: {e}")

log("\n✅ KAGGLE DOWNLOAD COMPLETE")
