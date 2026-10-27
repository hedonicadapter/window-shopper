# resale-watch

Self-hosted saved-search aggregator for secondhand fashion marketplaces. Cron polls each platform with native filters (condition, color, size, price), diffs against SQLite, pushes new hits via ntfy. Web UI for triage, MCP server for Claude.

Replaces Gem/Crawli/Gently: those drop platform-specific filters and don't cover all of eBay, Vinted, Depop, Grailed, Mercari, Poshmark, TheRealReal, Vestiaire Collective.

## Layout

```
schema.sql      SQLite schema (saved_search, listing, price_history, run_log)
poller.py       adapters + diff + notify; run from cron
web.py          FastAPI + htmx UI (new / all / starred, star, hide, CRUD searches)
mcp_server.py   FastMCP server over same db + ad-hoc cross-platform search
```

All three share one `searches.db`. Poller writes, UI and MCP read/write flags.

## Setup

```sh
python -m venv .venv && . .venv/bin/activate
pip install requests fastapi uvicorn python-multipart mcp
cp .env.example .env   # see Env
python poller.py       # creates db from schema.sql on first run
uvicorn web:app --port 8080
```

Cron:

```
*/15 * * * * cd /opt/resale-watch && . .venv/bin/activate && set -a && . .env && python poller.py >> poller.log 2>&1
```

Per-search `interval_s` gates actual polling; cron just ticks.

MCP (Claude Code `.mcp.json`):

```json
{"mcpServers": {"resale": {"command": "/opt/resale-watch/.venv/bin/python",
  "args": ["/opt/resale-watch/mcp_server.py"], "env": {"DB": "/opt/resale-watch/searches.db"}}}}
```

Remote: `MCP_TRANSPORT=streamable-http`, reverse proxy + bearer, add as custom connector in Claude app.

## Env

| var | used by | note |
|---|---|---|
| `DB` | all | path to sqlite, default `searches.db` |
| `EBAY_TOKEN` | poller | OAuth client-credentials, scope `https://api.ebay.com/oauth/api_scope`; expires 2h, see backlog |
| `APIFY_TOKEN` | poller | for Apify-backed adapters |
| `VINTED_COOKIE` | poller | optional; `_vinted_fr_session=...` from browser, avoids 403 |
| `NTFY_TOPIC` | poller | full URL e.g. `https://ntfy.sh/<secret>` |
| `MCP_TRANSPORT` | mcp | `stdio` (default) or `streamable-http` |

## Filter DSL

Stored as JSON in `saved_search.filters`. Adapters map what they can, ignore the rest.

```json
{"price_max": 350, "currency": "SEK", "size": ["43"], "gender": "men",
 "condition": ["new", "very_good", "good", "fair"], "color": ["red"], "brand": [],
 "color_ids": [], "size_ids": []}
```

`color_ids` / `size_ids` are Vinted-specific numeric ids (per locale). Resolve via `GET /api/v2/colors`, `GET /api/v2/sizes` on vinted.se.

## Adapter contract

```python
class X:
    name = "x"
    def fetch(self, query: str, filters: dict) -> list[poller.Item]: ...
```

Register in `poller.ADAPTERS`. `Item.platform_id` must be stable per listing; it forms the primary key `platform:id`. Return newest-first, ~50 items; the poller handles dedupe and price-change tracking. Raise on failure; poller logs to `run_log` and continues.

Apify-backed adapters are config: `Apify(name, actor_id, build_input, map_row)`.

## Platform status

| platform | method | stability |
|---|---|---|
| ebay | official Browse API, `EBAY_SE` | stable |
| vinted | internal `/api/v2/catalog/items` | unofficial, years-stable, cookie helps |
| depop | Apify `nerolabs~depop-marketplace-monitor` | depends on actor |
| grailed | TODO (Algolia-backed site) | — |
| mercari | TODO (Apify or internal) | — |
| poshmark | TODO (Apify) | — |
| therealreal | TODO (scrape) | — |
| vestiaire | TODO (Apify or scrape) | — |

## Data lifecycle

- `listing.first_seen` drives "new since last visit" (UI) and `new_listings(since=)` (MCP).
- `dismissed=1` hides permanently; `starred=1` pins.
- `gone` is declared in schema but never set yet, see backlog.
- `price_history` appends every poll; prune in backlog.

## Testing

No test suite yet. Smoke: seed db, `TestClient(web.app)`, hit `/`, `/l/{key}/star`, `/seen`. Adapters: run `poller.search_adhoc`-style via `python -c "import poller; print(poller.ADAPTERS['vinted'].fetch('red boots', {'price_max':350}))"`.
