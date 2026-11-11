"""Regressões da granularidade, escolha da avaliação e prazo por calendário."""

import importlib.util
from pathlib import Path

import duckdb
import pandas as pd
import pytest


def test_order_grain_delivery_rules_and_latest_review():
    orders = pd.DataFrame(
        {
            "order_id": ["same_day", "late", "missing", "canceled"],
            "customer_id": ["c1"] * 4,
            "order_status": ["delivered", "delivered", "delivered", "canceled"],
            "order_purchase_timestamp": ["2018-01-01 10:00:00"] * 4,
            "order_delivered_customer_date": [
                "2018-01-02 23:59:59",
                "2018-01-04",
                None,
                "2018-01-05",
            ],
            "order_estimated_delivery_date": ["2018-01-02"] * 4,
        }
    )
    customers = pd.DataFrame(
        {
            "customer_id": ["c1"],
            "customer_unique_id": ["u1"],
            "customer_state": ["SP"],
        }
    )
    reviews = pd.DataFrame(
        {
            "order_id": ["late", "late", "same_day"],
            "review_id": ["r1", "r2", "r3"],
            "review_score": ["1", "5", "2"],
            "review_answer_timestamp": ["2018-01-05", "2018-01-06", "2018-01-06"],
            "review_creation_date": ["2018-01-05"] * 3,
            "review_comment_title": [""] * 3,
            "review_comment_message": [""] * 3,
        }
    )
    with duckdb.connect() as connection:
        connection.register("raw_orders", orders)
        connection.register("raw_customers", customers)
        connection.register("raw_reviews", reviews)
        sql = Path(__file__).resolve().parents[1] / "sql/build_orders.sql"
        connection.execute(sql.read_text(encoding="utf-8"))
        rows = (
            connection.execute("SELECT * FROM analytics_orders")
            .df()
            .set_index("order_id")
        )
        assert len(rows) == 4
        assert rows.index.is_unique
        assert not rows.loc["same_day", "is_late"]
        assert rows.loc["same_day", "delay_days"] == 0
        assert rows.loc["late", "is_late"]
        assert rows.loc["late", "delay_days"] == 2
        assert rows.loc["late", "review_score"] == 5
        assert rows.loc["late", "review_count"] == 2
        assert rows.loc["missing", ["is_late", "delay_days"]].isna().all()
        assert not rows.loc["canceled", "delivery_eligible"]
        assert pd.isna(rows.loc["canceled", "is_late"])
        counts = connection.execute(
            "SELECT SUM(total_orders), SUM(eligible_orders), SUM(late_orders) FROM reconciliation"
        ).fetchone()
        assert counts == (4, 2, 1)


def test_invalid_key_keeps_previous_active_version(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[1] / "src/build_analytics.py"
    spec = importlib.util.spec_from_file_location("build_analytics", script)
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    monkeypatch.setattr(builder, "ROOT", tmp_path)
    raw = tmp_path / "data/raw"
    raw.mkdir(parents=True)
    for filename, _ in builder.SOURCES.values():
        (raw / filename).write_text("placeholder\nvalue\n", encoding="utf-8")
    (raw / "olist_customers_dataset.csv").write_text(
        "customer_id\nsame\nsame\n", encoding="utf-8"
    )
    (tmp_path / "sql").mkdir()
    (tmp_path / "sql/build_orders.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "requirements.txt").touch()
    processed = tmp_path / "data/processed"
    processed.mkdir()
    pointer = processed / "current.json"
    previous = '{"version":"previous-valid-version"}'
    pointer.write_text(previous, encoding="utf-8")
    with pytest.raises(ValueError, match="Chave inválida"):
        builder.main()
    assert pointer.read_text(encoding="utf-8") == previous
