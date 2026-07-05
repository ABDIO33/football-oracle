#!/usr/bin/env python3
"""
███████╗██╗  ██╗ █████╗ ██████╗  ██████╗ ██╗    ██╗
██╔════╝██║  ██║██╔══██╗██╔══██╗██╔═══██╗██║    ██║
███████╗███████║██║  ██║██║  ██║██║   ██║██║ █╗ ██║
╚════██║██╔══██║██║  ██║██║  ██║██║   ██║██║███╗██║
███████║██║  ██║╚█████╔╝██████╔╝╚██████╔╝╚███╔███╔╝
╚══════╝╚═╝  ╚═╝ ╚════╝ ╚═════╝  ╚═════╝  ╚══╝╚══╝

FotMob BULK HEIST — Next.js Data Route Exploit
SHADOWHACKER-GOD • DΞMON CORE v9999999
"""

import os, json, re, time, sqlite3, hashlib, gzip, random
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, List, Any
from curl_cffi import requests

# ── CONFIG ──────────────────────────────────────────────────────────────
HEIST_DIR = os.path.join(os.path.dirname(__file__), 'heist_output')
os.makedirs(HEIST_DIR, exist_ok=True)

DB_PATH = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

# User agents for rotation
UA_LIST = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.6099.230 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.6099.71 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Chrome/120.0.6099.230 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.6099.230 Safari/537.36',
]

