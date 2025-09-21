from fastapi import APIRouter, Request
from pydantic import BaseModel

notes_router = APIRouter()

class NoteData(BaseModel):
    content: str

@notes_router.get("/note")
async def get_note(request: Request):
    db = request.app.state.db
    cursor = db.execute("SELECT content FROM Notes WHERE id = 1")
    row = cursor.fetchone()
    return {"content": row[0]} if row else {"content": ""}

@notes_router.post("/note")
async def save_note(data: NoteData, request: Request):
    db = request.app.state.db
    db.execute("REPLACE INTO Notes (id, content) VALUES (1, ?)", (data.content,))
    db.commit()
    return {"status": "saved"}