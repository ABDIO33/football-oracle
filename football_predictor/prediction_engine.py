import numpy as np
from math import exp, factorial, log, sqrt
from datetime import datetime, timedelta
import requests
import os
import json
import time
import difflib
import sqlite3
from collections import defaultdict
from scipy.optimize import minimize_scalar
from scipy.stats import poisson as sp_poisson
from sklearn.isotonic import IsotonicRegression
try:
    import edge_scraper
except ImportError:
    edge_scraper = None
import evaluation
import venues as venue_module
try:
    import forebet_scraper as forebets
except ImportError:
    forebets = None
try:
    import calibration
except ImportError:
    calibration = None
try:
    import lineups
except ImportError:
    lineups = None
try:
    import fotmob_scraper as fs
except ImportError:
    fs = None
try:
    import statsbomb_scraper as sbs
except ImportError:
    sbs = None
try:
    import clubelo_scraper as ces
except ImportError:
    ces = None
try:
    import understat_scraper as uss
except ImportError:
    uss = None
try:
    import model_trainer as mt
except ImportError:
    mt = None
try:
    import whoscored_scraper as ws
except ImportError:
    ws = None
try:
    import fbref_scraper as fbs
except ImportError:
    fbs = None
try:
    import football_predictor.odds_api_scraper as oas
except ImportError:
    try:
        import odds_api_scraper as oas
    except ImportError:
        oas = None

# ═══════════════════════════════════════════════════════════════
# DIXON-COLES CONFIG (integrated)
# ═══════════════════════════════════════════════════════════════
XI_DECAY       = 0.002    # time-decay rate (half-life ~346 days)
W_XG           = 0.65     # weight on recent xG-form signal vs raw goals
MAX_GOALS_DC   = 9
RHO_BOUNDS     = (-0.20, 0.05)
RHO_DEFAULT    = mt.get_rho() if (mt and mt.get_rho() is not None) else -0.07
HOME_ADV_BASE  = 1.12
_FITTED_RHO    = RHO_DEFAULT
_CALIBRATORS   = {}
_LEAGUE_RHO_CACHE = {}

