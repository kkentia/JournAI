from datetime import datetime
import sqlite3
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

chat_router = APIRouter()
entries_router = APIRouter()


def load_system_prompt(path: str = "prompts/system_prompt.txt") -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


class ChatRequest(BaseModel):
    message: str
    entry_id: int | None = None
    bot_enabled: bool = False  


def fetch_user_info(db: sqlite3.Connection) -> dict:
    row = db.execute("SELECT name, age, gender FROM User WHERE id = 1 LIMIT 1").fetchone()
    if not row:
        return {}

    name, age, gender = row
    return {
        "name": name if name else None,
        "age": age,
        "gender": gender
    }


# ---------------------- /chat endpoint (NO in-memory session) ----------------------

@chat_router.post("/chat")
async def chat_handler(request: Request, chat_request: ChatRequest):
    print("bot_enabled from client:", chat_request.bot_enabled, "entry_id:", chat_request.entry_id)
    #check if a msg is already being processed
    if getattr(request.app.state, "is_processing", False):
        raise HTTPException(status_code=429, detail="Wait for the bot to reply before sending another message.")

    request.app.state.is_processing = True  # lock

    try:
        db = request.app.state.db
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        session_id = request.app.state.session_id
        entry_id = chat_request.entry_id

        # always create an entry_id if missing
        if not entry_id:
            cursor = db.execute(
                "INSERT INTO Conversations (session_id, title, timestamp) VALUES (?, ?, ?)",
                (session_id, chat_request.message, now)
            )
            entry_id = cursor.lastrowid

        # always insert the user’s message
        db.execute(
            "INSERT INTO Messages (entry_id, sender, content, timestamp) VALUES (?, ?, ?, ?)",
            (entry_id, "user", chat_request.message, now)
        )
        db.commit()

        # ---------------- bot reply (optional) ----------------
        full_reply = None
        if chat_request.bot_enabled:   # <-- only call LLM if enabled
            try:
                history_rows = db.execute("""
                    SELECT sender, content FROM Messages
                    WHERE entry_id = ?
                    ORDER BY timestamp ASC
                """, (entry_id,)).fetchall()

                history_str = "\n".join(
                    f"{'User' if sender == 'user' else 'Bot'}: {content}"
                    for sender, content in history_rows
                )

                user_info = fetch_user_info(request.app.state.db)
                prompt = f"""System: {load_system_prompt()}
                        User Information: {user_info}
                        History: {history_str} 
                        User: {chat_request.message}
                        Bot:"""

                result = request.app.state.llm(
                    prompt,
                    max_tokens=400,
                    temperature=0.7,
                    top_p=0.9,
                    repeat_penalty=1.1,
                    stop=["User", "System:", "JournAI:"],
                    stream=False
                )
                full_reply = result["choices"][0]["text"].strip()

                db.execute(
                    "INSERT INTO Messages (entry_id, sender, content, timestamp) VALUES (?, ?, ?, ?)",
                    (entry_id, "bot", full_reply, now)
                )
                db.commit()
            except Exception as e:
                print(f" Bot reply skipped: {e}")
                full_reply = None
        else:
            # bot disabled
            full_reply = None

        # always return entry_id!!! even if bot is disabled
        return JSONResponse(content={
            "user": chat_request.message,
            "bot": full_reply,
            "entry_id": entry_id
        })

    finally:
        request.app.state.is_processing = False  # unlock

# ------------------------------------ /history -----------------------------------

@chat_router.get("/history")
async def get_history(request: Request, entry_id: Optional[int] = None):
    """
    Returns messages for the given entry_id. If entry_id not provided, returns messages for the last conversation.
    """
    db: sqlite3.Connection = request.app.state.db
    if db is None:
        db = sqlite3.connect("backend/databases/journai.db", check_same_thread=False)

    if entry_id is None:
        row = db.execute("SELECT entry_id FROM Conversations ORDER BY timestamp DESC LIMIT 1").fetchone()
        if row is None:
            return {"history": []}
        entry_id = row[0]

    rows = db.execute(
        "SELECT sender, content, timestamp FROM Messages WHERE entry_id = ? ORDER BY timestamp ASC",
        (entry_id,)
    ).fetchall()

    formatted = [{"sender": s, "content": c, "timestamp": t} for s, c, t in rows]
    return {"entry_id": entry_id, "history": formatted}


