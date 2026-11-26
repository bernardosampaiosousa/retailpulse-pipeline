# RetailPulse

RetailPulse is a Python project for turning retail CSV exports into a small SQLite database and monthly sales reports.

I made it to practice the less glamorous part of data work: cleaning up inconsistent input, keeping reimports predictable, and making sure refunds don't inflate revenue. The included data is fictional, so you can run everything locally.

## Try it with the sample data

Python 3.11+ is required. You don't need Docker or an external database.

On Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m retailpulse demo
```

On macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m retailpulse demo
```

The demo writes three files to `output/demo/`:

| File | What it's for |
| --- | --- |
| `retailpulse.sqlite` | Cleaned transactions you can query with SQL |
| `rejected_rows.csv` | Row numbers and reasons for rejected records |
| `monthly_kpis.csv` | Revenue, refunds, orders, units, and average order value |

Run the demo twice. On the second run, the same transactions are reported as unchanged rather than inserted again.

The generated examples are also checked into [`examples/`](examples/), so you can inspect the output without installing Python.

## Optional dashboard

There is a small Streamlit dashboard in [`dashboard.py`](dashboard.py). It reads the checked-in monthly report, so anyone can reproduce the charts without a database or a separate website.

```bash
python -m pip install -e '.[dashboard]'
streamlit run dashboard.py
```

It has country filters, sales totals, a monthly net-revenue chart, and the report table. The previous externally hosted dashboard isn't required to run this version.

## What the pipeline does

1. Reads a CSV and checks the required columns.
2. Validates dates, IDs, country codes, quantities, statuses, and USD prices.
3. Stores accepted transactions in SQLite, keyed by `transaction_id`.
4. Saves rejected row numbers and explanations in a separate CSV.
5. Uses Pandas to calculate monthly metrics by country.

`PAID` rows add to gross revenue; `REFUNDED` rows subtract from net revenue; `CANCELLED` rows don't affect revenue. Multiple paid lines on the same order count as one paid order for average order value.

The sample includes intentional data errors. From one clean run, the September Brazil summary is:

| Gross revenue | Refunds | Net revenue | Paid orders |
| ---: | ---: | ---: | ---: |
| $130.90 | $99.90 | $31.00 | 2 |

## Use another file

Your input needs these columns:

```text
transaction_id,order_id,customer_id,ordered_at,country,category,quantity,unit_price_usd,status
```

- `ordered_at` uses YYYY-MM-DD.
- `country` is a two-letter code.
- `quantity` must be between 1 and 1000.
- `unit_price_usd` must be positive with no fractional cents.
- `status` is PAID, REFUNDED, or CANCELLED.

Run the two steps separately:

```bash
python -m retailpulse ingest --input data/sample_sales.csv --db output/sales.sqlite --rejects output/rejected_rows.csv
python -m retailpulse report --db output/sales.sqlite --output output/monthly_kpis.csv
```

I used Python's `Decimal` to parse prices and store them as integer cents. This avoids rounding errors while saving data. The ingestion uses a SQLite transaction, and an unexpected CSV format error rolls back the batch. The rejection report is written to a temporary file first, so a failed import doesn't overwrite the previous report.

## Source and tests

- [`retailpulse/models.py`](retailpulse/models.py) validates a transaction.
- [`retailpulse/ingest.py`](retailpulse/ingest.py) handles CSV imports.
- [`retailpulse/database.py`](retailpulse/database.py) handles SQLite writes.
- [`retailpulse/report.py`](retailpulse/report.py) calculates monthly metrics.
- [`tests/`](tests/) covers validation, repeated imports, corrected records, and reports.

Run the tests with:

```bash
python -m pytest -q
```

GitHub Actions runs the tests and regenerates the sample report.

## What isn't covered

The pipeline processes an entire CSV in memory during reporting, so it isn't designed for huge datasets. It doesn't have scheduling, migrations, or anomaly detection. Those would make sense if I extended it beyond a local exercise.

The sample dashboard uses committed output rather than live sales data. To refresh it, run the pipeline and update `examples/monthly_kpis.csv`.

MIT license.
