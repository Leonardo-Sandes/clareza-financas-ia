"""Regras determinísticas: não inventamos categorias quando faltam evidências."""

import re
import unicodedata

import pandas as pd

from financas_ia.constants import UNKNOWN


def normalize_text(value: str) -> str:
    s = unicodedata.normalize("NFKD", str(value)).lower()
    return "".join(c for c in s if not unicodedata.combining(c))


RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Alimentação", (r"\b(ifood|uber\s*eats|rappi|restaurante|lanchonete|pizzaria|hamburgueria|padaria|cafeteria|cafe\s+do|burger\s*king|mc\s*donalds|mcdonalds|subway|bar\s+(?:do|da|de)\s+\w+)\b",)),
    ("Assinaturas", (r"\b(netflix|spotify|disney\s*\+?|prime\s*video|amazon\s*prime|deezer|youtube\s*premium|hbo\s*max|max\s*streaming|crunchyroll|game\s*pass|icloud)\b",)),
    ("Entretenimento", (r"\b(cinema|ingresso|teatro|show|festival|boliche|parque\s+de\s+divers|steam|playstation\s*store|riot\s*games|sympla)\b",)),
    ("Transporte", (r"\b(uber\s*rides|uber(?!\s*eats)|99\s*(?:pop|taxi)|taxi|metro|metr[oô]|onibus|posto\s+(?:de\s+)?(?:gasolina|combustivel)|combustivel|gasolina|estacionamento|pedagio|bilhete\s+unico|shell|ipiranga)\b",)),
    ("Saúde", (r"\b(farmacia|drogaria|drogasil|droga\s*raia|consulta\s+medica|laboratorio|clinica|hospital|dentista|plano\s+de\s+saude)\b",)),
    ("Educação", (r"\b(faculdade|universidade|mensalidade\s+escolar|curso\s+online|udemy|alura|livraria|escola|colegio)\b",)),
    ("Moradia", (r"\b(aluguel|condominio|imobiliaria|iptu|reforma|material\s+de\s+construcao)\b",)),
    ("Contas e serviços", (r"\b(energia\s+eletrica|conta\s+de\s+luz|enel|light\s+sa|aguas\s+do\s+rio|conta\s+de\s+agua|internet\s+residencial|vivo\s+(?:fibra|internet)|claro\s+(?:internet|net)|tim\s+(?:celular|pos|p[oô]s)|telefone|gas\s+encanado)\b",)),
    ("Compras", (r"\b(mercado\s+livre|mercadolivre|amazon(?!\s*prime)(?:mktplc)?|shopee|shein|ali\s*express|magalu|magazine\s+luiza|renner|riachuelo|centauro|loja\s+de\s+roupas)\b",)),
    ("Mercado", (r"\b(supermercado|hipermercado|mercearia|hortifruti|sacolao|atacadao|assai|carrefour|pao\s+de\s+acucar|guanabara|mundial|mercado\s+(?:do|da|de|bairro))\b",)),
    ("Transferências", (r"\b(pix\s+(?:enviado|transferencia)|ted\s+enviada|transferencia\s+(?:realizada|enviada))\b",)),
)


def classify_description(description: str) -> tuple[str, str]:
    clean = normalize_text(description)
    for category, patterns in RULES:
        if any(re.search(pattern, clean) for pattern in patterns):
            return category, "Regra"
    return UNKNOWN, "Desconhecido"


def classify_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    if result.empty:
        result["categoria"] = pd.Series(dtype=str)
        result["origem"] = pd.Series(dtype=str)
        return result
    labels = result["descricao"].map(classify_description)
    result["categoria"] = labels.map(lambda item: item[0])
    result["origem"] = labels.map(lambda item: item[1])
    return result