# ═══════════════════════════════════════════════════════════════
# TEAM DATABASE — ~260 teams (clubs + World Cup 2026 nations)
# (elo, goals_for_per_game, goals_against_per_game, form_0_to_1)
# ═══════════════════════════════════════════════════════════════
TEAM_DB = {
    # ── Premier League (20) ──
    'Manchester City':        (1900, 2.5, 0.8, 0.85),
    'Arsenal':                (1880, 2.3, 0.9, 0.82),
    'Liverpool':              (1870, 2.4, 1.0, 0.80),
    'Chelsea':                (1820, 2.0, 1.1, 0.72),
    'Manchester United':      (1810, 1.8, 1.2, 0.68),
    'Tottenham Hotspur':      (1800, 2.0, 1.3, 0.70),
    'Newcastle United':       (1830, 2.1, 1.0, 0.75),
    'Aston Villa':            (1800, 1.9, 1.2, 0.72),
    'Brighton & Hove Albion': (1780, 1.8, 1.3, 0.68),
    'West Ham United':        (1760, 1.6, 1.4, 0.60),
    'Brentford':              (1740, 1.7, 1.5, 0.58),
    'Crystal Palace':         (1740, 1.5, 1.4, 0.55),
    'Fulham':                 (1730, 1.5, 1.5, 0.55),
    'Wolverhampton':          (1720, 1.4, 1.5, 0.52),
    'Everton':                (1700, 1.2, 1.4, 0.50),
    'Nottingham Forest':      (1710, 1.3, 1.5, 0.48),
    'Bournemouth':            (1730, 1.5, 1.6, 0.52),
    'Leicester City':         (1720, 1.4, 1.5, 0.50),
    'Southampton':            (1680, 1.2, 1.6, 0.45),
    'Ipswich Town':           (1660, 1.1, 1.7, 0.42),
    # ── La Liga (20) ──
    'Barcelona':              (1880, 2.3, 0.9, 0.82),
    'Real Madrid':            (1900, 2.4, 0.8, 0.85),
    'Atletico Madrid':        (1850, 2.0, 0.9, 0.78),
    'Athletic Bilbao':        (1780, 1.7, 1.2, 0.68),
    'Real Sociedad':          (1770, 1.6, 1.2, 0.65),
    'Real Betis':             (1740, 1.5, 1.4, 0.58),
    'Valencia':               (1730, 1.4, 1.4, 0.55),
    'Villarreal':             (1760, 1.7, 1.3, 0.62),
    'Sevilla':                (1750, 1.5, 1.3, 0.58),
    'Osasuna':                (1700, 1.3, 1.5, 0.50),
    'Girona':                 (1750, 1.6, 1.3, 0.60),
    'Celta Vigo':             (1710, 1.3, 1.5, 0.50),
    'Rayo Vallecano':         (1690, 1.2, 1.5, 0.48),
    'Getafe':                 (1680, 1.1, 1.4, 0.48),
    'Mallorca':               (1680, 1.1, 1.5, 0.45),
    'Las Palmas':             (1660, 1.0, 1.6, 0.42),
    'Alaves':                 (1670, 1.1, 1.5, 0.45),
    'Espanyol':               (1660, 1.0, 1.6, 0.42),
    'Valladolid':             (1640, 0.9, 1.7, 0.38),
    'Leganes':                (1650, 1.0, 1.6, 0.40),
    # ── Bundesliga (18) ──
    'Bayern Munich':          (1890, 2.6, 0.8, 0.85),
    'Borussia Dortmund':      (1830, 2.1, 1.1, 0.75),
    'RB Leipzig':             (1820, 2.0, 1.1, 0.72),
    'Bayer Leverkusen':       (1870, 2.4, 0.9, 0.82),
    'Eintracht Frankfurt':    (1770, 1.8, 1.3, 0.65),
    'VfB Stuttgart':          (1760, 1.7, 1.3, 0.62),
    'Borussia Monchengladbach': (1720, 1.5, 1.5, 0.55),
    'VfL Wolfsburg':          (1730, 1.5, 1.4, 0.55),
    'Union Berlin':           (1740, 1.4, 1.3, 0.58),
    'SC Freiburg':            (1740, 1.5, 1.3, 0.58),
    'FC Augsburg':            (1690, 1.3, 1.6, 0.48),
    '1. FC Heidenheim':       (1670, 1.2, 1.7, 0.45),
    'Werder Bremen':          (1700, 1.4, 1.5, 0.50),
    'TSG Hoffenheim':         (1700, 1.3, 1.6, 0.48),
    'Mainz 05':               (1700, 1.3, 1.5, 0.50),
    'VfL Bochum':             (1650, 1.1, 1.8, 0.40),
    'Holstein Kiel':          (1640, 1.0, 1.8, 0.38),
    'FC St. Pauli':           (1660, 1.1, 1.7, 0.42),
    # ── Serie A (20) ──
    'Inter Milan':            (1880, 2.3, 0.8, 0.82),
    'AC Milan':               (1830, 2.0, 1.1, 0.72),
    'Juventus':               (1860, 2.1, 0.9, 0.78),
    'Napoli':                 (1850, 2.2, 1.0, 0.78),
    'Atalanta':               (1820, 2.1, 1.1, 0.72),
    'Roma':                   (1780, 1.8, 1.2, 0.68),
    'Lazio':                  (1780, 1.7, 1.2, 0.65),
    'Fiorentina':             (1760, 1.6, 1.3, 0.62),
    'Bologna':                (1750, 1.5, 1.2, 0.62),
    'Torino':                 (1720, 1.4, 1.4, 0.55),
    'Udinese':                (1700, 1.3, 1.5, 0.50),
    'Genoa':                  (1690, 1.2, 1.5, 0.48),
    'Monza':                  (1680, 1.2, 1.5, 0.48),
    'Lecce':                  (1670, 1.1, 1.6, 0.45),
    'Empoli':                 (1670, 1.1, 1.6, 0.45),
    'Cagliari':               (1680, 1.2, 1.6, 0.45),
    'Parma':                  (1670, 1.1, 1.7, 0.42),
    'Verona':                 (1660, 1.1, 1.7, 0.42),
    'Venezia':                (1640, 1.0, 1.8, 0.38),
    'Como':                   (1650, 1.0, 1.7, 0.40),
    # ── Ligue 1 (18) ──
    'Paris Saint Germain':    (1890, 2.5, 0.8, 0.85),
    'Marseille':              (1800, 1.9, 1.1, 0.72),
    'Lyon':                   (1780, 1.8, 1.3, 0.65),
    'Monaco':                 (1800, 2.0, 1.1, 0.72),
    'Lille':                  (1770, 1.7, 1.2, 0.65),
    'Nice':                   (1760, 1.6, 1.2, 0.62),
    'Rennes':                 (1750, 1.6, 1.3, 0.58),
    'Lens':                   (1740, 1.5, 1.3, 0.58),
    'Reims':                  (1710, 1.4, 1.5, 0.52),
    'Strasbourg':             (1700, 1.3, 1.5, 0.50),
    'Toulouse':               (1690, 1.3, 1.6, 0.48),
    'Brest':                  (1720, 1.5, 1.4, 0.55),
    'Montpellier':            (1680, 1.2, 1.6, 0.45),
    'Auxerre':                (1670, 1.1, 1.6, 0.45),
    'Nantes':                 (1680, 1.2, 1.6, 0.45),
    'Saint-Etienne':          (1660, 1.1, 1.7, 0.42),
    'Angers':                 (1650, 1.0, 1.7, 0.40),
    'Le Havre':               (1650, 1.0, 1.8, 0.38),
    # ── Eredivisie (18) ──
    'Ajax':                   (1820, 2.2, 1.0, 0.78),
    'Feyenoord':              (1810, 2.1, 1.0, 0.75),
    'PSV':                    (1830, 2.3, 0.9, 0.80),
    'AZ Alkmaar':             (1750, 1.8, 1.2, 0.68),
    'FC Twente':              (1730, 1.7, 1.3, 0.62),
    'FC Utrecht':             (1700, 1.5, 1.4, 0.58),
    'SC Heerenveen':          (1670, 1.3, 1.6, 0.48),
    'Go Ahead Eagles':        (1660, 1.2, 1.5, 0.48),
    'NEC Nijmegen':           (1660, 1.2, 1.6, 0.45),
    'Fortuna Sittard':        (1640, 1.1, 1.7, 0.42),
    'Heracles Almelo':        (1630, 1.0, 1.7, 0.40),
    'PEC Zwolle':             (1640, 1.1, 1.7, 0.42),
    'Willem II':              (1630, 1.0, 1.8, 0.38),
    'RKC Waalwijk':           (1620, 1.0, 1.8, 0.38),
    'Sparta Rotterdam':       (1650, 1.1, 1.6, 0.42),
    'Almere City':            (1610, 0.9, 1.9, 0.35),
    'NAC Breda':              (1620, 1.0, 1.8, 0.38),
    'Groningen':              (1630, 1.0, 1.7, 0.40),
    # ── Portuguese Liga (18) ──
    'Benfica':                (1840, 2.3, 0.9, 0.80),
    'Porto':                  (1830, 2.1, 1.0, 0.78),
    'Sporting CP':            (1840, 2.2, 0.9, 0.80),
    'Braga':                  (1740, 1.6, 1.2, 0.62),
    'Vitoria Guimaraes':      (1700, 1.4, 1.4, 0.55),
    'Rio Ave':                (1660, 1.2, 1.5, 0.48),
    'Gil Vicente':            (1640, 1.1, 1.6, 0.45),
    'Estoril Praia':          (1650, 1.1, 1.6, 0.45),
    'Famalicao':              (1650, 1.1, 1.6, 0.45),
    'Arouca':                 (1640, 1.1, 1.7, 0.42),
    'Boavista':               (1630, 1.0, 1.7, 0.40),
    'Moreirense':             (1640, 1.0, 1.6, 0.42),
    'Casa Pia':               (1630, 1.0, 1.7, 0.40),
    'Estrela Amadora':        (1620, 1.0, 1.8, 0.38),
    'Farense':                (1620, 0.9, 1.8, 0.38),
    'AVS':                    (1610, 0.9, 1.9, 0.35),
    'Santa Clara':            (1630, 1.0, 1.7, 0.40),
    'Nacional':               (1620, 1.0, 1.8, 0.38),
    # ── Scottish Premiership (10) ──
    'Celtic':                 (1800, 2.5, 0.8, 0.85),
    'Rangers':                (1780, 2.2, 0.9, 0.80),
    'Aberdeen':               (1650, 1.3, 1.5, 0.50),
    'Hearts':                 (1640, 1.3, 1.5, 0.48),
    'Hibernian':              (1630, 1.2, 1.6, 0.45),
    'Dundee United':          (1610, 1.1, 1.7, 0.42),
    'St Mirren':              (1600, 1.0, 1.7, 0.40),
    'Motherwell':             (1600, 1.0, 1.7, 0.40),
    'Kilmarnock':             (1610, 1.0, 1.6, 0.42),
    'Ross County':            (1580, 0.9, 1.8, 0.38),
    # ── Turkish Super Lig (18) ──
    'Galatasaray':            (1820, 2.4, 0.9, 0.82),
    'Fenerbahce':             (1800, 2.2, 1.0, 0.78),
    'Besiktas':               (1770, 1.9, 1.2, 0.70),
    'Trabzonspor':            (1720, 1.6, 1.3, 0.60),
    'Basaksehir':             (1700, 1.5, 1.4, 0.55),
    'Adana Demirspor':        (1690, 1.4, 1.5, 0.52),
    'Sivasspor':              (1670, 1.3, 1.6, 0.48),
    'Kayserispor':            (1660, 1.2, 1.6, 0.45),
    'Antalyaspor':            (1650, 1.2, 1.6, 0.45),
    'Kasimpasa':              (1650, 1.1, 1.7, 0.42),
    'Alanyaspor':             (1650, 1.2, 1.6, 0.45),
    'Rizespor':               (1640, 1.1, 1.7, 0.42),
    'Gaziantep FK':           (1640, 1.1, 1.7, 0.42),
    'Samsunspor':             (1630, 1.0, 1.7, 0.40),
    'Hatayspor':              (1630, 1.0, 1.7, 0.40),
    'Bodrum FK':              (1610, 0.9, 1.8, 0.38),
    'Eyupspor':               (1620, 1.0, 1.8, 0.38),
    'Konyaspor':              (1630, 1.0, 1.6, 0.40),
    # ── Saudi Pro League (18) ──
    'Al Hilal':               (1850, 2.6, 0.8, 0.88),
    'Al Nassr':               (1830, 2.4, 0.9, 0.82),
    'Al Ittihad':             (1810, 2.2, 1.0, 0.78),
    'Al Ahli':                (1780, 1.9, 1.2, 0.70),
    'Al Shabab':              (1720, 1.5, 1.4, 0.58),
    'Al Taawoun':             (1690, 1.4, 1.5, 0.52),
    'Al Fateh':               (1670, 1.3, 1.6, 0.48),
    'Al Wehda':               (1660, 1.2, 1.6, 0.45),
    'Al Khaleej':             (1650, 1.1, 1.7, 0.42),
    'Al Raed':                (1640, 1.1, 1.7, 0.42),
    'Al Riyadh':              (1630, 1.0, 1.7, 0.40),
    'Al Okhdood':             (1620, 1.0, 1.8, 0.38),
    'Damac':                  (1640, 1.1, 1.7, 0.42),
    'Abha':                   (1630, 1.0, 1.7, 0.40),
    'Al Hazem':               (1620, 0.9, 1.8, 0.38),
    'Al Tai':                 (1620, 1.0, 1.8, 0.38),
    'Al Feiha':               (1630, 1.0, 1.7, 0.40),
    'Al Orubah':              (1610, 0.9, 1.8, 0.38),
    # ── African Clubs (15) ──
    'Al Ahly':                (1780, 2.1, 0.8, 0.78),
    'Wydad Casablanca':       (1740, 1.7, 1.1, 0.68),
    'Esperance Sportive':     (1760, 1.8, 1.0, 0.70),
    'Zamalek':                (1720, 1.6, 1.2, 0.62),
    'Raja Casablanca':        (1720, 1.5, 1.2, 0.60),
    'Mamelodi Sundowns':      (1750, 2.0, 0.9, 0.75),
    'TP Mazembe':             (1700, 1.5, 1.2, 0.60),
    'JS Kabylie':             (1670, 1.3, 1.4, 0.55),
    'Enyimba':                (1660, 1.2, 1.4, 0.52),
    'Hearts of Oak':          (1640, 1.2, 1.5, 0.50),
    'Petro Atletico':         (1650, 1.2, 1.5, 0.50),
    'ASEC Mimosas':           (1660, 1.3, 1.4, 0.52),
    'CR Belouizdad':          (1670, 1.3, 1.4, 0.52),
    'Young Africans':         (1640, 1.2, 1.5, 0.50),
    'Orlando Pirates':        (1680, 1.4, 1.3, 0.55),
    # ── UEFA Nations (16) ──
    'France':                 (1900, 2.4, 0.8, 0.82),
    'Spain':                  (1880, 2.2, 0.8, 0.80),
    'England':                (1890, 2.3, 0.8, 0.82),
    'Germany':                (1850, 2.1, 0.9, 0.78),
    'Netherlands':            (1840, 2.0, 0.9, 0.78),
    'Portugal':               (1850, 2.1, 0.9, 0.78),
    'Belgium':                (1830, 2.0, 1.0, 0.75),
    'Italy':                  (1840, 2.0, 0.9, 0.76),
    'Croatia':                (1790, 1.7, 1.1, 0.68),
    'Denmark':                (1780, 1.7, 1.1, 0.68),
    'Switzerland':            (1760, 1.5, 1.2, 0.62),
    'Serbia':                 (1740, 1.5, 1.3, 0.58),
    'Poland':                 (1730, 1.4, 1.3, 0.58),
    'Ukraine':                (1730, 1.4, 1.3, 0.55),
    'Sweden':                 (1720, 1.4, 1.4, 0.55),
    'Austria':                (1720, 1.4, 1.4, 0.55),
    # ── CONMEBOL Nations (7) ──
    'Brazil':                 (1920, 2.6, 0.7, 0.88),
    'Argentina':              (1910, 2.5, 0.7, 0.88),
    'Uruguay':                (1830, 2.0, 0.9, 0.78),
    'Colombia':               (1800, 1.8, 1.0, 0.72),
    'Ecuador':                (1760, 1.6, 1.1, 0.65),
    'Paraguay':               (1700, 1.2, 1.3, 0.50),
    'Chile':                  (1720, 1.3, 1.3, 0.52),
    # ── CONCACAF Nations (6) ──
    'United States':          (1760, 1.7, 1.1, 0.65),
    'Mexico':                 (1770, 1.7, 1.1, 0.65),
    'Canada':                 (1730, 1.5, 1.2, 0.60),
    'Costa Rica':             (1680, 1.2, 1.4, 0.48),
    'Jamaica':                (1660, 1.1, 1.5, 0.45),
    'Honduras':               (1640, 1.0, 1.5, 0.42),
    # ── CAF Nations (11) ──
    'Morocco':                (1780, 1.6, 0.9, 0.72),
    'Senegal':                (1760, 1.6, 1.0, 0.68),
    'Nigeria':                (1750, 1.5, 1.0, 0.65),
    'Egypt':                  (1740, 1.4, 1.0, 0.62),
    'Algeria':                (1740, 1.5, 1.1, 0.62),
    'Cameroon':               (1700, 1.3, 1.2, 0.55),
    'Ghana':                  (1700, 1.3, 1.2, 0.55),
    'Ivory Coast':            (1730, 1.5, 1.1, 0.60),
    'Tunisia':                (1700, 1.2, 1.2, 0.52),
    'Burkina Faso':           (1650, 1.0, 1.4, 0.42),
    'South Africa':           (1650, 1.1, 1.4, 0.45),
    # ── AFC Nations (8) ──
    'Japan':                  (1750, 1.6, 1.0, 0.65),
    'South Korea':            (1740, 1.5, 1.0, 0.62),
    'Australia':              (1720, 1.4, 1.1, 0.58),
    'Iran':                   (1730, 1.4, 1.0, 0.60),
    'Saudi Arabia':           (1680, 1.2, 1.3, 0.50),
    'Qatar':                  (1660, 1.1, 1.4, 0.45),
    'Iraq':                   (1650, 1.0, 1.4, 0.42),
    'United Arab Emirates':   (1650, 1.1, 1.4, 0.45),
    # ── OFC Nation (1) ──
    'New Zealand':            (1650, 1.2, 1.4, 0.48),
    # ── English Championship (24) ──
    'Leeds United':           (1710, 1.6, 1.3, 0.62),
    'Burnley':                (1720, 1.5, 1.2, 0.60),
    'Sheffield United':       (1700, 1.4, 1.4, 0.55),
    'West Bromwich Albion':   (1690, 1.3, 1.4, 0.52),
    'Middlesbrough':          (1680, 1.3, 1.4, 0.52),
    'Coventry City':          (1680, 1.3, 1.4, 0.50),
    'Sunderland':             (1670, 1.3, 1.5, 0.50),
    'Norwich City':           (1670, 1.3, 1.5, 0.50),
    'Watford':                (1660, 1.2, 1.5, 0.48),
    'Bristol City':           (1660, 1.2, 1.5, 0.48),
    'Cardiff City':           (1650, 1.2, 1.5, 0.48),
    'Stoke City':             (1650, 1.1, 1.5, 0.45),
    'Blackburn Rovers':       (1660, 1.2, 1.5, 0.48),
    'Swansea City':           (1650, 1.2, 1.5, 0.48),
    'Millwall':               (1640, 1.1, 1.5, 0.45),
    'Luton Town':             (1640, 1.1, 1.6, 0.42),
    'Hull City':              (1640, 1.1, 1.6, 0.42),
    'Preston North End':      (1630, 1.1, 1.6, 0.42),
    'Sheffield Wednesday':    (1630, 1.1, 1.6, 0.42),
    'Oxford United':          (1620, 1.0, 1.6, 0.40),
    'Plymouth Argyle':        (1610, 1.0, 1.7, 0.38),
    'Derby County':           (1630, 1.1, 1.6, 0.42),
    'Queens Park Rangers':    (1630, 1.1, 1.6, 0.42),
    'Portsmouth':             (1620, 1.0, 1.6, 0.40),
    # ── Brazilian Serie A (20) ──
    'Flamengo':               (1800, 2.0, 0.9, 0.78),
    'Palmeiras':              (1790, 1.9, 0.9, 0.78),
    'Santos':                 (1720, 1.5, 1.2, 0.62),
    'Sao Paulo':              (1750, 1.6, 1.1, 0.65),
    'Corinthians':            (1740, 1.5, 1.2, 0.62),
    'Internacional':          (1710, 1.4, 1.3, 0.58),
    'Gremio':                 (1720, 1.5, 1.3, 0.58),
    'Cruzeiro':               (1700, 1.4, 1.3, 0.55),
    'Atletico Mineiro':       (1720, 1.5, 1.2, 0.60),
    'Botafogo':               (1710, 1.4, 1.3, 0.58),
    'Fortaleza':              (1680, 1.3, 1.4, 0.52),
    'Bahia':                  (1670, 1.3, 1.4, 0.50),
    'Fluminense':             (1700, 1.4, 1.3, 0.55),
    'Vasco da Gama':          (1690, 1.3, 1.4, 0.52),
    'Cuiaba':                 (1640, 1.1, 1.6, 0.45),
    'Juventude':              (1630, 1.1, 1.6, 0.42),
    'Vitoria':                (1640, 1.1, 1.6, 0.42),
    'Atletico Goianiense':    (1630, 1.1, 1.6, 0.42),
    'Criciuma':               (1620, 1.0, 1.7, 0.40),
    'Red Bull Bragantino':    (1670, 1.3, 1.4, 0.50),
    # ── MLS (15) ──
    'Inter Miami':            (1710, 1.6, 1.3, 0.60),
    'LA Galaxy':              (1720, 1.7, 1.3, 0.62),
    'Los Angeles FC':         (1730, 1.7, 1.2, 0.65),
    'Atlanta United':         (1700, 1.5, 1.4, 0.58),
    'New York Red Bulls':     (1680, 1.4, 1.4, 0.55),
    'New York City FC':       (1680, 1.4, 1.4, 0.55),
    'Seattle Sounders':       (1700, 1.5, 1.3, 0.58),
    'Philadelphia Union':     (1690, 1.4, 1.4, 0.55),
    'FC Cincinnati':          (1700, 1.5, 1.3, 0.58),
    'Columbus Crew':          (1690, 1.5, 1.3, 0.58),
    'CF Montreal':            (1660, 1.3, 1.5, 0.50),
    'Toronto FC':             (1650, 1.2, 1.6, 0.48),
    'Vancouver Whitecaps':    (1660, 1.3, 1.5, 0.50),
    'Portland Timbers':       (1670, 1.4, 1.5, 0.52),
    'Sporting Kansas City':   (1660, 1.3, 1.5, 0.50),
    # ── J-League (10) ──
    'Yokohama F Marinos':     (1680, 1.5, 1.3, 0.58),
    'Kawasaki Frontale':      (1690, 1.6, 1.3, 0.60),
    'Urawa Red Diamonds':     (1670, 1.4, 1.3, 0.55),
    'Vissel Kobe':            (1680, 1.5, 1.3, 0.58),
    'Sanfrecce Hiroshima':    (1670, 1.4, 1.3, 0.55),
    'Nagoya Grampus':         (1660, 1.3, 1.4, 0.52),
    'Kashima Antlers':        (1670, 1.4, 1.4, 0.55),
    'Gamba Osaka':            (1650, 1.3, 1.4, 0.50),
    'FC Tokyo':               (1660, 1.3, 1.4, 0.52),
    'Cerezo Osaka':           (1650, 1.3, 1.4, 0.50),
    # ── Belgian Pro League (10) ──
    'Club Brugge':            (1760, 1.8, 1.1, 0.68),
    'Anderlecht':             (1730, 1.6, 1.2, 0.62),
    'Genk':                   (1720, 1.6, 1.3, 0.60),
    'Royal Antwerp':          (1710, 1.5, 1.3, 0.58),
    'Union Saint-Gilloise':   (1720, 1.6, 1.2, 0.60),
    'Gent':                   (1690, 1.4, 1.4, 0.55),
    'Standard Liege':         (1680, 1.3, 1.4, 0.52),
    'Cercle Brugge':          (1660, 1.2, 1.5, 0.48),
    'Mechelen':               (1650, 1.2, 1.5, 0.48),
    'St Truidense':           (1640, 1.1, 1.5, 0.45),
    # ── Swiss Super League (6) ──
    'Young Boys':             (1730, 1.7, 1.2, 0.65),
    'Basel':                  (1710, 1.5, 1.3, 0.58),
    'Lugano':                 (1670, 1.3, 1.4, 0.52),
    'Zurich':                 (1680, 1.4, 1.4, 0.55),
    'Servette':               (1670, 1.3, 1.4, 0.52),
    'St Galler':              (1650, 1.2, 1.5, 0.48),
    # ── Greek Super League (6) ──
    'Olympiacos':             (1760, 1.8, 1.1, 0.68),
    'Panathinaikos':          (1730, 1.6, 1.2, 0.62),
    'PAOK':                   (1740, 1.7, 1.2, 0.65),
    'AEK Athens':             (1730, 1.6, 1.2, 0.62),
    'Aris Thessaloniki':      (1670, 1.3, 1.4, 0.52),
    'OFI Crete':              (1630, 1.1, 1.6, 0.42),
    # ── Austrian Bundesliga (6) ──
    'Red Bull Salzburg':      (1760, 1.9, 1.0, 0.72),
    'Sturm Graz':             (1700, 1.5, 1.3, 0.60),
    'LASK Linz':              (1680, 1.4, 1.4, 0.55),
    'Rapid Vienna':           (1670, 1.3, 1.4, 0.52),
    'Austria Vienna':         (1660, 1.3, 1.5, 0.50),
    'Wolfsberger AC':         (1640, 1.2, 1.5, 0.48),
    # ── Czech First League (6) ──
    'Slavia Prague':          (1750, 1.8, 1.0, 0.70),
    'Sparta Prague':          (1740, 1.7, 1.1, 0.68),
    'Viktoria Plzen':         (1700, 1.5, 1.3, 0.58),
    'Banik Ostrava':          (1640, 1.2, 1.5, 0.45),
    'Sigma Olomouc':          (1630, 1.1, 1.5, 0.45),
    'Slovan Liberec':         (1630, 1.1, 1.5, 0.45),
    # ── Russian Premier League (6) ──
    'Zenit St Petersburg':    (1770, 1.9, 1.0, 0.72),
    'CSKA Moscow':            (1730, 1.6, 1.2, 0.62),
    'Spartak Moscow':         (1730, 1.6, 1.2, 0.62),
    'Lokomotiv Moscow':       (1710, 1.5, 1.3, 0.58),
    'Krasnodar':              (1720, 1.5, 1.2, 0.60),
    'Dynamo Moscow':          (1710, 1.5, 1.3, 0.58),
    # ── Croatian HNL (4) ──
    'Dinamo Zagreb':          (1750, 1.8, 1.0, 0.70),
    'Hajduk Split':           (1700, 1.5, 1.2, 0.60),
    'Rijeka':                 (1670, 1.3, 1.4, 0.52),
    'Osijek':                 (1650, 1.2, 1.5, 0.48),
    # ── Danish Superliga (6) ──
    'FC Copenhagen':          (1740, 1.7, 1.1, 0.65),
    'Midtjylland':            (1710, 1.6, 1.2, 0.62),
    'Brondby':                (1690, 1.4, 1.3, 0.55),
    'FC Nordsjaelland':       (1680, 1.4, 1.4, 0.55),
    'AGF Aarhus':             (1660, 1.3, 1.4, 0.50),
    'Silkeborg':              (1640, 1.1, 1.5, 0.45),
    # ── Norwegian Eliteserien (6) ──
    'Bodo Glimt':             (1710, 1.7, 1.1, 0.65),
    'Molde':                  (1690, 1.5, 1.3, 0.58),
    'Rosenborg':              (1680, 1.4, 1.4, 0.55),
    'Viking':                 (1650, 1.3, 1.5, 0.50),
    'Brann':                  (1650, 1.3, 1.5, 0.50),
    'Lillestrom':             (1630, 1.2, 1.5, 0.48),
    # ── Swedish Allsvenskan (6) ──
    'Malmo FF':               (1720, 1.6, 1.2, 0.62),
    'Djurgardens':            (1680, 1.4, 1.4, 0.55),
    'Hammarby':               (1670, 1.4, 1.4, 0.52),
    'AIK':                    (1670, 1.3, 1.4, 0.52),
    'IFK Goteborg':           (1660, 1.3, 1.5, 0.50),
    'Elfsborg':               (1660, 1.3, 1.4, 0.52),
    # ── More CONMEBOL (4) ──
    'Venezuela':              (1650, 1.1, 1.5, 0.42),
    'Peru':                   (1680, 1.2, 1.4, 0.48),
    'Bolivia':                (1640, 1.0, 1.6, 0.38),
    # ── More CAF (6) ──
    'DR Congo':               (1660, 1.1, 1.3, 0.45),
    'Mali':                   (1660, 1.1, 1.3, 0.45),
    'Guinea':                 (1640, 1.0, 1.4, 0.42),
    'Zambia':                 (1630, 1.0, 1.4, 0.40),
    'Cape Verde':             (1640, 1.0, 1.4, 0.42),
    'Equatorial Guinea':      (1620, 0.9, 1.5, 0.38),
    # ── AFC Asia Cup (6) ──
    'Uzbekistan':             (1650, 1.2, 1.3, 0.50),
    'Jordan':                 (1640, 1.1, 1.3, 0.48),
    'Bahrain':                (1630, 1.1, 1.4, 0.45),
    'Oman':                   (1620, 1.0, 1.4, 0.42),
    'China':                  (1630, 1.1, 1.4, 0.45),
    'Thailand':               (1620, 1.0, 1.4, 0.42),
}

# ═══════════════════════════════════════════════════════════════
# API KEYS
# ═══════════════════════════════════════════════════════════════
FOOTBALL_DATA_API_KEY = os.environ.get('FOOTBALL_DATA_API_KEY', '')
API_SPORT_KEY = os.environ.get('API_SPORT_KEY', '')
AGENTROUTER_KEY = os.environ.get('AGENTROUTER_KEY', '')
AGENTROUTER_BASE = 'https://agentrouter.org/v1'
GROQ_KEY = os.environ.get('GROQ_KEY', '')
GROQ_BASE = 'https://api.groq.com/openai/v1'
OPENROUTER_KEY = os.environ.get('OPENROUTER_KEY', '')
OPENROUTER_BASE = 'https://openrouter.ai/api/v1'

