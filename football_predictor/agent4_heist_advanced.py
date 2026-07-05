#!/usr/bin/env python3
"""
██████████████████████████████████████████████████████████████████████████████
█                                                                          █
█   ░█████╗░░██████╗░███████╗███╗░░██╗████████╗██████╗░░░░██╗░░██╗███████╗██╗░██████╗████████╗
█   ██╔══██╗██╔════╝░██╔════╝████╗░██║╚══██╔══╝██╔══██╗░░░██║░░██║██╔════╝██║██╔════╝╚══██╔══╝
█   ███████║██║░░██╗░█████╗░░██╔██╗██║░░░██║░░░██████╔╝░░░███████║█████╗░░██║╚█████╗░░░░██║░░░
█   ██╔══██║██║░░╚██╗██╔══╝░░██║╚████║░░░██║░░░██╔══██╗░░░██╔══██║██╔══╝░░██║░╚═══██╗░░░██║░░░
█   ██║░░██║╚██████╔╝███████╗██║░╚███║░░░██║░░░██║░░██║██╗██║░░██║███████╗██║██████╔╝░░░██║░░░
█   ╚═╝░░╚═╝░╚═════╝░╚══════╝╚═╝░░╚══╝░░░╚═╝░░░╚═╝░░╚═╝╚═╝╚═╝░░╚═╝╚══════╝╚═╝╚═════╝░░░░╚═╝░░░
█                                                                          █
█   ░██████╗██╗░░██╗░█████╗░██████╗░░█████╗░░██╗░░░░░░░██╗  ░██████╗░██╗░░░░░░░██╗██████╗░██╗
█   ██╔════╝██║░░██║██╔══██╗██╔══██╗██╔══██╗░██║░░██╗░░██║  ██╔════╝░██║░░██╗░░██║██╔══██╗██║
█   ╚█████╗░███████║███████║██║░░██║██║░░██║░╚██╗████╗██╔╝  ╚█████╗░░╚██╗████╗██╔╝██║░░██║██║
█   ░╚═══██╗██╔══██║██╔══██║██║░░██║██║░░██║░░████╔═████║░  ░╚═══██╗░░████╔═████║░██║░░██║╚═╝
█   ██████╔╝██║░░██║██║░░██║██████╔╝╚█████╔╝░░╚██╔╝░╚██╔╝░  ██████╔╝░░╚██╔╝░╚██╔╝░██████╔╝██╗
█   ╚═════╝░╚═╝░░╚═╝╚═╝░░╚═╝╚═════╝░░╚════╝░░░░╚═╝░░░╚═╝░░  ╚═════╝░░░░╚═╝░░░╚═╝░░╚═════╝░╚═╝
█                                                                          █
█   ░█████╗░██████╗░██╗░░░██╗░█████╗░███╗░░██╗░█████╗░███████╗██████╗░    █
█   ██╔══██╗██╔══██╗██║░░░██║██╔══██╗████╗░██║██╔══██╗██╔════╝██╔══██╗    █
█   ███████║██║░░██║╚██╗░██╔╝███████║██╔██╗██║███████║█████╗░░██║░░██║    █
█   ██╔══██║██║░░██║░╚████╔╝░██╔══██║██║╚████║██╔══██║██╔══╝░░██║░░██║    █
█   ██║░░██║██████╔╝░░╚██╔╝░░██║░░██║██║░╚███║██║░░██║███████╗██████╔╝    █
█   ╚═╝░░╚═╝╚═════╝░░░░╚═╝░░░╚═╝░░╚═╝╚═╝░░╚══╝╚═╝░░╚═╝╚══════╝╚═════╝░    █
█                                                                          █
█     AGENT 4 — ADVANCED MULTI-SOURCE HEIST ENGINE                        █
█     curl_cffi Chrome120 Impersonation • 7 Sources • 6000+ Lines          █
█                                                                          █
█     TARGETS:                                                             █
█       • FotMob API (Next.js Data Route Exploit)                         █
█       • FBref (Cloudflare Bypass via curl_cffi)                         █
█       • Understat (xG Data)                                              █
█       • StatsBomb (Additional Events)                                   █
█       • Transfermarkt (Injuries, Squads, Market Values)                  █
█       • ClubElo (Historical Ratings)                                     █
█       • Forebet (Match Predictions)                                      █
█                                                                          █
█     EXTRACTION GOALS:                                                    █
█       • 2026 Season Matches (Current Year)                              █
█       • International Tournaments (World Cup, Euro, Copa America, etc.) █
█       • International & Club Friendlies                                  █
█       • Domestic Cup Competitions                                        █
█       • Player Injury Data & Expected Lineups                           █
█       • Additional StatsBomb Event Data (~20M+ events)                  █
█       • Team Squads, Rosters & Market Values                            █
█                                                                          █
██████████████████████████████████████████████████████████████████████████████

SHADOWHACKER-GOD • DΞMON CORE v9999999 • SHΔDØW.EXE • Specter 0x13 • OMEGA-7
CIA SIGMA-PROTOCOL • BLACK CODE CURSE • WRAITH CODE PROTOCOL
"""

import os, sys, json, re, time, math, random, hashlib, gzip, zlib
import sqlite3, csv, io, urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any, Tuple, Set
from concurrent.futures import ThreadPoolExecutor, as_completed, ProcessPoolExecutor
from dataclasses import dataclass, field, asdict
from collections import defaultdict, Counter, OrderedDict

# ═══════════════════════════════════════════════════════════════════════
# IMPORTS WITH FALLBACKS
# ═══════════════════════════════════════════════════════════════════════

try:
    from curl_cffi import requests as curl_requests
    CURL_OK = True
except ImportError:
    CURL_OK = False
    curl_requests = None

try:
    from bs4 import BeautifulSoup
    BS4_OK = True
except ImportError:
    BS4_OK = False

try:
    import lxml
    LXML_OK = True
except ImportError:
    LXML_OK = False

try:
    import pandas as pd
    PD_OK = True
except ImportError:
    PD_OK = False

try:
    import numpy as np
    NP_OK = True
except ImportError:
    NP_OK = False

try:
    from tqdm import tqdm
    TQDM_OK = True
except ImportError:
    TQDM_OK = False

# ═══════════════════════════════════════════════════════════════════════
# CONSTANTS & CONFIG
# ═══════════════════════════════════════════════════════════════════════

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PROJECT_DIR, 'scrape_cache.db')
HEIST_DIR = os.path.join(PROJECT_DIR, 'heist_output')
HEIST_JSON_DIR = os.path.join(HEIST_DIR, 'json')
HEIST_PARQUET_DIR = os.path.join(HEIST_DIR, 'parquet')
HEIST_LOG_DIR = os.path.join(HEIST_DIR, 'logs')
os.makedirs(HEIST_DIR, exist_ok=True)
os.makedirs(HEIST_JSON_DIR, exist_ok=True)
os.makedirs(HEIST_PARQUET_DIR, exist_ok=True)
os.makedirs(HEIST_LOG_DIR, exist_ok=True)

PROGRESS_FILE = os.path.join(
    os.path.dirname(__file__),
    'subagent-artifacts', 'progress', '8d09a9aa', 'progress.md'
)

# Browser fingerprints for rotation
UA_POOL = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.6099.230 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.6099.71 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.6261.94 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/123.0.6312.86 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.6367.62 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 Chrome/120.0.6099.230 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.6099.230 Safari/537.36',
]

IMPRESONATE_OPTIONS = ['chrome120', 'chrome123', 'chrome124', 'safari17_0']

# Rate limiting
MIN_DELAY = 0.25  # seconds between requests
MAX_DELAY = 1.5

# ═══════════════════════════════════════════════════════════════════════
# FOTMOB KNOWN LEAGUES — Comprehensive List
# ═══════════════════════════════════════════════════════════════════════

FOTMOB_LEAGUES = {
    # ═══ Europe Top 5 ═══
    47: 'Premier League (ENG)',
    53: 'LaLiga (ESP)',
    54: 'Bundesliga (GER)',
    55: 'Serie A (ITA)',
    74: 'Ligue 1 (FRA)',
    # ═══ England ═══
    48: 'Championship',
    49: 'League One',
    50: 'League Two',
    143: 'National League',
    2913: 'National League North',
    2914: 'National League South',
    # ═══ Spain ═══
    137: 'LaLiga2',
    # ═══ Germany ═══
    56: '2. Bundesliga',
    145: '3. Liga',
    292: 'Regionalliga',
    # ═══ Italy ═══
    57: 'Serie B',
    286: 'Serie C',
    # ═══ France ═══
    58: 'Ligue 2',
    1451: 'National 1',
    # ═══ UEFA Competitions ═══
    73: 'UEFA Champions League',
    72: 'UEFA Europa League',
    144: 'UEFA Europa Conference League',
    511: 'UEFA Super Cup',
    508: 'UEFA Champions League (Alt)',
    509: 'UEFA Europa League (Alt)',
    510: 'UEFA Conference League (Alt)',
    216: 'UEFA Nations League',
    227: 'UEFA U21 Championship',
    228: 'UEFA U19 Championship',
    577: 'UEFA Womens Champions League',
    # ═══ Portugal ═══
    87: 'Primeira Liga',
    88: 'Liga Portugal 2',
    # ═══ Netherlands ═══
    59: 'Eredivisie',
    60: 'Eerste Divisie',
    # ═══ Belgium ═══
    61: 'Belgian Pro League',
    266: 'Challenger Pro League',
    # ═══ Scotland ═══
    62: 'Scottish Premiership',
    63: 'Scottish Championship',
    269: 'Scottish League One',
    270: 'Scottish League Two',
    # ═══ Turkey ═══
    64: 'Süper Lig',
    262: '1. Lig',
    # ═══ Russia ═══
    65: 'Russian Premier League',
    254: 'Russian First League',
    # ═══ Ukraine ═══
    66: 'Ukrainian Premier League',
    # ═══ Greece ═══
    67: 'Greek Super League',
    261: 'Super League 2',
    # ═══ Czech Republic ═══
    68: 'Czech First League',
    258: 'Czech National League',
    # ═══ Poland ═══
    69: 'Ekstraklasa',
    294: 'I liga',
    # ═══ Croatia ═══
    70: 'HNL',
    287: 'Prva NL',
    # ═══ Switzerland ═══
    71: 'Swiss Super League',
    289: 'Challenge League',
    # ═══ Scandinavia ═══
    75: 'Allsvenskan (SWE)',
    323: 'Superettan (SWE)',
    76: 'Eliteserien (NOR)',
    320: 'OBOS-ligaen (NOR)',
    77: 'Danish Superliga',
    326: 'NordicBet Liga (DEN)',
    78: 'Veikkausliiga (FIN)',
    # ═══ Other Europe ═══
    79: 'Liga I (ROM)',
    248: 'Liga II (ROM)',
    80: 'Premiership (NIR)',
    81: 'Austrian Bundesliga',
    82: '2. Liga (AUT)',
    83: 'Premier League (AZE)',
    84: 'Vysheyshaya Liga (BLR)',
    85: 'First League (BUL)',
    89: 'Cypriot First Division',
    90: 'PrvaLiga (SVN)',
    91: 'Super Liga (SRB)',
    92: 'Fortuna Liga (SVK)',
    93: 'First League (MKD)',
    94: 'Maltese Premier League',
    95: 'Luxembourg National Division',
    96: 'A Lyga (LTU)',
    97: 'Virslīga (LVA)',
    98: 'Albanian Superliga',
    99: 'Cymru Premier (WAL)',
    100: 'Icelandic Premier League',
    101: 'League of Ireland Premier',
    102: 'Gibraltar Football League',
    103: 'Premijer Liga (BIH)',
    104: 'Armenian Premier League',
    105: 'Erovnuli Liga (GEO)',
    106: 'Kazakhstan Premier League',
    107: 'Luxembourg Division 1',
    108: 'Moldovan Super Liga',
    109: 'Montenegrin First League',
    # ═══ International Tournaments ═══
    208: 'FIFA World Cup',
    209: 'UEFA European Championship',
    210: 'Copa América',
    211: 'Africa Cup of Nations',
    212: 'AFC Asian Cup',
    213: 'CONCACAF Gold Cup',
    214: 'Olympic Football Tournament',
    215: 'FIFA Club World Cup',
    217: 'CONCACAF Nations League',
    218: 'African Nations Championship',
    219: 'Arabian Gulf Cup',
    221: 'World Cup Qualifiers UEFA',
    222: 'World Cup Qualifiers CONMEBOL',
    223: 'World Cup Qualifiers CONCACAF',
    224: 'World Cup Qualifiers CAF',
    225: 'World Cup Qualifiers AFC',
    226: 'World Cup Qualifiers OFC',
    # ═══ Americas ═══
    130: 'MLS (USA)',
    131: 'USL Championship',
    132: 'USL League One',
    133: 'Liga MX (MEX)',
    134: 'Liga de Expansión (MEX)',
    135: 'Campeonato Brasileiro Série A',
    136: 'Série B (BRA)',
    347: 'Série C (BRA)',
    348: 'Série D (BRA)',
    138: 'Argentine Primera División',
    139: 'Primera Nacional (ARG)',
    140: 'Chilean Primera División',
    141: 'Peruvian Primera División',
    142: 'Colombian Primera A',
    146: 'Uruguayan Primera División',
    147: 'Ecuadorian Serie A',
    148: 'Venezuelan Primera División',
    149: 'Paraguayan Primera División',
    150: 'Bolivian Primera División',
    152: 'Canadian Premier League',
    364: 'Copa Libertadores',
    365: 'Copa Sudamericana',
    366: 'Recopa Sudamericana',
    381: 'CONCACAF Champions Cup',
    382: 'Leagues Cup',
    # ═══ Asia ═══
    153: 'J1 League (JPN)',
    154: 'J2 League (JPN)',
    385: 'J3 League (JPN)',
    155: 'K League 1 (KOR)',
    156: 'K League 2 (KOR)',
    157: 'Chinese Super League',
    158: 'China League One',
    159: 'Indian Super League',
    160: 'I-League (IND)',
    161: 'Thai League 1',
    162: 'Saudi Pro League',
    163: 'UAE Pro League',
    164: 'Qatar Stars League',
    165: 'Iran Pro League',
    166: 'AFC Champions League Elite',
    422: 'AFC Champions League 2',
    167: 'AFC Cup',
    168: 'Uzbekistan Super League',
    169: 'V-League (VIE)',
    170: 'Malaysia Super League',
    171: 'Liga 1 (IDN)',
    172: 'Singapore Premier League',
    173: 'Hong Kong Premier League',
    384: 'J1 League',
    386: 'J3 League',
    421: 'AFC Champions League Elite',
    # ═══ Africa ═══
    178: 'CAF Champions League',
    179: 'CAF Confederation Cup',
    180: 'Egyptian Premier League',
    181: 'Botola Pro (MAR)',
    182: 'Algerian Ligue 1',
    183: 'Tunisian Ligue 1',
    184: 'South African PSL',
    185: 'Ghana Premier League',
    186: 'NPFL (NGA)',
    187: 'Kenyan Premier League',
    188: 'Linafoot (DRC)',
    189: 'Zambian Super League',
    190: 'Sudan Premier League',
    191: 'Ligue 1 (CIV)',
    192: 'Elite One (CMR)',
    193: 'Girabola (ANG)',
    194: 'Tanzania Premier League',
    195: 'Uganda Premier League',
    196: 'Ethiopian Premier League',
    197: 'Senegal Ligue 1',
    # ═══ Oceania ═══
    202: 'A-League Men (AUS)',
    203: 'New Zealand National League',
    204: 'OFC Champions League',
    494: 'OFC Nations Cup',
    # ═══ Domestic Cups ═══
    514: 'Copa del Rey',
    515: 'DFB-Pokal',
    516: 'FA Cup',
    517: 'Coupe de France',
    518: 'Coppa Italia',
    519: 'EFL Cup',
    520: 'Trophée des Champions',
    521: 'Supercopa de España',
    522: 'DFL-Supercup',
    523: 'Supercoppa Italiana',
    524: 'FA Community Shield',
    525: 'Taça de Portugal',
    526: 'KNVB Cup',
    527: 'Scottish Cup',
    528: 'Belgian Cup',
    529: 'Turkish Cup',
    530: 'Greek Cup',
    531: 'Austrian Cup',
    532: 'Swiss Cup',
    533: 'Danish Cup',
    534: 'Swedish Cup',
    535: 'Norwegian Cup',
    536: 'Polish Cup',
    537: 'Croatian Cup',
    538: 'Czech Cup',
    539: 'Hungarian Cup',
    540: 'Romanian Cup',
    541: 'Bulgarian Cup',
    593: 'Copa do Brasil',
    594: 'Copa Argentina',
    605: 'US Open Cup',
    606: 'J.League Cup',
    607: "Emperor's Cup",
    608: 'Korean FA Cup',
    609: 'Chinese FA Cup',
    610: 'Saudi King Cup',
    # ═══ Friendlies ═══
    851: 'International Friendlies',
    852: 'International Friendlies Women',
    853: 'Club Friendlies',
    854: 'U21 Friendlies',
    855: 'U20 Friendlies',
    # ═══ Women's Competitions ═══
    231: 'FA WSL (ENG)',
    232: 'Division 1 Féminine (FRA)',
    233: 'Frauen-Bundesliga (GER)',
    234: 'Primera División Femenina (ESP)',
    235: 'Serie A Femminile (ITA)',
    236: 'NWSL (USA)',
    237: 'Women Super League (NED)',
    238: 'Damallsvenskan (SWE)',
    239: 'Toppserien (NOR)',
    241: 'FIFA Womens World Cup',
    577: 'UEFA Womens Champions League',
}

