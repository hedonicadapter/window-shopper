#!/usr/bin/env python3
"""MCP server over searches.db. pip install mcp
stdio:  python mcp_server.py
http:   MCP_TRANSPORT=streamable-http python mcp_server.py   (put behind caddy + bearer auth for mobile)
"""
import json, os, sqlite3
from mcp.server.fastmcp import FastMCP
import poller

DB = os.environ.get("DB", "searches.db")
mcp = FastMCP("resale-searches")

def db():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c

def rows(q, *a):
    with db() as c: return [dict(r) for r in c.execute(q, a).fetchall()]

@mcp.tool()
def list_searches() -> list[dict]:
    """All saved searches with filters, platforms, last run and unseen-new count."""
    return rows("""SELECT s.*, (SELECT COUNT(*) FROM listing l WHERE l.search_id=s.id
                   AND l.dismissed=0 AND l.first_seen > COALESCE(s.last_run,'')) AS pending
                   FROM saved_search s ORDER BY id""")

@mcp.tool()
def create_search(name: str, query: str, platforms: list[str], filters: dict | None = None,
                  interval_s: int = 900) -> int:
    """Create a saved search. filters keys: price_max, currency, size[], gender, condition[]
    (new|very_good|good|fair), color[], brand[]. platforms: ebay, vinted, depop, ..."""
    with db() as c:
        cur = c.execute("INSERT INTO saved_search(name,query,platforms,filters,interval_s) VALUES(?,?,?,?,?)",
                        (name, query, json.dumps(platforms), json.dumps(filters or {}), interval_s))
        return cur.lastrowid

@mcp.tool()
def update_search(id: int, query: str | None = None, platforms: list[str] | None = None,
                  filters: dict | None = None, active: bool | None = None, interval_s: int | None = None) -> dict:
    """Patch fields of a saved search. filters replaces the whole dict."""
    sets, vals = [], []
    for k, v in [("query", query), ("platforms", platforms), ("filters", filters),
                 ("active", active), ("interval_s", interval_s)]:
        if v is not None:
            sets.append(f"{k}=?"); vals.append(json.dumps(v) if isinstance(v, (list, dict)) else int(v) if isinstance(v, bool) else v)
    with db() as c: c.execute(f"UPDATE saved_search SET {', '.join(sets)} WHERE id=?", (*vals, id))
    return rows("SELECT * FROM saved_search WHERE id=?", id)[0]

@mcp.tool()
def delete_search(id: int) -> str:
    with db() as c: c.execute("DELETE FROM saved_search WHERE id=?", (id,))
    return "deleted"

@mcp.tool()
def run_now(id: int) -> dict:
    """Poll one saved search immediately (also fires ntfy for new hits)."""
    with db() as c:
        s = dict(c.execute("SELECT * FROM saved_search WHERE id=?", (id,)).fetchone())
        poller.run_search(c, s)
    return rows("SELECT platform, ok, n_total, n_new, error FROM run_log WHERE search_id=? ORDER BY id DESC LIMIT 8", id)

@mcp.tool()
def new_listings(search_id: int | None = None, since: str = "-1 day", limit: int = 40,
                 include_dismissed: bool = False) -> list[dict]:
    """Listings first seen since a SQLite time modifier ('-1 day', '-6 hours'), newest first."""
    q = """SELECT key,platform,title,price,currency,condition,size,color,brand,url,image,first_seen,starred
           FROM listing WHERE first_seen >= datetime('now', ?) AND gone=0"""
    a = [since]
    if search_id: q += " AND search_id=?"; a.append(search_id)
    if not include_dismissed: q += " AND dismissed=0"
    return rows(q + " ORDER BY first_seen DESC LIMIT ?", *a, limit)

@mcp.tool()
def mark(keys: list[str], starred: bool | None = None, dismissed: bool | None = None) -> int:
    """Star or dismiss listings by key ('vinted:12345')."""
    with db() as c:
        n = 0
        for k in keys:
            if starred is not None:   n += c.execute("UPDATE listing SET starred=? WHERE key=?", (int(starred), k)).rowcount
            if dismissed is not None: n += c.execute("UPDATE listing SET dismissed=? WHERE key=?", (int(dismissed), k)).rowcount
        return n

@mcp.tool()
def starred() -> list[dict]:
    return rows("SELECT key,platform,title,price,currency,url,gone FROM listing WHERE starred=1 ORDER BY first_seen DESC")

@mcp.tool()
def price_history(key: str) -> list[dict]:
    return rows("SELECT seen, price FROM price_history WHERE key=? ORDER BY seen", key)

@mcp.tool()
def search_adhoc(query: str, platforms: list[str], filters: dict | None = None) -> list[dict]:
    """One-off cross-platform search, not saved, nothing written to db."""
    out = []
    for p in platforms:
        if ad := poller.ADAPTERS.get(p):
            try: out += [poller.asdict(i) for i in ad.fetch(query, filters or {})]
            except Exception as e: out.append({"platform": p, "error": str(e)[:200]})
    return out

@mcp.tool()
def health() -> list[dict]:
    """Last run per platform; surfaces broken adapters."""
    return rows("""SELECT platform, MAX(started) last, SUM(ok=0) fails_24h FROM run_log
                   WHERE started >= datetime('now','-1 day') GROUP BY platform""")

if __name__ == "__main__":
    mcp.run(transport=os.environ.get("MCP_TRANSPORT", "stdio"))
