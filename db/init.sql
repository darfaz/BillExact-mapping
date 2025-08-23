CREATE TABLE IF NOT EXISTS clients (client_id TEXT PRIMARY KEY, name TEXT);
CREATE TABLE IF NOT EXISTS matters (matter_id TEXT PRIMARY KEY, client_id TEXT, description TEXT);
CREATE TABLE IF NOT EXISTS timekeepers (id TEXT PRIMARY KEY, name TEXT);
CREATE TABLE IF NOT EXISTS time_entries (
  id INTEGER PRIMARY KEY,
  date TEXT,
  description TEXT,
  duration REAL,
  utbms_code TEXT,
  matter_id TEXT,
  client_id TEXT,
  timekeeper_id TEXT
);
