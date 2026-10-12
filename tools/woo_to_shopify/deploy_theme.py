"""Copy the live theme and upload every theme file that differs from this repo.

    python3 deploy_theme.py            # new unpublished copy, prints its preview URL
    python3 deploy_theme.py --publish  # also publish it when the upload is clean

config/settings_data.json is merged, not replaced: the copy keeps every setting made in
the theme editor and only gets the keys this repo sets (e.g. gtm_id, whatsapp_number).
Needs the write_themes scope.
"""
import base64, hashlib, json, os, re, sys, time

from sync import gql, log

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
DIRS = ("assets", "config", "layout", "locales", "sections", "snippets", "templates")
REPO_SETTINGS = ("gtm_id", "whatsapp_number", "color_schemes", "color_highlight", "font_pairing")

THEMES_Q = "{ themes(first: 20) { nodes { id name role } } }"
FILES_Q = """query($id: ID!, $after: String) { theme(id: $id) { files(first: 250, after: $after) {
  pageInfo { hasNextPage endCursor } nodes { filename checksumMd5 } } } }"""
FILE_BODY_Q = """query($id: ID!, $names: [String!]) { theme(id: $id) { files(filenames: $names, first: 5) {
  nodes { filename body { ... on OnlineStoreThemeFileBodyText { content } } } } } }"""
DUPLICATE = """mutation($id: ID!, $name: String) { themeDuplicate(id: $id, name: $name) {
  newTheme { id name } userErrors { field message } } }"""
UPSERT = """mutation($id: ID!, $files: [OnlineStoreThemeFilesUpsertFileInput!]!) {
  themeFilesUpsert(themeId: $id, files: $files) { upsertedThemeFiles { filename } userErrors { field message } } }"""
PUBLISH = """mutation($id: ID!) { themePublish(id: $id) { theme { id role } userErrors { field message } } }"""


def strip_comments(text):
    return json.loads(re.sub(r"/\*.*?\*/", "", text, flags=re.S))


def remote_sums(theme_id):
    sums, after = {}, None
    while True:
        page = gql(FILES_Q, {"id": theme_id, "after": after})["theme"]["files"]
        sums.update({f["filename"]: f["checksumMd5"] for f in page["nodes"]})
        if not page["pageInfo"]["hasNextPage"]:
            return sums
        after = page["pageInfo"]["endCursor"]


def main():
    live = next(t for t in gql(THEMES_Q)["themes"]["nodes"] if t["role"] == "MAIN")
    name = f"Baba Saleh 2027 – {time.strftime('%Y-%m-%d %H:%M')}"
    r = gql(DUPLICATE, {"id": live["id"], "name": name})["themeDuplicate"]
    if r["userErrors"]:
        sys.exit(f"duplicate failed: {r['userErrors']}")
    theme_id = r["newTheme"]["id"]
    log("copied", live["name"], "->", name, theme_id)
    for _ in range(60):  # the copy fills in asynchronously
        sums = remote_sums(theme_id)
        if len(sums) >= len(remote_sums(live["id"])):
            break
        time.sleep(3)

    uploads = []
    for d in DIRS:
        for fn in sorted(os.listdir(os.path.join(ROOT, d))):
            path = f"{d}/{fn}"
            raw = open(os.path.join(ROOT, path), "rb").read()
            if path == "config/settings_data.json":
                body = gql(FILE_BODY_Q, {"id": theme_id, "names": [path]})["theme"]["files"]["nodes"][0]["body"]["content"]
                data, repo = strip_comments(body), strip_comments(raw.decode())
                for key in REPO_SETTINGS:
                    if repo["current"].get(key):
                        data["current"][key] = repo["current"][key]
                raw = json.dumps(data, ensure_ascii=False, indent=2).encode()
            if sums.get(path) == hashlib.md5(raw).hexdigest():
                continue
            text = raw.decode("utf-8", errors="strict") if not fn.endswith((".png", ".jpg", ".woff2", ".ico")) else None
            body = {"type": "TEXT", "value": text} if text is not None else {"type": "BASE64", "value": base64.b64encode(raw).decode()}
            uploads.append({"filename": path, "body": body})
    log("uploading", len(uploads), "files:", ", ".join(u["filename"] for u in uploads))
    errors = []
    for i in range(0, len(uploads), 20):
        r = gql(UPSERT, {"id": theme_id, "files": uploads[i:i + 20]})["themeFilesUpsert"]
        errors += r["userErrors"]
    if errors:
        log("upload errors:", errors)
    numeric = theme_id.rsplit("/", 1)[1]
    log("preview: https://babasaleh.myshopify.com/?preview_theme_id=" + numeric)
    if "--publish" in sys.argv and not errors:
        r = gql(PUBLISH, {"id": theme_id})["themePublish"]
        log("published" if not r["userErrors"] else f"publish failed: {r['userErrors']}")
    print(numeric)


if __name__ == "__main__":
    main()
