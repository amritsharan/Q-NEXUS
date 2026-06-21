# pyrefly: ignore-errors
from __future__ import annotations

import json
import os
import sqlite3
import warnings

# Override showwarning to completely suppress deprecation, langchain and user warnings
_old_showwarning = warnings.showwarning
def _new_showwarning(message, category, filename, lineno, file=None, line=None):
    cat_name = category.__name__ if category else ""
    if "deprecation" in cat_name.lower() or "userwarning" in cat_name.lower() or "langchain" in cat_name.lower():
        return
    _old_showwarning(message, category, filename, lineno, file, line)
warnings.showwarning = _new_showwarning

warnings.filterwarnings("ignore")
from datetime import datetime, timezone
from typing import List
import bcrypt

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Any, Optional

from src.q_nexus.pipeline import evaluate_batch

app = FastAPI(title="Q-Nexus Prototype API")
app.mount("/static", StaticFiles(directory="static"), name="static")

DB_PATH = "q_nexus.db"

# Vercel serverless environment workarounds: SQLite & Chroma require writable directories.
if os.environ.get("VERCEL"):
    import shutil
    # Copy SQLite DB
    tmp_db_path = "/tmp/q_nexus.db"
    if not os.path.exists(tmp_db_path):
        if os.path.exists("q_nexus.db"):
            try:
                shutil.copy("q_nexus.db", tmp_db_path)
            except Exception as e:
                print(f"Error copying SQLite database to /tmp: {e}")
        else:
            print("Warning: q_nexus.db template file not found in root.")
    DB_PATH = tmp_db_path


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    conn = _get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            input_count INTEGER NOT NULL,
            payload_json TEXT NOT NULL,
            result_json TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    try:
        conn.execute("ALTER TABLE runs ADD COLUMN username TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


_init_db()


class BatchRequest(BaseModel):
    # Accept either `molecules` (new) or `smiles_list` (legacy). Both optional to allow raw list bodies.
    molecules: Optional[List[Any]] = None
    smiles_list: Optional[List[Any]] = None
    username: Optional[str] = None


class UserAuth(BaseModel):
    username: str
    password: str


class QARequest(BaseModel):
    query: str
    persist_directory: str | None = None
    api_key: str | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/register")
def register(payload: UserAuth):
    conn = _get_db()
    try:
        row = conn.execute("SELECT username FROM users WHERE username = ?", (payload.username,)).fetchone()
        if row:
            raise HTTPException(status_code=400, detail="Username already exists")
        
        hashed = bcrypt.hashpw(payload.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        created_at = datetime.now(timezone.utc).isoformat()
        conn.execute("INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)", (payload.username, hashed, created_at))
        conn.commit()
    finally:
        conn.close()
    return {"status": "success", "message": "User registered successfully"}


@app.post("/login")
def login(payload: UserAuth):
    conn = _get_db()
    try:
        row = conn.execute("SELECT username, password_hash FROM users WHERE username = ?", (payload.username,)).fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="Invalid username or password")
        
        if not bcrypt.checkpw(payload.password.encode('utf-8'), row["password_hash"].encode('utf-8')):
            raise HTTPException(status_code=400, detail="Invalid username or password")
    finally:
        conn.close()
    return {"status": "success", "username": row["username"]}


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.post("/validate_batch")
def validate_batch(payload: BatchRequest):
    # Determine input list: new `molecules`, legacy `smiles_list`, or raise if neither provided.
    input_list = None
    if payload.molecules is not None:
        input_list = payload.molecules
    elif payload.smiles_list is not None:
        input_list = payload.smiles_list
    else:
        raise HTTPException(status_code=422, detail="Request must include 'molecules' or 'smiles_list'")

    results = evaluate_batch(input_list)
    created_at = datetime.now(timezone.utc).isoformat()

    conn = _get_db()
    cursor = conn.execute(
        """
        INSERT INTO runs (created_at, input_count, payload_json, result_json, username)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            created_at,
            len(input_list),
            json.dumps(input_list),
            json.dumps(results),
            payload.username,
        ),
    )
    conn.commit()
    run_id = cursor.lastrowid
    conn.close()

    return {"run_id": run_id, "results": results}


@app.get("/runs")
def list_runs(username: Optional[str] = None):
    conn = _get_db()
    if username:
        rows = conn.execute(
            "SELECT id, created_at, input_count FROM runs WHERE username = ? ORDER BY id DESC LIMIT 50",
            (username,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, created_at, input_count FROM runs WHERE username IS NULL ORDER BY id DESC LIMIT 50"
        ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/runs/{run_id}")
def get_run(run_id: int):
    conn = _get_db()
    row = conn.execute(
        "SELECT id, created_at, input_count, payload_json, result_json FROM runs WHERE id = ?",
        (run_id,),
    ).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "input_count": row["input_count"],
        "payload": json.loads(row["payload_json"]),
        "results": json.loads(row["result_json"]),
    }



@app.post("/qa")
def qa_endpoint(payload: QARequest):
    try:
        from src.q_nexus.langchain_integration import get_retriever, answer_query, create_chroma_store
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"LangChain dependencies failed to load: {e}",
        )

    api_key = payload.api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "answer": "No OpenAI API Key found. Please configure your API key in the settings input at the top of the chatbot panel to enable the AI Copilot."
        }

    persist_dir = payload.persist_directory
    if not persist_dir:
        if os.environ.get("VERCEL"):
            persist_dir = "/tmp/chroma_store"
            # Copy chroma_store to /tmp if it doesn't exist yet
            if not os.path.exists(persist_dir) and os.path.exists("chroma_store"):
                try:
                    import shutil
                    shutil.copytree("chroma_store", persist_dir)
                except Exception as e:
                    print(f"Error copying chroma_store to /tmp: {e}")
        else:
            persist_dir = "./chroma_store"
    try:
        retriever = get_retriever(persist_dir, api_key=api_key)
    except Exception:
        # If store doesn't exist, create it from repo files
        repo_root = "./"
        try:
            create_chroma_store(repo_root, persist_directory=persist_dir, api_key=api_key)
            retriever = get_retriever(persist_dir, api_key=api_key)
        except Exception as e:
            return {"answer": f"Error indexing repository / initializing Chroma DB: {e}"}

    try:
        answer = answer_query(payload.query, retriever, api_key=api_key)
        return {"answer": answer}
    except Exception as e:
        return {"answer": f"Error query execution: {e}"}
