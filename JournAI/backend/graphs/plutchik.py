from datetime import datetime
from collections import defaultdict
import logging
from typing import Dict, List

from .base import BaseAnalysis, normalize_to_plutchik

# ---------- constants / helpers ----------
PLUTCHIK: Dict[str, Dict[int, str]] = {
    "joy":          {1: "serenity",     2: "joy",          3: "ecstasy"},
    "trust":        {1: "acceptance",   2: "trust",        3: "admiration"},
    "fear":         {1: "apprehension", 2: "fear",         3: "terror"},
    "surprise":     {1: "distraction",  2: "surprise",     3: "amazement"},
    "sadness":      {1: "pensiveness",  2: "sadness",      3: "grief"},
    "disgust":      {1: "boredom",      2: "disgust",      3: "loathing"},
    "anger":        {1: "annoyance",    2: "anger",        3: "rage"},
    "anticipation": {1: "interest",     2: "anticipation", 3: "vigilance"},
}

DYAD_NAME: Dict[tuple, str] = {
    ("joy","trust"): "love",
    ("trust","fear"): "submission",
    ("fear","surprise"): "awe",
    ("surprise","sadness"): "disapproval",
    ("sadness","disgust"): "remorse",
    ("disgust","anger"): "contempt",
    ("anger","anticipation"): "aggressiveness",
    ("anticipation","joy"): "optimism",
    ("anticipation","trust"): "hope",
    ("anticipation","fear"): "anxiety",
    ("joy","fear"): "guilt",
    ("joy","surprise"): "delight",
    ("trust","surprise"): "curiosity",
    ("trust","sadness"): "sentimentality",
    ("fear","sadness"): "despair",
    ("fear","disgust"): "shame",
    ("surprise","disgust"): "unbelief",
    ("surprise","anger"): "outrage",
    ("sadness","anger"): "envy",
    ("sadness","anticipation"): "pessimism",
    ("disgust","anticipation"): "cynicism",
    ("disgust","joy"): "morbidness",
    ("anger","joy"): "pride",
    ("anger","trust"): "dominance",
}
DYAD_NAME.update({(b, a): v for (a, b), v in list(DYAD_NAME.items())})  #symmetric

THRESH_DYAD = 0.40
logger = logging.getLogger("uvicorn.error")

def clamp01(x: float) -> float:
    try: x = float(x)
    except Exception: x = 0.0
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x

def canonical_sub(primary: str, level: int) -> str:
    p = (primary or "").lower().strip()
    if p not in PLUTCHIK: return ""
    try: L = int(level)
    except Exception: L = 2
    if L not in (1,2,3): L = 2
    return PLUTCHIK[p][L]

def level_from_intensity(intensity: float) -> int:
    x = clamp01(intensity)
    if x < 1/3: return 1
    if x < 2/3: return 2
    return 3


