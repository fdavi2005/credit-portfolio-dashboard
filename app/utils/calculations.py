import pandas as pd

from config.constants import STATUS_ATIVO, STATUS_EXCLUIDOS_DO_ATIVO


def saldo_carteira_ativa(df: pd.DataFrame) -> float:
    """Saldo total da carteira ativa: exclui liquidados e baixados por perda."""
    return df[~df["status"].isin(STATUS_EXCLUIDOS_DO_ATIVO)]["saldo_devedor"].sum()


def npl(df: pd.DataFrame) -> float:
    """NPL (%): sum(valor_em_atraso) / sum(saldo_devedor) × 100.

    Base de cálculo: contratos ativos e inadimplentes (exclui liquidados e baixados por perda).
    """
    base = df[~df["status"].isin(STATUS_EXCLUIDOS_DO_ATIVO)]
    saldo_total = base["saldo_devedor"].sum()
    if saldo_total == 0:
        return 0.0
    return base["valor_em_atraso"].sum() / saldo_total * 100


def taxa_media_ponderada_mensal(df: pd.DataFrame) -> float:
    """Taxa mensal média ponderada pelo saldo devedor (%) — base: carteira ativa."""
    base = df[~df["status"].isin(STATUS_EXCLUIDOS_DO_ATIVO)]
    peso_total = base["saldo_devedor"].sum()
    if peso_total == 0:
        return 0.0
    return (base["taxa_juros_mensal"] * base["saldo_devedor"]).sum() / peso_total


def taxa_anual_equivalente(taxa_mensal_pct: float) -> float:
    """Converte taxa mensal em % para taxa anual equivalente em %."""
    i = taxa_mensal_pct / 100
    return ((1 + i) ** 12 - 1) * 100


def prazo_medio_ponderado(df: pd.DataFrame) -> float:
    """Prazo residual médio ponderado pelo saldo devedor (meses) — base: carteira ativa."""
    base = df[~df["status"].isin(STATUS_EXCLUIDOS_DO_ATIVO)].copy()
    base["prazo_residual"] = base["prazo_meses"] - base["meses_decorridos"]
    peso_total = base["saldo_devedor"].sum()
    if peso_total == 0:
        return 0.0
    return (base["prazo_residual"] * base["saldo_devedor"]).sum() / peso_total


def ticket_medio(df: pd.DataFrame) -> float:
    """Ticket médio dos contratos ativos (valor de contratação)."""
    ativos = df[df["status"] == STATUS_ATIVO]
    if len(ativos) == 0:
        return 0.0
    return ativos["valor_contrato"].mean()


def pmt_price(pv: float, taxa_mensal_pct: float, prazo: int) -> float:
    """PMT pelo sistema Price. taxa_mensal_pct em % (ex.: 1.85)."""
    i = taxa_mensal_pct / 100
    if i == 0:
        return pv / prazo
    return pv * i / (1 - (1 + i) ** (-prazo))


def saldo_devedor_price(pv: float, taxa_mensal_pct: float, prazo: int, meses_decorridos: int) -> float:
    """Saldo devedor pelo sistema Price após k períodos pagos.

    PV × (1+i)^k − PMT × ((1+i)^k − 1) / i
    """
    i = taxa_mensal_pct / 100
    if meses_decorridos <= 0:
        return pv
    if meses_decorridos >= prazo:
        return 0.0
    pmt = pmt_price(pv, taxa_mensal_pct, prazo)
    fator = (1 + i) ** meses_decorridos
    return pv * fator - pmt * (fator - 1) / i