# Compat keys for old env vars
BSD_API_KEY = os.environ.get('BSD_API_KEY', '')
SPORTMONKS_KEY = os.environ.get('SPORTMONKS_KEY', '')
ODDS_API_KEY = os.environ.get('ODDS_API_KEY', '')
FOOTBALL_DATA_BASE = 'https://api.football-data.org/v4'
API_FOOTBALL_BASE = 'https://v3.football.api-sports.io'
SPORTMONKS_BASE = 'https://api.sportmonks.com/v3/football'
ODDS_API_BASE = 'https://api.the-odds-api.com/v4'
BSD_API_BASE = 'https://sports.bzzoiro.com/api/v2'

# ═══════════════════════════════════════════════════════════════
# PERSISTENT CACHE (SQLite — survives restarts, 7-day TTL)
# ═══════════════════════════════════════════════════════════════
_CACHE = {}
_CACHE_TIME = {}
_CACHE_DB = os.path.join(os.path.dirname(__file__), 'api_cache.db')

def _init_cache_db():
    try:
        conn = sqlite3.connect(_CACHE_DB, timeout=5)
        conn.execute('CREATE TABLE IF NOT EXISTS cache (url TEXT PRIMARY KEY, data TEXT, updated REAL)')
        conn.commit()
        conn.close()
    except:
        pass

_init_cache_db()
# Ensure evaluation DB is initialized so predictions get logged
try:
    evaluation.init_evaluation_db()
except:
    pass

def _cached_or_fetch(url, headers, cache_minutes=30):
    now = time.time()
    cache_ttl = cache_minutes * 60
    # Memory check
    if url in _CACHE and (now - _CACHE_TIME.get(url, 0)) < cache_ttl:
        return _CACHE[url]
    # Disk check (7-day max on disk)
    try:
        conn = sqlite3.connect(_CACHE_DB, timeout=3)
        cur = conn.execute('SELECT data, updated FROM cache WHERE url = ?', (url,))
        row = cur.fetchone()
        if row:
            data = json.loads(row[0])
            age = now - row[1]
            if age < cache_ttl:
                _CACHE[url] = data
                _CACHE_TIME[url] = now
                conn.close()
                return data
            if age < 604800:  # 7-day absolute max
                _CACHE[url] = data
                _CACHE_TIME[url] = now
                conn.close()
                return data
        conn.close()
    except:
        pass
    # Fetch
    try:
        h = headers() if callable(headers) else headers
        r = requests.get(url, headers=h, timeout=15)
        if r.status_code == 200:
            data = r.json()
            _CACHE[url] = data
            _CACHE_TIME[url] = now
            try:
                conn = sqlite3.connect(_CACHE_DB, timeout=3)
                conn.execute('INSERT OR REPLACE INTO cache VALUES (?, ?, ?)',
                             (url, json.dumps(data, default=str), now))
                conn.commit()
                conn.close()
            except:
                pass
            return data
    except:
        pass
    # Fallback: return stale disk cache if fetch failed
    try:
        conn = sqlite3.connect(_CACHE_DB, timeout=3)
        cur = conn.execute('SELECT data FROM cache WHERE url = ?', (url,))
        row = cur.fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
    except:
        pass
    return None

# ═══════════════════════════════════════════════════════════════
# THE SPORTS DB — unlimited team resolution
# ═══════════════════════════════════════════════════════════════
SPORTSDB_KEY = '3'  # free tier key
SPORTSDB_BASE = 'https://www.thesportsdb.com/api/v1/json'

def _sportsdb_team_id(name):
    url = f'{SPORTSDB_BASE}/{SPORTSDB_KEY}/searchteams.php?t={name.replace(" ", "%20")}'
    data = _cached_or_fetch(url, {}, 10080)
    if data and data.get('teams'):
        return data['teams'][0].get('idTeam')
    return None

def _sportsdb_team_info(name):
    url = f'{SPORTSDB_BASE}/{SPORTSDB_KEY}/searchteams.php?t={name.replace(" ", "%20")}'
    data = _cached_or_fetch(url, {}, 10080)
    if data and data.get('teams'):
        return data['teams'][0]
    return None

# ═══════════════════════════════════════════════════════════════
# HEADERS
# ═══════════════════════════════════════════════════════════════
headers_api_football = lambda: {'x-apisports-key': os.environ.get('API_SPORT_KEY', '')}
headers_agentrouter = lambda: {'Authorization': f'Bearer {os.environ.get("AGENTROUTER_KEY", "")}', 'Content-Type': 'application/json'}
headers_groq = lambda: {'Authorization': f'Bearer {os.environ.get("GROQ_KEY", "")}', 'Content-Type': 'application/json'}
headers_openrouter = lambda: {'Authorization': f'Bearer {os.environ.get("OPENROUTER_KEY", "")}', 'Content-Type': 'application/json'}
headers_football_data = lambda: {'X-Auth-Token': os.environ.get('FOOTBALL_DATA_API_KEY', '')}
headers_bsd = lambda: {'Authorization': f"Token {os.environ.get('BSD_API_KEY', '')}"}

# ═══════════════════════════════════════════════════════════════
# TEAM NAME RESOLUTION
# ═══════════════════════════════════════════════════════════════
_team_id_cache = {}

def _normalize(n):
    return n.lower().strip().replace('-', ' ').replace('_', ' ')

def _resolve_team_name(name):
    n = name.strip()
    exact = TEAM_DB.get(n)
    if exact:
        return n
    n_lower = _normalize(n)
    for team in TEAM_DB:
        if _normalize(team) == n_lower:
            return team
    matches = difflib.get_close_matches(n, TEAM_DB.keys(), n=1, cutoff=0.6)
    if matches:
        return matches[0]
    if os.environ.get('API_SPORT_KEY', ''):
        try:
            name_encoded = requests.utils.quote(n)
            url = f"{API_FOOTBALL_BASE}/teams?search={name_encoded}"
            data = _cached_or_fetch(url, headers_api_football, 1440)
            if data and 'response' in data and len(data['response']) > 0:
                return data['response'][0]['team']['name']
        except:
            pass
    # TheSportsDB fallback (unlimited, no key needed)
    try:
        info = _sportsdb_team_info(n)
        if info and info.get('strTeam'):
            return info['strTeam']
    except:
        pass
    return n.title()

# ═══════════════════════════════════════════════════════════════
# KELLY CRITERION
# ═══════════════════════════════════════════════════════════════
def kelly_criterion(prob_pct, odds_dec):
    p = prob_pct / 100.0
    q = 1.0 - p
    b = odds_dec - 1.0
    if b <= 0:
        return 0.0
    f = (b * p - q) / b
    return round(max(0.0, min(f, 0.25)), 4)

# ═══════════════════════════════════════════════════════════════
# HEAD-TO-HEAD
# ═══════════════════════════════════════════════════════════════
def _get_team_id_api(team_name):
    if not os.environ.get('API_SPORT_KEY', ''):
        return None
    name_encoded = requests.utils.quote(team_name)
    url = f"{API_FOOTBALL_BASE}/teams?search={name_encoded}"
    data = _cached_or_fetch(url, headers_api_football, 1440)
    if data and 'response' in data and len(data['response']) > 0:
        return data['response'][0]['team']['id']
    url2 = f"{API_FOOTBALL_BASE}/teams?name={name_encoded}"
    data2 = _cached_or_fetch(url2, headers_api_football, 1440)
    if data2 and 'response' in data2 and len(data2['response']) > 0:
        return data2['response'][0]['team']['id']
    return None

def get_head_to_head(team1, team2):
    h2h = {
        'total_matches': 0, 'home_wins': 0, 'draws': 0, 'away_wins': 0,
        'home_goals': 0, 'away_goals': 0, 'last_meetings': [], 'source': 'none'
    }
    t1_lower = team1.lower()
    t2_lower = team2.lower()
    if os.environ.get('API_SPORT_KEY', ''):
        try:
            t1_id = _get_team_id_api(team1)
            t2_id = _get_team_id_api(team2)
            if t1_id and t2_id:
                url = f"{API_FOOTBALL_BASE}/fixtures?h2h={t1_id}-{t2_id}&last=20"
                data = _cached_or_fetch(url, headers_api_football, 60)
                if data and 'response' in data:
                    for match in data['response'][:10]:
                        fixture = match.get('fixture', {})
                        goals = match.get('goals', {})
                        teams = match.get('teams', {})
                        home_name = (teams.get('home') or {}).get('name', '')
                        away_name = (teams.get('away') or {}).get('name', '')
                        home_goals = goals.get('home')
                        away_goals = goals.get('away')
                        if home_goals is None or away_goals is None:
                            continue
                        is_home = t1_lower in home_name.lower() or t2_lower in away_name.lower()
                        t1_goals = home_goals if is_home else away_goals
                        t2_goals = away_goals if is_home else home_goals
                        h2h['last_meetings'].append({
                            'date': fixture.get('date', '')[:10],
                            'home': home_name, 'away': away_name,
                            'home_goals': home_goals, 'away_goals': away_goals
                        })
                        h2h['total_matches'] += 1
                        h2h['home_goals'] += t1_goals
                        h2h['away_goals'] += t2_goals
                        if t1_goals > t2_goals:
                            h2h['home_wins'] += 1
                        elif t2_goals > t1_goals:
                            h2h['away_wins'] += 1
                        else:
                            h2h['draws'] += 1
                    if h2h['total_matches'] > 0:
                        h2h['source'] = 'api-sports'
                        return h2h
        except:
            pass
    if os.environ.get('BSD_API_KEY', ''):
        try:
            ids = {}
            for team in [team1, team2]:
                name_encoded = requests.utils.quote(team)
                d = _cached_or_fetch(f"{BSD_API_BASE}/teams/?name={name_encoded}", headers_bsd, 1440)
                if d:
                    results = d.get('results') if isinstance(d, dict) else (d if isinstance(d, list) else [])
                    if results:
                        ids[team] = results[0].get('id')
            if ids.get(team1) and ids.get(team2):
                h2h_url = f"{BSD_API_BASE}/events/?team_id={ids[team1]}&status=finished&limit=50"
                hd = _cached_or_fetch(h2h_url, headers_bsd, 60)
                if hd:
                    evr = hd.get('results') if isinstance(hd, dict) else (hd if isinstance(hd, list) else [])
                    for ev in evr:
                        hs = ev.get('home_score')
                        ac = ev.get('away_score')
                        if hs is None or ac is None:
                            continue
                        opp_id = ev.get('away_team_id') if ev.get('home_team_id') == ids[team1] else ev.get('home_team_id')
                        if opp_id != ids[team2]:
                            continue
                        ed = ev.get('event_date', '')[:10]
                        t1_goals = hs if ev.get('home_team_id') == ids[team1] else ac
                        t2_goals = ac if ev.get('home_team_id') == ids[team1] else hs
                        h2h['last_meetings'].append({
                            'date': ed, 'home': ev.get('home_team'), 'away': ev.get('away_team'),
                            'home_goals': hs, 'away_goals': ac
                        })
                        h2h['total_matches'] += 1
                        h2h['home_goals'] += t1_goals
                        h2h['away_goals'] += t2_goals
                        if t1_goals > t2_goals:
                            h2h['home_wins'] += 1
                        elif t2_goals > t1_goals:
                            h2h['away_wins'] += 1
                        else:
                            h2h['draws'] += 1
                    if h2h['total_matches'] > 0:
                        h2h['all_time_count'] = h2h['total_matches']
                        h2h['last_meetings'] = sorted(h2h['last_meetings'], key=lambda x: x.get('date', ''), reverse=True)[:10]
                        h2h['total_matches'] = min(h2h['total_matches'], 10)
                        h2h['source'] = 'bsd'
                        return h2h
        except:
            pass
    return h2h

# ═══════════════════════════════════════════════════════════════
# COMPETITION MATCHES (e.g. World Cup 2026 group stage only)
# ═══════════════════════════════════════════════════════════════
def get_competition_matches(team_name, from_date, to_date=None):
    results = {
        'matches': [], 'goals_scored': 0, 'goals_conceded': 0,
        'wins': 0, 'draws': 0, 'losses': 0, 'played': 0
    }
    if not os.environ.get('BSD_API_KEY', ''):
        return results
    try:
        name_encoded = requests.utils.quote(team_name)
        d = _cached_or_fetch(f"{BSD_API_BASE}/teams/?name={name_encoded}", headers_bsd, 1440)
        if not d:
            return results
        res = d.get('results') if isinstance(d, dict) else (d if isinstance(d, list) else [])
        if not res:
            return results
        tid = res[0].get('id')
        url = f"{BSD_API_BASE}/events/?team_id={tid}&status=finished&limit=50&date_from={from_date}"
        if to_date:
            url += f"&date_to={to_date}"
        data = _cached_or_fetch(url, headers_bsd, 60)
        if not data:
            return results
        for ev in (data.get('results') if isinstance(data, dict) else (data if isinstance(data, list) else [])):
            hs = ev.get('home_score'); ac = ev.get('away_score')
            if hs is None or ac is None:
                continue
            is_home = ev.get('home_team_id') == tid
            scored = hs if is_home else ac
            conceded = ac if is_home else hs
            results['matches'].append({
                'date': ev.get('event_date', '')[:10],
                'home': ev.get('home_team', ''), 'away': ev.get('away_team', ''),
                'home_score': hs, 'away_score': ac,
                'scored': scored, 'conceded': conceded,
                'result': ('W' if scored > conceded else 'D' if scored == conceded else 'L')
            })
            results['goals_scored'] += scored
            results['goals_conceded'] += conceded
            results['played'] += 1
            if scored > conceded: results['wins'] += 1
            elif scored == conceded: results['draws'] += 1
            else: results['losses'] += 1
        if results['played'] > 0:
            results['gs_avg'] = round(results['goals_scored'] / results['played'], 3)
            results['gc_avg'] = round(results['goals_conceded'] / results['played'], 3)
            results['form_pct'] = round((results['wins'] * 3 + results['draws']) / (results['played'] * 3) * 100, 1)
    except:
        pass
    return results

# ═══════════════════════════════════════════════════════════════
# MARKET PROBABILITIES
# ═══════════════════════════════════════════════════════════════
def get_market_probabilities(home_team, away_team, league_key=None):
    """Use odds_api_scraper for market probabilities with overround removal"""
    global ODDS_API_KEY
    if not ODDS_API_KEY and oas:
        ODDS_API_KEY = oas.ODDS_API_KEY
    if not ODDS_API_KEY:
        return None
    cache_key = f"odds_{home_team}_{away_team}"
    now = time.time()
    if cache_key in _CACHE and (now - _CACHE_TIME.get(cache_key, 0)) < 1800:
        return _CACHE[cache_key]
    if oas is None:
        return None
    try:
        event = oas.get_odds_for_match(home_team, away_team, league_key=league_key)
        if not event:
            return None
        probs = oas.extract_market_probabilities(event)
        if not probs:
            return None
        result = {
            'available': True,
            'home': probs['fair_probs'].get('home', 33.33),
            'draw': probs['fair_probs'].get('draw', 33.33),
            'away': probs['fair_probs'].get('away', 33.33),
            'overround': probs.get('avg_overround', 0),
            'bookmaker_count': probs['bookmaker_count'],
            'fair_probs': probs['fair_probs'],
        }
        _CACHE[cache_key] = result
        _CACHE_TIME[cache_key] = now
        return result
    except Exception:
        pass
    return None

# ═══════════════════════════════════════════════════════════════
# GET LIVE TEAM DATA
# ═══════════════════════════════════════════════════════════════
POPULAR_LEAGUES = [39, 140, 135, 78, 61, 2, 1, 88, 94, 203, 13, 9]

