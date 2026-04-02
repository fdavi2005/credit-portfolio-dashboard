import pandas as pd
import streamlit as st

from config.settings import DATA_MOCK_PATH


@st.cache_data
def load_data() -> pd.DataFrame:
    """Lê o CSV da carteira sintética e retorna DataFrame normalizado.

    Separador ';', decimal ',', datas convertidas para datetime.
    Toda leitura de dados passa por aqui — nunca instanciar pd.read_csv fora desta função.
    """
    df = pd.read_csv(DATA_MOCK_PATH, sep=";", decimal=",", encoding="utf-8-sig")
    df["data_inicio"] = pd.to_datetime(df["data_inicio"])
    df["data_vencimento"] = pd.to_datetime(df["data_vencimento"])
    return df
