#!/usr/bin/env python3
"""Gera faturas fictícias e valida seus valores e casos de teste."""

import argparse
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"
WORKFLOW = ROOT / "n8n" / "Finance_ETL_Core.json"
RULES_SQL = ROOT / "sql" / "002_regras.sql"
MONTHS = dict(zip(("JAN", "FEV", "MAR", "ABR", "MAI", "JUN",
                   "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"), range(1, 13)))

# Os valores são centavos inteiros; pagamentos não entram no total da fatura.
INVOICES = [
    ("fatura_01.pdf", "15 JAN 2026", [
        ("03 JAN", "SUPERMARKET EXEMPLO", 10000),
        ("03 JAN", "SUPERMARKET EXEMPLO", 10000),
        ("05 JAN", "GAS STATION EXEMPLO", 5000),
        ("07 JAN", "LOJA XYZ 123 EXEMPLO", 2500),
        ("08 JAN", "SUPERMARKET EXEMPLO", -1000),
    ], ("14 JAN", "Pagamento anterior", -9000), 26500),
    ("fatura_02.pdf", "15 FEV 2026", [
        ("02 FEV", "STREAMING EXEMPLO", 2000),
        ("04 FEV", "PHARMACY EXEMPLO", 3500),
        ("06 FEV", "SERVICO ABC EXEMPLO", 4500),
    ], None, 10000),
    ("fatura_03.pdf", "15 MAR 2026", [
        ("01 MAR", "RESTAURANT EXEMPLO", 4000),
        ("04 MAR", "RIDE APP EXEMPLO", 3000),
        ("08 MAR", "LOJA XYZ 456 EXEMPLO", 6000),
    ], None, 13000),
]


def bank_keyword():
    workflows = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    matches = []
    for workflow in workflows:
        for node in workflow["nodes"]:
            code = node.get("parameters", {}).get("jsCode", "")
            matches.extend(re.findall(r"const BANK_KEYWORD = '([^']+)';", code))
    if len(matches) != 1:
        raise ValueError("A constante do banco no ETL não foi encontrada de forma única.")
    return matches[0].lower()


def validate_invoices():
    rules_sql = RULES_SQL.read_text(encoding="utf-8")
    patterns = re.findall(r"\(\s*'([^']+)'\s*,\s*'[^']+'\s*\)", rules_sql)
    if len(patterns) != 6:
        raise ValueError("Eram esperadas seis regras sintéticas de categorização.")

    covered_rules = set()
    has_duplicate = False
    has_refund = False
    has_payment = False
    has_unmatched = False

    for name, due_text, transactions, payment, expected_total in INVOICES:
        due_match = re.fullmatch(r"(\d{2}) ([A-ZÇ]{3}) (2026)", due_text)
        if not due_match:
            raise ValueError(f"{name}: vencimento fora do ano de 2026 ou formato inesperado.")
        due_date = date(int(due_match[3]), MONTHS[due_match[2]], int(due_match[1]))
        total = sum(value for _, _, value in transactions)
        if total != expected_total:
            raise ValueError(f"{name}: a soma das transações não confere com o total da fatura.")

        duplicates = Counter(transactions)
        has_duplicate |= any(count > 1 for count in duplicates.values())
        has_refund |= any(value < 0 for _, _, value in transactions)
        for date_text, description, _ in transactions:
            if not description.endswith("EXEMPLO"):
                raise ValueError(f"{name}: descrição sintética sem o sufixo EXEMPLO.")
            day, month_name = date_text.split()
            month = MONTHS[month_name]
            transaction_year = due_date.year - (month > due_date.month)
            if date(transaction_year, month, int(day)) > due_date:
                raise ValueError(f"{name}: transação posterior ao vencimento.")
            matches = [pattern for pattern in patterns
                       if pattern.casefold() in description.casefold()]
            covered_rules.update(matches)
            has_unmatched |= not matches
        if payment:
            has_payment |= payment[1].casefold().startswith("pagamento") and payment[2] < 0

    if covered_rules != set(patterns):
        raise ValueError("As amostras não exercitam todas as regras de categorização.")
    if not all((has_duplicate, has_refund, has_payment, has_unmatched)):
        raise ValueError("Falta cobertura de duplicata, estorno, pagamento ou descrição sem regra.")