# ------------------------------------- /end-session ---------------------------------------
class EndSessionRequest(BaseModel):
    entry_id: int | None = None

@chat_router.post("/end-entry")
async def end_entry(request: Request, data: EndSessionRequest):
    db = request.app.state.db
    session_id = request.app.state.session_id

    if data.entry_id:
        try:
            # update Metrics tbl to link recent unassociated metrics to the new entry_id
            db.execute("""
                UPDATE Metrics
                SET entry_id = ?
                WHERE session_id = ?
                  AND entry_id IS NULL
                  AND timestamp >= datetime('now', '-5 minutes')
            """, (data.entry_id, session_id))
            db.commit()
            return PlainTextResponse("Session entry finalized and metrics linked.", status_code=200)

        except Exception as e:
            db.rollback()
            return PlainTextResponse(f"Error linking metrics: {e}", status_code=500)
    
    return PlainTextResponse("No entry_id provided to link metrics.", status_code=400)

# ------------------------------- entries listing / delete -----------------------------------

@entries_router.get("/entries")
async def get_conversations(request: Request):
    db = request.app.state.db
    if db is None:
        db = sqlite3.connect("backend/databases/journai.db", check_same_thread=False)
        request.app.state.db = db

    conversations = db.execute("""
        SELECT entry_id, title, timestamp
        FROM Conversations
        ORDER BY timestamp DESC
    """).fetchall()

    result = []
    for convo in conversations:
        entry_id, title, ts = convo
        messages = db.execute("""
            SELECT sender, content, timestamp
            FROM Messages
            WHERE entry_id = ?
            ORDER BY timestamp ASC
        """, (entry_id,)).fetchall()

        result.append({
            "entry_id": entry_id,
            "title": title,
            "timestamp": ts,
            "messages": [
                {"sender": sender, "content": content, "timestamp": msg_ts}
                for sender, content, msg_ts in messages
            ]
        })

    return result


@entries_router.delete("/entries/{entry_id}")
async def delete_entry(entry_id: int, request: Request):
    db: sqlite3.Connection = request.app.state.db
    db.execute("PRAGMA foreign_keys = ON;")
    try:
        db.execute("BEGIN")
        # delete children 
        db.execute("DELETE FROM plutchik_dyads      WHERE entry_id = ?", (entry_id,))
        db.execute("DELETE FROM plutchik_events     WHERE entry_id = ?", (entry_id,))
        db.execute("DELETE FROM Metrics             WHERE entry_id = ?", (entry_id,))
        db.execute("DELETE FROM Messages            WHERE entry_id = ?", (entry_id,))
        db.execute("DELETE FROM analysis_results    WHERE entry_id = ?", (entry_id,))
        db.execute("DELETE FROM themeriver          WHERE entry_id = ?", (entry_id,))

        # delete parent
        db.execute("DELETE FROM Conversations       WHERE entry_id = ?", (entry_id,))
        db.commit()
        return {"status": "ok", "deleted_entry_id": entry_id, "message": "Entry and associated data deleted."}
    except sqlite3.IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Foreign key integrity error: {e}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")
    
    
    #----------------------------------RENAME CONV PUT ENDPOINT-------------------------------
class RenamePayload(BaseModel):
    new_title: str

@chat_router.put("/entries/{entry_id}/rename")
async def rename_chat_entry(entry_id: int, payload: RenamePayload, request: Request):
    db: sqlite3.Connection = request.app.state.db
    new_title = payload.new_title.strip()

    if not new_title:
        raise HTTPException(status_code=400, detail="Title cannot be empty")

    try:
        cursor = db.execute(
            "UPDATE Conversations SET title = ? WHERE entry_id = ?",
            (new_title, entry_id)
        )
        db.commit()
        return JSONResponse({"status": "ok", "message": "Entry renamed successfully"})
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")