def get_live_team_data(team_name, competition=None):
    default = TEAM_DB.get(team_name)
    if default:
        elo, gf, ga, form = default
    else:
        elo, gf, ga, form = 1600, 1.3, 1.4, 0.50
    result = {
        'attack_xg': gf, 'defense_xg': ga,
        'form_points': form * 15,
        'elo': elo, 'injury_count': 0, 'played_count': 10,
        'source': 'database'
    }
    if os.environ.get('API_SPORT_KEY', ''):
        try:
            team_info = None
            cached = _team_id_cache.get(_normalize(team_name))
            if cached:
                team_info = cached
            if not team_info:
                name_encoded = requests.utils.quote(team_name)
                url = f"{API_FOOTBALL_BASE}/teams?search={name_encoded}"
                data = _cached_or_fetch(url, headers_api_football, 1440)
                if data and 'response' in data and len(data['response']) > 0:
                    team = data['response'][0]['team']
                    team_info = {'id': team['id'], 'name': team['name']}
                    _team_id_cache[_normalize(team_name)] = team_info
                else:
                    url2 = f"{API_FOOTBALL_BASE}/teams?name={name_encoded}"
                    data2 = _cached_or_fetch(url2, headers_api_football, 1440)
                    if data2 and 'response' in data2 and len(data2['response']) > 0:
                        team = data2['response'][0]['team']
                        team_info = {'id': team['id'], 'name': team['name']}
                        _team_id_cache[_normalize(team_name)] = team_info
            if not team_info:
                try:
                    sportsdb_id = _sportsdb_team_id(team_name)
                    if sportsdb_id:
                        info = _sportsdb_team_info(team_name)
                        if info:
                            team_info = {'id': sportsdb_id, 'name': info.get('strTeam', team_name)}
                            _team_id_cache[_normalize(team_name)] = team_info
                except:
                    pass
            if team_info:
                team_id = team_info['id']
                fixtures_data = None
                current_year = datetime.now().year
                for season in [current_year, current_year - 1, current_year - 2]:
                    season_url = f"{API_FOOTBALL_BASE}/fixtures?team={team_id}&season={season}&status=FT"
                    data = _cached_or_fetch(season_url, headers_api_football, 60)
                    if data and 'response' in data:
                        n = len(data['response'])
                        if n >= 3:
                            fixtures_data = data
                            break
                if not fixtures_data:
                    for season in [current_year, current_year - 1, current_year - 2]:
                        season_url = f"{API_FOOTBALL_BASE}/fixtures?team={team_id}&season={season}"
                        data = _cached_or_fetch(season_url, headers_api_football, 60)
                        if data and 'response' in data:
                            ft = [m for m in data['response'] if m.get('fixture',{}).get('status',{}).get('short') in ['FT','AET','PEN']]
                            if len(ft) >= 3:
                                fixtures_data = data
                                break
                if fixtures_data and 'response' in fixtures_data:
                    matches = fixtures_data['response']
                    if len(matches) >= 1:
                        xi = 0.0018
                        now_ts = time.time()
                        w_gf, w_ga, tw = 0.0, 0.0, 0.0
                        w_hgf, w_hga, hw = 0.0, 0.0, 0.0
                        w_agf, w_aga, aw = 0.0, 0.0, 0.0
                        wins, draws = 0, 0
                        count = 0
                        for m in matches:
                            if m.get('fixture', {}).get('status', {}).get('short') not in ['FT', 'AET', 'PEN']:
                                continue
                            is_home = m.get('teams', {}).get('home', {}).get('id') == team_id
                            hg = (m.get('goals', {}) or {}).get('home', 0) or 0
                            ag = (m.get('goals', {}) or {}).get('away', 0) or 0
                            m_date = m.get('fixture', {}).get('date', '')
                            days_since = 30
                            if m_date:
                                try:
                                    m_ts = datetime.strptime(m_date[:10], '%Y-%m-%d').timestamp()
                                    days_since = max(1, (now_ts - m_ts) / 86400)
                                except:
                                    pass
                            w = exp(-xi * days_since)
                            opp = (m.get('teams', {}).get('away', {}).get('name', '') if is_home else m.get('teams', {}).get('home', {}).get('name', ''))
                            opp_elo = TEAM_DB.get(opp, (1700, 1.3, 1.4, 0.50))[0]
                            elo_factor = opp_elo / 1700.0
                            gf = hg if is_home else ag
                            gc = ag if is_home else hg
                            w_gf += gf * w * elo_factor
                            w_ga += gc * w
                            tw += w
                            if is_home:
                                w_hgf += gf * w * elo_factor; w_hga += gc * w; hw += w
                            else:
                                w_agf += gf * w * elo_factor; w_aga += gc * w; aw += w
                            if gf > gc: wins += 1
                            elif gf == gc: draws += 1
                            count += 1
                        if count >= 3 and tw > 0:
                            avg_gf = w_gf / tw
                            avg_ga = w_ga / tw
                            form_pts = (wins * 3 + draws * 1)
                            max_pts = count * 3
                            form_norm = form_pts / max_pts if max_pts > 0 else 0.5
                            attack_xg = max(0.3, min(4.0, avg_gf))
                            defense_xg = max(0.3, min(4.0, avg_ga))
                            form_points = max(0, min(15, form_norm * 15))
                            elo_calc = 1500 + int(((avg_gf - avg_ga) * 80) + (wins * 2))
                            elo_calc = max(1400, min(2000, elo_calc))
                            result = {
                                'attack_xg': attack_xg,
                                'defense_xg': defense_xg,
                                'form_points': form_points,
                                'elo': elo_calc,
                                'injury_count': 0,
                                'played_count': count,
                                'source': 'live_api',
                                'home_gs': round(w_hgf / max(hw, 0.001), 3),
                                'home_gc': round(w_hga / max(hw, 0.001), 3),
                                'away_gs': round(w_agf / max(aw, 0.001), 3),
                                'away_gc': round(w_aga / max(aw, 0.001), 3),
                                'home_count': int(hw > 0 and count > 0),
                                'away_count': int(aw > 0 and count > 0),
                            }
                if result.get('source') == 'live_api':
                    injuries_url = f"{API_FOOTBALL_BASE}/injuries?team={team_id}"
                    injuries_data = _cached_or_fetch(injuries_url, headers_api_football, 60)
                    if injuries_data and 'response' in injuries_data:
                        result['injury_count'] = len(injuries_data['response'])
        except:
            pass
    # Fallback: SofaScore direct API via curl_cffi (unlimited, no key)
    if result.get('source') == 'database':
        try:
            from curl_cffi import requests as curl_requests
            sofa_headers = {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 14; Pixel 9 Pro) AppleWebKit/537.36 Chrome/120.0.6099.230 Mobile Safari/537.36',
                'Accept': 'application/json', 'Origin': 'https://www.sofascore.com',
                'Referer': 'https://www.sofascore.com/', 'x-requested-with': '721637',
            }
            sofa_name = team_name.replace(' ', '%20')
            search_cache_key = f'sofa_search_{sofa_name}'
            sdata = _CACHE.get(search_cache_key) if search_cache_key in _CACHE else None
            if sdata is None:
                time.sleep(0.35)
                sr = curl_requests.get(
                    f'https://www.sofascore.com/api/v1/search/teams?q={sofa_name}',
                    headers=sofa_headers, impersonate='chrome120', timeout=15)
                if sr.status_code == 200:
                    sdata = sr.json()
                    _CACHE[search_cache_key] = sdata
                    _CACHE_TIME[search_cache_key] = time.time()
            if sdata and 'results' in sdata:
                for r in sdata['results']:
                    if r.get('type') == 'team' and 'entity' in r:
                        team_entity = r['entity']
                        sofa_team_id = team_entity.get('id')
                        ev_cache_key = f'sofa_events_{sofa_team_id}'
                        ev_data = _CACHE.get(ev_cache_key) if ev_cache_key in _CACHE else None
                        if ev_data is None:
                            time.sleep(0.35)
                            evr = curl_requests.get(
                                f'https://www.sofascore.com/api/v1/team/{sofa_team_id}/events/last/20',
                                headers=sofa_headers, impersonate='chrome120', timeout=15)
                            if evr.status_code == 200:
                                ev_data = evr.json()
                                _CACHE[ev_cache_key] = ev_data
                                _CACHE_TIME[ev_cache_key] = time.time()
                        if ev_data and 'events' in ev_data:
                            events = [e for e in ev_data['events'] if e.get('status', {}).get('type') == 'finished']
                            if len(events) >= 3:
                                total_gf, total_ga, wins, draws = 0, 0, 0, 0
                                for e in events[:15]:
                                    hs = (e.get('homeScore') or {}).get('display', 0)
                                    aws = (e.get('awayScore') or {}).get('display', 0)
                                    is_home = (e.get('homeTeam') or {}).get('id') == sofa_team_id
                                    gf = hs if is_home else aws
                                    ga = aws if is_home else hs
                                    total_gf += gf; total_ga += ga
                                    if gf > ga: wins += 1
                                    elif gf == ga: draws += 1
                                n = min(len(events), 15)
                                avg_gf = max(0.3, min(4.0, total_gf / n))
                                avg_ga = max(0.3, min(4.0, total_ga / n))
                                form_norm = (wins * 3 + draws) / (n * 3) if n > 0 else 0.5
                                result['attack_xg'] = avg_gf
                                result['defense_xg'] = avg_ga
                                result['form_points'] = max(0, min(15, form_norm * 15))
                                result['elo'] = max(1400, min(2000, 1500 + int(((avg_gf - avg_ga) * 40) + (wins * 1.5))))
                                result['played_count'] = n
                                result['source'] = 'sofascore_api'
                                result['injury_count'] = 0
                            break
        except Exception:
            pass
    # Fallback: Flashscore via Edge WebDriver (unlimited)
    if result.get('source') == 'database':
        try:
            fs = edge_scraper.get_team_form(team_name)
            if fs and fs.get('matches', 0) >= 3:
                n = fs['matches']
                result['attack_xg'] = fs['avg_gs']
                result['defense_xg'] = fs['avg_gc']
                result['form_points'] = min(15, fs['form_rating'] / 100 * 15)
                elo_calc = 1500 + int(((fs['avg_gs'] - fs['avg_gc']) * 80) + (fs['wins'] * 2))
                result['elo'] = max(1400, min(2000, elo_calc))
                result['played_count'] = n
                result['source'] = 'flashscore'
                result['injury_count'] = 0
        except:
            pass
    # Final fallback: Sofascore via Edge WebDriver (unlimited, bypasses Cloudflare)
    if result.get('source') == 'database':
        try:
            ss = edge_scraper.get_sofascore_team_form(team_name)
            if ss and ss.get('matches', 0) >= 3:
                n = ss['matches']
                result['attack_xg'] = ss['avg_gs']
                result['defense_xg'] = ss['avg_gc']
                result['form_points'] = min(15, ss['form_rating'] / 100 * 15)
                elo_calc = 1500 + int(((ss['avg_gs'] - ss['avg_gc']) * 80) + (ss['wins'] * 2))
                result['elo'] = max(1400, min(2000, elo_calc))
                result['played_count'] = n
                result['source'] = 'sofascore_edge'
                result['injury_count'] = 0
        except:
            pass
    return result

# ═══════════════════════════════════════════════════════════════
# WIKIPEDIA SCRAPER — unlimited historical league data
# ═══════════════════════════════════════════════════════════════
WIKI_BASE = 'https://en.wikipedia.org'
WIKI_CACHE = {}
WIKI_LEAGUES = {
    'Premier League': '/wiki/2025%E2%80%9326_Premier_League',
    'La Liga': '/wiki/2025%E2%80%9326_La_Liga',
    'Bundesliga': '/wiki/2025%E2%80%9326_Bundesliga',
    'Serie A': '/wiki/2025%E2%80%9326_Serie_A',
    'Ligue 1': '/wiki/2025%E2%80%9326_Ligue_1',
    'Eredivisie': '/wiki/2025%E2%80%9326_Eredivisie',
}

def _wiki_fetch(url, cache_minutes=1440):
    if url in WIKI_CACHE:
        if time.time() - WIKI_CACHE[url]['time'] < cache_minutes * 60:
            return WIKI_CACHE[url]['data']
    try:
        r = requests.get(WIKI_BASE + url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        if r.status_code == 200:
            WIKI_CACHE[url] = {'data': r.text, 'time': time.time()}
            return r.text
    except:
        pass
    return None

def _wiki_parse_scores(html, team_name=None):
    import re
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'lxml')
    scores = []
    for table in soup.find_all('table', class_='wikitable'):
        for row in table.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) >= 4:
                text = row.get_text(strip=True)
                m = re.search(r'(\d+)\s*[–\-—]\s*(\d+)', text)
                if m:
                    texts = [c.get_text(strip=True) for c in cells]
                    non_numbers = [t for t in texts if t and not t.isdigit() and len(t) > 2]
                    if len(non_numbers) >= 2:
                        h = int(m.group(1)); a = int(m.group(2))
                        if team_name is None or any(team_name.lower() in t.lower() for t in non_numbers):
                            scores.append((non_numbers[0], h, a, non_numbers[-1]))
    return scores

def wiki_team_matches(team_name, league_name=None):
    """Fetch team match history from Wikipedia (unlimited)"""
    leagues = [league_name] if league_name else list(WIKI_LEAGUES.keys())
    all_scores = []
    for lg in leagues:
        path = WIKI_LEAGUES.get(lg)
        if not path:
            continue
        html = _wiki_fetch(path)
        if html:
            scores = _wiki_parse_scores(html, team_name)
            all_scores.extend(scores)
    return all_scores

# ═══════════════════════════════════════════════════════════════
# COMPUTE FEATURES
# ═══════════════════════════════════════════════════════════════
def compute_features(home_team, away_team, neutral_venue=False):
    live_home = get_live_team_data(home_team)
    live_away = get_live_team_data(away_team)
    h2h = get_head_to_head(home_team, away_team)
    source_priority = {'live_api': 3, 'flashscore': 2, 'sportsdb': 1, 'database': 0}
    src_h = live_home.get('source', 'database')
    src_a = live_away.get('source', 'database')
    best_src = src_h if source_priority.get(src_h, 0) >= source_priority.get(src_a, 0) else src_a

    def _blend(xg, raw_goals):
        return W_XG * float(xg) + (1.0 - W_XG) * float(raw_goals)

    atk_h = _blend(live_home.get('attack_xg', 1.2), live_home.get('attack_xg', 1.2))
    atk_a = _blend(live_away.get('attack_xg', 1.0), live_away.get('attack_xg', 1.0))
    def_h = _blend(live_home.get('defense_xg', 1.2), live_home.get('defense_xg', 1.2))
    def_a = _blend(live_away.get('defense_xg', 1.0), live_away.get('defense_xg', 1.0))

    features = {
        'attack_xg_home': atk_h,
        'attack_xg_away': atk_a,
        'defense_xg_home': def_h,
        'defense_xg_away': def_a,
        'form_points_home': live_home.get('form_points', 7.5),
        'form_points_away': live_away.get('form_points', 7.5),
        'elo_home': live_home.get('elo', 1500),
        'elo_away': live_away.get('elo', 1500),
        'h2h_home_wins': h2h.get('home_wins', 0),
        'h2h_draws': h2h.get('draws', 0),
        'h2h_away_wins': h2h.get('away_wins', 0),
        'h2h_matches': h2h.get('total_matches', 0),
        'h2h_home_goals': h2h.get('home_goals', 0),
        'h2h_away_goals': h2h.get('away_goals', 0),
        'home_advantage': HOME_ADV_BASE if not neutral_venue else 1.0,
        'injury_penalty_home': min(live_home.get('injury_count', 0) * 0.03, 0.15),
        'injury_penalty_away': min(live_away.get('injury_count', 0) * 0.03, 0.15),
        'days_since_last_home': 4,
        'days_since_last_away': 4,
        'league_avg_xg': 1.5,
        'source': best_src,
        'source_home': src_h,
        'source_away': src_a,
    }
    if features['h2h_matches'] > 0:
        h2h_home_avg = features['h2h_home_goals'] / max(features['h2h_matches'], 1)
        h2h_away_avg = features['h2h_away_goals'] / max(features['h2h_matches'], 1)
        features['attack_xg_home'] = features['attack_xg_home'] * 0.7 + h2h_home_avg * 0.3
        features['attack_xg_away'] = features['attack_xg_away'] * 0.7 + h2h_away_avg * 0.3
    return features

# ═══════════════════════════════════════════════════════════════
# DIXON-COLES CORE (fit_rho, calibrators, tau correction, predict)
# ═══════════════════════════════════════════════════════════════

