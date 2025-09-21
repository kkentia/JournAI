from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import List, Optional

mood_router = APIRouter()

class MoodLog(BaseModel):
    phq4_answers: List[Optional[int]]
    state_feelings: List[Optional[int]]
    note: Optional[str] = None
    entry_id: Optional[int] = None #optional unless messages are associated

@mood_router.post("/mood")
async def submit_mood(log: MoodLog, request: Request):
    #phq = [v for v in log.phq4_answers if v is not None]
    #feelings = [v for v in log.state_feelings if v is not None]

    db = request.app.state.db
    session_id = request.app.state.journal.get_or_create_session_id(db)
    entry_id = log.entry_id if log.entry_id else None
    
    phq_comments = {
        "q1": "Feeling nervous, anxious, or on edge",
        "q2": "Not being able to stop or control worrying",
        "q3": "Feeling down, depressed, or hopeless",
        "q4": "Little interest or pleasure in doing things"
    }

    feelings_comments = {
        "f1": "Distressed",
        "f2": "Irritable",
        "f3": "Nervous",
        "f4": "Scared",
        "f5": "Unhappy",
        "f6": "Upset",
        "f7": "Lonely"
    }

    for i, value in enumerate(log.phq4_answers):
        if value is not None:
            qid = f"q{i+1}"
            db.execute(
                "INSERT INTO Metrics (session_id, entry_id, metric_type, description, comment, rating) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, entry_id, "quiz", qid, phq_comments.get(qid, ""), value)
            )

    for i, value in enumerate(log.state_feelings):
        if value is not None:
            fid = f"f{i+1}"
            db.execute(
                "INSERT INTO Metrics (session_id, entry_id, metric_type, description, comment, rating) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, entry_id, "quiz", fid, feelings_comments.get(fid, ""), value)
            )

    if log.note:
        db.execute(
            "INSERT INTO Metrics (session_id, entry_id, metric_type, description, comment, rating) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, entry_id, "quiz", "note", log.note, None)
        )

    db.commit()
    return {"message": "Mood log saved"}
