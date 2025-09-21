# analysis_optimized.py
from __future__ import annotations
import json
import logging
import sqlite3
from typing import Any, List, Dict, Optional, Literal

from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import JSONResponse

from graphs.valence_arousal import ValenceArousalAnalysis
from graphs.spider import SpiderAnalysis
from graphs.plutchik import PlutchikAnalysis
from graphs.activity import ActivityAnalysis
from graphs.themeriver import ThemeriverAnalysis
from graphs.base import fetch_user_text, fetch_session_id, _range_from_view

analysis_router = APIRouter()
logger = logging.getLogger("uvicorn.error")

# ----------------------- helpers -----------------------

def _extract_llm_text(resp: Any) -> str:
    if resp is None: return ""
    if isinstance(resp, str): return resp.strip()
    if isinstance(resp, dict):
        ch = (resp.get("choices") or [{}])[0]
        if "text" in ch: return str(ch["text"]).strip()
        msg = ch.get("message") or {}
        if "content" in msg: return str(msg["content"]).strip()
        if "error" in resp: return f"__LLM_ERROR__:{resp['error']}"
    return ""

def _strip_code_fences(s: str) -> str:
    t = s.strip()
    if t.startswith("```"):
        parts = t.split("```")
        if len(parts) >= 3: return parts[1].strip()
    return s

def _iter_balanced_json_chunks(s: str):
    stack: List[str] = []
    start = None
    for i, ch in enumerate(s):
        if ch in "{[":
            if not stack: start = i
            stack.append(ch)
        elif ch in "}]":
            if stack:
                o = stack.pop()
                if ((o == "{" and ch == "}") or (o == "[" and ch == "]")) and not stack and start is not None:
                    yield s[start:i + 1]; start = None

def _extract_parsable_json(s: str, prefer_last: bool = True) -> str:
    if not s: return ""
    chunks = list(_iter_balanced_json_chunks(_strip_code_fences(s)))
    if prefer_last: chunks.reverse()
    for c in chunks:
        try:
            json.loads(c); return c
        except Exception: continue
    return ""

#same as last func but for themeriver who generates lists
def _extract_all_parsable_json(s: str, prefer_last: bool = True) -> List[Any]:
    if not s: return []
    chunks = list(_iter_balanced_json_chunks(_strip_code_fences(s)))
    if prefer_last: chunks.reverse()
    out: List[Any] = []
    for c in chunks:
        try: out.append(json.loads(c))
        except Exception: pass
    return out

def _shape_wants_array(shape: Any) -> bool:
    if isinstance(shape, str): return shape.lstrip().startswith("[")
    return isinstance(shape, (list, tuple))

def _shape_to_text(shape: Any) -> str:
    if isinstance(shape, str): return shape.strip()
    try: return json.dumps(shape, ensure_ascii=False, indent=2)
    except Exception: return str(shape)

def _unwrap_if_wrapped(parsed: Any, *keys: str):
    if isinstance(parsed, dict):
        for k in keys:
            if k and isinstance(parsed.get(k), list):
                return parsed[k]
    return parsed

def _coerce_float(x, default=None):
    if x is None: return default
    try: return float(x)
    except Exception: return default

def _normalize_themeriver_rows(obj: Any) -> List[dict]:
    obj = _unwrap_if_wrapped(obj, "themeriver", "items", "data", "rows", "values")
    if isinstance(obj, dict): obj = [obj]
    if not isinstance(obj, list): return []
    out: List[dict] = []
    for d in obj:
        if not isinstance(d, dict): continue
        emo = str(d.get("emotion", "")).strip().lower()
        if not emo: continue
        reasons = d.get("reasons")
        if isinstance(reasons, str): reasons = [reasons]
        if reasons is None: reasons = []
        out.append({
            "timestamp": d.get("timestamp"),
            "emotion": emo,
            "valence": _coerce_float(d.get("valence"), 0.0),
            "arousal": _coerce_float(d.get("arousal"), 0.0),
            "intensity": _coerce_float(d.get("intensity"), 0.0),
            "confidence": _coerce_float(d.get("confidence"), None),
            "reasons": reasons,
        })
    return out

# -----------------------  LLM runner -----------------------