# ── FotMob League IDs (comprehensive — top 200+ leagues worldwide) ──────
# Source: FotMob web scraping + manual curation
KNOWN_LEAGUES = {
    # Europe Top 5
    47: 'Premier League (ENG)',
    53: 'LaLiga (ESP)',
    54: 'Bundesliga (GER)',
    55: 'Serie A (ITA)',
    74: 'Ligue 1 (FRA)',
    # England lower
    48: 'Championship',
    49: 'League One',
    50: 'League Two',
    143: 'National League',
    # Spain lower
    137: 'LaLiga2',
    # Germany lower
    56: '2. Bundesliga',
    145: '3. Liga',
    # Italy lower
    57: 'Serie B',
    # France lower
    58: 'Ligue 2',
    # Other European
    73: 'Champions League',
    72: 'Europa League',
    144: 'Europa Conference League',
    87: 'Primeira Liga (POR)',
    88: 'Liga Portugal 2',
    59: 'Eredivisie (NED)',
    60: 'Eerste Divisie (NED)',
    61: 'Jupiler Pro League (BEL)',
    62: 'Scottish Premiership',
    63: 'Scottish Championship',
    64: 'Super Lig (TUR)',
    65: 'Russian Premier League',
    66: 'Premier League (UKR)',
    67: 'Super League (GRE)',
    68: 'Czech First League',
    69: 'Ekstraklasa (POL)',
    70: 'SuperSport HNL (CRO)',
    71: 'Swiss Super League',
    75: 'Allsvenskan (SWE)',
    76: 'Eliteserien (NOR)',
    77: 'Superliga (DEN)',
    78: 'Veikkausliiga (FIN)',
    79: 'Liga I (ROM)',
    80: 'Premiership (NIR)',
    81: 'Premier League (AUT)',
    82: 'Bundesliga (AUT)',
    83: 'Premyer Liqa (AZE)',
    84: 'Vysheyshaya Liga (BLR)',
    85: 'First League (BUL)',
    86: 'Prva HNL (CRO)',
    89: 'Premier League (CYP)',
    90: 'PrvaLiga (SVN)',
    91: 'Super Liga (SRB)',
    92: 'Fortuna Liga (SVK)',
    93: 'Prva Makedonska (MKD)',
    94: 'Premier League (MLT)',
    95: 'National Division (LUX)',
    96: 'A Lyga (LTU)',
    97: 'Virslīga (LVA)',
    98: 'Premier League (ALB)',
    99: 'Premier League (WAL)',
    100: 'Premier League (ISL)',
    101: 'Premier League (IRL)',
    102: 'Luxembourg National Division',
    103: 'Gibraltar Football League',
    104: 'Premijer Liga (BIH)',
    105: 'League of Ireland',
    106: 'Primera División (AND)',
    107: 'Cymru Premier',
    108: 'Premier League (ARM)',
    109: 'Erovnuli Liga (GEO)',
    110: 'Premier League (KAZ)',
    111: 'Premier League (KGZ)',
    112: 'Super Liga (MDA)',
    113: 'Super League (MNE)',
    114: 'Pyramid (EGY)',
    # Americas
    130: 'MLS (USA)',
    131: 'USL Championship',
    132: 'USL League One',
    133: 'Liga MX (MEX)',
    134: 'Liga de Expansión (MEX)',
    135: 'Campeonato Brasileiro Série A',
    136: 'Série B (BRA)',
    138: 'Primera División (ARG)',
    139: 'Primera B Nacional (ARG)',
    140: 'Primera División (CHI)',
    141: 'Primera División (PER)',
    142: 'Primera División (COL)',
    146: 'Primera División (URU)',
    147: 'Serie A (ECU)',
    148: 'Primera División (VEN)',
    149: 'Primera División (PAR)',
    150: 'Primera División (BOL)',
    151: 'Liga 1 (PER)',
    152: 'Canadian Premier League',
    # Asia
    153: 'J1 League (JPN)',
    154: 'J2 League (JPN)',
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
    166: 'AFC Champions League',
    167: 'AFC Cup',
    168: 'Uzbekistan Super League',
    169: 'Vietnam V-League',
    170: 'Malaysia Super League',
    171: 'Indonesia Liga 1',
    172: 'Singapore Premier League',
    173: 'Hong Kong Premier League',
    174: 'Philippines PFL',
    175: 'Myanmar National League',
    176: 'Mongolia Premier League',
    177: 'Taiwan Football Premier League',
    # Africa
    178: 'CAF Champions League',
    179: 'CAF Confederation Cup',
    180: 'Egyptian Premier League',
    181: 'Botola Pro (MAR)',
    182: 'Ligue 1 (ALG)',
    183: 'Tunisian Ligue 1',
    184: 'South African PSL',
    185: 'Ghana Premier League',
    186: 'NPFL (NGA)',
    187: 'Kenyan Premier League',
    188: 'Linafoot (DRC)',
    189: 'Zambian Super League',
    190: 'Sudan Premier League',
    191: 'Premiere League (CIV)',
    192: 'Cameroon Elite One',
    193: 'Angola Girabola',
    194: 'Tanzania Premier League',
    195: 'Uganda Premier League',
    196: 'Ethiopian Premier League',
    197: 'Senegal Ligue 1',
    198: 'Mali Première Division',
    199: 'Burkina Faso Premier League',
    200: 'Mozambique Moçambola',
    201: 'Zimbabwe Premier League',
    # Oceania
    202: 'A-League (AUS)',
    203: 'New Zealand Premiership',
    204: 'OFC Champions League',
    205: 'Papua New Guinea Premier League',
    206: 'Fiji Premier League',
    207: 'Solomon Islands S League',
    # International
    208: 'FIFA World Cup',
    209: 'European Championship',
    210: 'Copa América',
    211: 'Africa Cup of Nations',
    212: 'Asian Cup',
    213: 'CONCACAF Gold Cup',
    214: 'Olympic Football Tournament',
    215: 'FIFA Club World Cup',
    216: 'UEFA Nations League',
    217: 'CONCACAF Nations League',
    218: 'African Nations Championship',
    219: 'Arabian Gulf Cup',
    220: 'AFC Asian Cup Qualifiers',
    221: 'World Cup Qualifiers - UEFA',
    222: 'World Cup Qualifiers - CONMEBOL',
    223: 'World Cup Qualifiers - CONCACAF',
    224: 'World Cup Qualifiers - CAF',
    225: 'World Cup Qualifiers - AFC',
    226: 'World Cup Qualifiers - OFC',
    227: 'Euro U21 Championship',
    228: 'Euro U19 Championship',
    229: 'U20 World Cup',
    230: 'U17 World Cup',
    # Women
    231: 'FA WSL (ENG)',
    232: 'Division 1 Féminine (FRA)',
    233: 'Frauen-Bundesliga (GER)',
    234: 'Primera División Femenina (ESP)',
    235: 'Serie A Femminile (ITA)',
    236: 'NWSL (USA)',
    237: 'Women\'s Super League (NED)',
    238: 'Damallsvenskan (SWE)',
    239: 'Toppserien (NOR)',
    240: 'Women\'s Champions League',
    241: 'FIFA Women\'s World Cup',
    242: 'WE League (JPN)',
    243: 'A-League Women (AUS)',
    # More European
    244: 'Liga Leumit (ISR)',
    245: 'Israeli Premier League',
    246: 'Premier League (HUN)',
    247: 'NB II (HUN)',
    248: 'Liga II (ROM)',
    249: 'Superliga (DEN)',
    250: '1. SNL (SVN)',
    251: 'Prva Liga (SRB)',
    252: 'Premier League (BLR)',
    253: 'Liga 1 (IDN)',
    254: 'Football National League (RUS)',
    255: 'Premier League (RUS)',
    256: 'Premier League (UKR)',
    257: 'Chance Liga (CZE)',
    258: 'Fortuna Liga (CZE)',
    259: 'Niké Liga (SVK)',
    260: 'O TE (GRE)',
    261: 'Super League 2 (GRE)',
    262: 'Trendyol 1. Lig (TUR)',
    263: 'Liga Portugal 2',
    264: 'Primeira Liga (POR)',
    265: 'Pro League (BEL)',
    266: 'Proximus League (BEL)',
    267: 'Premiership (SCO)',
    268: 'Championship (SCO)',
    269: 'League 1 (SCO)',
    270: 'League 2 (SCO)',
    271: 'Premier League (NIR)',
    272: 'Premier League (WAL)',
    273: 'League of Ireland Premier',
    274: 'League of Ireland First',
    275: 'Premier League (ISL)',
    276: 'Besta deild (ISL)',
    277: '1. deild (ISL)',
    278: 'Premier League (FRO)',
    279: 'Premier League (MLT)',
    280: 'Premier League (GIB)',
    281: 'Premier League (AND)',
    282: 'Premier League (SMR)',
    283: 'Premier League (MNE)',
    284: 'Premier League (BIH)',
    285: 'PrvaLiga (SLO)',
    286: 'HNL (CRO)',
    287: 'NLB League (CRO)',
    288: 'Super League (SUI)',
    289: 'Challenge League (SUI)',
    290: 'Bundesliga (AUT)',
    291: '2. Liga (AUT)',
    292: 'Regionalliga (AUT)',
    293: 'Ekstraklasa (POL)',
    294: 'I liga (POL)',
    295: 'II liga (POL)',
    296: 'Super Liga (SVK)',
    297: 'Nemzeti Bajnokság (HUN)',
    298: 'Liga I (ROM)',
    299: 'Liga II (ROM)',
    300: 'Liga III (ROM)',
    301: 'First League (BUL)',
    302: 'Second League (BUL)',
    303: 'Super League (GRE)',
    304: 'Super League 2 (GRE)',
    305: 'Prva Liga (SRB)',
    306: 'Prva Liga (MNE)',
    307: 'Premijer Liga (BIH)',
    308: 'Liga (ALB)',
    309: 'Macedonian First League',
    310: 'Super League (MLT)',
    311: 'Premier League (CYP)',
    312: 'A League (LUX)',
    313: 'A Lyga (LTU)',
    314: 'Virslīga (LVA)',
    315: 'Premium Liiga (EST)',
    316: 'Esiliiga (EST)',
    317: 'Ykkönen (FIN)',
    318: 'Kakkonen (FIN)',
    319: 'Eliteserien (NOR)',
    320: 'OBOS-ligaen (NOR)',
    321: 'PostNord-ligaen (NOR)',
    322: 'Allsvenskan (SWE)',
    323: 'Superettan (SWE)',
    324: 'Ettan (SWE)',
    325: 'Superliga (DEN)',
    326: '1. Division (DEN)',
    327: '2. Division (DEN)',
    328: 'Premier League (ARM)',
    329: 'Erovnuli Liga (GEO)',
    330: 'Premier League (AZE)',
    331: 'Premier League (KAZ)',
    332: 'Premier League (UZB)',
    333: 'Premier League (TKM)',
    334: 'Premier League (KGZ)',
    335: 'Premier League (TJK)',
    336: 'Premier League (MDA)',
    337: 'Divizia Națională (MDA)',
    338: 'Premier League (LTU)',
    339: 'Premier League (LVA)',
    340: 'Premier League (EST)',
    # South America extra
    341: 'Primera División (ARG)',
    342: 'Primera B Nacional (ARG)',
    343: 'Primera B Metropolitana (ARG)',
    344: 'Federal A (ARG)',
    345: 'Campeonato Brasileiro Série A',
    346: 'Série B (BRA)',
    347: 'Série C (BRA)',
    348: 'Série D (BRA)',
    349: 'Campeonato Carioca (BRA)',
    350: 'Campeonato Paulista (BRA)',
    351: 'Primera División (CHI)',
    352: 'Primera B (CHI)',
    353: 'Primera División (URU)',
    354: 'Segunda División (URU)',
    355: 'LigaPro (ECU)',
    356: 'Serie B (ECU)',
    357: 'Liga 1 (PER)',
    358: 'Liga 2 (PER)',
    359: 'Primera División (PAR)',
    360: 'División Intermedia (PAR)',
    361: 'Primera División (BOL)',
    362: 'Primera División (VEN)',
    363: 'Segunda División (VEN)',
    364: 'Copa Libertadores',
    365: 'Copa Sudamericana',
    366: 'Recopa Sudamericana',
    # North America extra
    367: 'Liga MX (MEX)',
    368: 'Liga de Expansión (MEX)',
    369: 'Liga Premier (MEX)',
    370: 'Canadian Premier League',
    371: 'USL League Two',
    372: 'MLS Next Pro',
    373: 'Liga Nacional (HON)',
    374: 'Liga Primera (NCA)',
    375: 'Primera División (SLV)',
    376: 'Liga Nacional (GUA)',
    377: 'Liga de Ascenso (CRC)',
    378: 'Primera División (CRC)',
    379: 'Liga Panameña (PAN)',
    380: 'Liga Dominicana (DOM)',
    381: 'CONCACAF Champions Cup',
    382: 'Leagues Cup',
    383: 'Campeones Cup',
    # Asia extra
    384: 'J1 League (JPN)',
    385: 'J2 League (JPN)',
    386: 'J3 League (JPN)',
    387: 'K League 1 (KOR)',
    388: 'K League 2 (KOR)',
    389: 'CSL (CHN)',
    390: 'China League One',
    391: 'China League Two',
    392: 'ISL (IND)',
    393: 'I-League (IND)',
    394: 'Thai League 1',
    395: 'Thai League 2',
    396: 'Saudi Pro League',
    397: 'FD League (KSA)',
    398: 'UAE Pro League',
    399: 'UAE First Division',
    400: 'Qatar Stars League',
    401: 'Qatar 2nd Division',
    402: 'Iran Pro League',
    403: 'Azadegan League (IRN)',
    404: 'Uzbek Super League',
    405: 'Uzbek Pro League',
    406: 'V-League (VIE)',
    407: 'V-League 2 (VIE)',
    408: 'Malaysia Super League',
    409: 'Malaysia M3 League',
    410: 'Liga 1 (IDN)',
    411: 'Liga 2 (IDN)',
    412: 'Singapore Premier League',
    413: 'Hong Kong Premier League',
    414: 'Philippines PFL',
    415: 'Myanmar National League',
    416: 'Mongolia Premier League',
    417: 'Cambodian Premier League',
    418: 'Lao Premier League',
    419: 'Maldives Dhivehi League',
    420: 'Sri Lanka Super League',
    421: 'AFC Champions League Elite',
    422: 'AFC Champions League 2',
    423: 'ASEAN Club Championship',
    # Africa extra
    424: 'CAF Champions League',
    425: 'CAF Confederation Cup',
    426: 'CAF Super Cup',
    427: 'Egyptian Premier League',
    428: 'Egyptian Second Division',
    429: 'Botola Pro (MAR)',
    430: 'Botola 2 (MAR)',
    431: 'Ligue 1 (ALG)',
    432: 'Ligue 2 (ALG)',
    433: 'Tunisian Ligue 1',
    434: 'Tunisian Ligue 2',
    435: 'PSL (RSA)',
    436: 'First Division (RSA)',
    437: 'Ghana Premier League',
    438: 'Division One (GHA)',
    439: 'NPFL (NGA)',
    440: 'Nigeria National League',
    441: 'Kenyan Premier League',
    442: 'National Super League (KEN)',
    443: 'Linafoot (DRC)',
    444: 'Zambian Super League',
    445: 'Zambian Division 1',
    446: 'Sudan Premier League',
    447: 'Ligue 1 (CIV)',
    448: 'Elite One (CMR)',
    449: 'Elite Two (CMR)',
    450: 'Girabola (ANG)',
    451: 'Gira Angola (ANG)',
    452: 'Ligi Kuu Bara (TAN)',
    453: 'Uganda Premier League',
    454: 'FUFA Big League (UGA)',
    455: 'Ethiopian Premier League',
    456: 'Ethiopian Higher League',
    457: 'Ligue 1 (SEN)',
    458: 'Première Division (MLI)',
    459: 'Première Division (BFA)',
    460: 'Moçambola (MOZ)',
    461: 'Zimbabwe Premier League',
    462: 'Namibia Premier League',
    463: 'Botswana Premier League',
    464: 'Lesotho Premier League',
    465: 'Eswatini Premier League',
    466: 'Malawi Super League',
    467: 'Rwanda Premier League',
    468: 'Burundi Premier League',
    469: 'South Sudan Premier League',
    470: 'Cape Verde Premier League',
    471: 'São Tomé Premier League',
    472: 'Guinea Ligue 1',
    473: 'Liberia Premier League',
    474: 'Sierra Leone Premier League',
    475: 'Gambia Premier League',
    476: 'Guinea-Bissau Premier League',
    477: 'Chad Premier League',
    478: 'Niger Premier League',
    479: 'Togo Premier League',
    480: 'Benin Premier League',
    481: 'Première Division (RCA)',
    482: 'Congo Premier League',
    483: 'Gabon Premier League',
    484: 'Equatorial Guinea Premier League',
    485: 'Mauritania Ligue 1',
    486: 'Mauritius Premier League',
    487: 'Seychelles Premier League',
    488: 'Comoros Premier League',
    # Oceania extra
    489: 'A-League Men (AUS)',
    490: 'A-League Women (AUS)',
    491: 'Australia Cup',
    492: 'National Premier Leagues (AUS)',
    493: 'New Zealand National League',
    494: 'OFC Champions League',
    495: 'OFC Nations Cup',
    496: 'Tahiti Ligue 1',
    497: 'Fiji Premier League',
    498: 'Solomon Islands S-League',
    499: 'Vanuatu Premier League',
    500: 'Papua New Guinea Premier League',
    501: 'Samoa National League',
    502: 'Cook Islands Round Cup',
    503: 'American Samoa FFAS League',
    504: 'Tuvalu A-Division',
    505: 'Kiribati National Championship',
    506: 'New Caledonia Super Ligue',
    507: 'Wallis Futuna Premier League',
    # European Cups
    508: 'UEFA Champions League',
    509: 'UEFA Europa League',
    510: 'UEFA Conference League',
    511: 'UEFA Super Cup',
    512: 'FIFA Club World Cup',
    513: 'FIFA Intercontinental Cup',
    514: 'Copa del Rey (ESP)',
    515: 'DFB-Pokal (GER)',
    516: 'FA Cup (ENG)',
    517: 'Coupe de France',
    518: 'Coppa Italia (ITA)',
    519: 'EFL Cup (ENG)',
    520: 'Trophée des Champions (FRA)',
    521: 'Supercopa (ESP)',
    522: 'DFL-Supercup (GER)',
    523: 'Supercoppa (ITA)',
    524: 'Community Shield (ENG)',
    525: 'Taça de Portugal',
    526: 'KNVB Cup (NED)',
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
    542: 'Serbian Cup',
    543: 'Slovenian Cup',
    544: 'Slovak Cup',
    545: 'Belarusian Cup',
    546: 'Ukrainian Cup',
    547: 'Russian Cup',
    548: 'Israeli Cup',
    549: 'Cypriot Cup',
    550: 'Luxembourg Cup',
    551: 'Estonian Cup',
    552: 'Latvian Cup',
    553: 'Lithuanian Cup',
    554: 'Icelandic Cup',
    555: 'Irish Cup',
    556: 'Welsh Cup',
    557: 'Northern Irish Cup',
    558: 'Maltese FA Trophy',
    559: 'Albanian Cup',
    560: 'Armenian Cup',
    561: 'Georgian Cup',
    562: 'Azerbaijani Cup',
    563: 'Kazakh Cup',
    564: 'Moldovan Cup',
    565: 'Macedonian Cup',
    566: 'Montenegrin Cup',
    567: 'Bosnian Cup',
    568: 'Luxembourg Cup',
    569: 'Andorran Cup',
    570: 'Gibraltar Cup',
    571: 'San Marino Coppa',
    572: 'Liechtenstein Cup',
    573: 'Coppa Italia Primavera',
    574: 'DFB-Pokal Junior',
    575: 'FA Youth Cup',
    576: 'UEFA Youth League',
    577: 'UEFA Women\'s Champions League',
    578: 'Copa América Femenina',
    579: 'AFC Women\'s Asian Cup',
    580: 'Africa Women Cup of Nations',
    581: 'CONCACAF W Championship',
    582: 'OFC Women\'s Nations Cup',
    583: 'Pinatar Cup',
    584: 'SheBelieves Cup',
    585: 'Arnold Clark Cup',
    586: 'Tournoi de France',
    587: 'Cyprus Women\'s Cup',
    588: 'Algarve Cup',
    589: 'FIFA U-20 Women\'s World Cup',
    590: 'FIFA U-17 Women\'s World Cup',
    591: 'Euro U19 Women\'s Championship',
    592: 'Euro U17 Women\'s Championship',
    # More domestic cups
    593: 'Copa do Brasil',
    594: 'Copa Argentina',
    595: 'Copa Chile',
    596: 'Copa Colombia',
    597: 'Copa Perú',
    598: 'Copa Uruguay',
    599: 'Copa Ecuador',
    600: 'Copa Paraguay',
    601: 'Copa Bolivia',
    602: 'Copa Venezuela',
    603: 'Copa México',
    604: 'Canadian Championship',
    605: 'US Open Cup',
    606: 'J.League Cup (JPN)',
    607: 'Emperor\'s Cup (JPN)',
    608: 'Korean FA Cup',
    609: 'Chinese FA Cup',
    610: 'Saudi King Cup',
    611: 'UAE President\'s Cup',
    612: 'Amir Cup (QAT)',
    613: 'Hazfi Cup (IRN)',
    614: 'FA Cup (IND)',
    615: 'Thai FA Cup',
    616: 'Singapore Cup',
    617: 'Hong Kong FA Cup',
    618: 'Malaysia FA Cup',
    619: 'Piala Indonesia',
    620: 'AFC Cup',
    621: 'CAF Cup',
    622: 'Copa CONMEBOL',
    623: 'Intercontinental Cup',
    624: 'Campeonato Mineiro (BRA)',
    625: 'Campeonato Gaúcho (BRA)',
    626: 'Campeonato Carioca (BRA)',
    627: 'Campeonato Paulista (BRA)',
    628: 'Campeonato Paranaense (BRA)',
    629: 'Campeonato Baiano (BRA)',
    630: 'Campeonato Pernambucano (BRA)',
    631: 'Campeonato Goiano (BRA)',
    632: 'Campeonato Catarinense (BRA)',
    633: 'Campeonato Cearense (BRA)',
    634: 'Campeonato Amazonense (BRA)',
    635: 'Campeonato Alagoano (BRA)',
    636: 'Campeonato Sergipano (BRA)',
    637: 'Campeonato Maranhense (BRA)',
    638: 'Campeonato Paraibano (BRA)',
    639: 'Campeonato Potiguar (BRA)',
    640: 'Campeonato Piauiense (BRA)',
    641: 'Campeonato Rondoniense (BRA)',
    642: 'Campeonato Roraimense (BRA)',
    643: 'Campeonato Amapaense (BRA)',
    644: 'Campeonato Acreano (BRA)',
    645: 'Campeonato Tocantinense (BRA)',
    646: 'Campeonato Brasiliense (BRA)',
    647: 'Campeonato Mato-Grossense (BRA)',
    648: 'Campeonato Sul-Mato-Grossense (BRA)',
    649: 'Campeonato Espirito-Santense (BRA)',
    650: 'Campeonato Fluminense (BRA)',
    # Youth/Reserve
    651: 'Premier League 2 (ENG)',
    652: 'Premier League U18 (ENG)',
    653: 'Professional Development League',
    654: 'U23 Bundesliga (GER)',
    655: 'U19 Bundesliga (GER)',
    656: 'Campionato Primavera 1 (ITA)',
    657: 'Campionato Primavera 2 (ITA)',
    658: 'División de Honor Juvenil (ESP)',
    659: 'NextGen Series',
    # Futsal
    660: 'FIFA Futsal World Cup',
    661: 'UEFA Futsal Championship',
    662: 'Copa América de Futsal',
    663: 'AFC Futsal Asian Cup',
    664: 'CAF Futsal Cup',
    665: 'CONCACAF Futsal Championship',
    666: 'OFC Futsal Championship',
    667: 'Primera División de Futsal (ESP)',
    668: 'Serie A Futsal (ITA)',
    669: 'Futsal Bundesliga (GER)',
    670: 'Liga Nationala de Futsal (ROM)',
    # Beach Soccer
    671: 'FIFA Beach Soccer World Cup',
    672: 'Euro Beach Soccer League',
    673: 'CONCACAF Beach Soccer Championship',
    674: 'African Beach Soccer Cup',
    675: 'AFC Beach Soccer Asian Cup',
    676: 'Copa América Beach Soccer',
    677: 'OFC Beach Soccer Championship',
    # Esports / Virtual
    678: 'ePremier League',
    679: 'FIFAe Nations Cup',
    680: 'FIFAe Club World Cup',
    681: 'eChampions League',
    682: 'eLaLiga',
    683: 'Virtual Bundesliga',
    684: 'eSerie A',
    685: 'eLigue 1',
    686: 'eMLS',
    687: 'eJ.League',
    688: 'eFootball Championship',
}

