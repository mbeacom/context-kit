# data files (`duckdb`, `sqlite-utils`)

Run real SQL over CSV / Parquet / JSON without importing first. Reach for these
when the question involves joins, aggregation, or large tabular data — where
`jq`/`rg` would be slow or awkward.

## duckdb — analytical SQL over files

```bash
duckdb -c "SELECT * FROM 'f.csv' LIMIT 5"            # peek at a CSV
duckdb -c "DESCRIBE SELECT * FROM 'f.csv'"           # inferred schema/types
duckdb -c "SELECT * FROM 'events.parquet' LIMIT 5"   # Parquet read directly
duckdb -c "SELECT * FROM 'records.json' LIMIT 5"     # JSON read directly
```

Aggregate and group:

```bash
duckdb -c "
  SELECT status, count(*) AS n, avg(latency_ms) AS avg_ms
  FROM 'logs.parquet'
  GROUP BY status
  ORDER BY n DESC"
```

Scan many files at once with a glob:

```bash
duckdb -c "SELECT count(*) FROM 'data/*.parquet'"    # union by glob
duckdb -c "SELECT * FROM read_csv_auto('data/*.csv') LIMIT 10"
```

## sqlite-utils — quick SQLite/CSV queries

```bash
sqlite-utils memory data.csv "select count(*) from data"   # in-memory, no file
sqlite-utils memory a.csv b.csv \
  "select * from a join b on a.id = b.id"                  # ad-hoc join
sqlite-utils memory data.csv "select * from data limit 5" --csv   # CSV output
sqlite-utils memory data.csv "select * from data limit 5" --json  # JSON output
```

## When SQL beats jq / rg

- **Joins** across two or more files (by key).
- **Aggregation**: `GROUP BY`, `count`, `avg`, `sum`, window functions.
- **Large tabular** data where streaming line-greps are slow or lose structure.
- You want **typed columns** and a real query planner rather than text munging.

Use `duckdb` for analytical Parquet/CSV at scale; `sqlite-utils memory` for quick
one-off SQL over a CSV without setting up a database.
