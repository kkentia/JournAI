import logging
import sqlite3
from fastapi import Query, APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import datetime as dt
from datetime import datetime
from collections import defaultdict
from typing import Literal, Optional, List
import re
from datetime import datetime, date, timedelta
from itertools import combinations


from graphs.base import  _range_from_view
from graphs.plutchik import canonical_sub, level_from_intensity, DYAD_NAME


metrics_router = APIRouter()

class MetricForm(BaseModel):
    tag: str
    description: str
    comment: Optional[str] = None
    rating: int
    entry_id: Optional[int] = None  # optional journal entry ID




def _normalize_activity(name: str) -> str:
    s = (name or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s

def _resolve_activity_id(db: sqlite3.Connection, raw_name: str) -> int:
    """
    Resolve 'raw_name' to a canonical Activities.id.
    - If it exists and is an alias, follow alias_of chain to canonical.
    - If not found, create a new *canonical* row (alias_of=NULL).
    """
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

#------------------------------------endpoint--------------------------------
@metrics_router.post("/submit-metric")
async def submit_metric(data: MetricForm, request: Request):
    db = request.app.state.db
    db.execute("PRAGMA foreign_keys = ON;")

    if not (1 <= data.rating <= 10):
        return {"error": "Invalid rating"}

    session_id = request.app.state.journal.get_or_create_session_id(db)
    entry_id = data.entry_id

    if data.tag == "activity":
        # resolve canonical id (creates if missing; respects aliases)
        activity_id = _resolve_activity_id(db, data.description)

        db.execute("""
            INSERT INTO Metrics (session_id, entry_id, metric_type, activity_id, description, rating, comment, source)
            VALUES (?, ?, 'activity', ?, ?, ?, ?, 'user')
        """, (session_id, entry_id, activity_id, data.description, data.rating, data.comment))

    elif data.tag == "quiz":
        db.execute("""
            INSERT INTO Metrics (session_id, entry_id, metric_type, description, rating, comment, source)
            VALUES (?, ?, 'quiz', ?, ?, ?,'user')
        """, (session_id, entry_id, data.description, data.rating, data.comment))

    else:
        db.execute("""
            INSERT INTO Metrics (session_id, entry_id, metric_type, description, rating, comment, source)
            VALUES (?, ?, ?, ?, ?, ?,'user')
        """, (session_id, entry_id, data.tag, data.description, data.rating, data.comment))

    db.commit()

    return {"status": "ok", "entry_id": entry_id}







#------------------------------------GET--------------------------------

@metrics_router.get("/metrics/histogram")
async def get_activity_histogram(
    request: Request,
    view: Optional[Literal["day","week","month"]] = Query(default="week"),
    entry_id: Optional[int] = Query(default=None),
    session_id: Optional[int] = Query(default=None),
):
    db = request.app.state.db
    start, end = _range_from_view(view)

    base = """
        SELECT
            date(m.timestamp)     AS day,
            a.name                AS name,
            COUNT(*)              AS cnt,
            AVG(m.rating)         AS avg_rating   -- NULL-safe; AVG ignores NULLs
        FROM Metrics m
        JOIN Activities a ON m.activity_id = a.id
        WHERE m.metric_type = 'activity'
    """
    params: list = []

    #priority: entry-> session-> date-range-> all
    if entry_id is not None:
        q = base + " AND m.entry_id = ? GROUP BY day, name ORDER BY day ASC"
        params = [entry_id]
    elif session_id is not None:
        q = base + " AND m.session_id = ? GROUP BY day, name ORDER BY day ASC"
        params = [session_id]
    elif start and end:
        q = base + " AND m.timestamp >= ? AND m.timestamp < ? GROUP BY day, name ORDER BY day ASC"
        params = [start, end]
    else:
        q = base + " GROUP BY day, name ORDER BY day ASC"

    rows = db.execute(q, params).fetchall()

    by_day = defaultdict(list)
    for day, name, cnt, avg_rating in rows:
        by_day[day].append({
            "name":   name,
            "count":  int(cnt),
            "mood":   float(avg_rating) if avg_rating is not None else None
        })

    result = []
    for day, acts in by_day.items():
        acts.sort(key=lambda x: x.get("count", 0), reverse=True)
        result.append({"day": day, "activities": acts})

    result.sort(key=lambda d: d["day"])   #chronological
    return JSONResponse(result)


@metrics_router.get("/metrics/mood-histogram")
async def get_mood_histogram(request: Request):
    db = request.app.state.db

    query = """
    SELECT 
        date(m.timestamp) as day,
        a.name as activity_name,
        COUNT(*) as count,
        AVG(m.rating) as avg_rating
    FROM Metrics m
    JOIN Activities a ON m.activity_id = a.id
    WHERE m.metric_type = 'activity' AND m.rating IS NOT NULL
    GROUP BY day, activity_name
    ORDER BY day ASC, avg_rating DESC
    """
    rows = db.execute(query).fetchall()

    grouped_by_day = defaultdict(list)
    all_dates = set()

    for day_str, activity_name, count, avg_rating in rows:
        grouped_by_day[day_str].append({
            "name": activity_name,
            "count": count,
            "mood": avg_rating
        })
        all_dates.add(day_str)

    # if no dates exist, at least include today
    # if we have no rows, show just today with empty activities
    if not all_dates:
        day_list = [date.today()]
    else:
        # build a continuous day range from the min to max date we saw
        min_date = min(date.fromisoformat(d) for d in all_dates)
        max_date = max(date.fromisoformat(d) for d in all_dates)

        day_list = []
        cur = min_date
        while cur <= max_date:
            day_list.append(cur)
            cur += timedelta(days=1)

    # assemble response
    result = []
    for d in day_list:
        day_str = d.isoformat()
        result.append({
            "day": day_str,
            "activities": grouped_by_day.get(day_str, [])
        })

    return result



#----------------------------- MERGE ACTIVITIES ROUTE -----------------------------

class MergeActivitiesBody(BaseModel):
    sources: List[str] = Field(..., description="Labels to merge (e.g., ['game','gaming'])")
    target: str        = Field(..., description="Canonical label to use (e.g., 'gaming')")

@metrics_router.post("/metrics/activities/merge")
async def merge_activities(body: MergeActivitiesBody, request: Request):
    db: sqlite3.Connection = request.app.state.db
    sources = [s.strip() for s in body.sources if s and s.strip()]
    target  = (body.target or "").strip()
    if not sources or not target:
        return {"error": "sources and target are required"}

    norm_sources = [_normalize_activity(s) for s in sources]
    norm_target  = _normalize_activity(target)

    try:
        db.execute("BEGIN")

        # ensure target exists & is canonical
        row = db.execute(
            "SELECT id, alias_of FROM Activities WHERE lower(name) = ?",
            (norm_target,)
        ).fetchone()

        if row:
            target_id, alias_of = row
            if alias_of is not None:
                db.execute("UPDATE Activities SET alias_of = NULL WHERE id = ?", (target_id,))
        else:
            cur = db.execute("INSERT INTO Activities (name, alias_of) VALUES (?, NULL)", (norm_target,))
            target_id = cur.lastrowid

        # alias each source to target + collect ids for repointing them
        src_ids = []
        for src in norm_sources:
            srow = db.execute("SELECT id, alias_of FROM Activities WHERE lower(name) = ?", (src,)).fetchone()
            if srow:
                sid, _ = srow
            else:
                cur = db.execute("INSERT INTO Activities (name, alias_of) VALUES (?, ?)", (src, target_id))
                sid = cur.lastrowid

            if sid != target_id:
                db.execute("UPDATE Activities SET alias_of = ? WHERE id = ?", (target_id, sid))
                src_ids.append(sid)

        # repoint historical metrics to the target canonical id
        if src_ids:
            qmarks = ",".join("?" for _ in src_ids)
            db.execute(
                f"UPDATE Metrics SET activity_id = ? WHERE activity_id IN ({qmarks})",
                (target_id, *src_ids)
            )

        db.commit()
        return {
            "status": "ok",
            "target_id": target_id,
            "canonical": norm_target,
            "aliased_count": len(src_ids)
        }

    except Exception as e:
        db.rollback()
        return {"error": f"merge failed: {e}"}
    


# ----------------------------- PLUTCHIK MANUAL POST ROUTE -----------------------------



Primary = Literal['joy','trust','fear','surprise','sadness','disgust','anger','anticipation']
logger = logging.getLogger("uvicorn.error")
THRESH_DYAD = 0.40

class ManualPlutchikItem(BaseModel):
    primary_emotion: Primary
    intensity: float = Field(..., ge=0.0, le=1.0)  
    level: Optional[int] = Field(None, ge=1, le=3)

class ManualPlutchikBody(BaseModel):
    emotions: List[ManualPlutchikItem] = Field(default_factory=list)


# ------------------------------------------------------------------------------

@metrics_router.post("/manual/plutchik")
async def manual_plutchik(request: Request, body: ManualPlutchikBody):
    db: sqlite3.Connection = request.app.state.db
    session_id = request.app.state.journal.get_or_create_session_id(db)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        db.execute("BEGIN")
        inserted = 0

        # ts -> primary -> {id, intensity}
        events_by_ts: dict[str, dict[str, dict]] = defaultdict(dict)

        # 1) insert events
        for emo in body.emotions:
            primary_raw = (emo.primary_emotion or "").strip().lower()
            if not primary_raw:
                continue

            intensity = float(emo.intensity)  # 0..1
            level = emo.level if emo.level in (1, 2, 3) else level_from_intensity(intensity)
            sub = canonical_sub(primary_raw, level)

            #per emotion timestamps in payload, else use 'now'
            ts = getattr(emo, "timestamp", None) or now

            cur = db.execute(
                """
                INSERT INTO plutchik_events
                    (entry_id, session_id, source, primary_emotion, level, intensity, sub_label, confidence, timestamp)
                VALUES (NULL, ?, 'user', ?, ?, ?, ?, NULL, ?)
                """,
                (session_id, primary_raw, level, intensity, sub, ts),
            )
            eid = cur.lastrowid
            events_by_ts[ts][primary_raw] = {"id": eid, "intensity": intensity}
            inserted += 1

        logger.info("[manual_plutchik] inserted %d events; timestamps: %s",
                    inserted, list(events_by_ts.keys()))

        # 2)build dyads within each timestamp group 
        for ts, prim_map in events_by_ts.items():
            primaries = list(prim_map.keys())
            logger.info("[manual_plutchik] TS=%s primaries=%s", ts, primaries)

            for a, b in combinations(primaries, 2):
                ia = float(prim_map[a]["intensity"])
                ib = float(prim_map[b]["intensity"])
                label = DYAD_NAME.get((a, b))

                logger.info("[manual_plutchik] consider TS=%s pair=(%s,%s) ia=%.2f ib=%.2f label=%s",
                            ts, a, b, ia, ib, label or "—")

                if not label:
                    continue
                if ia <= THRESH_DYAD or ib <= THRESH_DYAD:
                    logger.info("[manual_plutchik]  skip (%s,%s) below THRESH=%.2f", a, b, THRESH_DYAD)
                    continue

                eid_a = prim_map[a]["id"]
                eid_b = prim_map[b]["id"]
                ev1, ev2 = (eid_a, eid_b) if eid_a < eid_b else (eid_b, eid_a)
                weight = (ia + ib) / 2.0

                db.execute(
                    """
                    INSERT INTO plutchik_dyads
                        (entry_id, session_id, source, event_a_id, event_b_id, dyad_label, weight, confidence, timestamp)
                    VALUES (NULL, ?, 'user', ?, ?, ?, ?, NULL, ?)
                    ON CONFLICT(entry_id, source, event_a_id, event_b_id) DO UPDATE SET
                        dyad_label = excluded.dyad_label,
                        weight     = excluded.weight,
                        confidence = excluded.confidence,
                        timestamp  = excluded.timestamp
                    """,
                    (session_id, ev1, ev2, label, weight, ts),
                )
                logger.info("[manual_plutchik]  INSERT dyad=%s ev1=%s ev2=%s ts=%s weight=%.2f",
                            label, ev1, ev2, ts, weight)

        db.commit()
        return {"status": "ok", "inserted_events": inserted}

    except Exception as e:
        db.rollback()
        logger.exception("manual plutchik failed")
        return {"error": f"manual plutchik failed: {e}"}