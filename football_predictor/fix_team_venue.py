"""
fix_team_venue.py — Fix incorrect team_venue coordinates caused by substring matching
"""
import sys, os, sqlite3

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

FIXES = {
    # Team name pattern -> (lat, lon, venue_name, city)
    'Angers': (47.47, -0.55, 'Stade Raymond Kopa', 'Angers'),
    'Angers SCO': (47.47, -0.55, 'Stade Raymond Kopa', 'Angers'),
    'Cove Rangers': (57.15, -2.08, 'Balmoral Stadium', 'Aberdeen'),
    'Carrick Rangers': (54.72, -5.87, 'Loughshore Hotel Arena', 'Carrickfergus'),
    'Berwick Rangers': (55.77, -2.01, 'Shielfield Park', 'Berwick-upon-Tweed'),
    'Rangers de Talca': (-35.43, -71.67, 'Estadio Fiscal de Talca', 'Talca'),
    'Enugu Rangers': (6.44, 7.49, 'Nnamdi Azikiwe Stadium', 'Enugu'),
    'Queens Park Rangers': (51.51, -0.23, 'Loftus Road', 'London'),
    'Rangers': (55.85, -4.31, 'Ibrox Stadium', 'Glasgow'),
    'Almirante Brown': (-34.67, -58.79, 'Estadio Fragata Presidente Sarmiento', 'Isidro Casanova'),
    'Arsenal de Sarandí': (-34.68, -58.34, 'Estadio Julio H. Grondona', 'Sarandí'),
    'Arsenal Dzerzhinsk': (53.68, 27.13, 'City Stadium', 'Dzerzhinsk'),
    'Mirandés': (41.68, -1.02, 'Estadio Municipal de Anduva', 'Miranda de Ebro'),
    'Barcelona SC': (-2.19, -79.88, 'Estadio Monumental Banco Pichincha', 'Guayaquil'),
    'Barcelona B': (41.38, 2.12, 'Estadio Johan Cruyff', 'Barcelona'),
    'Sporting CP': (38.76, -9.16, 'Estádio José Alvalade', 'Lisbon'),
    'Sporting Kansas City': (39.12, -94.82, 'Children\'s Mercy Park', 'Kansas City'),
    'Sporting Gijón': (43.53, -5.64, 'El Molinón', 'Gijón'),
    'Sporting Cristal': (-12.07, -77.03, 'Estadio Alberto Gallardo', 'Lima'),
    'Sporting Charleroi': (50.41, 4.44, 'Stade du Pays de Charleroi', 'Charleroi'),
}

def fix_coordinates():
    conn = sqlite3.connect(DB)
    fixed = 0
    for pattern, (lat, lon, venue, city) in FIXES.items():
        cur = conn.execute(
            "UPDATE team_venue SET lat=?, lon=?, venue_name=?, city=? WHERE team_name LIKE ?",
            (lat, lon, venue, city, f'%{pattern}%')
        )
        if cur.rowcount > 0:
            print(f'  Fixed {pattern}: {cur.rowcount} row(s) -> ({lat}, {lon}) {venue}')
            fixed += cur.rowcount
    conn.commit()
    conn.close()
    print(f'\nFixed {fixed} team_venue rows total')

if __name__ == '__main__':
    print('Fixing team_venue coordinate mappings...')
    fix_coordinates()
