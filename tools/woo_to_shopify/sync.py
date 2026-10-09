"""WooCommerce -> Shopify import: products, sizes/variants, stock and orders.

Usage (stdlib only):
    python3 sync.py fetch      # download Woo products, variations, orders + Shopify catalog into DATA_DIR
    python3 sync.py products   # create missing products, fix changed ones, correct stock, publish
    python3 sync.py orders     # import Woo orders as backdated Shopify orders (no emails, no stock change)

Env: WC_CONSUMER_KEY, WC_CONSUMER_SECRET, and SHOPIFY_ADMIN_TOKEN or SHOPIFY_CLIENT_ID + SHOPIFY_CLIENT_SECRET,
     WC_URL (default https://babasaleh.com), SHOPIFY_STORE (default babasaleh.myshopify.com),
     DATA_DIR (default ./woo_data)

Every step is safe to re-run: products are upserted by handle and orders are
skipped when a Shopify order tagged woo-<id> already exists.
"""
import base64, glob, html, json, os, subprocess, sys, time, urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.environ.get("DATA_DIR", "woo_data")
WC = os.environ.get("WC_URL", "https://babasaleh.com").rstrip("/") + "/wp-json/wc/v3"
SHOP = os.environ.get("SHOPIFY_STORE", "babasaleh.myshopify.com")
API = f"https://{SHOP}/admin/api/2026-07/graphql.json"
LOC = "gid://shopify/Location/95288852528"
PUBLICATIONS = ["gid://shopify/Publication/226598060080", "gid://shopify/Publication/226598092848"]  # Online Store, POS


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ---------------------------------------------------------------- HTTP helpers
def http(req, tries=6):
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read(), dict(r.headers)
        except (urllib.error.URLError, TimeoutError) as e:
            if isinstance(e, urllib.error.HTTPError) and e.code < 500 and e.code != 429:
                raise RuntimeError(f"{e.code} {e.read()[:500]!r}")
            time.sleep(2 ** i)
    raise RuntimeError(f"giving up on {req.full_url}")


def wc_get(path, **params):
    auth = base64.b64encode(f"{os.environ['WC_CONSUMER_KEY']}:{os.environ['WC_CONSUMER_SECRET']}".encode()).decode()
    url = f"{WC}/{path}?" + urllib.parse.urlencode(params)
    # Cloudflare in front of the store rejects urllib's default User-Agent (error 1010)
    body, headers = http(urllib.request.Request(url, headers={"Authorization": f"Basic {auth}", "User-Agent": "Mozilla/5.0 (woo-to-shopify sync)"}))
    return json.loads(body), int(headers.get("X-WP-TotalPages") or headers.get("x-wp-totalpages") or 1)


_token = {"value": os.environ.get("SHOPIFY_ADMIN_TOKEN"), "expires": float("inf")}


def shopify_token():
    """Static SHOPIFY_ADMIN_TOKEN, or a Dev Dashboard app's client-credentials token (refreshed before it expires)."""
    if not _token["value"] or time.time() > _token["expires"]:
        form = urllib.parse.urlencode({"grant_type": "client_credentials", "client_id": os.environ["SHOPIFY_CLIENT_ID"],
                                       "client_secret": os.environ["SHOPIFY_CLIENT_SECRET"]}).encode()
        out = json.loads(http(urllib.request.Request(f"https://{SHOP}/admin/oauth/access_token", data=form,
                                                     headers={"Content-Type": "application/x-www-form-urlencoded"}))[0])
        _token.update(value=out["access_token"], expires=time.time() + out.get("expires_in", 86400) - 600)
    return _token["value"]