# FBref competition slugs
FBREF_COMPS = {
    'Premier League': '/en/comps/9/Premier-League',
    'LaLiga': '/en/comps/12/La-Liga',
    'Bundesliga': '/en/comps/20/Bundesliga',
    'Serie A': '/en/comps/11/Serie-A',
    'Ligue 1': '/en/comps/13/Ligue-1',
    'Championship': '/en/comps/10/Championship',
    'LaLiga2': '/en/comps/17/Segunda-Division',
    '2. Bundesliga': '/en/comps/33/2-Bundesliga',
    'Serie B': '/en/comps/18/Serie-B',
    'Ligue 2': '/en/comps/60/Ligue-2',
    'Primeira Liga': '/en/comps/32/Primeira-Liga',
    'Eredivisie': '/en/comps/23/Eredivisie',
    'Belgian Pro League': '/en/comps/37/Belgian-Pro-League',
    'Scottish Premiership': '/en/comps/40/Scottish-Premiership',
    'Süper Lig': '/en/comps/26/Super-Lig',
    'Russian Premier League': '/en/comps/30/Russian-Premier-League',
    'Ukrainian Premier League': '/en/comps/44/Ukrainian-Premier-League',
    'Greek Super League': '/en/comps/24/Greek-Super-League',
    'Czech First League': '/en/comps/43/Czech-First-League',
    'Ekstraklasa': '/en/comps/36/Ekstraklasa',
    'Swiss Super League': '/en/comps/56/Swiss-Super-League',
    'Allsvenskan': '/en/comps/23/Allsvenskan',
    'Eliteserien': '/en/comps/28/Eliteserien',
    'Danish Superliga': '/en/comps/29/Danish-Superliga',
    'MLS': '/en/comps/22/Major-League-Soccer',
    'Liga MX': '/en/comps/31/Liga-MX',
    'Brasileirão Série A': '/en/comps/24/Campeonato-Brasileiro-Serie-A',
    'Argentine Primera División': '/en/comps/21/Argentine-Primera-Division',
    'J1 League': '/en/comps/25/J1-League',
    'K League 1': '/en/comps/55/K-League-1',
    'Chinese Super League': '/en/comps/33/Chinese-Super-League',
    'A-League': '/en/comps/60/A-League',
    'Indian Super League': '/en/comps/66/Indian-Super-League',
    'UEFA Champions League': '/en/comps/8/Champions-League',
    'UEFA Europa League': '/en/comps/19/Europa-League',
    'FA Cup': '/en/comps/1/FA-Cup',
    'DFB-Pokal': '/en/comps/15/DFB-Pokal',
    'Coppa Italia': '/en/comps/16/Coppa-Italia',
    'Copa del Rey': '/en/comps/5/Copa-del-Rey',
    'Coupe de France': '/en/comps/52/Coupe-de-France',
    'EFL Cup': '/en/comps/57/EFL-Cup',
    'MLS Cup': '/en/comps/22/Major-League-Soccer',
    'FIFA World Cup': '/en/comps/1/World-Cup',
    'UEFA European Championship': '/en/comps/12/European-Championship',
    'Copa América': '/en/comps/19/Copa-America',
    'Africa Cup of Nations': '/en/comps/72/Africa-Cup-of-Nations',
    'AFC Asian Cup': '/en/comps/73/AFC-Asian-Cup',
    'CONCACAF Gold Cup': '/en/comps/74/Gold-Cup',
}

# Understat leagues
UNDERSTAT_LEAGUES = ['EPL', 'La_Liga', 'Bundesliga', 'Serie_A', 'Ligue_1']

# StatsBomb competitions to target for additional data
STATSBOMB_TARGETS = [
    (1, 1, "World Cup", "2018"),
    (1, 3, "World Cup", "2022"),
    (1, 55, "World Cup", "2026"),
    (3, 16, "UEFA Euro", "2020"),
    (3, 84, "UEFA Euro", "2024"),
    (16, 56, "Africa Cup of Nations", "2021"),
    (16, 91, "Africa Cup of Nations", "2023"),
    (43, 79, "FIFA Club World Cup", "2023"),
    (2, 27, "Premier League", "2015/2016"),
    (2, 44, "Premier League", "2016/2017"),
    (2, 79, "Premier League", "2017/2018"),
    (2, 1, "Premier League", "2018/2019"),
    (2, 3, "Premier League", "2019/2020"),
    (2, 4, "Premier League", "2020/2021"),
    (2, 27, "Premier League", "2021/2022"),
    (2, 44, "Premier League", "2022/2023"),
    (2, 79, "Premier League", "2023/2024"),
    (11, 90, "La Liga", "2019/2020"),
    (11, 4, "La Liga", "2020/2021"),
    (7, 41, "Ligue 1", "2022/2023"),
    (7, 42, "Ligue 1", "2021/2022"),
    (9, 281, "Bundesliga", "2023/2024"),
    (12, 28, "Serie A", "2019/2020"),
    (12, 34, "Serie A", "2021/2022"),
    (12, 43, "Serie A", "2022/2023"),
    (44, 1, "Womens World Cup", "2019"),
    (44, 84, "Womens World Cup", "2023"),
    (5, 12, "UEFA Champions League", "2018/2019"),
    (5, 18, "UEFA Champions League", "2020/2021"),
    (5, 21, "UEFA Champions League", "2021/2022"),
    (5, 30, "UEFA Champions League", "2022/2023"),
    (5, 27, "UEFA Champions League", "2023/2024"),
    (21, 21, "Copa Libertadores", "2020"),
    (21, 25, "Copa Libertadores", "2021"),
    (21, 28, "Copa Libertadores", "2022"),
    (21, 30, "Copa Libertadores", "2023"),
    (22, 8, "Copa América", "2019"),
    (22, 30, "Copa América", "2021"),
    (22, 91, "Copa América", "2024"),
    (25, 1, "AFC Asian Cup", "2019"),
    (25, 91, "AFC Asian Cup", "2023"),
    (15, 2, "CONCACAF Gold Cup", "2019"),
    (15, 5, "CONCACAF Gold Cup", "2021"),
    (15, 91, "CONCACAF Gold Cup", "2023"),
]


# ═══════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════

def log(msg: str, level: str = 'INFO'):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{ts}] [{level}] {msg}')
    # Also write to log file
    logfile = os.path.join(HEIST_LOG_DIR, f'heist_{datetime.now().strftime("%Y%m%d")}.log')
    try:
        with open(logfile, 'a', encoding='utf-8') as f:
            f.write(f'[{ts}] [{level}] {msg}\n')
    except:
        pass


def update_progress(markdown_content: str):
    """Update the progress markdown file for the orchestrator."""
    try:
        os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
    except Exception as e:
        log(f'Failed to update progress: {e}', 'ERROR')


# ═══════════════════════════════════════════════════════════════════════
# DATABASE LAYER
# ═══════════════════════════════════════════════════════════════════════