# ---------- analysis ----------
class PlutchikAnalysis(BaseAnalysis):
    name = "plutchik"

    def instructions(self) -> str:
        return (
            "Identify the primary emotions expressed in the Journal Entry, using Plutchik's 8 primary emotions. "
            "For each detected emotion, provide its intensity (0..1, representing how strong said emotion is felt), "
            "confidence (0..1, representing how sure you are of your answer), and level (1, 2, or 3). "
            "Return a JSON object with an 'emotions' array containing one object per detected emotion."
        )

    def json_shape(self) -> str:
        return """{
        "emotions": [
            { "primary_emotion": "joy/ fear/ sadness...", "intensity": "0-1", "confidence": "0-1", "level": "1, 2 or 3" }
        ]
        }""".strip()

    def parse_output(self, section: dict) -> dict:
        out = []
        for emo in section.get("emotions", []):
            pe_raw = str(emo.get("primary_emotion", "")).strip().lower()
            pe = normalize_to_plutchik(pe_raw)
            if not pe:
                continue
            intensity = clamp01(emo.get("intensity", 0.0))
            level = int(emo.get("level", level_from_intensity(intensity)))
            out.append({
                "primary_emotion": pe,
                "intensity": intensity,
                "level": level,
                "sub_label": canonical_sub(pe, level),
                "confidence": float(emo.get("confidence", 1.0)),
                "timestamp": emo.get("timestamp"),
            })
        return {"emotions": out}

    def save_to_db(self, db, session_id: int, entry_id: int, result: dict):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        timestamps_touched: List[str] = []

        # 1) insert events
        for emo in result["emotions"]:
            primary = emo["primary_emotion"]
            intensity = float(emo["intensity"])
            confidence = float(emo.get("confidence", 1.0))
            ts = str(emo.get("timestamp") or now)

            db.execute(
                """
                INSERT INTO plutchik_events
                    (entry_id, session_id, source, primary_emotion, level, intensity, sub_label, confidence, timestamp)
                VALUES (?, ?, 'ai', ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_id, session_id,
                    primary, emo["level"], intensity, emo["sub_label"],
                    confidence, ts
                )
            )
            timestamps_touched.append(ts)

        # 2) re query exact timestamps we just touched and source = ai (manual is inside metrics.py)
        self._derive_dyads_from_db_for_timestamps(db, entry_id, session_id, timestamps_touched, source="ai")

    # ---- dyad derivation from DB rows that share same timestamp ----
    def _derive_dyads_from_db_for_timestamps(self, db, entry_id: int, session_id: int,
                                             timestamps: List[str], source: str = "ai") -> None:
        if not timestamps:
            return

        # de-duplicate timestamps for more opti
        ts_unique = sorted(set(timestamps))
        placeholders = ",".join("?" for _ in ts_unique)

        q = f"""
            SELECT id, primary_emotion, intensity, confidence, timestamp
            FROM plutchik_events
            WHERE entry_id = ? AND session_id = ? AND source = ?
              AND timestamp IN ({placeholders})
            ORDER BY timestamp ASC, id ASC
        """
        rows = db.execute(q, (entry_id, session_id, source, *ts_unique)).fetchall()

        # group by exact timestamp string
        by_ts: dict[str, list[dict]] = defaultdict(list)
        for rid, primary, intensity, confidence, ts in rows:
            by_ts[str(ts)].append({
                "id": rid,
                "primary": str(primary).lower(),
                "intensity": float(intensity or 0.0),
                "confidence": float(confidence or 1.0),
            })

        for ts, evs in by_ts.items():
            logger.info("[plutchik] dyads@%s source=%s evs=%s",
                        ts, source, [(e["primary"], e["intensity"]) for e in evs])

            #all pair combinations within the same timestamp
            m = len(evs)
            for i in range(m):
                a = evs[i]
                for j in range(i + 1, m):
                    b = evs[j]

                    label = DYAD_NAME.get((a["primary"], b["primary"]))
                    logger.info(
                        "[plutchik]   pair (%s,%s) => %s  ia=%.3f ib=%.3f",
                        a["primary"], b["primary"], label or "—", a["intensity"], b["intensity"]
                    )
                    if not label:
                        continue
                    if a["intensity"] <= THRESH_DYAD or b["intensity"] <= THRESH_DYAD:
                        continue

                    ev1, ev2 = (a["id"], b["id"]) if a["id"] < b["id"] else (b["id"], a["id"])
                    weight = (a["intensity"] + b["intensity"]) / 2.0

                    db.execute(
                        """
                        INSERT INTO plutchik_dyads
                            (entry_id, session_id, source, event_a_id, event_b_id, dyad_label, weight, confidence, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 1.0, ?)
                        ON CONFLICT(entry_id, source, event_a_id, event_b_id) DO UPDATE SET
                            dyad_label = excluded.dyad_label,
                            weight     = excluded.weight,
                            confidence = excluded.confidence,
                            timestamp  = excluded.timestamp
                        """,
                        (entry_id, session_id, source, ev1, ev2, label, weight, ts)
                    )
                    logger.info("[plutchik]     INSERT dyad=%s evs=(%s,%s) ts=%s weight=%.3f",
                                label, ev1, ev2, ts, weight)

    # ---------------------- getters--------------- ----
    @staticmethod
    def get_results(db, start=None, end=None, source=None, entry_id=None, session_id=None):
        q_base = """
        SELECT entry_id, session_id, source, primary_emotion, level, intensity, sub_label, confidence, timestamp
        FROM plutchik_events
        """
        params = []
        if entry_id is not None:
            q = q_base + " WHERE entry_id = ?"; params = [entry_id]
            if source in ("ai","user"): q += " AND source = ?"; params.append(source)
            q += " ORDER BY timestamp ASC"
        elif session_id is not None:
            q = q_base + " WHERE session_id = ?"; params = [session_id]
            if source in ("ai","user"): q += " AND source = ?"; params.append(source)
            q += " ORDER BY timestamp ASC"
        elif start and end:
            q = q_base + " WHERE timestamp >= ? AND timestamp < ?"; params = [start, end]
            if source in ("ai","user"): q += " AND source = ?"; params.append(source)
            q += " ORDER BY timestamp ASC"
        else:
            q = q_base
            if source in ("ai","user"): q += " WHERE source = ?"; params = [source]
            q += " ORDER BY timestamp ASC"

        rows = db.execute(q, tuple(params)).fetchall()
        return [{
            "entry_id":   r[0],
            "session_id": r[1],
            "source":     r[2],
            "primary":    r[3],
            "level":      r[4],
            "intensity":  float(r[5]),
            "sub_label":  r[6],
            "confidence": float(r[7]) if r[7] is not None else None,
            "timestamp":  r[8],
        } for r in rows]

    @staticmethod
    def get_dyads(db, start=None, end=None, source=None, entry_id=None, session_id=None):
        q_base = """
        SELECT
            d.entry_id,
            d.session_id,
            d.source,
            e1.primary_emotion AS primary_a,
            e2.primary_emotion AS primary_b,
            d.dyad_label,
            COALESCE(d.weight, (e1.intensity + e2.intensity)/2.0) AS weight,
            d.confidence,
            d.timestamp
        FROM plutchik_dyads d
        LEFT JOIN plutchik_events e1 ON e1.id = d.event_a_id
        LEFT JOIN plutchik_events e2 ON e2.id = d.event_b_id
        """
        params = []
        if entry_id is not None:
            q = q_base + " WHERE d.entry_id = ?"; params = [entry_id]
            if source in ("ai","user"): q += " AND d.source = ?"; params.append(source)
            q += " ORDER BY d.timestamp ASC"
        elif session_id is not None:
            q = q_base + " WHERE d.session_id = ?"; params = [session_id]
            if source in ("ai","user"): q += " AND d.source = ?"; params.append(source)
            q += " ORDER BY d.timestamp ASC"
        elif start and end:
            q = q_base + " WHERE d.timestamp >= ? AND d.timestamp < ?"; params = [start, end]
            if source in ("ai","user"): q += " AND d.source = ?"; params.append(source)
            q += " ORDER BY d.timestamp ASC"
        else:
            q = q_base
            if source in ("ai","user"): q += " WHERE d.source = ?"; params = [source]
            q += " ORDER BY d.timestamp ASC"

        rows = db.execute(q, tuple(params)).fetchall()
        return [{
            "entry_id":   r[0],
            "session_id": r[1],
            "source":     r[2],
            "primary_a":  r[3],
            "primary_b":  r[4],
            "dyad_label": r[5],
            "weight":     float(r[6]) if r[6] is not None else 0.0,
            "confidence": float(r[7]) if r[7] is not None else None,
            "timestamp":  r[8],
        } for r in rows]