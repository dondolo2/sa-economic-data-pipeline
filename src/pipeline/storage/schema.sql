-- Canonical observation table.
-- Natural key (indicator_name, date, source) is what makes loads idempotent:
-- re-running the loader conflicts on this key and updates in place.
CREATE TABLE IF NOT EXISTS economic_indicators (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    indicator_name  TEXT      NOT NULL,
    date            DATE      NOT NULL,
    value           REAL      NOT NULL,
    unit            TEXT      NOT NULL,
    source          TEXT      NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(indicator_name, date, source)
);

CREATE INDEX IF NOT EXISTS idx_indicator_date
    ON economic_indicators (indicator_name, date);