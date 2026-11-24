"""Minimal command-line interface for local use and CI."""

import argparse
from pathlib import Path

from .ingest import ingest_csv
from .report import write_report


SAMPLE_CSV = Path(__file__).resolve().parent.parent / "data" / "sample_sales.csv"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="retailpulse", description="Validate, store and analyze retail sales CSVs."
    )
    command = parser.add_subparsers(dest="command", required=True)

    ingest = command.add_parser("ingest", help="Load a CSV into SQLite with validation")
    ingest.add_argument("--input", type=Path, required=True)
    ingest.add_argument("--db", type=Path, default=Path("output/retailpulse.sqlite"))
    ingest.add_argument("--rejects", type=Path, default=Path("output/rejected_rows.csv"))

    report = command.add_parser("report", help="Generate monthly country-level KPIs")
    report.add_argument("--db", type=Path, default=Path("output/retailpulse.sqlite"))
    report.add_argument("--output", type=Path, default=Path("output/monthly_kpis.csv"))

    demo = command.add_parser("demo", help="Run the pipeline on synthetic sample data")
    demo.add_argument("--output-dir", type=Path, default=Path("output/demo"))

    args = parser.parse_args(argv)
    if args.command == "ingest":
        stats = ingest_csv(args.input, args.db, args.rejects)
        print(f"Ingestion complete: {stats.inserted} inserted, {stats.updated} updated, "
              f"{stats.unchanged} unchanged, {stats.rejected} rejected")
        print(f"Rejected rows: {args.rejects}")
    elif args.command == "report":
        summary = write_report(args.db, args.output)
        print(f"Report generated: {len(summary)} groups -> {args.output}")
    else:
        db = args.output_dir / "retailpulse.sqlite"
        rejected = args.output_dir / "rejected_rows.csv"
        output = args.output_dir / "monthly_kpis.csv"
        stats = ingest_csv(SAMPLE_CSV, db, rejected)
        summary = write_report(db, output)
        print(f"Demo ingested: {stats.inserted} new, {stats.updated} updated, "
              f"{stats.unchanged} unchanged, {stats.rejected} rejected")
        print(f"Monthly report: {output}")
        print(summary.to_string(index=False))
    return 0
