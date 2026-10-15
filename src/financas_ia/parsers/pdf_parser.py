"""Extrator conservador de extratos PDF textuais.

Suporta linhas do tipo:
  03/10/2026 MERCADO BAIRRO -78,90
  04/10/2026 IFOOD 48,50 D
  05/10 MERCEARIA 120,00 C
Por segurança, ignora linhas com mais de um valor monetário identificável
(por exemplo, quando o PDF mostra valor e saldo na mesma linha).
"""

import io
import re

import pandas as pd
import pdfplumber

DATE = re.compile(r"^\s*(?P<date>\d{1,2}/\d{1,2}(?:/\d{2,4})?|\d{4}-\d{2}-\d{2})\s+", re.I)
MONEY = re.compile(r"(?<![\w/])(?:R\$\s*)?(?P<amount>\(?[+-]?(?:\d{1,3}(?:\.\d{3})+|\d+),\d{2}\)?)(?:\s*(?P<kind>[DC]))?(?!\w)", re.I)


def parse_pdf(content: bytes, year_if_missing: int) -> tuple[pd.DataFrame, list[str]]:
    if not content.startswith(b"%PDF"):
        raise ValueError("O arquivo não parece ser um PDF válido.")

    rows: list[dict[str, str]] = []
    text_pages = 0
    ambiguous = 0
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                if text.strip():
                    text_pages += 1
                for line in text.splitlines():
                    match_date = DATE.match(line)
                    if not match_date:
                        continue
                    rest = line[match_date.end():].strip()
                    matches = list(MONEY.finditer(rest))
                    if len(matches) > 1:
                        ambiguous += 1
                        continue
                    if len(matches) != 1:
                        continue
                    money = matches[0]
                    desc = (rest[:money.start()] + " " + rest[money.end():]).strip(" -|")
                    if not desc:
                        continue
                    raw_date = match_date.group("date")
                    if raw_date.count("/") == 1:
                        raw_date += f"/{year_if_missing}"
                    rows.append({
                        "Data": raw_date,
                        "Descrição": re.sub(r"\s+", " ", desc),
                        "Valor": money.group("amount"),
                        "Tipo": "D" if (money.group("kind") or "").upper() == "D" else
                                "C" if (money.group("kind") or "").upper() == "C" else "",
                    })
    except Exception as exc:
        raise ValueError(f"Não foi possível ler o PDF: {exc}") from exc

    warnings: list[str] = []
    if ambiguous:
        warnings.append(f"{ambiguous} linha(s) com mais de um valor monetário foram ignoradas para evitar confusão com saldo.")
    if not text_pages:
        warnings.append("O PDF não contém texto selecionável. PDFs escaneados exigem OCR, não incluído nesta versão.")
    if not rows:
        warnings.append("Nenhuma transação no formato reconhecido foi encontrada. Esse layout de PDF precisará de um adaptador específico.")

    return pd.DataFrame(rows, columns=["Data", "Descrição", "Valor", "Tipo"]), warnings
