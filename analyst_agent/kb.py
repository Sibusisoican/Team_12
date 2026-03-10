from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import duckdb
import pandas as pd


@dataclass
class KnowledgeBaseBuildResult:
    db_path: Path
    schema_path: Path
    tables: List[str]


def _sanitize_table_name(file_path: Path) -> str:
    base = file_path.stem.lower()
    base = re.sub(r"[^a-z0-9_]+", "_", base)
    base = re.sub(r"_+", "_", base).strip("_")
    if not base:
        base = "table"
    if base[0].isdigit():
        base = f"t_{base}"
    return base


def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    unnamed = [c for c in normalized.columns if str(c).lower().startswith("unnamed")]
    if unnamed:
        normalized = normalized.drop(columns=unnamed)

    for col in normalized.columns:
        col_name = str(col).lower()
        if "date" in col_name or col_name.endswith("_dt"):
            converted = pd.to_datetime(normalized[col], errors="coerce")
            if converted.notna().sum() > 0:
                normalized[col] = converted
    return normalized


def _collect_schema_metadata(connection: duckdb.DuckDBPyConnection, tables: List[str]) -> Dict[str, dict]:
    metadata: Dict[str, dict] = {}
    for table in tables:
        columns = connection.execute(f"PRAGMA table_info('{table}')").fetchall()
        metadata[table] = {
            "columns": [
                {
                    "name": row[1],
                    "type": row[2],
                    "nullable": bool(row[3] == 0),
                    "is_primary_key": bool(row[5]),
                }
                for row in columns
            ]
        }
    return metadata


def build_knowledge_base(
    csv_directory: str | Path,
    db_path: str | Path = "data/knowledge_base.duckdb",
    schema_path: str | Path = "data/schema_metadata.json",
) -> KnowledgeBaseBuildResult:
    csv_dir = Path(csv_directory).expanduser().resolve()
    if not csv_dir.exists():
        raise FileNotFoundError(f"CSV directory does not exist: {csv_dir}")

    csv_files = sorted(csv_dir.glob("*.csv"))
    if not csv_files:
        raise ValueError(f"No CSV files found in {csv_dir}")

    db = Path(db_path).resolve()
    db.parent.mkdir(parents=True, exist_ok=True)
    schema_file = Path(schema_path).resolve()
    schema_file.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(db))
    tables: List[str] = []

    for csv_file in csv_files:
        table_name = _sanitize_table_name(csv_file)
        df = pd.read_csv(csv_file, low_memory=False)
        df = _normalize_dataframe(df)
        con.register("tmp_df", df)
        con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM tmp_df")
        con.unregister("tmp_df")
        tables.append(table_name)

    schema = _collect_schema_metadata(con, tables)
    schema_file.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    con.close()

    return KnowledgeBaseBuildResult(db_path=db, schema_path=schema_file, tables=tables)