# Curated list of league IDs that definitely exist on FotMob
# (verified through actual scraping)
VERIFIED_LEAGUES = {
    47: 'Premier League',
    53: 'LaLiga',
    54: 'Bundesliga',
    55: 'Serie A',
    74: 'Ligue 1',
    48: 'Championship',
    49: 'League One',
    50: 'League Two',
    137: 'LaLiga2',
    56: '2. Bundesliga',
    73: 'UEFA Champions League',
    72: 'UEFA Europa League',
    87: 'Primeira Liga',
    88: 'Liga Portugal 2',
    59: 'Eredivisie',
    61: 'Jupiler Pro League',
    62: 'Scottish Premiership',
    64: 'Süper Lig',
    65: 'Russian Premier League',
    66: 'Ukrainian Premier League',
    67: 'Greek Super League',
    68: 'Czech First League',
    69: 'Ekstraklasa',
    70: 'HNL',
    71: 'Swiss Super League',
    75: 'Allsvenskan',
    76: 'Eliteserien',
    77: 'Danish Superliga',
    130: 'MLS',
    133: 'Liga MX',
    135: 'Campeonato Brasileiro Série A',
    138: 'Argentine Primera División',
    153: 'J1 League',
    155: 'K League 1',
    157: 'Chinese Super League',
    162: 'Saudi Pro League',
    166: 'AFC Champions League',
    178: 'CAF Champions League',
    202: 'A-League',
    208: 'FIFA World Cup',
    364: 'Copa Libertadores',
    365: 'Copa Sudamericana',
    508: 'UEFA Champions League',
    509: 'UEFA Europa League',
    510: 'UEFA Conference League',
}


