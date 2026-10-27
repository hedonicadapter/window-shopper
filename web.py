#!/usr/bin/env python3
"""pip install fastapi uvicorn python-multipart ; uvicorn web:app --port 8080
Same DB as poller.py. Views: unseen (since last 'mark seen'), all, starred; filter by search."""
import json, os, sqlite3
from html import escape as e
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse

DB = os.environ.get("DB", "searches.db")
app = FastAPI()

def db():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    c.execute("CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT)")
    return c

def last_visit(c):
    r = c.execute("SELECT v FROM kv WHERE k='last_visit'").fetchone()
    return r[0] if r else "1970-01-01"

CSS = """
:root{--bg:#E9EAE6;--panel:#F7F7F4;--ink:#1C1E1F;--mute:#70746F;--line:#CFD2CB;--new:#1E5C3A;--star:#8A6A00}
@media(prefers-color-scheme:dark){:root{--bg:#16181A;--panel:#202326;--ink:#E7E8E4;--mute:#8E938C;--line:#33373B;--new:#5BBF86;--star:#E0B84A}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.4 system-ui,sans-serif}
header{display:flex;gap:8px;flex-wrap:wrap;align-items:center;padding:12px 16px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--bg);z-index:1}
h1{font-size:17px;font-weight:600;margin:0 12px 0 0}a{color:inherit}
.tab{padding:5px 11px;border:1px solid var(--line);border-radius:999px;text-decoration:none;font-size:14px}.tab.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px;padding:14px 16px}
.card{background:var(--panel);border-radius:8px;overflow:hidden;position:relative;display:flex;flex-direction:column}
.card img{width:100%;aspect-ratio:3/4;object-fit:cover;background:var(--line)}.card .b{padding:8px 10px 10px;font-size:13px}
.card .t{display:block;color:var(--ink);text-decoration:none;max-height:2.8em;overflow:hidden}.card .p{font-weight:600}.card .m{color:var(--mute)}
.card .pf{position:absolute;top:8px;left:8px;background:var(--bg);font-size:11px;padding:2px 7px;border-radius:4px}
.acts{display:flex;gap:4px;margin-top:6px}.acts button{flex:1;border:1px solid var(--line);background:none;color:var(--ink);padding:4px;border-radius:5px;font-size:13px;cursor:pointer}
.card.star .acts .s{background:var(--star);color:#fff;border-color:var(--star)}
.empty{padding:40px 16px;color:var(--mute)}
details{padding:10px 16px;border-bottom:1px solid var(--line)}summary{cursor:pointer;color:var(--mute)}
form.s{display:grid;grid-template-columns:1fr 1fr;gap:6px;max-width:640px;margin-top:10px}form.s input,form.s textarea{font:inherit;padding:6px 8px;border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--ink)}
form.s textarea,form.s button{grid-column:1/-1}form.s button{padding:8px;border:0;border-radius:6px;background:var(--ink);color:var(--bg);font:inherit;cursor:pointer}
ul.ss{list-style:none;padding:0;margin:10px 0 0}ul.ss li{display:flex;gap:10px;align-items:baseline;padding:6px 0;border-top:1px solid var(--line)}ul.ss code{color:var(--mute);font-size:12px}ul.ss form{margin-left:auto;display:inline}ul.ss button{background:none;border:0;color:var(--mute);cursor:pointer;text-decoration:underline;font:inherit}
.new{color:var(--new);font-weight:600}
"""

def card(r):
    price = f"{r['price']:g} {r['currency']}" if r["price"] is not None else ""
    meta = " / ".join(x for x in (r["condition"], r["size"], r["color"]) if x)
    return f"""<div class="card{' star' if r['starred'] else ''}" id="c-{e(r['key'])}">
<span class="pf">{e(r['platform'])}</span>
<a class="t" href="{e(r['url'])}" target="_blank" rel="noopener"><img src="{e(r['image'] or '')}" loading="lazy" alt=""></a>
<div class="b"><a class="t" href="{e(r['url'])}" target="_blank" rel="noopener">{e(r['title'] or '')}</a>
<div class="p">{e(price)}</div><div class="m">{e(meta)}</div>
<div class="acts"><button class="s" hx-post="/l/{e(r['key'])}/star" hx-target="#c-{e(r['key'])}" hx-swap="outerHTML">★</button>
<button hx-post="/l/{e(r['key'])}/dismiss" hx-target="#c-{e(r['key'])}" hx-swap="delete">hide</button></div></div></div>"""

