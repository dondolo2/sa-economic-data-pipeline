# Design Decisions

This document records the *why* behind the major choices in this project. It exists
so that anyone reviewing the code can understand the reasoning without reading every
file, and so that future-me doesn't repeat decisions I've already justified.

---

## 1. Data sources

### World Bank — CPI (indicator `FP.CPI.TOTL`)
**Chosen because:** keyless REST API, JSON output, stable, well-documented, and
covers South Africa (country code `ZAF`) back to the 1960s.
**Tradeoff:** annual frequency only. Not useful for short-term trend analysis.
**Why it's still worth including:** CPI is the canonical economic indicator, and
having one annual series alongside one daily series forces the pipeline to
normalize across frequencies — which is a real DE problem, not a toy one.

### Frankfurter — USD/ZAR daily exchange rate
**Chosen because:** keyless, JSON, daily granularity, sourced from ECB reference
rates (so the upstream is trustworthy), and supports historical date ranges in a
single call (`/2023-01-01..2024-12-31?from=USD&to=ZAR`).
**Tradeoff:** ECB publishes on business days only. Weekends and holidays are
missing, not zero. The pipeline must treat missing dates as *gaps*, not errors.
**Why it's still worth including:** daily frequency means real time-series
handling, and the missing-date case is a genuine data quality problem that the
validation layer needs to reason about.

### Fuel prices — deferred
**Reason:** there is no free, stable, keyless API for South African fuel prices.
The alternatives were:
- Scrape a government or news site → brittle, breaks weekly, not defensible
  as production code.
- Manually download a CSV and commit it → works, but adds a maintenance burden
  on Day 1 that doesn't demonstrate anything new.

Shipping v1 with two clean programmatic sources is more honest than shipping
three sources where one is a hack. If time allows on Day 6, I'll add fuel prices
via a documented manual CSV with a `scripts/refresh_fuel_prices.md` procedure.

### Why only two sources for v1
Two sources with different shapes (annual + daily, different field names,
different date formats) already exercise every part of the pipeline:
ingestion, schema normalization, frequency handling, idempotency. Adding a third
source before the pipeline is proven is scope creep. The pattern generalizes —
adding a fourth source later is a config change, not a rewrite.

---

## 2. Storage: SQLite instead of PostgreSQL

**Chosen because:**
- **Single writer, analytical read workload.** The pipeline runs as a batch
  job; nothing writes concurrently. SQLite's single-writer limitation is
  irrelevant here.
- **The dataset fits comfortably in one file.** ~60 years of annual CPI plus
  a few years of daily FX is well under 10 MB.
- **Removes a moving part from the demo.** `docker compose up` shouldn't
  require the reviewer to wait for a Postgres container to become healthy.
- **The SQL is identical.** Every query in `src/pipeline/storage/` runs
  unchanged on Postgres.

**Tradeoff acknowledged:** SQLite is not appropriate for concurrent ingestion
or multi-user writes. If this pipeline ever ingested from multiple sources in
parallel, or served an API with concurrent writers, Postgres would be required.

**Mitigation:** the storage layer is abstracted behind a thin DB module
(`src/pipeline/storage/db.py`) that owns the connection string. Swapping to
Postgres is a connection-string change plus running the migrations against a
Postgres instance. No application code changes.

**The question I expect:** *"Why not just use Postgres with Docker?"*
**The answer:** because it would add a health-check dependency, a port, and a
volume to the compose file for a workload that doesn't benefit from any of
those things. Postgres is the right answer for a production deployment of this
pipeline. SQLite is the right answer for a demo that a reviewer runs in under
a minute.

---

## 3. Raw / processed split

**Layout:**
```
data/
├── raw/         # exactly as fetched, never modified
└── processed/   # cleaned, normalized, ready to load
```

**Chosen because:**
- **Raw is immutable.** If a transformation has a bug, I can re-run cleaning
  against the same raw file without re-fetching. This is the single most
  important property of a pipeline for debugging.
- **Separation makes the pipeline legible.** A reviewer opening `data/raw/`
  sees what the source gave me; opening `data/processed/` sees what I decided
  it should look like. The diff between them *is* the transformation logic.
- **It matches how real pipelines are structured.** Bronze/silver/gold,
  landing/curated, raw/refined — the naming varies but the split is universal.

