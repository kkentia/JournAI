from datetime import datetime
import json
from .base import BaseAnalysis

class ValenceArousalAnalysis(BaseAnalysis):
    name = "va"
    
    def instructions(self) -> str:
        return (
            "Analyze the user's text and provide a valence score (-1 to +1), an arousal score (0 to 1), "
            "a primary emotion, a secondary emotion, and a list of activity tags mentioned in the text."
        )
    
    def json_shape(self) -> str:
        return """{
    "valence": "",
    "arousal": "",
    "primary_emotion": "",
    "secondary_emotion": "",
    "activity_tags": [""]
    }""".strip()

    def parse_output(self, section: dict) -> dict:
        # normalization
        valence = float(section.get("valence", 0.0))
        arousal = float(section.get("arousal", 0.0))
        return {
            "valence": max(-1.0, min(1.0, valence)),
            "arousal": max(0.0, min(1.0, arousal)),
            "primary_emotion": str(section.get("primary_emotion", "") or ""),
            "secondary_emotion": str(section.get("secondary_emotion", "") or ""),
            "activity_tags": section.get("activity_tags", []) if isinstance(section.get("activity_tags", []), list) else [str(section.get("activity_tags"))]
        }

    def save_to_db(self, db, session_id: int, entry_id: int, result: dict):
        tags_str = json.dumps(result["activity_tags"], ensure_ascii=False)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        db.execute("""
            INSERT INTO analysis_results
                (session_id, entry_id, valence, arousal, primary_emotion, secondary_emotion, activity_tags,timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(entry_id) DO UPDATE SET
                session_id=excluded.session_id,
                valence=excluded.valence,
                arousal=excluded.arousal,
                primary_emotion=excluded.primary_emotion,
                secondary_emotion=excluded.secondary_emotion,
                activity_tags=excluded.activity_tags,
                timestamp=excluded.timestamp

        """, (
            session_id, entry_id,
            result["valence"], result["arousal"],
            result["primary_emotion"], result["secondary_emotion"], tags_str, now
        ))

    # -------------------------------------GET:goes into sentiment_analysis-------------------------------------
    @staticmethod
    def get_results(db, start: str | None = None, end: str | None = None,
                    entry_id: int | None = None, session_id: int | None = None):
        base_select = """
            SELECT entry_id, session_id, valence, arousal,
                   primary_emotion, secondary_emotion, activity_tags, timestamp
            FROM analysis_results
        """

        #for the filter by view
        if entry_id is not None:
            rows = db.execute(base_select + " WHERE entry_id = ? ORDER BY timestamp ASC", (entry_id,)).fetchall()
        elif session_id is not None:
            rows = db.execute(base_select + " WHERE session_id = ? ORDER BY timestamp ASC", (session_id,)).fetchall()
        elif start and end:
            rows = db.execute(base_select + " WHERE timestamp >= ? AND timestamp < ? ORDER BY timestamp ASC",
                              (start, end)).fetchall()
        else:
            rows = db.execute(base_select + " ORDER BY timestamp ASC").fetchall()

        out = []
        for r in rows:
            out.append({
                "entry_id": r[0],
                "session_id": r[1],
                "valence": r[2],
                "arousal": r[3],
                "primary_emotion": r[4],
                "secondary_emotion": r[5],
                "activity_tags": json.loads(r[6]) if r[6] else [],
                "timestamp": r[7],
            })
        return out