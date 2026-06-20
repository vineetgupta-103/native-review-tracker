"""
Native M2 Pro Water Purifier — Amazon.in review tracker dashboard.

Reads amazon_review_tracking_B0G4CHKBGP.csv (one row per day, appended by the
scheduled scraper) and renders day-on-day charts of the rating distribution.
"""

import html
import json
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
    {"label": "M1", "asin": "B0D79G62J3",
     "url": "https://www.amazon.in/dp/B0D79G62J3/"},
    {"label": "Locks Pro", "asin": "B0DJGYW9R9",
     "url": "https://www.amazon.in/Native-UC-Doorbell-Installation-Warranty/dp/B0DJGYW9R9/"},
    {"label": "Locks Ultra", "asin": "B0H2MVF2L2",
     "url": "https://www.amazon.in/Native-Lock-Ultra-Urban-Company/dp/B0H2MVF2L2/"},
]


def csv_path(asin):
    return Path(__file__).parent / f"amazon_review_tracking_{asin}.csv"


@st.cache_data(ttl=60)
def load_summary(asin):
    """Per-product 'Customers say' summary, aspect chips and recent reviews."""
    path = Path(__file__).parent / f"amazon_summary_{asin}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


# --- Water purifiers: comparison line + competitor cards ---
PURIFIER_COMPETITORS = [
    {"label": "Atomberg Intellon", "brand": "Atomberg", "asin": "B0F6CXR97M", "color": "#f59e0b"},
    {"label": "Aquaguard Ritz", "brand": "Aquaguard", "asin": "B0DN1KJFY7", "color": "#2563eb"},
    {"label": "Kent Grand Plus", "brand": "Kent", "asin": "B07PZPN3J9", "color": "#dc2626"},
    {"label": "Kent Supreme Plus", "brand": "Kent", "asin": "B0CB8KG44H", "color": "#9333ea"},
    {"label": "Aquaguard Delight", "brand": "Aquaguard", "asin": "B0F5PXXWM9", "color": "#0d9488"},
]
PURIFIER_COMPARISON = [
    {"label": "Native M2 Pro", "asin": "B0G4CHKBGP", "color": "#6c4cff", "native": True},
    {"label": "Native M0", "asin": "B0FB3L3FSH", "color": "#16a34a", "native": True},
    {"label": "Native M1", "asin": "B0D79G62J3", "color": "#0891b2", "native": True},
] + [{"label": c["label"], "asin": c["asin"], "color": c["color"], "native": False}
     for c in PURIFIER_COMPETITORS]

# --- Smart locks: comparison line + competitor cards ---
LOCK_COMPETITORS = [
    {"label": "QUBO Optima", "brand": "QUBO", "asin": "B0F8VK4H3P", "color": "#06b6d4"},
    {"label": "Golens X32", "brand": "Golens", "asin": "B0CCV4ZW5S", "color": "#84cc16"},
    {"label": "LAVNA LA44", "brand": "LAVNA", "asin": "B0CTHS9H4Z", "color": "#db2777"},
    {"label": "Atomberg SL 1", "brand": "Atomberg", "asin": "B0C2CS3FNJ", "color": "#2563eb"},
    {"label": "Mygate Plus", "brand": "Mygate", "asin": "B0DCBMB7Q2", "color": "#9333ea"},
    {"label": "Godrej Catus Advantage", "brand": "Godrej", "asin": "B0FGQ65W9G", "color": "#d97706"},
    {"label": "Godrej Neo Pro View", "brand": "Godrej", "asin": "B0G34MC2B9", "color": "#0d9488"},
    {"label": "Atomberg Cypheo Elite", "brand": "Atomberg", "asin": "B0GMXB2XJ5", "color": "#dc2626"},
]
LOCK_COMPARISON = [
    {"label": "Native Locks Pro", "asin": "B0DJGYW9R9", "color": "#6c4cff", "native": True},
    {"label": "Native Locks Ultra", "asin": "B0H2MVF2L2", "color": "#16a34a", "native": True},
] + [{"label": c["label"], "asin": c["asin"], "color": c["color"], "native": False}
     for c in LOCK_COMPETITORS]

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

