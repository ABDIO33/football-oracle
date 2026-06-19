"""
glicko2_calc.py — Compute Glicko-2 ratings for all historical matches
Stores pre-match glicko_rating and glicko_rd in glicko_state table.
"""
import sys, os, sqlite3, math
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))
DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

INITIAL_RATING = 1500.0
INITIAL_RD = 350.0
INITIAL_VOL = 0.06
TAU = 0.5
PI_SQ = math.pi * math.pi
CONV = 173.7178

def update_ratings(h_r, h_rd, h_v, a_r, a_rd, a_v, s_h, s_a):
    """Update both teams' ratings using pre-match states. Returns (h_new_r, h_new_rd, h_new_v, a_new_r, a_new_rd, a_new_v)."""
    # Home update
    mu = (h_r - 1500) / CONV
    phi = h_rd / CONV
    mu_j = (a_r - 1500) / CONV
    phi_j = a_rd / CONV
    g_phi_j = 1.0 / math.sqrt(1.0 + 3.0 * phi_j * phi_j / PI_SQ)
    e = 1.0 / (1.0 + math.exp(-g_phi_j * (mu - mu_j)))
    v_i = 1.0 / (g_phi_j * g_phi_j * e * (1.0 - e))
    delta = v_i * g_phi_j * (s_h - e)

    # Volatility update for home
    def f_h(x):
        ex = math.exp(x)
        num = ex * (delta * delta - phi * phi - v_i - ex)
        den = 2.0 * (phi * phi + v_i + ex) ** 2
        return num / den - (x - a_l) / (TAU * TAU)

    a_l = math.log(h_v * h_v)
    A = a_l
    if delta * delta > phi * phi + v_i:
        B_h = math.log(delta * delta - phi * phi - v_i)
    else:
        k = 1.0
        while f_h(a_l - k * TAU) <= 0:
            k += 1.0
        B_h = a_l - k * TAU

    fA_h, fB_h = f_h(A), f_h(B_h)
    for _ in range(50):
        if abs(fB_h - fA_h) < 1e-10:
            break
        C = A + (A - B_h) * fA_h / (fB_h - fA_h)
        fC = f_h(C)
        if fC * fB_h < 0:
            A, fA_h = B_h, fB_h
        else:
            fA_h *= 0.5
        B_h, fB_h = C, fC
        if abs(fB_h) < 1e-7:
            break
    new_hv = math.exp(B_h / 2.0)
    phi_star = math.sqrt(phi * phi + new_hv * new_hv)
    new_phi = 1.0 / math.sqrt(1.0 / (phi_star * phi_star) + 1.0 / v_i)
    new_mu = mu + new_phi * new_phi * g_phi_j * (s_h - e)
    h_new_r = CONV * new_mu + 1500
    h_new_rd = CONV * new_phi
    h_new_v = new_hv

    # Away update (using pre-match states of both)
    mu_a = (a_r - 1500) / CONV
    phi_a = a_rd / CONV
    mu_j_h = (h_r - 1500) / CONV
    phi_j_h = h_rd / CONV
    g_phi_j_a = 1.0 / math.sqrt(1.0 + 3.0 * phi_j_h * phi_j_h / PI_SQ)
    e_a = 1.0 / (1.0 + math.exp(-g_phi_j_a * (mu_a - mu_j_h)))
    v_a = 1.0 / (g_phi_j_a * g_phi_j_a * e_a * (1.0 - e_a))
    delta_a = v_a * g_phi_j_a * (s_a - e_a)

    def f_a(x):
        ex = math.exp(x)
        num = ex * (delta_a * delta_a - phi_a * phi_a - v_a - ex)
        den = 2.0 * (phi_a * phi_a + v_a + ex) ** 2
        return num / den - (x - a_la) / (TAU * TAU)

    a_la = math.log(a_v * a_v)
    A_a = a_la
    if delta_a * delta_a > phi_a * phi_a + v_a:
        B_a = math.log(delta_a * delta_a - phi_a * phi_a - v_a)
    else:
        k = 1.0
        while f_a(a_la - k * TAU) <= 0:
            k += 1.0
        B_a = a_la - k * TAU

    fA_a, fB_a = f_a(A_a), f_a(B_a)
    for _ in range(50):
        if abs(fB_a - fA_a) < 1e-10:
            break
        C = A_a + (A_a - B_a) * fA_a / (fB_a - fA_a)
        fC = f_a(C)
        if fC * fB_a < 0:
            A_a, fA_a = B_a, fB_a
        else:
            fA_a *= 0.5
        B_a, fB_a = C, fC
        if abs(fB_a) < 1e-7:
            break
    new_av = math.exp(B_a / 2.0)
    phi_star_a = math.sqrt(phi_a * phi_a + new_av * new_av)
    new_phi_a = 1.0 / math.sqrt(1.0 / (phi_star_a * phi_star_a) + 1.0 / v_a)
    new_mu_a = mu_a + new_phi_a * new_phi_a * g_phi_j_a * (s_a - e_a)
    a_new_r = CONV * new_mu_a + 1500
    a_new_rd = CONV * new_phi_a
    a_new_v = new_av

    return h_new_r, h_new_rd, h_new_v, a_new_r, a_new_rd, a_new_v

