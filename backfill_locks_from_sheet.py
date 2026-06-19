"""One-time backfill of historical Locks Pro review data from the
'Target Planning Sheet - Native' (6 May -> 19 Jun 2026; no data before 6 May).

The sheet stores Locks as rating + total + per-star %, with no explicit counts,
so all per-star counts are derived as round(pct/100 * total).
Rows where the sheet has a % but no total (09 May, 06/17/18 Jun) are skipped.
Writes amazon_review_tracking_B0DJGYW9R9.csv in the canonical column order.
"""
import csv
from pathlib import Path

ASIN = "B0DJGYW9R9"
CSV_PATH = Path(__file__).parent / f"amazon_review_tracking_{ASIN}.csv"

# (date, avg, total, p5, p4, p3, p2, p1)
ROWS = [
    ("2026-05-06", 4.6, 545, 85, 7, 1, 1, 6),
    ("2026-05-07", 4.6, 550, 85, 7, 1, 1, 6),
    ("2026-05-11", 4.6, 558, 85, 7, 1, 1, 6),
    ("2026-05-13", 4.6, 514, 84, 8, 1, 1, 6),
    ("2026-05-14", 4.6, 516, 84, 8, 1, 1, 6),
    ("2026-05-15", 4.6, 518, 84, 8, 1, 1, 6),
    ("2026-05-17", 4.6, 520, 84, 8, 2, 1, 5),
    ("2026-05-18", 4.6, 521, 84, 8, 2, 1, 5),
    ("2026-05-19", 4.6, 521, 84, 8, 2, 1, 5),
    ("2026-05-20", 4.6, 521, 84, 8, 2, 1, 5),
    ("2026-05-21", 4.6, 521, 84, 8, 2, 1, 5),
    ("2026-05-23", 4.6, 529, 85, 8, 1, 1, 5),
    ("2026-05-24", 4.6, 533, 85, 8, 1, 1, 5),
    ("2026-05-25", 4.6, 535, 85, 8, 1, 1, 5),
    ("2026-05-26", 4.6, 538, 85, 8, 1, 1, 5),
    ("2026-05-27", 4.6, 539, 85, 8, 1, 1, 5),
    ("2026-05-29", 4.6, 540, 85, 7, 2, 1, 5),
    ("2026-05-30", 4.6, 541, 85, 7, 2, 1, 5),
    ("2026-06-01", 4.6, 543, 84, 8, 2, 1, 5),
    ("2026-06-02", 4.6, 544, 85, 8, 1, 1, 5),
    ("2026-06-03", 4.6, 545, 85, 8, 1, 1, 5),
    ("2026-06-04", 4.6, 546, 85, 8, 1, 1, 5),
    ("2026-06-05", 4.6, 548, 85, 8, 1, 2, 5),
    ("2026-06-08", 4.6, 550, 84, 7, 1, 2, 6),
    ("2026-06-09", 4.6, 552, 84, 7, 1, 2, 6),
    ("2026-06-10", 4.6, 555, 83, 8, 1, 2, 6),
    ("2026-06-11", 4.6, 556, 83, 8, 1, 2, 6),
    ("2026-06-12", 4.6, 557, 83, 8, 1, 2, 6),
    ("2026-06-13", 4.6, 558, 83, 8, 1, 2, 6),
    ("2026-06-15", 4.6, 560, 83, 8, 1, 2, 6),
    ("2026-06-19", 4.6, 562, 83, 8, 1, 2, 6),
]

HEADER = [
    "date", "total_ratings", "avg_stars",
    "pct_5", "pct_4", "pct_3", "pct_2", "pct_1",
    "count_5", "count_4", "count_3", "count_2", "count_1",
]

with CSV_PATH.open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(HEADER)
    for date, avg, total, p5, p4, p3, p2, p1 in ROWS:
        counts = [round(p / 100 * total) for p in (p5, p4, p3, p2, p1)]
        w.writerow([date, total, avg, p5, p4, p3, p2, p1, *counts])

print(f"Wrote {len(ROWS)} rows to {CSV_PATH.name}")
