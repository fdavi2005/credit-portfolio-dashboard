import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from config.constants import STATUS_COLORS, STATUS_INADIMPLENTE, STATUS_LIQUIDADO

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


_PRAZO_COLORS = {
    12: "#00b4d8",
    24: "#48cae4",
    36: "#2ecc71",
    48: "#f1c40f",
    60: "#f4a261",
    72: "#e76f51",
    84: "#9b59b6",
    96: "#e74c3c",
}

_REF_DATE = pd.Timestamp("2026-03-30")


def _monthly_snapshot(df: pd.DataFrame, groupby_col: str = "prazo_meses") -> pd.DataFrame:
    """
    Foto mensal da carteira: para cada mês entre data_inicio mínima e a data de
    referência, filtra contratos com data_inicio <= fim_do_mês e
    data_vencimento >= início_do_mês e status != liquidado, depois agrega
    saldo_devedor pela coluna indicada em groupby_col.
    """
    base = df[df["status"] != STATUS_LIQUIDADO].copy()
    if base.empty:
        return pd.DataFrame(columns=["ano_mes", groupby_col, "saldo_devedor"])

    months = pd.period_range(
        base["data_inicio"].min().to_period("M"),
        _REF_DATE.to_period("M"),
        freq="M",
    )

    rows = []
    for m in months:
        m_start = m.to_timestamp()
        m_next = (m + 1).to_timestamp()
        mask = (base["data_inicio"] < m_next) & (base["data_vencimento"] >= m_start)
        group = (
            base[mask]
            .groupby(groupby_col)["saldo_devedor"]
            .sum()
            .reset_index()
        )
        group["ano_mes"] = m.strftime("%Y-%m")
        rows.append(group)

    return pd.concat(rows, ignore_index=True)


def chart_participacao_prazo(df: pd.DataFrame) -> go.Figure:
    """Barras empilhadas 100%: participação proporcional de cada prazo no saldo mês a mês."""
    snapshot = _monthly_snapshot(df)
    if snapshot.empty:
        return go.Figure()

    totais = snapshot.groupby("ano_mes")["saldo_devedor"].sum().rename("total")
    snapshot = snapshot.join(totais, on="ano_mes")
    snapshot["participacao"] = snapshot["saldo_devedor"] / snapshot["total"] * 100

    prazos = sorted(snapshot["prazo_meses"].unique())
    fig = go.Figure()
    for prazo in prazos:
        d = snapshot[snapshot["prazo_meses"] == prazo].sort_values("ano_mes")
        fig.add_trace(go.Bar(
            x=d["ano_mes"],
            y=d["participacao"],
            name=f"{prazo}m",
            marker_color=_PRAZO_COLORS.get(prazo, "#aaaaaa"),
        ))
    fig.update_layout(
        **_LAYOUT_DEFAULTS,
        title="Participação por Prazo no Saldo (% por Mês)",
        barmode="stack",
        yaxis=dict(ticksuffix="%", range=[0, 100]),
        legend=dict(title="Prazo", orientation="h", y=-0.25, x=0),
    )
    fig.update_xaxes(tickangle=45, nticks=24)
    return fig


def chart_evolucao_saldo_prazo(df: pd.DataFrame) -> go.Figure:
    """Área empilhada: evolução do saldo devedor por prazo mês a mês."""
    snapshot = _monthly_snapshot(df)
    if snapshot.empty:
        return go.Figure()

    prazos = sorted(snapshot["prazo_meses"].unique())
    fig = go.Figure()
    for prazo in prazos:
        d = snapshot[snapshot["prazo_meses"] == prazo].sort_values("ano_mes")
        color = _PRAZO_COLORS.get(prazo, "#aaaaaa")
        fig.add_trace(go.Scatter(
            x=d["ano_mes"],
            y=d["saldo_devedor"],
            name=f"{prazo}m",
            mode="lines",
            stackgroup="one",
            line=dict(width=0.5, color=color),
            fillcolor=color,
        ))
    fig.update_layout(
        **_LAYOUT_DEFAULTS,
        title="Evolução do Saldo Devedor por Prazo (R$)",
        yaxis=dict(tickprefix="R$ "),
        legend=dict(title="Prazo", orientation="h", y=-0.25, x=0),
    )
    fig.update_xaxes(tickangle=45, nticks=24)
    return fig


