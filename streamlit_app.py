"""
Native M2 Pro Water Purifier — Amazon.in review tracker dashboard.

Reads amazon_review_tracking_B0G4CHKBGP.csv (one row per day, appended by the
scheduled scraper) and renders day-on-day charts of the rating distribution.
"""

import os
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ASIN = "B0G4CHKBGP"
CSV_PATH = Path(__file__).parent / f"amazon_review_tracking_{ASIN}.csv"
PRODUCT_URL = f"https://www.amazon.in/Native-M2-Pro-Dispensing-Mineraliser/dp/{ASIN}/"

STAR_COLORS = {
    "5": "#1a9850",
    "4": "#91cf60",
    "3": "#fee08b",
    "2": "#fc8d59",
    "1": "#d73027",
}

st.set_page_config(
    page_title="Native M2 Pro — Amazon Review Tracker",
    page_icon="💧",
    layout="wide",
)


@st.cache_data(ttl=60)
def load_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # Ensure derived count columns exist / are consistent with pct + total.
    for star in ["5", "4", "3", "2", "1"]:
        pct_col = f"pct_{star}"
        cnt_col = f"count_{star}"
        if pct_col in df.columns and cnt_col not in df.columns:
            df[cnt_col] = (df[pct_col] / 100.0 * df["total_ratings"]).round().astype(int)
    return df


def line_chart(df, y_col, title, y_title, color, is_pct=False):
    fmt = ".1f" if is_pct else ",.0f"
    enc_y = alt.Y(f"{y_col}:Q", title=y_title, scale=alt.Scale(zero=False))
    chart = (
        alt.Chart(df)
        .mark_line(point=True, color=color, strokeWidth=2.5)
        .encode(
            x=alt.X("date:T", title="Date"),
            y=enc_y,
            tooltip=[
                alt.Tooltip("date:T", title="Date"),
                alt.Tooltip(f"{y_col}:Q", title=y_title, format=fmt),
            ],
        )
        .properties(height=300, title=title)
    )
    return chart


df = load_data(CSV_PATH)

st.title("💧 Native M2 Pro — Amazon.in Review Tracker")
st.caption(f"[{ASIN}]({PRODUCT_URL}) · data appended daily by the scheduled scraper · source: `{CSV_PATH.name}`")

if df.empty:
    st.warning(
        "No data yet. The tracking CSV is missing or empty. "
        "It gets a new row each day from the scheduled scraper."
    )
    st.stop()

latest = df.iloc[-1]
prev = df.iloc[-2] if len(df) > 1 else None


def delta(col):
    if prev is None:
        return None
    return f"{latest[col] - prev[col]:+,.0f}"


# ---- Top-line metrics ----
c1, c2, c3, c4 = st.columns(4)
c1.metric("Avg rating", f"{latest['avg_stars']:.1f} ★",
          None if prev is None else f"{latest['avg_stars'] - prev['avg_stars']:+.2f}")
c2.metric("Total ratings", f"{int(latest['total_ratings']):,}", delta("total_ratings"))
c3.metric("Days tracked", f"{len(df)}")
c4.metric("Latest date", latest["date"].strftime("%d %b %Y"))

st.divider()

# ---- Chart 1: avg rating + total ratings ----
st.subheader("1 · Daily average rating & total number of ratings")
g1, g2 = st.columns(2)
with g1:
    st.altair_chart(
        line_chart(df, "avg_stars", "Average rating (★)", "Avg stars", "#3366cc"),
        use_container_width=True,
    )
with g2:
    st.altair_chart(
        line_chart(df, "total_ratings", "Total ratings", "# ratings", "#9933cc"),
        use_container_width=True,
    )

st.divider()

# ---- Charts 2-6: per-star absolute + % ----
for star in ["5", "4", "3", "2", "1"]:
    st.subheader(f"{6 - int(star)} · {star}-star ratings — absolute & % of total")
    color = STAR_COLORS[star]
    a, b = st.columns(2)
    with a:
        st.altair_chart(
            line_chart(df, f"count_{star}", f"# of {star}★ ratings (absolute)", "Count", color),
            use_container_width=True,
        )
    with b:
        st.altair_chart(
            line_chart(df, f"pct_{star}", f"{star}★ as % of total", "% of total", color, is_pct=True),
            use_container_width=True,
        )
    st.divider()

# ---- Raw data ----
with st.expander("Raw tracking data"):
    st.dataframe(
        df.assign(date=df["date"].dt.strftime("%Y-%m-%d")),
        use_container_width=True,
        hide_index=True,
    )
    st.download_button(
        "Download CSV",
        data=df.assign(date=df["date"].dt.strftime("%Y-%m-%d")).to_csv(index=False),
        file_name=CSV_PATH.name,
        mime="text/csv",
    )
