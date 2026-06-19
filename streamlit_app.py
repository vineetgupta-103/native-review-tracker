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


def overview_combo_chart(df):
    """Single dual-axis chart: total ratings as a stacked-by-star bar (left axis)
    + average rating as a line with value labels (right axis)."""
    star_cols = {
        "count_5": "5",
        "count_4": "4",
        "count_3": "3",
        "count_2": "2",
        "count_1": "1",
    }
    long = df.melt(
        id_vars=["date"],
        value_vars=list(star_cols.keys()),
        var_name="star_col",
        value_name="count",
    )
    long["star"] = long["star_col"].map(star_cols)
    order = ["5", "4", "3", "2", "1"]

    bars = (
        alt.Chart(long)
        .mark_bar()
        .encode(
            x=alt.X("date:T", title="Date"),
            y=alt.Y("count:Q", title="# ratings", stack=True),
            color=alt.Color(
                "star:N",
                title="Star",
                scale=alt.Scale(domain=order, range=[STAR_COLORS[s] for s in order]),
                sort=order,
            ),
            order=alt.Order("star:N", sort="descending"),
            tooltip=[
                alt.Tooltip("date:T", title="Date"),
                alt.Tooltip("star:N", title="Star"),
                alt.Tooltip("count:Q", title="# ratings", format=",.0f"),
            ],
        )
    )

    lo = max(0.0, float(df["avg_stars"].min()) - 0.3)
    hi = min(5.0, float(df["avg_stars"].max()) + 0.3)
    avg_base = alt.Chart(df).encode(
        x=alt.X("date:T", title="Date"),
        y=alt.Y(
            "avg_stars:Q",
            title="Avg stars",
            scale=alt.Scale(domain=[lo, hi]),
            axis=alt.Axis(orient="right", format=".1f", titleColor="#111"),
        ),
    )
    line = avg_base.mark_line(point=True, color="#111", strokeWidth=2.5).encode(
        tooltip=[
            alt.Tooltip("date:T", title="Date"),
            alt.Tooltip("avg_stars:Q", title="Avg stars", format=".2f"),
        ]
    )
    labels = avg_base.mark_text(dy=-12, color="#111", fontWeight="bold").encode(
        text=alt.Text("avg_stars:Q", format=".1f")
    )

    total_labels = (
        alt.Chart(df)
        .mark_text(dy=-6, fontSize=9, color="#333")
        .encode(
            x=alt.X("date:T"),
            y=alt.Y("total_ratings:Q"),
            text=alt.Text("total_ratings:Q", format=",.0f"),
        )
    )

    return (
        alt.layer(alt.layer(bars, total_labels), alt.layer(line, labels))
        .resolve_scale(y="independent")
        .properties(height=360, title="Total ratings (stacked by star) + average rating ★")
    )


def _pct_domain(series, min_span=20.0):
    """Y-domain for a % axis that always spans at least `min_span` points,
    so small day-to-day moves don't look like dramatic swings."""
    pmin, pmax = float(series.min()), float(series.max())
    span = pmax - pmin
    pad = (min_span - span) / 2 if span < min_span else 2.0
    lo, hi = max(0.0, pmin - pad), min(100.0, pmax + pad)
    if hi - lo < min_span:  # re-expand if clamping at 0/100 shrank it
        if lo == 0.0:
            hi = min(100.0, lo + min_span)
        elif hi == 100.0:
            lo = max(0.0, hi - min_span)
    return [lo, hi]


def count_pct_combo(df, star, color):
    """Single dual-axis chart for one star level: absolute count as bars (left axis)
    + share of total as a line (right axis)."""
    cnt, pct = f"count_{star}", f"pct_{star}"

    bars = (
        alt.Chart(df)
        .mark_bar(color=color, opacity=0.75)
        .encode(
            x=alt.X("date:T", title="Date"),
            y=alt.Y(f"{cnt}:Q", title=f"# {star}★ ratings (abs)"),
            tooltip=[
                alt.Tooltip("date:T", title="Date"),
                alt.Tooltip(f"{cnt}:Q", title=f"# {star}★", format=",.0f"),
            ],
        )
    )
    bar_labels = (
        alt.Chart(df)
        .mark_text(dy=-6, fontSize=9, color=color)
        .encode(
            x=alt.X("date:T"),
            y=alt.Y(f"{cnt}:Q"),
            text=alt.Text(f"{cnt}:Q", format=",.0f"),
        )
    )

    pct_base = alt.Chart(df).encode(
        x=alt.X("date:T", title="Date"),
        y=alt.Y(
            f"{pct}:Q",
            title=f"% {star}★ of total",
            scale=alt.Scale(domain=_pct_domain(df[pct])),
            axis=alt.Axis(orient="right", format=".0f", titleColor="#111"),
        ),
    )
    line = pct_base.mark_line(point=True, color="#111", strokeWidth=2.5).encode(
        tooltip=[
            alt.Tooltip("date:T", title="Date"),
            alt.Tooltip(f"{pct}:Q", title=f"% {star}★", format=".0f"),
        ]
    )
    pct_labels = pct_base.mark_text(dy=-10, fontSize=9, color="#111", fontWeight="bold").encode(
        text=alt.Text(f"{pct}:Q", format=".0f")
    )

    return (
        alt.layer(alt.layer(bars, bar_labels), alt.layer(line, pct_labels))
        .resolve_scale(y="independent")
        .properties(height=320, title=f"{star}★ — count (bars) & % of total (line)")
    )


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

# ---- Chart 1: total ratings (stacked by star) + avg rating, one dual-axis chart ----
st.subheader("1 · Total ratings by star & average rating")
st.altair_chart(overview_combo_chart(df), use_container_width=True)

st.divider()

# ---- Charts 2-6: per-star count (bars) + % of total (line), one dual-axis chart each ----
for star in ["5", "4", "3", "2", "1"]:
    st.subheader(f"{6 - int(star)} · {star}-star ratings — count & % of total")
    st.altair_chart(count_pct_combo(df, star, STAR_COLORS[star]), use_container_width=True)
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