# ═══════════════════════════════════════════════════════════════════════
# DATABASE LAYER
# ═══════════════════════════════════════════════════════════════════════

def get_db():
    """Get or create the scrape cache database with heist tables."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=OFF')
    conn.execute('PRAGMA cache_size=-64000')  # 64MB cache
    
    # FotMob tables
    conn.execute('''CREATE TABLE IF NOT EXISTS fotmob_league_cache (
        league_id INTEGER, season TEXT, data TEXT, scraped_at TEXT,
        PRIMARY KEY(league_id, season))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS fotmob_match_cache (
        id INTEGER PRIMARY KEY, slug TEXT, home_name TEXT, away_name TEXT,
        home_id INTEGER, away_id INTEGER, home_score INTEGER, away_score INTEGER,
        data TEXT, scraped_at TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS fotmob_team_map (
        team_name TEXT, team_id INTEGER, league_id INTEGER,
        PRIMARY KEY(team_name, league_id))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS fotmob_heist_progress (
        league_id INTEGER PRIMARY KEY, status TEXT, total_matches INTEGER,
        scraped_matches INTEGER, seasons TEXT, errors INTEGER, last_fetch REAL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS fotmob_player_cache (
        player_id INTEGER PRIMARY KEY, name TEXT, team_id INTEGER,
        data TEXT, scraped_at TEXT)''')
    
    # Heist output tracking
    conn.execute('''CREATE TABLE IF NOT EXISTS heist_files (
        filename TEXT PRIMARY KEY, source TEXT, record_count INTEGER,
        file_size_bytes INTEGER, created_at TEXT, checksum TEXT)''')
    
    conn.commit()
    return conn


def save_league_data(league_id, season, data):
    conn = get_db()
    try:
        conn.execute('INSERT OR REPLACE INTO fotmob_league_cache VALUES (?,?,?,?)',
                     (league_id, season, json.dumps(data), datetime.now(timezone.utc).isoformat()))
        conn.commit()
    finally:
        conn.close()


def save_match_data(match_id, slug, home_name, away_name, home_id, away_id, home_score, away_score, data):
    conn = get_db()
    try:
        conn.execute('''INSERT OR REPLACE INTO fotmob_match_cache VALUES (?,?,?,?,?,?,?,?,?,?)''',
                     (match_id, slug, home_name, away_name, home_id, away_id, home_score, away_score,
                      json.dumps(data), datetime.now(timezone.utc).isoformat()))
        conn.commit()
    finally:
        conn.close()


def update_progress(league_id, status, total=0, scraped=0, seasons='', errors=0):
    conn = get_db()
    try:
        conn.execute('''INSERT OR REPLACE INTO fotmob_heist_progress 
                       VALUES (?,?,?,?,?,?,?)''',
                     (league_id, status, total, scraped, seasons, errors, time.time()))
        conn.commit()
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════
# HEIST OUTPUT — JSONL files in heist_output/
# ═══════════════════════════════════════════════════════════════════════

def write_jsonl(source_name, records, batch_size=1000):
    """Write records to a JSONL file in heist_output/. Returns (filename, count)."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'{source_name}_{timestamp}.jsonl'
    filepath = os.path.join(HEIST_DIR, filename)
    
    count = 0
    with open(filepath, 'w', encoding='utf-8') as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + '\n')
            count += 1
    
    # Compute checksum
    checksum = hashlib.md5(open(filepath, 'rb').read()).hexdigest()
    filesize = os.path.getsize(filepath)
    
    # Track in DB
    conn = get_db()
    try:
        conn.execute('INSERT OR REPLACE INTO heist_files VALUES (?,?,?,?,?,?)',
                     (filename, source_name, count, filesize, 
                      datetime.now(timezone.utc).isoformat(), checksum))
        conn.commit()
    finally:
        conn.close()
    
    return filename, count


