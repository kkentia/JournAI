#THEMERIVER ROUTER WITH POST AND GET
from __future__ import annotations
from typing import Optional, List, Any, Dict, Literal
import json, logging, sqlite3
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from graphs.base import fetch_user_text, fetch_session_id, _range_from_view
from graphs.themeriver import ThemeriverAnalysis

logger = logging.getLogger("uvicorn.error")
themeriver_router = APIRouter()

class ExtractBody(BaseModel):
    entry_id: int = Field(..., ge=1)

@themeriver_router.post("/themeriver")
async def extract_and_insert_themeriver(request: Request, body: ExtractBody):
    db: sqlite3.Connection = request.app.state.db
    llm = request.app.state.llm
    if llm is None:
        raise HTTPException(status_code=503, detail="LLM not available")

    session_id = fetch_session_id(db, body.entry_id)
    user_text = fetch_user_text(db, body.entry_id)
    if not user_text:
        raise HTTPException(status_code=400, detail="No user text for this entry")

    tr = ThemeriverAnalysis()
    prompt = tr.build_prompt() + f"\nUser entry:\n\"\"\"{user_text}\"\"\"\n"

    try:
        resp = llm(prompt, max_tokens=800)
        raw = resp["choices"][0]["text"]
    except Exception as e:
        logger.exception("LLM call failed")
        raise HTTPException(status_code=500, detail=f"LLM failed: {e}")

    json_block = _extract_json_array(raw)
    if not json_block:
        logger.error("No JSON array found in LLM output. raw=%r", raw[:400])
        raise HTTPException(status_code=500, detail="No JSON array found in model output")

    try:
        section = json.loads(json_block)
    except Exception:
        logger.exception("Model JSON parse failed")
        raise HTTPException(status_code=500, detail="Model JSON parse failed")

    items = tr.parse_output(section)
    if not items:
        logger.info("No valid themeriver items for entry_id=%s", body.entry_id)
        return JSONResponse({"status": "ok", "entry_id": body.entry_id, "session_id": session_id,
                             "inserted_count": 0, "items": []})

    tr.save_to_db(db, session_id, body.entry_id, items)
    db.commit()
    return JSONResponse({
        "status": "ok",
        "entry_id": body.entry_id,
        "session_id": session_id,
        "inserted_count": len(items),
        "items": items,
    })


@themeriver_router.get("/themeriver")
async def get_theme_river(
    request: Request,
    view: Literal["day","week","month"] = Query(default="day"),
    session_id: Optional[int] = Query(default=None),
    entry_id: Optional[int] = Query(default=None),
):
    db: sqlite3.Connection = request.app.state.db

    if entry_id is not None:
        rows = db.execute(
            """
            SELECT session_id, timestamp, emotion, valence, arousal, intensity, confidence, reasons, entry_id
            FROM themeriver
            WHERE entry_id = ?
            ORDER BY timestamp ASC, emotion ASC
            """,
            (entry_id,),
        ).fetchall()
        logger.info("ThemeRiver GET: entry_id=%s -> %d rows", entry_id, len(rows))

    elif session_id is not None:
        rows = db.execute(
            """
            SELECT session_id, timestamp, emotion, valence, arousal, intensity, confidence, reasons, entry_id
            FROM themeriver
            WHERE session_id = ?
            ORDER BY timestamp ASC, emotion ASC
            """,
            (session_id,),
        ).fetchall()
        logger.info("ThemeRiver GET: session_id=%s -> %d rows", session_id, len(rows))
    
    else:
        #fallback to the date view if no specific entryid isgiven
        start, end = _range_from_view(view)

        rows = db.execute(
            """
            SELECT session_id, timestamp, emotion, valence, arousal, intensity, confidence, reasons, entry_id
            FROM themeriver
            WHERE timestamp >= ? AND timestamp < ?
            ORDER BY timestamp ASC, emotion ASC
            """,
            (start, end),
        ).fetchall()
        logger.info("ThemeRiver GET: view=%s (%s to %s) -> %d rows", view, start, end, len(rows))

    items: List[Dict[str, Any]] = []
    for sid, ts, emo, v, a, I, conf, reasons_json, eid in rows:
        try:
            reasons = json.loads(reasons_json) if reasons_json else []
        except Exception:
            reasons = []
        items.append({
            "session_id": sid,
            "timestamp": ts,
            "entry_id": eid,
            "emotion": emo,
            "valence": float(v),
            "arousal": float(a),
            "intensity": float(I),
            "confidence": None if conf is None else float(conf),
            "reasons": reasons,
        })

    return JSONResponse({"items": items})

def _extract_json_array(s: str) -> str:
    start = s.find("[")
    if start == -1: return ""
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "[": depth += 1
        elif s[i] == "]":
            depth -= 1
            if depth == 0: return s[start:i+1]
    return ""