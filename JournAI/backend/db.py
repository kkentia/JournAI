from datetime import datetime
import sqlite3

def init_db():
    conn =  sqlite3.connect("./databases/journai.db", check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def close_db(db):
    db.close()

def create_tables(db):

    db.execute("""
    CREATE TABLE IF NOT EXISTS User (
        "id" INTEGER PRIMARY KEY CHECK (id = 1),
        "name"	TEXT,
        "age"	INTEGER NOT NULL,
        "gender" TEXT NOT NULL
    );
    """)

    db.execute("""

        CREATE TABLE IF NOT EXISTS Sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT ,
            mood_avg REAL CHECK(mood_avg BETWEEN 1 AND 10),
            date TEXT NOT NULL UNIQUE,  -- "YYYY-MM-DD"
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS Conversations (
            entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,  -- NEW FK to Sessions
            title TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES Sessions(id) ON DELETE CASCADE
        );
    """)
    
    db.execute("""
        CREATE TABLE IF NOT EXISTS Messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id INTEGER NOT NULL,
            sender TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (entry_id) REFERENCES Conversations(entry_id) ON DELETE CASCADE
        );
    """)

    db.execute("""
    CREATE TABLE IF NOT EXISTS Metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER,
        entry_id INTEGER,
        metric_type TEXT NOT NULL,                  -- 'activity' | 'quiz'
        activity_id INTEGER,
        description TEXT NOT NULL,                  
        comment TEXT,
        rating INTEGER CHECK(rating BETWEEN 1 AND 10),
        source TEXT NOT NULL DEFAULT 'user',        
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (entry_id) REFERENCES Conversations(entry_id) ON DELETE CASCADE,
        FOREIGN KEY (activity_id) REFERENCES Activities(id),
        FOREIGN KEY (session_id) REFERENCES Sessions(id)
    );
    """)


    db.execute("""
        CREATE TABLE IF NOT EXISTS Activities (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT UNIQUE NOT NULL,
            alias_of  INTEGER REFERENCES Activities(id) ON DELETE CASCADE
        );
    """)


    db.execute("""
        CREATE TABLE IF NOT EXISTS Notes (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        content TEXT
         );
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS analysis_results (
            id INTEGER PRIMARY KEY,
            session_id INTEGER,
            entry_id INTEGER UNIQUE,
            valence REAL,
            arousal REAL,
            primary_emotion TEXT,
            secondary_emotion TEXT,
            activity_tags TEXT,
            timestamp TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (entry_id) REFERENCES Conversations(entry_id),
            FOREIGN KEY (session_id) REFERENCES Sessions(id)
        );
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS plutchik_events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id        INTEGER,
            session_id      INTEGER NOT NULL,
            source          TEXT CHECK (source IN ('ai','user')) NOT NULL,
            primary_emotion TEXT NOT NULL CHECK (primary_emotion IN ('joy','trust','fear','surprise','sadness','disgust','anger','anticipation')),
            level           INTEGER NOT NULL CHECK (level IN (1,2,3)),
            intensity       REAL NOT NULL CHECK (intensity >= 0.0 AND intensity <= 1.0),
            sub_label       TEXT NOT NULL,
            confidence      REAL,
            notes           TEXT,
            timestamp       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now','localtime')),
            UNIQUE(entry_id, source, primary_emotion) ON CONFLICT REPLACE,
            FOREIGN KEY (entry_id)   REFERENCES Conversations(entry_id) ON DELETE CASCADE,
            FOREIGN KEY (session_id) REFERENCES Sessions(id)
        );
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS plutchik_dyads (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id     INTEGER,                   
            session_id   INTEGER NOT NULL,
            source       TEXT CHECK (source IN ('ai','user')) NOT NULL,
            event_a_id   INTEGER NOT NULL,             
            event_b_id   INTEGER NOT NULL,              
            dyad_label   TEXT NOT NULL,                 
            weight       REAL NOT NULL CHECK (weight >= 0.0 AND weight <= 1.0),
            confidence   REAL,
            timestamp    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now','localtime')),   
            UNIQUE(entry_id, source, event_a_id, event_b_id) ON CONFLICT REPLACE,
            FOREIGN KEY (entry_id)   REFERENCES Conversations(entry_id) ON DELETE CASCADE,
            FOREIGN KEY (session_id) REFERENCES Sessions(id),
            FOREIGN KEY (event_a_id) REFERENCES plutchik_events(id) ON DELETE CASCADE,
            FOREIGN KEY (event_b_id) REFERENCES plutchik_events(id) ON DELETE CASCADE

        );
    """)


    db.executescript("""
        CREATE TABLE IF NOT EXISTS themeriver (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id INTEGER NOT NULL,
            session_id INTEGER NOT NULL,
            emotion TEXT NOT NULL,
            reasons TEXT NOT NULL,
            valence REAL NOT NULL CHECK(valence BETWEEN -1.0 AND 1.0),
            arousal REAL NOT NULL CHECK(arousal BETWEEN 0.0 AND 1.0),
            intensity REAL NOT NULL CHECK(intensity BETWEEN 0.0 AND 1.0),
            confidence REAL CHECK(confidence BETWEEN 0.0 AND 1.0),
            timestamp TEXT NOT NULL,
            FOREIGN KEY (entry_id) REFERENCES Conversations(entry_id) ON DELETE CASCADE,
            FOREIGN KEY (session_id) REFERENCES Sessions(id) ON DELETE CASCADE
        );
               
        CREATE INDEX IF NOT EXISTS idx_themeriver_entry ON themeriver(entry_id);
        CREATE INDEX IF NOT EXISTS idx_themeriver_session ON themeriver(session_id);
        CREATE INDEX IF NOT EXISTS idx_themeriver_time ON themeriver(timestamp);
    """)

    db.commit()

def get_or_create_session_id(db):
    today = datetime.now().strftime("%Y-%m-%d")

    # check if a session already exists 4 today
    cursor = db.execute("SELECT id FROM Sessions WHERE date = ?", (today,))
    row = cursor.fetchone()

    if row:
        return row[0]

    # if no session exists -> create a new one
    db.execute(
        "INSERT INTO Sessions (date) VALUES (?)",
        (today,)
    )
    db.commit()

    # get id of newly created session
    cursor = db.execute("SELECT id FROM Sessions WHERE date = ?", (today,))
    return cursor.fetchone()[0]


    