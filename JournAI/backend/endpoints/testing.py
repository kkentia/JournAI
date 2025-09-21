# testing data for filling db -> GPT code

import sqlite3
from datetime import datetime
import json

def main():
    db = None 
    try:
        db = sqlite3.connect("backend/databases/journai.db")
        db.execute("PRAGMA foreign_keys = ON")
        print("Successfully connected to the database.")

        session_id = 50
        entry_id = 100
        current_date = datetime.now().strftime('%Y-%m-%d')
        entry_timestamp = current_date

        print(f"\nPreparing to insert data for Session ID: {session_id} and Entry ID: {entry_id}")

        db.execute(
            "INSERT OR IGNORE INTO User (id, name, age, gender) VALUES (?, ?, ?, ?);",
            (1, 'Default User', 30, 'other')
        )
        print("-  Default user created.")

        # 1. Create the Session
        db.execute(
            "INSERT OR IGNORE INTO Sessions (id, mood_avg, date) VALUES (?, ?, ?);",
            (session_id, 5.2, current_date)
        )
        print("- Inserted record into Sessions table.")

        # 2. Create the parent Conversation entry to satisfy FOREIGN KEY constraints
        db.execute(
             """
             INSERT OR IGNORE INTO Conversations (entry_id, session_id, title, timestamp)
             VALUES (?, ?, ?, ?);
             """,
             (entry_id, session_id, 'Journal Entry Analysis', entry_timestamp)
        )
        print(f"- Ensured parent record exists in Conversations table for entry_id {entry_id}.")

        # 3. Populate the Activities lookup table
        activities_to_insert = [
            ('waking',), ('scrolling',), ('working',), ('eating',), ('walking',),
            ('watching',), ('calling',), ('cooking',), ('folding',), ('writing',)
        ]
        db.executemany(
            "INSERT OR IGNORE INTO Activities (name) VALUES (?);",
            activities_to_insert
        )
        print("- Populated or verified records in Activities table.")

        # 4. Insert user-reported activity metrics
        # (This part remains the same)
        user_metrics_sql = f"""
            INSERT INTO Metrics (session_id, entry_id, metric_type, activity_id, description, comment, rating, source, timestamp) VALUES
            ({session_id}, {entry_id}, 'activity', (SELECT id FROM Activities WHERE name = 'waking'), 'waking', 'Later than desired, low energy', 4, 'user', '{entry_timestamp}'),
            ({session_id}, {entry_id}, 'activity', (SELECT id FROM Activities WHERE name = 'scrolling'), 'scrolling', 'Passive activity, not fulfilling', 4, 'user', '{entry_timestamp}'),
            ({session_id}, {entry_id}, 'activity', (SELECT id FROM Activities WHERE name = 'working'), 'working', 'Fine, kept busy but felt pointless', 5, 'user', '{entry_timestamp}'),
            ({session_id}, {entry_id}, 'activity', (SELECT id FROM Activities WHERE name = 'eating'), 'eating', 'Unnoticed, distracted by YouTube', 4, 'user', '{entry_timestamp}'),
            ({session_id}, {entry_id}, 'activity', (SELECT id FROM Activities WHERE name = 'walking'), 'walking', 'Cleared head, felt better afterwards', 7, 'user', '{entry_timestamp}'),
            ({session_id}, {entry_id}, 'activity', (SELECT id FROM Activities WHERE name = 'watching'), 'watching', 'Background activity, low engagement', 5, 'user', '{entry_timestamp}'),
            ({session_id}, {entry_id}, 'activity', (SELECT id FROM Activities WHERE name = 'calling'), 'calling', 'Positive, provided some connection', 6, 'user', '{entry_timestamp}'),
            ({session_id}, {entry_id}, 'activity', (SELECT id FROM Activities WHERE name = 'cooking'), 'cooking', 'Small meal, neutral-positive', 6, 'user', '{entry_timestamp}'),
            ({session_id}, {entry_id}, 'activity', (SELECT id FROM Activities WHERE name = 'folding'), 'folding', 'Chore, neutral mood', 5, 'user', '{entry_timestamp}'),
            ({session_id}, {entry_id}, 'activity', (SELECT id FROM Activities WHERE name = 'writing'), 'writing', 'Helpful for sorting out thoughts', 6, 'user', '{entry_timestamp}');
        """
        db.executescript(user_metrics_sql)
        print("- Inserted user-reported activity metrics.")

        # 5. Insert AI-analyzed quiz metrics
        # (This part remains the same)
        ai_metrics_sql = f"""
            INSERT INTO Metrics (session_id, entry_id, metric_type, description, comment, rating, source, timestamp) VALUES
            ({session_id}, {entry_id}, 'quiz', 'f1', 'distressed', 5, 'ai', '{entry_timestamp}'),
            ({session_id}, {entry_id}, 'quiz', 'f2', 'irritable', 3, 'ai', '{entry_timestamp}'),
            ({session_id}, {entry_id}, 'quiz', 'f3', 'nervous', 3, 'ai', '{entry_timestamp}'),
            ({session_id}, {entry_id}, 'quiz', 'f4', 'scared', 2, 'ai', '{entry_timestamp}'),
            ({session_id}, {entry_id}, 'quiz', 'f5', 'unhappy', 5, 'ai', '{entry_timestamp}'),
            ({session_id}, {entry_id}, 'quiz', 'f6', 'upset', 4, 'ai', '{entry_timestamp}'),
            ({session_id}, {entry_id}, 'quiz', 'f7', 'lonely', 6, 'ai', '{entry_timestamp}');
        """
        db.executescript(ai_metrics_sql)
        print("- Inserted AI-analyzed quiz metrics.")

        # 6. *** FIX: Insert overall analysis results with correctly formatted JSON ***
        activity_tags_list = ["waking", "scrolling", "working", "eating", "walking", "watching", "calling", "cooking", "folding", "writing"]
        activity_tags_json = json.dumps(activity_tags_list) # Convert Python list to JSON string

        db.execute(
            """
            INSERT INTO analysis_results (id, session_id, entry_id, valence, arousal, primary_emotion, secondary_emotion, activity_tags, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (entry_id, session_id, entry_id, 0.25, 0.35, 'sadness', 'joy', activity_tags_json, entry_timestamp)
        )
        print("- Inserted overall analysis results with JSON-formatted activity_tags.")

        # 7. Insert Plutchik emotion events
        # (This part remains the same)
        plutchik_events_sql = f"""
            INSERT INTO plutchik_events (entry_id, session_id, source, primary_emotion, level, intensity, sub_label, confidence) VALUES
            ({entry_id}, {session_id}, 'ai', 'sadness', 2, 0.5, 'sadness', 0.9),
            ({entry_id}, {session_id}, 'ai', 'joy', 1, 0.3, 'joy', 0.8),
            ({entry_id}, {session_id}, 'ai', 'anticipation', 1, 0.2, 'anticipation', 0.7),
            ({entry_id}, {session_id}, 'ai', 'trust', 1, 0.2, 'trust', 0.7),
            ({entry_id}, {session_id}, 'ai', 'disgust', 1, 0.2, 'disgust', 0.6);
        """
        db.executescript(plutchik_events_sql)
        print("- Inserted Plutchik emotion events.")

        # 8. *** FIX: Insert ThemeRiver data using parameterized queries and JSON formatting ***
        themeriver_data = [
            (entry_id, session_id, 'sadness', json.dumps(['work felt pointless', 'couldn’t focus to read', 'half-watched series', 'writing to sort thoughts']), 0.25, 0.35, 1, 1, entry_timestamp),
            (entry_id, session_id, 'joy', json.dumps(['smiled seeing happy dog', 'walk cleared head', 'cooked small dinner', 'called mom']), 0.25, 0.35, 1, 1, entry_timestamp),
            (entry_id, session_id, 'anticipation', json.dumps(['plan to wake earlier tomorrow', 'aim for proper breakfast']), 0.25, 0.35, 1, 1, entry_timestamp),
            (entry_id, session_id, 'trust', json.dumps(['connection after calling mom', 'self-knowledge about habits']), 0.25, 0.35, 1, 1, entry_timestamp),
            (entry_id, session_id, 'disgust', json.dumps(['day felt kind of pointless', 'mindless YouTube while eating']), 0.25, 0.35, 1, 1, entry_timestamp)
        ]
        db.executemany(
            """
            INSERT INTO themeriver (entry_id, session_id, emotion, reasons, valence, arousal, intensity, confidence, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            themeriver_data
        )
        print("- Inserted ThemeRiver data with JSON-formatted reasons.")


        # Commit all the changes to the database
        db.commit()
        print("\nAll data has been successfully committed to the database.")

    except sqlite3.Error as e:
        print(f"\nAn error occurred: {e}")
        # If an error occurs, roll back any changes made during the transaction
        if db:
            db.rollback()
            print("Transaction has been rolled back.")

    finally:
        # Ensure the database connection is closed
        if db:
            db.close()
            print("Database connection closed.")

if __name__ == "__main__":
    main()