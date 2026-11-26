"""Monthly USD retail KPIs produced with Pandas from SQLite data."""

from pathlib import Path
import sqlite3

import pandas as pd


REPORT_COLUMNS = [
    "month", "country", "gross_revenue_usd", "refunded_usd", "net_revenue_usd",
    "paid_orders", "units_sold", "average_order_value_usd",
]


def monthly_kpis(connection: sqlite3.Connection) -> pd.DataFrame:
    """Groups sales and refunds by month and country to build the summary."""
    sales = pd.read_sql_query(
        "SELECT order_id, ordered_at, country, quantity, unit_price_cents, status FROM transactions",
        connection,
    )
    if sales.empty:
        return pd.DataFrame(columns=REPORT_COLUMNS)

    sales["month"] = sales["ordered_at"].str.slice(0, 7)
    amount = sales["quantity"] * sales["unit_price_cents"]
    paid = sales["status"].eq("PAID")
    refunded = sales["status"].eq("REFUNDED")
    sales["gross_cents"] = amount.where(paid, 0)
    sales["refund_cents"] = amount.where(refunded, 0)
    sales["paid_order_id"] = sales["order_id"].where(paid, None)
    sales["sold_units"] = sales["quantity"].where(paid, 0)

    summary = sales.groupby(["month", "country"], as_index=False, sort=True).agg(
        gross_cents=("gross_cents", "sum"),
        refund_cents=("refund_cents", "sum"),
        paid_orders=("paid_order_id", "nunique"),
        units_sold=("sold_units", "sum"),
    )
    summary["net_cents"] = summary["gross_cents"] - summary["refund_cents"]
    # Round to the nearest cent (half up), using integer math throughout.
    order_count = summary["paid_orders"].where(summary["paid_orders"] > 0, 1)
    summary["aov_cents"] = ((2 * summary["gross_cents"] + order_count) // (2 * order_count)).astype("int64")

    # Convert integer cents to decimal values only at the CSV presentation boundary.
    summary["gross_revenue_usd"] = (summary["gross_cents"] / 100).round(2)
    summary["refunded_usd"] = (summary["refund_cents"] / 100).round(2)
    summary["net_revenue_usd"] = (summary["net_cents"] / 100).round(2)
    summary["average_order_value_usd"] = (summary["aov_cents"] / 100).round(2)

    return summary[REPORT_COLUMNS].reset_index(drop=True)


def write_report(db_path: Path, output_path: Path) -> pd.DataFrame:
    """Exports those KPIs as CSV so they can be used without running Python."""
    if not db_path.is_file():
        raise FileNotFoundError(f"Database not found: {db_path}. Run ingest first.")
    with sqlite3.connect(db_path) as connection:
        frame = monthly_kpis(connection)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False, float_format="%.2f")
    return frame
