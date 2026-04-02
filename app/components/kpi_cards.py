import streamlit as st


def render_kpi_row(kpis: list[dict]) -> None:
    """Renderiza uma linha de cards de métricas.

    Cada item de `kpis` é um dict com chaves:
      - label  (str)  — obrigatório
      - value  (str)  — obrigatório
      - delta  (str)  — opcional
      - help   (str)  — opcional
    """
    cols = st.columns(len(kpis))
    for col, kpi in zip(cols, kpis):
        with col:
            st.metric(
                label=kpi["label"],
                value=kpi["value"],
                delta=kpi.get("delta"),
                help=kpi.get("help"),
            )
