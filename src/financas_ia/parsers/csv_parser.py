"""Importação tolerante de CSVs brasileiros e internacionais."""

import csv
import io
import re
import unicodedata

import pandas as pd


def load_csv(content: bytes) -> tuple[pd.DataFrame, str, str]:
    if not content:
        raise ValueError("O CSV está vazio.")

    decoded = None
    encoding_used = ""
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            decoded = content.decode(encoding)
            encoding_used = encoding
            break
        except UnicodeDecodeError:
            pass

    if decoded is None:
        raise ValueError("Não foi possível identificar a codificação do CSV.")

    decoded = decoded.lstrip("\ufeff")
    try:
        dialect = csv.Sniffer().sniff(decoded[:12000], delimiters=",;\t|")
        separator = dialect.delimiter
    except csv.Error:
        header = decoded.splitlines()[0] if decoded.splitlines() else ""
        separator = max((";", ",", "\t", "|"), key=header.count)
        if separator not in header:
            raise ValueError("O arquivo não parece conter colunas separadas.")

    try:
        df = pd.read_csv(
            io.StringIO(decoded),
            sep=separator,
            dtype=str,
            keep_default_na=False,
            on_bad_lines="error",
        )
    except (pd.errors.ParserError, ValueError) as exc:
        raise ValueError(f"CSV malformado: {exc}") from exc

    df.columns = [str(c).strip() for c in df.columns]
    if df.empty:
        raise ValueError("O CSV não contém lançamentos.")
    if len(df.columns) < 2:
        raise ValueError("O CSV precisa ter pelo menos duas colunas.")
    return df, encoding_used, separator


def _normal(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in s if not unicodedata.combining(c)).lower())


def suggest_columns(columns: list[str]) -> dict[str, str | None]:
    """Faz sugestões; o usuário sempre pode corrigir o mapeamento."""
    aliases = {
        "date": ("data", "datahora", "datalancamento", "datacompra", "date", "transactiondate"),
        "description": ("descricao", "descricaooriginal", "historico", "estabelecimento", "lancamento", "merchant", "description", "titulo", "title", "transactiontitle"),
        "amount": ("valor", "valorrs", "valortransacao", "amount", "quantia", "total"),
        "type": ("tipo", "natureza", "operacao", "debitocredito", "tipooperacao", "type"),
    }
    result = {}
    used: set[str] = set()
    for field, wanted in aliases.items():
        chosen = next((col for alias in wanted for col in columns if _normal(col) == alias and col not in used), None)
        if chosen is None:
            chosen = next((col for alias in wanted for col in columns if _normal(col).startswith(alias) and col not in used), None)
        result[field] = chosen
        if chosen:
            used.add(chosen)
    return result


def detect_expense_sign(df: pd.DataFrame) -> tuple[str, str | None]:
    """Sugere o sentido do valor sem alterar a escolha explícita do usuário.

    O cartão Nubank exporta CSV com date,title,amount: cobranças positivas
    e pagamentos/ajustes negativos. Este layout é tratado separadamente
    de extratos de conta, em que débitos frequentemente são negativos.

    Retorna (sinal, motivo), sendo motivo=None quando não há identificação
    segura do layout. Não identifica o banco por nome de arquivo.
    """
    normalized = {_normal(col) for col in df.columns}
    if {"date", "title", "amount"}.issubset(normalized):
        return (
            "positive",
            "Layout de fatura de cartão (date, title, amount): "
            "compras positivas e pagamentos/ajustes negativos. "
            "Confirme a convenção com a prévia.",
        )
    return "negative", None
