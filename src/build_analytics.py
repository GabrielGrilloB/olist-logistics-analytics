"""Audita os nove CSVs e publica uma versão validada da tabela por pedido."""

import hashlib
import json
import os
import tempfile
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "customers": ("olist_customers_dataset.csv", ["customer_id"]),
    "geolocation": ("olist_geolocation_dataset.csv", []),
    "items": ("olist_order_items_dataset.csv", ["order_id", "order_item_id"]),
    "payments": (
        "olist_order_payments_dataset.csv",
        ["order_id", "payment_sequential"],
    ),
    "reviews": ("olist_order_reviews_dataset.csv", []),
    "orders": ("olist_orders_dataset.csv", ["order_id"]),
    "products": ("olist_products_dataset.csv", ["product_id"]),
    "sellers": ("olist_sellers_dataset.csv", ["seller_id"]),
    "categories": ("product_category_name_translation.csv", ["product_category_name"]),
}
RELATIONSHIPS = [
    ("orders", "customer_id", "customers", "customer_id"),
    ("items", "order_id", "orders", "order_id"),
    ("items", "product_id", "products", "product_id"),
    ("items", "seller_id", "sellers", "seller_id"),
    ("payments", "order_id", "orders", "order_id"),
    ("reviews", "order_id", "orders", "order_id"),
    ("products", "product_category_name", "categories", "product_category_name"),
]


def fingerprint():
    digest = hashlib.sha256()
    paths = [ROOT / "data/raw" / name for name, _ in SOURCES.values()]
    paths += [Path(__file__), ROOT / "sql/build_orders.sql", ROOT / "requirements.txt"]
    for path in paths:
        digest.update(path.name.encode())
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def audit(connection):
    report = {"files": {}, "relationships": {}, "date_checks": {}}
    for table, (filename, key) in SOURCES.items():
        path = ROOT / "data/raw" / filename
        frame = pd.read_csv(path, dtype=str)
        profile = {
            "rows": len(frame),
            "columns": list(frame.columns),
            "duplicate_rows": int(frame.duplicated().sum()),
            "missing": {
                column: int(value) for column, value in frame.isna().sum().items()
            },
        }
        if key:
            profile["duplicate_keys"] = int(frame.duplicated(key).sum())
            profile["missing_keys"] = int(frame[key].isna().any(axis=1).sum())
            if profile["duplicate_keys"] or profile["missing_keys"]:
                raise ValueError(f"Chave inválida em {filename}: {key}")
        report["files"][table] = profile
        connection.execute(
            f"CREATE TABLE raw_{table} AS SELECT * FROM read_csv(?, all_varchar=true)",
            [str(path)],
        )
        for column in frame.columns:
            if (
                column.endswith(("_date", "_timestamp"))
                or column == "order_approved_at"
            ):
                invalid = connection.execute(
                    f'SELECT COUNT(*) FROM raw_{table} WHERE "{column}" IS NOT NULL '
                    f'AND TRY_CAST("{column}" AS TIMESTAMP) IS NULL'
                ).fetchone()[0]
                report["date_checks"][f"{table}.{column}.invalid_format"] = invalid
                if invalid:
                    raise ValueError(f"Data inválida em {table}.{column}")
    for child, foreign, parent, primary in RELATIONSHIPS:
        name = f"{child}.{foreign} -> {parent}.{primary}"
        report["relationships"][name] = connection.execute(
            f"SELECT COUNT(*) FROM raw_{child} c WHERE c.{foreign} IS NOT NULL "
            f"AND NOT EXISTS (SELECT 1 FROM raw_{parent} p WHERE p.{primary}=c.{foreign})"
        ).fetchone()[0]
    # Traduções ausentes serão mantidas e documentadas. As demais relações são críticas.
    critical = {
        key: value
        for key, value in report["relationships"].items()
        if not key.startswith("products.product_category_name") and value
    }
    if critical:
        raise ValueError(f"Referências órfãs: {critical}")
    return report


