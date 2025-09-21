from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
import sqlite3
from typing import Any, Literal, Optional, Union

from fastapi import HTTPException


class BaseAnalysis(ABC):
    """
    each analyzer must expose:
      - name: str
      - instructions(): str            
      - json_shape(): str              
      - parse_output(section): Any     -> normalize model output for DB 
      - save_to_db(db, session_id, entry_id, result)
    """

    #json key, e.g. 'spider', 'va'
    name: str

    # --- prompt building stuff to expose by analyzers ------------------
    def instructions(self) -> str:
        #per analyer instrucions /rules
        return ""

    @abstractmethod
    def json_shape(self) -> str:
        #give example of json object needed
        raise NotImplementedError

    # --- model output ------
    @abstractmethod
    def parse_output(self, section: Union[dict, list]) -> Any:
        raise NotImplementedError

    @abstractmethod
    def save_to_db(self, db: sqlite3.Connection, session_id: int, entry_id: int, result: Any) -> None:
        raise NotImplementedError


# ------------------------------------- common methods -module level -------------------------------------
def fetch_user_text(db: sqlite3.Connection, entry_id: int) -> str:
    rows = db.execute("""
        SELECT content
        FROM Messages
        WHERE entry_id = ? AND sender = 'user'
        ORDER BY timestamp ASC
    """, (entry_id,)).fetchall()
    return " ".join(r[0] for r in rows).strip()


def fetch_session_id(db: sqlite3.Connection, entry_id: int) -> int:
    row = db.execute("SELECT session_id FROM Conversations WHERE entry_id = ?", (entry_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="entry_id not found")
    return int(row[0])


# internal func for getting time in day, week, month
def _range_from_view(view: str) -> tuple[str, str]:
    if not view:
        return None, None
    now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    #end date is tmrw at midnight 
    end = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    start=now
    
    if view == 'day':
        #start is today at midnight
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif view == 'week':
        #start is exactly 7 days before the end date (moving 7day window)
        start = end - timedelta(days=7)
    elif view == 'month':
        #start is the 1st day of current calendar month
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    fmt = "%Y-%m-%d %H:%M:%S"
    return start.strftime(fmt), end.strftime(fmt)





PLUTCHIK_PRIMARIES = {"joy","trust","fear","surprise","sadness","disgust","anger","anticipation"}

#synonym map
_SYNONYM_TO_PRIMARY = {
    # positive
    "happy": "joy", "happiness": "joy", "glad": "joy", "good": "joy", "great": "joy",
    "excited": "anticipation", "eager": "anticipation", "curious": "anticipation",
    "calm": "trust", "content": "trust", "safe": "trust", "secure": "trust",
    "surprised": "surprise", "shocked": "surprise", "amazed": "surprise",
    # negative
    "tired": "sadness", "exhausted": "sadness", "fatigued": "sadness", "lonely": "sadness", "tiredness": "sadness",
    "frustration": "anger", "frustrated": "anger", "annoyed": "anger", "irritated": "anger",
    "mad": "anger", "furious": "anger", "rage": "anger",
    "disappointed": "sadness", "grief": "sadness", "depressed": "sadness", "down": "sadness",
    "anxious": "fear", "anxiety": "fear", "worried": "fear", "afraid": "fear", "scared": "fear", "nervous": "fear",
    "stressed": "fear", "overwhelmed": "fear",
    "disgusted": "disgust", "gross": "disgust", "repulsed": "disgust", "bored": "disgust",
}

def normalize_to_plutchik(label: str) -> str | None:
    #map free text emotion to Plutchik primaries.
    if not label:
        return None
    s = str(label).strip().lower()
    if s in PLUTCHIK_PRIMARIES:
        return s
    return _SYNONYM_TO_PRIMARY.get(s)