def _dc_tau(x, y, lam, mu, rho):
    if x == 0 and y == 0:
        return 1.0 - lam * mu * rho
    if x == 0 and y == 1:
        return 1.0 + lam * rho
    if x == 1 and y == 0:
        return 1.0 + mu * rho
    if x == 1 and y == 1:
        return 1.0 - rho
    return 1.0


def _score_matrix(lam, mu, rho, max_goals=MAX_GOALS_DC):
    lam = max(0.01, float(lam))
    mu = max(0.01, float(mu))
    h = sp_poisson.pmf(np.arange(max_goals + 1), lam)
    a = sp_poisson.pmf(np.arange(max_goals + 1), mu)
    M = np.outer(h, a)
    for i in (0, 1):
        for j in (0, 1):
            M[i, j] *= _dc_tau(i, j, lam, mu, rho)
    M = np.clip(M, 1e-15, None)
    return M / M.sum()


def fit_rho(historical_matches, xi=XI_DECAY, league=None):
    """Time-decay weighted MLE for rho. If league is given and we have a pre-trained
       league-specific rho, use that instead (much more robust)."""
    global _FITTED_RHO
    if league and mt:
        lr = mt.get_rho(league)
        if lr is not None:
            _FITTED_RHO = lr
            return _FITTED_RHO
    if not historical_matches:
        _FITTED_RHO = RHO_DEFAULT
        return _FITTED_RHO

    hg = np.array([m['home_goals'] for m in historical_matches], dtype=int)
    ag = np.array([m['away_goals'] for m in historical_matches], dtype=int)
    lam = np.clip(np.array([m['lambda_home'] for m in historical_matches], float), 0.01, None)
    mu = np.clip(np.array([m['lambda_away'] for m in historical_matches], float), 0.01, None)
    w = np.exp(-xi * np.array([m['days_ago'] for m in historical_matches], float))

    base = (sp_poisson.logpmf(hg, lam) + sp_poisson.logpmf(ag, mu))

    def neg_ll(rho):
        tau = np.array([_dc_tau(int(x), int(y), l, u, rho)
                        for x, y, l, u in zip(hg, ag, lam, mu)])
        tau = np.clip(tau, 1e-12, None)
        ll = w * (base + np.log(tau))
        return -np.sum(ll)

    res = minimize_scalar(neg_ll, bounds=RHO_BOUNDS, method='bounded')
    _FITTED_RHO = float(res.x) if res.success else RHO_DEFAULT
    _FITTED_RHO = max(RHO_BOUNDS[0], min(RHO_BOUNDS[1], _FITTED_RHO))
    return _FITTED_RHO


def fit_calibrators(eval_rows):
    """Isotonic regression on 1X2 outputs from historical predictions.
       eval_rows: list of dicts: home_win_prob, draw_prob, away_win_prob, result (H/D/A)."""
    global _CALIBRATORS
    if len(eval_rows) < 50:
        _CALIBRATORS = {}
        return _CALIBRATORS

    cols = {'home': ('home_win_prob', 'H'),
            'draw': ('draw_prob', 'D'),
            'away': ('away_win_prob', 'A')}
    fitted = {}
    for key, (prob_key, label) in cols.items():
        x = np.array([r[prob_key] for r in eval_rows], float) / 100.0
        y = np.array([1.0 if r['result'] == label else 0.0 for r in eval_rows], float)
        iso = IsotonicRegression(out_of_bounds='clip', y_min=0.0, y_max=1.0)
        try:
            iso.fit(x, y)
            fitted[key] = iso
        except Exception:
            pass
    _CALIBRATORS = fitted
    return _CALIBRATORS


def _apply_calibration(home, draw, away):
    if not _CALIBRATORS:
        return home, draw, away
    h = float(_CALIBRATORS['home'].predict([[home / 100.0]])[0]) if 'home' in _CALIBRATORS else home / 100.0
    d = float(_CALIBRATORS['draw'].predict([[draw / 100.0]])[0]) if 'draw' in _CALIBRATORS else draw / 100.0
    a = float(_CALIBRATORS['away'].predict([[away / 100.0]])[0]) if 'away' in _CALIBRATORS else away / 100.0
    s = h + d + a
    if s <= 0:
        return home, draw, away
    return h * 100 / s, d * 100 / s, a * 100 / s


def dixon_coles_predict(home_goals_avg, away_goals_avg, rho=None, max_goals=MAX_GOALS_DC):
    """Full Dixon-Coles prediction. Returns same dict contract as original."""
    if rho is None:
        rho = _FITTED_RHO
    hg = max(0.01, float(home_goals_avg))
    ag = max(0.01, float(away_goals_avg))
    probs = _score_matrix(hg, ag, rho, max_goals)

    home_win = float(np.tril(probs, -1).sum())
    draw = float(np.trace(probs))
    away_win = float(np.triu(probs, 1).sum())
    btts_yes = float(probs[1:, 1:].sum())
    btts_no = 1.0 - btts_yes
    idx = np.arange(max_goals + 1)
    total = idx[:, None] + idx[None, :]
    under_2_5 = float(probs[total <= 2].sum())
    over_2_5 = 1.0 - under_2_5
    under_3_5 = float(probs[total <= 3].sum())
    under_1_5 = float(probs[total <= 1].sum())
    under_0_5 = float(probs[total <= 0].sum())
    under_4_5 = float(probs[total <= 4].sum())
    under_5_5 = float(probs[total <= 5].sum())
    home_expected = float((idx * probs.sum(axis=1)).sum())
    away_expected = float((idx * probs.sum(axis=0)).sum())

    max_idx = np.unravel_index(probs.argmax(), probs.shape)
    most_likely = f"{max_idx[0]}-{max_idx[1]}"
    most_likely_prob = round(float(probs[max_idx]) * 100, 2)

    flat = [(i, j) for i in range(max_goals + 1) for j in range(max_goals + 1)]
    flat.sort(key=lambda s: -probs[s[0], s[1]])
    top_scores = [{'score': f'{i}-{j}', 'prob': round(float(probs[i, j]) * 100, 2)}
                  for i, j in flat[:8]]

    # Asian Handicap (same as original)
    single_goal_win = float(probs[(idx[:, None] - idx[None, :]) == 1].sum())
    two_goal_win = float(probs[(idx[:, None] - idx[None, :]) >= 2].sum())
    ah_0 = home_win
    ah_m025 = home_win + 0.5 * draw
    ah_05 = home_win
    ah_m075 = home_win - 0.5 * single_goal_win
    ah_10 = two_goal_win + 0.5 * (home_win - two_goal_win)

    return {
        'home_win_prob': home_win,
        'draw_prob': draw,
        'away_win_prob': away_win,
        'most_likely_score': most_likely,
        'exact_score_prob': most_likely_prob,
        'under_0_5': under_0_5,
        'under_1_5': under_1_5,
        'under_2_5': under_2_5,
        'under_3_5': under_3_5,
        'under_4_5': under_4_5,
        'under_5_5': under_5_5,
        'over_2_5': over_2_5,
        'over_3_5': 1.0 - under_3_5,
        'over_4_5': 1.0 - under_4_5,
        'btts_yes': btts_yes,
        'btts_no': btts_no,
        'asian_handicap': {
            'ah_0': round(ah_0, 4),
            'ah_m025': round(ah_m025, 4),
            'ah_05': round(ah_05, 4),
            'ah_m075': round(ah_m075, 4),
            'ah_10': round(ah_10, 4),
        },
        'probs': probs,
        'expected_goals_home': home_expected,
        'expected_goals_away': away_expected,
        'top_scores': top_scores,
        'top_3': top_scores[:3],
    }

