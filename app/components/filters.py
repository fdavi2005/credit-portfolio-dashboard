import pandas as pd
import streamlit as st

from config.constants import STATUS_VALIDOS


def get_status_filter(key: str = "filter_status") -> list[str]:
    """Multiselect de status. Retorna lista de status selecionados."""
    return st.multiselect(
        "Status",
        options=STATUS_VALIDOS,
        default=STATUS_VALIDOS,
        key=key,
    )


def get_prazo_filter(df: pd.DataFrame, key: str = "filter_prazo") -> list[int]:
    """Multiselect de prazos disponíveis no dataset. Retorna lista de prazos selecionados."""
    prazos = sorted(df["prazo_meses"].unique().tolist())
    return st.multiselect(
        "Prazo (meses)",
        options=prazos,
        default=prazos,
        key=key,
    )
