"""fast_bulk_load_v6.py — ALL matches (1983-2026), 120 features, V3-compatible"""
import sqlite3, os, time
import numpy as np
import pandas as pd

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

def extract_v6():
    t0 = time.time()
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA cache_size = -800000")
    
    query = """
    SELECT 
        r.id, r.home_team, r.away_team, r.home_score, r.away_score, r.date, r.tournament,
        hwf.elo AS home_elo, hwf.rolling_xg_for AS hxgf, hwf.rolling_xg_against AS hxga,
        hwf.form_points AS hf, hwf.matches_played AS hmp,
        hwf.rolling_shots_for AS hsf, hwf.rolling_shots_against AS hsa,
        awf.elo AS away_elo, awf.rolling_xg_for AS axgf, awf.rolling_xg_against AS axga,
        awf.form_points AS af, awf.matches_played AS amp,
        awf.rolling_shots_for AS asf, awf.rolling_shots_against AS asa,
        hg.glicko_rating AS hglicko, hg.glicko_rd AS hgrd,
        ag.glicko_rating AS aglicko, ag.glicko_rd AS agrd
    FROM sofa_historical_results r
    LEFT JOIN walkforward_state hwf ON hwf.team_name=r.home_team AND hwf.date=(SELECT MAX(wf2.date) FROM walkforward_state wf2 WHERE wf2.team_name=r.home_team AND wf2.date<=r.date)
    LEFT JOIN walkforward_state awf ON awf.team_name=r.away_team AND awf.date=(SELECT MAX(wf2.date) FROM walkforward_state wf2 WHERE wf2.team_name=r.away_team AND wf2.date<=r.date)
    LEFT JOIN glicko_state hg ON hg.team_name=r.home_team AND hg.date=(SELECT MAX(g2.date) FROM glicko_state g2 WHERE g2.team_name=r.home_team AND g2.date<=r.date)
    LEFT JOIN glicko_state ag ON ag.team_name=r.away_team AND ag.date=(SELECT MAX(g2.date) FROM glicko_state g2 WHERE g2.team_name=r.away_team AND g2.date<=r.date)
    WHERE r.home_score IS NOT NULL AND r.away_score IS NOT NULL AND r.status_type='finished'
    ORDER BY r.start_timestamp
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    print(f"Loaded {len(df):,} rows in {time.time()-t0:.1f}s")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    df = df.fillna(0)
    
    n = len(df)
    X = np.zeros((n, 120), dtype=np.float32)
    eps = 0.01
    
    he = df['home_elo'].values.astype(np.float32); ae = df['away_elo'].values.astype(np.float32)
    hf = df['hf'].values.astype(np.float32); af = df['af'].values.astype(np.float32)
    hxgf = df['hxgf'].values.astype(np.float32); hxga = df['hxga'].values.astype(np.float32)
    axgf = df['axgf'].values.astype(np.float32); axga = df['axga'].values.astype(np.float32)
    hsf = df['hsf'].values.astype(np.float32); hsa = df['hsa'].values.astype(np.float32)
    asf = df['asf'].values.astype(np.float32); asa = df['asa'].values.astype(np.float32)
    hmp = df['hmp'].values.astype(np.float32); amp = df['amp'].values.astype(np.float32)
    hg = df['hglicko'].values.astype(np.float32); agh = df['aglicko'].values.astype(np.float32)
    hgrd = df['hgrd'].values.astype(np.float32); agrd = df['agrd'].values.astype(np.float32)
    dates = pd.to_datetime(df['date'])
    
    X[:, 0] = he; X[:, 1] = ae
    X[:, 2] = he - ae; X[:, 3] = X[:, 2]**2; X[:, 4] = np.sign(X[:, 2]); X[:, 5] = he + ae
    X[:, 6] = hf; X[:, 7] = af; X[:, 8] = hf - af; X[:, 9] = X[:, 8]**2
    X[:, 10] = X[:, 0]*X[:, 6]; X[:, 11] = X[:, 1]*X[:, 7]; X[:, 12] = X[:, 2]*X[:, 8]
    X[:, 13] = hxgf; X[:, 14] = hxga; X[:, 15] = axgf; X[:, 16] = axga
    X[:, 17] = hxgf - hxga; X[:, 18] = axgf - axga
    X[:, 19] = X[:, 0]*X[:, 13]; X[:, 20] = X[:, 1]*X[:, 15]
    X[:, 21] = X[:, 6]*X[:, 13]; X[:, 22] = X[:, 7]*X[:, 15]
    X[:, 23] = hxgf/(axgf+eps); X[:, 24] = hxgf/(hxga+eps); X[:, 25] = axgf/(axga+eps)
    X[:, 26] = hxgf+axgf
    X[:, 27] = hsf; X[:, 28] = hsa; X[:, 29] = asf; X[:, 30] = asa
    X[:, 31] = hsf/(asf+eps); X[:, 32] = hxgf/(hsf+eps); X[:, 33] = axgf/(asf+eps)
    X[:, 34] = hmp/38.0; X[:, 35] = amp/38.0; X[:, 36] = hmp - amp
    X[:, 37] = hg; X[:, 38] = agh; X[:, 39] = hg - agh
    X[:, 40] = 1.0/(hgrd+1); X[:, 41] = 1.0/(agrd+1); X[:, 42] = hgrd + agrd
    
    for i, ki in enumerate([2, 8, 39, 23]):
        v = X[:, ki]; b = 43 + i*3
        X[:, b] = np.sqrt(np.abs(v)+eps)*np.sign(v)
        X[:, b+1] = np.log(np.abs(v)+eps+1e-10)
        X[:, b+2] = np.abs(v)
    
    months = dates.dt.month.values; days = dates.dt.dayofweek.values; doy = dates.dt.dayofyear.values
    X[:, 55] = months; X[:, 56] = np.sin(2*np.pi*months/12)
    X[:, 57] = np.cos(2*np.pi*months/12); X[:, 58] = days
    X[:, 59] = (days >= 5).astype(np.float32); X[:, 60] = doy / 365.0
    
    ki_idx = [2, 8, 39, 23, 17, 18]; inter_idx = 61
    for i, fi in enumerate(ki_idx):
        for fj in ki_idx[i+1:]:
            if inter_idx < 100:
                X[:, inter_idx] = X[:, fi] * X[:, fj]
                inter_idx += 1
    
    X[:, 100] = X[:, 0]*X[:, 13]; X[:, 101] = X[:, 1]*X[:, 15]
    X[:, 102] = X[:, 6]*X[:, 13]; X[:, 103] = X[:, 7]*X[:, 15]
    X[:, 104] = X[:, 2]*np.abs(X[:, 17]); X[:, 105] = -X[:, 2]*np.abs(X[:, 18])
    X[:, 106] = X[:, 6]*np.clip(X[:, 2], -200, 200)
    X[:, 107] = X[:, 7]*np.clip(-X[:, 2], -200, 200)
    X[:, 108] = X[:, 106]-X[:, 107]
    X[:, 109] = X[:, 0]/(X[:, 1]+1); X[:, 110] = X[:, 13]/(X[:, 16]+eps)
    X[:, 111] = X[:, 15]/(X[:, 14]+eps); X[:, 112] = X[:, 17]-X[:, 18]; X[:, 113] = X[:, 34]-X[:, 35]
    # Extra features to reach 120
    X[:, 114] = X[:, 2]*X[:, 39]  # elo_diff * glicko_diff
    X[:, 115] = X[:, 6]*X[:, 17]  # home_form * xg_diff
    X[:, 116] = X[:, 7]*X[:, 18]  # away_form * xg_diff
    X[:, 117] = X[:, 13]+X[:, 15]  # total xg for
    X[:, 118] = X[:, 27]+X[:, 29]  # total shots
    X[:, 119] = X[:, 37]+X[:, 38]  # total glicko
    
    hs = df['home_score'].values.astype(int); as_s = df['away_score'].values.astype(int)
    y = np.array([min(max(int(h),0),4)*5+min(max(int(a),0),4) for h,a in zip(hs, as_s)], dtype=np.int32)
    rt = np.array([0 if h>a else 1 if h==a else 2 for h,a in zip(hs, as_s)], dtype=np.int32)
    
    nan_cnt = int(np.isnan(X).sum()); inf_cnt = int(np.isinf(X).sum())
    print(f'V6: {X.shape}, nan={nan_cnt}, inf={inf_cnt}, time={time.time()-t0:.0f}s')
    
    out_path = os.path.join(os.path.dirname(__file__), 'training_data_v6.npz')
    np.savez_compressed(out_path, X=X, y=y, result_types=rt, match_ids=df['id'].values)
    print(f'Saved: {out_path} ({X.nbytes/1024/1024:.0f} MB)')

if __name__ == '__main__':
    extract_v6()
