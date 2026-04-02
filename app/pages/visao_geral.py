import sys
from pathlib import Path

# Garante que o root do projeto está no sys.path ao rodar via `streamlit run app/main.py`
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from app.components.charts import (
    chart_distribuicao_status,
    chart_distribuicao_taxa,
    chart_evolucao_originacao,
    chart_saldo_por_prazo,
)
from app.components.kpi_cards import render_kpi_row
from app.utils.calculations import (
    npl,
    prazo_medio_ponderado,
    saldo_carteira_ativa,
    taxa_anual_equivalente,
    taxa_media_ponderada_mensal,
    ticket_medio,
)
from app.utils.data_loader import load_data
from app.utils.formatters import (
    format_currency,
    format_months,
    format_number,
    format_percent,
)
from config.constants import STATUS_ATIVO, STATUS_INADIMPLENTE, STATUS_LIQUIDADO

st.set_page_config(
    page_title="Visão Geral — Carteira Consignado",
    page_icon="📊",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Dados
# ---------------------------------------------------------------------------
df = load_data()

# ---------------------------------------------------------------------------
# Sidebar: filtros
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Filtros")

    status_sel = st.multiselect(
        "Status",
        options=[STATUS_ATIVO, STATUS_INADIMPLENTE, STATUS_LIQUIDADO],
        default=[STATUS_ATIVO, STATUS_INADIMPLENTE, STATUS_LIQUIDADO],
        key="vg_status",
    )

    prazos_disponiveis = sorted(df["prazo_meses"].unique().tolist())
    prazo_sel = st.multiselect(
        "Prazo (meses)",
        options=prazos_disponiveis,
        default=prazos_disponiveis,
        key="vg_prazo",
    )

    st.caption("Data de referência: 30/03/2026")

df_filtered = df[
    df["status"].isin(status_sel) & df["prazo_meses"].isin(prazo_sel)
]

# ---------------------------------------------------------------------------
# Cabeçalho
# ---------------------------------------------------------------------------
st.title("Visão Geral da Carteira")
st.caption(
    f"Carteira consignado pré-fixado · {format_number(len(df_filtered))} contratos exibidos "
    f"(total: {format_number(len(df))})"
)

if df_filtered.empty:
    st.warning("Nenhum contrato encontrado com os filtros selecionados.")
    st.stop()

# ---------------------------------------------------------------------------
# Cálculo dos KPIs
# ---------------------------------------------------------------------------
saldo_total = saldo_carteira_ativa(df_filtered)
n_ativos = int((df_filtered["status"] == STATUS_ATIVO).sum())
n_inadimplentes = int((df_filtered["status"] == STATUS_INADIMPLENTE).sum())
cpfs_unicos = df_filtered["cpf_anonimizado"].nunique()
npl_pct = npl(df_filtered)
ticket = ticket_medio(df_filtered)
taxa_mensal = taxa_media_ponderada_mensal(df_filtered)
taxa_anual = taxa_anual_equivalente(taxa_mensal)
prazo_medio = prazo_medio_ponderado(df_filtered)

# ---------------------------------------------------------------------------
# Linha 1 de KPIs — volume e operações
# ---------------------------------------------------------------------------
st.subheader("Volume e Operações")
render_kpi_row([
    {
        "label": "Saldo da Carteira Ativa",
        "value": format_currency(saldo_total),
        "help": "Saldo devedor total de contratos ativos e inadimplentes (status ≠ liquidado)",
    },
    {
        "label": "Contratos Ativos",
        "value": format_number(n_ativos),
        "help": "Contratos com status 'ativo' (em dia)",
    },
    {
        "label": "Contratos Inadimplentes",
        "value": format_number(n_inadimplentes),
        "help": "Contratos com status 'inadimplente'",
    },
    {
        "label": "CPFs Únicos",
        "value": format_number(cpfs_unicos),
        "help": "Número de clientes distintos na seleção atual",
    },
])

st.divider()

# ---------------------------------------------------------------------------
# Linha 2 de KPIs — risco e rentabilidade
# ---------------------------------------------------------------------------
st.subheader("Risco e Rentabilidade")
render_kpi_row([
    {
        "label": "Inadimplência (NPL)",
        "value": format_percent(npl_pct),
        "help": "Non-Performing Loan: valor em atraso / saldo devedor total × 100 (base: não liquidados)",
    },
    {
        "label": "Ticket Médio",
        "value": format_currency(ticket),
        "help": "Valor médio de contratação dos contratos ativos",
    },
    {
        "label": "Taxa Média Ponderada (a.m.)",
        "value": format_percent(taxa_mensal, decimals=4),
        "help": "Taxa mensal média ponderada pelo saldo devedor — proxy de rentabilidade da carteira",
    },
    {
        "label": "Taxa Média Equivalente (a.a.)",
        "value": format_percent(taxa_anual, decimals=2),
        "help": "Taxa anual equivalente à taxa mensal ponderada: (1 + i_m)^12 − 1",
    },
    {
        "label": "Prazo Médio Residual",
        "value": format_months(prazo_medio),
        "help": "Prazo remanescente médio ponderado pelo saldo devedor",
    },
])

st.divider()

# ---------------------------------------------------------------------------
# Gráficos — linha 1
# ---------------------------------------------------------------------------
col1, col2 = st.columns([1, 2])

with col1:
    st.plotly_chart(
        chart_distribuicao_status(df_filtered),
        use_container_width=True,
    )

with col2:
    st.plotly_chart(
        chart_saldo_por_prazo(df_filtered),
        use_container_width=True,
    )

# ---------------------------------------------------------------------------
# Gráficos — linha 2
# ---------------------------------------------------------------------------
col3, col4 = st.columns(2)

with col3:
    st.plotly_chart(
        chart_evolucao_originacao(df_filtered),
        use_container_width=True,
    )

with col4:
    st.plotly_chart(
        chart_distribuicao_taxa(df_filtered),
        use_container_width=True,
    )
