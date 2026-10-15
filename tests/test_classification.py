from financas_ia.classification.llm import sanitize_description
from financas_ia.classification.rules import classify_description
from financas_ia.constants import UNKNOWN


def test_rule_priority():
    assert classify_description("UBER EATS entrega")[0] == "Alimentação"
    assert classify_description("UBER TRIP")[0] == "Transporte"
    assert classify_description("MERCADO LIVRE BR")[0] == "Compras"
    assert classify_description("SUPERMERCADO GUANABARA")[0] == "Mercado"
    assert classify_description("AMAZON PRIME")[0] == "Assinaturas"


def test_unknown_not_forced_into_category():
    assert classify_description("COMPRA CARTAO XJ009181")[0] == UNKNOWN
    assert classify_description("PIX 12345")[0] == UNKNOWN


def test_sanitization():
    clean = sanitize_description("Email pessoa@dominio.com CPF 123.456.789-10 pago")
    assert "pessoa@dominio.com" not in clean
    assert "123.456.789-10" not in clean
