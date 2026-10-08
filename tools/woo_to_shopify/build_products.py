"""Build productSet bulk JSONL (one line per product) from the WooCommerce export."""
import json, glob, html, itertools, sys, urllib.parse as U, collections as C

D = sys.argv[1]
LOC = "gid://shopify/Location/95288852528"
P = [json.loads(l) for l in open(f"{D}/products.ndjson")]
V = {int(f.split("/")[-1][:-5]): json.load(open(f)) for f in glob.glob(f"{D}/var/*.json")}
S = [json.loads(l) for l in open(f"{D}/shopify.jsonl")]
existing = {o["handle"]: o["id"] for o in S if "handle" in o}
by_pid = {}
for o in S:
    if "__parentId" in o:
        key = tuple(sorted((x["name"].lower(), x["value"].strip().lower()) for x in o["selectedOptions"]))
        by_pid.setdefault(o["__parentId"], {})[key] = o["id"]

stats = C.Counter()
out = open(f"{D}/productset.jsonl", "w")
inv_out = open(f"{D}/inventory_plan.jsonl", "w")


def money(x):
    return str(x) if x not in (None, "") else None


def stock(obj, parent):
    """Return (tracked, quantity, policy) for a Woo product/variation."""
    ms = obj["manage_stock"]
    src = parent if ms == "parent" else obj
    if ms is True or ms == "parent":
        stats["stock_parent_pool" if ms == "parent" else "stock_own"] += 1
        policy = "CONTINUE" if src.get("backorders") in ("notify", "yes") else "DENY"
        return True, int(src["stock_quantity"] or 0), policy
    # Untracked in Woo: keep untracked unless explicitly out of stock.
    if obj["stock_status"] == "outofstock":
        stats["stock_untracked_oos"] += 1
        return True, 0, "DENY"
    stats["stock_untracked"] += 1
    return False, None, "DENY"


def price_pair(o):
    reg, sale = money(o["regular_price"]), money(o["sale_price"])
    if sale and reg and float(sale) < float(reg):
        return sale, reg
    return reg or money(o["price"]) or "0", None


def variant(o, parent, opts, file_url, gid=None):
    tracked, qty, policy = stock(o, parent)
    price, cmp = price_pair(o)
    v = {
        "optionValues": [{"optionName": n, "name": val} for n, val in opts],
        "price": price,
        "inventoryPolicy": policy,
        "inventoryItem": {"tracked": tracked, "sku": o["sku"] or parent["sku"] or None},
    }
    if cmp:
        v["compareAtPrice"] = cmp
    if gid:
        key = tuple(sorted((n.lower(), val.strip().lower()) for n, val in opts))
        vid = by_pid.get(gid, {}).get(key)
        if vid:
            v["id"] = vid
            stats["variant_kept"] += 1
    if tracked:
        v["inventoryQuantities"] = [{"locationId": LOC, "name": "available", "quantity": qty}]
    if file_url:
        v["file"] = {"originalSource": file_url, "contentType": "IMAGE"}
    return v, (tracked, qty)


for p in P:
    handle = U.unquote(p["slug"]) or str(p["id"])
    brand = (p.get("brands") or [{}])[0].get("name")
    inp = {
        "title": html.unescape(p["name"]),
        "handle": handle,
        "status": "ACTIVE" if p["status"] == "publish" else "DRAFT",
    }
    gid = existing.get(handle)
    if not gid:
        cats = [html.unescape(c["name"]) for c in p["categories"] if c["slug"] != "uncategorized"]
        inp.update(
            descriptionHtml=p["description"] or p["short_description"],
            productType=cats[0] if cats else "",
            tags=sorted(set(cats + [html.unescape(t["name"]) for t in p["tags"]])),
            vendor=(brand or "Baba Saleh").title() if brand else "Baba Saleh",
        )
    images = [i["src"] for i in p["images"]]
    plan = []
    if p["type"] == "simple":
        inp["productOptions"] = [{"name": "Title", "values": [{"name": "Default Title"}]}]
        v, st = variant(p, p, [("Title", "Default Title")], None, gid)
        inp["variants"] = [v]
        plan.append((("Default Title",), st))
    else:
        vattrs = [a for a in p["attributes"] if a["variation"]]
        combos = {}
        for w in sorted(V[p["id"]], key=lambda w: w["menu_order"]):
            if w["status"] != "publish":
                stats["var_disabled"] += 1
                continue
            set_ = {a["name"]: a["option"] for a in w["attributes"] if a["option"]}
            choices = [[set_[a["name"]]] if a["name"] in set_ else a["options"] for a in vattrs]
            for combo in itertools.product(*choices):
                combos.setdefault(combo, w)  # Woo: first matching variation wins
        # Drop attributes with only one value (e.g. Gender=Women) - they add no choice.
        keep = [i for i, a in enumerate(vattrs) if len({c[i] for c in combos}) > 1] or ([0] if vattrs else [])
        if len(keep) > 3:
            stats["skipped_too_many_options"] += 1
            print("SKIP >3 options", handle, file=sys.stderr)
            continue
        names = [vattrs[i]["name"] for i in keep] or ["Title"]
        seen = {}
        for combo, w in combos.items():
            k = tuple(combo[i] for i in keep) or ("Default Title",)
            seen.setdefault(k, w)
        if not seen:
            stats["skipped_no_variations"] += 1
            print("SKIP no variations", handle, file=sys.stderr)
            continue
        inp["productOptions"] = [
            {"name": n, "values": [{"name": x} for x in dict.fromkeys(k[j] for k in seen)]}
            for j, n in enumerate(names)
        ]
        inp["variants"] = []
        for k, w in seen.items():
            img = w["image"]["src"] if w.get("image") else None
            if img and img not in images:
                images.append(img)
            v, st = variant(w, p, list(zip(names, k)), img if not gid else None, gid)
            inp["variants"].append(v)
            plan.append((k, st))
        stats["variants"] += len(inp["variants"])
    if not gid and images:
        inp["files"] = [{"originalSource": u, "contentType": "IMAGE"} for u in dict.fromkeys(images)]
    line = {"input": inp, "synchronous": True}
    if gid:
        line["identifier"] = {"id": gid}
        stats["update"] += 1
    else:
        stats["create"] += 1
    out.write(json.dumps(line, ensure_ascii=False) + "\n")
    inv_out.write(json.dumps({"handle": handle, "plan": plan}, ensure_ascii=False) + "\n")

print(dict(stats))
