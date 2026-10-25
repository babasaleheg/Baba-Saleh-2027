#!/bin/sh
# Daily upkeep, safe to re-run. New products are put in the right category, get readable
# names / web addresses, tidy sizes and colours, English + Arabic text and SEO / alt text;
# collections keep in-stock items first and are checked for products that don't belong. Items that need a person end up in quality_report.json.
# A step that fails (e.g. a dropped connection) is retried once; the others still run.
cd "$(dirname "$0")"
export DATA_DIR="${DATA_DIR:-./woo_data}"
mkdir -p "$DATA_DIR"
failed=""
step() {
  python3 "$@" || { sleep 30; python3 "$@"; } || failed="$failed $*;"
}
step categorize.py
step product_quality.py
step collection_audit.py
step sync.py seo
step seo_bilingual.py
step sync.py sort-stock
step sync.py reviews-sync
step came_from.py
step recommendations.py
step search_words.py
if [ -n "$failed" ]; then
  echo "FAILED:$failed"
  exit 1
fi
echo "daily upkeep OK"
