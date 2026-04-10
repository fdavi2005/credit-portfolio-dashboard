import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from app.components.charts import (
    chart_aging_faixas,
    chart_atraso_por_prazo,
    chart_evolucao_npl,
)
from app.components.kpi_cards import render_kpi_row
from app.utils.calculations import npl
from app.utils.data_loader import load_data
from app.utils.formatters import (
    format_currency_compact,
    format_currency_k,
    format_number,
    format_percent,
)
from config.constants import STATUS_INADIMPLENTE, STATUS_LIQUIDADO

st.set_page_config(
    page_title="Inadimplência — Carteira",
    page_icon="📉",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.header-banner {
    background: linear-gradient(135deg, #1a0a3d 0%, #1a3a8f 100%);
    border-radius: 12px;
    padding: 1.5rem 2rem;
    margin-bottom: 1rem;
    text-align: center;
}
.header-banner h1 {
    color: #ffffff !important;
    font-size: 1.9rem;
    font-weight: 700;
    margin: 0;
    letter-spacing: -0.01em;
}
.header-banner p {
    color: rgba(255,255,255,0.7);
    font-size: 0.85rem;
    margin: 0.25rem 0 0;
}
[data-testid="stMetric"] {
    background: #dbe7f5;
    border: 1px solid rgba(26, 58, 139, 0.15);
    border-radius: 12px;
}
[data-testid="stMetricLabel"] {
    text-align: center;
}
[data-testid="stMetricValue"] {
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Dados
# ---------------------------------------------------------------------------
df = load_data()

# ---------------------------------------------------------------------------
# Sidebar: filtros
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Filtros")

    prazos_disponiveis = sorted(df["prazo_meses"].unique().tolist())
    prazo_sel = st.multiselect(
        "Prazo (meses)",
        options=prazos_disponiveis,
        default=prazos_disponiveis,
        key="inadimp_prazo",
    )

    st.caption("Data de referência: 30/03/2026")

# df_filtered: base completa (todos os status) filtrada por prazo — usada para
# NPL e evolução temporal, que precisam do denominador correto (não liquidados).
df_filtered = df[df["prazo_meses"].isin(prazo_sel)]

# df_inad: apenas contratos inadimplentes — usado nos KPIs de atraso e gráficos
# que focam exclusivamente na parcela inadimplente da carteira.
df_inad = df_filtered[df_filtered["status"] == STATUS_INADIMPLENTE]

# ---------------------------------------------------------------------------
# Cabeçalho
# ---------------------------------------------------------------------------
n_inad = len(df_inad)
n_total = len(df_filtered[df_filtered["status"] != STATUS_LIQUIDADO])

st.markdown(
    f"""
    <div class="header-banner">
        <h1>Inadimplência</h1>
        <p>Consignado pré-fixado &nbsp;·&nbsp; {format_number(n_inad)} contratos inadimplentes
        de {format_number(n_total)} ativos</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if df_filtered.empty:
    st.warning("Nenhum contrato encontrado com os filtros selecionados.")
    st.stop()

# ---------------------------------------------------------------------------
# Cálculo dos KPIs
# ---------------------------------------------------------------------------
npl_pct = npl(df_filtered)
valor_total_atraso = df_inad["valor_em_atraso"].sum()
ticket_atraso = df_inad["valor_em_atraso"].mean() if n_inad > 0 else 0.0
pct_contratos_inad = n_inad / n_total * 100 if n_total > 0 else 0.0

# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------
st.subheader("Visão Geral da Inadimplência")
render_kpi_row([
    {
        "label": "NPL (%)",
        "value": format_percent(npl_pct),
        "help": "Non-Performing Loan: valor em atraso / saldo devedor total × 100 (base: não liquidados)",
    },
    {
        "label": "Valor Total em Atraso",
        "value": format_currency_compact(valor_total_atraso),
        "help": "Soma de valor_em_atraso de todos os contratos inadimplentes na seleção",
    },
    {
        "label": "Contratos Inadimplentes",
        "value": format_number(n_inad),
        "help": "Número de contratos com status 'inadimplente' na seleção",
    },
    {
        "label": "% Contratos em Atraso",
        "value": format_percent(pct_contratos_inad),
        "help": "Inadimplentes / total não liquidados × 100",
    },
    {
        "label": "Ticket Médio em Atraso",
        "value": format_currency_k(ticket_atraso),
        "help": "Valor médio de valor_em_atraso por contrato inadimplente",
    },
])

st.divider()

# ---------------------------------------------------------------------------
# Gráfico — evolução do NPL
# ---------------------------------------------------------------------------
st.plotly_chart(
    chart_evolucao_npl(df_filtered),
    use_container_width=True,
)

st.divider()

# ---------------------------------------------------------------------------
# Gráficos — distribuição e aging
# ---------------------------------------------------------------------------
col1, col2 = st.columns(2)

with col1:
    st.plotly_chart(
        chart_atraso_por_prazo(df_filtered),
        use_container_width=True,
    )

with col2:
    st.plotly_chart(
        chart_aging_faixas(df_filtered),
        use_container_width=True,
    )
