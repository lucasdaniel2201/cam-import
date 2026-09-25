"""
Executa a importacao em lotes sequenciais, chamando zabbix_web_batch_import.py
para cada lote.

Sem argumentos adicionais, usa os defaults do importador web. E obrigatorio
informar ao menos um grupo de host destino. Ex., com um layout personalizado:

  python run_batches.py --group-id 1 --host-prefix "CAM - "

Uso: python run_batches.py [--csv CSV] [--url URL] [--offset INICIO]
                           [--lot-size N] [opcoes de layout do importador]
"""

import argparse
import csv
import getpass
import math
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
IMPORT_SCRIPT = SCRIPT_DIR / "zabbix_web_batch_import.py"
CSV = SCRIPT_DIR / "cameras_normalized.csv"
REPORT_DIR = SCRIPT_DIR / "reports"
DEFAULT_URL = "http://localhost/zabbix"
DEFAULT_LOT_SIZE = 25


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Importa o CSV em lotes chamando zabbix_web_batch_import.py. "
            "Sem opcoes de layout, usa os defaults do importador."
        )
    )
    parser.add_argument("--csv", type=Path, default=CSV, help="CSV de origem.")
    parser.add_argument("--url", default=DEFAULT_URL, help="URL base do Zabbix.")
    parser.add_argument("--offset", type=int, default=0, help="Registro inicial do CSV.")
    parser.add_argument(
        "--lot-size",
        type=int,
        default=DEFAULT_LOT_SIZE,
        help="Quantidade de registros por lote.",
    )
    # Opcoes de layout: repassadas ao importador somente quando informadas.
    parser.add_argument(
        "--group-id",
        action="append",
        help="ID do host group destino. Pode ser informado mais de uma vez.",
    )
    parser.add_argument(
        "--template-id",
        action="append",
        help="ID do template a vincular. Pode ser informado mais de uma vez.",
    )
    parser.add_argument("--proxy-id", help="ID do proxy destino.")
    parser.add_argument("--proxy-name", help="Nome do proxy (usado no relatorio).")
    parser.add_argument("--port", help="Porta da interface agent.")
    parser.add_argument("--host-prefix", help="Prefixo do host tecnico.")
    parser.add_argument("--visible-name-prefix", help="Prefixo do nome visivel.")
    parser.add_argument("--host-suffix", help="Sufixo do host tecnico.")
    parser.add_argument("--visible-name-suffix", help="Sufixo do nome visivel.")
    return parser.parse_args()


def count_csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return sum(1 for row in reader if row.get("Name", "").strip())


def build_base_args(args: argparse.Namespace, username: str, password: str) -> list[str]:
    cmd = [
        sys.executable,
        str(IMPORT_SCRIPT),
        "--csv", str(args.csv),
        "--url", args.url,
        "--username", username,
        "--password", password,
        "--report-dir", str(REPORT_DIR),
    ]

    single_value_flags = [
        "--proxy-id", args.proxy_id,
        "--proxy-name", args.proxy_name,
        "--port", args.port,
        "--host-prefix", args.host_prefix,
        "--visible-name-prefix", args.visible_name_prefix,
        "--host-suffix", args.host_suffix,
        "--visible-name-suffix", args.visible_name_suffix,
    ]
    for flag, value in zip(single_value_flags[::2], single_value_flags[1::2], strict=True):
        if value:
            cmd += [flag, value]

    for flag, values in [("--group-id", args.group_id), ("--template-id", args.template_id)]:
        for value in values or []:
            cmd += [flag, value]

    return cmd


def ask_credentials() -> tuple[str, str]:
    """Pede usuario e senha no terminal (a senha nao aparece na tela)."""
    print("Credenciais do Zabbix (nao ficam salvas em disco):")
    username = input("  Usuario: ").strip()
    password = getpass.getpass("  Senha: ")
    return username, password


def main() -> int:
    args = parse_args()

    username, password = ask_credentials()
    if not username or not password:
        print("Erro: usuario e senha sao obrigatorios.", file=sys.stderr)
        return 2

    total = count_csv_rows(args.csv)

    if args.offset >= total:
        print(f"Nenhum registro a importar a partir do offset {args.offset} (total: {total}).")
        return 0

    total_lotes = math.ceil((total - args.offset) / args.lot_size)

    print("=" * 52)
    print("  IMPORTACAO EM LOTES - ZABBIX")
    print("=" * 52)
    print(f"  Total cameras : {total}")
    print(f"  Offset inicial: {args.offset}")
    print(f"  Tamanho lote  : {args.lot_size}")
    print(f"  Total lotes   : {total_lotes}")
    print(f"  CSV           : {args.csv.name}")
    print("=" * 52)
    print()

    base_args = build_base_args(args, username, password)
    lotes_erros = []

    for i in range(total_lotes):
        offset = args.offset + i * args.lot_size
        lote_num = i + 1

        print(f"\n{'=' * 50}")
        print(f"  LOTE {lote_num} / {total_lotes}  (offset={offset}, limit={args.lot_size})")
        print(f"{'=' * 50}")

        cmd = base_args + ["--offset", str(offset), "--limit", str(args.lot_size)]
        result = subprocess.run(cmd, capture_output=False, text=True)

        if result.returncode != 0:
            print(f"\n  *** ATENCAO: Lote {lote_num} terminou com codigo {result.returncode} ***")
            lotes_erros.append(lote_num)
            print("  Continuando para o proximo lote automaticamente...")
            # Detalhes dos erros ficam no relatorio JSON do lote em reports/
        else:
            print(f"  Lote {lote_num} concluido com sucesso.")

    print(f"\n{'=' * 50}")
    print("  IMPORTACAO FINALIZADA")
    print(f"{'=' * 50}")
    print(f"  Lotes processados: {total_lotes}")
    print(f"  Lotes com erro   : {len(lotes_erros)} (lotes: {lotes_erros})")
    print(f"  Relatorios       : {REPORT_DIR}")

    return 1 if lotes_erros else 0


if __name__ == "__main__":
    sys.exit(main())
