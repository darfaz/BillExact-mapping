-- db/migrations/001_add_mvp_pilot.sql

CREATE TABLE IF NOT EXISTS matters (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id TEXT NOT NULL,
  client_matter_id TEXT NOT NULL,
  law_firm_matter_id TEXT NOT NULL,
  law_firm_id TEXT NOT NULL,
  description TEXT,
  billing_start TEXT,
  billing_end   TEXT
);

CREATE TABLE IF NOT EXISTS timekeepers (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  classification TEXT NOT NULL,
  rate REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS utbms_overrides (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  phrase TEXT NOT NULL,
  task_code TEXT NOT NULL,
  activity_code TEXT NOT NULL,
  notes TEXT,
  UNIQUE(phrase)
);

CREATE TABLE IF NOT EXISTS bindings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,
  pattern TEXT NOT NULL,
  target TEXT NOT NULL
);
