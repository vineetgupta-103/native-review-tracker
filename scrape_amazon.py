#!/usr/bin/env python3
"""
Standalone daily scraper for the Native M2 Pro review breakdown on Amazon.in.

Self-contained: uses Playwright's own bundled Chromium (no dependency on Claude
Code or the user's Chrome). Designed to be run unattended by macOS launchd.

Flow: open product page -> parse the "Customer reviews" block -> append one row
per day to the tracking CSV (dedup by date) -> git commit & push.

Exit codes: 0 = success (CSV updated/confirmed), 1 = scrape failed (CSV untouched).
"""
import csv
import datetime
import re
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT = Path(__file__).parent
ASIN = "B0G4CHKBGP"
CSV_PATH = PROJECT / f"amazon_review_tracking_{ASIN}.csv"
URL = f"https://www.amazon.in/Native-M2-Pro-Dispensing-Mineraliser/dp/{ASIN}/"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
)
HEADER = [
    "date", "total_ratings", "avg_stars",
    "pct_5", "pct_4", "pct_3", "pct_2", "pct_1",
    "count_5", "count_4", "count_3", "count_2", "count_1",
]


def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def parse_reviews(text):
    """Extract avg, total, and per-star % from the page's rendered text."""
    avg_m = re.search(r"([0-9](?:\.[0-9])?)\s*out of\s*5\s*stars", text)
    total_m = re.search(r"([0-9][0-9,]*)\s*(?:global\s*)?ratings", text)
    if not avg_m or not total_m:
        return None
    avg = float(avg_m.group(1))
    total = int(total_m.group(1).replace(",", ""))

    pct = {}
    for star in ("5", "4", "3", "2", "1"):
        # e.g. "5 star\n79%" in the histogram. Take the first match per star.
        m = re.search(rf"\b{star}\s*star\b[\s\S]{{0,12}}?(\d{{1,3}})\s*%", text)
        if not m:
            return None
        pct[star] = int(m.group(1))
    return avg, total, pct


def scrape():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="en-IN",
                                  viewport={"width": 1366, "height": 900})
        page = ctx.new_page()
        for attempt in (1, 2):
            try:
                log(f"Navigating (attempt {attempt})…")
                page.goto(URL, wait_until="domcontentloaded", timeout=60000)
                # Wait for the ratings text to be present.
                page.wait_for_function(
                    "() => /out of\\s*5\\s*stars/.test(document.body.innerText)"
                    " && /ratings/.test(document.body.innerText)",
                    timeout=30000,
                )
                text = page.inner_text("body")
                parsed = parse_reviews(text)
                if parsed:
                    browser.close()
                    return parsed
                log("Could not parse review block; retrying…")
            except Exception as e:  # noqa: BLE001
                log(f"Attempt {attempt} error: {e}")
        # Save a debug screenshot to help diagnose blocks/captchas.
        try:
            page.screenshot(path=str(PROJECT / "scrape_debug.png"))
            log("Saved scrape_debug.png")
        except Exception:
            pass
        browser.close()
        return None


def upsert_csv(avg, total, pct):
    today = datetime.date.today().isoformat()
    counts = {s: round(pct[s] / 100 * total) for s in ("5", "4", "3", "2", "1")}
    row = {
        "date": today, "total_ratings": total, "avg_stars": avg,
        "pct_5": pct["5"], "pct_4": pct["4"], "pct_3": pct["3"],
        "pct_2": pct["2"], "pct_1": pct["1"],
        "count_5": counts["5"], "count_4": counts["4"], "count_3": counts["3"],
        "count_2": counts["2"], "count_1": counts["1"],
    }

    rows = []
    if CSV_PATH.exists():
        with CSV_PATH.open() as f:
            rows = list(csv.DictReader(f))
    rows = [r for r in rows if r.get("date") != today]  # dedup today
    rows.append({k: str(v) for k, v in row.items()})
    rows.sort(key=lambda r: r["date"])

    with CSV_PATH.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        w.writerows(rows)
    log(f"Wrote row for {today}: total={total}, avg={avg}, 5★={pct['5']}%")
    return today


def git_push(today):
    def run(*args):
        return subprocess.run(
            ["git", "-C", str(PROJECT), *args],
            capture_output=True, text=True,
        )
    run("add", CSV_PATH.name)
    diff = run("diff", "--cached", "--quiet")
    if diff.returncode == 0:
        log("No CSV change to commit.")
        return
    run("-c", "user.name=Native Tracker",
        "-c", "user.email=vineetgupta@urbancompany.com",
        "commit", "-m", f"data: review snapshot for {today}")
    push = run("push")
    if push.returncode != 0:
        log(f"git push failed: {push.stderr.strip()}")
    else:
        log("Pushed to GitHub.")


def main():
    log("=== scrape run start ===")
    result = scrape()
    if not result:
        log("SCRAPE FAILED — CSV left unchanged.")
        sys.exit(1)
    avg, total, pct = result
    today = upsert_csv(avg, total, pct)
    git_push(today)
    log("=== scrape run done ===")


if __name__ == "__main__":
    main()