**What "raw" means here:** the exact bytes returned by the API, saved with a
timestamped filename (`worldbank_cpi_2026-09-14T10-32-05Z.json`). Not parsed,
not reformatted, not pretty-printed. If the API changes its response shape
tomorrow, the historical raw files still show what it used to return.

**Gitignored:** `data/raw/*` and `data/processed/*` are not committed, only
`.gitkeep`. Committing generated data is a smell — the pipeline regenerates it.
The `.gitkeep` files exist so the directory structure is present after clone.

---

## 4. Idempotent loads

**The rule:** running `fetch → clean → load` twice must leave the database in
the same state as running it once. Row counts don't grow, values don't duplicate.

**Why this matters:** batch pipelines run on schedules. A cron job that fires
twice because of a retry, or a manual re-run after a fix, must not corrupt the
table. Idempotency is the property that makes a pipeline safe to re-run, which
is the property that makes it safe to operate.

**How it's implemented:**
- Every row is keyed by a natural composite key: `(indicator_name, date, source)`.
- Loads use `INSERT ... ON CONFLICT(indicator_name, date, source) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP`.
- A test (`tests/test_storage.py::test_load_is_idempotent`) runs the load
  twice against a temp DB and asserts the row count is unchanged.

**Alternative considered:** `DELETE FROM ... WHERE source = ?` then re-insert.
Rejected because it loses `created_at` (when the row first appeared) and makes
it impossible to distinguish "value was corrected" from "value was re-fetched
identical."

---

## 5. Schema

**Single table: `economic_indicators`**

```sql
CREATE TABLE economic_indicators (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    indicator_name  TEXT    NOT NULL,   -- 'CPI', 'USD_ZAR'
    date            DATE    NOT NULL,   -- ISO 8601, normalized
    value           REAL    NOT NULL,
    unit            TEXT    NOT NULL,   -- 'index_2010_100', 'ZAR_per_USD'
    source          TEXT    NOT NULL,   -- 'world_bank', 'frankfurter'
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(indicator_name, date, source)
);
```

**Why one table instead of one per indicator:**
- All indicators share the same shape: a named value at a point in time,
  with a unit and a source. A separate table per indicator would duplicate
  the schema N times for zero benefit.
- Adding a new indicator is a data change, not a schema migration.
- Cross-indicator queries (e.g. "CPI vs FX") are natural joins on `date`.

**Why `source` is part of the unique key, not just a column:**
If I ever pull CPI from a second provider (for cross-validation), both
versions should coexist. The key `(indicator_name, date, source)` makes that
possible without conflating them.

**Why `unit` is stored, not inferred:**
Because "value = 5.2" is meaningless without knowing whether that's a percent,
an index, or a currency ratio. Units belong with the data, not in a lookup
table that can drift.

**Why `created_at` AND `updated_at`:**
`created_at` tells me when the pipeline first saw this observation.
`updated_at` tells me when the value last changed. If the upstream revises a
historical figure (which World Bank does), `updated_at` will move and
`created_at` won't — and that revision is itself a signal worth keeping.

**Alternative considered:** a wide table with one column per indicator.
Rejected because it requires a schema migration for every new indicator and
forces every row to be a specific frequency (annual OR daily, not both).

**Alternative considered:** separate `cpi` and `fx_rates` tables.
Rejected as scope creep for two indicators. If this grew past ~10 indicators
with genuinely different semantics (e.g. geospatial, high-frequency tick data),
the split would be justified. It isn't yet.

---

## 6. ETL, not ELT

**Chosen because:**
- **The dataset is small.** ELT's advantage (pushing compute into the
  warehouse) matters at scales this project will never reach.
- **The transformations are semantic, not just mechanical.** Renaming a column
  is ELT-shaped; deciding that a missing FX rate on a weekend is a *gap* not a
  *zero* is a decision that has to happen before the data reaches the database.
- **The raw files are the source of truth, not the database.** In ELT, the
  warehouse holds raw data and transformations run as queries against it. Here,
  `data/raw/` holds the raw data and the database holds cleaned data. This keeps
  the "replay from raw" property intact (see §3).

**When this would change:** if the sources started streaming, or if the volume
made re-transforming expensive, or if multiple consumers wanted different
transformation views of the same raw data — then ELT with a proper warehouse
(dbt, Snowflake/BigQuery) would be the right call.

