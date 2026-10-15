import io

import pandas as pd
from reportlab.pdfgen.canvas import Canvas

from financas_ia.analytics.summary import brl_from_cents, by_category, kpis
from financas_ia.classification.rules import classify_dataframe
from financas_ia.parsers.csv_parser import load_csv, suggest_columns
from financas_ia.parsers.pdf_parser import parse_pdf
from financas_ia.processing import ColumnMapping, prepare_transactions


def test_csv_semicolon_and_column_suggestions():
    content = "Data;Descrição;Valor;Tipo\n01/10/2026;IFOOD;-23,90;D\n".encode()
    frame, encoding, sep = load_csv(content)
    assert sep == ";" and len(frame) == 1
    guesses = suggest_columns(list(frame.columns))
    assert guesses == {"date": "Data", "description": "Descrição", "amount": "Valor", "type": "Tipo"}


def test_pdf_extraction_with_reportlab():
    buffer = io.BytesIO()
    pdf = Canvas(buffer)
    pdf.drawString(50, 750, "03/10/2026 RESTAURANTE DO CENTRO -45,90")
    pdf.drawString(50, 720, "04/10/2026 MERCADO BAIRRO 123,40 D")
    pdf.drawString(50, 690, "05/10/2026 RECEBIMENTO 900,00 C")
    pdf.drawString(50, 660, "06/10/2026 COMPRA 25,00 SALDO 100,00")
    pdf.save()
    rows, warnings = parse_pdf(buffer.getvalue(), 2026)
    assert len(rows) == 3
    assert any("1 linha" in warning for warning in warnings)
    tx, report = prepare_transactions(rows, ColumnMapping("Data", "Descrição", "Valor", "Tipo"))
    assert report["income"] == 1
    assert len(tx) == 2


def test_summary():
    data = pd.DataFrame({
        "id": ["0", "1"],
        "data": [pd.Timestamp("2026-10-01").date(), pd.Timestamp("2026-10-01").date()],
        "descricao": ["IFOOD", "NAO SEI"],
        "valor_centavos": [1500, 500], "valor": [15.0, 5.0],
    })
    categorized = classify_dataframe(data)
    assert kpis(categorized)["total_centavos"] == 2000
    assert kpis(categorized)["unknown_centavos"] == 500
    assert round(by_category(categorized)["participacao"].sum(), 5) == 100
    assert brl_from_cents(123456) == "R$ 1.234,56"
