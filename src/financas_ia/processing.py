"""Normalização de dados, conversão exata em centavos e separação de créditos."""

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import pandas as pd


@dataclass(frozen=True)
class ColumnMapping:
    date: str
    description: str
    amount: str
    transaction_type: str | None = None


def parse_cents(value: object) -> int | None:
    if value is None:
        return None
    s = str(value).strip().replace("\u00a0", "").replace(" ", "")
    if not s:
        return None
    s = re.sub(r"(?i)R\$", "", s)
    negative = s.startswith("-") or (s.startswith("(") and s.endswith(")"))
    s = re.sub(r"[()DCdc]", "", s).lstrip("+-")
    if not re.fullmatch(r"[\d.,]+", s):
        return None
    if "," in s and "." in s:
        decimal_sep = "," if s.rfind(",") > s.rfind(".") else "."
    elif "," in s:
        decimal_sep = "," if len(s.split(",")[-1]) in (1, 2) else None
    elif "." in s:
        decimal_sep = "." if len(s.split(".")[-1]) in (1, 2) else None
    else:
        decimal_sep = None
    if decimal_sep == ",":
        s = s.replace(".", "").replace(",", ".")
    elif decimal_sep == ".":
        s = s.replace(",", "")
    else:
        s = s.replace(",", "").replace(".", "")
    try:
        cents = int((Decimal(s) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except InvalidOperation:
        return None
    return -cents if negative else cents


def _date(value: object) -> date | None:
    if pd.isna(value):
        return None
    s = str(value).strip()
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y", "%d-%m-%y", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def _type(value: object) -> str | None:
    normalized = str(value).strip().lower()
    if normalized in {"d", "debito", "débito", "debit", "despesa", "saida", "saída", "compra", "pagamento", "pix enviado"}:
        return "expense"
    if normalized in {"c", "credito", "crédito", "credit", "receita", "entrada", "deposito", "depósito", "estorno", "recebimento", "pix recebido"}:
        return "income"
    return None


def prepare_transactions(
    raw: pd.DataFrame,
    mapping: ColumnMapping,
    expense_sign: str = "negative",
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Retorna apenas saídas, mantendo repetições legítimas do extrato.

    expense_sign: 'negative' (saídas negativas) ou 'positive' (saídas positivas).
    A coluna tipo, quando reconhecida, tem prioridade sobre o sinal.
    """
    if expense_sign not in {"negative", "positive"}:
        raise ValueError("Convenção de sinal inválida.")
    required = [mapping.date, mapping.description, mapping.amount]
    if len(set(required)) != 3 or not all(col in raw.columns for col in required):
        raise ValueError("Selecione três colunas diferentes e existentes: data, descrição e valor.")
    if mapping.transaction_type and mapping.transaction_type not in raw.columns:
        raise ValueError("Coluna tipo inexistente.")

    rows = []
    invalid = 0
    income = 0
    for idx, row in raw.iterrows():
        dt = _date(row[mapping.date])
        description = str(row[mapping.description]).strip()
        cents = parse_cents(row[mapping.amount])
        if dt is None or not description or cents is None or cents == 0:
            invalid += 1
            continue

        operation = _type(row[mapping.transaction_type]) if mapping.transaction_type else None
        if operation is None:
            operation = "expense" if (cents < 0 if expense_sign == "negative" else cents > 0) else "income"
        if operation == "income":
            income += 1
            continue

        rows.append({
            "id": str(idx),
            "data": dt,
            "descricao": description,
            "valor_centavos": abs(cents),
            "valor": abs(cents) / 100,
        })

    df = pd.DataFrame(rows, columns=["id", "data", "descricao", "valor_centavos", "valor"])
    return df, {"invalid": invalid, "income": income, "expenses": len(df), "total": len(raw)}
