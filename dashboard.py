"""A small dashboard for the sample reports produced by RetailPulse."""

from pathlib import Path

import pandas as pd


REPORT = Path(__file__).resolve().parent / "examples" / "monthly_kpis.csv"


def load_sample_report(path: Path = REPORT) -> pd.DataFrame:
    """Load the checked-in pipeline output so the demo needs no database."""
    return pd.read_csv(path, dtype={"month": str, "country": str})


def main() -> None:
    """Shows the sample KPIs with country filters; no database is needed to browse them."""
    import streamlit as st

    st.set_page_config(page_title="RetailPulse", layout="wide")
    st.title("RetailPulse")
    st.caption("Monthly sales from fictional transactions. Source: examples/monthly_kpis.csv")

    report = load_sample_report()
    countries = sorted(report["country"].unique().tolist())
    selected = st.multiselect("Countries", countries, default=countries)
    filtered = report.loc[report["country"].isin(selected)]

    if filtered.empty:
        st.info("Choose at least one country to see the report.")
        return

    gross = filtered["gross_revenue_usd"].sum()
    refunds = filtered["refunded_usd"].sum()
    net = filtered["net_revenue_usd"].sum()
    orders = int(filtered["paid_orders"].sum())

    gross_col, refunds_col, net_col, orders_col = st.columns(4)
    gross_col.metric("Gross sales", "$" + f"{gross:,.2f}")
    refunds_col.metric("Refunds", "$" + f"{refunds:,.2f}")
    net_col.metric("Net sales", "$" + f"{net:,.2f}")
    orders_col.metric("Paid orders", f"{orders:,}")

    st.subheader("Net revenue by month")
    by_month = filtered.groupby("month", as_index=True)["net_revenue_usd"].sum()
    st.bar_chart(by_month, y_label="USD", x_label="Month")

    st.subheader("Monthly breakdown")
    st.dataframe(
        filtered.sort_values(["month", "country"]),
        hide_index=True,
        width="stretch",
    )
    st.caption("To update the numbers, run the pipeline and replace the sample report.")


if __name__ == "__main__":
    main()