def gql(query, variables=None):
    req = lambda: urllib.request.Request(
        API, data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Content-Type": "application/json", "X-Shopify-Access-Token": shopify_token()})
    while True:
        out = json.loads(http(req())[0])
        errs = out.get("errors")
        if errs and any((e.get("extensions") or {}).get("code") == "THROTTLED" for e in errs):
            time.sleep(2)
            continue
        if errs:
            raise RuntimeError(json.dumps(errs)[:1000])
        avail = out["extensions"]["cost"]["throttleStatus"]["currentlyAvailable"]
        if avail < 200:
            time.sleep(2)
        return out["data"]


# ---------------------------------------------------------------- fetch
def fetch():
    os.makedirs(f"{D}/var", exist_ok=True)
    for name in ("products", "orders"):
        with open(f"{D}/{name}.ndjson", "w") as f:
            page, pages = 1, 1
            while page <= pages:
                rows, pages = wc_get(name, per_page=100, page=page, status="any")
                f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
                log(name, "page", page, "/", pages)
                page += 1
    for l in open(f"{D}/products.ndjson"):
        p = json.loads(l)
        if p["type"] == "variable":
            rows, _ = wc_get(f"products/{p['id']}/variations", per_page=100)
            json.dump(rows, open(f"{D}/var/{p['id']}.json", "w"), ensure_ascii=False)
    export_shopify()


SHOP_PRODUCTS_Q = """query($after: String) { products(first: 50, after: $after) {
  pageInfo { hasNextPage endCursor }
  nodes { id title handle status variants(first: 250) { nodes { id sku title
    selectedOptions { name value } inventoryItem { id tracked } inventoryQuantity } } } } }"""


def export_shopify():
    after, n = None, 0
    with open(f"{D}/shopify.jsonl", "w") as f:
        while True:
            page = gql(SHOP_PRODUCTS_Q, {"after": after})["products"]
            for p in page["nodes"]:
                vs = p.pop("variants")["nodes"]
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
                for v in vs:
                    f.write(json.dumps(dict(v, __parentId=p["id"]), ensure_ascii=False) + "\n")
                n += 1
            if not page["pageInfo"]["hasNextPage"]:
                break
            after = page["pageInfo"]["endCursor"]
    log("shopify products exported:", n)


# ---------------------------------------------------------------- products
PRODUCT_SET = """mutation($input: ProductSetInput!, $identifier: ProductSetIdentifiers) {
  productSet(input: $input, identifier: $identifier, synchronous: true) {
    product { id handle } userErrors { field message code } } }"""
PUBLISH = """mutation($id: ID!, $input: [PublicationInput!]!) {
  publishablePublish(id: $id, input: $input) { userErrors { field message } } }"""
SET_QTY = """mutation($input: InventorySetQuantitiesInput!) {
  inventorySetQuantities(input: $input) { userErrors { field message code } } }"""
TRACK = """mutation($id: ID!, $input: InventoryItemInput!) {
  inventoryItemUpdate(id: $id, input: $input) { userErrors { field message } } }"""


def products():
    export_shopify()
    subprocess.run([sys.executable, "-I", f"{HERE}/build_products.py", D], check=True)
    S = [json.loads(l) for l in open(f"{D}/shopify.jsonl")]
    sv = {o["id"]: o for o in S if "__parentId" in o}
    failed = []
    for l in open(f"{D}/productset.jsonl"):
        d = json.loads(l)
        inp, handle = d["input"], d["input"]["handle"]
        if "identifier" not in d:  # new product
            r = gql(PRODUCT_SET, {"input": inp, "identifier": {"handle": handle}})["productSet"]
            if r["userErrors"] or not r["product"]:
                failed.append((handle, r["userErrors"]))
                log("FAILED", handle, r["userErrors"])
                continue
            gql(PUBLISH, {"id": r["product"]["id"], "input": [{"publicationId": p} for p in PUBLICATIONS]})
            log("created", handle)
            continue
        # Existing product: keep variant IDs, only touch what differs.
        pid = d["identifier"]["id"]
        old = {k for k, o in sv.items() if o["__parentId"] == pid}
        kept, qty, track = set(), [], []
        for v in inp["variants"]:
            if "id" not in v:
                continue
            kept.add(v["id"])
            o = sv[v["id"]]
            q = v.pop("inventoryQuantities", None)
            if v["inventoryItem"]["tracked"] != o["inventoryItem"]["tracked"]:
                track.append((o["inventoryItem"]["id"], v["inventoryItem"]["tracked"]))
            if q and (q[0]["quantity"] != o["inventoryQuantity"] or not o["inventoryItem"]["tracked"]):
                qty.append({"inventoryItemId": o["inventoryItem"]["id"], "locationId": LOC,
                            "quantity": q[0]["quantity"], "changeFromQuantity": None})
        if old - kept or len(kept) < len(inp["variants"]):
            r = gql(PRODUCT_SET, {"input": inp, "identifier": d["identifier"]})["productSet"]
            if r["userErrors"]:
                failed.append((handle, r["userErrors"]))
                log("FAILED", handle, r["userErrors"])
                continue
            log("variants fixed", handle, f"-{len(old - kept)} +{len(inp['variants']) - len(kept)}")
        for item, tracked in track:
            gql(TRACK, {"id": item, "input": {"tracked": tracked}})
        if qty:
            r = gql(SET_QTY, {"input": {"name": "available", "reason": "correction", "quantities": qty}})
            log("stock fixed", handle, len(qty), r["inventorySetQuantities"]["userErrors"] or "")
    json.dump(failed, open(f"{D}/products_failed.json", "w"), ensure_ascii=False, indent=1)
    log("products done, failures:", len(failed))


# ---------------------------------------------------------------- orders
ORDER_CREATE = """mutation($order: OrderCreateOrderInput!, $options: OrderCreateOptionsInput) {
  orderCreate(order: $order, options: $options) { order { id name } userErrors { field message code } } }"""
ORDER_CANCEL = """mutation($id: ID!) { orderCancel(orderId: $id, reason: OTHER, refund: false, restock: false,
  notifyCustomer: false, staffNote: "Cancelled in WooCommerce") {
  job { id } orderCancelUserErrors { field message code } } }"""
ORDER_EXISTS = """query($q: String!) { orders(first: 1, query: $q) { nodes { id } } }"""


def money(x):
    return {"shopMoney": {"amount": str(round(float(x), 2)), "currencyCode": "EGP"}}


def address(a):
    st = (a.get("state") or "").upper()
    out = {"firstName": a["first_name"], "lastName": a["last_name"], "address1": a["address_1"],
           "address2": a["address_2"], "city": a["city"], "zip": a["postcode"], "phone": a.get("phone"),
           "company": a["company"], "countryCode": a["country"] or "EG"}
    if st.startswith(a["country"] or "EG"):
        st = st[len(a["country"] or "EG"):]
    if st:
        out["provinceCode"] = st
    return {k: v for k, v in out.items() if v}


def variant_index():
    export_shopify()
    S = [json.loads(l) for l in open(f"{D}/shopify.jsonl")]
    handle = {o["id"]: o["handle"] for o in S if "handle" in o}
    idx = {}
    for o in S:
        if "__parentId" in o:
            opts = {x["value"].strip().lower() for x in o["selectedOptions"] if x["name"] != "Title"}
            idx.setdefault(handle[o["__parentId"]], []).append((opts, o["id"]))
    return idx


def orders():
    P = {p["id"]: p for p in map(json.loads, open(f"{D}/products.ndjson"))}
    V = {v["id"]: v for f in glob.glob(f"{D}/var/*.json") for v in json.load(open(f))}
    idx = variant_index()
    done_path = f"{D}/orders_done.json"
    done = json.load(open(done_path)) if os.path.exists(done_path) else {}
    O = sorted(map(json.loads, open(f"{D}/orders.ndjson")), key=lambda o: o["id"])
    stats = {"created": 0, "skipped": 0, "failed": 0, "custom_lines": 0}
    for o in O:
        key = str(o["id"])
        if key in done:
            stats["skipped"] += 1
            continue
        hit = gql(ORDER_EXISTS, {"q": f"tag:'woo-{o['id']}'"})["orders"]["nodes"]
        if hit:
            done[key] = hit[0]["id"]
            stats["skipped"] += 1
            continue
        lines, discount = [], 0.0
        for li in o["line_items"]:
            qty = li["quantity"] or 1
            unit = float(li["subtotal"]) / qty
            discount += float(li["subtotal"]) - float(li["total"])
            line = {"quantity": qty, "priceSet": money(unit)}
            p = P.get(li["product_id"])
            # match on option values only: Woo attribute labels don't always equal Shopify option names
            want = {str(m["display_value"]).strip().lower() for m in li["meta_data"] if not m["key"].startswith("_")}
            if li["variation_id"] in V:
                want |= {a["option"].strip().lower() for a in V[li["variation_id"]]["attributes"] if a["option"]}
            cands = idx.get(urllib.parse.unquote(p["slug"]), []) if p else []
            match = [vid for opts, vid in cands if opts <= want and (opts or len(cands) == 1)]
            if match:
                line["variantId"] = match[0]
            else:
                stats["custom_lines"] += 1
                line.update(title=html.unescape(li["name"].replace("<span> - </span>", " - ")), sku=li["sku"] or None)
            lines.append(line)
        status = o["status"]
        order = {
            "name": f"#{o['number']}", "currency": "EGP", "processedAt": o["date_created_gmt"] + "Z",
            "email": o["billing"]["email"] or None, "phone": o["billing"]["phone"] or None,
            "billingAddress": address(o["billing"]), "shippingAddress": address(o["shipping"] if o["shipping"]["address_1"] else o["billing"]),
            "lineItems": lines, "note": o["customer_note"] or None,
            "tags": ["woocommerce", f"woo-{o['id']}", f"woo-status-{status}"],
            "sourceIdentifier": key, "sourceName": "woocommerce",
            "shippingLines": [{"title": s["method_title"], "code": s["method_id"], "priceSet": money(s["total"])} for s in o["shipping_lines"]],
            "financialStatus": "PAID" if status == "completed" else "PENDING",
        }
        if o["billing"]["email"]:
            order["customer"] = {"toUpsert": {"email": o["billing"]["email"], "firstName": o["billing"]["first_name"],
                                              "lastName": o["billing"]["last_name"]}}
        if discount > 0.005:
            order["discountCode"] = {"itemFixedDiscountCode": {"code": "WOO-DISCOUNT", "amountSet": money(discount)}}
        if status == "completed":
            order["fulfillmentStatus"] = "FULFILLED"
            order["transactions"] = [{"kind": "SALE", "status": "SUCCESS", "gateway": o["payment_method_title"] or "Cash on Delivery",
                                      "amountSet": money(o["total"]), "processedAt": (o["date_paid_gmt"] or o["date_created_gmt"]) + "Z"}]
        if o["date_completed_gmt"] and status == "completed":
            order["closedAt"] = o["date_completed_gmt"] + "Z"
        order = {k: v for k, v in order.items() if v not in (None, [], "")}
        opts = {"sendReceipt": False, "sendFulfillmentReceipt": False, "inventoryBehaviour": "BYPASS"}
        r = gql(ORDER_CREATE, {"order": order, "options": opts})["orderCreate"]
        if r["userErrors"] and any("province" in json.dumps(e).lower() for e in r["userErrors"]):
            for a in ("billingAddress", "shippingAddress"):
                order[a].pop("provinceCode", None)
            r = gql(ORDER_CREATE, {"order": order, "options": opts})["orderCreate"]
        if r["userErrors"] or not r["order"]:
            stats["failed"] += 1
            log("FAILED order", o["number"], r["userErrors"])
            continue
        if status == "cancelled":
            c = gql(ORDER_CANCEL, {"id": r["order"]["id"]})["orderCancel"]
            if c["orderCancelUserErrors"]:
                log("cancel failed", o["number"], c["orderCancelUserErrors"])
        done[key] = r["order"]["id"]
        stats["created"] += 1
        if os.environ.get("ORDER_LIMIT") and stats["created"] >= int(os.environ["ORDER_LIMIT"]):
            break
        if stats["created"] % 25 == 0:
            json.dump(done, open(done_path, "w"))
            log("orders", stats)
    json.dump(done, open(done_path, "w"))
    log("orders done", stats)


if __name__ == "__main__":
    {"fetch": fetch, "products": products, "orders": orders, "export": export_shopify}[sys.argv[1]]()
