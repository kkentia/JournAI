import logging
from typing import Dict
from .base import BaseAnalysis

logger = logging.getLogger("uvicorn.error")

_EMOTIONS = ["distressed","irritable","nervous","scared","unhappy","upset","lonely"]

class SpiderAnalysis(BaseAnalysis):
    name = "spider"


    def json_shape(self) -> str:
        return """{
        "distressed": 1-10,
        "irritable": 1-10,
        "nervous": 1-10,
        "scared": 1-10,
        "unhappy": 1-10,
        "upset": 1-10,
        "lonely": 1-10
        }""".strip()

    
    def instructions(self):
        return (
            "Analyze the journal entry and return ratings 1..10 for these emotional states: "
            "distressed, irritable, nervous, scared, unhappy, upset, lonely. "
            "Return them as a single JSON object with each emotion as a key and its rating as a number."
        )
    
    def parse_output(self, section: dict) -> Dict[str, int]:
        if not isinstance(section, dict):
            raise ValueError("Spider: section must be an object")
        out: Dict[str, int] = {}
        for e in _EMOTIONS:
            v = section.get(e)
            if v is None:
                continue
            try:
                iv = int(round(float(v)))
                out[e] = max(1, min(10, iv))
            except Exception:
                continue
        if not out:
            raise ValueError("Spider: no valid ratings parsed")
        return out

    def save_to_db(self, db, session_id: int, entry_id: int, result: Dict[str, int]):
        desc_map = {
            "distressed": "f1",
            "irritable":  "f2",
            "nervous":    "f3",
            "scared":     "f4",
            "unhappy":    "f5",
            "upset":      "f6",
            "lonely":     "f7",
        }
        for k, v in result.items():
            desc = desc_map.get(k)
            if not desc:
                continue
            db.execute("""
                INSERT INTO Metrics (session_id, entry_id, metric_type, description, comment, rating, source)
                VALUES (?, ?, 'quiz', ?, ?, ?, 'ai')
            """, (session_id, entry_id, desc, k, v))



#-----------------------------------GET: gets called in sentiment_analysis.py-----------------------------------
    @staticmethod
    def get_results(db, start: str | None = None, end: str | None = None,
                    entry_id: int|None=None, session_id:int |None=None):
        q = """
            SELECT description, source, AVG(rating) AS avg_rating
            FROM Metrics
            WHERE metric_type = 'quiz'
        """
        params: list[str] = []

        if entry_id is not None:
            q += " AND entry_id = ?"
            params.append(entry_id)
        elif session_id is not None:
            q += " AND session_id = ?"
            params.append(session_id)
        elif start and end:
            q += " AND timestamp >= ? AND timestamp < ?"
            params += [start, end]
            
        q += " GROUP BY description, source ORDER BY description ASC, source ASC"

        rows = db.execute(q, tuple(params)).fetchall()
        return [
            {"description": r[0], "source": r[1], "rating": round(float(r[2] or 0.0), 2)}
            for r in rows
        ]