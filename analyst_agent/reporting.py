from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional

import matplotlib.pyplot as plt
import pandas as pd


def _pick_chart_columns(df: pd.DataFrame) -> tuple[Optional[str], Optional[str], str]:
    if df.empty or len(df.columns) < 2:
        return None, None, "none"

    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    datetime_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
    categorical = [
        c
        for c in df.columns
        if c not in numeric and c not in datetime_cols and not pd.api.types.is_bool_dtype(df[c])
    ]

    if datetime_cols and numeric:
        return datetime_cols[0], numeric[0], "line"
    if categorical and numeric:
        return categorical[0], numeric[0], "bar"
    if len(numeric) >= 2:
        return numeric[0], numeric[1], "scatter"
    return None, None, "none"


def create_chart(df: pd.DataFrame, question: str, output_dir: str | Path = "data/charts") -> Optional[Path]:
    x_col, y_col, chart_type = _pick_chart_columns(df)
    if chart_type == "none" or x_col is None or y_col is None:
        return None

    chart_dir = Path(output_dir)
    chart_dir.mkdir(parents=True, exist_ok=True)
    filename = f"chart_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
    chart_path = chart_dir / filename

    plot_df = df.copy()
    if chart_type == "bar":
        plot_df = plot_df.head(20)
    if chart_type == "line":
        plot_df = plot_df.sort_values(by=x_col)

    plt.figure(figsize=(10, 5))
    if chart_type == "line":
        plt.plot(plot_df[x_col], plot_df[y_col], marker="o")
    elif chart_type == "bar":
        plt.bar(plot_df[x_col].astype(str), plot_df[y_col])
        plt.xticks(rotation=45, ha="right")
    elif chart_type == "scatter":
        plt.scatter(plot_df[x_col], plot_df[y_col])

    plt.title(f"Auto chart for: {question[:80]}")
    plt.xlabel(str(x_col))
    plt.ylabel(str(y_col))
    plt.tight_layout()
    plt.savefig(chart_path)
    plt.close()
    return chart_path


def _summarize_metrics(df: pd.DataFrame) -> List[str]:
    insights: List[str] = []
    if df.empty:
        return ["The query returned no rows, which could indicate a restrictive filter or missing data."]

    insights.append(f"The query returned {len(df)} row(s) and {len(df.columns)} column(s).")
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]

    for col in numeric_cols[:3]:
        series = df[col].dropna()
        if series.empty:
            continue
        insights.append(
            f"{col}: avg={series.mean():,.2f}, min={series.min():,.2f}, max={series.max():,.2f}."
        )

    if len(df.columns) >= 2 and numeric_cols:
        cat_candidates = [c for c in df.columns if c not in numeric_cols]
        if cat_candidates:
            cat_col = cat_candidates[0]
            val_col = numeric_cols[0]
            grouped = (
                df[[cat_col, val_col]]
                .dropna()
                .groupby(cat_col, as_index=False)[val_col]
                .sum()
                .sort_values(by=val_col, ascending=False)
            )
            if not grouped.empty:
                top = grouped.iloc[0]
                insights.append(
                    f"Top contributor is '{top[cat_col]}' with {top[val_col]:,.2f} on {val_col}."
                )
    return insights


def build_narrative_report(question: str, sql: str, result_df: pd.DataFrame) -> tuple[str, List[str], Optional[Path]]:
    chart_path = create_chart(result_df, question)
    insights = _summarize_metrics(result_df)

    if result_df.empty:
        narrative = (
            f"For your question '{question}', the SQL executed successfully but returned no data. "
            "You may want to broaden the date range or remove filters."
        )
    else:
        first_cols = ", ".join(str(c) for c in result_df.columns[:3])
        narrative = (
            f"To answer '{question}', I ran a SQL query and found {len(result_df)} matching record(s). "
            f"The results are structured around: {first_cols}. "
            "I also generated key metrics and an optional chart for quick interpretation."
        )

    return narrative, insights, chart_path


def save_markdown_report(
    question: str,
    sql: str,
    result_df: pd.DataFrame,
    narrative: str,
    insights: List[str],
    chart_path: Optional[Path],
    output_dir: str | Path = "reports",
) -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.md"

    preview = result_df.head(20).to_markdown(index=False) if not result_df.empty else "_No rows returned._"
    chart_markdown = f"![chart]({chart_path})" if chart_path else "_No chart generated for this result shape._"
    insights_md = "\n".join(f"- {item}" for item in insights)

    content = f"""# AI Analyst Agent Report

## Question
{question}

## Generated SQL
```sql
{sql}
```

## Narrative Summary
{narrative}

## Key Insights
{insights_md}

## Result Preview
{preview}

## Diagram
{chart_markdown}
"""
    report_path.write_text(content, encoding="utf-8")
    return report_path
