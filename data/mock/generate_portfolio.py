"""
Gerador de dados sintéticos de carteira de crédito consignado pré-fixado.

Gera contratos com:
- CPF anonimizado
- Valor do contrato
- Prazo em meses
- Taxa de juros pré-fixada (mensal)
- Data de início
- Status (ativo / inadimplente / liquidado)
- Valor em atraso (quando inadimplente)
- Campos derivados: parcela mensal, saldo devedor estimado
"""

import calendar
import hashlib
import random
from datetime import date, timedelta

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Configurações
# ---------------------------------------------------------------------------
SEED = 42
N_CONTRATOS = 2_000

# Distribuição de status (proporções aproximadas do mercado consignado)
STATUS_PESOS = {"ativo": 0.70, "inadimplente": 0.10, "liquidado": 0.20}

# Prazos disponíveis (meses) — padrão consignado público/privado
PRAZOS_MESES = [12, 24, 36, 48, 60, 72, 84, 96]

# Faixas de valor (R$)
VALOR_MIN = 1_000.0
VALOR_MAX = 150_000.0

# Taxa de juros pré-fixada mensal (%) — faixa realista INSS/funcionalismo
TAXA_MIN = 0.014   # 1,40% a.m.
TAXA_MAX = 0.024   # 2,40% a.m.

# Janela de datas de início dos contratos (últimos 10 anos)
DATA_FIM_INICIO = date(2025, 12, 31)
DATA_INI_INICIO = date(2015, 1, 1)

# Percentual do saldo devedor que está em atraso (para inadimplentes)
ATRASO_MIN_PERC = 0.02
ATRASO_MAX_PERC = 0.30


# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------

def anonimizar_cpf(cpf_int: int) -> str:
    """Retorna um identificador irreversível derivado do CPF."""
    raw = f"CPF-{cpf_int:011d}".encode()
    digest = hashlib.sha256(raw).hexdigest()[:12].upper()
    return f"ANON-{digest}"


def gerar_cpf_unico(rng: np.random.Generator, n: int) -> list[str]:
    """Gera n CPFs anonimizados únicos."""
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
    """Sistema Price: parcela fixa, amortização crescente, juros decrescentes. PMT = PV * i / (1 - (1+i)^-n)."""
    if taxa == 0:
        return pv / prazo
    return pv * taxa / (1 - (1 + taxa) ** (-prazo))


def saldo_devedor(pv: float, taxa: float, prazo: int, meses_decorridos: int) -> float:
    """Saldo devedor pelo método Price após k parcelas pagas."""
    if meses_decorridos <= 0:
        return pv
    if meses_decorridos >= prazo:
        return 0.0
    pmt = calcular_parcela(pv, taxa, prazo)
    # PV futuro após k pagamentos
    fator = (1 + taxa) ** meses_decorridos
    return pv * fator - pmt * (fator - 1) / taxa


def data_aleatoria(rng: np.random.Generator, ini: date, fim: date) -> date:
    delta = (fim - ini).days
    return ini + timedelta(days=int(rng.integers(0, delta)))


# ---------------------------------------------------------------------------
# Gerador principal
# ---------------------------------------------------------------------------

def gerar_carteira(n: int = N_CONTRATOS, seed: int = SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    random.seed(seed)

    hoje = date(2026, 3, 30)  # data de referência fixa para reprodutibilidade

    # --- CPFs anonimizados únicos ---
    cpfs = gerar_cpf_unico(rng, n)

    # --- Características do contrato ---
    valores = rng.uniform(VALOR_MIN, VALOR_MAX, n).round(2)
    prazos = rng.choice(PRAZOS_MESES, size=n)
    taxas = rng.uniform(TAXA_MIN, TAXA_MAX, n).round(6)

    # --- Datas de início ---
    datas_inicio = [data_aleatoria(rng, DATA_INI_INICIO, DATA_FIM_INICIO) for _ in range(n)]

    # --- Status ---
    status_opcoes = list(STATUS_PESOS.keys())
    status_probs = list(STATUS_PESOS.values())
    status_list = rng.choice(status_opcoes, size=n, p=status_probs)

    # --- Construção linha a linha ---
    registros = []
    for i in range(n):
        pv = float(valores[i])
        taxa = float(taxas[i])
        prazo = int(prazos[i])
        dt_inicio = datas_inicio[i]
        status = str(status_list[i])

        # Meses decorridos desde o início
        meses_dec = (hoje.year - dt_inicio.year) * 12 + (hoje.month - dt_inicio.month)
        meses_dec = max(0, min(meses_dec, prazo))

        # Para contratos liquidados, forçar meses_dec == prazo
        if status == "liquidado":
            meses_dec = prazo

        # Parcela e saldo
        parcela = round(calcular_parcela(pv, taxa, prazo), 2)
        saldo = round(saldo_devedor(pv, taxa, prazo, meses_dec), 2)

        # Valor em atraso: apenas para inadimplentes
        if status == "inadimplente":
            perc_atraso = rng.uniform(ATRASO_MIN_PERC, ATRASO_MAX_PERC)
            valor_atraso = round(saldo * float(perc_atraso), 2)
            # Garantir ao menos 1 parcela em atraso
            valor_atraso = max(valor_atraso, parcela)
        else:
            valor_atraso = 0.0

        # Data de vencimento prevista (último dia do mês se necessário)
        total_months = dt_inicio.month + prazo
        vc_year = dt_inicio.year + (total_months - 1) // 12
        vc_month = (total_months - 1) % 12 + 1
        max_day = calendar.monthrange(vc_year, vc_month)[1]
        vc_day = min(dt_inicio.day, max_day)
        dt_vencimento = date(vc_year, vc_month, vc_day)

        registros.append(
            {
                "cpf_anonimizado": cpfs[i],
                "valor_contrato": pv,
                "prazo_meses": prazo,
                "taxa_juros_mensal": round(taxa * 100, 4),   # em %
                "taxa_juros_anual": round(((1 + taxa) ** 12 - 1) * 100, 4),  # em %
                "parcela_mensal": parcela,
                "data_inicio": dt_inicio.isoformat(),
                "data_vencimento": dt_vencimento.isoformat(),
                "meses_decorridos": meses_dec,
                "saldo_devedor": saldo,
                "status": status,
                "valor_em_atraso": valor_atraso,
            }
        )

    df = pd.DataFrame(registros)

    # Ordenar por data de início
    df.sort_values("data_inicio", inplace=True)
    df.reset_index(drop=True, inplace=True)

    return df


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os

    output_path = os.path.join(os.path.dirname(__file__), "portfolio_mock.csv")

    print(f"Gerando {N_CONTRATOS} contratos sintéticos...")
    df = gerar_carteira()

    df.to_csv(output_path, index=False, encoding="utf-8-sig", sep=";", decimal=",")
    print(f"Arquivo salvo em: {output_path}")

    # --- Resumo rápido ---
    print("\n=== Resumo da carteira ===")
    print(f"Total de contratos : {len(df):,}")
    print(f"Valor total        : R$ {df['valor_contrato'].sum():,.2f}")
    print(f"Saldo devedor total: R$ {df['saldo_devedor'].sum():,.2f}")
    print(f"Em atraso total    : R$ {df['valor_em_atraso'].sum():,.2f}")
    print("\nDistribuição por status:")
    print(df["status"].value_counts().to_string())
    print("\nEstatísticas de taxa (% a.m.):")
    print(df["taxa_juros_mensal"].describe().round(4).to_string())
