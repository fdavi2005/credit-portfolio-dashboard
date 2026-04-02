import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from config.constants import STATUS_COLORS, STATUS_LIQUIDADO

_LAYOUT_DEFAULTS = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(size=12),
    margin=dict(t=48, b=8, l=8, r=8),
)


def chart_distribuicao_status(df: pd.DataFrame) -> go.Figure:
    """Donut: quantidade de contratos por status."""
    counts = df["status"].value_counts().reset_index()
    counts.columns = ["status", "contratos"]
    fig = px.pie(
        counts,
        names="status",
        values="contratos",
        color="status",
        color_discrete_map=STATUS_COLORS,
        title="Distribuição por Status",
        hole=0.45,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(**_LAYOUT_DEFAULTS, showlegend=False)
    return fig


def chart_saldo_por_prazo(df: pd.DataFrame) -> go.Figure:
    """Barras: saldo devedor agrupado por prazo original."""
    base = df[df["status"] != STATUS_LIQUIDADO]
    saldo_por_prazo = (
        base.groupby("prazo_meses")["saldo_devedor"]
        .sum()
        .reset_index()
        .rename(columns={"prazo_meses": "Prazo (meses)", "saldo_devedor": "Saldo (R$)"})
    )
    fig = px.bar(
        saldo_por_prazo,
        x="Prazo (meses)",
        y="Saldo (R$)",
        title="Saldo por Prazo Original (contratos não liquidados)",
        text_auto=".2s",
        color_discrete_sequence=["#3498db"],
    )
    fig.update_layout(**_LAYOUT_DEFAULTS)
    fig.update_traces(textfont_size=11, textangle=0)
    return fig


def chart_evolucao_originacao(df: pd.DataFrame) -> go.Figure:
    """Área: volume originado por mês."""
    df_plot = df.copy()
    df_plot["ano_mes"] = df_plot["data_inicio"].dt.to_period("M").astype(str)
    vol = (
        df_plot.groupby("ano_mes")["valor_contrato"]
        .sum()
        .reset_index()
        .rename(columns={"ano_mes": "Mês", "valor_contrato": "Volume (R$)"})
    )
    fig = px.area(
        vol,
        x="Mês",
        y="Volume (R$)",
        title="Evolução de Originação Mensal (R$)",
        color_discrete_sequence=["#3498db"],
    )
    fig.update_layout(**_LAYOUT_DEFAULTS)
    fig.update_xaxes(tickangle=45, nticks=24)
    return fig


def chart_distribuicao_taxa(df: pd.DataFrame) -> go.Figure:
    """Histograma: distribuição de taxas mensais na carteira ativa."""
    base = df[df["status"] != STATUS_LIQUIDADO]
    fig = px.histogram(
        base,
        x="taxa_juros_mensal",
        nbins=25,
        title="Distribuição de Taxa de Juros (% a.m.) — não liquidados",
        labels={"taxa_juros_mensal": "Taxa Mensal (%)"},
        color_discrete_sequence=["#9b59b6"],
    )
    fig.update_layout(**_LAYOUT_DEFAULTS, bargap=0.04)
    return fig
