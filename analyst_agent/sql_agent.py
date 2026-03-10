from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


DISALLOWED_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|replace|attach|copy|export|call)\b",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _load_schema(schema_path: str | Path) -> Dict[str, dict]:
    path = Path(schema_path)
    if not path.exists():
        raise FileNotFoundError(f"Schema metadata not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _choose_table(question: str, schema: Dict[str, dict]) -> str:
    table_names = list(schema.keys())
    if len(table_names) == 1:
        return table_names[0]

    qn = _normalize(question)
    for table in table_names:
        if _normalize(table) in qn:
            return table
    return table_names[0]


def _extract_columns(schema_table: dict) -> List[Tuple[str, str]]:
    return [(c["name"], c["type"]) for c in schema_table["columns"]]


def _match_column(fragment: str, columns: List[Tuple[str, str]]) -> Optional[str]:
    cleaned_fragment = _normalize(fragment)
    if not cleaned_fragment:
        return None

    for col, _ in columns:
        if cleaned_fragment == _normalize(col):
            return col
    for col, _ in columns:
        if cleaned_fragment in _normalize(col) or _normalize(col) in cleaned_fragment:
            return col
    return None


def _date_column(columns: List[Tuple[str, str]], question: str) -> Optional[str]:
    lower_q = question.lower()
    preferred_token = "launch" if "launch" in lower_q else ("end" if "end" in lower_q else "")

    candidates = []
    for col, col_type in columns:
        if "date" in col.lower() or "timestamp" in col_type.lower() or "date" in col_type.lower():
            candidates.append(col)

    if preferred_token:
        for col in candidates:
            if preferred_token in col.lower():
                return col
    return candidates[0] if candidates else None


def _numeric_columns(columns: List[Tuple[str, str]]) -> List[str]:
    numeric_tokens = ("int", "double", "float", "decimal", "numeric", "real", "bigint", "smallint")
    return [col for col, typ in columns if any(token in typ.lower() for token in numeric_tokens)]


def _categorical_columns(columns: List[Tuple[str, str]]) -> List[str]:
    return [col for col, typ in columns if "varchar" in typ.lower() or "text" in typ.lower()]


def validate_sql_is_safe(sql: str) -> None:
    if ";" in sql.strip().rstrip(";"):
        raise ValueError("Multiple SQL statements are not allowed.")
    if not re.match(r"^\s*select\b", sql, flags=re.IGNORECASE):
        raise ValueError("Only SELECT queries are allowed.")
    if DISALLOWED_SQL.search(sql):
        raise ValueError("Potentially unsafe SQL detected.")


def generate_sql(question: str, schema_path: str | Path) -> str:
    schema = _load_schema(schema_path)
    table = _choose_table(question, schema)
    columns = _extract_columns(schema[table])
    column_names = [c[0] for c in columns]
    date_col = _date_column(columns, question)
    numeric_cols = _numeric_columns(columns)
    categorical_cols = _categorical_columns(columns)

    q = question.lower().strip()

    # Default safe fallback.
    fallback = f"SELECT * FROM {table} LIMIT 20"

    # Explicit schema exploration.
    if "what columns" in q or "schema" in q:
        return (
            "SELECT table_name, column_name, data_type "
            "FROM information_schema.columns "
            f"WHERE table_name = '{table}' ORDER BY ordinal_position"
        )

    metric_expr = "COUNT(*) AS value"
    if any(k in q for k in ("average", "avg", "mean")) and numeric_cols:
        metric_col = numeric_cols[0]
        metric_expr = f"AVG({metric_col}) AS value"
    elif any(k in q for k in ("sum", "total")) and numeric_cols:
        metric_col = numeric_cols[0]
        metric_expr = f"SUM({metric_col}) AS value"
    elif any(k in q for k in ("max", "highest", "largest")) and numeric_cols:
        metric_col = numeric_cols[0]
        metric_expr = f"MAX({metric_col}) AS value"
    elif any(k in q for k in ("min", "lowest", "smallest")) and numeric_cols:
        metric_col = numeric_cols[0]
        metric_expr = f"MIN({metric_col}) AS value"

    # "by <column>" grouping parser.
    group_col = None
    by_match = re.search(r"\bby ([a-z0-9_ ]+)", q)
    if by_match:
        group_fragment = by_match.group(1).strip()
        for stopper in (" last ", " this ", " where ", " top ", " order ", " limit ", " between "):
            if stopper.strip() in group_fragment:
                group_fragment = group_fragment.split(stopper.strip())[0].strip()
        group_col = _match_column(group_fragment, columns)

    # Question mentions a known column directly.
    if not group_col:
        for col in column_names:
            if _normalize(col) in _normalize(q) and col in categorical_cols:
                group_col = col
                break

    filters: List[str] = []
    if date_col:
        if "last week" in q:
            filters.append(f"{date_col} >= current_date - interval 7 day")
        elif "last month" in q:
            filters.append(f"{date_col} >= current_date - interval 1 month")
        elif "this month" in q:
            filters.append(f"date_trunc('month', {date_col}) = date_trunc('month', current_date)")
        elif "today" in q:
            filters.append(f"CAST({date_col} AS DATE) = current_date")

        between_match = re.search(r"between (\d{4}-\d{2}-\d{2}) and (\d{4}-\d{2}-\d{2})", q)
        if between_match:
            start_date, end_date = between_match.groups()
            filters.append(f"CAST({date_col} AS DATE) BETWEEN DATE '{start_date}' AND DATE '{end_date}'")

    where_clause = f" WHERE {' AND '.join(filters)}" if filters else ""

    # Trend question: daily/weekly series.
    if any(k in q for k in ("trend", "over time", "day by day", "weekly")) and date_col:
        period = "week" if "week" in q or "weekly" in q else "day"
        sql = (
            f"SELECT date_trunc('{period}', {date_col}) AS period, {metric_expr} "
            f"FROM {table}{where_clause} GROUP BY 1 ORDER BY 1"
        )
        validate_sql_is_safe(sql)
        return sql

    # Top-N extraction.
    top_n = None
    top_match = re.search(r"\btop (\d+)\b", q)
    if top_match:
        top_n = int(top_match.group(1))

    if group_col:
        sql = f"SELECT {group_col}, {metric_expr} FROM {table}{where_clause} GROUP BY 1 ORDER BY 2 DESC"
        if top_n:
            sql += f" LIMIT {top_n}"
        validate_sql_is_safe(sql)
        return sql

    if any(k in q for k in ("how many", "count", "number of", "total")):
        sql = f"SELECT {metric_expr} FROM {table}{where_clause}"
        validate_sql_is_safe(sql)
        return sql

    validate_sql_is_safe(fallback)
    return fallback
