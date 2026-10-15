"""Painel de gastos com importação CSV/PDF e classificação híbrida.

Execute na raiz do projeto: streamlit run app.py
"""

import hashlib
import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

from financas_ia.analytics.summary import brl_from_cents, by_category, by_month, kpis
from financas_ia.classification.llm import AIClassificationError, classify_unknown_with_ai
from financas_ia.classification.rules import classify_dataframe
from financas_ia.constants import CATEGORIES, CATEGORY_COLORS, UNKNOWN
from financas_ia.parsers.csv_parser import detect_expense_sign, load_csv, suggest_columns
from financas_ia.parsers.pdf_parser import parse_pdf
from financas_ia.processing import ColumnMapping, prepare_transactions

load_dotenv(ROOT / ".env")
st.set_page_config(page_title="Clareza | Seus gastos", page_icon="💳", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
  .block-container {max-width: 1260px; padding-top: 2.3rem; padding-bottom: 4rem;}
  h1,h2,h3 {letter-spacing: -.035em; color: #17352E;}
  h1 {font-weight: 720;}
  p, label {color: #41534B;}
  div[data-testid="stMetric"] {background: white; border: 1px solid #E4EAE5;
     border-radius: 16px; padding: 18px 20px; min-height: 132px;}
  div[data-testid="stMetricLabel"] {font-size: .87rem; color: #607169;}
  div[data-testid="stMetricValue"] {font-size: 1.55rem; font-weight: 700; color: #183C34;}
  div[data-testid="stFileUploader"] {border-radius: 18px;}
  div[data-testid="stAlert"] {border-radius: 12px;}
  section[data-testid="stSidebar"] {background-color: #F3F6F2; border-right: 1px solid #E4ECE7;}
  div[data-testid="stPlotlyChart"] {background-color: white; border: 1px solid #E5EBE6;
    border-radius: 16px; padding: 12px;}
  .eyebrow {font-size: .73rem; letter-spacing: .16em; color: #42756A; font-weight: 800;}
  .muted {color: #667970; font-size: .92rem;}
  .hero {padding-bottom: .7rem;}
</style>
""", unsafe_allow_html=True)


def plot_style(fig, height: int = 360):
    fig.update_layout(
        height=height, margin=dict(l=12, r=20, t=30, b=22),
        font=dict(family="Arial, sans-serif", size=12, color="#40564C"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(bgcolor="#FFFFFF"),
        legend_title_text="",
    )
    fig.update_xaxes(showgrid=True, gridcolor="#EEF1EF", zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)
    return fig


def select_col(label: str, cols: list[str], proposed: str | None, optional: bool = False) -> str | None:
    options = (["(nenhuma)"] if optional else []) + cols
    if not options:
        st.error("Não há colunas disponíveis.")
        st.stop()
    index = options.index(proposed) if proposed in options else 0
    selected = st.selectbox(label, options, index=index)
    return None if selected == "(nenhuma)" else selected


def signature(contents: bytes, settings: dict) -> str:
    h = hashlib.sha256(contents).hexdigest()
    extra = json.dumps(settings, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(f"{h}|{extra}".encode()).hexdigest()


def get_transactions(raw: pd.DataFrame, mapping: ColumnMapping, sign: str, key: str):
    if st.session_state.get("fingerprint") != key:
        tx, report = prepare_transactions(raw, mapping, sign)
        st.session_state["fingerprint"] = key
        st.session_state["transactions"] = classify_dataframe(tx)
        st.session_state["report"] = report
        st.session_state["ai_labels"] = {}
        st.session_state["ai_summary"] = None
        st.session_state["overrides"] = {}
        st.session_state["ai_summary"] = None
    return st.session_state["transactions"].copy(), st.session_state["report"]


def add_user_labels(df: pd.DataFrame) -> pd.DataFrame:
    labels = st.session_state.get("ai_labels", {})
    overrides = st.session_state.get("overrides", {})
    if df.empty:
        return df
    for idx in df.index:
        desc = df.at[idx, "descricao"]
        tx_id = df.at[idx, "id"]
        if df.at[idx, "categoria"] == UNKNOWN and labels.get(desc, UNKNOWN) != UNKNOWN:
            df.at[idx, "categoria"] = labels[desc]
            df.at[idx, "origem"] = "IA"
        if tx_id in overrides:
            df.at[idx, "categoria"] = overrides[tx_id]
            df.at[idx, "origem"] = "Revisão manual"
    return df


st.sidebar.markdown("### ◈ CLAREZA")
st.sidebar.caption("Dashboard pessoal de despesas")
st.sidebar.divider()
uploaded = st.sidebar.file_uploader(
    "Importe seu extrato", type=["csv", "pdf"],
    help="CSV ou PDF com texto selecionável, até 20 MB. Os dados não são salvos pelo aplicativo.",
)
st.sidebar.caption("Formatos aceitos: .csv e .pdf (até 20 MB)")

st.markdown('<div class="hero"><div class="eyebrow">FINANÇAS PESSOAIS · ANÁLISE INTELIGENTE</div></div>', unsafe_allow_html=True)
st.title("Entenda para onde vai seu dinheiro.")
st.markdown("Importe seu extrato, organize suas despesas e explore cada categoria em um painel interativo.")

if uploaded is None:
    st.info("Comece enviando um CSV ou PDF pela barra lateral. Para testar, utilize `examples/extrato_exemplo.csv` incluído no projeto.")
    st.markdown("#### O que você terá aqui")
    cols = st.columns(3)
    with cols[0]:
        st.markdown("**01 · Importação flexível**")
        st.caption("Mapeamento de colunas, datas e créditos para evitar distorções.")
    with cols[1]:
        st.markdown("**02 · Classificação responsável**")
        st.caption("Regras locais, IA opcional e categoria Desconhecido.")
    with cols[2]:
        st.markdown("**03 · Exploração e exportação**")
        st.caption("Filtros, gráficos, revisão manual e CSV tratado.")
    st.stop()

content = uploaded.getvalue()
if len(content) > 20 * 1024 * 1024:
    st.error("Arquivo acima de 20 MB. Exporte um período menor.")
    st.stop()

is_pdf = uploaded.name.lower().endswith(".pdf")
st.sidebar.markdown("#### Configuração de leitura")
try:
    if is_pdf:
        year = st.sidebar.number_input("Ano para datas sem ano (PDF)", min_value=1990, max_value=2100, value=date.today().year)
        import_key = hashlib.sha256(content + str(year).encode()).hexdigest()
        if st.session_state.get("import_key") != import_key:
            parsed = parse_pdf(content, year_if_missing=int(year))
            st.session_state["import_key"] = import_key
            st.session_state["import_result"] = parsed
        raw, parse_warnings = st.session_state["import_result"]
        mapping = ColumnMapping("Data", "Descrição", "Valor", "Tipo")
        st.sidebar.caption(f"PDF: {len(raw)} linhas reconhecidas.")
        for warning in parse_warnings:
            st.warning(warning)
        if raw.empty:
            st.stop()
    else:
        import_key = hashlib.sha256(content).hexdigest()
        if st.session_state.get("import_key") != import_key:
            parsed = load_csv(content)
            st.session_state["import_key"] = import_key
            st.session_state["import_result"] = parsed
        raw, encoding, separator = st.session_state["import_result"]
        suggested = suggest_columns(list(raw.columns))
        with st.sidebar.expander("Associar colunas do CSV", expanded=True):
            dt_col = select_col("Coluna da data", list(raw.columns), suggested["date"])
            desc_col = select_col("Coluna da descrição", list(raw.columns), suggested["description"])
            amount_col = select_col("Coluna do valor", list(raw.columns), suggested["amount"])
            kind_col = select_col("Crédito / débito (opcional)", list(raw.columns), suggested["type"], optional=True)
        mapping = ColumnMapping(dt_col, desc_col, amount_col, kind_col)
        st.sidebar.caption(f"CSV: {len(raw)} linhas · {encoding} · separador: {repr(separator)}")

    suggested_sign, profile_explanation = (
        ("negative", None) if is_pdf else detect_expense_sign(raw)
    )
    sign_label = st.sidebar.radio(
        "Como o extrato representa despesas sem tipo explícito?",
        ["Automático (recomendado)", "Negativo = gasto", "Positivo = gasto"],
        index=0,
        help=(
            "O modo automático reconhece o layout de fatura Nubank (date,title,amount), "
            "que usa compras positivas. Nos demais formatos, assume valores negativos; "
            "uma coluna Tipo explícita prevalece sobre o sinal."
        ),
    )
    sign = (suggested_sign if sign_label.startswith("Automático") else
            "negative" if sign_label.startswith("Negativo") else "positive")
    if profile_explanation and sign_label.startswith("Automático"):
        st.sidebar.success("Padrão de cartão reconhecido: positivo = gasto.")
    else:
        st.sidebar.caption(
            f"Convenção aplicada: {'positivo' if sign == 'positive' else 'negativo'} = gasto."
        )
    settings = {"mapping": vars(mapping), "sign": sign, "year": int(year) if is_pdf else None, "name": uploaded.name}
    tx, report = get_transactions(raw, mapping, sign, signature(content, settings))
except ValueError as exc:
    st.error(str(exc))
    st.stop()
except Exception as exc:
    st.error(f"Não foi possível importar o arquivo ({type(exc).__name__}). Verifique se o formato é suportado.")
    st.stop()

if not is_pdf and profile_explanation and sign_label.startswith("Automático"):
    st.success(
        "**Fatura de cartão reconhecida.** As colunas e o sentido dos valores foram "
        "configurados automaticamente: **compras positivas = despesas**; "
        "**pagamentos/ajustes negativos = créditos**."
    )

with st.expander("Prévia do extrato original", expanded=False):
    st.dataframe(raw.head(12), width="stretch", hide_index=True)
    st.caption("Confira se data, descrição, valor e tipo foram interpretados corretamente antes de analisar.")

if report["invalid"]:
    st.warning(
        f"{report['invalid']} lançamento(s) ignorado(s) por data, descrição ou valor inválido/zerado. "
        "Confira se as colunas Data, Descrição e Valor estão associadas corretamente "
        "na barra lateral."
    )
if report["income"]:
    st.caption(f"{report['income']} entrada(s) ou crédito(s) foram excluídos do cálculo de despesas.")
if tx.empty:
    st.warning(
        "Nenhuma despesa identificada. Verifique o mapeamento das colunas e o sentido "
        "dos valores na barra lateral. Para faturas de cartão Nubank use 'Positivo = gasto'."
    )
    st.stop()

st.sidebar.divider()
st.sidebar.markdown("#### Classificação com IA")
st.sidebar.caption(
    "A IA Groq é opcional. Apenas descrições sem categoria são enviadas, "
    "após sua autorização (com mascaramento básico de identificadores)."
)
if os.getenv("GROQ_API_KEY", "").strip():
    st.sidebar.caption("Chave Groq encontrada no .env (será verificada na chamada).")
else:
    st.sidebar.warning("GROQ_API_KEY não encontrada. Confira o arquivo .env na raiz do projeto.")

allow_ai = st.sidebar.checkbox("Autorizo enviar descrições desconhecidas à Groq", value=False)
unknown_descriptions = tx.loc[tx["categoria"] == UNKNOWN, "descricao"].unique().tolist()
uncategorized = [d for d in unknown_descriptions if d not in st.session_state.get("ai_labels", {})]

if allow_ai:
    if st.sidebar.button(
        f"Classificar com IA ({min(len(uncategorized), 200)})",
        disabled=not uncategorized,
        width="stretch",
    ):
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        if not api_key:
            st.sidebar.error("Chave ausente: configure GROQ_API_KEY no arquivo .env.")
        else:
            try:
                with st.spinner("Classificando descrições desconhecidas..."):
                    results = classify_unknown_with_ai(
                        uncategorized[:200],
                        api_key=api_key,
                        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
                    )
                st.session_state["ai_labels"].update(results)
                classified = sum(1 for category in results.values() if category != UNKNOWN)
                st.session_state["ai_summary"] = (len(results), classified)
                st.rerun()
            except AIClassificationError as exc:
                st.sidebar.error(str(exc))
            except Exception:
                st.sidebar.error(
                    "Erro inesperado ao executar a classificação. Confira o terminal; "
                    "nenhuma categoria foi alterada."
                )

if st.session_state.get("ai_summary"):
    analyzed, classified = st.session_state["ai_summary"]
    st.sidebar.success(
        f"IA analisou {analyzed} descrição(ões) e classificou {classified}. "
        "As demais continuam como Desconhecido."
    )

all_tx = add_user_labels(tx)
min_date, max_date = all_tx["data"].min(), all_tx["data"].max()
st.sidebar.divider()
st.sidebar.markdown("#### Filtros")
period = st.sidebar.date_input("Período", value=(min_date, max_date), min_value=min_date, max_value=max_date)
selected_categories = st.sidebar.multiselect("Categorias", CATEGORIES)
search = st.sidebar.text_input("Buscar descrição", placeholder="Ex.: supermercado")

filtered = all_tx.copy()
if isinstance(period, (list, tuple)) and len(period) == 2:
    start, end = period
    filtered = filtered.loc[filtered["data"].between(start, end)]
elif isinstance(period, date):
    filtered = filtered.loc[filtered["data"] == period]
if selected_categories:
    filtered = filtered.loc[filtered["categoria"].isin(selected_categories)]
if search.strip():
    filtered = filtered.loc[filtered["descricao"].str.contains(search.strip(), case=False, na=False, regex=False)]

st.markdown("### Visão geral")
summary = kpis(filtered)
count_unknown = int((filtered["categoria"] == UNKNOWN).sum())
metrics = st.columns(4)
metrics[0].metric("Total de gastos", brl_from_cents(summary["total_centavos"]))
metrics[1].metric("Transações", f"{summary['count']:,}".replace(",", "."))
metrics[2].metric("Gasto médio", brl_from_cents(summary["avg_centavos"]))
metrics[3].metric("Sem classificação", f"{count_unknown} · {brl_from_cents(summary['unknown_centavos'])}")

if filtered.empty:
    st.info("Nenhuma transação corresponde aos filtros. Altere o período, categoria ou busca.")
    st.stop()

st.markdown("### Distribuição dos gastos")
category_df = by_category(filtered)
monthly_df = by_month(filtered)
left, right = st.columns([1.03, 1], gap="large")
with left:
    st.markdown("**Participação por categoria**")
    fig = px.pie(category_df, names="categoria", values="valor", hole=0.66,
                 color="categoria", color_discrete_map=CATEGORY_COLORS)
    fig.update_traces(textposition="outside", textinfo="percent", hovertemplate="%{label}<br>R$ %{value:,.2f}<extra></extra>")
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.15, x=0))
    st.plotly_chart(plot_style(fig, 380), width="stretch", config={"displayModeBar": False})
with right:
    st.markdown("**Valor por categoria**")
    bar_data = category_df.sort_values("valor", ascending=True)
    fig = px.bar(bar_data, y="categoria", x="valor", orientation="h", color="categoria",
                 color_discrete_map=CATEGORY_COLORS, labels={"categoria": "", "valor": "Gasto (R$)"})
    fig.update_layout(showlegend=False)
    fig.update_traces(hovertemplate="%{y}<br>R$ %{x:,.2f}<extra></extra>")
    st.plotly_chart(plot_style(fig, 380), width="stretch", config={"displayModeBar": False})

st.markdown("### Evolução no tempo")
fig = px.line(monthly_df, x="mes", y="valor", markers=True, labels={"mes": "Mês", "valor": "Despesas (R$)"})
fig.update_traces(line=dict(color="#287A68", width=3), marker=dict(size=9),
                  fill="tozeroy", fillcolor="rgba(40,122,104,0.07)",
                  hovertemplate="%{x}<br>R$ %{y:,.2f}<extra></extra>")
st.plotly_chart(plot_style(fig, 300), width="stretch", config={"displayModeBar": False})

st.markdown("### Detalhamento por categoria")
category_table = category_df.rename(columns={"categoria": "Categoria", "valor": "Total (R$)", "participacao": "Participação (%)"})
st.dataframe(category_table[["Categoria", "Total (R$)", "Participação (%)"]], width="stretch", hide_index=True,
             column_config={"Total (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                            "Participação (%)": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100)})

st.markdown("### Revisar transações")
st.caption("Edite a categoria pela lista suspensa. A alteração atualiza indicadores e gráficos sem alterar o arquivo original.")
editor_source = filtered.sort_values(["data", "id"], ascending=[False, False]).head(250)
if len(filtered) > 250:
    st.caption("Mostrando as 250 transações mais recentes para edição. O dashboard e o CSV exportado incluem todas as transações filtradas.")
editor = editor_source.set_index("id")[["data", "descricao", "valor", "categoria", "origem"]].copy()
filter_key = hashlib.sha256(str((period, selected_categories, search)).encode()).hexdigest()[:10]
edited = st.data_editor(
    editor, key=f"editor_{st.session_state['fingerprint']}_{filter_key}", width="stretch", hide_index=True,
    num_rows="fixed",
    disabled=["data", "descricao", "valor", "origem"],
    column_config={
        "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
        "descricao": st.column_config.TextColumn("Descrição", width="large"),
        "valor": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
        "categoria": st.column_config.SelectboxColumn("Categoria", options=CATEGORIES, required=True),
        "origem": st.column_config.TextColumn("Classificada por"),
    },
)
changed = False
for transaction_id, row in edited.iterrows():
    selected = row["categoria"]
    previous = editor.at[transaction_id, "categoria"]
    if selected in CATEGORIES and selected != previous:
        st.session_state["overrides"][str(transaction_id)] = selected
        changed = True
if changed:
    st.rerun()

st.markdown("### Exportar resultados")
output = filtered[["data", "descricao", "valor", "categoria", "origem"]].copy()
output.columns = ["Data", "Descrição", "Valor (R$)", "Categoria", "Origem da classificação"]
output["Data"] = pd.to_datetime(output["Data"]).dt.strftime("%d/%m/%Y")
file_csv = output.to_csv(index=False, sep=";", decimal=",", encoding="utf-8-sig").encode("utf-8-sig")
summary_export = category_table[["Categoria", "Total (R$)", "Participação (%)"]].to_csv(
    index=False, sep=";", decimal=",", encoding="utf-8-sig").encode("utf-8-sig")
col1, col2 = st.columns(2)
col1.download_button("Baixar transações classificadas (CSV)", data=file_csv,
                     file_name="despesas_classificadas.csv", mime="text/csv", width="stretch")
col2.download_button("Baixar resumo por categoria (CSV)", data=summary_export,
                     file_name="resumo_categorias.csv", mime="text/csv", width="stretch")
st.caption("Análise informativa. Confira datas, sinais de débito/crédito e lançamentos duplicados antes de usar os totais para decisões financeiras.")