def _run_single_analyzer(llm, text: str, a: Any) -> Any:
    shape_raw = (a.json_shape() or "")
    wants_array = _shape_wants_array(shape_raw)
    empty_fragment = [] if wants_array else {}
    prompt = (
        "Respond ONLY in JSON. No prose. No comments.\n\n"
        f'Key "{a.name}"\n'
        f"Instructions:\n{(a.instructions() or '').strip()}\n\n"
        f'JSON schema for "{a.name}":\n{_shape_to_text(shape_raw)}\n\n'
        "If you cannot infer anything, return an empty array [] or empty object {} matching the shape.\n\n"
        "<<<BEGIN_OF_JOURNAL_ENTRY>>>\n"
        f"{text}\n"
        "<<<END_OF_JOURNAL_ENTRY>>>\n"
    )

    resp = llm(prompt, max_tokens=500, temperature=0.0, top_p=1.0)
    raw = _extract_llm_text(resp)

    if wants_array:
        rows: List[dict] = []
        for f in _extract_all_parsable_json(raw, prefer_last=True):
            # unwrap common wrappers only when expecting arrays
            frag = _unwrap_if_wrapped(f, getattr(a, "name", None), "themeriver", "items", "data", "rows", "values")
            if isinstance(frag, list):
                rows += [x for x in frag if isinstance(x, dict)]
            elif isinstance(frag, dict):
                rows.append(frag)
        return rows

    json_str = _extract_parsable_json(raw, prefer_last=True)
    if not json_str: return empty_fragment
    try:
        return json.loads(json_str)
    except Exception:
        return empty_fragment

# ---------------------- GET endpoints ----------------------

@analysis_router.get("/va-results")
async def get_va_results(
    request: Request,
    view: Optional[Literal["day","week","month"]] = Query(default="day"),
    entry_id: Optional[int] = Query(default=None),
    session_id: Optional[int] = Query(default=None),

):
    db: sqlite3.Connection = request.app.state.db
    start, end = _range_from_view(view)
    data = ValenceArousalAnalysis.get_results(db, start=start, end=end, entry_id=entry_id, session_id=session_id)
    return JSONResponse(data)

@analysis_router.get("/metrics/spider-results")
async def get_spider_results(
    request: Request,
    view: Optional[Literal["day","week","month"]] = Query(default="day"),
    entry_id: Optional[int] = Query(default=None),
    session_id: Optional[int] = Query(default=None),

):
    db: sqlite3.Connection = request.app.state.db
    start, end = _range_from_view(view)
    data = SpiderAnalysis.get_results(db, start=start, end=end, entry_id=entry_id, session_id=session_id)
    return JSONResponse(data)

@analysis_router.get("/plutchik-results")
async def get_plutchik_results(
    request: Request,
    view: Optional[Literal["day","week","month"]] = Query(default="day"),
    source: Optional[Literal["ai","user"]] = Query(default=None),
   entry_id: Optional[int] = Query(default=None),
    session_id: Optional[int] = Query(default=None),

):
    db = request.app.state.db
    start, end = _range_from_view(view)
    data = PlutchikAnalysis.get_results(db, start=start, end=end, source=source, entry_id=entry_id, session_id=session_id)
    return JSONResponse(data)

@analysis_router.get("/plutchik-dyads")
async def get_plutchik_dyads(
    request: Request,
    view: Optional[Literal["day", "week", "month"]] = Query(default="day"),
    source: Optional[Literal["ai","user"]] = Query(default=None),
    entry_id: Optional[int] = Query(default=None),
    session_id: Optional[int] = Query(default=None),

):
    db = request.app.state.db
    start, end = _range_from_view(view)
    try:
        data = PlutchikAnalysis.get_dyads(db, start=start, end=end, source=source, entry_id=entry_id, session_id=session_id)
        return JSONResponse(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"plutchik-dyads query failed: {e}")

# ---------------------- POST: per-analyzer run ----------------------

@analysis_router.post("/analyze-all")
async def analyze_all_and_save(request: Request, payload: dict):
    db: sqlite3.Connection = request.app.state.db
    llm = request.app.state.llm

    entry_id = payload.get("entry_id")
    if not entry_id:
        raise HTTPException(status_code=400, detail="entry_id is required")

    text = fetch_user_text(db, entry_id)
    if not text:
        raise HTTPException(status_code=400, detail="No user messages for this entry_id")

    MAX_TEXT_CHARS = 4000
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS] + "…"

    analyzers: List[Any] = [
        ValenceArousalAnalysis(),
        SpiderAnalysis(),
        PlutchikAnalysis(),
        ActivityAnalysis(),
        ThemeriverAnalysis(),
    ]

    merged: Dict[str, Any] = {}
    for a in analyzers:
        try:
            merged[a.name] = _run_single_analyzer(llm, text, a)
        except Exception:
            wants_array = False
            try: wants_array = _shape_wants_array(a.json_shape())
            except Exception: pass
            merged[a.name] = [] if wants_array else {}

    session_id = fetch_session_id(db, entry_id)

    try:
        for analyzer in analyzers:
            section = merged.get(analyzer.name)
            print(f"\n[DB] Processing section '{analyzer.name}'...")

            # normalize ONLY Themeriver into list-of-rows
            if str(getattr(analyzer, "name", "")).lower() in ("themeriver"):
                section = _normalize_themeriver_rows(section)

            parsed = analyzer.parse_output(section)
            if parsed:
                analyzer.save_to_db(db, session_id, entry_id, parsed)

        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"DB write failed: {e}")

    return JSONResponse({
        "status": "ok",
        "entry_id": entry_id,
        "session_id": session_id,
        **merged
    })
