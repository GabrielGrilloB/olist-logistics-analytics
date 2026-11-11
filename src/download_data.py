"""Baixa e extrai os CSVs públicos da Olist, sem publicar os dados no Git."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from urllib.request import Request, urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
URL = "https://www.kaggle.com/api/v1/datasets/download/olistbr/brazilian-ecommerce"
EXPECTED = {
    "olist_customers_dataset.csv", "olist_geolocation_dataset.csv",
    "olist_order_items_dataset.csv", "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv", "olist_orders_dataset.csv",
    "olist_products_dataset.csv", "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="ZIP já baixado do Kaggle")
    args = parser.parse_args()
    destination = ROOT / "data" / "raw"
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        archive = args.archive
        if archive is None:
            archive = Path(temporary) / "olist.zip"
            print("Baixando base pública da Olist...", flush=True)
            request = Request(URL, headers={"User-Agent": "olist-portfolio/1.0"})
            with urlopen(request, timeout=120) as response, archive.open("wb") as output:
                shutil.copyfileobj(response, output)
        with ZipFile(archive) as zipped:
            available = set(zipped.namelist())
            missing = EXPECTED - available
            if missing:
                raise ValueError(f"Arquivos ausentes no ZIP: {sorted(missing)}")
            for name in EXPECTED:
                if (destination / name).exists():
                    raise FileExistsError(f"Arquivo já existe: {destination / name}")
            staging = Path(temporary) / "extracted"
            staging.mkdir()
            manifest = {}
            for name in sorted(EXPECTED):
                target = staging / name
                with zipped.open(name) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
                manifest[name] = {
                    "bytes": target.stat().st_size,
                    "sha256": hashlib.file_digest(target.open("rb"), "sha256").hexdigest(),
                }
            for name in sorted(EXPECTED):
                shutil.move(str(staging / name), str(destination / name))
            (destination / "manifest.json").write_text(
                json.dumps({"source": URL, "files": manifest}, indent=2), encoding="utf-8"
            )
    print(f"OK: nove CSVs extraídos em {destination}")


if __name__ == "__main__":
    main()
