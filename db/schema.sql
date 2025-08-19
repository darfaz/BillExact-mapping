-- Database schema for the Passive Activity‑to‑LEDES Translator
-- This file defines the tables required by the application. It is intended
-- to be executed once during app initialization to create the necessary
-- tables when running locally. When deployed to Databutton, the built‑in
-- database can be initialized using these statements via the Databutton
-- dashboard or programmatically via sqlite3.

-- Table storing keyword mappings between free‑text activity descriptions
-- and UTBMS task/activity codes. Each keyword row includes an optional
-- confidence_boost value (0–1) that influences scoring in the
-- categorization algorithm. The keyword field is marked unique to avoid
-- duplicate entries.
CREATE TABLE IF NOT EXISTS utbms_keywords (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  keyword TEXT NOT NULL UNIQUE,
  task_code TEXT NOT NULL,
  activity_code TEXT NOT NULL,
  confidence_boost REAL DEFAULT 0.8,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table storing individual time entries derived from ActivityWatch
-- events. Each row represents a discrete block of work with a
-- timestamp, duration, mapped UTBMS codes and financial details.
CREATE TABLE IF NOT EXISTS time_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT,
  client_id TEXT,
  matter_id TEXT,
  timekeeper_id TEXT,
  timekeeper_name TEXT,
  date DATE,
  -- Confidence score from the categorisation algorithm (0–1). Higher
  -- values indicate greater certainty that the assigned task and
  -- activity codes are correct.
  confidence REAL,
  -- The exact timestamp (UTC) when the underlying ActivityWatch event
  -- occurred. Stored as an ISO 8601 string. Used for deduplication.
  timestamp TEXT,
  description TEXT,
  duration_hours REAL,
  task_code TEXT,
  activity_code TEXT,
  rate REAL,
  total REAL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);