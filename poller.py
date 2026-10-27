#!/usr/bin/env python3
"""Saved-search poller. Run from cron: */15 * * * * poller.py

Env: EBAY_TOKEN (OAuth client-credentials, scope buy.browse),
     APIFY_TOKEN, VINTED_COOKIE (optional, raises rate limits),
     NTFY_TOPIC (e.g. https://ntfy.sh/sam-resale)
"""
import json, os, sqlite3, sys, time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import requests

DB = os.environ.get("DB", "searches.db")

@dataclass
class Item:
    platform: str; platform_id: str; url: str
    title: str = ""; price: float | None = None; currency: str = ""
    image: str = ""; condition: str = ""; size: str = ""
    color: str = ""; brand: str = ""
    @property
    def key(self): return f"{self.platform}:{self.platform_id}"

# ---------- adapters ----------
# Each: fetch(query:str, f:dict) -> list[Item]. Map normalized filters to native ones.

class Ebay:
    name = "ebay"
    COND = {"new": "1000", "very_good": "3000", "good": "4000", "fair": "5000"}
    def fetch(self, q, f):
        flt = []
        if f.get("price_max"):
            flt.append(f"price:[..{f['price_max']}],priceCurrency:{f.get('currency','SEK')}")
        if f.get("condition"):
            flt.append("conditionIds:{" + "|".join(self.COND[c] for c in f["condition"] if c in self.COND) + "}")
        params = {"q": q, "limit": 50, "sort": "newlyListed", "filter": ",".join(flt)}
        aspects = []
        if f.get("color"): aspects.append("Color:{" + "|".join(f["color"]) + "}")
        if f.get("size"):  aspects.append("US Shoe Size:{" + "|".join(f["size"]) + "}")
        if aspects: params["aspect_filter"] = "categoryId:11450," + ",".join(aspects)
        r = requests.get("https://api.ebay.com/buy/browse/v1/item_summary/search",
                         params=params, timeout=30,
                         headers={"Authorization": f"Bearer {os.environ['EBAY_TOKEN']}",
                                  "X-EBAY-C-MARKETPLACE-ID": "EBAY_SE"})
        r.raise_for_status()
        out = []
        for it in r.json().get("itemSummaries", []):
            p = it.get("price", {})
            out.append(Item("ebay", it["itemId"], it["itemWebUrl"], it.get("title", ""),
                            float(p.get("value", 0)) or None, p.get("currency", ""),
                            it.get("image", {}).get("imageUrl", ""), it.get("condition", "")))
        return out

class Vinted:
    """Internal catalog endpoint; undocumented, needs session cookie from a GET on the site."""
    name = "vinted"
    HOST = "https://www.vinted.se"
    COND = {"new": 6, "very_good": 1, "good": 2, "fair": 3}  # status_ids
    def _session(self):
        s = requests.Session()
        s.headers["User-Agent"] = "Mozilla/5.0"
        if c := os.environ.get("VINTED_COOKIE"): s.headers["Cookie"] = c
        else: s.get(self.HOST, timeout=30)  # sets _vinted_fr_session cookie
        return s
    def fetch(self, q, f):
        params = {"search_text": q, "order": "newest_first", "per_page": 60}
        if f.get("price_max"): params["price_to"] = f["price_max"]
        if f.get("condition"): params["status_ids[]"] = [self.COND[c] for c in f["condition"] if c in self.COND]
        # color_ids / size_ids are numeric per-locale; resolve once via /api/v2/colors, /api/v2/sizes
        if f.get("color_ids"): params["color_ids[]"] = f["color_ids"]
        if f.get("size_ids"):  params["size_ids[]"] = f["size_ids"]
        r = self._session().get(f"{self.HOST}/api/v2/catalog/items", params=params, timeout=30)
        r.raise_for_status()
        return [Item("vinted", str(it["id"]), it["url"], it.get("title", ""),
                     float(it["price"]["amount"]), it["price"]["currency_code"],
                     (it.get("photo") or {}).get("url", ""), it.get("status", ""),
                     it.get("size_title", ""), brand=it.get("brand_title", ""))
                for it in r.json().get("items", [])]

