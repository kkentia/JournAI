import datetime
from fastapi import APIRouter, Request


session_router = APIRouter()

async def start_journaling(request: Request):
    db = request.app.state.db
    journal = request.app.state.journal        
    session_id = journal.get_or_create_session_id(db)
    entry_id = journal.start_new_entry(db)
    return {"entry_id": entry_id, "session_id": session_id}

session_router.post("/start-journaling")(start_journaling)


class sessionMemory:
    def __init__(self): 
        self.current_entry_id = None
        self.current_session_id = None

    def get_or_create_session_id(self, db):
        today = datetime.date.today().isoformat()
        cursor = db.execute("SELECT id FROM Sessions WHERE date = ?", (today,))
        row = cursor.fetchone()
        if row:
            self.current_session_id = row[0]
        else:
            cursor = db.execute("INSERT INTO Sessions (date) VALUES (?)", (today,))
            self.current_session_id = cursor.lastrowid
            db.commit()
        return self.current_session_id

    #TODO: implement 
    def start_new_entry(self, db):
        cursor = db.execute("""
            INSERT INTO Conversations (title)
            VALUES (?)
        """, ("empty_entry",))
        self.current_entry_id = cursor.lastrowid
        db.commit()
        return self.current_entry_id

    def end_session(self):
        self.current_entry_id = None