_TAXA_BINS = [1.4, 1.6, 1.8, 2.0, 2.2, 2.4]
_TAXA_LABELS = [f"{_TAXA_BINS[i]:.1f}–{_TAXA_BINS[i+1]:.1f}" for i in range(len(_TAXA_BINS) - 1)]
_TAXA_FAIXA_COLORS = {
    "1.4–1.6": "#2ecc71",
    "1.6–1.8": "#f1c40f",
    "1.8–2.0": "#f4a261",
    "2.0–2.2": "#e67e22",
    "2.2–2.4": "#e74c3c",
}


def chart_evolucao_taxa_faixas(df: pd.DataFrame) -> go.Figure:
    """Área empilhada 100%: participação de cada faixa de taxa no saldo devedor mês a mês."""
    df_taxa = df.copy()
    df_taxa["faixa_taxa"] = pd.cut(
        df_taxa["taxa_juros_mensal"],
        bins=_TAXA_BINS,
        labels=_TAXA_LABELS,
        right=False,
    ).astype(str)

    snapshot = _monthly_snapshot(df_taxa, groupby_col="faixa_taxa")
    if snapshot.empty:
        return go.Figure()

    totais = snapshot.groupby("ano_mes")["saldo_devedor"].sum().rename("total")
    snapshot = snapshot.join(totais, on="ano_mes")
    snapshot["participacao"] = snapshot["saldo_devedor"] / snapshot["total"] * 100

    fig = go.Figure()
    for faixa in _TAXA_LABELS:
        d = snapshot[snapshot["faixa_taxa"] == faixa].sort_values("ano_mes")
        color = _TAXA_FAIXA_COLORS.get(faixa, "#aaaaaa")
        fig.add_trace(go.Scatter(
            x=d["ano_mes"],
            y=d["participacao"],
            name=f"{faixa}%",
            mode="lines",
            stackgroup="one",
            line=dict(width=0.5, color=color),
            fillcolor=color,
        ))
    fig.update_layout(
        **_LAYOUT_DEFAULTS,
        title="Participação por Faixa de Taxa no Saldo (% por Mês)",
        yaxis=dict(ticksuffix="%", range=[0, 100]),
        legend=dict(title="Taxa (% a.m.)", orientation="h", y=-0.25, x=0),
    )
    fig.update_xaxes(tickangle=45, nticks=24)
    return fig


_MESES_PT = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
_ANO_COLORS = ["#3498db", "#2ecc71", "#e67e22", "#9b59b6"]


def chart_evolucao_originacao(df: pd.DataFrame) -> go.Figure:
    """Barras agrupadas: volume originado por mês do ano, uma barra por ano."""
    df_plot = df.copy()
    df_plot["mes"] = df_plot["data_inicio"].dt.month
    df_plot["ano"] = df_plot["data_inicio"].dt.year
    vol = (
        df_plot.groupby(["ano", "mes"])["valor_contrato"]
        .sum()
        .reset_index()
    )
    vol["mes_nome"] = vol["mes"].apply(lambda m: _MESES_PT[m - 1])

    anos = sorted(vol["ano"].unique())
    fig = go.Figure()
    for i, ano in enumerate(anos):
        d = vol[vol["ano"] == ano].sort_values("mes")
        fig.add_trace(go.Bar(
            x=d["mes_nome"],
            y=d["valor_contrato"],
            name=str(ano),
            marker_color=_ANO_COLORS[i % len(_ANO_COLORS)],
        ))
    fig.update_layout(
        **_LAYOUT_DEFAULTS,
        title="Originação Mensal por Ano (R$)",
        barmode="group",
        yaxis=dict(tickprefix="R$ "),
        xaxis=dict(categoryorder="array", categoryarray=_MESES_PT),
        legend=dict(title="Ano", orientation="h", y=-0.25, x=0),
    )
    return fig


_AGING_BINS = [0, 5, 10, 20, 30, 101]
_AGING_LABELS = ["0–5%", "5–10%", "10–20%", "20–30%", ">30%"]
_AGING_COLORS = ["#f1c40f", "#f4a261", "#e67e22", "#e74c3c", "#c0392b"]


