import pandas as pd

from financas_ia.processing import ColumnMapping, parse_cents, prepare_transactions


def test_parse_cents_pt_br_and_us():
    assert parse_cents("R$ -1.234,56") == -123456
    assert parse_cents("1,234.56") == 123456
    assert parse_cents("(99,99)") == -9999
    assert parse_cents("1.234") == 123400
    assert parse_cents("0,01") == 1
    assert parse_cents("abc") is None


def test_expenses_and_income_with_type():
    raw = pd.DataFrame({
        "Data": ["01/10/2026", "02/10/2026", "03/10/2026", "invalid"],
        "Descrição": ["IFOOD", "SALARIO", "PAGAMENTO", "RUIM"],
        "Valor": ["-56,90", "2.000,00", "30,00", "5,00"],
        "Tipo": ["D", "C", "D", "D"],
    })
    df, report = prepare_transactions(raw, ColumnMapping("Data", "Descrição", "Valor", "Tipo"))
    assert df["valor_centavos"].tolist() == [5690, 3000]
    assert report == {"invalid": 1, "income": 1, "expenses": 2, "total": 4}


def test_positive_expense_mode_without_type():
    raw = pd.DataFrame({"Data": ["01/10/2026", "02/10/2026"],
                        "Descrição": ["Almoço", "Salário"], "Valor": ["20,00", "-50,00"]})
    df, _ = prepare_transactions(raw, ColumnMapping("Data", "Descrição", "Valor"), "positive")
    assert len(df) == 1
    assert df.iloc[0]["valor_centavos"] == 2000


def test_duplicate_transactions_are_not_discarded():
    raw = pd.DataFrame({"Data": ["01/10/2026", "01/10/2026"],
                        "Descrição": ["Uber", "Uber"], "Valor": ["-10,00", "-10,00"]})
    df, _ = prepare_transactions(raw, ColumnMapping("Data", "Descrição", "Valor"))
    assert len(df) == 2
