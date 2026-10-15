"""Regressão do problema de importação do CSV da fatura do cartão Nubank."""

from financas_ia.analytics.summary import by_category, by_month, kpis
from financas_ia.classification.rules import classify_dataframe
from financas_ia.parsers.csv_parser import detect_expense_sign, load_csv, suggest_columns
from financas_ia.processing import ColumnMapping, prepare_transactions


def test_nubank_card_csv_maps_columns_detects_sign_and_builds_dashboard_data():
    # Dados de teste INVENTADOS. Não armazenar extratos pessoais nos testes.
    content = (
        'date,title,amount\n'
        '2026-10-14,Dl*Uberrides,"23,94"\n'
        '2026-10-13,Mc Donalds,"36,00"\n'
        '2026-10-05,Pagamento recebido,"- 10,50"\n'
        '2026-10-05,Pagamento recebido,"- 520,00"\n'
        '2026-10-04,Parcelamento de Fatura - 1/3,"25,93"\n'
        '2026-10-03,Apple.Com/Bill,"17,90"\n'
    ).encode('utf-8')
    raw, _, sep = load_csv(content)
    assert sep == ','
    guessed = suggest_columns(list(raw.columns))
    assert guessed == {'date': 'date', 'description': 'title', 'amount': 'amount', 'type': None}
    sign, reason = detect_expense_sign(raw)
    assert sign == 'positive'
    assert reason is not None

    tx, report = prepare_transactions(
        raw,
        ColumnMapping(guessed['date'], guessed['description'], guessed['amount'], guessed['type']),
        sign,
    )
    assert report == {'invalid': 0, 'income': 2, 'expenses': 4, 'total': 6}
    assert sum(tx['valor_centavos']) == (2394 + 3600 + 2593 + 1790)

    categorized = classify_dataframe(tx)
    assert categorized.loc[categorized['descricao'] == 'Dl*Uberrides', 'categoria'].item() == 'Transporte'
    assert categorized.loc[categorized['descricao'] == 'Mc Donalds', 'categoria'].item() == 'Alimentação'
    assert categorized.loc[categorized['descricao'] == 'Apple.Com/Bill', 'categoria'].item() == 'Desconhecido'
    assert kpis(categorized)['count'] == 4
    assert len(by_category(categorized)) > 0
    assert len(by_month(categorized)) == 1


def test_unrecognized_generic_csv_keeps_negative_expense_convention():
    raw, _, _ = load_csv('Data;Descrição;Valor\n10/10/2026;Teste;-45,00\n'.encode())
    assert detect_expense_sign(raw) == ('negative', None)
