import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from .base import BaseAnalysis

# -------- normalizer-------------
def _normalize_activity(name: str) -> str:
    s = (name or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s

def _resolve_activity_id(db, raw_name: str) -> int:
#if new acitivity --> create a new row for it in Activities
# if existing activity -> dont create new


    norm = _normalize_activity(raw_name)

    row = db.execute(
        "SELECT id, alias_of FROM Activities WHERE lower(name) = ?",
        (norm,)
    ).fetchone()

    if row:
        act_id, alias_of = row
        while alias_of is not None:
            act_id, alias_of = db.execute(
                "SELECT id, alias_of FROM Activities WHERE id = ?",
                (alias_of,)
            ).fetchone()
        return act_id

    cur = db.execute("INSERT INTO Activities (name, alias_of) VALUES (?, NULL)", (norm,))
    return cur.lastrowid


# --------------------- Analysis class ---------------------
class ActivityAnalysis(BaseAnalysis):
    name = "activities"
    
    def json_shape(self) -> str:
        return """{
        "activities": [
            { "name": "one word verb", "rating": "1-10", "comment": "" }
        ]
        }""".strip()
    
    def instructions(self):
        return ("Analyse Journal Entry and extract any activities (one word verb, for e.g. working, hiking, gaming, etc.) they mention doing, along with a rating from 1 to 10 representing the mood afterwards, and optional comment. DO NOT invent activities! If no valid activity is present, then return nothing.")

    def parse_output(self, section: Dict[str, Any]) -> Dict[str, Any]:
        out: List[Dict[str, Any]] = []
        items = (section or {}).get("activities", [])
        if not isinstance(items, list):
            return {"activities": out}

        for it in items:
            if not isinstance(it, dict):
                continue
            name = (it.get("name") or "").strip()
            if not name:
                continue

            rating_raw: Optional[Any] = it.get("rating")
            rating: Optional[int] = None
            if rating_raw is not None:
                try:
                    r = int(round(float(rating_raw)))
                    if 1 <= r <= 10:
                        rating = r
                except Exception:
                    rating = None

            out.append({
                "name": name,
                "rating": rating,
                "comment": (it.get("comment") or "").strip() or None,
            })
        return {"activities": out}

    def save_to_db(self, db, session_id: int, entry_id: int, result: Dict[str, Any]):

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for act in result.get("activities", []):
            name = act["name"]
            rating = act["rating"]
            comment = act["comment"]
            activity_id = _resolve_activity_id(db, name)

            db.execute("""
                INSERT INTO Metrics
                    (session_id, entry_id, metric_type, activity_id, description, rating, comment, source, timestamp)
                VALUES (?, ?, 'activity', ?, ?, ?, ?, 'ai', ?)
            """, (
                session_id, entry_id,
                activity_id, name, rating, comment, now
            ))