"""
Converte cameras.xlsx para CSV normalizado com colunas esperadas pelos scripts.
Uso: python xlsx_to_csv.py [--input cameras.xlsx] [--output saida.csv]
"""

import argparse
import csv
import sys
import unicodedata
from pathlib import Path

import openpyxl

# Cada coluna destino aceita mais de um nome de origem, porque a planilha de
# cameras existe em mais de um formato de exportacao.
COLUMN_MAPPING = {
    "Name": ("Nome",),
    "Vendor": ("Fabricante:", "Fabricante"),
    "Model": ("Modelo",),
    "Firmware": ("Firmware",),
    "IP": ("IP/Nome", "IP"),
    "MAC address": ("Endereço MAC", "MAC"),
}


def normalize_vendor(vendor: str) -> str:
    if vendor is None:
        return ""
    vendor = vendor.strip()
    if vendor.upper() == "HIKVISION":
        return "Hikvision"
    return vendor


def normalize_for_match(value: str) -> str:
    """Normalize text for case-insensitive, accent-insensitive matching."""
    decomposed = unicodedata.normalize("NFKD", value or "")
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return without_accents.casefold()


def main() -> int:
    parser = argparse.ArgumentParser(description="Converte XLSX em CSV normalizado.")
    parser.add_argument("--input", type=Path, default=Path(__file__).resolve().parent / "cameras.xlsx")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "cameras_normalized.csv")
    args = parser.parse_args()

    source = args.input
    dest = args.output

    if not source.exists():
        print(f"Erro: planilha nao encontrada: {source}", file=sys.stderr)
        return 1

    print(f"Lendo: {source}")
    wb = openpyxl.load_workbook(source, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        print("Erro: planilha vazia.", file=sys.stderr)
        return 1

    raw_header = [str(c).strip() if c else "" for c in rows[0] if c is not None]
    print(f"Colunas ({len(raw_header)}): {raw_header}")

    col_indices = {}
    for csv_col, source_columns in COLUMN_MAPPING.items():
        for source_column in source_columns:
            try:
                col_indices[csv_col] = raw_header.index(source_column)
                break
            except ValueError:
                continue
        else:
            # Firmware is optional in the newer format and is intentionally
            # emitted as an empty value when absent.
            if csv_col != "Firmware":
                print(
                    f"Aviso: coluna(s) '{', '.join(source_columns)}' nao encontrada(s).",
                    file=sys.stderr,
                )

    target_fields = list(COLUMN_MAPPING)
    data_rows = rows[1:]
    converted = []
    skipped = 0
    skipped_exchange = 0

    for row in data_rows:
        values = [str(c) if c is not None else "" for c in row]
        csv_row = {}
        for csv_col, idx in col_indices.items():
            csv_row[csv_col] = values[idx].strip() if idx < len(values) else ""

        if not csv_row.get("Name"):
            skipped += 1
            continue

        if "troca realizada" in normalize_for_match(csv_row["Name"]):
            skipped += 1
            skipped_exchange += 1
            continue

        csv_row["Vendor"] = normalize_vendor(csv_row["Vendor"])
        converted.append(csv_row)

    with dest.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=target_fields)
        writer.writeheader()
        writer.writerows(converted)

    print(
        f"OK: {len(converted)} registros (ignorados: {skipped}; "
        f"troca realizada: {skipped_exchange}) -> {dest}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
