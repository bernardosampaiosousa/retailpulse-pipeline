from dashboard import load_sample_report


def test_dashboard_uses_committed_pipeline_results():
    data = load_sample_report()
    assert len(data) == 9
    assert {"month", "country", "net_revenue_usd", "paid_orders"}.issubset(data.columns)
    september_br = data[(data.month == "2026-09") & (data.country == "BR")].iloc[0]
    assert september_br.net_revenue_usd == 31.00
