"""Turn WordPress/Elementor page HTML into clean HTML for Shopify pages.

Usage: python3 -I build_pages.py <raw_dir> <out_dir>
Writes <out_dir>/pages/<handle>.html and <out_dir>/pages.json (title, handle, file).
"""
import html
import json
import os
import re
import sys
import urllib.parse
from html.parser import HTMLParser

RAW, OUT = sys.argv[1], sys.argv[2]
# WordPress pages that Shopify provides itself, or that only exist for the old theme.
SKIP = {"my-account", "checkout", "cart", "sample-page", "wishlist", "portfolio", "shop",
        "compare", "blog", "home-base", "categories", "refund_returns",
        # WPForms job applications: need a Shopify form app, see README.
        "maadi-branch-hiring", "october-branch-hiring"}
KEEP = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "li", "strong", "b", "em", "i",
        "a", "img", "br", "table", "thead", "tbody", "tr", "td", "th", "blockquote"}
BLOCK = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td", "th", "blockquote"}
DROP_CONTENT = {"script", "style", "noscript", "svg", "form", "button", "select", "iframe"}


def link(href):
    """Point old site links at their Shopify equivalents."""
    u = urllib.parse.urlsplit(html.unescape(href))
    if u.netloc not in ("babasaleh.com", "www.babasaleh.com"):
        return href
    path = u.path
    for old, new in (("/product/", "/products/"), ("/product-category/", "/collections/")):
        if path.startswith(old):
            slug = path.rstrip("/").split("/")[-1]
            return new + slug
    if path in ("/", ""):
        return "/"
    slug = re.sub(r"-+", "-", path.strip("/").split("/")[-1])
    return {"shop": "/collections/all"}.get(slug, "/pages/" + slug)


def image(src):
    u = urllib.parse.urlsplit(html.unescape(src))
    if u.netloc in ("babasaleh.com", "www.babasaleh.com"):
        return "https://i0.wp.com/babasaleh.com" + u.path + "?ssl=1"
    return urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, "ssl=1" if "wp.com" in u.netloc else u.query, ""))


class Cleaner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip, self.block = [], 0, 0

    def handle_starttag(self, tag, attrs):
        if tag in DROP_CONTENT:
            self.skip += 1
            return
        if self.skip or tag not in KEEP:
            return
        a = dict(attrs)
        if tag in BLOCK:
            self.block += 1
        if tag == "a":
            self.out.append(f'<a href="{html.escape(link(a.get("href", "#")))}">')
        elif tag == "img":
            src = a.get("data-src") or a.get("src") or ""
            if src and not src.startswith("data:"):
                self.out.append(f'<img src="{html.escape(image(src))}" alt="{html.escape(a.get("alt", ""))}">')
        else:
            self.out.append(f"<{tag}>")

    def handle_endtag(self, tag):
        if tag in DROP_CONTENT:
            self.skip = max(0, self.skip - 1)
            return
        if not self.skip and tag in KEEP and tag not in ("img", "br"):
            self.out.append(f"</{tag}>")
            if tag in BLOCK:
                self.block = max(0, self.block - 1)

    def handle_data(self, data):
        if self.skip:
            return
        data = html.escape(re.sub(r"\s+", " ", data))
        # Elementor keeps headings and captions in bare divs: give loose text a paragraph.
        if not self.block and data.strip():
            data = f"<p>{data.strip()}</p>"
        self.out.append(data)


def clean(raw):
    # Woodmart counters render "0" and animate to data-final with JavaScript.
    raw = re.sub(r'data-final="([^"]+)">\s*0\s*<', r'>\1<', raw)
    c = Cleaner()
    c.feed(raw)
    s = "".join(c.out)
    # Unwrap placeholder links ("#") and links into the Elementor template library.
    s = re.sub(r'<a href="(?:#|https://library\.elementor\.com[^"]*)">(.*?)</a>', r"\1", s, flags=re.S)
    # Collapse empty elements left behind by removed layout wrappers.
    for _ in range(3):
        s = re.sub(r"<(p|h\d|li|ul|ol|strong|b|em|i|a[^>]*)>\s*</\w+>", "", s)
    s = re.sub(r"\s*(<(?:/?(?:p|h\d|ul|ol|li|table|tr|blockquote))>)\s*", r"\1", s)
    s = re.sub(r"(</(?:p|h\d|ul|ol|table|blockquote)>)", r"\1\n", s)
    return s.strip()


os.makedirs(os.path.join(OUT, "pages"), exist_ok=True)
# Images already copied into Shopify Files (old URL -> Shopify CDN URL).
MEDIA_MAP = os.path.join(OUT, "media_map.json")
media = json.load(open(MEDIA_MAP)) if os.path.exists(MEDIA_MAP) else {}
pages = json.load(open(os.path.join(RAW, "pages.json"), encoding="utf-8"))
index = []
for p in pages:
    if p["slug"] in SKIP:
        continue
    handle = urllib.parse.unquote(p["slug"])
    body = clean(p["content"]["rendered"])
    for old, new in media.items():
        body = body.replace(html.escape(old), new).replace(old, new)
    path = os.path.join(OUT, "pages", f"{handle}.html")
    open(path, "w", encoding="utf-8").write(body + "\n")
    index.append({"title": html.unescape(p["title"]["rendered"]), "handle": handle,
                  "file": f"pages/{handle}.html", "old_url": p["link"]})
    print(f"{handle}: {len(p['content']['rendered'])} -> {len(body)} chars")
json.dump(index, open(os.path.join(OUT, "pages.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
