"""
Parse ALL football-data.co.uk historical CSV files and insert into DB
32 seasons (1993-2025), ~500K matches potentially
"""
import zipfile, os, csv, sqlite3, sys, time, re
sys.path.insert(0, os.path.dirname(__file__))

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
TDIR = os.path.join(os.path.dirname(__file__), 'fd_historical')
LOG = os.path.join(os.path.dirname(__file__), 'models', 'fd_integrate_log.txt')

def log(msg):
    with open(LOG, 'a') as f:
        f.write(f'[{time.strftime("%H:%M:%S")}] {msg}\n')
    print(f'[{time.strftime("%H:%M:%S")}] {msg}')

conn = sqlite3.connect(DB)
conn.execute("PRAGMA synchronous=OFF")
conn.execute("PRAGMA journal_mode=WAL")

# Load team name mappings
mappings = dict(conn.execute(
    'SELECT fd_name, sofa_name FROM team_name_mapping WHERE confidence >= 0.85'
).fetchall())

def map_team(name):
    """Map FD team name to SofaScore name with fuzzy fallback."""
    k = name.lower().strip()
    if k in mappings:
        return mappings[k]
    # Try fuzzy matching
    for fd_name, sofa_name in mappings.items():
        if k in fd_name or fd_name in k:
            return sofa_name
    return name  # Use original if no match

# Get all zip files
zips = sorted([f for f in os.listdir(TDIR) if f.endswith('.zip')])
log(f'Found {len(zips)} ZIP archives')

total_csvs = 0
total_rows = 0
inserted = 0
skipped_exist = 0
skipped_no_score = 0

for zf_name in zips:
    zf_path = os.path.join(TDIR, zf_name)
    season = zf_name.replace('.zip', '')
    try:
        with zipfile.ZipFile(zf_path, 'r') as zf:
            csv_files = [n for n in zf.namelist() if n.endswith('.csv')]
            for cf in csv_files:
                total_csvs += 1
                try:
                    with zf.open(cf) as f:
                        content = f.read().decode('latin-1')
                        lines = content.splitlines()
                        if len(lines) < 2:
                            continue
                        reader = csv.DictReader(lines)
                        for row in reader:
                            total_rows += 1
                            # Extract date
                            date_str = (row.get('Date') or row.get('date') or '').strip()
                            if not date_str:
                                continue
                            # Normalize date format
                            if '/' in date_str:
                                parts = date_str.split('/')
                                if len(parts[0]) == 4:
                                    date_str = f'{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}'
                                else:
                                    date_str = f'{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}'
                            
                            ht = (row.get('HomeTeam') or row.get('home_team') or '').strip()
                            at = (row.get('AwayTeam') or row.get('away_team') or '').strip()
                            hs_str = (row.get('FTHG') or row.get('FTHG') or row.get('home_score') or '').strip()
                            as_str = (row.get('FTAG') or row.get('FTAG') or row.get('away_score') or '').strip()
                            league = (row.get('Div') or row.get('league') or season).strip()
                            
                            if not ht or not at:
                                continue
                            if not hs_str or not as_str:
                                skipped_no_score += 1
                                continue
                            try:
                                hs = int(float(hs_str))
                                aws = int(float(as_str))
                            except:
                                skipped_no_score += 1
                                continue
                            if hs > 20 or aws > 20:
                                continue
                            
                            # Map team names
                            ht_m = map_team(ht)
                            at_m = map_team(at)
                            
                            # Check if exists
                            exists = conn.execute('''
                                SELECT COUNT(*) FROM sofa_historical_results
                                WHERE date=? AND home_team=? AND away_team=?
                            ''', (date_str, ht_m, at_m)).fetchone()[0]
                            if exists > 0:
                                skipped_exist += 1
                                continue
                            
                            try:
                                conn.execute('''
                                    INSERT INTO sofa_historical_results
                                    (id, home_team, away_team, home_score, away_score, tournament, date, status_type)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, 'finished')
                                ''', (-3000000 - total_rows, ht_m, at_m, hs, aws, league, date_str))
                                inserted += 1
                            except:
                                pass
                            
                            if inserted % 1000 == 0:
                                log(f'  {season}/{cf}: +{inserted} inserted ({skipped_exist} exist, {skipped_no_score} no score)')
                except Exception as e:
                    pass
        log(f'[SEASON {season}] Done: csvs={len(csv_files)}, rows={total_rows} total')
    except Exception as e:
        log(f'[ERROR] {zf_name}: {e}')

conn.commit()
total = conn.execute('SELECT COUNT(*) FROM sofa_historical_results').fetchone()[0]
conn.close()

log(f'\n=== FINAL ===')
log(f'Total CSV files: {total_csvs}')
log(f'Total rows parsed: {total_rows:,}')
log(f'Inserted: {inserted:,}')
log(f'Skipped (exist): {skipped_exist:,}')
log(f'Skipped (no score): {skipped_no_score:,}')
log(f'DB total: {total:,}')
log(f'NEW data from FD history: {inserted:,} matches')
