"""
Gerador v2 — carteira de crédito consignado pré-fixado.

Produz dois CSVs:
  contratos.csv        — 1 linha por contrato, dados fixos de originação
  evolucao_mensal.csv  — 1 linha por (contrato × mês ativo), saldo Price calculado

Parâmetros idênticos ao gerador v1 (seed=42, 2.000 contratos).
Inadimplência não implementada nesta versão: status_mes fixo como "ativo".
"""

import calendar
import hashlib
import os
import random
from datetime import date, timedelta

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Configurações
# ---------------------------------------------------------------------------
SEED = 42
N_CONTRATOS = 2_000

PRAZOS_MESES = [12, 24, 36, 48, 60, 72, 84, 96]

VALOR_MIN = 1_000.0
VALOR_MAX = 150_000.0

TAXA_MIN = 0.014   # 1,40% a.m.
TAXA_MAX = 0.024   # 2,40% a.m.

DATA_INI_INICIO = date(2015, 1, 1)
DATA_FIM_INICIO = date(2025, 12, 31)

DATA_REFERENCIA = date(2026, 3, 30)  # "hoje" fixo para reprodutibilidade


# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------

def anonimizar_cpf(cpf_int: int) -> str:
    raw = f"CPF-{cpf_int:011d}".encode()
    digest = hashlib.sha256(raw).hexdigest()[:12].upper()
    return f"ANON-{digest}"


def gerar_cpf_unico(rng: np.random.Generator, n: int) -> list[str]:
    seen: set[int] = set()
    result = []
    while len(result) < n:
        batch = rng.integers(10_000_000_000, 99_999_999_999, size=n - len(result) + 100)
        for c in batch:
            c = int(c)
            if c not in seen:
                seen.add(c)
                result.append(anonimizar_cpf(c))
                if len(result) == n:
                    break
    return result


def calcular_parcela(pv: float, taxa: float, prazo: int) -> float:
    """PMT pelo sistema Price: PV * i / (1 - (1+i)^-n)."""
    if taxa == 0:
        return pv / prazo
    return pv * taxa / (1 - (1 + taxa) ** (-prazo))


def calcular_saldo(pv: float, taxa: float, prazo: int, mes_vida: int) -> float:
    """Saldo devedor pelo sistema Price após mes_vida parcelas pagas."""
    if mes_vida <= 0:
        return pv
    if mes_vida >= prazo:
        return 0.0
    pmt = calcular_parcela(pv, taxa, prazo)
    fator = (1 + taxa) ** mes_vida
    return pv * fator - pmt * (fator - 1) / taxa


def data_aleatoria(rng: np.random.Generator, ini: date, fim: date) -> date:
    delta = (fim - ini).days
    return ini + timedelta(days=int(rng.integers(0, delta)))


def data_vencimento(dt_inicio: date, prazo: int) -> date:
    total_months = dt_inicio.month + prazo
    vc_year = dt_inicio.year + (total_months - 1) // 12
    vc_month = (total_months - 1) % 12 + 1
    max_day = calendar.monthrange(vc_year, vc_month)[1]
    return date(vc_year, vc_month, min(dt_inicio.day, max_day))


def adicionar_meses(dt: date, meses: int) -> date:
    total = dt.month + meses
    year = dt.year + (total - 1) // 12
    month = (total - 1) % 12 + 1
    max_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(dt.day, max_day))


# ---------------------------------------------------------------------------
# Gerador principal
# ---------------------------------------------------------------------------

def gerar_contratos(n: int = N_CONTRATOS, seed: int = SEED):
    """Retorna (df_contratos, df_evolucao)."""
    rng = np.random.default_rng(seed)
    random.seed(seed)

    cpfs = gerar_cpf_unico(rng, n)
    valores = rng.uniform(VALOR_MIN, VALOR_MAX, n).round(2)
    prazos = rng.choice(PRAZOS_MESES, size=n)
    taxas = rng.uniform(TAXA_MIN, TAXA_MAX, n).round(6)
    datas_inicio = [data_aleatoria(rng, DATA_INI_INICIO, DATA_FIM_INICIO) for _ in range(n)]

    contratos = []
    evolucao = []

    for i in range(n):
        id_contrato = f"CTR-{i + 1:06d}"
        pv = float(valores[i])
        taxa = float(taxas[i])
        prazo = int(prazos[i])
        dt_inicio = datas_inicio[i]
        dt_venc = data_vencimento(dt_inicio, prazo)

        parcela = round(calcular_parcela(pv, taxa, prazo), 2)
        taxa_anual = round(((1 + taxa) ** 12 - 1) * 100, 4)

        contratos.append({
            "id_contrato": id_contrato,
            "cpf_anonimizado": cpfs[i],
            "valor_contrato": pv,
            "prazo_meses": prazo,
            "taxa_juros_mensal": round(taxa * 100, 4),   # em %
            "taxa_juros_anual": taxa_anual,
            "parcela_mensal": parcela,
            "data_inicio": dt_inicio.isoformat(),
            "data_vencimento": dt_venc.isoformat(),
        })

        # Meses ativos até a data de referência (limitado ao prazo)
        meses_ate_ref = (DATA_REFERENCIA.year - dt_inicio.year) * 12 + (DATA_REFERENCIA.month - dt_inicio.month)
        meses_ativos = max(1, min(meses_ate_ref, prazo))

        for mes_vida in range(1, meses_ativos + 1):
            dt_mes = adicionar_meses(dt_inicio, mes_vida)
            ano_mes = f"{dt_mes.year}-{dt_mes.month:02d}"
            saldo = round(calcular_saldo(pv, taxa, prazo, mes_vida), 2)

            evolucao.append({
                "id_contrato": id_contrato,
                "ano_mes": ano_mes,
                "mes_vida": mes_vida,
                "saldo_devedor": saldo,
                "status_mes": "ativo",
            })

    df_contratos = pd.DataFrame(contratos).sort_values("data_inicio").reset_index(drop=True)
    df_evolucao = pd.DataFrame(evolucao)

    return df_contratos, df_evolucao


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    out_dir = os.path.dirname(__file__)

    print(f"Gerando {N_CONTRATOS} contratos sintéticos (v2)...")
    df_contratos, df_evolucao = gerar_contratos()

    csv_kwargs = dict(index=False, encoding="utf-8-sig", sep=";", decimal=",")

    path_contratos = os.path.join(out_dir, "contratos_mock.csv")
    df_contratos.to_csv(path_contratos, **csv_kwargs)
    print(f"contratos_mock.csv      salvo em: {path_contratos}  ({len(df_contratos):,} linhas)")

    path_evolucao = os.path.join(out_dir, "evolucao_mensal_mock.csv")
    df_evolucao.to_csv(path_evolucao, **csv_kwargs)
    print(f"evolucao_mensal_mock.csv salvo em: {path_evolucao}  ({len(df_evolucao):,} linhas)")

    print("\n=== Resumo ===")
    print(f"Contratos          : {len(df_contratos):,}")
    print(f"Linhas de evolução : {len(df_evolucao):,}")
    print(f"Meses por contrato : min={df_evolucao.groupby('id_contrato')['mes_vida'].max().min()}  "
          f"max={df_evolucao.groupby('id_contrato')['mes_vida'].max().max()}")
    print(f"Valor total orig.  : R$ {df_contratos['valor_contrato'].sum():,.2f}")
    print(f"Prazo médio (meses): {df_contratos['prazo_meses'].mean():.1f}")
    print(f"Taxa média (% a.m.): {df_contratos['taxa_juros_mensal'].mean():.4f}")