def main():
    print("=" * 60)
    print("GLICKO-2 RATING COMPUTATION")
    print("=" * 60)
    conn = sqlite3.connect(DB)
    print("\n[1] Loading matches...")
    rows = conn.execute('''
        SELECT id, home_team, away_team, home_score, away_score, start_timestamp, date
        FROM sofa_historical_results
        WHERE status_type = 'finished' AND home_score IS NOT NULL AND away_score IS NOT NULL
        ORDER BY start_timestamp ASC
    ''').fetchall()
    print(f"  Total matches: {len(rows)}")

    print("[2] Clearing old glicko table...")
    conn.execute('DROP TABLE IF EXISTS glicko_state')
    conn.execute('''
        CREATE TABLE glicko_state (
            team_name TEXT,
            date TEXT,
            glicko_rating REAL,
            glicko_rd REAL,
            glicko_vol REAL,
            matches_played INTEGER,
            PRIMARY KEY (team_name, date)
        )
    ''')
    conn.commit()

    # In-memory state: each team -> (rating, rd, vol)
    state = {}
    mp = defaultdict(int)  # matches played
    batch_state = []
    TOTAL = len(rows)
    BATCH_SIZE = 2000

    print("[3] Computing Glicko-2 ratings...")
    for idx, (eid, home, away, hs, aws, ts, date_str) in enumerate(rows):
        hs, aws = int(hs), int(aws)
        if home not in state:
            state[home] = [INITIAL_RATING, INITIAL_RD, INITIAL_VOL]
        if away not in state:
            state[away] = [INITIAL_RATING, INITIAL_RD, INITIAL_VOL]

        h_s = state[home]
        a_s = state[away]

        # Save PRE-MATCH states
        batch_state.append((home, date_str, h_s[0], h_s[1], h_s[2], mp[home]))
        batch_state.append((away, date_str, a_s[0], a_s[1], a_s[2], mp[away]))

        # Determine outcome
        if hs > aws:
            s_h, s_a = 1.0, 0.0
        elif hs == aws:
            s_h, s_a = 0.5, 0.5
        else:
            s_h, s_a = 0.0, 1.0

        # Compute both updates using pre-match states
        h_r, h_rd, h_v, a_r, a_rd, a_v = update_ratings(
            h_s[0], h_s[1], h_s[2],
            a_s[0], a_s[1], a_s[2],
            s_h, s_a
        )

        # Apply both updates
        state[home] = [h_r, h_rd, h_v]
        state[away] = [a_r, a_rd, a_v]
        mp[home] += 1
        mp[away] += 1

        if len(batch_state) >= BATCH_SIZE * 2:
            conn.executemany('''
                INSERT OR REPLACE INTO glicko_state
                (team_name, date, glicko_rating, glicko_rd, glicko_vol, matches_played)
                VALUES (?,?,?,?,?,?)
            ''', batch_state)
            conn.commit()
            batch_state = []

        if (idx + 1) % 10000 == 0:
            print(f"  {idx+1}/{TOTAL}")

    if batch_state:
        conn.executemany('''
            INSERT OR REPLACE INTO glicko_state
            (team_name, date, glicko_rating, glicko_rd, glicko_vol, matches_played)
            VALUES (?,?,?,?,?,?)
        ''', batch_state)
        conn.commit()

    cnt = conn.execute('SELECT COUNT(*) FROM glicko_state').fetchone()[0]
    teams = conn.execute('SELECT COUNT(DISTINCT team_name) FROM glicko_state').fetchone()[0]
    min_d = conn.execute('SELECT MIN(date) FROM glicko_state').fetchone()[0]
    max_d = conn.execute('SELECT MAX(date) FROM glicko_state').fetchone()[0]
    conn.close()

    print(f"\n{'='*60}")
    print(f"DONE: {cnt} snapshots ({teams} teams, {min_d} to {max_d})")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()
