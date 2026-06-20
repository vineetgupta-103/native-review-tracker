#!/usr/bin/env python3
"""
Standalone daily scraper for Native water-purifier review breakdowns on Amazon.in.

Self-contained: uses Playwright's own bundled Chromium (no dependency on Claude
Code or the user's Chrome). Designed to be run unattended by macOS launchd.
Scrapes every product in PRODUCTS in a single browser session.

Flow: open each product page -> parse the "Customer reviews" block -> append one
row per day to that product's tracking CSV (dedup by date) -> one git commit & push.

Exit codes: 0 = at least one product updated/confirmed, 1 = all scrapes failed.
"""
import csv
import datetime
import re
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT = Path(__file__).parent

PRODUCTS = [
    {"asin": "B0G4CHKBGP", "label": "M2 Pro",
     "url": "https://www.amazon.in/Native-M2-Pro-Dispensing-Mineraliser/dp/B0G4CHKBGP/"},
    {"asin": "B0FB3L3FSH", "label": "M0",
     "url": "https://www.amazon.in/Native-RO-Mineraliser-Purifier-Unconditional/dp/B0FB3L3FSH/"},
    {"asin": "B0DJGYW9R9", "label": "Locks Pro",
     "url": "https://www.amazon.in/Native-UC-Doorbell-Installation-Warranty/dp/B0DJGYW9R9/"},
    # Native (for the vs-competitors comparison)
    {"asin": "B0D79G62J3", "label": "Native M1", "url": "https://www.amazon.in/dp/B0D79G62J3/"},
    # Competitors
    {"asin": "B0F6CXR97M", "label": "Atomberg Intellon", "url": "https://www.amazon.in/dp/B0F6CXR97M/"},
    {"asin": "B0DN1KJFY7", "label": "Aquaguard Ritz", "url": "https://www.amazon.in/dp/B0DN1KJFY7/"},
    {"asin": "B07PZPN3J9", "label": "Kent Grand Plus", "url": "https://www.amazon.in/dp/B07PZPN3J9/"},
    {"asin": "B0CB8KG44H", "label": "Kent Supreme Plus", "url": "https://www.amazon.in/dp/B0CB8KG44H/"},
    {"asin": "B0F5PXXWM9", "label": "Aquaguard Delight", "url": "https://www.amazon.in/dp/B0F5PXXWM9/"},
]

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
)
HEADER = [
    "date", "total_ratings", "avg_stars",
    "pct_5", "pct_4", "pct_3", "pct_2", "pct_1",
    "count_5", "count_4", "count_3", "count_2", "count_1",
]


def csv_path(asin):
    return PROJECT / f"amazon_review_tracking_{asin}.csv"


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


def scrape_one(page, product):
    url, label = product["url"], product["label"]
    for attempt in (1, 2):
        try:
            log(f"[{label}] Navigating (attempt {attempt})…")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_function(
                "() => /out of\\s*5\\s*stars/.test(document.body.innerText)"
                " && /ratings/.test(document.body.innerText)",
                timeout=30000,
            )
            parsed = parse_reviews(page.inner_text("body"))
            if parsed:
                return parsed
            log(f"[{label}] Could not parse review block; retrying…")
        except Exception as e:  # noqa: BLE001
            log(f"[{label}] Attempt {attempt} error: {e}")
    try:
        page.screenshot(path=str(PROJECT / f"scrape_debug_{product['asin']}.png"))
        log(f"[{label}] Saved scrape_debug_{product['asin']}.png")
    except Exception:
        pass
    return None


def scrape_all():
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="en-IN",
                                  viewport={"width": 1366, "height": 900})
        page = ctx.new_page()
        for product in PRODUCTS:
            results[product["asin"]] = scrape_one(page, product)
        browser.close()
    return results


def upsert_csv(asin, label, avg, total, pct):
    today = datetime.date.today().isoformat()
    counts = {s: round(pct[s] / 100 * total) for s in ("5", "4", "3", "2", "1")}
    row = {
        "date": today, "total_ratings": total, "avg_stars": avg,
        "pct_5": pct["5"], "pct_4": pct["4"], "pct_3": pct["3"],
        "pct_2": pct["2"], "pct_1": pct["1"],
        "count_5": counts["5"], "count_4": counts["4"], "count_3": counts["3"],
        "count_2": counts["2"], "count_1": counts["1"],
    }
    path = csv_path(asin)
    rows = []
    if path.exists():
        with path.open() as f:
            rows = list(csv.DictReader(f))
    rows = [r for r in rows if r.get("date") != today]  # dedup today
    rows.append({k: str(v) for k, v in row.items()})
    rows.sort(key=lambda r: r["date"])
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        w.writerows(rows)
    log(f"[{label}] Wrote row for {today}: total={total}, avg={avg}, 5★={pct['5']}%")


def git_push(today, changed):
    def run(*args):
        return subprocess.run(["git", "-C", str(PROJECT), *args],
                              capture_output=True, text=True)
    for asin in changed:
        run("add", csv_path(asin).name)
    if run("diff", "--cached", "--quiet").returncode == 0:
        log("No CSV change to commit.")
        return
    run("-c", "user.name=Native Tracker",
        "-c", "user.email=vineetgupta@urbancompany.com",
        "commit", "-m", f"data: review snapshot for {today}")
    push = run("push")
    log("Pushed to GitHub." if push.returncode == 0
        else f"git push failed: {push.stderr.strip()}")


def main():
    log("=== scrape run start ===")
    results = scrape_all()
    today = datetime.date.today().isoformat()
    changed = []
    for product in PRODUCTS:
        parsed = results.get(product["asin"])
        if not parsed:
            log(f"[{product['label']}] SCRAPE FAILED — CSV left unchanged.")
            continue
        avg, total, pct = parsed
        upsert_csv(product["asin"], product["label"], avg, total, pct)
        changed.append(product["asin"])
    if not changed:
        log("All scrapes failed.")
        sys.exit(1)
    git_push(today, changed)
    log("=== scrape run done ===")


if __name__ == "__main__":
    main()
