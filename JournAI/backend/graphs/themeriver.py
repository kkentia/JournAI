from __future__ import annotations
from typing import List, Dict, Tuple, Optional
import json, sqlite3
from fastapi import HTTPException
from .base import BaseAnalysis, normalize_to_plutchik

EMOTION_TO_VA: Dict[str, Tuple[float, float]] = {
    "joy": (+0.90, 0.60), "trust": (+0.60, 0.40), "anticipation": (+0.40, 0.60),
    "surprise": (+0.10, 0.85), "anger": (-0.70, 0.80), "disgust": (-0.70, 0.30),
    "fear": (-0.80, 0.80), "sadness": (-0.90, 0.20),
}
ALLOWED_EMOTIONS = list(EMOTION_TO_VA.keys())

def _clamp01(x: Optional[float]) -> Optional[float]:
    if x is None: return None
    try: x = float(x)
    except: return None
    return 0.0 if x < 0 else (1.0 if x > 1 else x)

class ThemeriverAnalysis(BaseAnalysis):
    name = "themeriver"

    def instructions(self) -> str:
        return (
            "Identify the primary emotions expressed in the Journal Entry, using Plutchik's 8 primary emotions."
            "For each activity/emotion in the Journal Entry, add one array item. "
            "Confidence must be an integer between 0 and 1, representing how sure you are of your answer."
            "Intensity must be an integer between 0 and 1 representing how strong said emotion is felt."
        )
    
    def json_shape(self) -> str:
        return """{
                "themeriver": [ 
                    { "emotion": "joy/ fear/ sadness...", "reasons": [""], "intensity": "0-1", "confidence": "0-1" }
                    ]}""".strip()

    

    def parse_output(self, section: dict | list) -> List[dict]:
        if not isinstance(section, list):
            if isinstance(section, dict) and isinstance(section.get("items"), list):
                section = section["items"]
            else:
                return []

        out: List[dict] = []
        for it in section:
            if not isinstance(it, dict): 
                continue
            raw = str(it.get("emotion", "")).strip().lower()
            e = normalize_to_plutchik(raw)  # <-- normalize
            if not e:
                continue  # still unknown; skip
            reasons = it.get("reasons") or []
            if not isinstance(reasons, list): reasons = [str(reasons)]
            reasons = [str(r).strip() for r in reasons if str(r).strip()][:6]
            intensity = _clamp01(it.get("intensity")) or 0.4
            confidence = _clamp01(it.get("confidence"))
            v, a = EMOTION_TO_VA[e]
            out.append({
                "emotion": e, "reasons": reasons,
                "valence": v, "arousal": a,
                "intensity": float(intensity),
                "confidence": None if confidence is None else float(confidence),
            })
        return out

    def save_to_db(self, db: sqlite3.Connection, session_id: int, entry_id: int, result: List[dict]):
        row = db.execute("SELECT timestamp FROM Conversations WHERE entry_id = ?", (entry_id,)).fetchone()
        if not row: 
            raise HTTPException(status_code=404, detail="entry_id not found in Conversations")
        conv_ts = str(row[0])

        for item in result:
            db.execute(
                """
                INSERT INTO themeriver
                    (entry_id, session_id, emotion, reasons, valence, arousal, intensity, confidence, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_id, session_id, item["emotion"],
                    json.dumps(item["reasons"], ensure_ascii=False),
                    float(item["valence"]), float(item["arousal"]),
                    float(item["intensity"]),
                    item["confidence"] if item["confidence"] is None else float(item["confidence"]),
                    conv_ts,
                ),
            )