import sys
from pathlib import Path

# Garante que o root do projeto está no sys.path ao rodar via `streamlit run app/inicio.py`
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from app.components.charts import (
    chart_distribuicao_status,
    chart_distribuicao_taxa,
    chart_evolucao_originacao,
    chart_evolucao_saldo_prazo_evo,
    chart_evolucao_taxa_faixas_evo,
    chart_participacao_prazo_evo,
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
    format_currency_compact,
    format_currency_k,
    format_number,
    format_percent,
)
from config.constants import (
    STATUS_ATIVO,
    STATUS_BAIXADO_POR_PERDA,
    STATUS_INADIMPLENTE,
    STATUS_LIQUIDADO,
)

st.set_page_config(
    page_title="Visão Geral — Carteira",
    page_icon="📊",
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
ANO_MES_REF = "2026-03"
_CONTRATOS_ATTRS = [
    "id_contrato", "cpf_anonimizado", "taxa_juros_mensal",
    "prazo_meses", "valor_contrato", "data_inicio",
]

data = load_data()
df_contratos = data["contratos"]
df_evolucao = data["evolucao"]

# Evolucao enriquecida com atributos estáticos do contrato
df_evolucao_merged = df_evolucao.merge(df_contratos[_CONTRATOS_ATTRS], on="id_contrato")

# Snapshot do último mês disponível (2026-03) — base para KPIs e gráficos estáticos
df_snapshot = (
    df_evolucao_merged[df_evolucao_merged["ano_mes"] == ANO_MES_REF]
    .rename(columns={"status_mes": "status", "mes_vida": "meses_decorridos"})
    .copy()
)

# ---------------------------------------------------------------------------
# Sidebar: filtros
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Filtros")

    status_sel = st.multiselect(
        "Status",
        options=[STATUS_ATIVO, STATUS_INADIMPLENTE, STATUS_LIQUIDADO, STATUS_BAIXADO_POR_PERDA],
        default=[STATUS_ATIVO, STATUS_INADIMPLENTE, STATUS_LIQUIDADO, STATUS_BAIXADO_POR_PERDA],
        key="vg_status",
    )

    prazos_disponiveis = sorted(df_snapshot["prazo_meses"].unique().tolist())
    prazo_sel = st.multiselect(
        "Prazo (meses)",
        options=prazos_disponiveis,
        default=prazos_disponiveis,
        key="vg_prazo",
    )

    st.divider()
    st.markdown("**Originação**")

    anos_disponiveis = sorted(df_snapshot["data_inicio"].dt.year.unique().tolist())
    anos_default = anos_disponiveis[-3:]
    ano_sel = st.multiselect(
        "Ano",
        options=anos_disponiveis,
        default=anos_default,
        key="vg_ano_originacao",
    )

    st.caption(f"Data de referência: {ANO_MES_REF}")

# Snapshot filtrado por status e prazo — base para KPIs e gráficos de distribuição
df_filtered = df_snapshot[
    df_snapshot["status"].isin(status_sel) & df_snapshot["prazo_meses"].isin(prazo_sel)
]

# IDs dos contratos que passam no filtro de status+prazo
ids_filtered = set(df_filtered["id_contrato"])

# Subconjunto dos contratos filtrados com ano de originação selecionado
ids_anos = (
    set(df_filtered[df_filtered["data_inicio"].dt.year.isin(ano_sel)]["id_contrato"])
    if ano_sel else set()
)

# Série temporal completa para os contratos filtrados (todos os meses, não só 2026-03)
df_evo_anos = df_evolucao_merged[df_evolucao_merged["id_contrato"].isin(ids_anos)]

# Contratos filtrados por ano — para o gráfico de originação
df_contratos_anos = df_contratos[df_contratos["id_contrato"].isin(ids_anos)]

# ---------------------------------------------------------------------------
# Cabeçalho
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <div class="header-banner">
        <h1>Carteira de Crédito</h1>
        <p>Consignado pré-fixado &nbsp;·&nbsp; {format_number(len(df_filtered))} contratos exibidos
        (total: {format_number(len(df_contratos))})</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if df_filtered.empty:
    st.warning("Nenhum contrato encontrado com os filtros selecionados.")
    st.stop()

# ---------------------------------------------------------------------------
# Cálculo dos KPIs (snapshot 2026-03)
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
        "value": format_currency_compact(saldo_total),
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
        "value": format_currency_k(ticket),
        "help": "Valor médio de contratação dos contratos ativos",
    },
    {
        "label": "Taxa Média Ponderada (a.m.)",
        "value": format_percent(taxa_mensal, decimals=2),
        "help": "Taxa mensal média ponderada pelo saldo devedor — proxy de rentabilidade da carteira",
    },
    {
        "label": "Taxa Média Equivalente (a.a.)",
        "value": format_percent(taxa_anual, decimals=2),
        "help": "Taxa anual equivalente à taxa mensal ponderada: (1 + i_m)^12 − 1",
    },
    {
        "label": "Prazo Médio Residual (meses)",
        "value": format_number(prazo_medio),
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
        chart_participacao_prazo_evo(df_evo_anos),
        use_container_width=True,
    )

# ---------------------------------------------------------------------------
# Gráficos — linha 2
# ---------------------------------------------------------------------------
st.plotly_chart(
    chart_evolucao_saldo_prazo_evo(df_evo_anos),
    use_container_width=True,
)

# ---------------------------------------------------------------------------
# Gráficos — linha 3
# ---------------------------------------------------------------------------
st.plotly_chart(
    chart_evolucao_taxa_faixas_evo(df_evo_anos),
    use_container_width=True,
)

# ---------------------------------------------------------------------------
# Gráficos — linha 4
# ---------------------------------------------------------------------------
st.plotly_chart(
    chart_evolucao_originacao(df_contratos_anos),
    use_container_width=True,
)

# ---------------------------------------------------------------------------
# Gráficos — linha 5
# ---------------------------------------------------------------------------
st.plotly_chart(
    chart_distribuicao_taxa(df_filtered),
    use_container_width=True,
)
