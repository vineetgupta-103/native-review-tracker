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
import json
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
    {"asin": "B0H2MVF2L2", "label": "Locks Ultra",
     "url": "https://www.amazon.in/Native-Lock-Ultra-Urban-Company/dp/B0H2MVF2L2/"},
    # Native (for the vs-competitors comparison)
    {"asin": "B0D79G62J3", "label": "Native M1", "url": "https://www.amazon.in/dp/B0D79G62J3/"},
    # Competitors
    {"asin": "B0F6CXR97M", "label": "Atomberg Intellon", "url": "https://www.amazon.in/dp/B0F6CXR97M/"},
    {"asin": "B0DN1KJFY7", "label": "Aquaguard Ritz", "url": "https://www.amazon.in/dp/B0DN1KJFY7/"},
    {"asin": "B07PZPN3J9", "label": "Kent Grand Plus", "url": "https://www.amazon.in/dp/B07PZPN3J9/"},
    {"asin": "B0CB8KG44H", "label": "Kent Supreme Plus", "url": "https://www.amazon.in/dp/B0CB8KG44H/"},
    {"asin": "B0F5PXXWM9", "label": "Aquaguard Delight", "url": "https://www.amazon.in/dp/B0F5PXXWM9/"},
    # Smart-lock competitors
    {"asin": "B0F8VK4H3P", "label": "QUBO Optima", "url": "https://www.amazon.in/dp/B0F8VK4H3P/"},
    {"asin": "B0CCV4ZW5S", "label": "Golens X32", "url": "https://www.amazon.in/dp/B0CCV4ZW5S/"},
    {"asin": "B0CTHS9H4Z", "label": "LAVNA LA44", "url": "https://www.amazon.in/dp/B0CTHS9H4Z/"},
    {"asin": "B0C2CS3FNJ", "label": "Atomberg SL 1", "url": "https://www.amazon.in/dp/B0C2CS3FNJ/"},
    {"asin": "B0DCBMB7Q2", "label": "Mygate Plus", "url": "https://www.amazon.in/dp/B0DCBMB7Q2/"},
    {"asin": "B0FGQ65W9G", "label": "Godrej Catus Advantage", "url": "https://www.amazon.in/dp/B0FGQ65W9G/"},
    {"asin": "B0G34MC2B9", "label": "Godrej Neo Pro View", "url": "https://www.amazon.in/dp/B0G34MC2B9/"},
    {"asin": "B0GMXB2XJ5", "label": "Atomberg Cypheo Elite", "url": "https://www.amazon.in/dp/B0GMXB2XJ5/"},
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


JS_REVIEWS = """() => {
  const out = [];
  document.querySelectorAll('div[data-hook="review"]').forEach(r => {
    const author = (r.querySelector('.a-profile-name') || {}).textContent || '';
    const rating = (r.querySelector('[data-hook="review-star-rating"] .a-icon-alt, [data-hook="cmps-review-star-rating"] .a-icon-alt') || {}).textContent || '';
    const tEl = r.querySelector('[data-hook="reviewTitle"], [data-hook="review-title"]');
    let title = tEl ? (tEl.innerText || tEl.textContent || '') : '';
    title = title.split('\\n').map(s => s.trim())
      .filter(s => s && !/out of 5 stars/i.test(s)).join(' ');
    const date = (r.querySelector('[data-hook="review-date"]') || {}).textContent || '';
    const bEl = r.querySelector('[data-hook="reviewText"], [data-hook="review-body"]');
    const body = bEl ? (bEl.innerText || bEl.textContent || '') : '';
    out.push({author: author.trim(), rating: rating.trim(), title: title.trim(),
              date: date.trim(), body: body.replace(/\\s+/g,' ').trim().slice(0, 600)});
  });
  return out;
}"""


def _parse_review_date(txt):
    m = re.search(r"on (\d{1,2} \w+ \d{4})", txt)
    if not m:
        return None
    try:
        return datetime.datetime.strptime(m.group(1), "%d %B %Y").date()
    except ValueError:
        return None


def extract_extras(page, text):
    """The 'Customers say' AI summary, aspect chips, and 5 most recent reviews."""
    cs = re.search(r"Customers say\s+(.*?)\s+(?:AI )?Generated from the text", text, re.S)
    customers_say = re.sub(r"\s+", " ", cs.group(1)).strip() if cs else ""

    aspects = []
    reg = re.search(r"Select to learn more(.*?)(?:Top reviews|Reviews with images|"
                    r"Products related|Customers who|See more|How are ratings)", text, re.S)
    if reg:
        for m in re.finditer(r"([A-Za-z][A-Za-z &]+?)\s*\((\d[\d.,KkMm]*)\)", reg.group(1)):
            aspects.append({"name": m.group(1).strip(), "count": m.group(2)})

    reviews = []
    try:
        for r in page.evaluate(JS_REVIEWS):
            d = _parse_review_date(r.get("date", ""))
            rm = re.search(r"([0-9.]+)\s*out of", r.get("rating", ""))
            reviews.append({
                "author": r.get("author", ""),
                "rating": float(rm.group(1)) if rm else None,
                "title": r.get("title", ""),
                "date": d.isoformat() if d else "",
                "date_label": re.sub(r"^Reviewed in .*? on ", "", r.get("date", "")),
                "body": r.get("body", ""),
                "_o": d.toordinal() if d else 0,
            })
    except Exception as e:  # noqa: BLE001
        log(f"review extract error: {e}")
    reviews.sort(key=lambda x: x["_o"], reverse=True)
    top = reviews[:5]
    for r in top:
        r.pop("_o", None)
    return {"customers_say": customers_say, "aspects": aspects[:10], "reviews": top}


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
            text = page.inner_text("body")
            parsed = parse_reviews(text)
            if parsed:
                avg, total, pct = parsed
                return {"avg": avg, "total": total, "pct": pct,
                        "extras": extract_extras(page, text)}
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


def summary_path(asin):
    return PROJECT / f"amazon_summary_{asin}.json"


def write_summary(asin, extras, today):
    data = {"scraped": today, **extras}
    summary_path(asin).write_text(json.dumps(data, ensure_ascii=False, indent=2))


def git_push(today, files):
    def run(*args):
        return subprocess.run(["git", "-C", str(PROJECT), *args],
                              capture_output=True, text=True)
    for f in files:
        run("add", f)
    if run("diff", "--cached", "--quiet").returncode == 0:
        log("No change to commit.")
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
    files = []
    for product in PRODUCTS:
        res = results.get(product["asin"])
        if not res:
            log(f"[{product['label']}] SCRAPE FAILED — left unchanged.")
            continue
        upsert_csv(product["asin"], product["label"], res["avg"], res["total"], res["pct"])
        write_summary(product["asin"], res["extras"], today)
        files.append(csv_path(product["asin"]).name)
        files.append(summary_path(product["asin"]).name)
    if not files:
        log("All scrapes failed.")
        sys.exit(1)
    git_push(today, files)
    log("=== scrape run done ===")


if __name__ == "__main__":
    main()
