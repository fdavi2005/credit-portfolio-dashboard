# CLAUDE.md — Credit Portfolio Intelligence Dashboard

Contexto completo do projeto para o assistente de IA. Leia antes de qualquer tarefa.

---

## O que é o projeto

Dashboard analítico de carteira de crédito **consignado pré-fixado**, construído em Python com Streamlit. O objetivo é dar visibilidade a KPIs operacionais e de risco (saldo devedor, inadimplência, distribuição de taxas, concentração de prazos) e oferecer um simulador de contrato para uso interno.

Os dados em produção serão substituídos por dados reais; por enquanto, toda a interface consome o arquivo sintético gerado em `data/mock/generate_portfolio.py`.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Framework web | Streamlit (multi-page) |
| Gráficos | Plotly Express / Plotly Graph Objects (via `st.plotly_chart`) |
| Dados | pandas + NumPy |
| Linguagem | Python 3.12+ |
| Geração de mock | script puro (`generate_portfolio.py`) |
| Formato de dados | CSV com separador `;` e decimal `,` (padrão pt-BR) |

Dependências declaradas em `requirements.txt`. Não adicionar dependências sem atualizar esse arquivo.

---

## Estrutura de pastas

```
credit-portfolio-dashboard/
├── app/
│   ├── main.py                  # entrypoint do Streamlit (st.set_page_config, navegação raiz)
│   ├── pages/
│   │   ├── visao_geral.py       # página inicial: KPIs macro da carteira
│   │   ├── carteira.py          # análise de contratos: prazo, taxa, concentração
│   │   ├── inadimplencia.py     # aging, NPL, evolução de default
│   │   └── simulador.py         # simulador de parcela / custo efetivo
│   ├── components/
│   │   ├── charts.py            # funções que retornam figuras Plotly reutilizáveis
│   │   ├── filters.py           # componentes de filtro (st.selectbox, st.date_input, etc.)
│   │   └── kpi_cards.py         # cards de métricas com st.metric / st.columns
│   └── utils/
│       ├── calculations.py      # cálculos financeiros (Price, saldo devedor, CET, etc.)
│       ├── data_loader.py       # leitura e cache do CSV com @st.cache_data; nunca fazer pd.read_csv fora daqui
│       └── formatters.py        # formatação de moeda (R$), percentual, datas pt-BR
├── config/
│   ├── constants.py             # constantes de negócio (limites de taxa, status válidos, etc.)
│   └── settings.py              # configurações de ambiente (caminhos, debug flag)
├── data/
│   ├── mock/
│   │   ├── generate_portfolio.py  # gerador de dados sintéticos (seed=42, 2.000 contratos)
│   │   └── portfolio_mock.csv     # CSV gerado — NÃO commitar versões modificadas manualmente
│   ├── raw/                       # dados brutos de produção — NUNCA commitar
│   └── processed/                 # dados transformados — NUNCA commitar
├── assets/
│   └── images/                  # logos e imagens estáticas
├── docs/                        # documentação adicional (opcional)
├── tests/                       # testes unitários (pytest)
├── .env.example                 # template de variáveis de ambiente (sem valores reais)
├── .gitignore
├── requirements.txt
└── CLAUDE.md
```

---

## Convenções de código

### Geral
- **Português para domínio, inglês para infraestrutura**: nomes de variáveis de negócio em português (`saldo_devedor`, `taxa_juros_mensal`, `inadimplente`), nomes de funções utilitárias e estruturas de código em inglês (`load_data`, `format_currency`, `get_filter_options`).
- Snake_case em tudo (variáveis, funções, arquivos).
- Sem type annotations obrigatórias — adicionar apenas onde a lógica não é autoexplicativa.
- Sem docstrings em funções triviais; adicionar apenas em cálculos financeiros e funções públicas das utils.

### Streamlit / páginas
- Cada arquivo em `app/pages/` é uma página Streamlit autônoma. O nome do arquivo determina o item no menu lateral (Streamlit native multi-page).
- Lógica de renderização de cada página fica no próprio arquivo. Funções de UI reutilizáveis (cards, filtros, gráficos) são extraídas para `app/components/`.
- Usar `@st.cache_data` em toda função que lê ou transforma dados para evitar reprocessamento desnecessário a cada interação.
- Evitar `st.session_state` para dados derivados; preferir recomputação via cache.
- Widgets de filtro são criados via funções em `app/components/filters.py` que retornam os valores selecionados — não inline nas páginas.

### Dados
- Todo acesso ao CSV passa por `app/utils/data_loader.py`. Nunca instanciar `pd.read_csv` diretamente em página ou componente.
- O CSV usa separador `;` e decimal `,` — sempre ler com `sep=";"` e `decimal=","`.
- A coluna `taxa_juros_mensal` está em **percentual** (ex.: `1.8500` = 1,85% a.m.). Converter para decimal (`/ 100`) antes de qualquer cálculo matemático.
- Datas são strings ISO 8601 (`YYYY-MM-DD`); converter com `pd.to_datetime` ao carregar.

