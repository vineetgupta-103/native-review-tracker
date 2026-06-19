#!/usr/bin/env bash
# Manual fallback: commit & push the latest tracking CSV to GitHub.
# The daily scheduled scraper does this automatically; run this by hand if a
# push ever needs a nudge.
set -euo pipefail

REPO_DIR="/Users/vineetgupta/Documents/Native India Map - Water Quality"
CSV="amazon_review_tracking_B0G4CHKBGP.csv"

cd "$REPO_DIR"

if git diff --quiet -- "$CSV"; then
  echo "No changes in $CSV — nothing to push."
  exit 0
fi

git add "$CSV"
git -c user.name="Native Tracker" -c user.email="vineetgupta@urbancompany.com" \
  commit -m "data: manual review snapshot push"
git push
echo "Pushed latest data to GitHub."