# ═══════════════════════════════════════════════════════════════
# AI ENSEMBLE (AgentRouter or Groq)
# ═══════════════════════════════════════════════════════════════
def _ai_chat_completion(url, headers, model, messages, temperature=0.1, max_tokens=200, timeout=15):
    try:
        resp = requests.post(url, headers=headers,
            json={"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
            timeout=timeout)
        if resp.status_code == 200:
            return resp.json()['choices'][0]['message']['content']
        print(f"[AI] ⚠️ {model} returned {resp.status_code}")
    except Exception as e:
        print(f"[AI] ⚠️ {model} failed: {e}")
    return None

def _pick_ai_provider():
    providers = []
    if os.environ.get('AGENTROUTER_KEY', ''):
        providers.append(('agentrouter', AGENTROUTER_BASE, headers_agentrouter(), 'deepseek-v4-flash'))
        providers.append(('agentrouter', AGENTROUTER_BASE, headers_agentrouter(), 'claude-opus-4-6'))
    if os.environ.get('GROQ_KEY', ''):
        providers.append(('groq', GROQ_BASE, headers_groq(), 'llama-3.3-70b-versatile'))
    if os.environ.get('OPENROUTER_KEY', ''):
        providers.append(('openrouter', OPENROUTER_BASE, headers_openrouter(), 'mistralai/mistral-7b-instruct'))
        providers.append(('openrouter', OPENROUTER_BASE, headers_openrouter(), 'cognitivecomputations/dolphin-mixtral-8x7b'))
        providers.append(('openrouter', OPENROUTER_BASE, headers_openrouter(), 'google/gemini-2.0-flash-exp:free'))
    return providers

def ai_ensemble(features, prediction, home_team='', away_team=''):
    providers = _pick_ai_provider()
    if not providers:
        return prediction
    # ── مرحلـة 1: Devil's Advocate ──
    da_system = ("You are a strict Devil's Advocate for football predictions. "
                 "Your job is to DESTROY predictions. Find 3 reasons the prediction FAILS. "
                 "Return JSON only: {\"risk_factors\": [\"r1\",\"r2\",\"r3\"], "
                 "\"risk_score\": float 0-1, \"auto_reject\": bool}")
    da_user = (f"Match: {home_team} vs {away_team}. "
               f"Model prediction: {prediction.get('most_likely_score', '0-0')}. "
               f"Home {prediction.get('home_win_prob', 33):.1f}% / Draw "
               f"{prediction.get('draw_prob', 33):.1f}% / Away "
               f"{prediction.get('away_win_prob', 33):.1f}%. "
               f"Features: {json.dumps(features, default=str)}. "
               "Find 3 reasons this prediction fails. Risk score > 0.65 → auto_reject=true.")
    da_messages = [
        {"role": "system", "content": da_system},
        {"role": "user", "content": da_user}
    ]
    da_result = None
    for prov_name, base_url, headers, model in providers:
        content = _ai_chat_completion(f"{base_url}/chat/completions", headers, model, da_messages, 0.1, 250)
        if content:
            try:
                da_result = json.loads(content)
                if isinstance(da_result, dict):
                    break
            except:
                continue
    if da_result and isinstance(da_result, dict):
        prediction['devils_advocate'] = {
            'risk_factors': da_result.get('risk_factors', []),
            'risk_score': da_result.get('risk_score', 0.0),
            'auto_reject': da_result.get('auto_reject', False)
        }
        if da_result.get('auto_reject'):
            prediction['auto_rejected'] = True
            prediction['rejection_reasons'] = da_result.get('risk_factors', [])
            return prediction
    prediction['auto_rejected'] = False
    # ── مرحلـة 2: التعديل الأساسي (إن لم يُرفض) ──
    prompt = (
        "You are a football match analysis AI. Given the following match features as JSON, "
        "return a JSON object ONLY with: "
        '{"score_correction": [int, int], "confidence_boost": float(-0.1 to 0.1), "key_factor": string}. '
        "score_correction adjusts the most likely score (max +/-2 each). "
        "confidence_boost adjusts prediction confidence. "
        "key_factor is a 1-sentence explanation.\n\n"
        f"Features: {json.dumps(features, default=str)}\n"
        f"Current prediction (most likely): {prediction.get('most_likely_score', '0-0')}\n"
        "Return JSON only, no other text."
    )
    messages = [
        {"role": "system", "content": "You are a football prediction expert. Return JSON only."},
        {"role": "user", "content": prompt}
    ]
    for prov_name, base_url, headers, model in providers:
        content = _ai_chat_completion(f"{base_url}/chat/completions", headers, model, messages, 0.1, 200)
        if content:
            try:
                adjustment = json.loads(content)
                if isinstance(adjustment, dict):
                    return _apply_ai_adjustment(prediction, adjustment)
            except:
                continue
    return prediction

def _apply_ai_adjustment(prediction, adjustment):
    if not isinstance(adjustment, dict):
        return prediction
    score_corr = adjustment.get('score_correction', [0, 0])
    if isinstance(score_corr, list) and len(score_corr) >= 2:
        home_adj = max(-0.3, min(0.3, score_corr[0] * 0.15))
        away_adj = max(-0.3, min(0.3, score_corr[1] * 0.15))
        hg = prediction.get('expected_goals_home', 1.5) + home_adj
        ag = prediction.get('expected_goals_away', 1.2) + away_adj
        hg = max(0.25, min(4.5, hg))
        ag = max(0.25, min(4.5, ag))
        adj_pred = dixon_coles_predict(hg, ag)
        prediction['home_win_prob'] = adj_pred['home_win_prob']
        prediction['draw_prob'] = adj_pred['draw_prob']
        prediction['away_win_prob'] = adj_pred['away_win_prob']
        prediction['most_likely_score'] = adj_pred['most_likely_score']
        prediction['exact_score_prob'] = adj_pred['exact_score_prob']
        prediction['under_2_5'] = adj_pred['under_2_5']
        prediction['over_2_5'] = adj_pred['over_2_5']
        prediction['btts_yes'] = adj_pred['btts_yes']
        prediction['btts_no'] = adj_pred['btts_no']
        prediction['expected_goals_home'] = adj_pred['expected_goals_home']
        prediction['expected_goals_away'] = adj_pred['expected_goals_away']
        prediction['probs'] = adj_pred['probs']
    confidence_boost = adjustment.get('confidence_boost', 0)
    if isinstance(confidence_boost, (int, float)):
        prediction['ai_confidence_boost'] = max(-0.1, min(0.1, confidence_boost))
    prediction['ai_key_factor'] = adjustment.get('key_factor', '')
    prediction['ai_ensemble_applied'] = True
    return prediction

# ═══════════════════════════════════════════════════════════════
# DETERMINE BEST BET
# ═══════════════════════════════════════════════════════════════
def determine_best_bet(prediction, home_team, away_team):
    hw = prediction['home_win_prob']
    dw = prediction['draw_prob']
    aw = prediction['away_win_prob']
    over = prediction.get('over_2_5', 50)
    btts = prediction.get('btts_yes', 50)
    top1 = prediction.get('top_scores', [{}])[0] if prediction.get('top_scores') else {}
    top1_score = top1.get('score', '')
    top1_prob = top1.get('prob', 0)
    bets = []
    if hw > 65:
        bets.append({'bet': f'{home_team} Win', 'confidence': hw, 'type': 'home_win'})
    if aw > 65:
        bets.append({'bet': f'{away_team} Win', 'confidence': aw, 'type': 'away_win'})
    if dw > 40:
        bets.append({'bet': 'Draw', 'confidence': dw, 'type': 'draw'})
    if over > 65:
        bets.append({'bet': 'Over 2.5 Goals', 'confidence': over, 'type': 'over25'})
    if btts > 60:
        bets.append({'bet': 'BTTS Yes', 'confidence': btts, 'type': 'btts'})
    if top1_prob > 18:
        bets.append({'bet': f'Score: {top1_score}', 'confidence': top1_prob, 'type': 'exact'})
    bets.sort(key=lambda x: -x['confidence'])
    if not bets:
        bets = [{'bet': 'Over 1.5 Goals', 'confidence': 70, 'type': 'over15'}]
    return {
        'primary': bets[0]['bet'],
        'primary_confidence': round(bets[0]['confidence'], 1),
        'secondary': bets[1]['bet'] if len(bets) > 1 else '',
        'all_bets': bets[:4]
    }

# ═══════════════════════════════════════════════════════════════
# ANALYZE MATCH DEEP (main function)
# ═══════════════════════════════════════════════════════════════
def analyze_match_deep(home_team, away_team, competition=None, neutral_venue=False, fixture_id=None, use_fotmob=False, use_statsbomb=False, use_clubelo=False, use_understat=False, use_whoscored=False, use_fbref=False, use_market_odds=False, use_lambda_model=False, use_forebet=False, use_direct_model=False):
    start = time.time()
    home_resolved = _resolve_team_name(home_team)
    away_resolved = _resolve_team_name(away_team)
    # WC2026: use dedicated predictor
    if competition and 'world cup' in competition.lower():
        try:
            import wc2026_predictor as wc
            return wc.analyze_match_deep(home_resolved, away_resolved, competition=competition)
        except ImportError:
            pass
    features = compute_features(home_resolved, away_resolved, neutral_venue)
    if use_fotmob and fs is not None:
        try:
            fm_home = fs.get_live_team_data_full(home_resolved)
            fm_away = fs.get_live_team_data_full(away_resolved)
            if fm_home and fm_away:
                hs = fm_home['stats']; aws = fm_away['stats']
                if hs.get('matches_played', 0) >= 3:
                    features['attack_xg_home'] = max(0.5, hs['avg_gs'])
                    features['defense_xg_home'] = max(0.5, hs['avg_gc'])
                    pts = sum(3 if c == 'W' else (1 if c == 'D' else 0) for c in hs.get('form','')[-5:])
                    features['form_points_home'] = pts
                if aws.get('matches_played', 0) >= 3:
                    features['attack_xg_away'] = max(0.5, aws['avg_gs'])
                    features['defense_xg_away'] = max(0.5, aws['avg_gc'])
                    pts = sum(3 if c == 'W' else (1 if c == 'D' else 0) for c in aws.get('form','')[-5:])
                    features['form_points_away'] = pts
            fm_h2h = fs.get_h2h_data_full(home_resolved, away_resolved, limit=6)
            if fm_h2h:
                hgs = hgc = n = 0
                for m in fm_h2h[:6]:
                    hs = m.get('home_score'); aws = m.get('away_score')
                    if hs is not None and aws is not None:
                        hgs += int(hs); hgc += int(aws); n += 1
                if n:
                    features['h2h_home_goals'] = hgs / n
                    features['h2h_away_goals'] = hgc / n
        except Exception:
            pass
    if use_statsbomb and sbs is not None:
        try:
            sb_home = sbs.get_live_team_data_full(home_resolved)
            sb_away = sbs.get_live_team_data_full(away_resolved)
            if sb_home and sb_away:
                hh = sb_home['stats']; ah = sb_away['stats']
                if hh.get('matches_played', 0) >= 5:
                    features['attack_xg_home'] = features['attack_xg_home'] * 0.75 + hh['avg_gs'] * 0.25
                    features['defense_xg_home'] = features['defense_xg_home'] * 0.75 + hh['avg_gc'] * 0.25
                if ah.get('matches_played', 0) >= 5:
                    features['attack_xg_away'] = features['attack_xg_away'] * 0.75 + ah['avg_gs'] * 0.25
                    features['defense_xg_away'] = features['defense_xg_away'] * 0.75 + ah['avg_gc'] * 0.25
        except Exception:
            pass
    if use_clubelo and ces is not None:
        try:
            eh = ces.get_elo(home_resolved)
            ea = ces.get_elo(away_resolved)
            if eh and ea:
                features['elo_home'] = eh['elo']
                features['elo_away'] = ea['elo']
        except Exception:
            pass
    if use_understat and uss is not None:
        try:
            uh = uss.get_team_ppda(home_resolved)
            ua = uss.get_team_ppda(away_resolved)
            if uh and uh.get('matches',0) >= 5:
                ppda_ratio = max(0.5, min(2.0, (uh.get('ppda',10) or 10) / max(uh.get('opp_ppda',10) or 10, 0.1)))
                features['attack_xg_home'] = features['attack_xg_home'] * 0.8 + uh.get('xg_avg',0) * 0.2
                features['defense_xg_home'] = features['defense_xg_home'] * 0.8 + uh.get('xga_avg',0) * 0.2
            if ua and ua.get('matches',0) >= 5:
                features['attack_xg_away'] = features['attack_xg_away'] * 0.8 + ua.get('xg_avg',0) * 0.2
                features['defense_xg_away'] = features['defense_xg_away'] * 0.8 + ua.get('xga_avg',0) * 0.2
            if uh and ua:
                features['ppda_home'] = uh.get('ppda',0)
                features['ppda_away'] = ua.get('ppda',0)
        except Exception:
            pass
    if use_whoscored and ws is not None:
        try:
            ws_data = ws.get_match_data(home_resolved, away_resolved)
            if ws_data and ws_data.get('score'):
                parts = ws_data['score'].split(':')
                if len(parts) == 2:
                    features['whoscored_home_goals'] = float(parts[0])
                    features['whoscored_away_goals'] = float(parts[1])
        except Exception:
            pass
    if use_fbref and fbs is not None:
        try:
            fbref_h = fbs.get_live_team_data_full(home_resolved)
            fbref_a = fbs.get_live_team_data_full(away_resolved)
            if fbref_h and fbref_h['stats'].get('matches_played',0) >= 5:
                s = fbref_h['stats']
                features['attack_xg_home'] = features['attack_xg_home'] * 0.85 + s['avg_gs'] * 0.15
                features['defense_xg_home'] = features['defense_xg_home'] * 0.85 + s['avg_gc'] * 0.15
            if fbref_a and fbref_a['stats'].get('matches_played',0) >= 5:
                s = fbref_a['stats']
                features['attack_xg_away'] = features['attack_xg_away'] * 0.85 + s['avg_gs'] * 0.15
                features['defense_xg_away'] = features['defense_xg_away'] * 0.85 + s['avg_gc'] * 0.15
        except Exception:
            pass
    base_home = (features['attack_xg_home'] * features['defense_xg_away'] / features['league_avg_xg']) * features['home_advantage']
    base_away = (features['attack_xg_away'] * features['defense_xg_home'] / features['league_avg_xg']) * (1.0 if neutral_venue else 1.0 / features['home_advantage'])
    form_mult_home = 0.85 + (features['form_points_home'] / 15.0) * 0.30
    form_mult_away = 0.85 + (features['form_points_away'] / 15.0) * 0.30
    elo_diff_home = (features['elo_home'] - features['elo_away']) / 400.0
    elo_mult_home = 1.0 + max(-0.15, min(0.15, elo_diff_home * 0.15))
    elo_diff_away = (features['elo_away'] - features['elo_home']) / 400.0
    elo_mult_away = 1.0 + max(-0.15, min(0.15, elo_diff_away * 0.15))
    injury_mult_home = 1.0 - features['injury_penalty_home']
    injury_mult_away = 1.0 - features['injury_penalty_away']
    # ── ربط lineups.injury_adjustment() مع fixture_id ──
    if not fixture_id:
        try:
            daily = get_daily_matches()
            for m in daily:
                ht = m.get('home_team', '').lower()
                at = m.get('away_team', '').lower()
                if (ht in home_resolved.lower() or home_resolved.lower() in ht) and \
                   (at in away_resolved.lower() or away_resolved.lower() in at):
                    fixture_id = m.get('fixture_id')
                    break
        except:
            pass
    if fixture_id:
        try:
            for team, side in [(home_resolved, 'home'), (away_resolved, 'away')]:
                starters = lineups.get_expected_lineup(team, fixture_id)
                if starters:
                    adj, missing = lineups.injury_adjustment(team, expected_starters=starters)
                    if missing and missing != 'none_missing':
                        with open('injury_log.txt', 'a') as f:
                            f.write(f"{datetime.now()}|{team}|{missing}|{fixture_id}\n")
                    if side == 'home':
                        injury_mult_home *= adj
                    else:
                        injury_mult_away *= adj
        except:
            pass
    features['injury_adjusted'] = {
        'home_mult': round(injury_mult_home, 4),
        'away_mult': round(injury_mult_away, 4),
        'fixture_id': fixture_id
    }
    fatigue_mult_home = 0.95 if features['days_since_last_home'] < 3 else 1.0
    fatigue_mult_away = 0.95 if features['days_since_last_away'] < 3 else 1.0
    hg = base_home * form_mult_home * elo_mult_home * injury_mult_home * fatigue_mult_home
    ag = base_away * form_mult_away * elo_mult_away * injury_mult_away * fatigue_mult_away
    hg = max(0.25, min(4.5, hg))
    ag = max(0.25, min(4.5, ag))
    # Lambda model override — ML-predicted expected goals
    if use_lambda_model:
        try:
            import lambda_predictor as lp
            lh, la = lp.predict_lambda(home_resolved, away_resolved, datetime.now().strftime('%Y-%m-%d'))
            if lh is not None and la is not None:
                hg = (hg + lh) / 2  # blend: old formula + ML
                ag = (ag + la) / 2
                features['lambda_model_applied'] = True
                features['lambda_home_ml'] = lh
                features['lambda_away_ml'] = la
        except Exception as ex:
            print(f'[Lambda model] predict_lambda failed: {ex}')
    has_agent = bool(os.environ.get('AGENTROUTER_KEY', ''))
    has_groq = bool(os.environ.get('GROQ_KEY', ''))
    league_map = {'EPL': 'EPL', 'Premier League': 'EPL', 'Premier_League': 'EPL',
                  'La Liga': 'La_Liga', 'La_Liga': 'La_Liga',
                  'Bundesliga': 'Bundesliga',
                  'Serie A': 'Serie_A', 'Serie_A': 'Serie_A',
                  'Ligue 1': 'Ligue_1', 'Ligue_1': 'Ligue_1'}
    league_key = league_map.get(competition, '') if competition else ''
    league_rho = mt.get_rho(league_key) if (league_key and mt) else None
    # Market odds fetch (before Direct model so odds features can be used)
    market_probs = None
    if use_market_odds:
        market_probs = get_market_probabilities(home_resolved, away_resolved, league_key=competition)
    odds_b365 = odds_avg = None
    if market_probs and market_probs.get('available'):
        overround = market_probs.get('overround', 1.0)
        mh = market_probs['home'] / 100.0
        md = market_probs['draw'] / 100.0
        ma = market_probs['away'] / 100.0
        odds_b365 = (overround / mh if mh > 0 else 10.0,
                     overround / md if md > 0 else 10.0,
                     overround / ma if ma > 0 else 10.0)
        odds_avg = odds_b365  # Same as avg when only one source

    # Direct Score Model ── XGBoost multi-class (25 scores) replaces Dixon-Coles
    direct_used = False
    if use_direct_model:
        try:
            import direct_predictor as dp
            direct_result = dp.predict_match(home_resolved, away_resolved, datetime.now().strftime('%Y-%m-%d'),
                                             odds_b365=odds_b365, odds_avg=odds_avg)
            if direct_result is not None:
                sp = direct_result['score_probs']
                p1x2 = direct_result['probs_1x2']
                max_g = MAX_GOALS_DC
                probs = np.zeros((max_g + 1, max_g + 1), dtype=float)
                for h in range(5):
                    for a in range(5):
                        key = f'{h}-{a}'
                        probs[h, a] = sp.get(key, 0)
                total_p = probs.sum()
                if total_p > 0:
                    probs /= total_p
                home_win = float(np.tril(probs, -1).sum())
                draw = float(np.trace(probs))
                away_win = float(np.triu(probs, 1).sum())
                idx = np.arange(max_g + 1)
                total = idx[:, None] + idx[None, :]
                prediction = {
                    'home_win_prob': home_win,
                    'draw_prob': draw,
                    'away_win_prob': away_win,
                    'most_likely_score': direct_result['predicted_score'],
                    'exact_score_prob': round(direct_result['predicted_prob'] * 100, 2),
                    'under_0_5': float(probs[total <= 0].sum()),
                    'under_1_5': float(probs[total <= 1].sum()),
                    'under_2_5': float(probs[total <= 2].sum()),
                    'under_3_5': float(probs[total <= 3].sum()),
                    'under_4_5': float(probs[total <= 4].sum()),
                    'under_5_5': float(probs[total <= 5].sum()),
                    'over_2_5': float(probs[total > 2].sum()),
                    'over_3_5': float(probs[total > 3].sum()),
                    'over_4_5': float(probs[total > 4].sum()),
                    'btts_yes': float(probs[1:, 1:].sum()),
                    'btts_no': float(probs[:1, :1].sum()) + float(probs[0, 1:].sum()) + float(probs[1:, 0].sum()),
                    'probs': probs,
                    'expected_goals_home': direct_result['expected_goals']['home'],
                    'expected_goals_away': direct_result['expected_goals']['away'],
                    'top_scores': [{'score': s, 'prob': round(p * 100, 2)} for s, p in direct_result['top_scores'][:8]],
                    'top_3': [{'score': s, 'prob': round(p * 100, 2)} for s, p in direct_result['top_scores'][:3]],
                    'asian_handicap': {
                        'ah_0': round(home_win, 4),
                        'ah_m025': round(home_win + 0.5 * draw, 4),
                        'ah_05': round(home_win, 4),
                        'ah_m075': round(home_win - 0.5 * float(probs[(idx[:, None] - idx[None, :]) == 1].sum()), 4),
                        'ah_10': round(float(probs[(idx[:, None] - idx[None, :]) >= 2].sum()) + 0.5 * (home_win - float(probs[(idx[:, None] - idx[None, :]) >= 2].sum())), 4),
                    },
                }
                prediction['btts_no'] = 1.0 - prediction['btts_yes']
                # Override hg, ag for downstream WC/venue blending
                hg = direct_result['expected_goals']['home']
                ag = direct_result['expected_goals']['away']
                direct_used = True
                features['direct_model_applied'] = True
        except Exception as ex:
            print(f'[Direct model] failed: {ex}')
    if not direct_used:
        prediction = dixon_coles_predict(hg, ag, rho=league_rho)
    _AI_CALLS = getattr(analyze_match_deep, '_ai_calls', 0)
    if (has_agent or has_groq) and _AI_CALLS < 12:
        analyze_match_deep._ai_calls = _AI_CALLS + 1
        prediction = ai_ensemble(features, prediction, home_team=home_resolved, away_team=away_resolved)
        prediction['analysis'] = {}
        prediction['analysis']['best_bet_type'] = 'ai_ensemble'
    else:
        prediction['analysis'] = {}
        prediction['analysis']['best_bet_type'] = 'model'
    # World Cup 2026 competition-specific blend (before normalization)
    comp_name = (competition or '').lower()
    comp_type = ''
    if comp_name in ('world cup', 'world_cup', 'wc', 'wc 2026', 'world cup 2026', 'fifa world cup'):
        comp_type = 'world_cup'
    if comp_type == 'world_cup':
        wc_home = get_competition_matches(home_resolved, from_date='2026-06-11')
        wc_away = get_competition_matches(away_resolved, from_date='2026-06-11')
        home_gs = features.get('attack_xg_home', 1.5)
        away_gs = features.get('attack_xg_away', 1.2)
        if wc_home.get('played', 0) >= 1 and home_gs > 0.1:
            wc_home_gs = wc_home.get('gs_avg', home_gs)
            hg = hg * 0.4 + hg * (wc_home_gs / max(home_gs, 0.1)) * 0.6
            prediction = dixon_coles_predict(hg, ag)
            prediction['analysis'] = prediction.get('analysis', {})
            prediction['analysis']['best_bet_type'] = prediction['analysis'].get('best_bet_type', 'model')
        if wc_away.get('played', 0) >= 1 and away_gs > 0.1:
            wc_away_gs = wc_away.get('gs_avg', away_gs)
            ag = ag * 0.4 + ag * (wc_away_gs / max(away_gs, 0.1)) * 0.6
            prediction = dixon_coles_predict(hg, ag)
            prediction['analysis'] = prediction.get('analysis', {})
            prediction['analysis']['best_bet_type'] = prediction['analysis'].get('best_bet_type', 'model')
        prediction['wc_home_stats'] = wc_home
        prediction['wc_away_stats'] = wc_away
    # Market odds integration (Odds API blend)
    market_probs = None
    # FD Direct Model blend (uses market odds as features, full score distribution)
    if market_probs and market_probs.get('available') and use_direct_model:
        try:
            import fd_direct_predictor as fdp
            overround = market_probs.get('overround', 1.0)
            mh = market_probs['home'] / 100.0
            md = market_probs['draw'] / 100.0
            ma = market_probs['away'] / 100.0
            # Convert market probs to B365-like odds
            b365h = overround / mh if mh > 0 else 10.0
            b365d = overround / md if md > 0 else 10.0
            b365a = overround / ma if ma > 0 else 10.0
            fd_result = fdp.predict_match(b365h, b365d, b365a)
            if fd_result and direct_used:
                fd_probs = np.zeros((MAX_GOALS_DC + 1, MAX_GOALS_DC + 1), dtype=float)
                sp = fd_result['score_probs']
                for h in range(5):
                    for a in range(5):
                        key = f'{h}-{a}'
                        fd_probs[h, a] = sp.get(key, 0)
                total_fd = fd_probs.sum()
                if total_fd > 0:
                    fd_probs /= total_fd
                # Blend: average the full probability distributions (Direct + FD)
                blend_weight = 0.35
                probs = prediction.get('probs')
                if probs is not None and probs.shape == fd_probs.shape:
                    blended_probs = probs * (1 - blend_weight) + fd_probs * blend_weight
                    blended_probs /= blended_probs.sum()  # renormalize
                    # Rebuild prediction from blended probs
                    idx = np.arange(MAX_GOALS_DC + 1)
                    total = idx[:, None] + idx[None, :]
                    home_win = float(np.tril(blended_probs, -1).sum())
                    draw = float(np.trace(blended_probs))
                    away_win = float(np.triu(blended_probs, 1).sum())
                    prediction['probs'] = blended_probs
                    prediction['home_win_prob'] = home_win
                    prediction['draw_prob'] = draw
                    prediction['away_win_prob'] = away_win
                    prediction['under_0_5'] = float(blended_probs[total <= 0].sum())
                    prediction['under_1_5'] = float(blended_probs[total <= 1].sum())
                    prediction['under_2_5'] = float(blended_probs[total <= 2].sum())
                    prediction['under_3_5'] = float(blended_probs[total <= 3].sum())
                    prediction['under_4_5'] = float(blended_probs[total <= 4].sum())
                    prediction['under_5_5'] = float(blended_probs[total <= 5].sum())
                    prediction['over_2_5'] = float(blended_probs[total > 2].sum())
                    prediction['over_3_5'] = float(blended_probs[total > 3].sum())
                    prediction['over_4_5'] = float(blended_probs[total > 4].sum())
                    prediction['btts_yes'] = float(blended_probs[1:, 1:].sum())
                    prediction['btts_no'] = 1.0 - prediction['btts_yes']
                    prediction['expected_goals_home'] = float((idx[:, None] * blended_probs).sum())
                    prediction['expected_goals_away'] = float((idx[None, :] * blended_probs).sum())
                    # Top scores from blended
                    scores_list = []
                    for h in range(5):
                        for a in range(5):
                            scores_list.append(((h, a), float(blended_probs[h, a])))
                    scores_list.sort(key=lambda x: -x[1])
                    predicted_score = scores_list[0][0]
                    prediction['most_likely_score'] = f'{predicted_score[0]}-{predicted_score[1]}'
                    prediction['exact_score_prob'] = round(scores_list[0][1] * 100, 2)
                    prediction['top_scores'] = [{'score': f'{s[0]}-{s[1]}', 'prob': round(p * 100, 2)} for s, p in scores_list[:8]]
                    prediction['top_3'] = [{'score': f'{s[0]}-{s[1]}', 'prob': round(p * 100, 2)} for s, p in scores_list[:3]]
                    prediction['fd_model_blended'] = True
        except Exception as ex:
            if 'fd_direct_predictor' in str(type(ex)) or 'fd' in str(ex).lower():
                print(f'[FD model] skip: {ex}')
    # Save pre-market true probabilities (pure model) for value bet detection
    true_h = prediction['home_win_prob']
    true_d = prediction['draw_prob']
    true_a = prediction['away_win_prob']
    MARKET_WEIGHT = 0.35
    if market_probs and market_probs.get('available'):
        mh = market_probs['home'] / 100.0
        md = market_probs['draw'] / 100.0
        ma = market_probs['away'] / 100.0
        dc_h = prediction['home_win_prob']
        dc_d = prediction['draw_prob']
        dc_a = prediction['away_win_prob']
        blended_h = dc_h * (1 - MARKET_WEIGHT) + mh * MARKET_WEIGHT
        blended_d = dc_d * (1 - MARKET_WEIGHT) + md * MARKET_WEIGHT
        blended_a = dc_a * (1 - MARKET_WEIGHT) + ma * MARKET_WEIGHT
        total_b = blended_h + blended_d + blended_a
        if total_b > 0:
            prediction['home_win_prob'] = blended_h / total_b
            prediction['draw_prob'] = blended_d / total_b
            prediction['away_win_prob'] = blended_a / total_b
        prediction['market_data_used'] = True
        prediction['market_implied_home'] = round(market_probs['fair_probs'].get('home', mh * 100), 2)
        prediction['market_implied_draw'] = round(market_probs['fair_probs'].get('draw', md * 100), 2)
        prediction['market_implied_away'] = round(market_probs['fair_probs'].get('away', ma * 100), 2)
        prediction['market_overround'] = market_probs.get('overround', 0)
        prediction['market_bookmaker_count'] = market_probs.get('bookmaker_count', 0)
        # Value bet detection: compare OUR model (pre-blend) vs MARKET implied
        if use_market_odds and oas is not None:
            try:
                true_probs = {
                    'home_prob': round(true_h * 100, 2),
                    'draw_prob': round(true_d * 100, 2),
                    'away_prob': round(true_a * 100, 2),
                }
                value_bets = oas.find_value_bets(
                    true_probs,
                    {'fair_probs': market_probs['fair_probs']}
                )
                if value_bets:
                    prediction['value_bets'] = value_bets
            except Exception:
                pass
    else:
        prediction['market_data_used'] = False
    # Forebet blend
    FOREBET_WEIGHT = 0.25
    if use_forebet and forebets is not None:
        try:
            fb_pred = forebets.find_prediction_for_match(home_resolved, away_resolved)
            if fb_pred and fb_pred.get('prob_h') is not None:
                fb_h = fb_pred['prob_h']
                fb_d = fb_pred['prob_d']
                fb_a = fb_pred['prob_a']
                dc_h = prediction['home_win_prob']
                dc_d = prediction['draw_prob']
                dc_a = prediction['away_win_prob']
                blended_h = dc_h * (1 - FOREBET_WEIGHT) + fb_h * FOREBET_WEIGHT
                blended_d = dc_d * (1 - FOREBET_WEIGHT) + fb_d * FOREBET_WEIGHT
                blended_a = dc_a * (1 - FOREBET_WEIGHT) + fb_a * FOREBET_WEIGHT
                total_b = blended_h + blended_d + blended_a
                if total_b > 0:
                    prediction['home_win_prob'] = blended_h / total_b
                    prediction['draw_prob'] = blended_d / total_b
                    prediction['away_win_prob'] = blended_a / total_b
                prediction['forebet_data_used'] = True
                prediction['forebet_pred'] = fb_pred['forebet_pred']
                prediction['forebet_correct_score'] = fb_pred['correct_score']
                prediction['forebet_avg_goals'] = fb_pred['avg_goals']
        except Exception:
            pass
    # Venue factor
    venue_result = venue_module.venue_factor(venue_name=features.get('venue_name'), home_team=home_resolved, away_team=away_resolved)
    if venue_result['applied']:
        hg *= venue_result['goals_multiplier']
        ag *= venue_result['goals_multiplier']
        prediction = dixon_coles_predict(hg, ag)
        prediction['analysis'] = prediction.get('analysis', {})
        prediction['analysis']['best_bet_type'] = prediction['analysis'].get('best_bet_type', 'model')
        prediction['venue_applied'] = venue_result['venue_name']
        prediction['venue_altitude'] = venue_result.get('is_high_altitude', False)
    # Normalize probabilities to percentages
    total_prob = prediction['home_win_prob'] + prediction['draw_prob'] + prediction['away_win_prob']
    if total_prob > 0:
        hw = round(prediction['home_win_prob'] / total_prob * 100, 2)
        dw = round(prediction['draw_prob'] / total_prob * 100, 2)
        aw = round(prediction['away_win_prob'] / total_prob * 100, 2)
    # Isotonic calibration (Dixon-Coles improved – uses _CALIBRATORS)
    try:
        hw, dw, aw = _apply_calibration(hw, dw, aw)
    except Exception:
        pass
    prediction['home_win_prob'] = hw
    prediction['draw_prob'] = dw
    prediction['away_win_prob'] = aw
    under = prediction['under_2_5']
    over = prediction['over_2_5']
    prediction['under_2_5'] = round(under * 100, 2)
    prediction['over_2_5'] = round(over * 100, 2)
    prediction['btts_yes'] = round(prediction['btts_yes'] * 100, 2)
    prediction['btts_no'] = round(prediction['btts_no'] * 100, 2)
    # Top scores from Dixon-Coles corrected probs matrix
    probs_matrix = prediction['probs']
    scores = [(i, j) for i in range(probs_matrix.shape[0]) for j in range(probs_matrix.shape[1])]
    sorted_scores = sorted(scores, key=lambda x: -float(probs_matrix[x[0]][x[1]]))
    sorted_probs = [(s, round(float(probs_matrix[s[0]][s[1]]) * 100, 2)) for s in sorted_scores[:8]]
    sorted_probs.sort(key=lambda x: -x[1])
    prediction['top_scores'] = [
        {'score': f"{s[0]}-{s[1]}", 'prob': p,
         'rank': idx + 1,
         'type': ('home_win' if s[0] > s[1] else 'draw' if s[0] == s[1] else 'away_win')}
        for idx, (s, p) in enumerate(sorted_probs[:8])
    ]
    prediction['top_3'] = prediction['top_scores'][:3]
    if prediction['top_scores']:
        prediction['most_likely_score'] = prediction['top_scores'][0]['score']
        prediction['exact_score_prob'] = prediction['top_scores'][0]['prob']
    # H2H
    h2h = get_head_to_head(home_resolved, away_resolved)
    if h2h['total_matches'] >= 3:
        h2h_home_wins_pct = (h2h['home_wins'] / h2h['total_matches']) * 100
        h2h_away_wins_pct = (h2h['away_wins'] / h2h['total_matches']) * 100
        h2h_draws_pct = (h2h['draws'] / h2h['total_matches']) * 100
    else:
        h2h_home_wins_pct = h2h_away_wins_pct = h2h_draws_pct = 33.33
    prediction['h2h'] = {
        'matches_played': h2h['total_matches'],
        'home_wins': h2h['home_wins'],
        'away_wins': h2h['away_wins'],
        'draws': h2h['draws'],
        'home_goals': h2h['home_goals'],
        'away_goals': h2h['away_goals'],
        'home_wins_pct': round(h2h_home_wins_pct, 1),
        'away_wins_pct': round(h2h_away_wins_pct, 1),
        'draws_pct': round(h2h_draws_pct, 1),
        'last_meetings': h2h['last_meetings']
    }
    # Kelly criterion
    for outcome_key, prob_key in [('home_win', 'home_win_prob'), ('draw', 'draw_prob'), ('away_win', 'away_win_prob')]:
        pct = prediction.get(prob_key, 33.33)
        dec_odds = 1.0 / (pct / 100.0) if pct > 0 else 0
        prediction[f'kelly_{outcome_key}'] = kelly_criterion(pct, round(dec_odds, 2))
    # Analysis block
    home_form_rating = int(max(0, min(100, (features['form_points_home'] / 15.0) * 100)))
    away_form_rating = int(max(0, min(100, (features['form_points_away'] / 15.0) * 100)))
    confidence = 'HIGH'
    recommendation = f"Strong recommendation: {home_resolved} win"
    if prediction['home_win_prob'] > 55:
        confidence = 'HIGH'
        recommendation = f"Strong recommendation: {home_resolved} win"
    elif prediction['home_win_prob'] > 45:
        confidence = 'MEDIUM'
        recommendation = f"Moderate recommendation: {home_resolved} win or draw"
    elif prediction['away_win_prob'] > 55:
        confidence = 'HIGH'
        recommendation = f"Strong recommendation: {away_resolved} win"
    elif prediction['away_win_prob'] > 45:
        confidence = 'MEDIUM'
        recommendation = f"Moderate recommendation: {away_resolved} win or draw"
    elif prediction['draw_prob'] > 40:
        confidence = 'MEDIUM'
        recommendation = "Recommendation: Draw"
    else:
        confidence = 'LOW'
        recommendation = "Uncertain match, avoid heavy betting"
    key_factors = []
    if features['injury_penalty_home'] > 0.05:
        key_factors.append(f"{home_resolved} have injuries affecting lineup")
    if features['injury_penalty_away'] > 0.05:
        key_factors.append(f"{away_resolved} have injuries affecting lineup")
    if features['form_points_home'] > 10:
        key_factors.append(f"{home_resolved} in excellent form")
    elif features['form_points_home'] < 5:
        key_factors.append(f"{home_resolved} in poor form")
    if features['form_points_away'] > 10:
        key_factors.append(f"{away_resolved} in excellent form")
    elif features['form_points_away'] < 5:
        key_factors.append(f"{away_resolved} in poor form")
    if abs(features['elo_home'] - features['elo_away']) > 100:
        stronger = home_resolved if features['elo_home'] > features['elo_away'] else away_resolved
        key_factors.append(f"{stronger} significantly higher rated")
    if not key_factors:
        key_factors.append("Evenly matched teams")
    best_bet_info = determine_best_bet(prediction, home_resolved, away_resolved)
    prediction['best_bet_info'] = best_bet_info
    prediction['analysis'] = {
        'home_form_rating': home_form_rating,
        'away_form_rating': away_form_rating,
        'confidence': confidence,
        'recommendation': recommendation,
        'best_bet': best_bet_info['primary'],
        'best_bet_type': prediction['analysis'].get('best_bet_type', 'model'),
        'analysis_time': round(time.time() - start, 2),
        'home_elo': features['elo_home'],
        'away_elo': features['elo_away'],
        'home_stats': {
            'attack': round(features['attack_xg_home'], 2),
            'defense': round(features['defense_xg_home'], 2),
        },
        'away_stats': {
            'attack': round(features['attack_xg_away'], 2),
            'defense': round(features['defense_xg_away'], 2),
        },
        'data_source': features.get('source', 'database'),
        'key_factors': key_factors,
    }
    if best_bet_info.get('all_bets'):
        prediction['analysis']['all_bets'] = best_bet_info['all_bets']
    # Template compatibility fields
    prediction['home_trend'] = 'stable'
    if home_form_rating >= 70:
        prediction['home_trend'] = 'ascending'
    elif home_form_rating <= 30:
        prediction['home_trend'] = 'declining'
    prediction['away_trend'] = 'stable'
    if away_form_rating >= 70:
        prediction['away_trend'] = 'ascending'
    elif away_form_rating <= 30:
        prediction['away_trend'] = 'declining'
    prediction['friendly_warning'] = (comp_type == 'friendly')
    prediction['competition_type'] = competition or 'Unknown'
    try:
        extra = get_match_extra(home_resolved, away_resolved)
        prediction['match_extra'] = extra if extra else {}
    except:
        prediction['match_extra'] = {}
    prediction['analysis']['sources'] = {
        'stats_home': features.get('source_home', 'database'),
        'stats_away': features.get('source_away', 'database'),
        'h2h': 'api' if h2h.get('source') else 'none'
    }
    prediction['expected_goals_home'] = round(hg, 2)
    prediction['expected_goals_away'] = round(ag, 2)
    prediction['lambda_home'] = round(hg, 4)
    prediction['lambda_away'] = round(ag, 4)
    prediction['lambda_model_applied'] = features.get('lambda_model_applied', False)
    # Log to evaluation database
    try:
        evaluation.log_prediction(home_resolved, away_resolved, prediction)
    except Exception as e:
        print(f"[DB] log_prediction failed for {home_resolved} vs {away_resolved}: {e}")
    return prediction

# ═══════════════════════════════════════════════════════════════
# EVALUATION DATABASE (compatibility with app.py)
# ═══════════════════════════════════════════════════════════════
_EVAL_DB_PATH = None

def _get_eval_db():
    global _EVAL_DB_PATH
    if _EVAL_DB_PATH is None:
        _EVAL_DB_PATH = os.path.join(os.path.dirname(__file__) or '.', 'evaluation.db')
    return _EVAL_DB_PATH

def init_evaluation_db():
    try:
        db = _get_eval_db()
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_date TEXT,
                home_team TEXT,
                away_team TEXT,
                predicted_home INTEGER,
                predicted_away INTEGER,
                actual_home INTEGER,
                actual_away INTEGER,
                confidence REAL,
                evaluated INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    except:
        pass

def save_prediction_for_eval(match_date, home_team, away_team, pred_home, pred_away, confidence):
    try:
        db = _get_eval_db()
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO predictions (match_date, home_team, away_team, predicted_home, predicted_away, confidence) VALUES (?,?,?,?,?,?)",
            (match_date or datetime.now().strftime('%Y-%m-%d'), home_team, away_team, int(pred_home or 0), int(pred_away or 0), float(confidence or 0))
        )
        conn.commit()
        conn.close()
    except:
        pass

