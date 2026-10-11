"""WooCommerce -> Shopify import: products, sizes/variants, stock and orders.

Usage (stdlib only):
    python3 sync.py fetch      # download Woo products, variations, orders + Shopify catalog into DATA_DIR
    python3 sync.py products   # create missing products, fix changed ones, correct stock, publish
    python3 sync.py orders     # import Woo orders as backdated Shopify orders (no emails, no stock change);
                               # cancelled Woo orders become draft orders so they never count as sales
    python3 sync.py cancelled-to-drafts   # one-off: move already-imported cancelled orders to draft orders
    python3 sync.py sort-stock # every collection: in-stock products first, sold-out last (re-run as stock changes)

Env: WC_CONSUMER_KEY, WC_CONSUMER_SECRET, and SHOPIFY_ADMIN_TOKEN or SHOPIFY_CLIENT_ID + SHOPIFY_CLIENT_SECRET,
     WC_URL (default https://babasaleh.com), SHOPIFY_STORE (default babasaleh.myshopify.com),
     DATA_DIR (default ./woo_data)

Every step is safe to re-run: products are upserted by handle and orders are
skipped when a Shopify order or draft order tagged woo-<id> already exists.

Cancelled orders are kept as draft orders, not cancelled orders: Shopify books a
cancellation as a sales reversal on the day it happens (it can't be backdated),
so importing cancelled orders would put one large negative day in the reports.
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
DRAFT_CREATE = """mutation($input: DraftOrderInput!) {
  draftOrderCreate(input: $input) { draftOrder { id name } userErrors { field message } } }"""
ORDER_DELETE = """mutation($id: ID!) { orderDelete(orderId: $id) { deletedId userErrors { field message } } }"""
ORDER_EXISTS = """query($q: String!) { orders(first: 1, query: $q) { nodes { id } } draftOrders(first: 1, query: $q) { nodes { id } } }"""
CUSTOMER_BY_EMAIL = """query($q: String!) { customers(first: 1, query: $q) { nodes { id } } }"""


def money(x):
    return {"shopMoney": {"amount": str(round(float(x), 2)), "currencyCode": "EGP"}}


def phone(p):
    """Woo stores local Egyptian numbers (01xxxxxxxxx); Shopify wants E.164 (+201xxxxxxxxx)."""
    d = "".join(c for c in (p or "") if c.isdigit())
    if not d:
        return None
    if (p or "").strip().startswith("+") or d.startswith("20"):
        return "+" + d
    return "+20" + d.lstrip("0") if d.startswith("0") else "+" + d


def address(a):
    st = (a.get("state") or "").upper()
    out = {"firstName": a["first_name"], "lastName": a["last_name"], "address1": a["address_1"],
           "address2": a["address_2"], "city": a["city"], "zip": a["postcode"], "phone": phone(a.get("phone")),
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


def load_orders():
    P = {p["id"]: p for p in map(json.loads, open(f"{D}/products.ndjson"))}
    V = {v["id"]: v for f in glob.glob(f"{D}/var/*.json") for v in json.load(open(f))}
    O = sorted(map(json.loads, open(f"{D}/orders.ndjson")), key=lambda o: o["id"])
    return P, V, variant_index(), O


def build_order(o, P, V, idx, stats):
    """Woo order -> OrderCreateOrderInput."""
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
        "email": o["billing"]["email"] or None, "phone": phone(o["billing"]["phone"]),
        "billingAddress": address(o["billing"]), "shippingAddress": address(o["shipping"] if o["shipping"]["address_1"] else o["billing"]),
        "lineItems": lines, "note": o["customer_note"] or None,
        "tags": ["woocommerce", f"woo-{o['id']}", f"woo-status-{status}"],
        "sourceIdentifier": str(o["id"]), "sourceName": "woocommerce",
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
    return {k: v for k, v in order.items() if v not in (None, [], "")}


def as_draft(order, o):
    """OrderCreateOrderInput -> DraftOrderInput, for cancelled Woo orders (drafts never count as sales)."""
    amount = lambda m: {"amount": m["shopMoney"]["amount"], "currencyCode": "EGP"}
    lines = []
    for li in order["lineItems"]:
        if "variantId" in li:
            lines.append({"variantId": li["variantId"], "quantity": li["quantity"], "priceOverride": amount(li["priceSet"])})
        else:
            lines.append({k: v for k, v in {"title": li["title"], "sku": li.get("sku"), "quantity": li["quantity"],
                                            "originalUnitPriceWithCurrency": amount(li["priceSet"])}.items() if v})
    placed = o["date_created_gmt"][:10]
    note = f"Cancelled WooCommerce order {order['name']}, placed {placed}. Kept for records; not a sale."
    draft = {
        "lineItems": lines, "email": order.get("email"), "phone": order.get("phone"),
        "billingAddress": order.get("billingAddress"), "shippingAddress": order.get("shippingAddress"),
        "note": note + (f"\n\nCustomer note: {order['note']}" if order.get("note") else ""),
        "tags": order["tags"] + ["woo-cancelled"], "sourceName": "woocommerce", "presentmentCurrencyCode": "EGP",
    }
    if order.get("shippingLines"):
        s = order["shippingLines"][0]
        draft["shippingLine"] = {"title": s["title"], "priceWithCurrency": amount(s["priceSet"])}
    if order.get("discountCode"):
        d = order["discountCode"]["itemFixedDiscountCode"]["amountSet"]["shopMoney"]["amount"]
        draft["appliedDiscount"] = {"title": "WOO-DISCOUNT", "value": float(d), "valueType": "FIXED_AMOUNT"}
    if order.get("email"):
        hit = gql(CUSTOMER_BY_EMAIL, {"q": f"email:'{order['email']}'"})["customers"]["nodes"]
        if hit:
            draft["purchasingEntity"] = {"customerId": hit[0]["id"]}
    return {k: v for k, v in draft.items() if v not in (None, [], "")}


def create_with_retries(mutation, field, payload_key, payload, extra=None):
    """Run a create mutation, retrying without province / phone / email when Shopify rejects them."""
    vars_ = lambda: dict({payload_key: payload}, **(extra or {}))
    r = gql(mutation, vars_())[field]
    for bad in ("province", "phone", "email"):
        if r["userErrors"] and any(bad in json.dumps(e).lower() for e in r["userErrors"]):
            if bad == "province":
                for a in ("billingAddress", "shippingAddress"):
                    (payload.get(a) or {}).pop("provinceCode", None)
            elif bad == "phone":
                payload.pop("phone", None)
                for a in ("billingAddress", "shippingAddress"):
                    (payload.get(a) or {}).pop("phone", None)
            else:  # e.g. test@test.com: "invalid domain name"
                payload.pop("email", None)
                payload.pop("customer", None)
                payload.pop("purchasingEntity", None)
            r = gql(mutation, vars_())[field]
    return r


def orders():
    P, V, idx, O = load_orders()
    done_path = f"{D}/orders_done.json"
    done = json.load(open(done_path)) if os.path.exists(done_path) else {}
    stats = {"created": 0, "drafts": 0, "skipped": 0, "failed": 0, "custom_lines": 0}
    opts = {"sendReceipt": False, "sendFulfillmentReceipt": False, "inventoryBehaviour": "BYPASS"}
    for o in O:
        key = str(o["id"])
        if key in done:
            stats["skipped"] += 1
            continue
        hit = gql(ORDER_EXISTS, {"q": f"tag:'woo-{o['id']}'"})
        hit = hit["orders"]["nodes"] + hit["draftOrders"]["nodes"]
        if hit:
            done[key] = hit[0]["id"]
            stats["skipped"] += 1
            continue
        order = build_order(o, P, V, idx, stats)
        if o["status"] == "cancelled":
            r = create_with_retries(DRAFT_CREATE, "draftOrderCreate", "input", as_draft(order, o))
            created = r.get("draftOrder")
        else:
            r = create_with_retries(ORDER_CREATE, "orderCreate", "order", order, {"options": opts})
            created = r.get("order")
        if r["userErrors"] or not created:
            stats["failed"] += 1
            log("FAILED order", o["number"], r["userErrors"])
            continue
        done[key] = created["id"]
        stats["drafts" if o["status"] == "cancelled" else "created"] += 1
        if os.environ.get("ORDER_LIMIT") and stats["created"] + stats["drafts"] >= int(os.environ["ORDER_LIMIT"]):
            break
        if (stats["created"] + stats["drafts"]) % 25 == 0:
            json.dump(done, open(done_path, "w"))
            log("orders", stats)
    json.dump(done, open(done_path, "w"))
    log("orders done", stats)


def cancelled_to_drafts():
    """Replace already-imported cancelled orders with draft orders, then delete the cancelled order."""
    P, V, idx, O = load_orders()
    stats = {"drafts": 0, "deleted": 0, "skipped": 0, "failed": 0, "custom_lines": 0}
    for o in O:
        if o["status"] != "cancelled":
            continue
        found = gql(ORDER_EXISTS, {"q": f"tag:'woo-{o['id']}'"})
        orders_, drafts = found["orders"]["nodes"], found["draftOrders"]["nodes"]
        if not drafts:
            r = create_with_retries(DRAFT_CREATE, "draftOrderCreate", "input", as_draft(build_order(o, P, V, idx, stats), o))
            if r["userErrors"] or not r["draftOrder"]:
                stats["failed"] += 1
                log("FAILED draft", o["number"], r["userErrors"])
                continue  # keep the order: never delete without a draft in place
            stats["drafts"] += 1
        else:
            stats["skipped"] += 1
        for n in orders_:
            d = gql(ORDER_DELETE, {"id": n["id"]})["orderDelete"]
            if d["userErrors"]:
                log("delete failed", o["number"], d["userErrors"])
            else:
                stats["deleted"] += 1
        if os.environ.get("ORDER_LIMIT") and stats["drafts"] >= int(os.environ["ORDER_LIMIT"]):
            break
    log("cancelled-to-drafts done", stats)

# ---------------------------------------------------------------- in stock first
COLLECTIONS_Q = """query($after: String) { collections(first: 50, after: $after) {
  pageInfo { hasNextPage endCursor }
  nodes { id handle sortOrder productsCount { count } metafield(namespace: "babasaleh", key: "base_sort") { value } } } }"""
COLLECTION_PRODUCTS_Q = """query($id: ID!, $after: String, $key: ProductCollectionSortKeys!, $rev: Boolean!) {
  collection(id: $id) { products(first: 250, after: $after, sortKey: $key, reverse: $rev) {
    pageInfo { hasNextPage endCursor } nodes { id totalInventory tracksInventory } } } }"""
COLLECTION_UPDATE = """mutation($input: CollectionInput!) { collectionUpdate(input: $input) { userErrors { field message } } }"""
METAFIELDS_SET = """mutation($m: [MetafieldsSetInput!]!) { metafieldsSet(metafields: $m) { userErrors { field message } } }"""
REORDER = """mutation($id: ID!, $moves: [MoveInput!]!) { collectionReorderProducts(id: $id, moves: $moves) {
  job { id done } userErrors { field message } } }"""
JOB_Q = """query($id: ID!) { job(id: $id) { done } }"""
# collection sort order -> (products sortKey, reverse)
BASE_SORT = {"ALPHA_ASC": ("TITLE", False), "ALPHA_DESC": ("TITLE", True), "BEST_SELLING": ("BEST_SELLING", False),
             "CREATED": ("CREATED", False), "CREATED_DESC": ("CREATED", True), "MANUAL": ("MANUAL", False),
             "PRICE_ASC": ("PRICE", False), "PRICE_DESC": ("PRICE", True)}


def sort_stock():
    """Put sold-out products last in every collection.

    Collections are switched to manual order; the order they had before is saved in the
    babasaleh.base_sort metafield and used to order products within the in-stock and
    sold-out groups, so re-running keeps e.g. best-selling order while stock changes."""
    after, stats = None, {"collections": 0, "reordered": 0, "products_moved": 0}
    while True:
        page = gql(COLLECTIONS_Q, {"after": after})["collections"]
        for c in page["nodes"]:
            if os.environ.get("COLLECTION") and c["handle"] != os.environ["COLLECTION"]:
                continue
            stats["collections"] += 1
            base = (c["metafield"] or {}).get("value") or c["sortOrder"]
            if not c["metafield"]:
                gql(METAFIELDS_SET, {"m": [{"ownerId": c["id"], "namespace": "babasaleh", "key": "base_sort",
                                            "type": "single_line_text_field", "value": base}]})
            key, rev = BASE_SORT.get(base, ("COLLECTION_DEFAULT", False))
            products, p_after = [], None
            while True:
                pp = gql(COLLECTION_PRODUCTS_Q, {"id": c["id"], "after": p_after, "key": key, "rev": rev})["collection"]["products"]
                products += pp["nodes"]
                if not pp["pageInfo"]["hasNextPage"]:
                    break
                p_after = pp["pageInfo"]["endCursor"]
            in_stock = lambda p: p["totalInventory"] > 0 or not p["tracksInventory"]
            wanted = [p["id"] for p in products if in_stock(p)] + [p["id"] for p in products if not in_stock(p)]
            if c["sortOrder"] != "MANUAL":
                gql(COLLECTION_UPDATE, {"input": {"id": c["id"], "sortOrder": "MANUAL"}})
                current = None  # unknown manual order: send every position
            else:
                current = [p["id"] for p in products] if base == "MANUAL" else None
            if current == wanted:
                continue
            if current is None and base != "MANUAL":
                # read the manual order we are about to replace, to send only the moves that matter
                cur, p_after = [], None
                while True:
                    pp = gql(COLLECTION_PRODUCTS_Q, {"id": c["id"], "after": p_after, "key": "MANUAL", "rev": False})["collection"]["products"]
                    cur += [p["id"] for p in pp["nodes"]]
                    if not pp["pageInfo"]["hasNextPage"]:
                        break
                    p_after = pp["pageInfo"]["endCursor"]
                current = cur
            moves = [{"id": pid, "newPosition": str(i)} for i, pid in enumerate(wanted) if i >= len(current) or current[i] != pid]
            if not moves:
                continue
            for i in range(0, len(moves), 250):
                r = gql(REORDER, {"id": c["id"], "moves": moves[i:i + 250]})["collectionReorderProducts"]
                if r["userErrors"]:
                    log("reorder failed", c["handle"], r["userErrors"])
                    break
                while r["job"] and not gql(JOB_Q, {"id": r["job"]["id"]})["job"]["done"]:
                    time.sleep(1)
            stats["reordered"] += 1
            stats["products_moved"] += len(moves)
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    log("sort-stock done", stats)


if __name__ == "__main__":
    {"fetch": fetch, "products": products, "orders": orders, "export": export_shopify,
     "cancelled-to-drafts": cancelled_to_drafts, "sort-stock": sort_stock}[sys.argv[1]]()