@app.get("/", response_class=HTMLResponse)
def index(view: str = "new", s: int = 0):
    with db() as c:
        lv = last_visit(c)
        searches = c.execute("SELECT * FROM saved_search ORDER BY id").fetchall()
        where = {"new": "first_seen > ? AND dismissed=0 AND gone=0", "all": "dismissed=0 AND gone=0 AND ?<>''", "starred": "starred=1 AND ?<>''"}[view]
        args = [lv]
        if s: where += " AND search_id=?"; args.append(s)
        rows = c.execute(f"SELECT * FROM listing WHERE {where} ORDER BY first_seen DESC LIMIT 300", args).fetchall()
        n_new = c.execute("SELECT COUNT(*) FROM listing WHERE first_seen > ? AND dismissed=0 AND gone=0", (lv,)).fetchone()[0]
    tab = lambda v, label: f'<a class="tab{" on" if view == v else ""}" href="/?view={v}&s={s}">{label}</a>'
    stabs = "".join(f'<a class="tab{" on" if s == r["id"] else ""}" href="/?view={view}&s={r["id"]}">{e(r["name"])}</a>' for r in searches)
    slist = "".join(f'<li>{e(r["name"])} <code>{e(r["query"])} {e(r["filters"])} {e(r["platforms"])}</code>'
                    f'<form hx-post="/s/{r["id"]}/toggle" hx-target="body"><button>{"pause" if r["active"] else "resume"}</button></form>'
                    f'<form hx-post="/s/{r["id"]}/delete" hx-confirm="Delete {e(r["name"])}?" hx-target="body"><button>delete</button></form></li>' for r in searches)
    body = "".join(card(r) for r in rows) or f'<div class="empty">{"Nothing new since last visit." if view=="new" else "Nothing here."}</div>'
    return f"""<!doctype html><meta name=viewport content="width=device-width,initial-scale=1"><title>searches</title><style>{CSS}</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/htmx/2.0.4/htmx.min.js"></script><body>
<header><h1>Saved searches</h1>{tab("new", f'<span class="new">{n_new} new</span>')}{tab("all","all")}{tab("starred","starred")}
<span style="width:10px"></span><a class="tab{' on' if not s else ''}" href="/?view={view}">every search</a>{stabs}
<form hx-post="/seen" hx-target="body" style="margin-left:auto"><button class="tab" type=submit>mark all seen</button></form></header>
<details><summary>manage searches ({len(searches)})</summary>
<form class="s" hx-post="/s" hx-target="body"><input name=name placeholder="name" required><input name=query placeholder="query e.g. red boots" required>
<input name=platforms placeholder="platforms: ebay,vinted,depop" required><input name=interval_s type=number value=900 placeholder="interval s">
<textarea name=filters rows=2 placeholder='filters json: {{"price_max":350,"currency":"SEK","size":["43"],"condition":["very_good"],"color":["red"]}}'>{{}}</textarea>
<button>Save search</button></form><ul class="ss">{slist}</ul></details>
<div class="grid">{body}</div></body>"""

@app.post("/seen")
def seen():
    with db() as c: c.execute("INSERT OR REPLACE INTO kv VALUES('last_visit', datetime('now'))")
    return index()

@app.post("/s")
def create(name: str = Form(), query: str = Form(), platforms: str = Form(), filters: str = Form("{}"), interval_s: int = Form(900)):
    with db() as c:
        c.execute("INSERT INTO saved_search(name,query,platforms,filters,interval_s) VALUES(?,?,?,?,?)",
                  (name, query, json.dumps([p.strip() for p in platforms.split(",") if p.strip()]), json.dumps(json.loads(filters or "{}")), interval_s))
    return index()

@app.post("/s/{sid}/toggle")
def toggle(sid: int):
    with db() as c: c.execute("UPDATE saved_search SET active=1-active WHERE id=?", (sid,))
    return index()

@app.post("/s/{sid}/delete")
def delete(sid: int):
    with db() as c: c.execute("DELETE FROM saved_search WHERE id=?", (sid,))
    return index()

@app.post("/l/{key}/star", response_class=HTMLResponse)
def star(key: str):
    with db() as c:
        c.execute("UPDATE listing SET starred=1-starred WHERE key=?", (key,))
        return card(c.execute("SELECT * FROM listing WHERE key=?", (key,)).fetchone())

@app.post("/l/{key}/dismiss", response_class=HTMLResponse)
def dismiss(key: str):
    with db() as c: c.execute("UPDATE listing SET dismissed=1 WHERE key=?", (key,))
    return ""