# ═══════════════════════════════════════════════════════════════
# GET DAILY MATCHES (compatibility with app.py)
# ═══════════════════════════════════════════════════════════════
def get_daily_matches(date=None):
    matches = []
    if date is None:
        date = datetime.now().strftime('%Y-%m-%d')
    competitions = [
        {'id': '2001', 'name': 'UEFA Champions League'},
        {'id': '2021', 'name': 'Premier League'},
        {'id': '2014', 'name': 'La Liga'},
        {'id': '2015', 'name': 'Ligue 1'},
        {'id': '2002', 'name': 'Bundesliga'},
        {'id': '2019', 'name': 'Serie A'},
        {'id': '2013', 'name': 'World Cup'},
        {'id': '2000', 'name': 'FIFA World Cup'},
        {'id': '2003', 'name': 'Eredivisie'},
        {'id': '2018', 'name': 'European Championship'},
        {'id': '2016', 'name': 'English Championship'},
        {'id': '2024', 'name': 'Primeira Liga'},
        {'id': '2006', 'name': 'Scottish Premiership'},
        {'id': '2004', 'name': 'UEFA Europa League'},
        {'id': '2008', 'name': 'UEFA Europa Conference'},
        {'id': '2022', 'name': 'Super Lig'},
        {'id': '2017', 'name': 'Serie B'},
        {'id': '2010', 'name': 'Brasileirão'},
        {'id': '2009', 'name': 'Jupiler Pro League'},
        {'id': '2007', 'name': 'MLS'},
        {'id': '2011', 'name': 'Liga MX'},
    ]
    if os.environ.get('FOOTBALL_DATA_API_KEY', ''):
        for comp in competitions:
            try:
                url = f"{FOOTBALL_DATA_BASE}/competitions/{comp['id']}/matches?dateFrom={date}&dateTo={date}"
                data = _cached_or_fetch(url, headers_football_data, 15)
                if data and 'matches' in data:
                    for m in data['matches']:
                        if m['status'] in ['SCHEDULED', 'TIMED']:
                            home = m['homeTeam'].get('name', '')
                            away = m['awayTeam'].get('name', '')
                            if home and away:
                                matches.append({
                                    'fixture_id': m.get('id'),
                                    'home_team': home,
                                    'away_team': away,
                                    'competition': comp['name'],
                                    'date': m.get('utcDate', date)[:10],
                                    'time': m.get('utcDate', ''),
                                    'status': m.get('status', ''),
                                    'home_crest': m['homeTeam'].get('crestUrl', ''),
                                    'away_crest': m['awayTeam'].get('crestUrl', '')
                                })
            except:
                pass
    # Primary: SofaScore via curl_cffi (unlimited, no API key)
    sofa_cache_key = f'sofa_events_{date}'
    sofa_data = _CACHE.get(sofa_cache_key) if sofa_cache_key in _CACHE else None
    if sofa_data is None:
        try:
            from curl_cffi import requests as curl_requests
            sofa_headers = {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 14; Pixel 9 Pro) AppleWebKit/537.36 Chrome/120.0.6099.230 Mobile Safari/537.36',
                'Accept': 'application/json',
                'Origin': 'https://www.sofascore.com',
                'Referer': 'https://www.sofascore.com/',
                'x-requested-with': '721637',
            }
            time.sleep(0.35)
            r = curl_requests.get(
                f'https://www.sofascore.com/api/v1/sport/football/scheduled-events/{date}',
                headers=sofa_headers, impersonate='chrome120', timeout=15)
            if r.status_code == 200:
                sofa_data = r.json()
                _CACHE[sofa_cache_key] = sofa_data
                _CACHE_TIME[sofa_cache_key] = time.time()
        except Exception:
            pass
    if sofa_data and 'events' in sofa_data:
        seen_ids = set()
        for e in sofa_data['events']:
            eid = e.get('id')
            if eid in seen_ids:
                continue
            seen_ids.add(eid)
            home_team = (e.get('homeTeam') or {}).get('name', '')
            away_team = (e.get('awayTeam') or {}).get('name', '')
            tournament = e.get('tournament', {})
            comp_name = tournament.get('name', 'Unknown')
            timestamp = e.get('startTimestamp', 0)
            match_time = datetime.fromtimestamp(timestamp).strftime('%H:%M') if timestamp else ''
            status = e.get('status', {}).get('type', 'unknown')
            if home_team and away_team:
                matches.append({
                    'fixture_id': eid,
                    'home_team': home_team,
                    'away_team': away_team,
                    'competition': comp_name,
                    'date': date,
                    'time': match_time,
                    'status': status,
                    'home_crest': '',
                    'away_crest': '',
                    'source': 'sofascore',
                })
    # Fallback: API-Football (if key is valid)
    if os.environ.get('API_SPORT_KEY', ''):
        try:
            url = f"{API_FOOTBALL_BASE}/fixtures?date={date}"
            rdata = _cached_or_fetch(url, headers_api_football, 15)
            if rdata and 'response' in rdata:
                existing_home_away = {(m['home_team'].lower(), m['away_team'].lower()) for m in matches}
                for m in rdata['response']:
                    fixture = m.get('fixture', {})
                    teams = m.get('teams', {})
                    league = m.get('league', {})
                    home = (teams.get('home') or {}).get('name', '')
                    away = (teams.get('away') or {}).get('name', '')
                    key = (home.lower(), away.lower())
                    if home and away and key not in existing_home_away:
                        existing_home_away.add(key)
                        matches.append({
                            'fixture_id': fixture.get('id'),
                            'home_team': home,
                            'away_team': away,
                            'competition': league.get('name', 'Unknown'),
                            'date': fixture.get('date', date)[:10],
                            'time': fixture.get('date', ''),
                            'status': (fixture.get('status') or {}).get('short', ''),
                            'home_crest': (teams.get('home') or {}).get('logo', ''),
                            'away_crest': (teams.get('away') or {}).get('logo', ''),
                            'source': 'api_football',
                        })
        except:
            pass
    return matches

