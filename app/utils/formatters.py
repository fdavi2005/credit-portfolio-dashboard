def format_currency(value: float) -> str:
    """Formata valor como moeda brasileira: R$ 1.234.567,89"""
    formatted = f"{value:,.2f}"
    # trocar separadores: vírgula → ponto de milhar, ponto → vírgula decimal
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def format_percent(value: float, decimals: int = 2) -> str:
    """Formata valor como percentual: 1,85%"""
    return f"{value:.{decimals}f}%".replace(".", ",")


def format_number(value: float) -> str:
    """Formata inteiro com separador de milhar pt-BR: 2.000"""
    return f"{value:,.0f}".replace(",", ".")


def format_months(value: float) -> str:
    """Formata prazo em meses: 24 meses"""
    return f"{value:.1f} meses".replace(".", ",")
