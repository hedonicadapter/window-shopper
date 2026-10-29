#!/usr/bin/env python3
"""pip install fastapi uvicorn python-multipart ; uvicorn web:app --port 8080
Same DB as poller.py. Views: unseen (since last 'mark seen'), all, starred; filter by search."""
import json, os, sqlite3
from html import escape as e
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import poller

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
form.s fieldset{grid-column:1/-1;border:1px solid var(--line);border-radius:6px;margin:0;padding:6px 10px 8px;display:flex;flex-wrap:wrap;gap:4px 14px}
form.s legend{color:var(--mute);font-size:13px;padding:0 4px}form.s label{display:inline-flex;gap:5px;align-items:center}
.rows{display:flex;flex-direction:column;gap:6px;width:100%}.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.row .k{min-width:84px;color:var(--mute);font-size:13px}.row .b{display:flex;flex-wrap:wrap;gap:4px 12px;align-items:center;flex:1}
.row .vals{display:contents}.row .v{display:inline-flex}.row .v input{width:90px}
.row input:not([type=checkbox]){font:inherit;padding:4px 7px;border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--ink);width:120px}
form.s .row button,form.s .ib{padding:2px 8px;border:1px solid var(--line);border-radius:6px;background:none;color:var(--mute);font:inherit;cursor:pointer}
.row.unsup .k{text-decoration:line-through}.row.unsup::after{content:"not used by selected platforms";color:var(--mute);font-size:12px}
form.s select{font:inherit;padding:4px 7px;border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--ink)}
.err{color:#B3261E;font-size:13px}
"""

FORM_JS = """(()=>{
const F=JSON.parse(document.getElementById('fields').textContent),S=JSON.parse(document.getElementById('support').textContent);
const form=document.querySelector('form.s'),rows=form.querySelector('.rows'),pick=form.querySelector('select.add'),err=form.querySelector('.err');
const sel=()=>[...form.querySelectorAll('input[name=platforms]:checked')].map(i=>i.value);
const inp=(k,f)=>`<input name="f:${k}" ${f.type=='number'||f.int?'type=number step=any':''} placeholder="${f.hint||''}">`;
const val=(k,f)=>`<span class=v>${inp(k,f)}<button type=button class=x title="remove value">×</button></span>`;
function refresh(){
  const ps=sel(),opts=Object.keys(F).map(k=>{const by=ps.filter(p=>S[p].includes(k));
    return by.length&&!rows.querySelector(`[data-k="${k}"]`)?`<option value="${k}">${F[k].label} (${by.join(', ')})</option>`:''}).join('');
  pick.innerHTML=`<option value="">${ps.length?(opts?'+ add filter':'no more filters'):'pick platforms first'}</option>`+opts;
  rows.querySelectorAll('.row').forEach(r=>r.classList.toggle('unsup',!ps.some(p=>S[p].includes(r.dataset.k))));
  if(ps.length)err.textContent='';
}
function addRow(k){
  const f=F[k],d=document.createElement('div');d.className='row';d.dataset.k=k;
  const body=f.options?f.options.map(o=>`<label><input type=checkbox name="f:${k}" value="${o}">${o.replace('_',' ')}</label>`).join('')
    :f.type=='list'?`<span class=vals>${val(k,f)}</span><button type=button class=more title="add value">+</button>`:inp(k,f);
  d.innerHTML=`<span class=k>${f.label}</span><span class=b>${body}</span><button type=button class=del title="remove filter">×</button>`;
  rows.append(d);refresh();d.querySelector('input').focus();
}
pick.addEventListener('change',()=>{if(pick.value)addRow(pick.value)});
form.addEventListener('change',e=>{if(e.target.name=='platforms')refresh()});
form.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;
  if(b.classList.contains('del')){b.closest('.row').remove();refresh()}
  else if(b.classList.contains('x'))b.parentNode.remove();
  else if(b.classList.contains('more')){const k=b.closest('.row').dataset.k;b.previousElementSibling.insertAdjacentHTML('beforeend',val(k,F[k]));b.previousElementSibling.lastElementChild.querySelector('input').focus()}});
form.addEventListener('htmx:beforeRequest',e=>{if(!sel().length){e.preventDefault();err.textContent='Pick at least one platform.'}});
refresh();
})();"""

def fmt_filters(f):
    lab = lambda k: poller.FIELDS.get(k, {}).get("label", k)
    return " · ".join(f"{lab(k)} {', '.join(map(str, v)) if isinstance(v, list) else v}" for k, v in f.items())

def parse_filters(items):
    """Form pairs ('f:<key>', value) -> filter dict; unknown keys and blanks dropped."""
    out = {}
    for k, v in items:
        if not k.startswith("f:") or not (v := str(v).strip()) or not (f := poller.FIELDS.get(k[2:])): continue
        k = k[2:]
        if f["type"] == "list": out.setdefault(k, []).append(int(float(v)) if f.get("int") else v)
        elif f["type"] == "number": out[k] = int(float(v)) if float(v).is_integer() else float(v)
        else: out[k] = v
    return out

def jscript(id, obj):
    s = json.dumps(obj).replace("</", "<\\/")
    return f'<script type="application/json" id="{id}">{s}</script>'


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
    slist = "".join(f'<li>{e(r["name"])} <code>{e(r["query"])} · {e(", ".join(json.loads(r["platforms"])))} · {e(fmt_filters(json.loads(r["filters"])))}</code>'
                    f'<form hx-post="/s/{r["id"]}/toggle" hx-target="body"><button>{"pause" if r["active"] else "resume"}</button></form>'
                    f'<form hx-post="/s/{r["id"]}/delete" hx-confirm="Delete {e(r["name"])}?" hx-target="body"><button>delete</button></form></li>' for r in searches)
    plats = "".join(f'<label><input type=checkbox name=platforms value="{e(n)}">{e(n)}</label>' for n in poller.ADAPTERS)
    support = {n: sorted(a.fields) for n, a in poller.ADAPTERS.items()}
    body = "".join(card(r) for r in rows) or f'<div class="empty">{"Nothing new since last visit." if view=="new" else "Nothing here."}</div>'
    return f"""<!doctype html><meta name=viewport content="width=device-width,initial-scale=1"><title>searches</title><style>{CSS}</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/htmx/2.0.4/htmx.min.js"></script><body>