# ═══════════════════════════════════════════════════════════════
# RATE MATCHES (compatibility with app.py)
# ═══════════════════════════════════════════════════════════════
def rate_matches(matches):
    rated = []
    for match in matches:
        try:
            pred = analyze_match_deep(match['home_team'], match['away_team'], match.get('competition'), fixture_id=match.get('fixture_id'), use_understat=True, use_whoscored=True, use_fbref=True, use_market_odds=True, use_lambda_model=True, use_forebet=True, use_direct_model=True)
            score = 0
            confidence_boost = {'HIGH': 30, 'MEDIUM': 15, 'LOW': 0}
            score += confidence_boost.get(pred['analysis']['confidence'], 0)
            if pred['home_win_prob'] > 60 or pred['away_win_prob'] > 60:
                score += 25
            if pred['under_2_5'] > 65 or pred['over_2_5'] > 65:
                score += 15
            if pred['btts_yes'] > 60:
                score += 10
            if pred['analysis']['home_form_rating'] > 60 or pred['analysis']['away_form_rating'] > 60:
                score += 10
            score += abs(pred['home_win_prob'] - pred['away_win_prob']) / 5
            score = min(100, score)
            rated.append({
                'match': match,
                'prediction': pred,
                'rating_score': round(score, 1),
                'predicted_score': pred['most_likely_score'],
                'confidence': pred['analysis']['confidence'],
                'home_win_prob': pred['home_win_prob'],
                'away_win_prob': pred['away_win_prob']
            })
        except Exception as e:
            print(f"[SKIP] {match.get('home_team','?')} vs {match.get('away_team','?')}: {e}")
    rated.sort(key=lambda x: x['rating_score'], reverse=True)
    return rated[:20]

# ═══════════════════════════════════════════════════════════════
# HELPER: find_team (compatibility)
# ═══════════════════════════════════════════════════════════════
def find_team(name):
    return _resolve_team_name(name)

# ═══════════════════════════════════════════════════════════════
# HELPER: get_team_stats (compatibility)
# ═══════════════════════════════════════════════════════════════
def get_team_stats(team_name):
    data = get_live_team_data(team_name)
    default = TEAM_DB.get(team_name, (1600, 1.3, 1.4, 0.50))
    return {
        'goals_scored_avg': data['attack_xg'],
        'goals_conceded_avg': data['defense_xg'],
        'form': data['form_points'] / 15.0 if data['form_points'] > 0 else 0.5,
        'elo': data['elo'],
        'attack_strength': max(0.3, min(3.0, data['attack_xg'] / 1.5)),
        'defense_strength': max(0.3, min(3.0, 1.5 / max(data['defense_xg'], 0.3))),
        'source': data['source'],
    }

# ═══════════════════════════════════════════════════════════════
# HELPER: evaluate_predictions (compatibility)
# ═══════════════════════════════════════════════════════════════
def evaluate_predictions():
    try:
        db = _get_eval_db()
        conn = sqlite3.connect(db)
        cur = conn.cursor()
        cur.execute("SELECT id, home_team, away_team, predicted_home, predicted_away, match_date FROM predictions WHERE evaluated=0 AND actual_home IS NOT NULL")
        rows = cur.fetchall()
        total, correct_exact, correct_winner = 0, 0, 0
        for row in rows:
            pid, ht, at, ph, pa, md = row
            actual = (None, None)
            if os.environ.get('BSD_API_KEY', ''):
                try:
                    name_encoded = requests.utils.quote(ht)
                    r = _cached_or_fetch(f"{BSD_API_BASE}/teams/?name={name_encoded}", headers_bsd, 1440)
                    if r:
                        results = r.get('results') if isinstance(r, dict) else (r if isinstance(r, list) else [])
                        if results:
                            tid = results[0].get('id')
                            if tid:
                                ev_url = f"{BSD_API_BASE}/events/?team_id={tid}&status=finished&limit=5"
                                ev_data = _cached_or_fetch(ev_url, headers_bsd, 60)
                                if ev_data:
                                    evr = ev_data.get('results') if isinstance(ev_data, dict) else (ev_data if isinstance(ev_data, list) else [])
                                    for ev in evr[:5]:
                                        ed = ev.get('event_date', '')[:10]
                                        if ed == md and ev.get('status') == 'finished':
                                            hs = ev.get('home_score')
                                            ac = ev.get('away_score')
                                            if hs is not None and ac is not None:
                                                if ev.get('home_team', '').lower() == ht.lower():
                                                    actual = (hs, ac)
                                                else:
                                                    actual = (ac, hs)
                                            break
                except:
                    pass
            ah, aa = actual
            if ah is not None and aa is not None:
                cur.execute("UPDATE predictions SET actual_home=?, actual_away=?, evaluated=1 WHERE id=?", (ah, aa, pid))
                total += 1
                if ph == ah and pa == aa:
                    correct_exact += 1
                if (ph > pa and ah > aa) or (ph < pa and ah < aa) or (ph == pa and ah == aa):
                    correct_winner += 1
                conn.commit()
        conn.close()
        if total > 0:
            return {
                'total_evaluated': total,
                'exact_score_accuracy': round(correct_exact / total * 100, 1),
                'winner_accuracy': round(correct_winner / total * 100, 1),
                'correct_exact': correct_exact,
                'correct_winner': correct_winner
            }
    except:
        pass
    return None

# ═══════════════════════════════════════════════════════════════
# WC 2026 VENUE DATABASE
# ═══════════════════════════════════════════════════════════════
WC2026_VENUES = {
    'MetLife Stadium': 8, "Levi's Stadium": 16, 'AT&T Stadium': 186,
    'SoFi Stadium': 34, 'Arrowhead Stadium': 327, 'NRG Stadium': 15,
    'Hard Rock Stadium': 2, 'Lincoln Financial Field': 9,
    'Gillette Stadium': 32, 'Lumen Field': 21, 'BC Place': 4,
    'BMO Field': 76, 'Estadio Azteca': 2240, 'Estadio Akron': 1562,
    'Estadio BBVA': 538, 'Rose Bowl': 270,
    'Mexico City': 2240, 'Guadalajara': 1562, 'Monterrey': 538,
    'Los Angeles': 89, 'Dallas': 186, 'Miami': 2,
    'New York': 8, 'Kansas City': 327, 'Seattle': 21,
    'Vancouver': 4, 'Toronto': 76, 'Houston': 15,
    'San Francisco': 16, 'Boston': 9, 'Philadelphia': 9,
}

# ═══════════════════════════════════════════════════════════════
# HELPER: get_match_extra (compatibility)
# ═══════════════════════════════════════════════════════════════
def get_match_extra(team1, team2):
    if not os.environ.get('BSD_API_KEY', ''):
        return {}
    try:
        ids = {}
        for team in [team1, team2]:
            name_encoded = requests.utils.quote(team)
            d = _cached_or_fetch(f"{BSD_API_BASE}/teams/?name={name_encoded}", headers_bsd, 1440)
            if d:
                results = d.get('results') if isinstance(d, dict) else (d if isinstance(d, list) else [])
                if results:
                    ids[team] = results[0].get('id')
        if not ids.get(team1) or not ids.get(team2):
            return {}
        url = f"{BSD_API_BASE}/events/?team_id={ids[team1]}&status=finished&limit=3"
        data = _cached_or_fetch(url, headers_bsd, 60)
        if not data:
            return {}
        evr = data.get('results') if isinstance(data, dict) else (data if isinstance(data, list) else [])
        for ev in evr:
            opp_id = ev.get('away_team_id') if ev.get('home_team_id') == ids[team1] else ev.get('home_team_id')
            if opp_id == ids[team2]:
                eid = ev.get('id')
                if eid:
                    detail = _cached_or_fetch(f"{BSD_API_BASE}/events/{eid}/", headers_bsd, 60)
                    if not detail:
                        continue
                    venue = {}
                    altitude = 0
                    if detail.get('venue_id'):
                        v = _cached_or_fetch(f"{BSD_API_BASE}/venues/{detail['venue_id']}/", headers_bsd, 1440)
                        if v:
                            venue = {'name': v.get('name'), 'city': v.get('city'), 'capacity': v.get('capacity')}
                            altitude = v.get('altitude', 0) or 0
                    if altitude == 0:
                        vname = (venue.get('name') or '').lower()
                        vcity = (venue.get('city') or '').lower()
                        for wc_name, wc_alt in WC2026_VENUES.items():
                            if wc_name.lower() in vname or wc_name.lower() in vcity:
                                altitude = wc_alt
                                venue['altitude_source'] = 'wc2026_db'
                                break
                    venue['altitude'] = altitude
                    lineups_data = _cached_or_fetch(f"{BSD_API_BASE}/events/{eid}/lineups/", headers_bsd, 60)
                    lineups = {}
                    if lineups_data:
                        if isinstance(lineups_data, dict):
                            for side in ['home', 'away']:
                                lineup = lineups_data.get(side, lineups_data.get(f'{side}_lineup', {}))
                                if isinstance(lineup, dict):
                                    lineups[side] = {
                                        'formation': lineup.get('formation', ''),
                                        'players': [p.get('name') for p in (lineup.get('players', []) or [])[:11] if isinstance(p, dict)]
                                    }
                        elif isinstance(lineups_data, list):
                            for lu in lineups_data[:2]:
                                side = 'home' if str(lu.get('team_id')) == str(ids[team1]) else 'away'
                                lineups[side] = {
                                    'formation': lu.get('formation', ''),
                                    'players': [p.get('player_name', '') for p in (lu.get('players', []) or [])[:11] if isinstance(p, dict)]
                                }
                    weather = {}
                    if detail.get('weather'):
                        weather = {
                            'code': detail['weather'].get('code'),
                            'description': detail['weather'].get('description'),
                            'temperature_c': detail['weather'].get('temperature_c'),
                            'wind_speed': detail['weather'].get('wind_speed')
                        }
                    return {
                        'venue': venue,
                        'lineups': lineups,
                        'weather': weather,
                        'pitch_condition': detail.get('pitch_condition'),
                        'attendance': detail.get('attendance'),
                        'is_neutral_ground': detail.get('is_neutral_ground'),
                        'source': 'bsd'
                    }
    except:
        pass
    return {}
