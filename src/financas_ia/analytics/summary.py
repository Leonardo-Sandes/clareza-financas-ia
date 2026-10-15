"""Agregações testáveis separadas da interface Streamlit."""

import pandas as pd

from financas_ia.constants import UNKNOWN


def kpis(df: pd.DataFrame) -> dict[str, float | int]:
    if df.empty:
        return {"total_centavos": 0, "count": 0, "avg_centavos": 0, "unknown_centavos": 0}
    total = int(df["valor_centavos"].sum())
    count = len(df)
    return {
        "total_centavos": total,
        "count": count,
        "avg_centavos": round(total / count),
        "unknown_centavos": int(df.loc[df["categoria"] == UNKNOWN, "valor_centavos"].sum()),
    }


def by_category(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["categoria", "total_centavos", "valor", "participacao"])
    agg = df.groupby("categoria", as_index=False)["valor_centavos"].sum().sort_values("valor_centavos", ascending=False)
    total = int(agg["valor_centavos"].sum())
    agg["valor"] = agg["valor_centavos"] / 100
    agg["participacao"] = 100 * agg["valor_centavos"] / total if total else 0.0
    return agg


def by_month(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["mes", "valor_centavos", "valor"])
    work = df.copy()
    work["mes"] = pd.to_datetime(work["data"]).dt.to_period("M").astype(str)
    agg = work.groupby("mes", as_index=False)["valor_centavos"].sum().sort_values("mes")
    agg["valor"] = agg["valor_centavos"] / 100
    return agg


def brl_from_cents(value: int) -> str:
    amount = f"{value / 100:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {amount}"
