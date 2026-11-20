"""Daily category audit input: every product as "title | type | cat:/for: tags | sizes", in two files
(woo_data/cats_a.txt, cats_b.txt) plus woo_data/categories.txt, for the nightly review of every product."""
import json, os
from sync import gql
D = os.environ.get("DATA_DIR", "woo_data")
Q = '''query($a:String){products(first:250,after:$a,query:"status:active OR status:draft"){pageInfo{hasNextPage endCursor}
  nodes{title productType tags variants(first:8){nodes{title}}}}}'''
rows, a = [], None
while True:
    r = gql(Q, {"a": a})["products"]
    for n in r["nodes"]:
        tags = " ".join(sorted(t for t in n["tags"] if t.startswith(("cat:", "for:"))))
        rows.append(f"{n['title']} | {n['productType']} | {tags} | sizes: {', '.join(v['title'] for v in n['variants']['nodes'])[:80]}")
    if not r["pageInfo"]["hasNextPage"]:
        break
    a = r["pageInfo"]["endCursor"]
rows.sort(key=lambda x: x.split(" | ")[2])
h = len(rows) // 2
open(os.path.join(D, "cats_a.txt"), "w").write("\n".join(rows[:h]))
open(os.path.join(D, "cats_b.txt"), "w").write("\n".join(rows[h:]))
tax = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "taxonomy.json")))
open(os.path.join(D, "categories.txt"), "w").write("\n".join(f"{k} = {v['type']}" for k, v in tax.items()))
print(f"category-list {len(rows)} products")
