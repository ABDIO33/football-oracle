import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'football.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create teams table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            short_name TEXT,
            tla TEXT,
            crest_url TEXT
        )
    ''')

    # Create matches table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY,
            competition_id INTEGER,
            season TEXT,
            utc_date TEXT,
            status TEXT,
            matchday INTEGER,
            home_team_id INTEGER,
            away_team_id INTEGER,
            home_score INTEGER,
            away_score INTEGER,
            winner TEXT,
            FOREIGN KEY (home_team_id) REFERENCES teams (id),
            FOREIGN KEY (away_team_id) REFERENCES teams (id)
        )
    ''')

    # Create elo_ratings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS elo_ratings (
            team_id INTEGER PRIMARY KEY,
            rating REAL NOT NULL,
            last_updated TEXT,
            FOREIGN KEY (team_id) REFERENCES teams (id)
        )
    ''')

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully.")
