"""Streamlit dashboard for the SA economic indicators pipeline.

Run with:
    streamlit run dashboard/app.py
"""

import sqlite3
import sys
from pathlib import Path

# Streamlit runs this file with dashboard/ as cwd, so the project root isn't
# on sys.path. Add it explicitly so `from dashboard.queries import ...` works.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import altair as alt
import pandas as pd
import streamlit as st

from dashboard.queries import (
    cpi_vs_fx_by_year,
    date_range_by_indicator,
    latest_value_by_indicator,
    load_indicators,
    row_count_by_source,
)

from src.pipeline.storage.paths import DB_PATH

st.set_page_config(
    page_title="SA Economic Indicators",
    page_icon="📈",
    layout="wide",
)


@st.cache_data(ttl=60)
def _load_all(db_path: str) -> dict[str, pd.DataFrame]:
    """Load every query result once per cache window."""
    con = sqlite3.connect(db_path)
    try:
        return {
            "indicators": load_indicators(con),
            "latest": latest_value_by_indicator(con),
            "by_source": row_count_by_source(con),
            "ranges": date_range_by_indicator(con),
            "cpi_vs_fx": cpi_vs_fx_by_year(con),
        }
    finally:
        con.close()


def _metric_card(label: str, value: str, help_text: str | None = None) -> None:
    st.metric(label=label, value=value, help=help_text)


def _overview_tab(data: dict[str, pd.DataFrame]) -> None:
    latest = data["latest"]
    indicators = data["indicators"]

    col1, col2, col3, col4 = st.columns(4)

    cpi_row = latest[latest["indicator_name"] == "CPI"]
    fx_row = latest[latest["indicator_name"] == "USD_ZAR"]

    with col1:
        if not cpi_row.empty:
            _metric_card(
                "Latest CPI",
                f"{cpi_row.iloc[0]['value']:.1f}",
                f"as of {cpi_row.iloc[0]['date']}",
            )
    with col2:
        if not fx_row.empty:
            _metric_card(
                "USD → ZAR",
                f"{fx_row.iloc[0]['value']:.2f}",
                f"as of {fx_row.iloc[0]['date']}",
            )
    with col3:
        _metric_card("Observations", f"{len(indicators):,}")
    with col4:
        sources = indicators["source"].nunique() if not indicators.empty else 0
        _metric_card("Sources", str(sources))

    st.divider()

    cpi = indicators[indicators["indicator_name"] == "CPI"]
    fx = indicators[indicators["indicator_name"] == "USD_ZAR"]

    left, right = st.columns(2)

    with left:
        st.subheader("CPI (annual)")
        if cpi.empty:
            st.info("No CPI data loaded.")
        else:
            chart = (
                alt.Chart(cpi)
                .mark_line(point=True)
                .encode(
                    x=alt.X("date:T", title="Year"),
                    y=alt.Y("value:Q", title="Index (2010 = 100)"),
                    tooltip=["date:T", "value:Q"],
                )
                .properties(height=320)
            )
            st.altair_chart(chart, use_container_width=True)

    with right:
        st.subheader("USD → ZAR (daily)")
        if fx.empty:
            st.info("No FX data loaded.")
        else:
            chart = (
                alt.Chart(fx)
                .mark_line()
                .encode(
                    x=alt.X("date:T", title="Date"),
                    y=alt.Y("value:Q", title="ZAR per USD"),
                    tooltip=["date:T", "value:Q"],
                )
                .properties(height=320)
            )
            st.altair_chart(chart, use_container_width=True)


def _crossover_tab(data: dict[str, pd.DataFrame]) -> None:
    df = data["cpi_vs_fx"]
    st.subheader("CPI vs average USD/ZAR (joined on year)")
    st.caption(
        "CPI is annual; FX is daily. Joining on year avoids the date-mismatch "
        "described in decisions.md §12."
    )
    if df.empty:
        st.info("Not enough overlapping data to build this view.")
        return

    base = alt.Chart(df).encode(x=alt.X("year:O", title="Year"))
    cpi_line = base.mark_line(point=True, color="#1f77b4").encode(
        y=alt.Y("cpi:Q", title="CPI"),
    )
    fx_line = base.mark_line(point=True, color="#ff7f0e").encode(
        y=alt.Y("fx_avg:Q", title="Avg ZAR per USD"),
    )
    chart = alt.layer(cpi_line, fx_line).resolve_scale(y="independent").properties(height=400)
    st.altair_chart(chart, use_container_width=True)

    with st.expander("Raw data"):
        st.dataframe(df, use_container_width=True)


def _quality_tab(data: dict[str, pd.DataFrame]) -> None:
    st.subheader("Data loaded")
    st.dataframe(data["by_source"], use_container_width=True, hide_index=True)

    st.subheader("Date coverage")
    st.dataframe(data["ranges"], use_container_width=True, hide_index=True)

    st.caption(
        "Weekend and holiday gaps in FX data are expected — the ECB does not "
        "publish on those days. See decisions.md §9.1."
    )


def main() -> None:
    st.title("South African Economic Indicators")
    st.caption("Source: World Bank (CPI) · Frankfurter / ECB (USD/ZAR)")

    if not DB_PATH.exists():
        st.error(
            f"Database not found at `{DB_PATH}`. Run the pipeline first:\n\n"
            "```\npython -m src.pipeline.ingestion.run\n"
            "python -m src.pipeline.transformation.run\n"
            "python -m src.pipeline.storage.run\n```"
        )
        st.stop()

    data = _load_all(str(DB_PATH))

    tab1, tab2, tab3 = st.tabs(["Overview", "CPI vs FX", "Data quality"])
    with tab1:
        _overview_tab(data)
    with tab2:
        _crossover_tab(data)
    with tab3:
        _quality_tab(data)


if __name__ == "__main__":
    main()