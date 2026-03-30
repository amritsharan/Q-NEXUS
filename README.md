# Q-NEXUS Prototype

Minimal prototype for the Q-Nexus validation pipeline: Z3 symbolic constraints + RDKit checks + stability proxy.

## Structure
- API + UI server: app.py
- UI assets: static/
- Core: src/q_nexus/molecule_validator.py

## Quick start
1) Install deps: `pip install -r requirements.txt`
2) Run server: `uvicorn app:app --reload`
3) Open UI: http://localhost:8000

### Windows quick-run

For Windows users, two convenience scripts are provided in the repository root:

- `run.ps1` — PowerShell helper: creates `.venv`, installs `requirements.txt`, and launches the server.
- `run.bat` — cmd helper: similar behavior for Command Prompt.

Usage examples:

PowerShell (recommended):

```powershell
./run.ps1
```

Command Prompt:

```cmd
run.bat
```

To force a fresh environment:

```powershell
./run.ps1 -Reinstall
```


## Notes
- Each validation run is stored in a local SQLite DB (q_nexus.db).
- The stability function uses VQE for H2, and Qiskit Nature VQE with a tiny active space for up to 30 atoms.
- Larger molecules fall back to classical energy; results are a coarse proxy for demo validation.

## LangChain integration

This repo includes a minimal LangChain integration to allow QA over the codebase using OpenAI and a Chroma vector store.

Quick setup:

1. Add your OpenAI API key to the environment:

```
setx OPENAI_API_KEY "your_api_key_here"
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Index the repository (first time) or let the API create the index on-demand:

```bash
python -m src.q_nexus.langchain_integration
```

4. Run the API server and use the `/qa` endpoint:

```bash
uvicorn app:app --reload
```

Example request (curl):

```bash
curl -X POST http://localhost:8000/qa -H "Content-Type: application/json" -d '{"query":"What does src/q_nexus/pipeline.py do?"}'
```

Files:
- `src/q_nexus/langchain_integration.py`: helpers to create embeddings, Chroma store, and run retrieval-augmented QA.
- `app.py`: exposes `/qa` endpoint that uses the store and OpenAI.

Batch validation input formats

The `/validate_batch` endpoint now accepts a list of molecule inputs (JSON array) where each item may be:

- a SMILES string (e.g. "CCO")
- an InChI string (starts with "InChI=")
- a Molfile / MolBlock text (multi-line string containing `M  END` or `V2000`/`V3000`)
- a JSON object with explicit type and value: `{"type":"smiles","value":"CCO"}` or `{"type":"molblock","value":"..."}`

Example requests:

```bash
curl -X POST http://localhost:8000/validate_batch -H "Content-Type: application/json" \
	-d '{"molecules": ["CCO", "InChI=1S/CH4/h1H4", {"type":"molblock","value":"<molfile text>"}]}'
```

