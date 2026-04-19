import pandas as pd
import streamlit as st

from config.settings import CONTRATOS_MOCK_PATH, EVOLUCAO_MOCK_PATH


@st.cache_data
def load_data() -> dict:
    """Lê os CSVs da carteira sintética v2 e retorna dicionário com dois DataFrames.

    Chaves:
        "contratos"  — atributos estáticos por contrato (taxa, prazo, valor, datas)
        "evolucao"   — snapshot mensal por contrato (saldo, status_mes, atraso, pcld)

    Separador ';', decimal ',', datas convertidas para datetime.
    Toda leitura de dados passa por aqui — nunca instanciar pd.read_csv fora desta função.
    """
    contratos = pd.read_csv(CONTRATOS_MOCK_PATH, sep=";", decimal=",", encoding="utf-8-sig")
    contratos["data_inicio"] = pd.to_datetime(contratos["data_inicio"])
    contratos["data_vencimento"] = pd.to_datetime(contratos["data_vencimento"])

    evolucao = pd.read_csv(EVOLUCAO_MOCK_PATH, sep=";", decimal=",", encoding="utf-8-sig")

    return {"contratos": contratos, "evolucao": evolucao}