def _monthly_npl_series(df: pd.DataFrame) -> pd.DataFrame:
    """
    Para cada mês entre data_inicio mínima e a data de referência, filtra
    contratos ativos no mês (mesma lógica de _monthly_snapshot) e calcula
    NPL = sum(valor_em_atraso) / sum(saldo_devedor) × 100.
    """
    base = df[df["status"] != STATUS_LIQUIDADO].copy()
    if base.empty:
        return pd.DataFrame(columns=["ano_mes", "npl_pct"])

    months = pd.period_range(
        base["data_inicio"].min().to_period("M"),
        _REF_DATE.to_period("M"),
        freq="M",
    )

    rows = []
    for m in months:
        m_start = m.to_timestamp()
        m_next = (m + 1).to_timestamp()
        mask = (base["data_inicio"] < m_next) & (base["data_vencimento"] >= m_start)
        subset = base[mask]
        saldo = subset["saldo_devedor"].sum()
        rows.append({
            "ano_mes": m.strftime("%Y-%m"),
            "npl_pct": subset["valor_em_atraso"].sum() / saldo * 100 if saldo > 0 else 0.0,
        })

    return pd.DataFrame(rows)


def chart_evolucao_npl(df: pd.DataFrame) -> go.Figure:
    """Linha com área: evolução do NPL (%) mês a mês."""
    series = _monthly_npl_series(df)
    if series.empty:
        return go.Figure()

    fig = go.Figure(go.Scatter(
        x=series["ano_mes"],
        y=series["npl_pct"],
        mode="lines+markers",
        line=dict(color="#e74c3c", width=2),
        marker=dict(size=5, color="#e74c3c"),
        fill="tozeroy",
        fillcolor="rgba(231, 76, 60, 0.1)",
        name="NPL",
    ))
    fig.update_layout(
        **_LAYOUT_DEFAULTS,
        title="Evolução do NPL (%) Mês a Mês",
        yaxis=dict(ticksuffix="%"),
        showlegend=False,
    )
    fig.update_xaxes(tickangle=45, nticks=24)
    return fig


def chart_atraso_por_prazo(df: pd.DataFrame) -> go.Figure:
    """Barras horizontais: valor em atraso por prazo original."""
    base = df[df["status"] == STATUS_INADIMPLENTE]
    if base.empty:
        return go.Figure()

    grouped = (
        base.groupby("prazo_meses")["valor_em_atraso"]
        .sum()
        .reset_index()
        .sort_values("prazo_meses")
    )
    grouped["label"] = grouped["prazo_meses"].astype(str) + "m"

    fig = go.Figure(go.Bar(
        x=grouped["valor_em_atraso"],
        y=grouped["label"],
        orientation="h",
        marker_color=[_PRAZO_COLORS.get(p, "#aaaaaa") for p in grouped["prazo_meses"]],
        text=grouped["valor_em_atraso"].apply(lambda v: f"R$ {v / 1_000:.0f}K"),
        textposition="outside",
    ))
    fig.update_layout(
        **_LAYOUT_DEFAULTS,
        title="Valor em Atraso por Prazo (R$)",
        xaxis=dict(tickprefix="R$ "),
    )
    return fig


def chart_aging_faixas(df: pd.DataFrame) -> go.Figure:
    """Barras: concentração do valor em atraso por faixa de % de atraso sobre o saldo."""
    base = df[df["status"] == STATUS_INADIMPLENTE].copy()
    if base.empty:
        return go.Figure()

    base["pct_atraso"] = base["valor_em_atraso"] / base["saldo_devedor"] * 100
    base["faixa"] = pd.cut(
        base["pct_atraso"],
        bins=_AGING_BINS,
        labels=_AGING_LABELS,
        right=False,
    ).astype(str)

    grouped = (
        base.groupby("faixa")["valor_em_atraso"]
        .sum()
        .reindex(_AGING_LABELS, fill_value=0)
        .reset_index()
    )
    grouped.columns = ["faixa", "valor_em_atraso"]

    fig = go.Figure(go.Bar(
        x=grouped["faixa"],
        y=grouped["valor_em_atraso"],
        marker_color=_AGING_COLORS,
        text=grouped["valor_em_atraso"].apply(lambda v: f"R$ {v / 1_000:.0f}K"),
        textposition="outside",
    ))
    fig.update_layout(
        **_LAYOUT_DEFAULTS,
        title="Aging: Valor em Atraso por Faixa (% sobre Saldo Devedor)",
        yaxis=dict(tickprefix="R$ "),
    )
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
