SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS transactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT NOT NULL,                 -- ISO YYYY-MM-DD
  description TEXT NOT NULL,
  amount REAL NOT NULL,               -- positive=income, negative=expense
  currency TEXT,
  account TEXT,
  category TEXT,
  subcategory TEXT,
  merchant TEXT,
  source_file TEXT,
  source_row INTEGER,
  unique_hash TEXT NOT NULL UNIQUE,
  raw_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);

CREATE TABLE IF NOT EXISTS budgets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  month TEXT NOT NULL,                -- YYYY-MM
  category TEXT NOT NULL,
  amount REAL NOT NULL,
  UNIQUE(month, category)
);
"""
