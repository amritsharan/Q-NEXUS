from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Any, Optional

from src.q_nexus.pipeline import evaluate_batch

app = FastAPI(title="Q-Nexus Prototype API")
app.mount("/static", StaticFiles(directory="static"), name="static")

DB_PATH = "q_nexus.db"


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
    conn.commit()
    conn.close()


_init_db()


class BatchRequest(BaseModel):
    # Accept either `molecules` (new) or `smiles_list` (legacy). Both optional to allow raw list bodies.
    molecules: Optional[List[Any]] = None
    smiles_list: Optional[List[Any]] = None


class QARequest(BaseModel):
    query: str
    persist_directory: str | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


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
        INSERT INTO runs (created_at, input_count, payload_json, result_json)
        VALUES (?, ?, ?, ?)
        """,
        (
            created_at,
            len(input_list),
            json.dumps(input_list),
            json.dumps(results),
        ),
    )
    conn.commit()
    run_id = cursor.lastrowid
    conn.close()

    return {"run_id": run_id, "results": results}


@app.get("/runs")
def list_runs():
    conn = _get_db()
    rows = conn.execute(
        "SELECT id, created_at, input_count FROM runs ORDER BY id DESC LIMIT 50"
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
    except Exception:
        raise HTTPException(
            status_code=503,
            detail=(
                "LangChain dependencies are not installed. Run `pip install -r requirements.txt` "
                "or install the optional environment as described in README.md."
            ),
        )

    persist_dir = payload.persist_directory or "./chroma_store"
    try:
        retriever = get_retriever(persist_dir)
    except Exception:
        # If store doesn't exist, create it from repo files
        repo_root = "./"
        create_chroma_store(repo_root, persist_directory=persist_dir)
        retriever = get_retriever(persist_dir)

    answer = answer_query(payload.query, retriever)
    return {"answer": answer}