---

## 7. Streamlit for the dashboard

**Chosen because:**
- It ships a working UI in Python with no frontend code. The dashboard is not
  the point of this project — the pipeline is. Streamlit lets the pipeline be
  the point.
- It reads pandas DataFrames directly, which the pipeline already produces.
- It runs with `streamlit run dashboard/app.py`. No build step, no bundler,
  no node_modules.

**Tradeoff:** Streamlit is not a production dashboarding tool. No auth, no
row-level permissions, no caching at scale, re-runs the whole script on every
interaction. For a portfolio demo that a reviewer runs locally, none of these
matter. For a real internal tool, the answer would be Metabase, Superset, or a
custom frontend.

---

## 8. What this project deliberately does not do

Listing non-goals is as important as listing goals, because it shows the scope
was chosen, not stumbled into.

- **No orchestration framework (Airflow, Prefect, Dagster).** Three tasks
  (`fetch → clean → load`) don't need a scheduler. A `Makefile` or a single
  `main.py` entrypoint is the correct amount of orchestration.
- **No dbt.** Transformation logic is ~150 lines of pandas. Adding dbt would
  add a dependency, a project structure, and a build step to replace code
  that already has tests.
- **No streaming.** Both sources are batch. Kafka or Flink would be
  résumé-driven development.
- **No cloud deployment.** The demo runs locally. Deployment is a
  packaging problem, not a data engineering one, and it isn't what this
  project is trying to demonstrate.
- **No ML / forecasting.** Out of scope. Adding a naive forecast to the
  dashboard would imply rigor that the pipeline doesn't actually have.

---

## 9. Known limitations


1. **Missing dates are not imputed.** Weekend FX gaps stay as gaps. The
   validation layer flags them; the dashboard shows them as gaps. Imputing
   would be a choice, and a wrong one to make silently.
2. **No backfill beyond what the APIs return.** The pipeline fetches a fixed
   historical window on first run, not "everything since 1960."
3. **Annual and daily series are stored in the same table** with no frequency
   column. Frequency is implied by the indicator. This is fine for two
   indicators; it would break at ten.
4. **No alerting.** If a fetch fails, it logs and exits non-zero. There's no
   Slack/email notification. For a batch job run manually, that's correct.
5. **SQLite file lives in a Docker volume.** If the volume is removed, the
   data is gone. Re-running the pipeline rebuilds it from raw files — which
   is exactly the point of keeping raw immutable, but it's still worth naming.

## 11. Canonical schema — one shape for all sources

Both sources produce the same five columns:
`indicator_name, date, value, unit, source`.

**Why a canonical shape at all:** because the loader, the validator, the tests,
and the dashboard should not know or care which source a row came from. Every
`if source == 'world_bank'` in the codebase is a bug waiting to happen. One
shape means one code path.

**Why `date` is a string in the transformed file but `DATE` in the database:**
because the processed CSV should be diffable and human-readable, and ISO 8601
dates in a CSV are both. The database parses them on load. Converting to
`TIMESTAMP` earlier would add timezone semantics we don't want.

## 12. Annual CPI dates: `YYYY-01-01`, not `YYYY-12-31`

The World Bank publishes CPI as an annual average. We must assign it to a
specific day to fit a time-series schema. Two defensible choices:

- **`YYYY-01-01`** — "value for the calendar year YYYY."
- **`YYYY-12-31`** — "value at the end of year YYYY."

Chosen **Jan 1**, matching the World Bank's own data portal convention.
This is a presentation choice, not a claim about measurement timing, and it's
documented here so it can't be mistaken for one.

**Consequence:** a naive `date`-based join between CPI and FX will miss,
because CPI lives at Jan 1 and FX lives at every business day. This is
resolved in the dashboard by joining on **year**, not on date. Noted in
decisions.md because it will bite anyone who reads the data raw.

## 13. Dropped records are counted, not silently ignored

Every transform logs `kept=N skipped(reason=count, reason=count, ...)`.
Nothing is dropped without a log line that says how many and why.

**Why:** silent data loss is the single most common bug in production
pipelines. A pipeline that "succeeds" while quietly discarding 40% of the
input is worse than one that fails loudly. Counting makes the loss visible.