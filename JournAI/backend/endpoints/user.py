import sqlite3
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional

user_router = APIRouter()

class User(BaseModel):
    name:Optional[str] = None
    age: int
    gender: Optional[str] = None

@user_router.post("/User")
async def create_user(request: Request, user: User):
    if user.age <= 0 or user.age > 100:
        raise HTTPException(status_code=400, detail="Age must be between 1 and 100")

    db = request.app.state.db
    db.execute(
        "REPLACE INTO User (id, name, age, gender) VALUES (1, ?, ?, ?)",
        (user.name, user.age, user.gender)
    )
    db.commit()
    return {"message": "User saved successfully"}


#---------------------------------GET---------------------------------
@user_router.get("/UserExists")
async def user_exists(request: Request):
    db = request.app.state.db
    cursor = db.execute("SELECT COUNT(*) FROM User")
    count = cursor.fetchone()[0] #when you call execute, the results are computed and fetched, and you use fetchone/fetchmany/fetchall to retrieve them
    return {"userExists": count > 0}

#GET
@user_router.get("/UserData")
async def user_data(request: Request):
    db = request.app.state.db
    cursor = db.execute("SELECT name, age, gender FROM User LIMIT 1")
    row = cursor.fetchone()
    if row:
        return {"name": row[0], "age": row[1], "gender": row[2]}
    else:
        return {"error": "No user data found"}

#POST
@user_router.delete("/DeleteAllData")
async def delete_all_data(request: Request):
    db = request.app.state.db
    db.execute("PRAGMA foreign_keys = OFF;")
    try:
        db.execute("BEGIN")

        # children first
        db.execute("DELETE FROM plutchik_dyads")
        db.execute("DELETE FROM plutchik_events")
        db.execute("DELETE FROM Metrics")
        db.execute("DELETE FROM Messages")
        db.execute("DELETE FROM analysis_results")
        db.execute("DELETE FROM themeriver")

        db.execute("DELETE FROM Notes")
        db.execute("DELETE FROM Activities")
        db.execute("DELETE FROM Conversations")
        db.execute("DELETE FROM Sessions")
        db.execute("DELETE FROM User")

        for t in ("Messages","Conversations","Metrics","Sessions","Activities","User",
                  "plutchik_events","plutchik_dyads","Notes"):
            db.execute("DELETE FROM sqlite_sequence WHERE name = ?", (t,))
        
        db.execute("PRAGMA foreign_keys = ON;")
        db.commit()
        return {"message": "All data deleted"}
    except sqlite3.IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Foreign key integrity error: {e}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Unexpected error during data deletion: {e}")