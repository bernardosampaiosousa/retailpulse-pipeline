"""CSV ingestion with row-level rejection and idempotent persistence."""

import csv
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from .database import database, save_transaction
from .models import REQUIRED_COLUMNS, ValidationError, parse_transaction


@dataclass(frozen=True)
class IngestStats:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    rejected: int = 0


def ingest_csv(source: Path, db_path: Path, rejected_path: Path) -> IngestStats:
    """Loads valid sales into SQLite and records why other rows were rejected."""
    rejected_path.parent.mkdir(parents=True, exist_ok=True)
    counts = {"inserted": 0, "updated": 0, "unchanged": 0, "rejected": 0}
    seen: set[str] = set()

    # Parse CSV and validate its header before opening a database transaction.
    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ValueError("Input CSV must contain a header")
        missing = set(REQUIRED_COLUMNS) - set(reader.fieldnames)
        if missing:
            raise ValueError(f"CSV missing columns: {', '.join(sorted(missing))}")

        # Keep the previous rejection report if this import fails halfway through.
        temporary_report: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="", dir=rejected_path.parent,
                prefix=f".{rejected_path.name}.", suffix=".tmp", delete=False,
            ) as reject_stream:
                temporary_report = Path(reject_stream.name)
                writer = csv.DictWriter(reject_stream, fieldnames=["row_number", "transaction_id", "reason"])
                writer.writeheader()
                with database(db_path) as conn:
                    with conn:
                        for number, row in enumerate(reader, start=2):
                            if None in row:
                                raise ValueError(f"CSV row {number}: more values than header columns")
                            try:
                                transaction = parse_transaction(row)
                                if transaction.transaction_id in seen:
                                    raise ValidationError("duplicate transaction_id in the same input file")
                            except ValidationError as exc:
                                counts["rejected"] += 1
                                writer.writerow({
                                    "row_number": number,
                                    "transaction_id": (row.get("transaction_id") or "")[:64],
                                    "reason": str(exc),
                                })
                                continue
                            seen.add(transaction.transaction_id)
                            counts[save_transaction(conn, transaction)] += 1

            temporary_report.replace(rejected_path)
        finally:
            if temporary_report is not None:
                temporary_report.unlink(missing_ok=True)

    return IngestStats(**counts)