class Apify:
    """Generic: run an actor synchronously, map dataset rows. Use for depop/grailed/mercari/poshmark/
    therealreal/vestiaire. Actor ids + field map are config, not code."""
    def __init__(self, name, actor, build_input, map_row):
        self.name, self.actor, self.build_input, self.map_row = name, actor, build_input, map_row
    def fetch(self, q, f):
        r = requests.post(f"https://api.apify.com/v2/acts/{self.actor}/run-sync-get-dataset-items",
                          params={"token": os.environ["APIFY_TOKEN"], "timeout": 120},
                          json=self.build_input(q, f), timeout=180)
        r.raise_for_status()
        return [self.map_row(self.name, row) for row in r.json()]

def _generic_row(name, row):
    return Item(name, str(row.get("id") or row.get("url")), row["url"], row.get("title", ""),
                row.get("price"), row.get("currency", ""), row.get("image", ""),
                row.get("condition", ""), row.get("size", ""), row.get("color", ""), row.get("brand", ""))

ADAPTERS = {a.name: a for a in [
    Ebay(), Vinted(),
    Apify("depop", "nerolabs~depop-marketplace-monitor",
          lambda q, f: {"searchQueries": [q], "maxItems": 60}, _generic_row),
    # add grailed/mercari/poshmark/therealreal/vestiaire actors here once chosen
]}

# ---------- core ----------
def notify(search, items):
    if not (t := os.environ.get("NTFY_TOPIC")) or not items: return
    body = "\n".join(f"{i.platform} {i.price:g} {i.currency} — {i.title[:60]}\n{i.url}"
                     for i in items[:10] if i.price is not None)
    requests.post(t, data=body.encode(), headers={"Title": f"{len(items)} new: {search['name']}"}, timeout=10)

def run_search(db, s):
    f = json.loads(s["filters"]); new_items = []
    for pf in json.loads(s["platforms"]):
        ad = ADAPTERS.get(pf)
        if not ad: continue
        t0 = time.time()
        try:
            items = ad.fetch(s["query"], f)
        except Exception as e:
            db.execute("INSERT INTO run_log(search_id,platform,ok,error) VALUES(?,?,0,?)", (s["id"], pf, str(e)[:500]))
            continue
        n_new = 0
        for it in items:
            if f.get("price_max") and it.price and it.price > f["price_max"]: continue  # belt and braces
            row = db.execute("SELECT price FROM listing WHERE key=?", (it.key,)).fetchone()
            if row is None:
                db.execute("""INSERT INTO listing(key,platform,search_id,title,price,currency,url,image,condition,size,color,brand)
                              VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                           (it.key, it.platform, s["id"], it.title, it.price, it.currency, it.url, it.image,
                            it.condition, it.size, it.color, it.brand))
                new_items.append(it); n_new += 1
            else:
                db.execute("UPDATE listing SET last_seen=datetime('now'), gone=0 WHERE key=?", (it.key,))
                if it.price is not None and row[0] != it.price:
                    db.execute("UPDATE listing SET price=? WHERE key=?", (it.price, it.key))
            if it.price is not None:
                db.execute("INSERT INTO price_history(key,price) VALUES(?,?)", (it.key, it.price))
        db.execute("INSERT INTO run_log(search_id,platform,ok,n_total,n_new) VALUES(?,?,1,?,?)",
                   (s["id"], pf, len(items), n_new))
    db.execute("UPDATE saved_search SET last_run=datetime('now') WHERE id=?", (s["id"],))
    db.commit()
    notify(s, new_items)

def main():
    db = sqlite3.connect(DB); db.row_factory = sqlite3.Row
    db.executescript(open(os.path.join(os.path.dirname(__file__), "schema.sql")).read())
    due = db.execute("""SELECT * FROM saved_search WHERE active=1 AND
                        (last_run IS NULL OR strftime('%s','now')-strftime('%s',last_run) >= interval_s)""").fetchall()
    for s in due: run_search(db, dict(s))

if __name__ == "__main__":
    main()
