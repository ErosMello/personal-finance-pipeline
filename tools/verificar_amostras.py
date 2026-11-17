#!/usr/bin/env python3
"""Extrai e confere as faturas sintéticas de forma independente do ETL."""

import re
import shutil
import subprocess
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path

from gerar_amostras import ROOT, bank_keyword

EXPECTED = {
    "fatura_01.pdf": (5, 1, 1, 1, 1),
    "fatura_02.pdf": (3, 0, 0, 0, 1),
    "fatura_03.pdf": (3, 0, 0, 0, 1),
}
MONTHS = dict(zip(("JAN", "FEV", "MAR", "ABR", "MAI", "JUN",
                   "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"), range(1, 13)))
VALUE = re.compile(r"([−\-])?\s*R\$\s*([\d\.,]+)")


def extract(path):
    extractor = shutil.which("pdftotext")
    if extractor:
        result = subprocess.run([extractor, "-enc", "UTF-8", "-layout", str(path), "-"],
                                check=True, capture_output=True)
        return result.stdout.decode("utf-8")
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Instale pdftotext ou pypdf para extrair o texto do PDF.") from exc
    reader = PdfReader(str(path))
    if len(reader.pages) != 1:
        raise ValueError(f"{path.name}: era esperada uma página.")
    return reader.pages[0].extract_text()


def cents(text):
    return int(Decimal(text.replace(".", "").replace(",", ".")) * 100)


def parse(text):
    due = re.search(r"Data de vencimento:\s*(\d{2})\s([A-ZÇ]{3})\s(\d{4})", text)
    total = re.search(r"Total a pagar R\$\s*([\d\.,]+)", text)
    if not due or not total or bank_keyword() not in text.lower():
        raise ValueError("Falta a palavra-chave do banco, o vencimento ou o total.")
    due_date = date(int(due[3]), MONTHS[due[2]], int(due[1]))
    total_cents = cents(total[1])
    extra = re.search(r"Outros lançamentos\s*([−\-])?\s*R\$\s*([\d\.,]+)", text)
    transactions = []
    ignored_payments = 0
    active = False
    terminated = False
    current_date = None
    last_description = None

    for line in (line.strip() for line in text.splitlines()):
        if not line:
            continue
        if line.startswith("TRANSAÇÕES"):
            active = True
            continue
        if not active:
            continue
        if line.startswith("Pagamentos"):
            terminated = True
            break
        day = re.match(r"^(\d{2})\s([A-ZÇ]{3})$", line)
        if day:
            month = MONTHS[day[2]]
            year = due_date.year - (month > due_date.month)
            current_date = date(year, month, int(day[1]))
            continue
        if line.startswith(("Conversão:", "USD")):
            continue
        value = VALUE.search(line)
        if value and current_date:
            amount = cents(value[2]) * (-1 if value[1] else 1)
            description = VALUE.sub("", line, count=1).strip() or last_description or "Transação"
            if amount < 0 and re.match(r"^pagamento", description, re.I):
                ignored_payments += 1
                continue
            transactions.append((current_date, description, amount))
            continue
        if "R$" not in line and not line.startswith("IOF"):
            last_description = line

    subtotal = sum(item[2] for item in transactions)
    if extra:
        extra_cents = cents(extra[2]) * (-1 if extra[1] else 1)
        if abs(total_cents - subtotal - extra_cents) <= 1:
            transactions.append((due_date, "Outros lançamentos (juros/encargos)", extra_cents))
    if not active or not terminated or sum(item[2] for item in transactions) != total_cents:
        raise ValueError("Falta uma seção ou seu terminador, ou o total não confere.")
    return transactions, ignored_payments, due_date


def main():
    sql = (ROOT / "sql" / "002_regras.sql").read_text(encoding="utf-8")
    patterns = re.findall(r"\(\s*'([^']+)'\s*,\s*'[^']+'\s*\)", sql)
    if len(patterns) != 6:
        raise ValueError("Eram esperadas seis regras sintéticas de categorização.")
    matched_patterns = set()
    for month, (name, expected) in enumerate(EXPECTED.items(), start=1):
        text = extract(ROOT / "samples" / name)
        transactions, payments, due = parse(text)
        duplicates = sum(count - 1 for count in Counter(transactions).values() if count > 1)
        refunds = sum(amount < 0 for _, _, amount in transactions)
        if due != date(2026, month, 15) or text.count("−") != refunds + payments:
            raise ValueError(f"{name}: vencimento ou contagem de sinais de menos inesperados.")
        unmatched = 0
        for _, description, _ in transactions:
            matches = [pattern for pattern in patterns if pattern.casefold() in description.casefold()]
            matched_patterns.update(matches)
            unmatched += not matches
        actual = (len(transactions), payments, duplicates, refunds, unmatched)
        if actual != expected:
            raise ValueError(f"{name}: quantidade inesperada de transações ou casos de teste.")
        print(f"{name}: transações={actual[0]}, pagamentos_ignorados={actual[1]}, "
              f"duplicatas={actual[2]}, estornos={actual[3]}, sem_regra={actual[4]}, total=OK")
    if len(matched_patterns) != len(patterns):
        raise ValueError("As amostras não exercitam todas as regras sintéticas.")
    print(f"Cobertura de regras: {len(matched_patterns)}/{len(patterns)}")


if __name__ == "__main__":
    main()
