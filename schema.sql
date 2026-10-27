PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS saved_search (
  id         INTEGER PRIMARY KEY,
  name       TEXT NOT NULL,
  query      TEXT NOT NULL,
  -- normalized filter DSL, mapped per adapter:
  -- {"price_max":350,"currency":"SEK","size":["43"],"gender":"men",
  --  "condition":["new","very_good"],"color":["red"],"brand":[]}
  filters    TEXT NOT NULL DEFAULT '{}',
  platforms  TEXT NOT NULL,                -- json array: ["ebay","vinted",...]
  active     INTEGER NOT NULL DEFAULT 1,
  interval_s INTEGER NOT NULL DEFAULT 900,
  last_run   TEXT,
  created    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS listing (
  key        TEXT PRIMARY KEY,             -- "<platform>:<platform_id>"
  platform   TEXT NOT NULL,
  search_id  INTEGER NOT NULL REFERENCES saved_search(id) ON DELETE CASCADE,
  title      TEXT,
  price      REAL,
  currency   TEXT,
  url        TEXT NOT NULL,
  image      TEXT,
  condition  TEXT,
  size       TEXT,
  color      TEXT,
  brand      TEXT,
  first_seen TEXT NOT NULL DEFAULT (datetime('now')),
  last_seen  TEXT NOT NULL DEFAULT (datetime('now')),
  gone       INTEGER NOT NULL DEFAULT 0,   -- not seen in N consecutive runs
  starred    INTEGER NOT NULL DEFAULT 0,
  dismissed  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS listing_search_seen ON listing(search_id, first_seen DESC);

CREATE TABLE IF NOT EXISTS price_history (
  key  TEXT NOT NULL REFERENCES listing(key) ON DELETE CASCADE,
  seen TEXT NOT NULL DEFAULT (datetime('now')),
  price REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS run_log (
  id        INTEGER PRIMARY KEY,
  search_id INTEGER,
  platform  TEXT,
  started   TEXT NOT NULL DEFAULT (datetime('now')),
  ok        INTEGER,
  n_total   INTEGER,
  n_new     INTEGER,
  error     TEXT
);