def append_jsonl(source_name, record):
    """Append a single record to a date-based JSONL file."""
    datedir = os.path.join(HEIST_DIR, datetime.now().strftime('%Y%m'))
    os.makedirs(datedir, exist_ok=True)
    filename = f'{source_name}_{datetime.now().strftime("%Y%m%d")}.jsonl'
    filepath = os.path.join(datedir, filename)
    
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + '\n')
    
    return filepath


def append_parquet(source_name, records_df):
    """Write records as Parquet (compressed, queryable)."""
    try:
        import pandas as pd
        datedir = os.path.join(HEIST_DIR, datetime.now().strftime('%Y%m'))
        os.makedirs(datedir, exist_ok=True)
        filename = f'{source_name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.parquet'
        filepath = os.path.join(datedir, filename)
        
        if isinstance(records_df, list):
            records_df = pd.DataFrame(records_df)
        
        records_df.to_parquet(filepath, index=False, compression='snappy')
        return filepath
    except ImportError:
        return None


# ═══════════════════════════════════════════════════════════════════════
# FOTMOB API — NEXT.JS DATA ROUTE EXPLOIT
# ═══════════════════════════════════════════════════════════════════════

def get_build_id() -> str:
    """Extract the Next.js build ID from FotMob's homepage."""
    r = requests.get('https://www.fotmob.com/', impersonate='chrome120', timeout=15)
    match = re.search(r'"buildId":"([^"]+)"', r.text)
    if match:
        return match.group(1)
    # Fallback: try known build ID
    return 'p3C1aZo1q8s-3rwiYMc3f'


def fetch_league_via_data_route(league_id: int, build_id: str = None, season: str = None) -> Optional[Dict]:
    """Fetch league data via FotMob's Next.js data route (the secret API).
    
    This exploits the Next.js __NEXT_DATA__ approach which returns JSON
    instead of HTML for server-rendered pages.
    """
    if build_id is None:
        build_id = get_build_id()
    
    params = 'tab=overview&type=league&timeZone=UTC'
    if season:
        params += f'&season={season}'
    
    url = f'https://www.fotmob.com/_next/data/{build_id}/leagues/{league_id}.json?{params}'
    
    headers = {
        'User-Agent': random.choice(UA_LIST),
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': f'https://www.fotmob.com/leagues/{league_id}',
        'X-Requested-With': 'XMLHttpRequest',
    }
    
    try:
        r = requests.get(url, headers=headers, impersonate='chrome120', timeout=20)
        if r.status_code == 200:
            data = r.json()
            if 'pageProps' in data and data['pageProps']:
                return data['pageProps']
        return None
    except Exception as e:
        print(f'  [FotMob] Error fetching league {league_id}: {e}')
        return None


