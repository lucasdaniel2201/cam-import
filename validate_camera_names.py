import argparse
import csv
import sys
import tempfile
import unicodedata
from collections import defaultdict
from pathlib import Path


def repair_mojibake(text: str) -> str:
    try:
        return text.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def normalize_name(name: str) -> str:
    repaired = repair_mojibake(name)
    repaired = repaired.replace("/", "-")
    repaired = repaired.replace('"', "")   # remove aspas duplas (Zabbix rejeita)
    repaired = repaired.replace("(", "-")  # remove parenteses (Zabbix rejeita)
    repaired = repaired.replace(")", "")   # fecha parenteses
    normalized = unicodedata.normalize("NFKD", repaired)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_only.strip()


def process_csv(csv_path: Path, output_path: Path | None) -> int:
    duplicates = defaultdict(list)
    seen_names = {}
    normalized_rows = []
    changed_names = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = reader.fieldnames or []

        if "Name" not in fieldnames:
            print("Erro: a coluna 'Name' nao foi encontrada no CSV.", file=sys.stderr)
            return 2

        for line_number, row in enumerate(reader, start=2):
            original_name = (row.get("Name") or "").strip()
            normalized_name = normalize_name(original_name)
            row["Name"] = normalized_name
            normalized_rows.append(row)

            if original_name != normalized_name:
                changed_names.append((line_number, original_name, normalized_name))

            if not normalized_name:
                print(f"Aviso: linha {line_number} com campo 'Name' vazio.", file=sys.stderr)
                continue

            if normalized_name in seen_names:
                duplicates[normalized_name].append(line_number)
            else:
                seen_names[normalized_name] = line_number

    if output_path is not None:
        destination = output_path
        temp_path = None

        if output_path.resolve() == csv_path.resolve():
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                newline="",
                delete=False,
                dir=str(output_path.parent),
                suffix=".csv",
            ) as temp_file:
                temp_path = Path(temp_file.name)
                writer = csv.DictWriter(temp_file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(normalized_rows)

            temp_path.replace(output_path)
        else:
            with output_path.open("w", encoding="utf-8", newline="") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(normalized_rows)

        print(f"CSV normalizado salvo em: {destination}")

    if changed_names:
        print("Nomes normalizados:")
        for line_number, original_name, normalized_name in changed_names:
            print(f"- linha {line_number}: {original_name} -> {normalized_name}")
    else:
        print("Nenhum nome precisou de normalizacao.")

    if duplicates:
        print("Foram encontrados nomes duplicados apos a normalizacao:")
        for name, duplicate_lines in sorted(duplicates.items()):
            all_lines = [seen_names[name], *duplicate_lines]
            formatted_lines = ", ".join(str(line) for line in all_lines)
            print(f"- {name}: linhas {formatted_lines}")
        return 1

    print("Nenhum nome duplicado foi encontrado na coluna 'Name' apos a normalizacao.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normaliza a coluna 'Name' para ASCII e valida se os nomes resultantes sao unicos."
    )
    parser.add_argument("csv_path", type=Path, help="Caminho do arquivo CSV.")
    parser.add_argument(
        "--output",
        type=Path,
        help="Caminho para salvar um novo CSV com a coluna 'Name' normalizada.",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Sobrescreve o proprio arquivo CSV com os nomes normalizados.",
    )
    args = parser.parse_args()

    if not args.csv_path.exists():
        print(f"Erro: arquivo nao encontrado: {args.csv_path}", file=sys.stderr)
        return 2

    output_path = args.csv_path if args.in_place else args.output

    if args.in_place and args.output is not None:
        print("Erro: use apenas um entre --output e --in-place.", file=sys.stderr)
        return 2

    return process_csv(args.csv_path, output_path)


if __name__ == "__main__":
    raise SystemExit(main())
