# Native M2 Pro — Amazon.in Review Tracker

A Streamlit dashboard tracking the day-on-day customer-review star distribution of the
[Native M2 Pro Water Purifier](https://www.amazon.in/Native-M2-Pro-Dispensing-Mineraliser/dp/B0G4CHKBGP/)
(ASIN `B0G4CHKBGP`) on Amazon.in.

## Charts
1. Daily average rating + total number of ratings
2. 5★ ratings — absolute & % of total
3. 4★ ratings — absolute & % of total
4. 3★ ratings — absolute & % of total
5. 2★ ratings — absolute & % of total
6. 1★ ratings — absolute & % of total

## Data
`amazon_review_tracking_B0G4CHKBGP.csv` holds one row per day. It is appended each day
by a local scheduled scraper (drives a real Chrome browser, since Amazon blocks plain
HTTP fetches) and pushed to this repo so the deployed app stays fed.

Amazon only publishes per-star **percentages** plus the **total** ratings count — the
absolute per-star counts are derived as `round(pct/100 * total)` and are approximate.

## Run locally
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run streamlit_app.py
```

## Deploy on Streamlit Community Cloud
1. Push this repo to GitHub.
2. Go to https://share.streamlit.io → **New app** → pick this repo, branch `main`,
   main file `streamlit_app.py`.
3. Deploy. The app reboots automatically whenever a new commit (i.e. a new daily data
   row) is pushed.
