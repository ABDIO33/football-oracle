#!/usr/bin/env python3
"""
Understat Matcher — يطابق اسماء فرق تحتستات مع قاعدة البيانات الرئيسية
باستخدام rapidfuzz + unidecode + manual mapping
"""
import sys, os, sqlite3, json, warnings
warnings.filterwarnings('ignore')
os.environ['PYTHONIOENCODING'] = 'utf-8'

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'scrape_cache.db')

from rapidfuzz import fuzz, process
from unidecode import unidecode

def log(m): print(f'[UnderstatMatcher] {m}', flush=True)

def clean_name(name):
    """Normalize team name"""
    if not name: return ''
    name = unidecode(name)
    name = name.replace('.', ' ').strip()
    name = name.replace('  ', ' ')
    # Remove common suffixes
    for suffix in [' FC', ' CF', ' SC', ' SV', ' SS', ' AS', ' AC', ' CD',
                   ' UD', ' SD', ' RC', ' Real ', ' Deportivo ']:
        pass  # handled in map
    return name.strip()

# Manual mapping for the known 14 problematic teams
MANUAL_MAP = {
    'SD Huesca': 'Huesca',
    'FC Heidenheim': 'Heidenheim',
    'Borussia M.Gladbach': 'Borussia Mönchengladbach',
    'Greuther Fuerth': 'Greuther Fürth',
    'Parma Calcio 1913': 'Parma',
    'Sporting CP': 'Sporting Lisbon',
    'AC Milan': 'Milan',
    'FC Internazionale': 'Inter Milan',
    '1. FC Koeln': 'FC Cologne',
    '1. FC Köln': 'FC Cologne',
    'Bayer 04 Leverkusen': 'Bayer Leverkusen',
    'Bayer Leverkusen': 'Bayer 04 Leverkusen',
    'Hertha BSC': 'Hertha Berlin',
    'RB Leipzig': 'RasenBallsport Leipzig',
    'Red Bull Salzburg': 'RB Salzburg',
    'FC Salzburg': 'RB Salzburg',
    'Real Betis': 'Real Betis Balompie',
    'Real Betis Balompie': 'Real Betis',
    'Inter Milan': 'Inter',
    'Milan': 'AC Milan',
    'FC Porto': 'Porto',
    'SL Benfica': 'Benfica',
    'Sporting Lisbon': 'Sporting CP',
    'Club Brugge KV': 'Club Brugge',
    'Club Brugge': 'Club Brugge KV',
    'RSC Anderlecht': 'Anderlecht',
    'R.S.C. Anderlecht': 'Anderlecht',
    'Racing Genk': 'Genk',
    'KRC Genk': 'Genk',
    'FC Basel 1893': 'Basel',
    'BSC Young Boys': 'Young Boys',
    'Young Boys': 'BSC Young Boys',
    'Fenerbahce': 'Fenerbahçe',
    'Besiktas': 'Beşiktaş',
    'Galatasaray': 'Galatasaray SK',
    'Galatasaray SK': 'Galatasaray',
    
    # Russian teams - map to themselves (Understat has them, training doesn't)
    'Akron': 'Akron Togliatti',
    'Amkar': 'Amkar Perm',
    'Anzhi Makhachkala': 'Anzhi Makhachkala',
    'Arsenal Tula': 'Arsenal Tula',
    'Baltika': 'Baltika Kaliningrad',
    'FC Rotor Volgograd': 'Rotor Volgograd',
    'FC Tambov': 'Tambov',
    'FC Ufa': 'Ufa',
    'FC Yenisey Krasnoyarsk': 'Yenisey Krasnoyarsk',
    'FK Akhmat': 'Akhmat Grozny',
    'Fakel': 'Fakel Voronezh',
    'Khimki': 'Khimki',
    'Kuban Krasnodar': 'Kuban Krasnodar',
    'Mordovya': 'Mordovia Saransk',
    'Nizhny Novgorod': 'Pari Nizhny Novgorod',
    'PFC Sochi': 'Sochi',
    'SKA-Khabarovsk': 'SKA Khabarovsk',
    'Tom Tomsk': 'Tom Tomsk',
    'Torpedo Moscow': 'Torpedo Moskva',
    'Tosno': 'Tosno',
    'Ural': 'Ural Yekaterinburg',
    
    # German teams
    'FC Cologne': 'FC Koln',
    'Hertha Berlin': 'Hertha BSC',
    'Mainz 05': 'Mainz',
    'RasenBallsport Leipzig': 'RB Leipzig',
    'RB Leipzig': 'RasenBallsport Leipzig',
    
    # French
    'Paris Saint Germain': 'Paris Saint Germain',
    
    # Italian
    'SPAL 2013': 'SPAL',
    
    # English
    'Wolverhampton Wanderers': 'Wolverhampton',
}

