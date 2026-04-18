"""
Gerador v2 — carteira de crédito consignado pré-fixado.

Produz dois CSVs:
  contratos_mock.csv        — 1 linha por contrato, dados fixos de originação
  evolucao_mensal_mock.csv  — 1 linha por (contrato × mês ativo), com modelo
                              de inadimplência por curva de hazard e PCLD
                              conforme Resolução Previc 21/2023

Parâmetros:
  seed=42, 2.000 contratos, mesmos ranges de taxa/prazo/valor do gerador v1.

Modelo de inadimplência:
  - Probabilidade mensal de default por faixa de mes_vida (hazard rate):
      1-6:    0,1%
      7-12:   0,2%
      13-24:  0,8%
      25-36:  0,6%
      37-60:  0,4%
      61+:    0,7%
  - Taxa de cura mensal: 35% (contrato inadimplente pode regularizar a cada mês)
  - Quando inadimplente: acumula dias_atraso (+30/mês) e valor_em_atraso (parcela × meses em atraso)
  - Quando cura: zera dias_atraso e valor_em_atraso, registra data_regularizacao
  - Múltiplos ciclos de default/cura são possíveis no mesmo contrato

PCLD — Resolução Previc 21/2023:
  dias_atraso  0      →  0%
  1–30         →  0%
  31–60        →  1%
  61–90        →  5%
  91–120       → 10%
  121–180      → 25%
  181–240      → 50%
  241–360      → 75%
  > 360        → 100%
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

# Curva de hazard: (mes_vida_max_inclusive, prob_mensal)
HAZARD_CURVE = [
    (6,   0.001),
    (12,  0.002),
    (24,  0.008),
    (36,  0.006),
    (60,  0.004),
    (None, 0.007),   # 61+
]

# Perfis de inadimplência sorteados a cada ciclo de default
PERFIS_INADIMPLENCIA = {
    "A": {"prob": 0.70, "taxa_cura": 0.35},
    "B": {"prob": 0.30, "taxa_cura": 0.05},
}

# Faixas PCLD — Resolução Previc 21/2023: (dias_atraso_max_inclusive, percentual)
PCLD_FAIXAS = [
    (0,   0.00),
    (30,  0.00),
    (60,  0.01),
    (90,  0.05),
    (120, 0.10),
    (180, 0.25),
    (240, 0.50),
    (360, 0.75),
    (None, 1.00),
]


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


def data_vencimento_contrato(dt_inicio: date, prazo: int) -> date:
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


def hazard_prob(mes_vida: int) -> float:
    for limite, prob in HAZARD_CURVE:
        if limite is None or mes_vida <= limite:
            return prob
    return HAZARD_CURVE[-1][1]


def pcld_percentual(dias_atraso: int) -> float:
    for limite, perc in PCLD_FAIXAS:
        if limite is None or dias_atraso <= limite:
            return perc
    return 1.0


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
        dt_venc = data_vencimento_contrato(dt_inicio, prazo)
        parcela = round(calcular_parcela(pv, taxa, prazo), 2)
        taxa_anual = round(((1 + taxa) ** 12 - 1) * 100, 4)

        contratos.append({
            "id_contrato": id_contrato,
            "cpf_anonimizado": cpfs[i],
            "valor_contrato": pv,
            "prazo_meses": prazo,
            "taxa_juros_mensal": round(taxa * 100, 4),
            "taxa_juros_anual": taxa_anual,
            "parcela_mensal": parcela,
            "data_inicio": dt_inicio.isoformat(),
            "data_vencimento": dt_venc.isoformat(),
        })

        meses_ate_ref = (
            (DATA_REFERENCIA.year - dt_inicio.year) * 12
            + (DATA_REFERENCIA.month - dt_inicio.month)
        )
        meses_ativos = max(1, min(meses_ate_ref, prazo))

        # --- Simulação de inadimplência mês a mês ---
        inadimplente = False
        baixado = False
        dias_atraso = 0
        saldo_inad = 0.0       # saldo que cresce com juros durante a inadimplência
        data_inadimplencia = None
        data_regularizacao = None
        perfil_atual = None    # sorteado a cada novo ciclo de default
        taxa_cura_atual = 0.0

        for mes_vida in range(1, meses_ativos + 1):
            dt_mes = adicionar_meses(dt_inicio, mes_vida)
            ano_mes = f"{dt_mes.year}-{dt_mes.month:02d}"

            # Contrato já baixado: permanece na série com zeros
            if baixado:
                evolucao.append({
                    "id_contrato": id_contrato,
                    "ano_mes": ano_mes,
                    "mes_vida": mes_vida,
                    "saldo_devedor": 0.0,
                    "status_mes": "baixado_por_perda",
                    "dias_atraso": dias_atraso,
                    "valor_em_atraso": 0.0,
                    "data_inadimplencia": data_inadimplencia,
                    "data_regularizacao": data_regularizacao,
                    "pcld": 0.0,
                    "perfil_inadimplencia": perfil_atual,
                })
                continue

            if inadimplente:
                # Saldo cresce com juros contratuais, sem amortização
                saldo_inad = round(saldo_inad * (1 + taxa), 2)
                dias_atraso += 30

                # Write-off: mais de 360 dias em atraso
                if dias_atraso > 360:
                    baixado = True
                    evolucao.append({
                        "id_contrato": id_contrato,
                        "ano_mes": ano_mes,
                        "mes_vida": mes_vida,
                        "saldo_devedor": 0.0,
                        "status_mes": "baixado_por_perda",
                        "dias_atraso": dias_atraso,
                        "valor_em_atraso": 0.0,
                        "data_inadimplencia": data_inadimplencia,
                        "data_regularizacao": data_regularizacao,
                        "pcld": 0.0,
                        "perfil_inadimplencia": perfil_atual,
                    })
                    continue

                # Tenta cura usando a taxa do perfil sorteado no ciclo atual
                if rng.random() < taxa_cura_atual:
                    inadimplente = False
                    data_regularizacao = dt_mes.isoformat()
                    dias_atraso = 0
                    saldo_inad = 0.0
                    perfil_atual = None
                    taxa_cura_atual = 0.0
                    status_mes = "ativo"
                    valor_em_atraso = 0.0
                    saldo = round(calcular_saldo(pv, taxa, prazo, mes_vida), 2)
                else:
                    status_mes = "inadimplente"
                    valor_em_atraso = round(parcela * (dias_atraso / 30), 2)
                    saldo = saldo_inad
            else:
                saldo = round(calcular_saldo(pv, taxa, prazo, mes_vida), 2)

                # Testa transição para default
                if rng.random() < hazard_prob(mes_vida):
                    inadimplente = True
                    data_inadimplencia = dt_mes.isoformat()
                    data_regularizacao = None
                    dias_atraso = 30
                    saldo_inad = round(saldo * (1 + taxa), 2)
                    status_mes = "inadimplente"
                    valor_em_atraso = round(parcela, 2)
                    saldo = saldo_inad
                    # Sorteia perfil para este ciclo de inadimplência
                    perfil_atual = rng.choice(
                        list(PERFIS_INADIMPLENCIA.keys()),
                        p=[v["prob"] for v in PERFIS_INADIMPLENCIA.values()],
                    )
                    taxa_cura_atual = PERFIS_INADIMPLENCIA[perfil_atual]["taxa_cura"]
                else:
                    status_mes = "ativo"
                    valor_em_atraso = 0.0

            pcld = round(pcld_percentual(dias_atraso) * saldo, 2)

            evolucao.append({
                "id_contrato": id_contrato,
                "ano_mes": ano_mes,
                "mes_vida": mes_vida,
                "saldo_devedor": saldo,
                "status_mes": status_mes,
                "dias_atraso": dias_atraso,
                "valor_em_atraso": valor_em_atraso,
                "data_inadimplencia": data_inadimplencia,
                "data_regularizacao": data_regularizacao,
                "pcld": pcld,
                "perfil_inadimplencia": perfil_atual,
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
    print(f"contratos_mock.csv       salvo: {len(df_contratos):,} linhas")

    path_evolucao = os.path.join(out_dir, "evolucao_mensal_mock.csv")
    df_evolucao.to_csv(path_evolucao, **csv_kwargs)
    print(f"evolucao_mensal_mock.csv salvo: {len(df_evolucao):,} linhas")

    # --- Resumo ---
    inad = df_evolucao[df_evolucao["status_mes"] == "inadimplente"]
    ultimo_mes = df_evolucao.groupby("id_contrato")["mes_vida"].max()

    print("\n=== Resumo ===")
    print(f"Contratos              : {len(df_contratos):,}")
    print(f"Linhas de evolução     : {len(df_evolucao):,}")
    print(f"Meses por contrato     : min={ultimo_mes.min()}  max={ultimo_mes.max()}")
    print(f"Valor total orig.      : R$ {df_contratos['valor_contrato'].sum():,.2f}")
    print(f"Prazo médio (meses)    : {df_contratos['prazo_meses'].mean():.1f}")
    print(f"Taxa média (% a.m.)    : {df_contratos['taxa_juros_mensal'].mean():.4f}")

    print("\n=== Inadimplência ===")
    total_linhas = len(df_evolucao)
    print(f"Linhas inadimplentes   : {len(inad):,}  ({len(inad)/total_linhas*100:.2f}% do total)")
    contratos_inad = inad["id_contrato"].nunique()
    print(f"Contratos com default  : {contratos_inad:,}  ({contratos_inad/N_CONTRATOS*100:.1f}%)")
    print(f"Valor em atraso (total): R$ {inad['valor_em_atraso'].sum():,.2f}")
    print(f"PCLD total             : R$ {df_evolucao['pcld'].sum():,.2f}")

    print("\nDistribuição de perfil (linhas inadimplentes + baixadas):")
    print(inad["perfil_inadimplencia"].value_counts().to_string())

    # Distribuição de status no último mês de cada contrato
    ultimo_status = df_evolucao.sort_values("mes_vida").groupby("id_contrato")["status_mes"].last()
    print("\nStatus no último mês observado:")
    print(ultimo_status.value_counts().to_string())