GSHEET_URL = "https://docs.google.com/spreadsheets/d/1SMTlR8oeegom6rSxsL4mc8sbkhvnGsbNV0ihZ0uDaV0/edit"

st.markdown(
    """
    <style>
      :root { --accent:#6c4cff; --good:#1a9850; --bad:#d73027; }
      .stApp { background:#f4f5f7; }
      .block-container { padding-top:1.3rem; padding-bottom:2rem; max-width:1180px; }
      #MainMenu, footer, [data-testid="stDecoration"] { visibility:hidden; }

      /* Tabs — purple active underline */
      .stTabs [data-baseweb="tab-list"] { gap:26px; border-bottom:1px solid #e6e6ea; }
      .stTabs [data-baseweb="tab"] { font-size:16px; font-weight:600; color:#7a7a86; padding:6px 2px; }
      .stTabs [data-baseweb="tab"][aria-selected="true"] { color:#1c1c1e; }
      .stTabs [data-baseweb="tab-highlight"],
      .stTabs [data-baseweb="tab-border"] { background-color:var(--accent); height:3px; }

      /* Chart cards (st.container keyed with 'chartcard') become white cards */
      [class*="st-key-chartcard"] {
        background:#fff; border:1px solid #ececf0 !important; border-radius:14px !important;
        box-shadow:0 1px 3px rgba(16,17,33,.04); padding:18px 20px;
      }

      /* Executive summary */
      .exec-wrap { background:#fff; border:1px solid #ececf0; border-radius:16px;
        padding:20px 22px; margin-bottom:18px; box-shadow:0 1px 3px rgba(16,17,33,.04); }
      .exec-label { border-left:4px solid var(--accent); padding-left:10px; font-size:12px;
        letter-spacing:.08em; font-weight:700; color:#3a3a44; margin-bottom:16px; }
      .exec-cards { display:flex; gap:16px; flex-wrap:wrap; }
      .exec-card { flex:1 1 200px; background:#fafafb; border:1px solid #eee; border-radius:12px;
        padding:16px 18px; border-top-width:3px; border-top-style:solid; }
      .exec-card .t { font-size:11px; letter-spacing:.06em; font-weight:700; color:#8a8a95; }
      .exec-card .v { font-size:30px; font-weight:800; color:#1c1c1e; margin-top:6px; line-height:1.1; }
      .exec-card .d { font-size:13px; font-weight:700; margin-top:4px; }
      .exec-card .s { font-size:12px; color:#9b9ba3; margin-top:8px; }

      /* Section headings inside cards */
      .sec-title { font-size:18px; font-weight:700; color:#1c1c1e; }
      .sec-sub { font-size:13px; color:#8a8a95; margin-top:2px; margin-bottom:6px; }

      /* Competitor rating-distribution cards */
      .cc-grid { display:flex; flex-wrap:wrap; gap:14px; margin-top:4px; }
      .cc-card { flex:1 1 205px; max-width:320px; background:#fff; border:1px solid #ececf0;
        border-radius:14px; padding:16px 18px; box-shadow:0 1px 3px rgba(16,17,33,.04); }
      .cc-head { display:flex; justify-content:space-between; align-items:flex-start; gap:8px; }
      .cc-name { font-size:15px; font-weight:700; color:#1c1c1e; line-height:1.2; }
      .cc-brand { font-size:12px; color:#8a8a95; margin-top:3px; }
      .cc-rating { font-size:23px; font-weight:800; white-space:nowrap; }
      .cc-meta { font-size:12px; color:#6b6b76; margin:8px 0 12px; }
      .cc-row { display:flex; align-items:center; gap:8px; margin:5px 0; }
      .cc-star { font-size:11px; color:#8a8a95; width:24px; }
      .cc-track { flex:1; height:6px; background:#ececef; border-radius:4px; overflow:hidden; }
      .cc-fill { height:100%; border-radius:4px; }
      .cc-pct { font-size:11px; color:#6b6b76; width:36px; text-align:right; }
      .cc-link { display:inline-block; margin-top:12px; font-size:12px; font-weight:600;
        color:#ff7a1a; text-decoration:none; }

      /* Customers-say summary + aspect chips */
      .cs-text { font-size:14px; color:#33333a; line-height:1.6; }
      .aspect-wrap { display:flex; flex-wrap:wrap; gap:8px; margin-top:14px; }
      .aspect-chip { font-size:12px; color:#0a7d33; background:#eef7f0; border:1px solid #d6ebdc;
        border-radius:16px; padding:4px 11px; }
      .aspect-chip b { font-weight:700; }
      .cs-credit { font-size:11px; color:#9b9ba3; margin-top:10px; }

      /* Recent reviews */
      .rev { padding:13px 0; border-top:1px solid #f0f0f3; }
      .rev:first-child { border-top:none; }
      .rev-stars { color:#f5a623; font-size:13px; letter-spacing:1px; }
      .rev-title { font-weight:700; font-size:14px; color:#1c1c1e; margin-left:6px; }
      .rev-meta { font-size:12px; color:#8a8a95; margin:3px 0 6px; }
      .rev-body { font-size:13px; color:#44444c; line-height:1.55; }
    </style>
    """,
    unsafe_allow_html=True,
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


def _section(title, subtitle):
    st.markdown(f'<div class="sec-title">{title}</div>'
                f'<div class="sec-sub">{subtitle}</div>', unsafe_allow_html=True)


def _exec_card(title, value, delta_txt, good, sub):
    color = "var(--good)" if good else "var(--bad)"
    return (
        f'<div class="exec-card" style="border-top-color:{color}">'
        f'<div class="t">{title}</div>'
        f'<div class="v">{value}</div>'
        f'<div class="d" style="color:{color}">{delta_txt}</div>'
        f'<div class="s">{sub}</div></div>'
    )


def _executive_summary(label, df):
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    d_avg = latest["avg_stars"] - prev["avg_stars"]
    d_tot = latest["total_ratings"] - prev["total_ratings"]
    d_p5 = latest["pct_5"] - prev["pct_5"]
    d_p1 = latest["pct_1"] - prev["pct_1"]
    cards = "".join([
        _exec_card("AVG RATING", f"{latest['avg_stars']:.1f} ★", f"{d_avg:+.2f}",
                   d_avg >= 0, "Amazon overall rating"),
        _exec_card("TOTAL RATINGS", f"{int(latest['total_ratings']):,}", f"{d_tot:+,.0f}",
                   d_tot >= 0, "Cumulative # of ratings"),
        _exec_card("5★ SHARE", f"{int(latest['pct_5'])}%", f"{d_p5:+.0f}pp",
                   d_p5 >= 0, "Share of 5-star ratings"),
        _exec_card("1★ SHARE", f"{int(latest['pct_1'])}%", f"{d_p1:+.0f}pp",
                   d_p1 <= 0, "Share of 1-star ratings (lower is better)"),
    ])
    st.markdown(
        f'<div class="exec-wrap"><div class="exec-label">EXECUTIVE SUMMARY — {label.upper()}'
        f' · {len(df)} DAY{"" if len(df) == 1 else "S"} · {latest["date"].strftime("%d %b %Y")}</div>'
        f'<div class="exec-cards">{cards}</div></div>',
        unsafe_allow_html=True,
    )


def _competitor_card(item, df):
    latest = df.iloc[-1]
    avg = float(latest["avg_stars"])
    total = int(latest["total_ratings"])
    p5 = int(latest["pct_5"])
    bars = ""
    for s in ["5", "4", "3", "2", "1"]:
        pct = int(latest[f"pct_{s}"])
        bars += (
            f'<div class="cc-row"><span class="cc-star">{s}★</span>'
            f'<div class="cc-track"><div class="cc-fill" style="width:{pct}%;'
            f'background:{STAR_COLORS[s]}"></div></div>'
            f'<span class="cc-pct">{pct}%</span></div>'
        )
    return (
        f'<div class="cc-card"><div class="cc-head">'
        f'<div><div class="cc-name">{item["label"]}</div>'
        f'<div class="cc-brand">{item["brand"]}</div></div>'
        f'<div class="cc-rating" style="color:{item["color"]}">{avg:.1f} ★</div></div>'
        f'<div class="cc-meta">{total:,} ratings · {p5}% are 5★</div>'
        f'<div>{bars}</div>'
        f'<a class="cc-link" href="https://www.amazon.in/dp/{item["asin"]}/" target="_blank">'
        f'View on Amazon ↗</a></div>'
    )


def _competitor_cards(competitors):
    cards = "".join(_competitor_card(c, load_data(csv_path(c["asin"])))
                    for c in competitors if not load_data(csv_path(c["asin"])).empty)
    if not cards:
        st.info("Competitor snapshots appear once the daily scraper runs.")
        return
    st.markdown(f'<div class="cc-grid">{cards}</div>', unsafe_allow_html=True)


def render_versus(comparison, competitors, key):
    """Day-on-day average-rating line chart (Native vs competitors) + today's
    competitor rating-distribution cards."""
    frames = []
    for item in comparison:
        d = load_data(csv_path(item["asin"]))
        if d.empty:
            continue
        sub = d[["date", "avg_stars"]].copy()
        sub["product"] = item["label"]
        frames.append(sub)

    with st.container(border=True, key=f"chartcard_{key}"):
        _section("Average rating — Native vs competitors",
                 "Daily Amazon average rating (Native = solid bold, competitors = dashed). "
                 "Series with only today's data show as a dot until more days accrue. Drag the x-axis to zoom.")
        if not frames:
            st.warning("No comparison data yet — it builds once the daily scraper runs.")
        else:
            long = pd.concat(frames, ignore_index=True)
            order = [i["label"] for i in comparison]
            colors = [i["color"] for i in comparison]
            natives = [i["label"] for i in comparison if i["native"]]
            comps = [i["label"] for i in comparison if not i["native"]]
            lo = max(0.0, float(long["avg_stars"].min()) - 0.15)
            hi = min(5.0, float(long["avg_stars"].max()) + 0.12)
            zoom = alt.selection_interval(bind="scales", encodings=["x"])
            base = alt.Chart(long).encode(
                x=alt.X("date:T", title="Date"),
                y=alt.Y("avg_stars:Q", title="Avg rating (★)", scale=alt.Scale(domain=[lo, hi])),
                color=alt.Color("product:N", title=None, sort=order,
                                scale=alt.Scale(domain=order, range=colors),
                                legend=alt.Legend(orient="bottom", columns=3, symbolType="stroke")),
                tooltip=[alt.Tooltip("date:T", title="Date"),
                         alt.Tooltip("product:N", title="Product"),
                         alt.Tooltip("avg_stars:Q", title="Avg rating", format=".1f")],
            )
            comp_line = (base.transform_filter(alt.FieldOneOfPredicate(field="product", oneOf=comps))
                         .mark_line(point=True, strokeWidth=1.6, opacity=0.85, strokeDash=[4, 2]))
            native_line = (base.transform_filter(alt.FieldOneOfPredicate(field="product", oneOf=natives))
                           .mark_line(point=True, strokeWidth=3))
            st.altair_chart(alt.layer(comp_line, native_line).add_params(zoom).properties(height=470),
                            use_container_width=True)

    _section("Competitor reviews — today's snapshot",
             "Rating distribution per competitor as of the latest scrape.")
    _competitor_cards(competitors)


def _render_amazon_voice(asin):
    """Bottom-of-tab: Amazon 'Customers say' summary + chips, and 5 recent reviews."""
    s = load_summary(asin)
    if not s:
        return

    if s.get("customers_say") or s.get("aspects"):
        with st.container(border=True, key=f"saycard_{asin}"):
            _section("Customers say", "Amazon's AI-generated summary of customer reviews")
            if s.get("customers_say"):
                st.markdown(f'<div class="cs-text">{html.escape(s["customers_say"])}</div>',
                            unsafe_allow_html=True)
            if s.get("aspects"):
                chips = "".join(
                    f'<span class="aspect-chip">{html.escape(a["name"])} <b>({a["count"]})</b></span>'
                    for a in s["aspects"])
                st.markdown(f'<div class="aspect-wrap">{chips}</div>', unsafe_allow_html=True)
            st.markdown('<div class="cs-credit">Generated from the text of customer reviews · '
                        'refreshed daily</div>', unsafe_allow_html=True)

    revs = s.get("reviews") or []
    if revs:
        with st.container(border=True, key=f"revcard_{asin}"):
            _section("Recent reviews", "5 most recent reviews on Amazon (refreshed daily)")
            blocks = ""
            for r in revs:
                full = int(round(r.get("rating") or 0))
                stars = "★" * full + "☆" * (5 - full)
                blocks += (
                    f'<div class="rev"><div><span class="rev-stars">{stars}</span>'
                    f'<span class="rev-title">{html.escape(r.get("title") or "")}</span></div>'
                    f'<div class="rev-meta">{html.escape(r.get("date_label") or "")} · '
                    f'{html.escape(r.get("author") or "")}</div>'
                    f'<div class="rev-body">{html.escape(r.get("body") or "")}</div></div>'
                )
            blocks += (
                f'<a class="cc-link" href="https://www.amazon.in/product-reviews/{asin}/?sortBy=recent"'
                f' target="_blank">See all reviews on Amazon ↗</a>'
            )
            st.markdown(blocks, unsafe_allow_html=True)


def render_product(label, asin, product_url):
    """Render the executive summary + chart set for one product (used inside a tab)."""
    df = load_data(csv_path(asin))
    if df.empty:
        st.warning(
            f"No data yet for {label}. The tracking CSV is missing or empty — "
            "it gets a new row each day from the scheduled scraper."
        )
        return

    _executive_summary(label, df)

    with st.container(border=True, key=f"chartcard_{asin}_overview"):
        _section("Total ratings by star & average rating",
                 "Daily total ratings split by star (stacked bars), with the average rating line above.")
        st.altair_chart(overview_combo_chart(df), use_container_width=True)

    for star in ["5", "4", "3", "2", "1"]:
        with st.container(border=True, key=f"chartcard_{asin}_{star}"):
            _section(f"{star}-star ratings",
                     "Daily count (bars, left axis) and share of total (line, right axis).")
            st.altair_chart(count_pct_combo(df, star, STAR_COLORS[star]), use_container_width=True)

    with st.expander("Raw tracking data"):
        out = df.assign(date=df["date"].dt.strftime("%Y-%m-%d"))
        st.dataframe(out, use_container_width=True, hide_index=True)
        st.download_button("Download CSV", data=out.to_csv(index=False),
                           file_name=csv_path(asin).name, mime="text/csv", key=f"dl_{asin}")
        st.caption(f"[View {label} on Amazon.in]({product_url})")

    _render_amazon_voice(asin)


st.markdown(
    f"""
    <div style="background:#1c1c1e;border-radius:16px;padding:22px 26px;
                display:flex;align-items:center;justify-content:space-between;gap:18px;
                margin:4px 0 18px 0;font-family:'Source Sans Pro',sans-serif;">
      <div style="display:flex;align-items:center;gap:18px;">
        <div style="width:54px;height:54px;border-radius:14px;background:#6c4cff;
                    display:flex;align-items:center;justify-content:center;flex:0 0 auto;">
          <span style="color:#fff;font-size:26px;font-weight:700;">N</span>
        </div>
        <div>
          <div style="color:#fff;font-size:26px;font-weight:800;line-height:1.2;">
            Native — Ratings Tracker
          </div>
          <div style="color:#9b9ba3;font-size:14px;margin-top:6px;">
            Native · M2 Pro &amp; M0 purifiers · Locks Pro · Amazon.in · ratings updated daily
          </div>
        </div>
      </div>
      <a href="{GSHEET_URL}" target="_blank" style="background:#2b2b30;border:1px solid #46464d;
         color:#fff;padding:9px 16px;border-radius:9px;text-decoration:none;font-size:13px;
         font-weight:600;white-space:nowrap;flex:0 0 auto;">Google Sheet</a>
    </div>
    """,
    unsafe_allow_html=True,
)

tabs = st.tabs([p["label"] for p in PRODUCTS]
               + ["Water Purifier vs Competitors", "Locks vs Competitors"])
for tab, p in zip(tabs, PRODUCTS):
    with tab:
        render_product(p["label"], p["asin"], p["url"])
with tabs[len(PRODUCTS)]:
    render_versus(PURIFIER_COMPARISON, PURIFIER_COMPETITORS, key="purifier_vs")
with tabs[len(PRODUCTS) + 1]:
    render_versus(LOCK_COMPARISON, LOCK_COMPETITORS, key="locks_vs")