def amount(cents):
    sign = "− " if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}R$ {cents // 100},{cents % 100:02d}"


def invoice_lines(due, transactions, payment, expected_total):
    total = sum(value for _, _, value in transactions)
    if total != expected_total:
        raise ValueError("A soma das transações não confere com o total esperado.")
    lines = [bank_keyword().upper(), f"Data de vencimento: {due}",
             f"Total a pagar {amount(total)}", "TRANSAÇÕES"]
    previous_date = None
    entries = [*transactions, *([payment] if payment else [])]
    for transaction_date, description, value in entries:
        if transaction_date != previous_date:
            lines.append(transaction_date)
            previous_date = transaction_date
        lines.append(f"{description} {amount(value)}")
    lines.extend(("Outros lançamentos", "Pagamentos"))
    return lines


def pdf_bytes(lines):
    # O código WinAnsi 150 representa o sinal de menos e usa um mapa Unicode.
    def encode(text):
        return text.replace("−", "\u2013").encode("cp1252")

    encoded = [encode(line) for line in lines]
    codes = sorted(set(b"".join(encoded)))
    mappings = []
    for code in codes:
        char = "−" if code == 150 else bytes([code]).decode("cp1252")
        mappings.append(f"<{code:02X}> <{ord(char):04X}>")
    cmap = (
        "/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
        "/CMapName /SyntheticUnicode def\n/CMapType 2 def\n"
        "1 begincodespacerange\n<00> <FF>\nendcodespacerange\n"
        f"{len(mappings)} beginbfchar\n" + "\n".join(mappings) +
        "\nendbfchar\nendcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n"
    ).encode("ascii")

    def escape(data):
        return data.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")

    content = b"BT\n/F1 12 Tf\n40 800 Td\n16 TL\n"
    for line in encoded:
        content += b"(" + escape(line) + b") Tj\nT*\n"
    content += b"ET\n"

    def stream(data):
        return b"<< /Length " + str(len(data)).encode() + b" >>\nstream\n" + data + b"endstream"

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding << /Type /Encoding /BaseEncoding /WinAnsiEncoding "
        b"/Differences [150 /minus] >> /ToUnicode 6 0 R >>",
        stream(content),
        stream(cmap),
    ]
    result = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offsets = []
    for number, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result += f"{number} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_offset = len(result)
    result += f"xref\n0 {len(objects) + 1}\n".encode()
    result += b"0000000000 65535 f \n"
    result += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    result += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
               f"startxref\n{xref_offset}\n%%EOF\n").encode()
    return result


def main():
    parser = argparse.ArgumentParser(description="Gera faturas sintéticas para testes.")
    parser.add_argument("--force", action="store_true",
                        help="Substitui arquivos de amostra já existentes.")
    args = parser.parse_args()

    validate_invoices()
    SAMPLES.mkdir(exist_ok=True)
    required_phrases = ("Data de vencimento", "Total a pagar", "TRANSAÇÕES",
                        "Outros lançamentos", "Pagamentos")
    for name, due, transactions, payment, expected_total in INVOICES:
        lines = invoice_lines(due, transactions, payment, expected_total)
        if not all(any(phrase in line for line in lines) for phrase in required_phrases):
            raise ValueError(f"{name}: falta uma frase exigida pelo layout.")
        target = SAMPLES / name
        data = pdf_bytes(lines)
        if target.exists() and target.read_bytes() != data and not args.force:
            raise FileExistsError(
                f"Recusando substituir uma amostra alterada sem a opção --force: {name}"
            )
        if not target.exists() or target.read_bytes() != data:
            target.write_bytes(data)
    print(f"{len(INVOICES)} faturas sintéticas geradas ou conferidas; valores e casos validados.")


if __name__ == "__main__":
    main()
