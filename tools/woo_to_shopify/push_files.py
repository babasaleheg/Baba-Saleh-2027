"""Upload repo theme files to an existing theme: python3 push_files.py <theme_id> path [path...]"""
import os, sys

from deploy_theme import ROOT, UPSERT
from sync import gql, log

tid = f"gid://shopify/OnlineStoreTheme/{sys.argv[1]}"
files = [{"filename": p, "body": {"type": "TEXT", "value": open(os.path.join(ROOT, p), encoding="utf-8").read()}} for p in sys.argv[2:]]
out = gql(UPSERT, {"id": tid, "files": files})["themeFilesUpsert"]
log(f"uploaded {len(out['upsertedThemeFiles'] or [])} files {out['userErrors'] or ''}")