def validate(connection):
    source_rows = connection.execute("SELECT COUNT(*) FROM raw_orders").fetchone()[0]
    result = connection.execute("SELECT * FROM analytics_orders").df()
    if len(result) != source_rows or result.order_id.nunique() != source_rows:
        raise ValueError("O cruzamento alterou a granularidade por pedido")
    # Cálculo independente do SQL para conferir elegibilidade, atraso e duração.
    orders = connection.execute("SELECT * FROM raw_orders").df().set_index("order_id")
    if set(result.order_id) != set(orders.index):
        raise ValueError("Conjunto de pedidos alterado")
    actual = result.set_index("order_id").reindex(orders.index)
    purchase = pd.to_datetime(orders.order_purchase_timestamp)
    delivery = pd.to_datetime(orders.order_delivered_customer_date)
    estimate = pd.to_datetime(orders.order_estimated_delivery_date)
    eligible = (
        orders.order_status.eq("delivered")
        & purchase.notna()
        & delivery.notna()
        & estimate.notna()
        & delivery.ge(purchase)
        & estimate.dt.normalize().ge(purchase.dt.normalize())
    )
    pd.testing.assert_series_equal(
        actual.delivery_eligible, eligible, check_names=False
    )
    expected_late = delivery.dt.normalize().gt(estimate.dt.normalize())
    assert actual.loc[eligible, "is_late"].astype(bool).equals(expected_late[eligible])
    expected_days = (delivery.dt.normalize() - estimate.dt.normalize()).dt.days.clip(
        lower=0
    )
    assert (
        actual.loc[eligible, "delay_days"]
        .astype(int)
        .equals(expected_days[eligible].astype(int))
    )
    assert actual.loc[~eligible, ["is_late", "delay_days"]].isna().all().all()
    reconciliation = connection.execute("SELECT * FROM reconciliation").df()
    assert reconciliation.total_orders.sum() == source_rows
    assert reconciliation.eligible_orders.sum() == eligible.sum()
    assert reconciliation.late_orders.sum() == expected_late[eligible].sum()
    return {
        "orders": source_rows,
        "eligible_orders": int(eligible.sum()),
        "late_orders": int(expected_late[eligible].sum()),
        "late_rate": float(expected_late[eligible].mean()),
        "orders_with_multiple_reviews": int((result.review_count > 1).sum()),
        "orders_without_review": int((result.review_count == 0).sum()),
        "delivered_missing_delivery_date": int(
            (orders.order_status.eq("delivered") & delivery.isna()).sum()
        ),
        "delivery_before_purchase": int(delivery.lt(purchase).sum()),
        "estimate_before_purchase_day": int(
            estimate.dt.normalize().lt(purchase.dt.normalize()).sum()
        ),
    }


def render_report(report):
    lines = [
        "# Auditoria dos dados Olist",
        "",
        "Relatório gerado por `python src/build_analytics.py`.",
        "",
        "| Arquivo | Linhas | Duplicatas exatas | Campos vazios |",
        "|---|---:|---:|---:|",
    ]
    for table, profile in report["files"].items():
        lines.append(
            f"| {table} | {profile['rows']} | {profile['duplicate_rows']} | "
            f"{sum(profile['missing'].values())} |"
        )
    lines += ["", "## Integridade referencial", ""]
    for name, count in report["relationships"].items():
        lines.append(f"- `{name}` tem {count} referências ausentes.")
    lines += ["", "## Resultado validado", ""]
    for name, count in report["summary"].items():
        lines.append(f"- `{name}` = {count}")
    lines += [
        "",
        "## Tratamento",
        "",
        "- Os nove arquivos originais são preservados. As duplicatas de geolocalização são registradas e essa tabela fica fora do cruzamento por pedido.",
        "- Comentários vazios são permitidos. Nota ausente fica nula e a cobertura das avaliações deve acompanhar as comparações.",
        "- Traduções de categoria ausentes são documentadas. Clientes e pedidos com chaves inválidas bloqueiam a publicação.",
        "- Pedidos sem datas válidas ou com cronologia inconsistente permanecem na tabela e ficam fora do denominador de atraso.",
        "- A data prometida é interpretada como um dia de calendário. Uma entrega no mesmo dia é pontual, independentemente do horário.",
        "- Entre múltiplas avaliações, escolhe-se a resposta mais recente. Os critérios de desempate estão no SQL.",
        "- Confira `audit.json` na versão local para as contagens por coluna e verificações de formato de datas.",
        "",
    ]
    return "\n".join(lines)


def main():
    processed = ROOT / "data/processed"
    versions = processed / "versions"
    versions.mkdir(parents=True, exist_ok=True)
    run_id = fingerprint()
    version = versions / run_id
    with tempfile.TemporaryDirectory(dir=versions) as temporary:
        staging = Path(temporary) / "validated"
        staging.mkdir()
        with duckdb.connect(str(staging / "olist.duckdb")) as connection:
            report = audit(connection)
            connection.execute(
                (ROOT / "sql/build_orders.sql").read_text(encoding="utf-8")
            )
            report["summary"] = validate(connection)
            for filename, query, options in [
                (
                    "orders.parquet",
                    "SELECT * FROM analytics_orders ORDER BY order_id",
                    "FORMAT PARQUET",
                ),
                (
                    "reconciliation.csv",
                    "SELECT * FROM reconciliation ORDER BY 1, 2",
                    "FORMAT CSV, HEADER",
                ),
            ]:
                connection.execute(
                    f"COPY ({query}) TO ? ({options})", [str(staging / filename)]
                )
        (staging / "audit.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        markdown = render_report(report)
        (staging / "audit.md").write_text(markdown, encoding="utf-8")
        if not version.exists():
            staging.rename(version)
    # A versão ativa só muda depois de todas as verificações terminarem.
    with tempfile.NamedTemporaryFile(
        mode="w", dir=processed, delete=False, encoding="utf-8"
    ) as pointer:
        json.dump(
            {"version": run_id, "directory": f"versions/{run_id}"}, pointer, indent=2
        )
        pointer_path = pointer.name
    os.replace(pointer_path, processed / "current.json")
    (ROOT / "docs/data_audit.md").write_text(markdown, encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"Versão validada em {version}")


if __name__ == "__main__":
    main()
