"""End-to-end local pipeline tests using disposable SQLite files."""

import csv
from pathlib import Path
import sqlite3

import pytest

from retailpulse.cli import main
from retailpulse.database import database
from retailpulse.ingest import ingest_csv
from retailpulse.report import REPORT_COLUMNS, write_report


SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample_sales.csv"


def count_rows(path: Path) -> int:
    with sqlite3.connect(path) as conn:
        return conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]


def test_sample_ingestion_counts_and_rejection_report(tmp_path):
    db = tmp_path / "retail.sqlite"
    rejects = tmp_path / "rejects.csv"
    stats = ingest_csv(SAMPLE, db, rejects)
    assert (stats.inserted, stats.updated, stats.unchanged, stats.rejected) == (14, 0, 0, 3)
    assert count_rows(db) == 14
    with rejects.open(newline="", encoding="utf-8") as stream:
        records = list(csv.DictReader(stream))
    assert len(records) == 3
    assert "unit_price_usd" in records[0]["reason"]
    assert "duplicate transaction_id" in records[-1]["reason"]
    assert set(records[0]) == {"row_number", "transaction_id", "reason"}


def test_repeated_ingestion_is_idempotent(tmp_path):
    db = tmp_path / "retail.sqlite"
    rejects = tmp_path / "rejects.csv"
    ingest_csv(SAMPLE, db, rejects)
    stats = ingest_csv(SAMPLE, db, rejects)
    assert (stats.inserted, stats.updated, stats.unchanged, stats.rejected) == (0, 0, 14, 3)
    assert count_rows(db) == 14


def test_later_file_corrects_existing_record(tmp_path):
    db = tmp_path / "retail.sqlite"
    rejects = tmp_path / "rejects.csv"
    ingest_csv(SAMPLE, db, rejects)
    header, *lines = SAMPLE.read_text(encoding="utf-8").splitlines()
    amended = tmp_path / "amended.csv"
    amended.write_text(header + "\n" + lines[0].replace("99.90", "129.90") + "\n", encoding="utf-8")
    stats = ingest_csv(amended, db, rejects)
    assert stats.updated == 1
    assert stats.inserted == 0
    assert count_rows(db) == 14
    with sqlite3.connect(db) as connection:
        price = connection.execute(
            "SELECT unit_price_cents FROM transactions WHERE transaction_id = 'TX-001'"
        ).fetchone()[0]
    assert price == 12990


def test_missing_csv_header_does_not_create_database(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("foo,bar\n1,2\n", encoding="utf-8")
    db = tmp_path / "retail.sqlite"
    with pytest.raises(ValueError, match="missing columns"):
        ingest_csv(path, db, tmp_path / "rejects.csv")
    assert not db.exists()


def test_unexpected_format_error_rolls_back_earlier_rows(tmp_path):
    lines = SAMPLE.read_text(encoding="utf-8").splitlines()
    path = tmp_path / "broken.csv"
    path.write_text("\n".join(lines[:2] + [lines[2] + ",EXTRA"]) + "\n", encoding="utf-8")
    db = tmp_path / "retail.sqlite"
    with pytest.raises(ValueError, match="more values"):
        ingest_csv(path, db, tmp_path / "rejects.csv")
    assert count_rows(db) == 0


def test_monthly_kpis_handle_refunds_cancelled_orders_and_aov(tmp_path):
    db = tmp_path / "retail.sqlite"
    ingest_csv(SAMPLE, db, tmp_path / "rejects.csv")
    frame = write_report(db, tmp_path / "report.csv")
    assert list(frame.columns) == REPORT_COLUMNS

    brazil_september = frame.loc[(frame.month == "2026-09") & (frame.country == "BR")].iloc[0]
    assert brazil_september.gross_revenue_usd == 130.90
    assert brazil_september.refunded_usd == 99.90
    assert brazil_september.net_revenue_usd == 31.00
    assert brazil_september.paid_orders == 2
    assert brazil_september.units_sold == 3
    assert brazil_september.average_order_value_usd == 65.45

    # 139.79 / 2 is 69.895; monetary output must round half-up to 69.90.
    brazil_october = frame.loc[(frame.month == "2026-10") & (frame.country == "BR")].iloc[0]
    assert brazil_october.average_order_value_usd == 69.90

    us_october = frame.loc[(frame.month == "2026-10") & (frame.country == "US")].iloc[0]
    assert us_october.gross_revenue_usd == 149.95
    assert us_october.paid_orders == 1
    assert us_october.units_sold == 1


def test_report_on_empty_database_has_headers(tmp_path):
    db = tmp_path / "empty.sqlite"
    with database(db):
        pass
    output = tmp_path / "empty.csv"
    frame = write_report(db, output)
    assert frame.empty
    assert output.read_text(encoding="utf-8").startswith("month,country,gross_revenue_usd")


def test_report_requires_an_existing_database(tmp_path):
    with pytest.raises(FileNotFoundError, match="Run ingest first"):
        write_report(tmp_path / "does-not-exist.sqlite", tmp_path / "report.csv")


def test_demo_command_is_repeatable(tmp_path, capsys):
    destination = tmp_path / "demo"
    assert main(["demo", "--output-dir", str(destination)]) == 0
    assert "14 new" in capsys.readouterr().out
    assert main(["demo", "--output-dir", str(destination)]) == 0
    assert "14 unchanged" in capsys.readouterr().out
    assert count_rows(destination / "retailpulse.sqlite") == 14
    assert (destination / "monthly_kpis.csv").exists()
