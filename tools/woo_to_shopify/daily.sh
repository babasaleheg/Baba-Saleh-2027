#!/bin/sh
# Daily upkeep, safe to re-run. New products get bilingual SEO/alt text, collections keep
# in-stock items first, and new WooCommerce orders are imported.
set -e
cd "$(dirname "$0")"
export DATA_DIR="${DATA_DIR:-./woo_data}"
python3 sync.py fetch
python3 sync.py orders
python3 sync.py sort-stock
python3 sync.py seo
python3 seo_bilingual.py
python3 sync.py reviews-sync