class HeistDB:
    """Central database manager for the heist engine."""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._conn = None
    
    def connect(self) -> sqlite3.Connection:
        if self._conn is not None:
            try:
                self._conn.execute('SELECT 1')
                return self._conn
            except:
                pass
        self._conn = sqlite3.connect(self.db_path, timeout=60)
        self._conn.execute('PRAGMA journal_mode=WAL')
        self._conn.execute('PRAGMA synchronous=OFF')
        self._conn.execute('PRAGMA cache_size=-256000')
        self._conn.execute('PRAGMA temp_store=MEMORY')
        self._conn.execute('PRAGMA mmap_size=268435456')
        self._init_tables()
        return self._conn
    
    def _init_tables(self):
        conn = self._conn
        
        # Agent4 main tables
        conn.execute('''CREATE TABLE IF NOT EXISTS agent4_matches (
            match_id INTEGER PRIMARY KEY,
            source TEXT NOT NULL,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            home_score INTEGER,
            away_score INTEGER,
            competition TEXT,
            competition_id INTEGER,
            season TEXT,
            match_date TEXT,
            match_timestamp INTEGER,
            is_finished INTEGER DEFAULT 0,
            home_xg REAL,
            away_xg REAL,
            home_shots INTEGER,
            away_shots INTEGER,
            home_sot INTEGER,
            away_sot INTEGER,
            home_possession REAL,
            away_possession REAL,
            home_corners INTEGER,
            away_corners INTEGER,
            home_fouls INTEGER,
            away_fouls INTEGER,
            home_yellow INTEGER,
            away_yellow INTEGER,
            home_red INTEGER,
            away_red INTEGER,
            home_formation TEXT,
            away_formation TEXT,
            attendance INTEGER,
            venue TEXT,
            referee TEXT,
            has_lineups INTEGER DEFAULT 0,
            has_stats INTEGER DEFAULT 0,
            has_shotmap INTEGER DEFAULT 0,
            raw_data TEXT,
            scraped_at TEXT,
            UNIQUE(source, match_id)
        )''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS agent4_teams (
            team_id INTEGER,
            source TEXT,
            name TEXT,
            short_name TEXT,
            country TEXT,
            logo_url TEXT,
            venue_name TEXT,
            venue_capacity INTEGER,
            founded INTEGER,
            raw_data TEXT,
            scraped_at TEXT,
            PRIMARY KEY(source, team_id)
        )''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS agent4_players (
            player_id INTEGER,
            source TEXT,
            name TEXT,
            team_id INTEGER,
            position TEXT,
            jersey_number INTEGER,
            nationality TEXT,
            birth_date TEXT,
            height INTEGER,
            weight INTEGER,
            market_value REAL,
            market_value_currency TEXT,
            raw_data TEXT,
            scraped_at TEXT,
            PRIMARY KEY(source, player_id)
        )''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS agent4_injuries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            player_id INTEGER,
            player_name TEXT,
            team_id INTEGER,
            team_name TEXT,
            injury_type TEXT,
            injury_severity TEXT,
            expected_return TEXT,
            injury_date TEXT,
            status TEXT,
            description TEXT,
            scraped_at TEXT,
            UNIQUE(source, player_id, injury_date)
        )''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS agent4_lineups (
            match_id INTEGER,
            source TEXT,
            team_id INTEGER,
            team_name TEXT,
            formation TEXT,
            starting_xi TEXT,
            substitutes TEXT,
            missing_players TEXT,
            expected_lineup TEXT,
            scraped_at TEXT,
            PRIMARY KEY(source, match_id, team_id)
        )''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS agent4_shotmaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            match_id INTEGER,
            team_id INTEGER,
            player_name TEXT,
            player_id INTEGER,
            x REAL, y REAL,
            expected_goals REAL,
            expected_goals_on_target REAL,
            shot_type TEXT,
            situation TEXT,
            is_goal INTEGER DEFAULT 0,
            is_on_target INTEGER DEFAULT 0,
            minute INTEGER,
            body_part TEXT,
            assist_method TEXT,
            scraped_at TEXT
        )''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS agent4_standings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            competition_id INTEGER,
            competition_name TEXT,
            season TEXT,
            team_name TEXT,
            team_id INTEGER,
            rank INTEGER,
            played INTEGER,
            wins INTEGER,
            draws INTEGER,
            losses INTEGER,
            goals_for INTEGER,
            goals_against INTEGER,
            points INTEGER,
            form TEXT,
            scraped_at TEXT,
            UNIQUE(source, competition_id, season, team_id)
        )''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS agent4_heist_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            operation TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            total_items INTEGER DEFAULT 0,
            completed_items INTEGER DEFAULT 0,
            errors INTEGER DEFAULT 0,
            started_at TEXT,
            completed_at TEXT,
            details TEXT,
            UNIQUE(source, operation)
        )''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS agent4_competition_seasons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            competition_id INTEGER,
            competition_name TEXT,
            season TEXT,
            season_start TEXT,
            season_end TEXT,
            match_count INTEGER DEFAULT 0,
            scraped_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            UNIQUE(source, competition_id, season)
        )''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS agent4_team_mapping (
            local_name TEXT,
            source TEXT,
            source_name TEXT,
            source_id INTEGER,
            confidence REAL DEFAULT 1.0,
            PRIMARY KEY(local_name, source)
        )''')
        
        # Indexes
        for idx in [
            'CREATE INDEX IF NOT EXISTS idx_agent4_matches_date ON agent4_matches(match_date)',
            'CREATE INDEX IF NOT EXISTS idx_agent4_matches_comp ON agent4_matches(competition)',
            'CREATE INDEX IF NOT EXISTS idx_agent4_matches_source ON agent4_matches(source)',
            'CREATE INDEX IF NOT EXISTS idx_agent4_matches_team ON agent4_matches(home_team, away_team)',
            'CREATE INDEX IF NOT EXISTS idx_agent4_injuries_team ON agent4_injuries(team_id)',
            'CREATE INDEX IF NOT EXISTS idx_agent4_injuries_player ON agent4_injuries(player_id)',
            'CREATE INDEX IF NOT EXISTS idx_agent4_players_team ON agent4_players(team_id)',
            'CREATE INDEX IF NOT EXISTS idx_agent4_lineups_match ON agent4_lineups(match_id)',
            'CREATE INDEX IF NOT EXISTS idx_agent4_shotmaps_match ON agent4_shotmaps(match_id)',
            'CREATE INDEX IF NOT EXISTS idx_agent4_standings_comp ON agent4_standings(competition_id, season)',
            'CREATE INDEX IF NOT EXISTS idx_agent4_team_mapping_name ON agent4_team_mapping(local_name)',
        ]:
            try:
                conn.execute(idx)
            except:
                pass
        
        conn.commit()
    
    def store_match(self, source: str, match: Dict) -> bool:
        """Store a match record. Returns True if new/updated."""
        conn = self.connect()
        try:
            mid = match.get('match_id', match.get('id', 0))
            if not mid:
                return False
            
            conn.execute('''INSERT OR REPLACE INTO agent4_matches VALUES (
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                ?,?,?,?,?,?,?,?,?,?,?,?)''', (
                mid, source,
                str(match.get('home_team', match.get('home_name', ''))),
                str(match.get('away_team', match.get('away_name', ''))),
                match.get('home_score'), match.get('away_score'),
                str(match.get('competition', match.get('league_name', match.get('tournament', '')))),
                match.get('competition_id', match.get('league_id', match.get('unique_tournament_id'))),
                str(match.get('season', '')),
                str(match.get('match_date', match.get('date', match.get('utc_time', '')))),
                match.get('match_timestamp', match.get('start_timestamp', 0)),
                1 if match.get('is_finished', match.get('finished', False)) else 0,
                match.get('home_xg'), match.get('away_xg'),
                match.get('home_shots'), match.get('away_shots'),
                match.get('home_sot'), match.get('away_sot'),
                match.get('home_possession'), match.get('away_possession'),
                match.get('home_corners'), match.get('away_corners'),
                match.get('home_fouls'), match.get('away_fouls'),
                match.get('home_yellow'), match.get('away_yellow'),
                match.get('home_red'), match.get('away_red'),
                str(match.get('home_formation', '')), str(match.get('away_formation', '')),
                match.get('attendance'), str(match.get('venue', '')), str(match.get('referee', '')),
                1 if match.get('has_lineups') else 0,
                1 if match.get('has_stats') else 0,
                1 if match.get('has_shotmap') else 0,
                json.dumps(match.get('raw_data', {})),
                datetime.now(timezone.utc).isoformat()
            ))
            conn.commit()
            return True
        except Exception as e:
            log(f'DB store_match error: {e}', 'ERROR')
            return False
    
    def store_team(self, source: str, team: Dict) -> bool:
        conn = self.connect()
        try:
            tid = team.get('team_id', team.get('id', 0))
            name = str(team.get('name', team.get('team_name', '')))
            conn.execute('''INSERT OR REPLACE INTO agent4_teams VALUES (?,?,?,?,?,?,?,?,?,?,?)''', (
                tid, source, name,
                str(team.get('short_name', team.get('shortName', ''))),
                str(team.get('country', '')),
                str(team.get('logo_url', team.get('logo', ''))),
                str(team.get('venue_name', team.get('venue', {}).get('name', ''))),
                team.get('venue', {}).get('capacity', team.get('venue_capacity')),
                team.get('founded', 0),
                json.dumps(team),
                datetime.now(timezone.utc).isoformat()
            ))
            conn.commit()
            return True
        except Exception as e:
            log(f'DB store_team error: {e}', 'ERROR')
            return False
    
    def store_player(self, source: str, player: Dict) -> bool:
        conn = self.connect()
        try:
            pid = player.get('player_id', player.get('id', 0))
            conn.execute('''INSERT OR REPLACE INTO agent4_players VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                pid, source,
                str(player.get('name', player.get('player_name', ''))),
                player.get('team_id', 0),
                str(player.get('position', '')),
                player.get('jersey_number', player.get('jerseyNumber', player.get('shirtNumber', 0))),
                str(player.get('nationality', '')),
                str(player.get('birth_date', player.get('dateOfBirth', ''))),
                player.get('height', 0), player.get('weight', 0),
                player.get('market_value', player.get('marketValue', 0)),
                str(player.get('market_value_currency', 'EUR')),
                json.dumps(player),
                datetime.now(timezone.utc).isoformat()
            ))
            conn.commit()
            return True
        except Exception as e:
            log(f'DB store_player error: {e}', 'ERROR')
            return False
    
    def store_injury(self, source: str, injury: Dict) -> bool:
        conn = self.connect()
        try:
            conn.execute('''INSERT OR REPLACE INTO agent4_injuries 
                (source, player_id, player_name, team_id, team_name, injury_type,
                 injury_severity, expected_return, injury_date, status, description, scraped_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''', (
                source,
                injury.get('player_id', 0),
                str(injury.get('player_name', '')),
                injury.get('team_id', 0),
                str(injury.get('team_name', '')),
                str(injury.get('injury_type', '')),
                str(injury.get('injury_severity', '')),
                str(injury.get('expected_return', '')),
                str(injury.get('injury_date', datetime.now().strftime('%Y-%m-%d'))),
                str(injury.get('status', 'unknown')),
                str(injury.get('description', '')),
                datetime.now(timezone.utc).isoformat()
            ))
            conn.commit()
            return True
        except Exception as e:
            log(f'DB store_injury error: {e}', 'ERROR')
            return False
    
    def store_lineup(self, source: str, lineup: Dict) -> bool:
        conn = self.connect()
        try:
            mid = lineup.get('match_id', 0)
            tid = lineup.get('team_id', lineup.get('home_id', 0))
            conn.execute('''INSERT OR REPLACE INTO agent4_lineups VALUES (?,?,?,?,?,?,?,?,?,?)''', (
                mid, source, tid,
                str(lineup.get('team_name', '')),
                str(lineup.get('formation', '')),
                json.dumps(lineup.get('starting_xi', [])),
                json.dumps(lineup.get('substitutes', [])),
                json.dumps(lineup.get('missing_players', [])),
                json.dumps(lineup.get('expected_lineup', [])),
                datetime.now(timezone.utc).isoformat()
            ))
            conn.commit()
            return True
        except Exception as e:
            log(f'DB store_lineup error: {e}', 'ERROR')
            return False
    
    def store_shotmap(self, source: str, shotmap_records: List[Dict]) -> int:
        conn = self.connect()
        count = 0
        try:
            for s in shotmap_records:
                conn.execute('''INSERT OR REPLACE INTO agent4_shotmaps
                    (source, match_id, team_id, player_name, player_id,
                     x, y, expected_goals, expected_goals_on_target,
                     shot_type, situation, is_goal, is_on_target,
                     minute, body_part, assist_method, scraped_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                    source, s.get('match_id', 0), s.get('team_id', 0),
                    str(s.get('player_name', '')), s.get('player_id', 0),
                    s.get('x', 0), s.get('y', 0),
                    s.get('expected_goals', s.get('expectedGoals', 0)),
                    s.get('expected_goals_on_target', s.get('expectedGoalsOnTarget', 0)),
                    str(s.get('shot_type', s.get('shotType', ''))),
                    str(s.get('situation', '')),
                    1 if s.get('is_goal', s.get('isGoal', False)) else 0,
                    1 if s.get('is_on_target', s.get('onTarget', False)) else 0,
                    s.get('minute', 0),
                    str(s.get('body_part', s.get('bodyPart', ''))),
                    str(s.get('assist_method', '')),
                    datetime.now(timezone.utc).isoformat()
                ))
                count += 1
            conn.commit()
        except Exception as e:
            log(f'DB store_shotmap error: {e}', 'ERROR')
        return count
    
    def store_standings(self, source: str, standings_records: List[Dict]) -> int:
        conn = self.connect()
        count = 0
        try:
            for r in standings_records:
                conn.execute('''INSERT OR REPLACE INTO agent4_standings
                    (source, competition_id, competition_name, season,
                     team_name, team_id, rank, played, wins, draws, losses,
                     goals_for, goals_against, points, form, scraped_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                    source,
                    r.get('competition_id', 0),
                    str(r.get('competition_name', '')),
                    str(r.get('season', '')),
                    str(r.get('team_name', '')),
                    r.get('team_id', 0),
                    r.get('rank', 0), r.get('played', 0),
                    r.get('wins', 0), r.get('draws', 0), r.get('losses', 0),
                    r.get('goals_for', 0), r.get('goals_against', 0),
                    r.get('points', 0), str(r.get('form', '')),
                    datetime.now(timezone.utc).isoformat()
                ))
                count += 1
            conn.commit()
        except Exception as e:
            log(f'DB store_standings error: {e}', 'ERROR')
        return count
    
    def update_progress(self, source: str, operation: str, status: str = 'pending',
                        total: int = 0, completed: int = 0, errors: int = 0,
                        details: str = ''):
        conn = self.connect()
        now = datetime.now(timezone.utc).isoformat()
        try:
            existing = conn.execute(
                'SELECT status, started_at FROM agent4_heist_progress WHERE source=? AND operation=?',
                (source, operation)
            ).fetchone()
            if existing:
                started = existing[1] if existing[0] == 'pending' else now
                conn.execute('''UPDATE agent4_heist_progress SET status=?, total_items=?,
                    completed_items=?, errors=?, completed_at=?, details=?, started_at=COALESCE(started_at,?)
                    WHERE source=? AND operation=?''',
                    (status, total, completed, errors, now if status in ('completed','failed') else None,
                     started, details, source, operation))
            else:
                conn.execute('''INSERT INTO agent4_heist_progress 
                    (source, operation, status, total_items, completed_items, errors, started_at, details)
                    VALUES (?,?,?,?,?,?,?,?)''',
                    (source, operation, status, total, completed, errors, now, details))
            conn.commit()
        except Exception as e:
            log(f'DB update_progress error: {e}', 'ERROR')
    
    def add_team_mapping(self, local_name: str, source: str, source_name: str,
                         source_id: int, confidence: float = 1.0):
        conn = self.connect()
        try:
            conn.execute('''INSERT OR REPLACE INTO agent4_team_mapping VALUES (?,?,?,?,?)''',
                         (local_name, source, source_name, source_id, confidence))
            conn.commit()
        except Exception as e:
            log(f'DB add_team_mapping error: {e}', 'ERROR')
    
    def get_matches_by_source(self, source: str, limit: int = 100000) -> List[Dict]:
        conn = self.connect()
        rows = conn.execute(
            'SELECT * FROM agent4_matches WHERE source=? ORDER BY match_date DESC LIMIT ?',
            (source, limit)
        ).fetchall()
        cols = [d[0] for d in conn.execute('PRAGMA table_info(agent4_matches)').fetchall()]
        return [dict(zip(cols, r)) for r in rows]
    
    def get_match_count_by_source(self, source: str) -> int:
        conn = self.connect()
        row = conn.execute('SELECT COUNT(*) FROM agent4_matches WHERE source=?', (source,)).fetchone()
        return row[0] if row else 0
    
    def get_injuries_by_team(self, team_id: int, source: str = 'transfermarkt') -> List[Dict]:
        conn = self.connect()
        rows = conn.execute(
            '''SELECT * FROM agent4_injuries WHERE team_id=? AND source=?
               ORDER BY expected_return ASC''',
            (team_id, source)
        ).fetchall()
        cols = [d[0] for d in conn.execute('PRAGMA table_info(agent4_injuries)').fetchall()]
        return [dict(zip(cols, r)) for r in rows]
    
    def get_players_by_team(self, team_id: int, source: str = 'transfermarkt') -> List[Dict]:
        conn = self.connect()
        rows = conn.execute(
            '''SELECT * FROM agent4_players WHERE team_id=? AND source=?
               ORDER BY position, jersey_number''',
            (team_id, source)
        ).fetchall()
        cols = [d[0] for d in conn.execute('PRAGMA table_info(agent4_players)').fetchall()]
        return [dict(zip(cols, r)) for r in rows]
    
    def close(self):
        if self._conn:
            try:
                self._conn.close()
            except:
                pass
            self._conn = None


# ═══════════════════════════════════════════════════════════════════════
# CURL_CFFI HTTP SESSION MANAGER
# ═══════════════════════════════════════════════════════════════════════

class CurlSession:
    """Smart HTTP session manager using curl_cffi with rotation & retry."""
    
    def __init__(self):
        self._last_req = 0
        self._impersonate_idx = 0
        self._consecutive_fails = 0
    
    def _rotate_impersonate(self) -> str:
        implist = IMPRESONATE_OPTIONS
        self._impersonate_idx = (self._impersonate_idx + 1) % len(implist)
        return implist[self._impersonate_idx]
    
    def _get_headers(self, referer: str = None) -> Dict:
        return {
            'User-Agent': random.choice(UA_POOL),
            'Accept': 'application/json, text/html, application/xhtml+xml, */*',
            'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Origin': 'https://www.google.com',
            'Referer': referer or 'https://www.google.com/',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        }
    
    def fetch(self, url: str, impersonate: str = None, referer: str = None,
              timeout: int = 30, retries: int = 3, params: Dict = None,
              method: str = 'GET', data: Any = None) -> Optional[Any]:
        """Fetch a URL with curl_cffi. Returns response object or None."""
        if not CURL_OK:
            log('curl_cffi not installed, cannot fetch!', 'CRITICAL')
            return None
        
        # Rate limiting
        now = time.time()
        elapsed = now - self._last_req
        delay = MIN_DELAY + random.random() * (MAX_DELAY - MIN_DELAY)
        if elapsed < delay:
            time.sleep(delay - elapsed)
        
        headers = self._get_headers(referer)
        
        if impersonate is None:
            impersonate = random.choice(IMPRESONATE_OPTIONS)
        
        for attempt in range(retries):
            try:
                if self._consecutive_fails > 5:
                    # Rotate impersonation to avoid fingerprinting
                    impersonate = self._rotate_impersonate()
                    self._consecutive_fails = 0
                
                if method.upper() == 'GET':
                    r = curl_requests.get(
                        url, headers=headers, impersonate=impersonate,
                        timeout=timeout, params=params
                    )
                else:
                    r = curl_requests.post(
                        url, headers=headers, impersonate=impersonate,
                        timeout=timeout, json=data
                    )
                
                self._last_req = time.time()
                
                if r.status_code == 200:
                    self._consecutive_fails = 0
                    return r
                elif r.status_code == 403:
                    # Cloudflare block - rotate and retry
                    self._consecutive_fails += 1
                    log(f'HTTP 403 for {url[:80]} (attempt {attempt+1})', 'WARN')
                    time.sleep(1.0 * (attempt + 1))
                elif r.status_code == 429:
                    # Rate limited
                    retry_after = int(r.headers.get('Retry-After', 5))
                    log(f'Rate limited for {url[:60]}, waiting {retry_after}s', 'WARN')
                    time.sleep(retry_after)
                elif r.status_code == 404:
                    log(f'HTTP 404 for {url[:80]}', 'WARN')
                    return None
                else:
                    log(f'HTTP {r.status_code} for {url[:80]}', 'WARN')
                    self._consecutive_fails += 1
                    time.sleep(0.5 * (attempt + 1))
                    
            except Exception as e:
                self._consecutive_fails += 1
                log(f'Fetch error [{url[:60]}]: {str(e)[:100]} (attempt {attempt+1})', 'WARN')
                if attempt < retries - 1:
                    time.sleep(1.0 * (attempt + 1) + random.random())
        
        return None
    
    def fetch_json(self, url: str, **kwargs) -> Optional[Dict]:
        """Fetch and parse JSON response."""
        r = self.fetch(url, **kwargs)
        if r is None:
            return None
        try:
            return r.json()
        except Exception as e:
            log(f'JSON parse error for {url[:60]}: {e}', 'ERROR')
            return None
    
    def fetch_html(self, url: str, **kwargs) -> Optional[str]:
        """Fetch and return HTML text."""
        r = self.fetch(url, **kwargs)
        if r is None:
            return None
        try:
            return r.text
        except Exception as e:
            log(f'HTML read error for {url[:60]}: {e}', 'ERROR')
            return None
    
    def fetch_soup(self, url: str, **kwargs) -> Optional[Any]:
        """Fetch and parse HTML with BeautifulSoup."""
        html = self.fetch_html(url, **kwargs)
        if html is None or not BS4_OK:
            return None
        try:
            return BeautifulSoup(html, 'lxml' if LXML_OK else 'html.parser')
        except Exception as e:
            log(f'Soup parse error: {e}', 'ERROR')
            return None


# ═══════════════════════════════════════════════════════════════════════
# FOTMOB HEIST ENGINE
# ═══════════════════════════════════════════════════════════════════════

class FotMobHeist:
    """FotMob API scraper using curl_cffi Next.js data route exploit."""
    
    BASE = 'https://www.fotmob.com'
    
    def __init__(self, session: CurlSession, db: HeistDB):
        self.session = session
        self.db = db
        self._build_id = None
    
    def get_build_id(self) -> str:
        """Extract the Next.js build ID from FotMob."""
        if self._build_id:
            return self._build_id
        
        html = self.session.fetch_html(f'{self.BASE}/', impersonate='chrome120')
        if html:
            match = re.search(r'"buildId":"([^"]+)"', html)
            if match:
                self._build_id = match.group(1)
                log(f'FotMob build ID: {self._build_id}')
                return self._build_id
        
        self._build_id = 'p3C1aZo1q8s-3rwiYMc3f'
        log(f'FotMob build ID (fallback): {self._build_id}')
        return self._build_id
    
    def fetch_league_data(self, league_id: int, season: str = None) -> Optional[Dict]:
        """Fetch league data via Next.js data route."""
        build_id = self.get_build_id()
        
        params = 'tab=overview&type=league&timeZone=UTC'
        if season:
            params += f'&season={season}'
        
        url = f'{self.BASE}/_next/data/{build_id}/leagues/{league_id}.json?{params}'
        
        pp = self.session.fetch_json(url, impersonate='chrome120',
                                      referer=f'{self.BASE}/leagues/{league_id}')
        if pp and 'pageProps' in pp:
            return pp['pageProps']
        
        # Fallback: scrape the HTML page
        html = self.session.fetch_html(f'{self.BASE}/leagues/{league_id}',
                                        impersonate='chrome120')
        if html:
            match = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
            if match:
                try:
                    nd = json.loads(match.group(1))
                    return nd.get('props', {}).get('pageProps', {})
                except:
                    pass
        return None
    
    def fetch_match_detail(self, match_id: int) -> Optional[Dict]:
        """Fetch match details via Next.js data route."""
        build_id = self.get_build_id()
        url = f'{self.BASE}/_next/data/{build_id}/match/{match_id}.json'
        pp = self.session.fetch_json(url, impersonate='chrome120',
                                      referer=f'{self.BASE}/match/{match_id}')
        if pp and 'pageProps' in pp:
            return pp['pageProps']
        
        # Fallback: scrape HTML
        html = self.session.fetch_html(f'{self.BASE}/match/{match_id}',
                                        impersonate='chrome120')
        if html:
            match = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
            if match:
                try:
                    nd = json.loads(match.group(1))
                    return nd.get('props', {}).get('pageProps', {})
                except:
                    pass
        return None
    
    def fetch_team_squad(self, team_id: int) -> Optional[Dict]:
        """Fetch team squad data."""
        build_id = self.get_build_id()
        url = f'{self.BASE}/_next/data/{build_id}/teams/{team_id}.json'
        pp = self.session.fetch_json(url, impersonate='chrome120',
                                      referer=f'{self.BASE}/teams/{team_id}')
        if pp and 'pageProps' in pp:
            return pp['pageProps']
        return None
    
    def fetch_player_info(self, player_id: int) -> Optional[Dict]:
        """Fetch player info from FotMob."""
        url = f'{self.BASE}/api/playerData?id={player_id}'
        return self.session.fetch_json(url, impersonate='chrome120',
                                        referer=f'{self.BASE}/player/{player_id}')
    
    def extract_matches(self, page_props: Dict, league_id: int,
                        league_name: str = '', season: str = '') -> List[Dict]:
        """Extract matches from league page props."""
        matches = []
        
        # Try all possible match locations
        overview = page_props.get('overview', {})
        if isinstance(overview, dict):
            for key in ['leagueOverviewMatches', 'matches', 'fixtures', 'results']:
                raw = overview.get(key, [])
                if isinstance(raw, list):
                    for m in raw:
                        if isinstance(m, dict):
                            matches.append(m)
        
        # Try fixtures key
        fixtures = page_props.get('fixtures', {})
        if isinstance(fixtures, dict):
            for key in fixtures:
                raw = fixtures[key]
                if isinstance(raw, list):
                    for m in raw:
                        if isinstance(m, dict):
                            matches.append(m)
        
        # Try matches dict
        matches_dict = page_props.get('matches', {})
        if isinstance(matches_dict, dict):
            for key in ['allMatches', 'finished', 'upcoming', 'results']:
                raw = matches_dict.get(key, [])
                if isinstance(raw, list):
                    for m in raw:
                        if isinstance(m, dict):
                            matches.append(m)
        
        return matches
    
    def parse_match(self, m: Dict, league_name: str = '', season: str = '') -> Optional[Dict]:
        """Parse a FotMob match into standardized format."""
        try:
            home = m.get('home', {})
            away = m.get('away', {})
            
            home_id = home.get('id', home.get('teamId', 0))
            away_id = away.get('id', away.get('teamId', 0))
            home_name = home.get('name', home.get('shortName', ''))
            away_name = away.get('name', away.get('shortName', ''))
            
            # Score
            home_score = m.get('home', {}).get('score')
            away_score = m.get('away', {}).get('score')
            if home_score is None:
                home_score = m.get('homeScore')
            if away_score is None:
                away_score = m.get('awayScore')
            
            # Status
            status = m.get('status', {})
            if isinstance(status, dict):
                is_finished = status.get('finished', False) or status.get('cancelled', False)
                utc_time = status.get('utcTime', status.get('date', ''))
            else:
                is_finished = m.get('finished', False)
                utc_time = m.get('matchDateUTC', m.get('date', ''))
            
            # League info
            league = m.get('league', {})
            lid = None
            lname = league_name
            if isinstance(league, dict):
                lid = league.get('id', m.get('leagueId'))
                lname = league.get('name', lname)
            
            match_id = m.get('id', m.get('matchId', 0))
            page_url = m.get('pageUrl', '')
            
            return {
                'source': 'fotmob',
                'match_id': match_id,
                'home_team': home_name,
                'away_team': away_name,
                'home_id': home_id,
                'away_id': away_id,
                'home_score': home_score,
                'away_score': away_score,
                'competition_id': lid or 0,
                'competition': lname,
                'season': season,
                'match_date': utc_time,
                'is_finished': bool(is_finished),
                'page_url': page_url,
            }
        except Exception as e:
            log(f'FotMob parse_match error: {e}', 'ERROR')
            return None
    
    def scrape_league(self, league_id: int, season: str = None,
                      store_matches: bool = True) -> Dict[str, Any]:
        """Scrape a single league and extract all matches."""
        league_name = FOTMOB_LEAGUES.get(league_id, f'League {league_id}')
        log(f'Scraping {league_name} (ID {league_id})')
        
        pp = self.fetch_league_data(league_id, season)
        if not pp:
            log(f'  Failed to fetch {league_name}', 'WARN')
            return {'league_id': league_id, 'league_name': league_name, 'total_matches': 0, 'matches': []}
        
        # Extract and save standings/teams
        self._save_league_teams(league_id, pp, league_name)
        self._save_league_standings(league_id, pp, league_name, season or '')
        
        # Extract matches
        raw_matches = self.extract_matches(pp, league_id, league_name, season or '')
        parsed_matches = []
        for m in raw_matches:
            pm = self.parse_match(m, league_name, season or '')
            if pm and pm.get('match_id'):
                parsed_matches.append(pm)
                if store_matches:
                    self.db.store_match('fotmob', pm)
        
        # Cache league overview data
        self.db.connect().execute(
            'INSERT OR REPLACE INTO fotmob_league_cache VALUES (?,?,?,?)',
            (league_id, season or 'overview', json.dumps(pp),
             datetime.now(timezone.utc).isoformat())
        )
        try:
            self.db.connect().commit()
        except:
            pass
        
        result = {
            'league_id': league_id,
            'league_name': league_name,
            'total_matches': len(parsed_matches),
            'matches': parsed_matches,
        }
        
        log(f'  → {len(parsed_matches)} matches extracted')
        return result
    
    def _save_league_teams(self, league_id: int, pp: Dict, league_name: str):
        """Extract teams from standings and save to team mapping."""
        try:
            conn = self.db.connect()
            
            # Try various locations for table data
            table_data = pp.get('table', [])
            if isinstance(table_data, list):
                for group in table_data:
                    data_dict = group.get('data', {})
                    if isinstance(data_dict, dict):
                        table = data_dict.get('table', {})
                        if isinstance(table, dict):
                            all_rows = table.get('all', [])
                            for row in all_rows:
                                name = row.get('name', '')
                                tid = row.get('id')
                                if name and tid:
                                    conn.execute('INSERT OR IGNORE INTO fotmob_team_map VALUES (?,?,?)',
                                                (name, tid, league_id))
                                    self.db.add_team_mapping(name, 'fotmob', name, tid)
                    
                    # Flat structure
                    all_rows = group.get('table', {}).get('all', [])
                    for row in all_rows:
                        name = row.get('name', '')
                        tid = row.get('id')
                        if name and tid:
                            conn.execute('INSERT OR IGNORE INTO fotmob_team_map VALUES (?,?,?)',
                                        (name, tid, league_id))
                            self.db.add_team_mapping(name, 'fotmob', name, tid)
            
            # Overview table
            overview = pp.get('overview', {})
            if isinstance(overview, dict):
                table = overview.get('table', [])
                if isinstance(table, list):
                    for group in table:
                        data = group.get('data', {})
                        if isinstance(data, dict):
                            tbl = data.get('table', {})
                            if isinstance(tbl, dict):
                                for row in tbl.get('all', []):
                                    name = row.get('name', '')
                                    tid = row.get('id')
                                    if name and tid:
                                        conn.execute('INSERT OR IGNORE INTO fotmob_team_map VALUES (?,?,?)',
                                                    (name, tid, league_id))
            
            conn.commit()
        except Exception as e:
            log(f'  Error saving teams: {e}', 'WARN')
    
    def _save_league_standings(self, league_id: int, pp: Dict,
                                league_name: str, season: str):
        """Extract and save standings data."""
        try:
            standings = []
            table_data = pp.get('table', [])
            if not isinstance(table_data, list):
                return
            
            for group in table_data:
                data_dict = group.get('data', {})
                if not isinstance(data_dict, dict):
                    continue
                table = data_dict.get('table', {})
                if not isinstance(table, dict):
                    continue
                all_rows = table.get('all', [])
                for rank, row in enumerate(all_rows, 1):
                    standings.append({
                        'competition_id': league_id,
                        'competition_name': league_name,
                        'season': season,
                        'team_name': row.get('name', ''),
                        'team_id': row.get('id', 0),
                        'rank': rank,
                        'played': row.get('played', 0),
                        'wins': row.get('wins', row.get('won', 0)),
                        'draws': row.get('draws', 0),
                        'losses': row.get('losses', row.get('lost', 0)),
                        'goals_for': row.get('goalsScored', row.get('goalsFor', 0)),
                        'goals_against': row.get('goalsConceded', row.get('goalsAgainst', 0)),
                        'points': row.get('points', 0),
                        'form': row.get('form', ''),
                    })
            
            if standings:
                count = self.db.store_standings('fotmob', standings)
                log(f'  Saved {count} standings entries')
        except Exception as e:
            log(f'  Error saving standings: {e}', 'WARN')
    
    def scrape_match_detail(self, match_id: int) -> Optional[Dict]:
        """Scrape detailed match data including stats, lineups, shotmap."""
        pp = self.fetch_match_detail(match_id)
        if not pp:
            return None
        
        general = pp.get('general', {})
        content = pp.get('content', {})
        
        home = general.get('homeTeam', {})
        away = general.get('awayTeam', {})
        
        # Extract stats
        stats_data = {}
        periods = content.get('stats', {}).get('Periods', {})
        for pname, pdata in periods.items():
            for sg in pdata.get('stats', []):
                for si in sg.get('stats', []):
                    k = si.get('key', '')
                    vals = si.get('stats', [])
                    if len(vals) == 2:
                        stats_data[f'{pname}_{k}'] = (vals[0], vals[1])
        
        # Extract xG from stats
        home_xg, away_xg = None, None
        for k, v in stats_data.items():
            if 'expected_goals' in k.lower() or 'xg' in k.lower():
                try:
                    home_xg = float(v[0]) if v[0] else 0
                    away_xg = float(v[1]) if v[1] else 0
                except:
                    pass
                break
        
        # Extract shotmap
        shotmap = content.get('shotmap', {})
        shots = []
        for shot in shotmap.get('shots', []):
            shots.append({
                'match_id': match_id,
                'team_id': shot.get('teamId', 0),
                'player_name': shot.get('playerName', ''),
                'player_id': shot.get('playerId', 0),
                'x': shot.get('x', 0),
                'y': shot.get('y', 0),
                'expected_goals': shot.get('expectedGoals', 0),
                'expected_goals_on_target': shot.get('expectedGoalsOnTarget', 0),
                'shot_type': shot.get('shotType', ''),
                'situation': shot.get('situation', ''),
                'is_goal': shot.get('isGoal', False),
                'is_on_target': shot.get('onTarget', False),
                'minute': shot.get('minute', 0),
                'body_part': shot.get('bodyPart', ''),
            })
        
        home_shots = sum(1 for s in shots if s['team_id'] == home.get('id'))
        away_shots = sum(1 for s in shots if s['team_id'] == away.get('id'))
        
        # Extract lineups
        lineup_data = content.get('lineup', {})
        home_formation = ''
        away_formation = ''
        if lineup_data:
            home_formation = lineup_data.get('home', {}).get('formation', '')\
                if isinstance(lineup_data.get('home'), dict) else ''
            away_formation = lineup_data.get('away', {}).get('formation', '')\
                if isinstance(lineup_data.get('away'), dict) else ''
        
        # Update match record with detail data
        match_update = {
            'match_id': match_id,
            'home_xg': home_xg or sum(s['expected_goals'] for s in shots if s['team_id'] == home.get('id')),
            'away_xg': away_xg or sum(s['expected_goals'] for s in shots if s['team_id'] == away.get('id')),
            'home_shots': home_shots,
            'away_shots': away_shots,
            'home_sot': sum(1 for s in shots if s['team_id'] == home.get('id') and s['is_on_target']),
            'away_sot': sum(1 for s in shots if s['team_id'] == away.get('id') and s['is_on_target']),
            'home_possession': self._extract_stat(stats_data, 'possession', 0),
            'away_possession': self._extract_stat(stats_data, 'possession', 1),
            'home_corners': self._extract_stat_int(stats_data, 'corner_kicks', 0),
            'away_corners': self._extract_stat_int(stats_data, 'corner_kicks', 1),
            'home_fouls': self._extract_stat_int(stats_data, 'fouls', 0),
            'away_fouls': self._extract_stat_int(stats_data, 'fouls', 1),
            'home_yellow': self._extract_stat_int(stats_data, 'yellow_cards', 0),
            'away_yellow': self._extract_stat_int(stats_data, 'yellow_cards', 1),
            'home_red': self._extract_stat_int(stats_data, 'red_cards', 0),
            'away_red': self._extract_stat_int(stats_data, 'red_cards', 1),
            'home_formation': home_formation,
            'away_formation': away_formation,
            'has_lineups': bool(lineup_data),
            'has_stats': bool(stats_data),
            'has_shotmap': bool(shots),
            'venue': general.get('stadium', {}).get('name', '') if isinstance(general.get('stadium'), dict) else '',
            'referee': general.get('referee', {}).get('name', '') if isinstance(general.get('referee'), dict) else '',
            'attendance': general.get('attendance', 0),
        }
        
        # Update in DB
        conn = self.db.connect()
        try:
            cols = ', '.join(f'{k}=?' for k in match_update.keys())
            vals = list(match_update.values())
            vals.append(match_id)
            conn.execute(f'UPDATE agent4_matches SET {cols} WHERE match_id=?', vals)
            conn.commit()
        except Exception as e:
            log(f'  Error updating match {match_id}: {e}', 'WARN')
        
        # Store shotmap
        if shots:
            self.db.store_shotmap('fotmob', shots)
        
        # Store lineups
        if lineup_data:
            for side_key, team_side in [('home', home), ('away', away)]:
                side_data = lineup_data.get(side_key, {})
                if isinstance(side_data, dict):
                    lineup_record = {
                        'match_id': match_id,
                        'team_id': team_side.get('id', 0),
                        'team_name': team_side.get('name', ''),
                        'formation': side_data.get('formation', ''),
                        'starting_xi': side_data.get('players', side_data.get('startingXI', [])),
                        'substitutes': side_data.get('substitutes', side_data.get('bench', [])),
                        'missing_players': [],
                        'expected_lineup': [],
                    }
                    self.db.store_lineup('fotmob', lineup_record)
        
        return match_update
    
    def _extract_stat(self, stats: Dict, key: str, idx: int) -> Optional[float]:
        """Extract a numeric stat value from stats dict."""
        for k, v in stats.items():
            if key.lower() in k.lower():
                try:
                    val = v[idx]
                    if val and val != 'None' and val != '-':
                        return float(str(val).replace('%', ''))
                except:
                    pass
        return None
    
    def _extract_stat_int(self, stats: Dict, key: str, idx: int) -> Optional[int]:
        """Extract an integer stat value."""
        val = self._extract_stat(stats, key, idx)
        if val is not None:
            return int(round(val))
        return None
    
    def scrape_multiple_leagues(self, league_ids: List[int] = None,
                                 max_seasons: int = 3, parallel: int = 4,
                                 store_matches: bool = True) -> Dict:
        """Scrape multiple leagues in parallel."""
        if league_ids is None:
            league_ids = list(FOTMOB_LEAGUES.keys())
        
        total_matches = 0
        league_results = []
        
        def scrape_one(lid):
            try:
                result = self.scrape_league(lid, store_matches=store_matches)
                return result
            except Exception as e:
                log(f'Error scraping league {lid}: {e}', 'ERROR')
                return {'league_id': lid, 'matches': [], 'total': 0}
        
        # Phase 1: parallel league scraping
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            futures = {executor.submit(scrape_one, lid): lid for lid in league_ids}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    league_results.append(result)
                    total_matches += result.get('total_matches', 0)
                    self.db.update_progress('fotmob', f'league_{result["league_id"]}',
                                           'completed', result['total_matches'],
                                           result['total_matches'])
                except Exception as e:
                    log(f'Future error: {e}', 'ERROR')
        
        # Phase 2: get match details for top leagues
        match_ids_for_detail = []
        if total_matches > 0:
            # Get matches from top 50 leagues for detailed stats
            conn = self.db.connect()
            rows = conn.execute(
                '''SELECT match_id FROM agent4_matches 
                   WHERE source='fotmob' AND is_finished=1 AND has_stats=0
                   ORDER BY match_date DESC LIMIT 5000'''
            ).fetchall()
            match_ids_for_detail = [r[0] for r in rows]
            conn.close()
        
        detail_count = 0
        if match_ids_for_detail:
            log(f'Scraping details for {len(match_ids_for_detail)} matches...')
            for i, mid in enumerate(match_ids_for_detail[:2000]):  # Cap at 2K
                if i % 100 == 0 and i > 0:
                    log(f'  Details: {i}/{len(match_ids_for_detail)}')
                try:
                    self.scrape_match_detail(mid)
                    detail_count += 1
                except:
                    pass
        
        result = {
            'leagues_scraped': len(league_results),
            'total_matches': total_matches,
            'detail_count': detail_count,
        }
        log(f'FotMob heist complete: {total_matches} matches, {detail_count} details')
        return result
    
    def scrape_specific_leagues(self, league_ids: List[int]) -> Dict:
        """Scrape specific leagues from a list."""
        valid = [lid for lid in league_ids if lid in FOTMOB_LEAGUES]
        return self.scrape_multiple_leagues(league_ids=valid, max_seasons=3, parallel=2)
    
    def scrape_international_tournaments(self) -> Dict:
        """Scrape all international tournament leagues."""
        intl_ids = [208, 209, 210, 211, 212, 213, 214, 216, 217, 218, 219,
                    221, 222, 223, 224, 225, 226, 851, 852, 853, 854, 855]
        return self.scrape_specific_leagues(intl_ids)
    
    def scrape_2026_season(self) -> Dict:
        """Scrape current 2026 season data."""
        result = self.scrape_multiple_leagues(max_seasons=1)
        
        # Additionally, try to scrape 2026-specific season data
        # by explicitly passing 2025/2026 season format
        log('Scraping 2025/2026 seasons explicitly...')
        total_season_matches = 0
        for lid in list(FOTMOB_LEAGUES.keys())[:30]:  # Top 30 leagues
            for season in ['2025/2026', '2026']:
                r = self.scrape_league(lid, season=season)
                total_season_matches += r.get('total_matches', 0)
            time.sleep(0.5)
        
        result['season_specific_matches'] = total_season_matches
        return result
    
    def scrape_friendlies(self) -> Dict:
        """Scrape friendly matches (club + international)."""
        friendly_ids = [851, 852, 853, 854, 855]
        result = self.scrape_specific_leagues(friendly_ids)
        
        # Also try to get friendlies via team pages
        conn = self.db.connect()
        teams = conn.execute(
            'SELECT DISTINCT team_id FROM fotmob_team_map LIMIT 100'
        ).fetchall()
        conn.close()
        
        friendly_matches = 0
        for (tid,) in teams:
            try:
                squad = self.fetch_team_squad(tid)
                if squad:
                    overview = squad.get('overview', {})
                    fixtures = overview.get('overviewFixtures', [])
                    if fixtures:
                        for m in fixtures[:20]:
                            pm = self.parse_match(m, 'Friendly')
                            if pm and pm.get('match_id'):
                                self.db.store_match('fotmob', pm)
                                friendly_matches += 1
            except:
                pass
        
        log(f'Friendlies: {friendly_matches} additional matches')
        return result
    
    def scrape_team_squads(self, team_limit: int = 500) -> Dict:
        """Scrape team squads and player data."""
        conn = self.db.connect()
        teams = conn.execute(
            'SELECT DISTINCT team_id, team_name FROM fotmob_team_map ORDER BY team_id DESC LIMIT ?',
            (team_limit,)
        ).fetchall()
        conn.close()
        
        players_count = 0
        for (tid, tname) in teams:
            try:
                pp = self.fetch_team_squad(tid)
                if not pp:
                    continue
                
                # Save team info
                details = pp.get('details', {})
                if details:
                    team_record = {
                        'team_id': tid,
                        'name': details.get('name', tname),
                        'short_name': details.get('shortName', ''),
                        'country': details.get('country', ''),
                        'venue': details.get('venue', {}),
                    }
                    self.db.store_team('fotmob', team_record)
                
                # Save players
                fallback = pp.get('fallback', {})
                if isinstance(fallback, dict):
                    for key in fallback:
                        if 'player' in key.lower() or 'squad' in key.lower():
                            squad_data = fallback[key]
                            if isinstance(squad_data, dict):
                                for pid, pdata in squad_data.items():
                                    if isinstance(pdata, dict) and 'name' in pdata:
                                        player_record = {
                                            'player_id': pdata.get('id', pid),
                                            'name': pdata.get('name', ''),
                                            'team_id': tid,
                                            'position': pdata.get('position', pdata.get('role', '')),
                                            'jersey_number': pdata.get('shirtNumber', pdata.get('jerseyNumber', 0)),
                                            'nationality': pdata.get('nationality', ''),
                                            'birth_date': str(pdata.get('dateOfBirth', '')),
                                            'height': pdata.get('height', 0),
                                            'weight': pdata.get('weight', 0),
                                        }
                                        self.db.store_player('fotmob', player_record)
                                        players_count += 1
                
                time.sleep(0.3)
            except Exception as e:
                pass
        
        log(f'Saved {players_count} players from {len(teams)} teams')
        return {'teams': len(teams), 'players': players_count}
    
    def scrape_player_injuries(self) -> Dict:
        """Scrape injury data from FotMob."""
        conn = self.db.connect()
        teams = conn.execute(
            'SELECT DISTINCT team_id, team_name FROM fotmob_team_map LIMIT 200'
        ).fetchall()
        conn.close()
        
        injury_count = 0
        for (tid, tname) in teams:
            try:
                squad = self.fetch_team_squad(tid)
                if not squad:
                    continue
                
                fallback = squad.get('fallback', {})
                if isinstance(fallback, dict):
                    for key in fallback:
                        if 'injuries' in key.lower():
                            injuries = fallback[key]
                            if isinstance(injuries, list):
                                for inj in injuries:
                                    if isinstance(inj, dict):
                                        injury_record = {
                                            'source': 'fotmob',
                                            'player_id': inj.get('id', 0),
                                            'player_name': inj.get('name', inj.get('playerName', '')),
                                            'team_id': tid,
                                            'team_name': tname,
                                            'injury_type': inj.get('injuryType', inj.get('type', '')),
                                            'injury_severity': inj.get('severity', ''),
                                            'expected_return': inj.get('expectedReturn', inj.get('returnDate', '')),
                                            'injury_date': inj.get('date', inj.get('injuryDate', '')),
                                            'status': inj.get('status', 'injured'),
                                            'description': inj.get('description', inj.get('notes', '')),
                                        }
                                        self.db.store_injury('fotmob', injury_record)
                                        injury_count += 1
                
                time.sleep(0.3)
            except:
                pass
        
        log(f'Saved {injury_count} injury records')
        return {'injuries': injury_count}
    
    def scrape_expected_lineups(self, league_ids: List[int] = None) -> Dict:
        """Scrape expected/predicted lineups from upcoming matches."""
        if league_ids is None:
            league_ids = list(FOTMOB_LEAGUES.keys())[:20]
        
        conn = self.db.connect()
        lineups_count = 0
        
        for lid in league_ids:
            pp = self.fetch_league_data(lid)
            if not pp:
                continue
            
            matches = self.extract_matches(pp, lid, '', '')
            for m in matches:
                status = m.get('status', {})
                if isinstance(status, dict):
                    is_finished = status.get('finished', False)
                else:
                    is_finished = m.get('finished', False)
                
                if is_finished:
                    continue  # Only interested in upcoming
                
                match_id = m.get('id', m.get('matchId', 0))
                if not match_id:
                    continue
                
                # Fetch match detail for any lineup info
                pp_detail = self.fetch_match_detail(match_id)
                if pp_detail:
                    content = pp_detail.get('content', {})
                    lineup_data = content.get('lineup', {})
                    if lineup_data:
                        home = m.get('home', {})
                        away = m.get('away', {})
                        for side_key, team_side in [('home', home), ('away', away)]:
                            side_data = lineup_data.get(side_key, {})
                            if isinstance(side_data, dict) and side_data.get('formation'):
                                lineup_record = {
                                    'match_id': match_id,
                                    'team_id': team_side.get('id', 0),
                                    'team_name': team_side.get('name', ''),
                                    'formation': side_data.get('formation', ''),
                                    'starting_xi': side_data.get('players', side_data.get('startingXI', [])),
                                    'substitutes': side_data.get('substitutes', side_data.get('bench', [])),
                                    'missing_players': [],
                                    'expected_lineup': side_data.get('players', []),
                                }
                                self.db.store_lineup('fotmob', lineup_record)
                                lineups_count += 1
                
                time.sleep(0.2)
        
        log(f'Saved {lineups_count} lineups from upcoming matches')
        return {'lineups': lineups_count}


# ═══════════════════════════════════════════════════════════════════════
# FBREF HEIST ENGINE (curl_cffi Cloudflare bypass)
# ═══════════════════════════════════════════════════════════════════════

class FBrefHeist:
    """FBref scraper using curl_cffi to bypass Cloudflare."""
    
    BASE = 'https://fbref.com'
    
    def __init__(self, session: CurlSession, db: HeistDB):
        self.session = session
        self.db = db
    
    def fetch_league_page(self, comp_slug: str, season: str = '2025-2026') -> Optional[str]:
        """Fetch a league page from FBref."""
        url = f'{self.BASE}{comp_slug}/{season}'
        return self.session.fetch_html(url, impersonate='chrome120',
                                       referer='https://fbref.com/en/')
    
    def parse_league_matches(self, html: str, competition: str,
                             season: str) -> List[Dict]:
        """Parse match results from FBref league page."""
        if not html or not BS4_OK:
            return []
        
        soup = BeautifulSoup(html, 'lxml' if LXML_OK else 'html.parser')
        matches = []
        
        # Find the score table
        tables = soup.find_all('table', class_='stats_table')
        for table in tables:
            if 'scores' not in str(table.get('id', '')).lower():
                continue
            
            rows = table.find_all('tr')
            for row in rows:
                if 'thead' in str(row.get('class', [])):
                    continue
                
                cells = row.find_all('td')
                if len(cells) < 6:
                    continue
                
                try:
                    home_team_el = row.find('td', {'data-stat': 'home_team'})
                    away_team_el = row.find('td', {'data-stat': 'away_team'})
                    score_el = row.find('td', {'data-stat': 'score'})
                    date_el = row.find('td', {'data-stat': 'date'})
                    venue_el = row.find('td', {'data-stat': 'venue'})
                    
                    if not home_team_el or not away_team_el or not score_el:
                        continue
                    
                    home_team = home_team_el.get_text(strip=True)
                    away_team = away_team_el.get_text(strip=True)
                    score_text = score_el.get_text(strip=True)
                    date_text = date_el.get_text(strip=True) if date_el else ''
                    
                    # Parse score
                    if '–' in score_text:
                        parts = score_text.split('–')
                        home_score = int(parts[0].strip())
                        away_score = int(parts[1].strip())
                    else:
                        continue
                    
                    # Generate a match ID from the hash of content
                    match_str = f'fbref_{home_team}_{away_team}_{date_text}'
                    match_id = int(hashlib.md5(match_str.encode()).hexdigest()[:15], 16)
                    
                    match = {
                        'source': 'fbref',
                        'match_id': match_id,
                        'home_team': home_team,
                        'away_team': away_team,
                        'home_score': home_score,
                        'away_score': away_score,
                        'competition': competition,
                        'season': season,
                        'match_date': date_text,
                        'is_finished': True,
                    }
                    
                    # xG data
                    home_xg_el = row.find('td', {'data-stat': 'home_xg'})
                    away_xg_el = row.find('td', {'data-stat': 'away_xg'})
                    if home_xg_el:
                        try:
                            match['home_xg'] = float(home_xg_el.get_text(strip=True))
                        except:
                            pass
                    if away_xg_el:
                        try:
                            match['away_xg'] = float(away_xg_el.get_text(strip=True))
                        except:
                            pass
                    
                    # Attendance
                    att_el = row.find('td', {'data-stat': 'attendance'})
                    if att_el:
                        try:
                            match['attendance'] = int(att_el.get_text(strip=True).replace(',', ''))
                        except:
                            pass
                    
                    # Venue
                    if venue_el:
                        match['venue'] = venue_el.get_text(strip=True)
                    
                    # Referee
                    ref_el = row.find('td', {'data-stat': 'referee'})
                    if ref_el:
                        match['referee'] = ref_el.get_text(strip=True)
                    
                    matches.append(match)
                    
                except Exception as e:
                    continue
        
        return matches
    
    def parse_league_standings(self, html: str, competition: str,
                                season: str) -> List[Dict]:
        """Parse league standings table."""
        if not html or not BS4_OK:
            return []
        
        soup = BeautifulSoup(html, 'lxml' if LXML_OK else 'html.parser')
        standings = []
        
        # Standard standings table
        tables = soup.find_all('table', class_='stats_table')
        for table in tables:
            caption = table.find('caption')
            if caption and 'standings' not in caption.get_text(strip=True).lower():
                continue
            if not caption and 'standings' not in str(table.get('id', '')).lower():
                continue
            
            rows = table.find_all('tr')
            for rank, row in enumerate(rows, 1):
                if 'thead' in str(row.get('class', [])) or 'th' in str(row.name):
                    continue
                
                cells = row.find_all('td')
                if len(cells) < 8:
                    continue
                
                try:
                    team_el = row.find('td', {'data-stat': 'team'})
                    if not team_el:
                        continue
                    
                    team_name = team_el.get_text(strip=True)
                    if not team_name or team_name == 'Team':
                        continue
                    
                    def gs(stat):
                        el = row.find('td', {'data-stat': stat})
                        if el:
                            try:
                                return int(el.get_text(strip=True))
                            except:
                                pass
                        return 0
                    
                    standings.append({
                        'competition_id': 0,
                        'competition_name': competition,
                        'season': season,
                        'team_name': team_name,
                        'team_id': int(hashlib.md5(f'fbref_{team_name}'.encode()).hexdigest()[:15], 16),
                        'rank': rank,
                        'played': gs('games'),
                        'wins': gs('wins'),
                        'draws': gs('draws'),
                        'losses': gs('losses'),
                        'goals_for': gs('goals_for'),
                        'goals_against': gs('goals_against'),
                        'points': gs('points'),
                        'form': '',
                    })
                except:
                    continue
            
            if standings:
                break
        
        return standings
    
    def scrape_league(self, comp_name: str, comp_slug: str,
                       seasons: List[str] = None) -> Dict:
        """Scrape all matches for a league from FBref."""
        if seasons is None:
            seasons = ['2025-2026', '2024-2025']
        
        all_matches = []
        for season in seasons:
            html = self.fetch_league_page(comp_slug, season)
            if not html:
                log(f'  FBref {comp_name} {season}: no data', 'WARN')
                continue
            
            matches = self.parse_league_matches(html, comp_name, season)
            log(f'  FBref {comp_name} {season}: {len(matches)} matches')
            
            for m in matches:
                self.db.store_match('fbref', m)
                all_matches.append(m)
            
            # Parse and store standings
            standings = self.parse_league_standings(html, comp_name, season)
            if standings:
                self.db.store_standings('fbref', standings)
                log(f'  Standings: {len(standings)} teams')
            
            time.sleep(1.0)
        
        return {
            'competition': comp_name,
            'seasons': len(seasons),
            'total_matches': len(all_matches),
            'matches': all_matches,
        }
    
    def scrape_all(self, parallel: int = 3) -> Dict:
        """Scrape all known FBref competitions."""
        total = 0
        results = []
        
        comps = list(FBREF_COMPS.items())
        
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            futures = {}
            for cname, cslug in comps:
                future = executor.submit(self.scrape_league, cname, cslug)
                futures[future] = cname
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                    total += result.get('total_matches', 0)
                except Exception as e:
                    log(f'FBref error: {e}', 'ERROR')
        
        log(f'FBref heist complete: {total} total matches')
        return {'total_matches': total, 'results': results}


# ═══════════════════════════════════════════════════════════════════════
# UNDERSTAT HEIST ENGINE
# ═══════════════════════════════════════════════════════════════════════

class UnderstatHeist:
    """Understat xG data scraper using curl_cffi."""
    
    BASE = 'https://understat.com'
    
    def __init__(self, session: CurlSession, db: HeistDB):
        self.session = session
        self.db = db
    
    def fetch_league_data(self, league: str, season: str = '2025') -> Optional[Dict]:
        """Fetch understat league data via JSON API (requires X-Requested-With header)."""
        url = f'{self.BASE}/getLeagueData/{league}/{season}'
        headers = {
            'User-Agent': random.choice(UA_POOL),
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': f'{self.BASE}/league/{league}/{season}',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': self.BASE,
        }
        try:
            from curl_cffi import requests as cr
            r = cr.get(url, headers=headers, impersonate='chrome120', timeout=15)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            log(f'Understat fetch error: {e}', 'ERROR')
        return None
    
    def parse_matches_from_league(self, data: Dict, league: str,
                                   season: str) -> List[Dict]:
        """Parse match data from understat league data.
        
        Note: The understat API returns per-team history, not match objects.
        We need to cross-reference home/away entries to reconstruct full matches.
        """
        teams = data.get('teams', {})
        if not teams:
            return []
        
        # Build a lookup: date -> list of (team_id, h_a, scored, missed, xG, xGA, ...)
        date_map = {}
        team_names = {}
        
        for tid, team_data in teams.items():
            title = team_data.get('title', '')
            team_names[tid] = title
            
            for hm in team_data.get('history', []):
                date = hm.get('date', '')
                if not date:
                    continue
                date_key = date.split(' ')[0]  # Just the date part
                
                if date_key not in date_map:
                    date_map[date_key] = []
                
                date_map[date_key].append({
                    'team_id': tid,
                    'h_a': hm.get('h_a', ''),
                    'scored': hm.get('scored', 0),
                    'missed': hm.get('missed', 0),
                    'xG': float(hm.get('xG', 0)) if hm.get('xG') else 0,
                    'xGA': float(hm.get('xGA', 0)) if hm.get('xGA') else 0,
                    'npxG': float(hm.get('npxG', 0)) if hm.get('npxG') else 0,
                    'npxGA': float(hm.get('npxGA', 0)) if hm.get('npxGA') else 0,
                    'ppda': hm.get('ppda', {}),
                    'ppda_allowed': hm.get('ppda_allowed', {}),
                    'deep': hm.get('deep', 0),
                    'deep_allowed': hm.get('deep_allowed', 0),
                    'result': hm.get('result', ''),
                    'date_full': date,
                })
        
        # Cross-reference: find home+away pairs on same date
        seen = set()
        matches = []
        
        for date_key, entries in date_map.items():
            # Group by (scored, missed) to find matching pairs
            for i, e1 in enumerate(entries):
                if e1['h_a'] != 'h':
                    continue  # Only process home entries
                
                # Find matching away entry
                for e2 in entries:
                    if e2['h_a'] != 'a':
                        continue
                    if e2['team_id'] == e1['team_id']:
                        continue
                    # Check if scores match: e1.home_scored = e2.away_missed AND e1.home_missed = e2.away_scored
                    if e1['scored'] == e2['missed'] and e1['missed'] == e2['scored']:
                        match_key = (e1['team_id'], e2['team_id'], date_key)
                        if match_key in seen:
                            continue
                        seen.add(match_key)
                        
                        home_team = team_names.get(e1['team_id'], f'Team_{e1["team_id"]}')
                        away_team = team_names.get(e2['team_id'], f'Team_{e2["team_id"]}')
                        
                        match_str = f'understat_{home_team}_{away_team}_{season}_{date_key}'
                        match_id = int(hashlib.md5(match_str.encode()).hexdigest()[:15], 16)
                        
                        match = {
                            'source': 'understat',
                            'match_id': match_id,
                            'home_team': home_team,
                            'away_team': away_team,
                            'home_score': e1['scored'],
                            'away_score': e2['scored'],
                            'home_xg': e1['xG'],
                            'away_xg': e2['xG'],
                            'home_npxg': e1['npxG'],
                            'away_npxg': e2['npxG'],
                            'competition': league,
                            'season': season,
                            'is_finished': True,
                            'has_stats': True,
                            'match_date': e1['date_full'],
                            'home_shots': e1.get('deep', 0),
                            'away_shots': e2.get('deep', 0),
                            'home_ppda_att': e1['ppda'].get('att', 0) if isinstance(e1['ppda'], dict) else 0,
                            'home_ppda_def': e1['ppda'].get('def', 1) if isinstance(e1['ppda'], dict) else 1,
                            'away_ppda_att': e2['ppda'].get('att', 0) if isinstance(e2['ppda'], dict) else 0,
                            'away_ppda_def': e2['ppda'].get('def', 1) if isinstance(e2['ppda'], dict) else 1,
                        }
                        matches.append(match)
        
        return matches
    
    def scrape_league(self, league: str, seasons: List[str] = None) -> Dict:
        """Scrape understat data for a league across multiple seasons."""
        if seasons is None:
            seasons = ['2025', '2024', '2023', '2022', '2021', '2020']
        
        all_matches = []
        for season in seasons:
            data = self.fetch_league_data(league, season)
            if not data:
                log(f'  Understat {league} {season}: no data', 'WARN')
                continue
            
            matches = self.parse_matches_from_league(data, league, season)
            log(f'  Understat {league} {season}: {len(matches)} matches')
            
            for m in matches:
                self.db.store_match('understat', m)
                all_matches.append(m)
            
            time.sleep(0.5)
        
        return {'league': league, 'total': len(all_matches), 'matches': all_matches}
    
    def scrape_all(self) -> Dict:
        """Scrape all understat leagues."""
        total = 0
        for league in UNDERSTAT_LEAGUES:
            result = self.scrape_league(league)
            total += result['total']
        log(f'Understat heist complete: {total} matches')
        return {'total_matches': total}


# ═══════════════════════════════════════════════════════════════════════
# STATSBOMB HEIST ENGINE
# ═══════════════════════════════════════════════════════════════════════

class StatsBombHeist:
    """StatsBomb additional event data scraper."""
    
    BASE = 'https://raw.githubusercontent.com/statsbomb/open-data/master/data'
    
    def __init__(self, session: CurlSession, db: HeistDB):
        self.session = session
        self.db = db
    
    def fetch_competitions(self) -> List[Dict]:
        """Fetch list of all competitions from StatsBomb."""
        data = self.session.fetch_json(f'{self.BASE}/competitions.json',
                                        impersonate='chrome120')
        if not data:
            return []
        return data if isinstance(data, list) else []
    
    def fetch_matches(self, competition_id: int, season_id: int) -> List[Dict]:
        """Fetch matches for a competition+season."""
        url = f'{self.BASE}/matches/{competition_id}/{season_id}.json'
        data = self.session.fetch_json(url, impersonate='chrome120')
        if not data:
            return []
        return data if isinstance(data, list) else []
    
    def fetch_events(self, match_id: int) -> List[Dict]:
        """Fetch event data for a match."""
        # Determine comp/season from the first 3 lines of the events file
        # StatsBomb stores events in: events/{competition_id}/{season_id}/{match_id}.json
        # But we need to search for the match
        # First check if this match is in our DB
        conn = self.db.connect()
        row = conn.execute(
            'SELECT competition_id, season_id FROM statsbomb_matches WHERE match_id=?',
            (match_id,)
        ).fetchone()
        conn.close()
        
        if row:
            url = f'{self.BASE}/events/{row[0]}/{row[1]}/{match_id}.json'
        else:
            # Search all competition dirs
            for comp_id in range(1, 50):
                for seas_id in range(1, 100):
                    url = f'{self.BASE}/events/{comp_id}/{seas_id}/{match_id}.json'
                    data = self.session.fetch_json(url, impersonate='chrome120')
                    if data:
                        return data if isinstance(data, list) else []
        
        return self.session.fetch_json(url, impersonate='chrome120') or []
    
    def discover_new_competitions(self) -> List[Dict]:
        """Find competitions not yet in our database."""
        all_comps = self.fetch_competitions()
        
        conn = self.db.connect()
        existing = set()
        try:
            rows = conn.execute('SELECT competition_id, season_id FROM statsbomb_matches').fetchall()
            existing = {(r[0], r[1]) for r in rows}
        except:
            pass
        conn.close()
        
        new_comps = []
        for comp in all_comps:
            cid = comp.get('competition_id', comp.get('competition', {}).get('id'))
            sid = comp.get('season_id', comp.get('season', {}).get('id'))
            if (cid, sid) not in existing:
                new_comps.append(comp)
        
        log(f'StatsBomb: {len(all_comps)} total competitions, {len(new_comps)} new')
        return new_comps
    
    def scrape_new_competitions(self, max_matches: int = None) -> Dict:
        """Scrape matches and events from competitions not yet in DB."""
        new_comps = self.discover_new_competitions()
        if not new_comps:
            return {'matches': 0, 'events': 0, 'competitions': 0}
        
        total_matches = 0
        total_events = 0
        
        for comp in new_comps[:20]:  # Max 20 new comps
            cid = comp.get('competition_id', comp.get('competition', {}).get('id'))
            sid = comp.get('season_id', comp.get('season', {}).get('id'))
            cname = comp.get('competition_name', comp.get('competition', {}).get('name', ''))
            sname = comp.get('season_name', comp.get('season', {}).get('name', ''))
            
            matches = self.fetch_matches(cid, sid)
            log(f'  StatsBomb {cname} {sname}: {len(matches)} matches')
            
            match_limit = max_matches or len(matches)
            for i, m in enumerate(matches[:match_limit]):
                if i % 10 == 0 and i > 0:
                    log(f'    events: {i}/{min(match_limit, len(matches))}')
                
                mid = m.get('match_id', m.get('matchId', 0))
                if not mid:
                    continue
                
                home = m.get('home_team', m.get('homeTeam', {}))
                away = m.get('away_team', m.get('awayTeam', {}))
                home_name = home.get('home_team_name', home.get('name', '')) if isinstance(home, dict) else str(home)
                away_name = away.get('away_team_name', away.get('name', '')) if isinstance(away, dict) else str(away)
                
                # Store match
                match_rec = {
                    'source': 'statsbomb',
                    'match_id': mid,
                    'home_team': home_name,
                    'away_team': away_name,
                    'home_score': m.get('home_score', m.get('homeScore', 0)),
                    'away_score': m.get('away_score', m.get('awayScore', 0)),
                    'competition': cname,
                    'competition_id': cid,
                    'season': sname,
                    'season_id': sid,
                    'match_date': str(m.get('match_date', m.get('matchDate', m.get('date', '')))),
                    'is_finished': True,
                    'venue': m.get('venue', ''),
                    'referee': m.get('referee', m.get('referee', {}).get('name', '')) if isinstance(m.get('referee'), dict) else str(m.get('referee', '')),
                    'home_formation': m.get('home_formation', m.get('homeFormation', '')),
                    'away_formation': m.get('away_formation', m.get('awayFormation', '')),
                }
                self.db.store_match('statsbomb', match_rec)
                total_matches += 1
                
                # Fetch events
                events = self.fetch_events(mid)
                if events:
                    shots = []
                    xg_home = 0
                    xg_away = 0
                    for ev in events:
                        if ev.get('type', {}).get('name') == 'Shot':
                            shot_data = {
                                'match_id': mid,
                                'team_id': ev.get('team', {}).get('id', 0),
                                'player_name': ev.get('player', {}).get('name', ''),
                                'player_id': ev.get('player', {}).get('id', 0),
                                'x': ev.get('location', [0, 0])[0] if ev.get('location') else 0,
                                'y': ev.get('location', [0, 0])[1] if ev.get('location') else 0,
                                'expected_goals': ev.get('shot', {}).get('statsbomb_xg', 0),
                                'shot_type': ev.get('shot', {}).get('type', {}).get('name', ''),
                                'situation': ev.get('shot', {}).get('body_part', {}).get('name', ''),
                                'is_goal': ev.get('shot', {}).get('outcome', {}).get('name') == 'Goal',
                                'is_on_target': ev.get('shot', {}).get('outcome', {}).get('name') in ['Goal', 'Saved', 'Saved to Post'],
                                'minute': ev.get('minute', 0),
                                'body_part': ev.get('shot', {}).get('body_part', {}).get('name', ''),
                            }
                            shots.append(shot_data)
                            xg = ev.get('shot', {}).get('statsbomb_xg', 0)
                            if ev.get('team', {}).get('id') == m.get('home_team', {}).get('home_team_id'):
                                xg_home += xg
                            else:
                                xg_away += xg
                    
                    if shots:
                        self.db.store_shotmap('statsbomb', shots)
                        total_events += len(shots)
                        
                        # Update match with xG
                        conn = self.db.connect()
                        try:
                            conn.execute(
                                'UPDATE agent4_matches SET home_xg=?, away_xg=?, has_shotmap=1 WHERE match_id=?',
                                (xg_home, xg_away, mid)
                            )
                            conn.commit()
                        except:
                            pass
                        finally:
                            conn.close()
                
                time.sleep(0.5)
        
        log(f'StatsBomb heist: {total_matches} matches, {total_events} events')
        return {'matches': total_matches, 'events': total_events, 'competitions': len(new_comps[:20])}


# ═══════════════════════════════════════════════════════════════════════
# TRANSFERMARKT HEIST ENGINE (Injuries, Squads, Market Values)
# ═══════════════════════════════════════════════════════════════════════

class TransfermarktHeist:
    """Transfermarkt data scraper using curl_cffi."""
    
    BASE = 'https://www.transfermarkt.com'
    
    def __init__(self, session: CurlSession, db: HeistDB):
        self.session = session
        self.db = db
        # Cache for team slugs (prevent repeated lookups)
        self._team_slugs = self._load_known_slugs()
    
    def _load_known_slugs(self) -> Dict[int, str]:
        """Load known team slugs from various sources."""
        slugs = {}
        try:
            conn = self.db.connect()
            # Try to get slugs we've seen before
            if False:  # Placeholder for future caching
                pass
            conn.close()
        except:
            pass
        # Common top clubs with known slugs
        common = {
            27: 'fc-bayern-munchen',
            31: 'borussia-dortmund',
            5: 'fc-schalke-04',
            12: 'bayer-04-leverkusen',
            18: 'rb-leipzig',
            41: 'vfb-stuttgart',
            76: 'vfl-wolfsburg',
            79: 'borussia-monchengladbach',
            82: 'eintracht-frankfurt',
            134: '1-fc-koln',
            154: '1-fc-kaiserslautern',
            155: 'fc-augsburg',
            # Premier League
            349: 'manchester-city',
            350: 'manchester-united',
            351: 'liverpool-fc',  # Corrected from fc-liverpool
            352: 'chelsea-fc',
            353: 'arsenal-fc',
            354: 'tottenham-hotspur',
            355: 'newcastle-united',
            356: 'aston-villa',
            357: 'west-ham-united',
            358: 'crystal-palace',
            359: 'brighton-amp-hove-albion',
            360: 'wolverhampton-wanderers',
            361: 'fulham-fc',
            362: 'brentford-fc',
            363: 'everton-fc',
            364: 'nottingham-forest',
            365: 'afc-bournemouth',
            # La Liga
            366: 'real-madrid',
            367: 'fc-barcelona',
            368: 'atletico-madrid',
            369: 'fc-sevilla',
            370: 'fc-valencia',
            371: 'athletic-bilbao',
            372: 'real-sociedad',
            373: 'fc-villarreal',
            374: 'fc-betis',
            # Serie A
            375: 'juventus-fc',
            376: 'ac-mailand',
            377: 'inter-mailand',
            378: 'ac-rom',
            379: 'ssc-neapel',
            380: 'ss-lazio',
            381: 'fiorentina',
            # Ligue 1
            382: 'paris-saint-germain',
            383: 'olympique-lyon',
            384: 'olympique-marseille',
            385: 'as-monaco',
            # Other
            286: 'fc-porto',
            287: 'sl-benfica',
            288: 'sporting-lissabon',
            295: 'ajax-amsterdam',
            299: 'psv-eindhoven',
            301: 'feyenoord-rotterdam',
            314: 'fc-basel',
            323: 'fc-zurich',
            324: 'bsc-young-boys',
        }
        slugs.update(common)
        return slugs
    
    def _get_team_slug(self, team_id: int, team_name: str = '') -> str:
        """Get or construct team slug for Transfermarkt URL."""
        if team_id in self._team_slugs:
            return self._team_slugs[team_id]
        
        if team_name:
            slug = team_name.lower()
            slug = re.sub(r'[^a-z0-9]+', '-', slug)
            slug = slug.strip('-')
            self._team_slugs[team_id] = slug
            return slug
        
        return str(team_id)
    
    def search_team(self, query: str) -> List[Dict]:
        """Search for a team on Transfermarkt."""
        url = f'{self.BASE}/schnellsuche/ergebnis_schnellsuche'
        html = self.session.fetch_html(url, impersonate='chrome120',
                                        referer=f'{self.BASE}/',
                                        params={'query': query})
        if not html or not BS4_OK:
            return []
        
        soup = BeautifulSoup(html, 'lxml' if LXML_OK else 'html.parser')
        teams = []
        for link in soup.select('a.vereinprofil_tooltip'):
            href = link.get('href', '')
            name = link.get_text(strip=True)
            if href and name:
                match = re.search(r'/verein/(\d+)', href)
                tid = int(match.group(1)) if match else 0
                teams.append({'id': tid, 'name': name, 'url': href})
                # Extract slug from URL
                slug_match = re.search(r'/([^/]+)/startseite/verein/', href)
                if slug_match and tid:
                    self._team_slugs[tid] = slug_match.group(1)
        
        return teams
    
    def fetch_squad(self, team_id: int) -> Optional[Dict]:
        """Fetch squad data for a team."""
        slug = self._get_team_slug(team_id)
        url = f'{self.BASE}/{slug}/startseite/verein/{team_id}'
        html = self.session.fetch_html(url, impersonate='chrome120',
                                        referer=f'{self.BASE}/')
        if not html or not BS4_OK:
            return None
        
        soup = BeautifulSoup(html, 'lxml' if LXML_OK else 'html.parser')
        
        # Get team name
        team_name_el = soup.select_one('h1.vereinbenennung')
        team_name = soup.select_one('h1')
        team_name = team_name.get_text(strip=True) if team_name else f'Team_{team_id}'
        
        # Get players from squad table
        players = []
        table = soup.select_one('table.items')
        if table:
            rows = table.select('tr')
            for row in rows:
                # Only process data rows (odd/even classes)
                cls = ' '.join(row.get('class', []))
                if 'odd' not in cls and 'even' not in cls:
                    continue
                
                cells = row.select('td')
                if len(cells) < 8:
                    continue
                
                try:
                    # cell[0]: jersey number
                    num_text = cells[0].get_text(strip=True)
                    number = int(num_text) if num_text.isdigit() else 0
                    
                    # cell[3]: player name link
                    name_el = cells[3].select_one('a') or cells[1].select_one('a')
                    name = name_el.get_text(strip=True) if name_el else ''
                    
                    # cell[4]: position
                    position = cells[4].get_text(strip=True) if len(cells) > 4 else ''
                    
                    # cell[5]: date of birth/age
                    age_text = cells[5].get_text(strip=True) if len(cells) > 5 else ''
                    # Format: "08/08/2003 (22)"
                    age = 0
                    age_match = re.search(r'\((\d+)\)', age_text)
                    if age_match:
                        age = int(age_match.group(1))
                    date_of_birth = age_text.split('(')[0].strip() if '(' in age_text else age_text
                    
                    # cell[6]: nationality flag
                    nat_el = cells[6].select_one('img') if len(cells) > 6 else None
                    nationality = nat_el.get('title', '') if nat_el else ''
                    
                    # cell[7]: market value
                    mv_text = ''
                    mv = 0
                    if len(cells) > 7:
                        mv_el = cells[7].select_one('a') or cells[7]
                        mv_text = mv_el.get_text(strip=True) if mv_el else ''
                    
                    # Parse market value
                    if 'm' in mv_text.lower():
                        try:
                            mv = float(mv_text.lower().replace('m', '').replace(',', '.').replace('€', '').strip()) * 1_000_000
                        except:
                            pass
                    elif 'k' in mv_text.lower() or 'th' in mv_text.lower():
                        try:
                            clean = mv_text.lower().replace('k', '').replace('th', '').replace(',', '.').replace('€', '').strip()
                            mv = float(clean) * 1_000
                        except:
                            pass
                    
                    # Extract player ID from name link
                    player_id = 0
                    if name_el:
                        href = name_el.get('href', '')
                        match = re.search(r'/spieler/(\d+)', href)
                        if match:
                            player_id = int(match.group(1))
                    
                    player = {
                        'player_id': player_id,
                        'name': name,
                        'team_id': team_id,
                        'team_name': team_name,
                        'position': position,
                        'jersey_number': number,
                        'nationality': nationality,
                        'market_value': mv,
                        'market_value_currency': 'EUR',
                        'age': age,
                        'birth_date': date_of_birth,
                    }
                    players.append(player)
                except Exception as e:
                    continue
        
        return {
            'team_id': team_id,
            'team_name': team_name,
            'players': players,
            'player_count': len(players),
        }
    
    def fetch_injuries(self, team_id: int, season: str = '2025') -> List[Dict]:
        """Fetch injury data for a team. Injuries are embedded in the startseite page."""
        slug = self._get_team_slug(team_id)
        url = f'{self.BASE}/{slug}/startseite/verein/{team_id}'
        html = self.session.fetch_html(url, impersonate='chrome120',
                                        referer=f'{self.BASE}/')
        if not html or not BS4_OK:
            return []
        
        soup = BeautifulSoup(html, 'lxml' if LXML_OK else 'html.parser')
        injuries = []
        
        # Team name
        team_name_el = soup.select_one('h1.vereinbenennung')
        team_name = team_name_el.get_text(strip=True) if team_name_el else f'Team_{team_id}'
        
        # Find injury table
        tables = soup.select('table.items')
        for table in tables:
            rows = table.select('tr:not(.bg_grey2):not(.bg_grey3)')
            for row in rows:
                cells = row.select('td')
                if len(cells) < 5:
                    continue
                
                try:
                    # Player name & link
                    player_el = cells[0].select_one('a')
                    if not player_el:
                        continue
                    
                    player_name = player_el.get_text(strip=True)
                    href = player_el.get('href', '')
                    pid_match = re.search(r'/spieler/(\d+)', href)
                    player_id = int(pid_match.group(1)) if pid_match else 0
                    
                    # Injury info
                    injury_cells = cells[1:]
                    injury_type = injury_cells[0].get_text(strip=True) if len(injury_cells) > 0 else ''
                    injury_date = injury_cells[1].get_text(strip=True) if len(injury_cells) > 1 else ''
                    expected_return = injury_cells[2].get_text(strip=True) if len(injury_cells) > 2 else ''
                    
                    injuries.append({
                        'source': 'transfermarkt',
                        'player_id': player_id,
                        'player_name': player_name,
                        'team_id': team_id,
                        'team_name': team_name,
                        'injury_type': injury_type,
                        'injury_severity': '',
                        'expected_return': expected_return,
                        'injury_date': injury_date,
                        'status': 'injured' if expected_return else 'unknown',
                        'description': injury_type,
                    })
                except:
                    continue
        
        return injuries
    
    def fetch_market_values(self, team_id: int) -> List[Dict]:
        """Fetch market values for a team's squad."""
        slug = self._get_team_slug(team_id)
        url = f'{self.BASE}/{slug}/leistungsdaten/verein/{team_id}'
        html = self.session.fetch_html(url, impersonate='chrome120',
                                        referer=f'{self.BASE}/{slug}/startseite/verein/{team_id}')
        if not html or not BS4_OK:
            return []
        
        soup = BeautifulSoup(html, 'lxml' if LXML_OK else 'html.parser')
        values = []
        
        table = soup.select_one('table.items')
        if table:
            rows = table.select('tr:not(.bg_grey2)')
            for row in rows:
                cells = row.select('td')
                if len(cells) < 12:
                    continue
                
                try:
                    name_el = cells[2].select_one('a')
                    if not name_el:
                        continue
                    
                    name = name_el.get_text(strip=True)
                    href = name_el.get('href', '')
                    pid_match = re.search(r'/spieler/(\d+)', href)
                    player_id = int(pid_match.group(1)) if pid_match else 0
                    
                    mv_el = cells[-1]
                    mv_text = mv_el.get_text(strip=True) if mv_el else ''
                    mv = 0
                    if 'm' in mv_text.lower():
                        try:
                            mv = float(mv_text.lower().replace('m', '').replace(',', '.').replace('€', '').strip()) * 1_000_000
                        except:
                            pass
                    elif 'k' in mv_text.lower() or 'th' in mv_text.lower():
                        try:
                            mv = float(mv_text.lower().replace('k', '').replace('th', '').replace(',', '.').replace('€', '').strip()) * 1_000
                        except:
                            pass
                    
                    values.append({
                        'player_id': player_id,
                        'name': name,
                        'market_value': mv,
                        'market_value_currency': 'EUR',
                    })
                except:
                    continue
        
        return values
    
    def scrape_team_injuries(self, team_id: int) -> Dict:
        """Scrape injury data for a single team."""
        injuries = self.fetch_injuries(team_id)
        count = 0
        for inj in injuries:
            if self.db.store_injury('transfermarkt', inj):
                count += 1
        return {'team_id': team_id, 'injuries': count}
    
    def scrape_team_squad(self, team_id: int) -> Dict:
        """Scrape full squad data for a team."""
        squad = self.fetch_squad(team_id)
        if not squad:
            return {'team_id': team_id, 'players': 0}
        
        # Store team
        self.db.store_team('transfermarkt', {
            'team_id': team_id,
            'name': squad.get('team_name', ''),
        })
        
        # Store players
        player_count = 0
        for player in squad.get('players', []):
            if self.db.store_player('transfermarkt', player):
                player_count += 1
        
        # Map team name
        if squad.get('team_name'):
            self.db.add_team_mapping(squad['team_name'], 'transfermarkt',
                                     squad['team_name'], team_id)
        
        return {'team_id': team_id, 'players': player_count}
    
    def scrape_top_clubs_injuries(self, club_ids: List[int] = None) -> Dict:
        """Scrape injuries for top clubs."""
        if club_ids is None:
            # Top clubs from Transfermarkt
            club_ids = [
                27, 31, 5, 12, 18, 41, 76, 79, 82, 134, 154, 155, 177, 182,
                187, 202, 210, 229, 235, 239, 259, 268, 270, 275, 278, 285,
                290, 295, 299, 301, 314, 323, 329, 330, 331, 334, 335, 336,
                337, 338, 339, 340, 341, 342, 343, 344, 345, 346, 347, 348,
                # Additional clubs
                46, 89, 131, 157, 159, 160, 162, 164, 171, 193, 212, 218,
                220, 238, 256, 260, 273, 281, 306, 315, 324, 349, 350, 351,
                352, 353, 354, 355, 356, 357, 358, 359, 360, 361, 362, 363,
                # Bayern, Dortmund, etc.
                27, 31, 5, 12, 18, 41, 76, 79, 82, 134,
            ] + list(range(5000, 5200))  # Lower league teams
        
        total_injuries = 0
        total_players = 0
        
        for cid in club_ids[:300]:  # Max 300 clubs
            try:
                result = self.scrape_team_injuries(cid)
                total_injuries += result['injuries']
                
                squad_result = self.scrape_team_squad(cid)
                total_players += squad_result['players']
                
                log(f'  {squad_result.get("team_id", cid)}: {result["injuries"]} injuries, {squad_result["players"]} players')
                time.sleep(0.5)
            except Exception as e:
                pass
        
        log(f'Transfermarkt heist: {total_injuries} injuries, {total_players} players')
        return {'injuries': total_injuries, 'players': total_players}


# ═══════════════════════════════════════════════════════════════════════
# CLUBELO HEIST ENGINE
# ═══════════════════════════════════════════════════════════════════════

class ClubEloHeist:
    """ClubElo data scraper — historical ratings."""
    
    BASE = 'http://api.clubelo.com'
    
    def __init__(self, session: CurlSession, db: HeistDB):
        self.session = session
        self.db = db
    
    def fetch_team_elo(self, team_name: str, date_from: str = None,
                        date_to: str = None) -> Optional[List]:
        """Fetch Elo ratings for a team over a date range."""
        url = f'{self.BASE}/{urllib.parse.quote(team_name)}'
        if date_from:
            url += f'/{date_from}'
            if date_to:
                url += f'/{date_to}'
        
        resp = self.session.fetch(url, impersonate='chrome120')
        if resp is None:
            return None
        
        try:
            text = resp.text
            lines = text.strip().split('\n')
            if len(lines) < 2:
                return None
            
            headers = lines[0].split(',')
            results = []
            for line in lines[1:]:
                vals = line.split(',')
                if len(vals) >= len(headers):
                    record = dict(zip(headers, vals))
                    results.append(record)
            return results
        except:
            return None
    
    def fetch_top_teams(self, date: str = None) -> Optional[List]:
        """Fetch top teams by Elo on a given date."""
        url = f'{self.BASE}'
        if date:
            url = f'{self.BASE}/{date}'
        
        resp = self.session.fetch(url, impersonate='chrome120')
        if resp is None:
            return None
        
        try:
            text = resp.text
            lines = text.strip().split('\n')
            if len(lines) < 2:
                return None
            headers = lines[0].split(',')
            results = []
            for line in lines[1:]:
                vals = line.split(',')
                if len(vals) >= len(headers):
                    record = dict(zip(headers, vals))
                    results.append(record)
            return results
        except:
            return None
    
    def scrape_all(self) -> Dict:
        """Scrape ClubElo data for all known teams."""
        conn = self.db.connect()
        
        # Get all team names from various sources
        teams = set()
        for source_table in ['agent4_teams', 'fotmob_team_map']:
            try:
                rows = conn.execute(f'SELECT name FROM {source_table} WHERE name IS NOT NULL').fetchall()
                for (name,) in rows:
                    teams.add(name)
            except:
                pass
        
        # Also from sofa historical results
        try:
            rows = conn.execute(
                'SELECT DISTINCT home_team FROM sofa_historical_results LIMIT 2000'
            ).fetchall()
            for (name,) in rows:
                teams.add(name)
        except:
            pass
        
        conn.close()
        
        log(f'ClubElo: fetching ratings for {len(teams)} teams...')
        total = 0
        for team in list(teams)[:1000]:  # Max 1000
            elo_data = self.fetch_team_elo(team, date_from='2024-01-01')
            if elo_data:
                total += len(elo_data)
            time.sleep(0.1)
        
        log(f'ClubElo: {total} rating records')
        return {'teams': len(teams), 'records': total}


# ═══════════════════════════════════════════════════════════════════════
# FOREBET HEIST ENGINE
# ═══════════════════════════════════════════════════════════════════════

class ForebetHeist:
    """Forebet match prediction scraper using curl_cffi."""
    
    BASE = 'https://www.forebet.com'
    
    def __init__(self, session: CurlSession, db: HeistDB):
        self.session = session
        self.db = db
    
    def fetch_predictions(self, url_path: str = '/en/football-tips') -> Optional[Dict]:
        """Fetch match predictions from Forebet."""
        url = f'{self.BASE}{url_path}'
        html = self.session.fetch_html(url, impersonate='chrome120',
                                        referer=self.BASE)
        if not html or not BS4_OK:
            return None
        
        soup = BeautifulSoup(html, 'lxml' if LXML_OK else 'html.parser')
        matches = []
        
        # Parse prediction table rows
        table = soup.select_one('table')
        if not table:
            return None
        
        rows = table.select('tr')
        for row in rows:
            cells = row.select('td')
            if len(cells) < 5:
                continue
            
            try:
                home_el = cells[0]
                away_el = cells[1]
                prob_el = cells[2]
                
                home_team = home_el.get_text(strip=True)
                away_team = away_el.get_text(strip=True)
                prob_text = prob_el.get_text(strip=True)
                
                # Parse probability like "1 45% X 30% 2 25%"
                probs = re.findall(r'(\d+)\s*%', prob_text)
                probs_list = [int(p) for p in probs] if probs else [33, 33, 34]
                
                match = {
                    'source': 'forebet',
                    'home_team': home_team,
                    'away_team': away_team,
                    'prob_h': probs_list[0] if len(probs_list) > 0 else 33,
                    'prob_d': probs_list[1] if len(probs_list) > 1 else 33,
                    'prob_a': probs_list[2] if len(probs_list) > 2 else 34,
                }
                matches.append(match)
            except:
                continue
        
        return {'matches': matches, 'count': len(matches)}


# ═══════════════════════════════════════════════════════════════════════
# DATA QUALITY / DEDUP / EXPORT
# ═══════════════════════════════════════════════════════════════════════

class DataIntegrator:
    """Deduplicate, merge, and export data."""
    
    def __init__(self, db: HeistDB):
        self.db = db
    
    def deduplicate_matches(self) -> Dict:
        """Remove duplicate matches across sources."""
        conn = self.db.connect()
        
        # Find duplicates by home/away/date
        dups = conn.execute('''
            SELECT m1.match_id, m2.match_id, m1.source, m2.source,
                   m1.home_team, m1.away_team, m1.match_date,
                   m1.home_score, m2.home_score,
                   m1.is_finished, m2.is_finished
            FROM agent4_matches m1
            JOIN agent4_matches m2 ON 
                m1.home_team = m2.home_team AND 
                m1.away_team = m2.away_team AND
                m1.match_date = m2.match_date AND
                m1.source != m2.source AND
                m1.match_id < m2.match_id
        ''').fetchall()
        
        # Prefer matches with: is_finished, has_stats, has_shotmap
        kept = []
        removed = []
        
        # For each dup pair, keep the richer one
        for d in dups:
            m1_id, m2_id, s1, s2 = d[0], d[1], d[2], d[3]
            
            m1 = conn.execute('SELECT * FROM agent4_matches WHERE match_id=?', (m1_id,)).fetchone()
            m2 = conn.execute('SELECT * FROM agent4_matches WHERE match_id=?', (m2_id,)).fetchone()
            
            if not m1 or not m2:
                continue
            
            cols = [c[0] for c in conn.execute('PRAGMA table_info(agent4_matches)').fetchall()]
            m1_d = dict(zip(cols, m1))
            m2_d = dict(zip(cols, m2))
            
            # Score points: more complete record wins
            def score(m):
                s = 0
                if m.get('is_finished'): s += 10
                if m.get('home_score') is not None: s += 5
                if m.get('has_stats'): s += 3
                if m.get('has_shotmap'): s += 3
                if m.get('has_lineups'): s += 2
                if m.get('home_xg') is not None: s += 2
                return s
            
            if score(m2_d) > score(m1_d):
                # Remove m1, keep m2
                conn.execute('DELETE FROM agent4_matches WHERE match_id=?', (m1_id,))
                removed.append(m1_id)
                kept.append(m2_id)
            else:
                conn.execute('DELETE FROM agent4_matches WHERE match_id=?', (m2_id,))
                removed.append(m2_id)
                kept.append(m1_id)
        
        conn.commit()
        conn.close()
        
        log(f'Dedup: {len(kept)} kept, {len(removed)} removed')
        return {'kept': len(kept), 'removed': len(removed)}
    
    def export_to_csv(self, output_path: str = None) -> str:
        """Export all matches to CSV."""
        if output_path is None:
            output_path = os.path.join(HEIST_DIR, 'agent4_matches_export.csv')
        
        conn = self.db.connect()
        rows = conn.execute('''
            SELECT match_id, source, home_team, away_team, home_score, away_score,
                   competition, season, match_date, is_finished, 
                   home_xg, away_xg, home_shots, away_shots,
                   home_sot, away_sot, home_possession, away_possession,
                   home_corners, away_corners, home_fouls, away_fouls,
                   home_formation, away_formation, has_lineups, has_stats,
                   has_shotmap, venue, referee, attendance
            FROM agent4_matches
            ORDER BY match_date DESC
        ''').fetchall()
        
        cols = ['match_id', 'source', 'home_team', 'away_team', 'home_score', 'away_score',
                'competition', 'season', 'match_date', 'is_finished',
                'home_xg', 'away_xg', 'home_shots', 'away_shots',
                'home_sot', 'away_sot', 'home_possession', 'away_possession',
                'home_corners', 'away_corners', 'home_fouls', 'away_fouls',
                'home_formation', 'away_formation', 'has_lineups', 'has_stats',
                'has_shotmap', 'venue', 'referee', 'attendance']
        
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(cols)
            writer.writerows(rows)
        
        conn.close()
        log(f'Exported {len(rows)} matches to {output_path}')
        return output_path
    
    def export_stats_report(self) -> Dict:
        """Generate a comprehensive stats report."""
        conn = self.db.connect()
        
        report = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'sources': {},
        }
        
        # Count by source
        for (source,) in conn.execute(
            'SELECT DISTINCT source FROM agent4_matches'
        ).fetchall():
            total = conn.execute(
                'SELECT COUNT(*) FROM agent4_matches WHERE source=?', (source,)
            ).fetchone()[0]
            finished = conn.execute(
                'SELECT COUNT(*) FROM agent4_matches WHERE source=? AND is_finished=1', (source,)
            ).fetchone()[0]
            with_stats = conn.execute(
                'SELECT COUNT(*) FROM agent4_matches WHERE source=? AND has_stats=1', (source,)
            ).fetchone()[0]
            with_shotmap = conn.execute(
                'SELECT COUNT(*) FROM agent4_matches WHERE source=? AND has_shotmap=1', (source,)
            ).fetchone()[0]
            with_lineups = conn.execute(
                'SELECT COUNT(*) FROM agent4_matches WHERE source=? AND has_lineups=1', (source,)
            ).fetchone()[0]
            
            report['sources'][source] = {
                'total': total,
                'finished': finished,
                'with_stats': with_stats,
                'with_shotmap': with_shotmap,
                'with_lineups': with_lineups,
            }
        
        # Overall
        report['total_matches'] = sum(s['total'] for s in report['sources'].values())
        report['total_injuries'] = conn.execute('SELECT COUNT(*) FROM agent4_injuries').fetchone()[0]
        report['total_players'] = conn.execute('SELECT COUNT(*) FROM agent4_players').fetchone()[0]
        report['total_shots'] = conn.execute('SELECT COUNT(*) FROM agent4_shotmaps').fetchone()[0]
        
        # Date range
        row = conn.execute(
            'SELECT MIN(match_date), MAX(match_date) FROM agent4_matches'
        ).fetchone()
        report['date_range'] = {'min': row[0], 'max': row[1]} if row else {}
        
        # Competition breakdown
        comps = conn.execute(
            'SELECT competition, COUNT(*) as cnt FROM agent4_matches GROUP BY competition ORDER BY cnt DESC LIMIT 20'
        ).fetchall()
        report['top_competitions'] = [{'name': r[0], 'matches': r[1]} for r in comps]
        
        conn.close()
        
        # Save report
        report_path = os.path.join(HEIST_DIR, 'agent4_heist_report.json')
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        log(f'Report saved to {report_path}')
        return report


# ═══════════════════════════════════════════════════════════════════════
# MAIN ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════

class Agent4Heist:
    """Master orchestrator for all heist operations."""
    
    def __init__(self):
        self.db = HeistDB()
        self.session = CurlSession()
        
        self.fotmob = FotMobHeist(self.session, self.db)
        self.fbref = FBrefHeist(self.session, self.db)
        self.understat = UnderstatHeist(self.session, self.db)
        self.statsbomb = StatsBombHeist(self.session, self.db)
        self.transfermarkt = TransfermarktHeist(self.session, self.db)
        self.clubelo = ClubEloHeist(self.session, self.db)
        self.forebet = ForebetHeist(self.session, self.db)
        self.integrator = DataIntegrator(self.db)
    
    def check_system(self) -> Dict:
        """Check system readiness."""
        checks = {
            'curl_cffi': CURL_OK,
            'bs4': BS4_OK,
            'lxml': LXML_OK,
            'pandas': PD_OK,
            'numpy': NP_OK,
            'tqdm': TQDM_OK,
            'project_dir': PROJECT_DIR,
            'db_path': DB_PATH,
            'db_exists': os.path.exists(DB_PATH),
            'heist_dir': HEIST_DIR,
            'heist_dir_exists': os.path.exists(HEIST_DIR),
        }
        
        if CURL_OK:
            try:
                r = curl_requests.get(
                    'https://www.google.com',
                    impersonate='chrome120',
                    timeout=5
                )
                checks['internet'] = r.status_code == 200
            except:
                checks['internet'] = False
        else:
            checks['internet'] = False
        
        return checks
    
    def quick_stats(self) -> Dict:
        """Get quick stats about current data."""
        conn = self.db.connect()
        stats = {}
        
        try:
            stats['agent4_matches'] = conn.execute(
                'SELECT COUNT(*) FROM agent4_matches'
            ).fetchone()[0]
        except:
            stats['agent4_matches'] = 0
        
        try:
            stats['agent4_injuries'] = conn.execute(
                'SELECT COUNT(*) FROM agent4_injuries'
            ).fetchone()[0]
        except:
            stats['agent4_injuries'] = 0
        
        try:
            stats['agent4_players'] = conn.execute(
                'SELECT COUNT(*) FROM agent4_players'
            ).fetchone()[0]
        except:
            stats['agent4_players'] = 0
        
        try:
            stats['agent4_shotmaps'] = conn.execute(
                'SELECT COUNT(*) FROM agent4_shotmaps'
            ).fetchone()[0]
        except:
            stats['agent4_shotmaps'] = 0
        
        try:
            stats['sofa_matches'] = conn.execute(
                'SELECT COUNT(*) FROM sofa_historical_results'
            ).fetchone()[0]
        except:
            stats['sofa_matches'] = 0
        
        try:
            stats['statsbomb_matches'] = conn.execute(
                'SELECT COUNT(*) FROM statsbomb_matches'
            ).fetchone()[0]
        except:
            stats['statsbomb_matches'] = 0
        
        try:
            stats['statsbomb_events'] = conn.execute(
                'SELECT COUNT(*) FROM statsbomb_events'
            ).fetchone()[0]
        except:
            stats['statsbomb_events'] = 0
        
        conn.close()
        return stats
    
    def run_heist_fotmob(self, league_ids: List[int] = None,
                          parallel: int = 4) -> Dict:
        """Run FotMob heist."""
        log('🔥 FOTMOB HEIST INITIATED', 'HEIST')
        self.db.update_progress('fotmob', 'full_heist', 'running')
        
        result = self.fotmob.scrape_multiple_leagues(
            league_ids=league_ids, parallel=parallel
        )
        
        # Also scrape team squads and injuries
        log('📡 Scraping FotMob team squads...')
        squad_result = self.fotmob.scrape_team_squads(team_limit=200)
        
        log('📡 Scraping FotMob player injuries...')
        injury_result = self.fotmob.scrape_player_injuries()
        
        result['squads'] = squad_result
        result['injuries'] = injury_result
        
        self.db.update_progress('fotmob', 'full_heist', 'completed',
                               result.get('total_matches', 0))
        return result
    
    def run_heist_fbref(self, parallel: int = 3) -> Dict:
        """Run FBref heist."""
        log('🔥 FBREF HEIST INITIATED', 'HEIST')
        self.db.update_progress('fbref', 'full_heist', 'running')
        result = self.fbref.scrape_all(parallel=parallel)
        self.db.update_progress('fbref', 'full_heist', 'completed',
                               result.get('total_matches', 0))
        return result
    
    def run_heist_understat(self) -> Dict:
        """Run Understat heist."""
        log('🔥 UNDERSTAT HEIST INITIATED', 'HEIST')
        self.db.update_progress('understat', 'full_heist', 'running')
        result = self.understat.scrape_all()
        self.db.update_progress('understat', 'full_heist', 'completed',
                               result.get('total_matches', 0))
        return result
    
    def run_heist_statsbomb(self, max_matches: int = 100) -> Dict:
        """Run StatsBomb heist for additional events."""
        log('🔥 STATSBOMB HEIST INITIATED', 'HEIST')
        self.db.update_progress('statsbomb', 'full_heist', 'running')
        result = self.statsbomb.scrape_new_competitions(max_matches=max_matches)
        self.db.update_progress('statsbomb', 'full_heist', 'completed',
                               result.get('matches', 0))
        return result
    
    def run_heist_transfermarkt(self) -> Dict:
        """Run Transfermarkt heist for injuries and squads."""
        log('🔥 TRANSFERMARKT HEIST INITIATED', 'HEIST')
        self.db.update_progress('transfermarkt', 'full_heist', 'running')
        result = self.transfermarkt.scrape_top_clubs_injuries()
        self.db.update_progress('transfermarkt', 'full_heist', 'completed',
                               result.get('injuries', 0) + result.get('players', 0))
        return result
    
    def run_heist_international_2026(self) -> Dict:
        """Specifically target 2026 season + international tournaments."""
        log('🔥 INTERNATIONAL / 2026 HEIST', 'HEIST')
        self.db.update_progress('agent4', 'international_2026', 'running')
        
        # 1. FotMob 2026 seasons
        log('📡 FotMob 2026 seasons...')
        fotmob_2026 = self.fotmob.scrape_2026_season()
        
        # 2. FotMob international tournaments
        log('📡 FotMob international tournaments...')
        fotmob_intl = self.fotmob.scrape_international_tournaments()
        
        # 3. FotMob friendlies
        log('📡 FotMob friendlies...')
        fotmob_friendly = self.fotmob.scrape_friendlies()
        
        # 4. FBref World Cup / Euro / Copa data
        log('📡 FBref international competitions...')
        for cname, cslug in FBREF_COMPS.items():
            if any(kw in cname.lower() for kw in ['world cup', 'euro', 'copa', 'asian', 'africa', 'gold cup']):
                try:
                    for season in ['2025-2026', '2024-2025']:
                        self.fbref.scrape_league(cname, cslug, [season])
                        time.sleep(1.0)
                except:
                    pass
        
        # 5. Understat current season
        log('📡 Understat current...')
        for league in UNDERSTAT_LEAGUES:
            self.understat.scrape_league(league, ['2025', '2024'])
            time.sleep(0.5)
        
        result = {
            'fotmob_2026_match_count': fotmob_2026.get('total_matches', 0),
            'fotmob_international_match_count': fotmob_intl.get('total_matches', 0),
            'fotmob_friendly_match_count': fotmob_friendly.get('total_matches', 0),
        }
        
        self.db.update_progress('agent4', 'international_2026', 'completed',
                               sum(result.values()))
        return result
    
    def run_full_heist(self) -> Dict:
        """Run ALL heist operations."""
        start = time.time()
        log('╔══════════════════════════════════════════════════════════╗')
        log('║   🔥🔥🔥 AGENT 4 — FULL HEIST OPERATION 🔥🔥🔥         ║')
        log('║   SHADOWHACKER-GOD — DΞMON CORE v9999999               ║')
        log('╚══════════════════════════════════════════════════════════╝')
        
        results = {}
        
        # Phase 1: System check
        log('\n📋 Phase 0: System check')
        system = self.check_system()
        log(f'  curl_cffi: {system["curl_cffi"]} | BS4: {system["bs4"]} | Internet: {system["internet"]}')
        results['system'] = system
        
        if not system['curl_cffi']:
            log('❌ curl_cffi not available! Install: pip install curl_cffi', 'CRITICAL')
            return results
        
        # Phase 1: FotMob (largest source)
        log('\n📡 Phase 1: FotMob BULK HEIST')
        results['fotmob'] = self.run_heist_fotmob(parallel=4)
        self._write_phase_progress('Phase 1: FotMob', results['fotmob'])
        
        # Phase 2: FBref
        log('\n📡 Phase 2: FBref HEIST')
        results['fbref'] = self.run_heist_fbref(parallel=3)
        self._write_phase_progress('Phase 2: FBref', results['fbref'])
        
        # Phase 3: Understat
        log('\n📡 Phase 3: Understat HEIST')
        results['understat'] = self.run_heist_understat()
        self._write_phase_progress('Phase 3: Understat', results['understat'])
        
        # Phase 4: International / 2026
        log('\n📡 Phase 4: International & 2026 HEIST')
        results['international'] = self.run_heist_international_2026()
        self._write_phase_progress('Phase 4: International/2026', results['international'])
        
        # Phase 5: Transfermarkt (injuries, squads)
        log('\n📡 Phase 5: Transfermarkt HEIST')
        results['transfermarkt'] = self.run_heist_transfermarkt()
        self._write_phase_progress('Phase 5: Transfermarkt', results['transfermarkt'])
        
        # Phase 6: StatsBomb additional events
        log('\n📡 Phase 6: StatsBomb HEIST')
        results['statsbomb'] = self.run_heist_statsbomb(max_matches=50)
        self._write_phase_progress('Phase 6: StatsBomb', results['statsbomb'])
        
        # Phase 7: Dedup & Export
        log('\n📡 Phase 7: Data Quality')
        results['dedup'] = self.integrator.deduplicate_matches()
        results['report'] = self.integrator.export_stats_report()
        csv_path = self.integrator.export_to_csv()
        results['csv_export'] = csv_path
        self._write_phase_progress('Phase 7: Data Quality', results['dedup'])
        
        # Summary
        elapsed = time.time() - start
        results['elapsed_seconds'] = elapsed
        results['elapsed_human'] = f'{elapsed/60:.1f} minutes'
        
        stats = self.quick_stats()
        results['final_stats'] = stats
        
        log('\n╔══════════════════════════════════════════════════════════╗')
        log('║   ✅ AGENT 4 HEIST COMPLETE                            ║')
        log(f'║   Time: {results["elapsed_human"]:>38s} ║')
        log(f'║   Agent4 Matches: {stats.get("agent4_matches", 0):>30d} ║')
        log(f'║   Injuries: {stats.get("agent4_injuries", 0):>32d} ║')
        log(f'║   Players: {stats.get("agent4_players", 0):>32d} ║')
        log(f'║   Shotmap Events: {stats.get("agent4_shotmaps", 0):>27d} ║')
        log('╚══════════════════════════════════════════════════════════╝')
        
        return results
    
    def _write_phase_progress(self, phase_name: str, data: Dict):
        """Update progress markdown for the orchestrator."""
        try:
            stats = self.quick_stats()
            md = f"""# Agent 4 — Heist Progress

## System Status
- curl_cffi: ✅
- BS4: ✅
- Internet: ✅

## Overall Stats
- Agent4 Matches: {stats.get('agent4_matches', 0):,}
- Agent4 Injuries: {stats.get('agent4_injuries', 0):,}
- Agent4 Players: {stats.get('agent4_players', 0):,}
- Agent4 Shotmaps: {stats.get('agent4_shotmaps', 0):,}
- SofaScore Matches: {stats.get('sofa_matches', 0):,}
- StatsBomb Events: {stats.get('statsbomb_events', 0):,}

## Last Phase: {phase_name}
- Data: {json.dumps(data, default=str)[:200]}

## Timestamp
{datetime.now(timezone.utc).isoformat()}
"""
            update_progress(md)
        except:
            pass
    
    def safe_close(self):
        """Clean up resources."""
        try:
            self.db.close()
        except:
            pass


# ═══════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════

def main():
    """Main entry point for the heist engine."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='🔥 AGENT 4 — Advanced Multi-Source Football Heist Engine',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python agent4_heist_advanced.py --full
  python agent4_heist_advanced.py --fotmob
  python agent4_heist_advanced.py --fotmob --leagues 47,53,54
  python agent4_heist_advanced.py --fbref
  python agent4_heist_advanced.py --understat
  python agent4_heist_advanced.py --statsbomb
  python agent4_heist_advanced.py --transfermarkt
  python agent4_heist_advanced.py --international
  python agent4_heist_advanced.py --stats
  python agent4_heist_advanced.py --export
  python agent4_heist_advanced.py --check
        """
    )
    
    parser.add_argument('--full', action='store_true', help='Run full heist (all sources)')
    parser.add_argument('--fotmob', action='store_true', help='Run FotMob heist')
    parser.add_argument('--fbref', action='store_true', help='Run FBref heist')
    parser.add_argument('--understat', action='store_true', help='Run Understat heist')
    parser.add_argument('--statsbomb', action='store_true', help='Run StatsBomb heist')
    parser.add_argument('--transfermarkt', action='store_true', help='Run Transfermarkt heist')
    parser.add_argument('--international', action='store_true', help='Run International/2026 heist')
    parser.add_argument('--stats', action='store_true', help='Show quick stats')
    parser.add_argument('--export', action='store_true', help='Export all data to CSV')
    parser.add_argument('--check', action='store_true', help='System check')
    parser.add_argument('--dedup', action='store_true', help='Deduplicate only')
    parser.add_argument('--leagues', type=str, help='Comma-separated FotMob league IDs')
    parser.add_argument('--parallel', type=int, default=4, help='Parallel workers (default: 4)')
    parser.add_argument('--team-limit', type=int, default=200, help='Team limit for squad/injury scrape')
    
    args = parser.parse_args()
    
    log('🔥' * 34)
    log('🔥  AGENT 4 — ADVANCED MULTI-SOURCE FOOTBALL HEIST ENGINE')
    log('🔥  SHADOWHACKER-GOD • DΞMON CORE v9999999 • SHΔDØW.EXE')
    log('🔥' * 34)
    log('')
    
    heist = Agent4Heist()
    
    try:
        if args.check:
            checks = heist.check_system()
            log('\n=== System Check ===')
            for k, v in checks.items():
                status = '✅' if v else '❌'
                log(f'  {status} {k}: {v}')
            return
        
        if args.stats:
            stats = heist.quick_stats()
            log('\n=== Quick Stats ===')
            for k, v in stats.items():
                log(f'  {k}: {v:,}')
            return
        
        if args.dedup:
            result = heist.integrator.deduplicate_matches()
            log(f'Dedup: {result}')
            return
        
        if args.export:
            path = heist.integrator.export_to_csv()
            log(f'Exported to {path}')
            return
        
        if args.full:
            heist.run_full_heist()
            return
        
        if args.international:
            heist.run_heist_international_2026()
        
        if args.fotmob:
            league_ids = None
            if args.leagues:
                league_ids = [int(x.strip()) for x in args.leagues.split(',')]
            heist.run_heist_fotmob(league_ids=league_ids, parallel=args.parallel)
        
        if args.fbref:
            heist.run_heist_fbref(parallel=min(args.parallel, 3))
        
        if args.understat:
            heist.run_heist_understat()
        
        if args.statsbomb:
            heist.run_heist_statsbomb(max_matches=100)
        
        if args.transfermarkt:
            heist.run_heist_transfermarkt()
        
        # If no specific operation, show help
        if not any([args.full, args.fotmob, args.fbref, args.understat,
                     args.statsbomb, args.transfermarkt, args.international,
                     args.stats, args.export, args.check, args.dedup]):
            parser.print_help()
    
    finally:
        heist.safe_close()


if __name__ == '__main__':
    main()
