# AI Analyst Agent

An end-to-end Analyst Agent that lets business users ask natural-language questions and get:

1. SQL generated automatically from the question  
2. Query execution on a local SQL engine (DuckDB)  
3. Narrative business explanation  
4. Key insights  
5. Auto-generated chart + markdown report  

---

## How it works

### 1) Create a knowledge base from CSVs
- The agent reads all `*.csv` files from a folder.
- Each CSV becomes a SQL table in `DuckDB`.
- Schema metadata is written to `data/schema_metadata.json`.

### 2) User submits a question
Example:  
`How many campaigns launched last week by campaign_name?`

### 3) Agent generates SQL
- Converts question to SQL using NL-to-SQL heuristics with schema awareness.
- Enforces read-only safety (`SELECT` only).

### 4) Agent executes SQL
- Runs the generated SQL against `data/knowledge_base.duckdb`.

### 5) Agent returns results
- Returns table output in CLI.

### 6) Agent returns narrative response
- Builds plain-English explanation from query output.

### 7) Agent generates insights + diagrams
- Creates key bullet insights.
- Produces auto chart in `data/charts/`.
- Writes a report in `reports/`.

---

## Setup

```bash
python3 -m pip install -r requirements.txt
```

## Run (Streamlit Web UI)

```bash
python3 -m streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501
```

Open in browser:
- `http://localhost:8501` (local machine)
- or your forwarded cloud URL if using a remote dev environment.

## Run (single question)

```bash
python3 -m analyst_agent.main \
  --csv-dir "/home/ubuntu/.cursor/projects/workspace/uploads" \
  --question "How many campaigns launched last week by campaign_name?"
```

## Run (interactive mode)

```bash
python3 -m analyst_agent.main --csv-dir "/home/ubuntu/.cursor/projects/workspace/uploads"
```

---

## Output artifacts

- Database: `data/knowledge_base.duckdb`
- Schema: `data/schema_metadata.json`
- Charts: `data/charts/*.png`
- Reports: `reports/report_*.md`