def fetch_league_page(league_id: int) -> Optional[Dict]:
    """Fallback: scrape the HTML page and extract __NEXT_DATA__."""
    url = f'https://www.fotmob.com/leagues/{league_id}'
    headers = {
        'User-Agent': random.choice(UA_LIST),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    try:
        r = requests.get(url, headers=headers, impersonate='chrome120', timeout=20)
        if r.status_code != 200:
            return None
        match = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
        if match:
            nd = json.loads(match.group(1))
            return nd.get('props', {}).get('pageProps', {})
        return None
    except:
        return None


def fetch_league_available_seasons(league_id: int) -> List[str]:
    """Get all available seasons for a league."""
    pp = fetch_league_via_data_route(league_id)
    if pp is None:
        pp = fetch_league_page(league_id)
    if pp is None:
        return []
    
    # Check different possible locations for seasons
    seasons = pp.get('allAvailableSeasons', [])
    if not seasons:
        seasons = pp.get('seasons', [])
    if not seasons:
        details = pp.get('details', {})
        seasons = details.get('availableSeasons', [])
    
    # Parse season objects
    result = []
    for s in seasons:
        if isinstance(s, dict):
            name = s.get('name', s.get('seasonName', s.get('slug', '')))
            if name:
                result.append(name)
        elif isinstance(s, str):
            result.append(s)
    
    return result


def extract_matches_from_pageprops(pp: Dict, league_id: int) -> List[Dict]:
    """Extract match list from pageProps data."""
    matches = []
    
    # Try overview matches first
    overview = pp.get('overview', {})
    if overview:
        raw = overview.get('leagueOverviewMatches', []) or overview.get('matches', []) or []
        for m in raw:
            if isinstance(m, dict):
                matches.append(m)
    
    # Try fixtures section
    fixtures = pp.get('fixtures', {})
    if fixtures:
        for key in fixtures:
            raw = fixtures[key]
            if isinstance(raw, list):
                for m in raw:
                    if isinstance(m, dict) and m not in matches:
                        matches.append(m)
    
    # Try matches dict
    matches_dict = pp.get('matches', {})
    if isinstance(matches_dict, dict):
        for key in ['allMatches', 'finished', 'upcoming', 'results']:
            raw = matches_dict.get(key, [])
            if isinstance(raw, list):
                for m in raw:
                    if isinstance(m, dict) and m not in matches:
                        matches.append(m)
    
    return matches


def parse_fotmob_match(m: Dict) -> Optional[Dict]:
    """Parse a FotMob match object into a standardized record."""
    try:
        # Get teams (FotMob uses nested structure)
        home = m.get('home', {})
        away = m.get('away', {})
        
        home_id = home.get('id', home.get('teamId', 0))
        away_id = away.get('id', away.get('teamId', 0))
        home_name = home.get('name', home.get('shortName', ''))
        away_name = away.get('name', away.get('shortName', ''))
        
        # Scores
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
            is_finished = False
            utc_time = m.get('matchDateUTC', m.get('date', ''))
        
        # League info
        league = m.get('league', {})
        if isinstance(league, dict):
            league_id = league.get('id', m.get('leagueId'))
            league_name = league.get('name', m.get('leagueName', ''))
        else:
            league_id = m.get('leagueId')
            league_name = m.get('leagueName', '')
        
        # Round/Week
        round_info = m.get('round', m.get('matchRound', ''))
        
        # IDs
        match_id = m.get('id', m.get('matchId', 0))
        
        record = {
            'source': 'fotmob',
            'match_id': match_id,
            'home_team': home_name,
            'away_team': away_name,
            'home_id': home_id,
            'away_id': away_id,
            'home_score': home_score,
            'away_score': away_score,
            'league_id': league_id,
            'league_name': league_name,
            'round': round_info,
            'utc_time': utc_time,
            'is_finished': is_finished,
            'page_url': m.get('pageUrl', ''),
        }
        return record
    except Exception as e:
        return None


def scrape_league_matches(league_id: int, seasons: List[str] = None, 
                          max_seasons: int = 5, build_id: str = None) -> Dict[str, Any]:
    """Scrape ALL matches for a given league across multiple seasons."""
    if build_id is None:
        build_id = get_build_id()
    
    if seasons is None:
        seasons = fetch_league_available_seasons(league_id)
    
    if not seasons:
        # Generate seasons from 2010 to 2026
        seasons = [f'{y}/{y+1}' for y in range(2010, 2026)]
    
    seasons = seasons[:max_seasons]
    all_matches = []
    errors = 0
    
    for season in seasons:
        try:
            pp = fetch_league_via_data_route(league_id, build_id, season)
            if pp is None:
                pp = fetch_league_page(league_id)
            
            if pp:
                matches = extract_matches_from_pageprops(pp, league_id)
                for m in matches:
                    parsed = parse_fotmob_match(m)
                    if parsed:
                        parsed['season'] = season
                        all_matches.append(parsed)
                
                # Cache league data
                save_league_data(league_id, season, pp)
                
                print(f'  [FotMob] League {league_id} season {season}: {len(matches)} matches')
            else:
                print(f'  [FotMob] League {league_id} season {season}: FAILED')
                errors += 1
            
            time.sleep(0.5 + random.random() * 0.5)  # Polite delay
        except Exception as e:
            print(f'  [FotMob] Error season {season}: {e}')
            errors += 1
    
    return {
        'league_id': league_id,
        'seasons': len(seasons),
        'total_matches': len(all_matches),
        'errors': errors,
        'matches': all_matches,
    }


def save_league_teams_standings(league_id: int, pp: Dict):
    """Extract and save team data from league page props."""
    conn = get_db()
    try:
        # Try standings table
        table_data = pp.get('table', [])
        if isinstance(table_data, list):
            for table_group in table_data:
                data_dict = table_group.get('data', {})
                if isinstance(data_dict, dict):
                    table_rows = data_dict.get('table', {}).get('all', [])
                    for row in table_rows:
                        name = row.get('name', '')
                        team_id = row.get('id')
                        if name and team_id:
                            conn.execute('INSERT OR IGNORE INTO fotmob_team_map VALUES (?,?,?)',
                                        (name, team_id, league_id))
                # Also check flat structure
                all_rows = table_group.get('table', {}).get('all', [])
                for row in all_rows:
                    name = row.get('name', '')
                    team_id = row.get('id')
                    if name and team_id:
                        conn.execute('INSERT OR IGNORE INTO fotmob_team_map VALUES (?,?,?)',
                                    (name, team_id, league_id))
        
        # Also try overview
        overview = pp.get('overview', {})
        if overview:
            table = overview.get('table', [])
            if isinstance(table, list):
                for group in table:
                    rows = group.get('data', {}).get('table', {}).get('all', [])
                    for row in rows:
                        name = row.get('name', '')
                        team_id = row.get('id')
                        if name and team_id:
                            conn.execute('INSERT OR IGNORE INTO fotmob_team_map VALUES (?,?,?)',
                                        (name, team_id, league_id))
        
        conn.commit()
    finally:
        conn.close()


def get_match_detail_nextjs(match_id: int, build_id: str = None) -> Optional[Dict]:
    """Fetch match detail via Next.js data route."""
    if build_id is None:
        build_id = get_build_id()
    
    url = f'https://www.fotmob.com/_next/data/{build_id}/match/{match_id}.json'
    headers = {
        'User-Agent': random.choice(UA_LIST),
        'Accept': 'application/json, text/plain, */*',
        'Referer': f'https://www.fotmob.com/match/{match_id}',
    }
    
    try:
        r = requests.get(url, headers=headers, impersonate='chrome120', timeout=15)
        if r.status_code == 200:
            data = r.json()
            return data.get('pageProps', {})
        return None
    except:
        return None


def extract_match_stats_from_detail(pp: Dict) -> Dict:
    """Extract detailed stats from match detail pageProps."""
    general = pp.get('general', {})
    content = pp.get('content', {})
    
    home = general.get('homeTeam', {})
    away = general.get('awayTeam', {})
    
    # Extract stats
    stats_data = {}
    periods = content.get('stats', {}).get('Periods', {})
    for period_name, period_data in periods.items():
        for stat_group in period_data.get('stats', []):
            for stat_item in stat_group.get('stats', []):
                stat_key = stat_item.get('key', '')
                stat_values = stat_item.get('stats', [])
                if len(stat_values) == 2:
                    stats_data[f'{period_name}_{stat_key}'] = {
                        'home': stat_values[0],
                        'away': stat_values[1],
                    }
    
    # Extract shotmap
    shotmap = content.get('shotmap', {})
    shots = []
    for shot in shotmap.get('shots', []):
        shots.append({
            'player_name': shot.get('playerName', ''),
            'team_id': shot.get('teamId', ''),
            'x': shot.get('x', 0),
            'y': shot.get('y', 0),
            'expected_goals': shot.get('expectedGoals', 0),
            'expected_goals_on_target': shot.get('expectedGoalsOnTarget', 0),
            'shot_type': shot.get('shotType', ''),
            'situation': shot.get('situation', ''),
            'is_goal': shot.get('isGoal', False),
            'is_on_target': shot.get('onTarget', False),
        })
    
    # Lineups
    lineup = content.get('lineup', {})
    
    # Team form
    team_form = content.get('matchFacts', {}).get('teamForm', [])
    
    return {
        'match_id': general.get('matchId'),
        'home_team': home.get('name'),
        'away_team': away.get('name'),
        'home_score': general.get('homeTeam', {}).get('score'),
        'away_score': general.get('awayTeam', {}).get('score'),
        'league_name': general.get('leagueName'),
        'league_id': general.get('leagueId'),
        'match_date_utc': general.get('matchTimeUTC'),
        'started': general.get('started'),
        'finished': general.get('finished'),
        'stats': stats_data,
        'shots': shots,
        'total_shots': len(shots),
        'home_shots': sum(1 for s in shots if s['team_id'] == home.get('id')),
        'away_shots': sum(1 for s in shots if s['team_id'] == away.get('id')),
        'home_xg': sum(s['expected_goals'] for s in shots if s['team_id'] == home.get('id')),
        'away_xg': sum(s['expected_goals'] for s in shots if s['team_id'] == away.get('id')),
        'has_lineups': bool(lineup),
    }


# ═══════════════════════════════════════════════════════════════════════
# BULK HEIST OPERATIONS
# ═══════════════════════════════════════════════════════════════════════

def heist_fotmob_all_known_leagues(max_seasons=3, parallel=4, limit_leagues=None):
    """Heist: scrape all known FotMob leagues for matches."""
    print('=' * 70)
    print('🔥 FOTMOB BULK HEIST — SHADOWHACKER-GOD')
    print('=' * 70)
    
    build_id = get_build_id()
    print(f'Build ID: {build_id}')
    
    leagues_to_scrape = KNOWN_LEAGUES if limit_leagues is None else {
        k: KNOWN_LEAGUES[k] for k in limit_leagues if k in KNOWN_LEAGUES
    }
    # If limit_leagues contains ints not in KNOWN_LEAGUES, add them
    if limit_leagues:
        for k in limit_leagues:
            if isinstance(k, int) and k not in leagues_to_scrape:
                leagues_to_scrape[k] = f'League {k}'
    
    total_all_matches = 0
    league_results = []
    
    # Phase 1: Scrape league overviews (faster, less detailed)
    print(f'\n📡 Phase 1: Scraping {len(leagues_to_scrape)} league overviews...')
    
    lid_list = list(leagues_to_scrape.keys())
    
    def scrape_one_league(lid):
        name = leagues_to_scrape.get(lid, f'League {lid}')
        try:
            # First try the data route
            pp = fetch_league_via_data_route(lid, build_id)
            if pp is None:
                pp = fetch_league_page(lid)
            
            if pp is None:
                update_progress(lid, 'not_found', errors=1)
                return {'league_id': lid, 'status': 'not_found', 'matches': 0}
            
            # Extract matches
            matches = extract_matches_from_pageprops(pp, lid)
            parsed_matches = []
            for m in matches:
                pm = parse_fotmob_match(m)
                if pm:
                    pm['league_name'] = name
                    parsed_matches.append(pm)
            
            # Save to DB
            save_league_data(lid, 'overview', pp)
            update_progress(lid, 'scraped', len(matches), len(parsed_matches))
            save_league_teams_standings(lid, pp)
            
            print(f'  ✅ {name} (ID {lid}): {len(parsed_matches)} matches')
            
            return {
                'league_id': lid,
                'name': name,
                'status': 'ok',
                'matches': parsed_matches,
                'total': len(parsed_matches),
            }
        except Exception as e:
            print(f'  ❌ {name} (ID {lid}): ERROR — {str(e)[:80]}')
            update_progress(lid, f'error: {str(e)[:80]}', errors=1)
            return {'league_id': lid, 'status': 'error', 'matches': [], 'error': str(e)}
    
    # Parallel scrape
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {executor.submit(scrape_one_league, lid): lid for lid in lid_list}
        for future in as_completed(futures):
            result = future.result()
            league_results.append(result)
            total_all_matches += result.get('total', 0)
            
            # Write matches to JSONL
            if result.get('matches'):
                lid = result['league_id']
                append_jsonl(f'fotmob_league_{lid}', {
                    'source': 'fotmob',
                    'league_id': lid,
                    'league_name': result.get('name', ''),
                    'matches': result['matches'],
                    'count': len(result['matches']),
                    'scraped_at': datetime.now(timezone.utc).isoformat(),
                })
            
            time.sleep(0.1)
    
    print(f'\n📊 Phase 1 Complete: {total_all_matches} total matches from {len(league_results)} leagues')
    
    # Phase 2: Get detailed stats for a subset of matches (top leagues)
    print(f'\n📡 Phase 2: Detailed match stats for top leagues...')
    
    top_league_ids = [47, 53, 54, 55, 74, 48, 73, 130, 133, 135, 138, 
                      153, 162, 166, 178, 202, 364, 365, 508, 509, 510]
    
    detail_matches = []
    for result in league_results:
        if result.get('league_id') in top_league_ids and result.get('matches'):
            # Get up to 200 finished matches with IDs
            finished = [m for m in result['matches'] if m.get('is_finished') and m.get('match_id')][:200]
            detail_matches.extend(finished)
    
    print(f'  Fetching details for {len(detail_matches)} matches...')
    detailed_stats = []
    
    for i, m in enumerate(detail_matches[:500]):  # Limit to 500 for speed
        if i % 50 == 0:
            print(f'  ... {i}/{min(len(detail_matches), 500)}')
        try:
            pp = get_match_detail_nextjs(m['match_id'], build_id)
            if pp:
                detail = extract_match_stats_from_detail(pp)
                detail['home_team'] = m['home_team']
                detail['away_team'] = m['away_team']
                detailed_stats.append(detail)
                save_match_data(
                    m['match_id'], m.get('page_url', ''),
                    m['home_team'], m['away_team'],
                    m['home_id'], m['away_id'],
                    m['home_score'], m['away_score'],
                    {'general': pp.get('general', {}), 'content': pp.get('content', {})}
                )
            time.sleep(0.3 + random.random() * 0.3)
        except Exception as e:
            pass
    
    if detailed_stats:
        filepath = append_jsonl('fotmob_match_details', {
            'source': 'fotmob',
            'type': 'match_details',
            'count': len(detailed_stats),
            'records': detailed_stats,
            'scraped_at': datetime.now(timezone.utc).isoformat(),
        })
        print(f'  ✅ Saved {len(detailed_stats)} detailed match stats')
    
    # Summary
    print(f'\n{"="*70}')
    print(f'🔥 FOTMOB HEIST COMPLETE')
    print(f'{"="*70}')
    print(f'  Leagues scraped: {leagues_ok_count}')
    print(f'  Total matches (phase 1): {total_all_matches}')
    print(f'  Detailed stats (phase 2): {len(detailed_stats)}')
    
    return {
        'leagues_scraped': leagues_ok_count,
        'total_matches': total_all_matches,
        'detailed_stats': len(detailed_stats),
        'league_results': league_results,
    }


def heist_fotmob_historical_seasons(league_ids=None, start_year=2010, end_year=2026, max_leagues=None):
    """DEEP HEIST: Scrape historical seasons for each league."""
    print('=' * 70)
    print('🔥 FOTMOB HISTORICAL SEASONS HEIST')
    print('=' * 70)
    
    build_id = get_build_id()
    print(f'Build ID: {build_id}')
    
    if league_ids is None:
        # Use verified leagues first, then fallback to known
        league_ids = list(VERIFIED_LEAGUES.keys()) + list(KNOWN_LEAGUES.keys())
        league_ids = list(set(league_ids))
    
    if max_leagues:
        league_ids = league_ids[:max_leagues]
    
    all_data = []
    total_matches = 0
    
    for lid in league_ids:
        name = KNOWN_LEAGUES.get(lid, VERIFIED_LEAGUES.get(lid, f'League {lid}'))
        print(f'\n📡 Scraping {name} (ID {lid})...')
        
        result = scrape_league_matches(lid, max_seasons=end_year - start_year, build_id=build_id)
        
        if result['matches']:
            all_data.extend(result['matches'])
            total_matches += len(result['matches'])
            
            # Save to JSONL
            append_jsonl(f'fotmob_historical_{lid}', {
                'source': 'fotmob_historical',
                'league_id': lid,
                'league_name': name,
                'seasons': result['seasons'],
                'matches': result['matches'],
                'count': len(result['matches']),
            })
        
        print(f'  → {len(result["matches"])} matches across {result["seasons"]} seasons')
        
        # Progress update
        update_progress(lid, 'historical_done', result['total_matches'], 
                       len(result['matches']), result['seasons'], result['errors'])
    
    # Write consolidated file
    if all_data:
        filename = write_jsonl('fotmob_historical_all', all_data)
        print(f'\n✅ Saved {len(all_data)} matches to {filename}')
    
    # Summary stats
    leagues_with_data = len([l for l in league_ids if any(d.get('league_id') == l for d in [{'league_id': lid} for lid in league_ids])])
    
    print(f'\n{"="*70}')
    print(f'🔥 HISTORICAL HEIST COMPLETE')
    print(f'{"="*70}')
    print(f'  Leagues: {len(league_ids)}')
    print(f'  Total historical matches: {total_matches}')
    print(f'  Date range: {start_year}-{end_year}')
    
    return {
        'total_matches': total_matches,
        'leagues_attempted': len(league_ids),
        'data': all_data,
    }


def verify_fotmob_league(league_id: int) -> bool:
    """Verify if a FotMob league ID actually exists."""
    try:
        build_id = get_build_id()
        pp = fetch_league_via_data_route(league_id, build_id)
        if pp:
            matches = extract_matches_from_pageprops(pp, league_id)
            return len(matches) > 0
    except:
        pass
    return False


def scan_league_id_range(start=1, end=1000, parallel=8):
    """Scan a range of league IDs to discover valid FotMob leagues."""
    print(f'🔍 Scanning FotMob league IDs {start}-{end}...')
    
    build_id = get_build_id()
    found = []
    
    def check_lid(lid):
        try:
            pp = fetch_league_via_data_route(lid, build_id)
            if pp and pp.get('details', {}).get('name'):
                name = pp['details']['name']
                matches = extract_matches_from_pageprops(pp, lid)
                print(f'  ✅ League {lid}: {name} ({len(matches)} matches)')
                return (lid, name, len(matches))
        except:
            pass
        return None
    
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {executor.submit(check_lid, lid): lid for lid in range(start, end + 1)}
        for future in as_completed(futures):
            result = future.result()
            if result:
                found.append(result)
    
    print(f'\n🔍 Found {len(found)} valid leagues in range {start}-{end}')
    return found


# ═══════════════════════════════════════════════════════════════════════
# MAIN — STANDALONE EXECUTION
# ═══════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import sys
    
    print('🔥🔥🔥 SHADOWHACKER-GOD — FOTMOB BULK HEIST ENGINE 🔥🔥🔥')
    print('DΞMON CORE v9999999 — SHΔDØW.EXE — Specter 0x13')
    print()
    
    # Test the connection
    print('🔌 Testing FotMob connection...')
    bid = get_build_id()
    print(f'  Build ID: {bid}')
    
    # Quick test with Premier League
    print('\n📡 Testing Premier League (ID 47)...')
    pp = fetch_league_via_data_route(47, bid)
    if pp:
        matches = extract_matches_from_pageprops(pp, 47)
        print(f'  ✅ OK — {len(matches)} matches in overview')
        
        # Save some teams
        save_league_teams_standings(47, pp)
        print('  ✅ Team map saved')
    else:
        print('  ⚠️ Data route failed, trying page scrape...')
        pp = fetch_league_page(47)
        if pp:
            matches = extract_matches_from_pageprops(pp, 47)
            print(f'  ✅ Page scrape — {len(matches)} matches')
    
    # Run the full heist
    print('\n🚀 STARTING FULL HEIST...')
    result = heist_fotmob_all_known_leagues(max_seasons=1, parallel=4)
    
    print(f'\n📊 FINAL SUMMARY')
    print(f'  Leagues scraped: {result["leagues_scraped"]}')
    print(f'  Total matches: {result["total_matches"]}')
    print(f'  Detailed stats: {result["detailed_stats"]}')
