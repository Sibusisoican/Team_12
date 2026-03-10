from __future__ import annotations

from pathlib import Path

import streamlit as st

from analyst_agent.main import run_question


DEFAULT_CSV_DIR = "/home/ubuntu/.cursor/projects/workspace/uploads"


def main() -> None:
    st.set_page_config(page_title="AI Analyst Agent", page_icon="📊", layout="wide")
    st.title("📊 AI Analyst Agent")
    st.caption("Ask business questions in natural language. Get SQL, results, narrative insights, and charts.")

    with st.sidebar:
        st.header("Data Source")
        csv_dir = st.text_input("CSV directory path", value=DEFAULT_CSV_DIR)
        st.markdown(
            "The app will ingest all CSV files in this folder and build a DuckDB knowledge base automatically."
        )

    question = st.text_area(
        "Your business question",
        placeholder="Example: Why did campaign launches drop last week by campaign_name?",
        height=100,
    )

    run_btn = st.button("Run Analysis", type="primary")

    if run_btn:
        if not question.strip():
            st.warning("Please enter a question.")
            return

        if not Path(csv_dir).exists():
            st.error(f"CSV directory not found: {csv_dir}")
            return

        with st.spinner("Running analyst agent..."):
            try:
                response = run_question(csv_dir=csv_dir, question=question.strip())
            except Exception as exc:  # noqa: BLE001
                st.exception(exc)
                return

        st.success("Analysis completed.")

        st.subheader("Generated SQL")
        st.code(response["sql"], language="sql")

        st.subheader("Narrative Response")
        st.write(response["narrative"])

        st.subheader("Key Insights")
        for insight in response["insights"]:
            st.markdown(f"- {insight}")

        st.subheader("Query Results")
        st.dataframe(response["results"], use_container_width=True)

        if response["chart_path"]:
            st.subheader("Diagram")
            st.image(str(response["chart_path"]), caption="Auto-generated chart", use_container_width=True)

        st.subheader("Artifacts")
        st.write(f"Report saved to: `{response['report_path']}`")
        st.write(f"Knowledge base tables: `{', '.join(response['tables'])}`")


if __name__ == "__main__":
    main()
