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

PRODUCTS = [
    {"label": "M2 Pro", "asin": "B0G4CHKBGP",
     "url": "https://www.amazon.in/Native-M2-Pro-Dispensing-Mineraliser/dp/B0G4CHKBGP/"},
    {"label": "M0", "asin": "B0FB3L3FSH",
     "url": "https://www.amazon.in/Native-RO-Mineraliser-Purifier-Unconditional/dp/B0FB3L3FSH/"},
]


def csv_path(asin):
    return Path(__file__).parent / f"amazon_review_tracking_{asin}.csv"

STAR_COLORS = {
    "5": "#1a9850",
    "4": "#91cf60",
    "3": "#fee08b",
    "2": "#fc8d59",
    "1": "#d73027",
}

st.set_page_config(
    page_title="Native — Ratings Tracker",
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


STAR_ORDER = ["5", "4", "3", "2", "1"]  # bottom -> top of the stack


def _label_rows(df):
    """Every-other-day rows for labelling — keeps charts readable at any zoom
    while still showing numbers throughout the full history. Anchored so the
    most recent day is always labelled."""
    n = len(df)
    keep = [i for i in range(n) if (n - 1 - i) % 2 == 0]
    return df.iloc[keep]


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


def _segments(df):
    """Explode each day into stacked segments with y0/y1/midpoint, so we can
    both draw the stack and place a centered % label inside each segment."""
    recs = []
    for _, r in df.iterrows():
        cum = 0.0
        for s in STAR_ORDER:
            c = float(r[f"count_{s}"])
            recs.append({
                "date": r["date"], "star": s, "count": c,
                "y0": cum, "y1": cum + c, "mid": cum + c / 2.0,
                "pct": float(r[f"pct_{s}"]),
            })
            cum += c
    seg = pd.DataFrame(recs)
    seg["pct_label"] = seg["pct"].round().astype(int).astype(str) + "%"
    return seg


def overview_combo_chart(df):
    """Stacked-by-star total ratings (with per-segment %), and the average
    rating drawn as a line floating ABOVE the bars. Labels: every other day;
    drag/scroll the x-axis to see the full history."""
    df = df.copy()
    df["count_sum"] = sum(df[f"count_{s}"] for s in STAR_ORDER)
    total_max = float(df["count_sum"].max())
    color_scale = alt.Scale(domain=STAR_ORDER, range=[STAR_COLORS[s] for s in STAR_ORDER])
    zoom = alt.selection_interval(bind="scales", encodings=["x"])

    seg = _segments(df)
    bars = (
        alt.Chart(seg)
        .mark_bar()
        .encode(
            x=alt.X("date:T", title="Date"),
            # 1.6x headroom leaves an empty band on top for the avg line.
            y=alt.Y("y0:Q", title="# ratings", scale=alt.Scale(domain=[0, total_max * 1.6])),
            y2="y1:Q",
            color=alt.Color("star:N", title="Star", scale=color_scale, sort=STAR_ORDER),
            tooltip=[
                alt.Tooltip("date:T", title="Date"),
                alt.Tooltip("star:N", title="Star"),
                alt.Tooltip("count:Q", title="# ratings", format=",.0f"),
                alt.Tooltip("pct_label:N", title="% of total"),
            ],
        )
    )

    # Per-segment % labels (every other day; skip tiny <3% segments to avoid clutter).
    label_dates = set(_label_rows(df)["date"])
    seg_lab = seg[seg["date"].isin(label_dates) & (seg["pct"] >= 3)]
    seg_pct_labels = (
        alt.Chart(seg_lab)
        .mark_text(fontSize=8, fontWeight="bold")
        .encode(
            x=alt.X("date:T"),
            y=alt.Y("mid:Q"),
            text=alt.Text("pct_label:N"),
            color=alt.Color(
                "star:N", legend=None,
                # black on the light/green bands, white only on the red 1★ band
                scale=alt.Scale(domain=STAR_ORDER,
                                range=["black", "black", "black", "black", "white"]),
            ),
        )
    )

    total_labels = (
        alt.Chart(_label_rows(df))
        .mark_text(dy=-6, fontSize=9, color="#333")
        .encode(
            x=alt.X("date:T"),
            y=alt.Y("count_sum:Q"),
            text=alt.Text("total_ratings:Q", format=",.0f"),
        )
    )
    bar_group = alt.layer(bars, seg_pct_labels, total_labels).resolve_scale(color="independent")

    # Average rating line, pushed into the top band via a high y-domain floor.
    amin, amax = float(df["avg_stars"].min()), float(df["avg_stars"].max())
    a_hi, a_lo = amax + 0.05, max(0.0, amin - 0.9)
    tick_vals = sorted({round(amin, 1), round((amin + amax) / 2, 1), round(amax, 1)})
    avg_scale = alt.Scale(domain=[a_lo, a_hi])
    avg_base = alt.Chart(df).encode(
        x=alt.X("date:T", title="Date"),
        y=alt.Y("avg_stars:Q", title="Avg stars", scale=avg_scale,
                axis=alt.Axis(orient="right", format=".1f", values=tick_vals, titleColor="#111")),
    )
    avg_line = avg_base.mark_line(point=True, color="#111", strokeWidth=2.5).encode(
        tooltip=[alt.Tooltip("date:T", title="Date"),
                 alt.Tooltip("avg_stars:Q", title="Avg stars", format=".2f")]
    )
    avg_labels = (
        alt.Chart(_label_rows(df))
        .mark_text(dy=-12, color="#111", fontWeight="bold")
        .encode(x=alt.X("date:T"), y=alt.Y("avg_stars:Q", scale=avg_scale),
                text=alt.Text("avg_stars:Q", format=".1f"))
    )
    avg_group = alt.layer(avg_line, avg_labels)

    return (
        alt.layer(bar_group, avg_group)
        .resolve_scale(y="independent")
        .add_params(zoom)
        .properties(height=440,
                    title="Avg rating ★ (above) · total ratings stacked by star, with %")
    )


def count_pct_combo(df, star, color):
    """Single dual-axis chart for one star level: absolute count as bars (left axis)
    + share of total as a line (right axis). Labels: every other day; x-axis is
    scrollable/zoomable to the full history."""
    cnt, pct = f"count_{star}", f"pct_{star}"
    df_lab = _label_rows(df)
    pct_scale = alt.Scale(domain=_pct_domain(df[pct]))
    zoom = alt.selection_interval(bind="scales", encodings=["x"])

    bars = (
        alt.Chart(df)
        .mark_bar(color=color, opacity=0.75)
        .encode(
            x=alt.X("date:T", title="Date"),
            y=alt.Y(f"{cnt}:Q", title=f"# {star}★ ratings (abs)"),
            tooltip=[
                alt.Tooltip("date:T", title="Date"),
                alt.Tooltip(f"{cnt}:Q", title=f"# {star}★", format=",.0f"),
                alt.Tooltip(f"{pct}:Q", title=f"% {star}★", format=".0f"),
            ],
        )
    )
    bar_labels = (
        alt.Chart(df_lab)
        .mark_text(dy=-6, fontSize=9, color=color)
        .encode(x=alt.X("date:T"), y=alt.Y(f"{cnt}:Q"),
                text=alt.Text(f"{cnt}:Q", format=",.0f"))
    )

    pct_base = alt.Chart(df).encode(
        x=alt.X("date:T", title="Date"),
        y=alt.Y(f"{pct}:Q", title=f"% {star}★ of total", scale=pct_scale,
                axis=alt.Axis(orient="right", format=".0f", titleColor="#111")),
    )
    line = pct_base.mark_line(point=True, color="#111", strokeWidth=2.5).encode(
        tooltip=[alt.Tooltip("date:T", title="Date"),
                 alt.Tooltip(f"{pct}:Q", title=f"% {star}★", format=".0f")]
    )
    pct_labels = (
        alt.Chart(df_lab)
        .mark_text(dy=-10, fontSize=9, color="#111", fontWeight="bold")
        .encode(x=alt.X("date:T"), y=alt.Y(f"{pct}:Q", scale=pct_scale),
                text=alt.Text(f"{pct}:Q", format=".0f"))
    )

    return (
        alt.layer(alt.layer(bars, bar_labels), alt.layer(line, pct_labels))
        .resolve_scale(y="independent")
        .add_params(zoom)
        .properties(height=320, title=f"{star}★ — count (bars) & % of total (line)")
    )


def render_product(label, asin, product_url):
    """Render the full metrics + chart set for one product (used inside a tab)."""
    df = load_data(csv_path(asin))
    if df.empty:
        st.warning(
            f"No data yet for {label}. The tracking CSV is missing or empty — "
            "it gets a new row each day from the scheduled scraper."
        )
        return

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else None

    def delta(col):
        return None if prev is None else f"{latest[col] - prev[col]:+,.0f}"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Avg rating", f"{latest['avg_stars']:.1f} ★",
              None if prev is None else f"{latest['avg_stars'] - prev['avg_stars']:+.2f}")
    c2.metric("Total ratings", f"{int(latest['total_ratings']):,}", delta("total_ratings"))
    c3.metric("Days tracked", f"{len(df)}")
    c4.metric("Latest date", latest["date"].strftime("%d %b %Y"))
    st.caption(f"[View {label} on Amazon.in]({product_url})")

    st.divider()
    st.subheader("1 · Total ratings by star & average rating")
    st.altair_chart(overview_combo_chart(df), use_container_width=True)

    st.divider()
    for star in ["5", "4", "3", "2", "1"]:
        st.subheader(f"{6 - int(star)} · {star}-star ratings — count & % of total")
        st.altair_chart(count_pct_combo(df, star, STAR_COLORS[star]), use_container_width=True)
        st.divider()

    with st.expander("Raw tracking data"):
        out = df.assign(date=df["date"].dt.strftime("%Y-%m-%d"))
        st.dataframe(out, use_container_width=True, hide_index=True)
        st.download_button("Download CSV", data=out.to_csv(index=False),
                           file_name=csv_path(asin).name, mime="text/csv", key=f"dl_{asin}")


st.markdown(
    """
    <div style="background:#1c1c1e;border-radius:16px;padding:22px 26px;
                display:flex;align-items:center;gap:18px;margin:4px 0 18px 0;
                font-family:'Source Sans Pro',sans-serif;">
      <div style="width:54px;height:54px;border-radius:14px;background:#6c4cff;
                  display:flex;align-items:center;justify-content:center;flex:0 0 auto;">
        <span style="color:#fff;font-size:26px;font-weight:700;">N</span>
      </div>
      <div>
        <div style="color:#fff;font-size:26px;font-weight:800;line-height:1.2;">
          Native — Ratings Tracker
        </div>
        <div style="color:#9b9ba3;font-size:14px;margin-top:6px;">
          Water Purifiers · Native M2 Pro &amp; M0 · Amazon.in · ratings updated daily
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

tabs = st.tabs([p["label"] for p in PRODUCTS])
for tab, p in zip(tabs, PRODUCTS):
    with tab:
        render_product(p["label"], p["asin"], p["url"])