### Cálculos financeiros
- Toda lógica de cálculo financeiro fica em `app/utils/calculations.py`.
- Usar **sistema Price** (parcela fixa): `PMT = PV × i / (1 − (1+i)^−n)`.
- Saldo devedor após `k` períodos: `PV × (1+i)^k − PMT × ((1+i)^k − 1) / i`.
- Nunca arredondar valores intermediários; arredondar apenas na apresentação (`round(x, 2)`).

---

## Regras de negócio — Consignado Pré-fixado

### Produto
- Modalidade de crédito com desconto em folha de pagamento (consignado).
- Taxa de juros **pré-fixada**: definida na contratação, não varia durante o contrato.
- Amortização pelo **sistema Price**: parcelas mensais iguais, compostas de juros decrescentes + amortização crescente.

### Parâmetros de mercado (referência do gerador sintético)
| Parâmetro | Valor |
|---|---|
| Prazos disponíveis (meses) | 12, 24, 36, 48, 60, 72, 84, 96 |
| Valor mínimo do contrato | R$ 1.000,00 |
| Valor máximo do contrato | R$ 150.000,00 |
| Taxa mínima (a.m.) | 1,40% |
| Taxa máxima (a.m.) | 2,40% |
| Taxa anual equivalente | `(1 + i_mensal)^12 − 1` |

### Status de contrato
| Status | Descrição |
|---|---|
| `ativo` | Contrato em dia, parcelas sendo pagas (~70% da carteira) |
| `inadimplente` | Contrato com valor em atraso (>0); atraso entre 2% e 30% do saldo devedor, com piso de 1 parcela (~10%) |
| `liquidado` | Contrato totalmente quitado; saldo devedor = 0 (~20%) |

### Campos do dataset
| Coluna | Tipo | Descrição |
|---|---|---|
| `cpf_anonimizado` | string | Identificador irreversível (SHA-256 truncado), nunca o CPF real |
| `valor_contrato` | float | Valor originado (PV) em R$ |
| `prazo_meses` | int | Prazo total do contrato |
| `taxa_juros_mensal` | float | Taxa mensal em % (ex.: 1.85 = 1,85% a.m.) |
| `taxa_juros_anual` | float | Taxa anual equivalente em % |
| `parcela_mensal` | float | PMT calculado pelo sistema Price, em R$ |
| `data_inicio` | date string | Data de contratação (ISO 8601) |
| `data_vencimento` | date string | Data do último vencimento (ISO 8601) |
| `meses_decorridos` | int | Meses desde a contratação até a data de referência |
| `saldo_devedor` | float | Saldo devedor estimado na data de referência, em R$ |
| `status` | string | `ativo` / `inadimplente` / `liquidado` |
| `valor_em_atraso` | float | Valor inadimplido em R$ (0 para não-inadimplentes) |

### KPIs principais
- **Saldo total da carteira**: `sum(saldo_devedor)` onde `status != 'liquidado'`
- **NPL (Non-Performing Loan)**: `sum(valor_em_atraso) / sum(saldo_devedor)` × 100
- **Taxa média ponderada**: média de `taxa_juros_mensal` ponderada por `saldo_devedor`
- **Prazo médio ponderado**: média de `(prazo_meses - meses_decorridos)` ponderada por `saldo_devedor`
- **Ticket médio**: `mean(valor_contrato)` da carteira ativa

---

## O que NUNCA deve ser commitado

```
# Dados reais ou sensíveis
data/raw/
data/processed/
*.csv           # exceto data/mock/portfolio_mock.csv gerado pelo script
*.xlsx
*.parquet
*.db

# Credenciais e ambiente
.env
.env.local
.env.*.local
config/secrets.py
*_credentials.*
*_key.*
*.pem
*.p12
*.pfx

# CPFs, nomes ou qualquer dado pessoal real (mesmo anonimizado incorretamente)
# Jamais commitar arquivos de exportação com dados de clientes reais

# Cache e artefatos locais
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.mypy_cache/
*.egg-info/
dist/
build/

# IDEs
.vscode/settings.json   # apenas settings pessoais; .vscode/extensions.json pode
.idea/
*.swp

# OS
.DS_Store
Thumbs.db
```

**Regra geral**: qualquer arquivo que contenha dados reais de clientes (CPF, nome, renda, dados bancários) — mesmo anonimizados por método caseiro — **jamais** vai para o repositório. Dados sintéticos gerados pelo script com seed fixo são aceitáveis.

---

## Data de referência

O gerador usa `date(2026, 3, 30)` como data de referência fixa para garantir reprodutibilidade. Ao implementar filtros temporais no dashboard, considerar essa data como "hoje" ao trabalhar com o mock.
