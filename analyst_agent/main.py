from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd
from tabulate import tabulate

from .kb import build_knowledge_base
from .reporting import build_narrative_report, save_markdown_report
from .sql_agent import generate_sql, validate_sql_is_safe


def run_question(
    csv_dir: str,
    question: str,
    db_path: str = "data/knowledge_base.duckdb",
    schema_path: str = "data/schema_metadata.json",
) -> dict:
    kb = build_knowledge_base(csv_dir, db_path=db_path, schema_path=schema_path)

    sql = generate_sql(question, kb.schema_path)
    validate_sql_is_safe(sql)

    con = duckdb.connect(str(kb.db_path))
    result_df: pd.DataFrame = con.execute(sql).fetch_df()
    con.close()

    narrative, insights, chart_path = build_narrative_report(question, sql, result_df)
    report_path = save_markdown_report(question, sql, result_df, narrative, insights, chart_path)

    return {
        "question": question,
        "sql": sql,
        "results": result_df,
        "narrative": narrative,
        "insights": insights,
        "chart_path": chart_path,
        "report_path": report_path,
        "tables": kb.tables,
    }


def _print_response(response: dict) -> None:
    print("\n=== KNOWLEDGE BASE TABLES ===")
    print(", ".join(response["tables"]))

    print("\n=== GENERATED SQL ===")
    print(response["sql"])

    print("\n=== QUERY RESULT (top rows) ===")
    df = response["results"]
    if df.empty:
        print("No rows returned.")
    else:
        print(tabulate(df.head(20), headers="keys", tablefmt="github", showindex=False))

    print("\n=== NARRATIVE RESPONSE ===")
    print(response["narrative"])

    print("\n=== KEY INSIGHTS ===")
    for insight in response["insights"]:
        print(f"- {insight}")

    if response["chart_path"]:
        print(f"\nChart saved to: {response['chart_path']}")
    print(f"Report saved to: {response['report_path']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Analyst Agent (CSV -> SQL -> Insights).")
    parser.add_argument(
        "--csv-dir",
        default="data/csv",
        help="Directory containing one or more CSV files.",
    )
    parser.add_argument("--question", default=None, help="Natural language business question.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    csv_dir = str(Path(args.csv_dir).expanduser())

    if args.question:
        response = run_question(csv_dir, args.question)
        _print_response(response)
        return

    print("AI Analyst Agent is ready. Type a question (or 'exit').")
    while True:
        question: Optional[str] = input("\nQuestion> ").strip()
        if not question:
            continue
        if question.lower() in {"exit", "quit"}:
            print("Goodbye.")
            break
        response = run_question(csv_dir, question)
        _print_response(response)


if __name__ == "__main__":
    main()
