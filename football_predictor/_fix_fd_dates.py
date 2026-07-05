"""Fix FD historical dates from YY-MM-DD to YYYY-MM-DD"""
import sqlite3, sys
sys.path.insert(0, '.')
conn = sqlite3.connect('scrape_cache.db')

# Get all FD historical matches with YY dates
rows = conn.execute('''
    SELECT id, date FROM sofa_historical_results
    WHERE id < -2500000
    AND date LIKE "__-__-__"
''').fetchall()
print(f'FD historical matches with YY dates: {len(rows):,}')

fixed = 0
for row in rows:
    mid, date_str = row
    try:
        parts = date_str.split('-')
        yy = int(parts[0])
        mm = parts[1]
        dd = parts[2]
        # 93-99 → 1993-1999, 00-25 → 2000-2025
        if yy >= 93:
            yyyy = 1900 + yy
        else:
            yyyy = 2000 + yy
        new_date = f'{yyyy}-{mm}-{dd}'
        conn.execute('UPDATE sofa_historical_results SET date = ? WHERE id = ?', (new_date, mid))
        fixed += 1
        if fixed % 50000 == 0:
            conn.commit()
            print(f'  Fixed {fixed:,}')
    except:
        pass

conn.commit()
print(f'Fixed {fixed:,} dates')

# Verify
total = conn.execute('SELECT COUNT(*) FROM sofa_historical_results WHERE id < -2500000').fetchone()[0]
rng = conn.execute('SELECT MIN(date), MAX(date) FROM sofa_historical_results').fetchone()
print(f'Total FD historical: {total:,}')
print(f'Full DB date range: {rng[0]} to {rng[1]}')

conn.close()