<header><h1>Saved searches</h1>{tab("new", f'<span class="new">{n_new} new</span>')}{tab("all","all")}{tab("starred","starred")}
<span style="width:10px"></span><a class="tab{' on' if not s else ''}" href="/?view={view}">every search</a>{stabs}
<form hx-post="/seen" hx-target="body" style="margin-left:auto"><button class="tab" type=submit>mark all seen</button></form></header>
<details><summary>manage searches ({len(searches)})</summary>
<form class="s" hx-post="/s" hx-target="body"><input name=name placeholder="name" required><input name=query placeholder="query e.g. red boots" required>
<label>poll every <input name=interval_s type=number min=60 value=900 style="width:90px"> s</label>
<fieldset><legend>platforms</legend>{plats}</fieldset>
<fieldset><legend>filters</legend><div class="rows"></div><select class="add"></select></fieldset>
<span class="err"></span><button>Save search</button></form><ul class="ss">{slist}</ul></details>
<div class="grid">{body}</div>{jscript("fields", poller.FIELDS)}{jscript("support", support)}<script>{FORM_JS}</script></body>"""

@app.post("/seen", response_class=HTMLResponse)
def seen():
    with db() as c: c.execute("INSERT OR REPLACE INTO kv VALUES('last_visit', datetime('now'))")
    return index()

@app.post("/s", response_class=HTMLResponse)
async def create(request: Request):
    form = await request.form()
    platforms = [p for p in form.getlist("platforms") if p in poller.ADAPTERS]
    if platforms and form.get("name") and form.get("query"):
        with db() as c:
            c.execute("INSERT INTO saved_search(name,query,platforms,filters,interval_s) VALUES(?,?,?,?,?)",
                      (form["name"], form["query"], json.dumps(platforms), json.dumps(parse_filters(form.multi_items())),
                       int(form.get("interval_s") or 900)))
    return index()

@app.post("/s/{sid}/toggle", response_class=HTMLResponse)
def toggle(sid: int):
    with db() as c: c.execute("UPDATE saved_search SET active=1-active WHERE id=?", (sid,))
    return index()

@app.post("/s/{sid}/delete", response_class=HTMLResponse)
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