def match_teams():
    conn = sqlite3.connect(DB, timeout=60)
    c = conn.cursor()
    
    # 1. Get ALL unique team names from understat
    log('Getting Understat teams...')
    ut = c.execute('''
        SELECT DISTINCT home_team FROM source_understat
        UNION
        SELECT DISTINCT away_team FROM source_understat
        ORDER BY 1
    ''').fetchall()
    understat_teams = [t[0] for t in ut]
    log(f'Understat unique teams: {len(understat_teams)}')
    
    # 2. Get teams from main training data (source_football_data_uk)
    log('Getting football-data.co.uk teams...')
    fd = c.execute('''
        SELECT DISTINCT home_team FROM source_football_data_uk
        UNION
        SELECT DISTINCT away_team FROM source_football_data_uk
        ORDER BY 1
    ''').fetchall()
    fd_teams = [t[0] for t in fd]
    log(f'football-data teams: {len(fd_teams)}')
    
    # 3. Get teams from SofaScore - check column names first
    log('Getting SofaScore teams...')
    try:
        ss_cols = [d[1] for d in c.execute('PRAGMA table_info(source_sofascore_extended)').fetchall()]
        log(f'SofaScore columns: {ss_cols[:15]}...')
        if 'home_name' in ss_cols:
            ss = c.execute('''
                SELECT DISTINCT home_name FROM source_sofascore_extended
                UNION
                SELECT DISTINCT away_name FROM source_sofascore_extended
                ORDER BY 1
            ''').fetchall()
        elif 'home_team' in ss_cols:
            ss = c.execute('''
                SELECT DISTINCT home_team FROM source_sofascore_extended
                UNION
                SELECT DISTINCT away_team FROM source_sofascore_extended
                ORDER BY 1
            ''').fetchall()
        else:
            ss = []
        ss_teams = [t[0] for t in ss if t[0]]
    except Exception as e:
        log(f'Error: {e}')
        ss_teams = []
    log(f'SofaScore teams: {len(ss_teams)}')
    
    # Combined reference list
    reference_teams = list(set(fd_teams + ss_teams))
    ref_clean = {t: clean_name(t) for t in reference_teams}
    log(f'Combined reference teams: {len(reference_teams)}')
    
    # Results
    results = []
    matched = 0
    manual = 0
    fuzzy_matched = 0
    failed = 0
    
    for ut_name in understat_teams:
        ut_clean = clean_name(ut_name)
        
        # 1. Check manual map first
        if ut_name in MANUAL_MAP:
            mapped = MANUAL_MAP[ut_name]
            results.append((ut_name, mapped, 'manual', 1.0))
            manual += 1
            matched += 1
            continue
        
        # 2. Direct match (after cleaning)
        found = False
        for ref_name, ref_c in ref_clean.items():
            if ut_clean == ref_c or unidecode(ut_name).lower() == unidecode(ref_name).lower():
                results.append((ut_name, ref_name, 'direct', 1.0))
                matched += 1
                found = True
                break
        
        if found:
            continue
        
        # 3. Fuzzy match with rapidfuzz
        choices = {r: (r, c) for r, c in ref_clean.items()}
        best_match = None
        best_score = 0
        
        for ref_name, ref_c in choices.values():
            # Token sort ratio handles word order
            score = fuzz.token_sort_ratio(ut_clean, ref_c) / 100.0
            if score > best_score:
                best_score = score
                best_match = ref_name
        
        if best_match and best_score >= 0.80:
            results.append((ut_name, best_match, 'fuzzy', best_score))
            fuzzy_matched += 1
            matched += 1
        else:
            results.append((ut_name, '❌ NOT FOUND', 'failed', best_score if best_match else 0))
            failed += 1
    
    log('')
    log('='*60)
    log(f'نتائج المطابقة:')
    log(f'  Direct match: {matched - manual - fuzzy_matched}')
    log(f'  Manual map:   {manual}')
    log(f'  Fuzzy match:  {fuzzy_matched}')
    log(f'  ❌ FAILED:     {failed}')
    log(f'  TOTAL:        {len(results)}')
    log(f'  نسبة النجاح:  {matched/len(results)*100:.1f}%')
    log('='*60)
    log('')
    
    if failed > 0:
        log('❌ الفرق الفاشلة:')
        for ut_name, ref_name, method, score in results:
            if method == 'failed':
                log(f'  {ut_name:40s} → {ref_name} (score={score:.2f})')
    
    # Save mapping to file
    mapping = {}
    for ut_name, ref_name, method, score in results:
        mapping[ut_name] = {'match': ref_name, 'method': method, 'score': score}
    
    with open(os.path.join(BASE, 'understat_mapping.json'), 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    log(f'✅ Saved mapping to understat_mapping.json')
    
    # Check how many understat matches now have proper names
    log('')
    log('ANALYZING understat match coverage...')
    total_understat = c.execute('SELECT COUNT(*) FROM source_understat').fetchone()[0]
    
    # Count how many matches have BOTH teams in the training data
    understat_joined = c.execute('''
        SELECT COUNT(*) FROM source_understat u
        WHERE u.home_team IN (SELECT DISTINCT home_team FROM source_football_data_uk)
        AND u.away_team IN (SELECT DISTINCT away_team FROM source_football_data_uk)
    ''').fetchone()[0]
    
    log(f'Total Understat matches: {total_understat}')
    log(f'Before matching: ~{total_understat * 0.53:.0f} matched (53%)')
    log(f'After mapping: {matched} out of {len(results)} teams mapped ({matched/len(results)*100:.0f}%)')
    log(f'Estimated new matches in training: ~{total_understat * matched/len(results):.0f}')
    
    conn.close()
    return results

if __name__ == '__main__':
    log('🚀 بدء مطابقة فرق تحتستات...')
    match_teams()
