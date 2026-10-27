# Backlog

Ordered. Top = do first.

## P0: make it run for real

- [x] `.env.example`, `requirements.txt`, `.gitignore` (`*.db`, `.env`, `.venv`, `*.log`)
- [ ] eBay OAuth: client-credentials token auto-refresh in `Ebay` adapter (cache in kv table with expiry) instead of static `EBAY_TOKEN`
- [ ] Vinted: resolve `color_ids` / `size_ids` from name, cache in kv; map `color`/`size` DSL keys automatically
- [ ] `gone` sweep in `poller.main`: set `gone=1` where `last_seen < now - 3*interval_s` and not starred
- [ ] Prune `price_history`: keep only rows where price changed from previous row
- [ ] Verify Depop actor output fields against `_generic_row`; adjust `map_row`
- [ ] Deploy: systemd units (`poller.timer`, `web.service`, optional `mcp.service`), reverse proxy + basic auth

## P1: remaining platforms

Pick per platform: official API > Apify actor > internal JSON endpoint > HTML scrape.

- [ ] grailed: site uses Algolia; check if a public search key is exposed in page source, else Apify
- [ ] mercari: internal GraphQL/`search` endpoint or Apify; US/JP sites differ, confirm which
- [ ] poshmark: Apify; condition + color filters are URL params on site
- [ ] therealreal: scrape, Playwright likely needed
- [ ] vestiaire: Apify or internal `/api/search` endpoint; note shipping to SE
- [ ] Per-adapter filter coverage table in README once done

## P2: UI

- [ ] Edit search in place (query, filters, platforms, interval)
- [ ] Sort: newest / price asc / price drop
- [ ] Price-drop badge on card (compare last two `price_history` rows)
- [ ] Keyboard: j/k navigate, s star, x hide, o open
- [ ] Run-now button per search, calling `poller.run_search`
- [ ] Health strip: last run per platform, fail count (same query as MCP `health`)
- [ ] Image proxy or cache if platform CDNs block hotlinking

## P3: MCP

- [ ] Resource `resale://searches` and `resale://new` for cheap context loading
- [ ] `suggest_filters(query)`: look at result distribution, propose tighter condition/size/brand
- [ ] Bearer auth middleware for streamable-http

## P4: quality

- [ ] Tests: adapter fixtures (recorded JSON), poller diff logic, web routes
- [ ] Dedupe across platforms when same seller cross-lists (title+price+image hash)
- [ ] Rate limiting / jitter per platform; backoff on 403/429
- [ ] Currency normalization to SEK for mixed-platform sorting (ECB rates, cached daily)
- [ ] Retention: delete dismissed + gone listings older than 90 days

## Decided / not doing

- No web UI auth beyond reverse proxy
- No cross-listing or selling features
- No React; htmx only
- Notifications via ntfy only, no email
