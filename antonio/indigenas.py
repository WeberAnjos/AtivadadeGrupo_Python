from __future__ import annotations

import io

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

SIDRA_URL = "https://apisidra.ibge.gov.br/values"
AGREGADOS_URL = "https://servicodados.ibge.gov.br/api/v3/agregados"
MALHA_UF_URL = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
    "?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=UF"
)
TABELA_UF = 9970
TABELA_MUNICIPIOS = 9718
TIMEOUT = 60
CACHE_TTL = 24 * 3600

CAPITAIS = {
    "Curitiba": "4106902",
    "Porto Alegre": "4314902",
    "Belo Horizonte": "3106200",
    "Salvador": "2927408",
    "Florianópolis": "4205407",
}

REGIOES = {"1": "Norte", "2": "Nordeste", "3": "Sudeste", "4": "Sul", "5": "Centro-Oeste"}

UF_SIGLA = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
    "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP",
    "41": "PR", "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF",
}

TOTAIS_BRASIL = pd.DataFrame(
    [
        {"ano": 2010, "situacao": "Urbana", "pessoas": 324_834},
        {"ano": 2010, "situacao": "Rural", "pessoas": 572_083},
        {"ano": 2022, "situacao": "Urbana", "pessoas": 914_746},
        {"ano": 2022, "situacao": "Rural", "pessoas": 780_090},
    ]
).assign(cod="1", nome="Brasil", uf="BR", regiao="Brasil")

SITUACOES = ["Urbana", "Rural"]
CORES = {"Urbana": "#2563eb", "Rural": "#16a34a"}
COLUNAS_UPLOAD = ["cod", "nome", "ano", "situacao", "pessoas"]


def get_json(url: str):
    resposta = requests.get(url, timeout=TIMEOUT)
    resposta.raise_for_status()
    return resposta.json()


def parametros_sidra(metadados: dict) -> str:
    variaveis = metadados.get("variaveis", [])
    indigenas = [v for v in variaveis if "indígena" in v.get("nome", "").lower()
                 and str(v.get("unidade", "")).lower() == "pessoas"]
    pessoas = [v for v in variaveis if str(v.get("unidade", "")).lower() == "pessoas"]
    escolhida = (indigenas or pessoas or [None])[0]
    filtro = f"/v/{escolhida['id']}" if escolhida else "/v/all"
    filtro += "/p/all"
    for classificacao in metadados.get("classificacoes", []):
        if "situação do domicílio" in classificacao.get("nome", "").lower():
            filtro += f"/c{classificacao['id']}/all"
    return filtro


def url_sidra(tabela: int, nivel: str) -> str:
    try:
        filtro = parametros_sidra(get_json(f"{AGREGADOS_URL}/{tabela}/metadados"))
    except (requests.RequestException, ValueError):
        filtro = "/v/all/p/all"
    return f"{SIDRA_URL}/t/{tabela}/{nivel}{filtro}"


def sidra_para_df(linhas: list[dict]) -> pd.DataFrame:
    if not linhas or len(linhas) < 2:
        return pd.DataFrame()
    df = pd.DataFrame(linhas[1:]).rename(columns=linhas[0])
    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce")
    return df


def normaliza(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=COLUNAS_UPLOAD)

    colunas = set(df.columns)
    col_cod = next((c for c in ("Município (Código)", "Unidade da Federação (Código)")
                    if c in colunas), None)
    col_nome = next((c for c in ("Município", "Unidade da Federação") if c in colunas), None)

    if "Variável" in colunas:
        variavel = df["Variável"].str.lower()
        so_indigenas = variavel.str.contains("indígena", na=False) & \
            ~variavel.str.contains("%|percentual|proporção", na=False)
        if so_indigenas.any():
            df = df[so_indigenas]
        elif "Unidade de Medida" in colunas:
            df = df[df["Unidade de Medida"].str.lower() == "pessoas"]

    saida = pd.DataFrame({
        "cod": df[col_cod].astype(str) if col_cod else "1",
        "nome": df[col_nome] if col_nome else "Brasil",
        "ano": pd.to_numeric(df["Ano"], errors="coerce") if "Ano" in colunas else pd.NA,
        "situacao": df["Situação do domicílio"] if "Situação do domicílio" in colunas else "Total",
        "pessoas": df["Valor"],
    })
    return saida.dropna(subset=["pessoas", "ano"]).astype({"ano": int}).reset_index(drop=True)


def com_territorio(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["cod"] = df["cod"].astype(str).str.replace(r"\.0$", "", regex=True)
    df["uf"] = df["cod"].str[:2].map(UF_SIGLA)
    df["regiao"] = df["cod"].str[:1].map(REGIOES)
    return df


def carrega_sidra(tabela: int, nivel: str) -> pd.DataFrame:
    return com_territorio(normaliza(sidra_para_df(get_json(url_sidra(tabela, nivel)))))


def le_upload(arquivo) -> pd.DataFrame:
    if arquivo.name.lower().endswith(".csv"):
        df = pd.read_csv(arquivo, sep=None, engine="python")
    else:
        df = pd.read_excel(arquivo)
    df.columns = [str(c).strip().lower() for c in df.columns]
    faltando = [c for c in COLUNAS_UPLOAD if c not in df.columns]
    if faltando:
        raise ValueError(f"Colunas ausentes no arquivo: {', '.join(faltando)}")
    df = df[COLUNAS_UPLOAD].copy()
    df["ano"] = pd.to_numeric(df["ano"], errors="coerce")
    df["pessoas"] = pd.to_numeric(df["pessoas"], errors="coerce")
    df["situacao"] = df["situacao"].astype(str).str.strip().str.capitalize()
    df = df.dropna(subset=["ano", "pessoas"]).astype({"ano": int})
    return com_territorio(df)


def tem_quebra_por_uf(df: pd.DataFrame) -> bool:
    return (not df.empty and df["uf"].notna().any()
            and df["situacao"].isin(SITUACOES).any())


def tabela_larga(df: pd.DataFrame, chave: list[str]) -> pd.DataFrame:
    larga = df.pivot_table(index=chave + ["ano"], columns="situacao",
                           values="pessoas", aggfunc="sum").reset_index()
    larga.columns.name = None
    for col in SITUACOES:
        if col not in larga:
            larga[col] = float("nan")
    if "Total" not in larga:
        larga["Total"] = larga[SITUACOES].sum(axis=1, min_count=1)
    larga["pct_urbana"] = larga["Urbana"] / larga["Total"] * 100
    return larga


def variacao_pct(atual: float, anterior: float) -> float | None:
    if not anterior or pd.isna(anterior) or pd.isna(atual):
        return None
    return (atual / anterior - 1) * 100


def outliers_iqr(serie: pd.Series) -> pd.Series:
    q1, q3 = serie.quantile([0.25, 0.75])
    iqr = q3 - q1
    return (serie < q1 - 1.5 * iqr) | (serie > q3 + 1.5 * iqr)


def fmt_int(n) -> str:
    return f"{n:,.0f}".replace(",", ".") if pd.notna(n) else "-"


def fmt_pct(n, sinal: bool = False) -> str:
    if n is None or pd.isna(n):
        return "-"
    return (f"{n:+.1f}%" if sinal else f"{n:.1f}%").replace(".", ",")


@st.cache_data(ttl=CACHE_TTL, show_spinner="Carregando dados do SIDRA/IBGE")
def dados_uf() -> pd.DataFrame:
    return carrega_sidra(TABELA_UF, "n3/all")


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def dados_capitais() -> pd.DataFrame:
    return carrega_sidra(TABELA_MUNICIPIOS, "n6/" + ",".join(CAPITAIS.values()))


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def malha_uf() -> dict:
    return get_json(MALHA_UF_URL)


def ajusta_layout(fig):
    fig.update_layout(separators=",.", legend_title_text="", margin=dict(t=30, b=10),
                      yaxis_tickformat=",.0f")
    return fig


def obtem_dados(arquivo) -> tuple[pd.DataFrame, str]:
    if arquivo is not None:
        try:
            return le_upload(arquivo), f"Arquivo importado: {arquivo.name}"
        except (ValueError, KeyError) as erro:
            st.sidebar.error(str(erro))

    try:
        df = dados_uf()
    except (requests.RequestException, ValueError, KeyError):
        df = pd.DataFrame()

    if tem_quebra_por_uf(df):
        return df, f"IBGE, Censo Demográfico 2010/2022 (SIDRA, tabela {TABELA_UF})"

    st.warning("Dados por UF indisponíveis no SIDRA. Exibindo totais nacionais do Censo 2010/2022.")
    return TOTAIS_BRASIL.copy(), "IBGE, Censo Demográfico 2010/2022 (totais nacionais)"


def secao_kpis(atual: pd.DataFrame, anterior: pd.DataFrame, ano: int, ano_base: int):
    total = atual["Total"].sum(min_count=1)
    urbana = atual["Urbana"].sum(min_count=1)
    rural = atual["Rural"].sum(min_count=1)
    variacao = variacao_pct(total, anterior["Total"].sum(min_count=1)) if ano != ano_base else None

    k1, k2, k3, k4 = st.columns(4)
    k1.metric(f"Pessoas indígenas ({ano})", fmt_int(total))
    k2.metric("Situação urbana", fmt_pct(urbana / total * 100) if total else "-")
    k3.metric("Situação rural", fmt_pct(rural / total * 100) if total else "-")
    k4.metric(f"Variação {ano_base}–{ano}", fmt_pct(variacao, sinal=True))


def secao_evolucao(base: pd.DataFrame, situacoes: list[str]):
    st.subheader("Evolução por situação do domicílio")
    evolucao = (base[base["situacao"].isin(situacoes)]
                .groupby(["ano", "situacao"], as_index=False)["pessoas"].sum())
    if evolucao.empty:
        st.info("Sem dados para a situação selecionada.")
        return
    evolucao["ano"] = evolucao["ano"].astype(str)
    fig = px.bar(evolucao, x="ano", y="pessoas", color="situacao", barmode="group",
                 text_auto=",.0f", color_discrete_map=CORES,
                 category_orders={"situacao": SITUACOES},
                 labels={"pessoas": "Pessoas", "ano": "Censo", "situacao": "Situação"})
    st.plotly_chart(ajusta_layout(fig), width="stretch")


def secao_por_uf(atual: pd.DataFrame, situacoes: list[str], ano: int):
    st.subheader(f"Distribuição por UF ({ano})")
    longa = atual.melt(id_vars=["uf"], value_vars=situacoes,
                       var_name="situacao", value_name="pessoas")
    ordem = atual.sort_values("Total", ascending=False)["uf"].tolist()
    fig = px.bar(longa, x="uf", y="pessoas", color="situacao", color_discrete_map=CORES,
                 category_orders={"uf": ordem, "situacao": SITUACOES},
                 labels={"uf": "UF", "pessoas": "Pessoas", "situacao": "Situação"})
    st.plotly_chart(ajusta_layout(fig), width="stretch")


def secao_mapa(atual: pd.DataFrame):
    st.subheader("Mapa por UF")
    metrica = st.radio("Métrica", ["Total de pessoas indígenas", "% em situação urbana"],
                       horizontal=True, key="ind_metrica")
    coluna = "Total" if metrica.startswith("Total") else "pct_urbana"
    try:
        geojson = malha_uf()
    except (requests.RequestException, ValueError):
        st.info("Malha territorial do IBGE indisponível.")
        return
    mapa = atual.assign(uf_cod=atual["cod"].str[:2])
    fig = px.choropleth(mapa, geojson=geojson, locations="uf_cod", color=coluna,
                        featureidkey="properties.codarea", hover_name="uf",
                        color_continuous_scale="YlOrBr", labels={coluna: metrica})
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_coloraxes(colorbar_tickformat=",.0f")
    st.plotly_chart(ajusta_layout(fig), width="stretch")


def secao_outliers(atual: pd.DataFrame, anterior: pd.DataFrame, ano: int, ano_base: int):
    st.subheader(f"Crescimento por UF ({ano_base}–{ano})")
    if ano == ano_base:
        st.caption(f"Comparação disponível apenas para anos posteriores a {ano_base}.")
        return
    cresc = atual[["uf", "nome", "Total"]].merge(
        anterior[["uf", "Total"]], on="uf", suffixes=("", "_base"))
    cresc["crescimento"] = (cresc["Total"] / cresc["Total_base"] - 1) * 100
    cresc["outlier"] = outliers_iqr(cresc["crescimento"]).map({True: "Sim", False: ""})
    cresc = cresc.sort_values("crescimento", ascending=False)
    tabela = pd.DataFrame({
        "UF": cresc["uf"],
        "Nome": cresc["nome"],
        str(ano_base): cresc["Total_base"].map(fmt_int),
        str(ano): cresc["Total"].map(fmt_int),
        "Crescimento": cresc["crescimento"].map(lambda v: fmt_pct(v, sinal=True)),
        "Outlier": cresc["outlier"],
    })
    st.dataframe(tabela, width="stretch", hide_index=True)
    st.caption("Outlier: valor fora do intervalo Q1 − 1,5·IQR a Q3 + 1,5·IQR. "
               "Parte do aumento em 2022 decorre de mudanças na captação e na autodeclaração.")


def secao_capitais(ano: int):
    st.subheader("Capitais")
    try:
        mun = dados_capitais()
    except (requests.RequestException, ValueError, KeyError):
        mun = pd.DataFrame()
    if mun.empty:
        st.info(f"Dados municipais indisponíveis (SIDRA, tabela {TABELA_MUNICIPIOS}).")
        return
    capitais = tabela_larga(mun, ["nome"])
    capitais = capitais[capitais["ano"] == ano]
    if capitais.empty:
        st.info(f"Sem dados municipais para {ano}.")
        return
    tabela = pd.DataFrame({"Município": capitais["nome"], "Total": capitais["Total"].map(fmt_int)})
    if capitais[SITUACOES].notna().any().any():
        tabela["Urbana"] = capitais["Urbana"].map(fmt_int)
        tabela["Rural"] = capitais["Rural"].map(fmt_int)
        tabela["% urbana"] = capitais["pct_urbana"].map(fmt_pct)
    st.dataframe(tabela, width="stretch", hide_index=True)


def render_indigenas():
    st.header("Pessoas indígenas por situação do domicílio")

    filtros = st.sidebar.container()
    with st.sidebar.expander("Fonte de dados"):
        arquivo = st.file_uploader("Importar tabela (CSV ou XLSX)", type=["csv", "xlsx"],
                                   key="ind_upload",
                                   help="Colunas: " + ", ".join(COLUNAS_UPLOAD))

    df, fonte = obtem_dados(arquivo)
    st.caption(f"Fonte: {fonte}")

    anos = sorted(df["ano"].unique().tolist())
    ano_base = anos[0]
    with filtros:
        st.subheader("Filtros")
        ano = st.selectbox("Ano do Censo", anos, index=len(anos) - 1, key="ind_ano")
        regioes = sorted(df["regiao"].dropna().unique())
        sel_regioes = st.multiselect("Região", regioes, default=regioes, key="ind_reg")
        ufs = sorted(df.loc[df["regiao"].isin(sel_regioes), "uf"].dropna().unique())
        sel_ufs = st.multiselect("UF", ufs, default=ufs, key="ind_uf")
        sel_situacoes = st.multiselect("Situação do domicílio", SITUACOES,
                                       default=SITUACOES, key="ind_sit")

    base = df[df["regiao"].isin(sel_regioes) & df["uf"].isin(sel_ufs)]
    if base.empty:
        st.info("Nenhum registro para os filtros selecionados.")
        return

    larga = tabela_larga(base, ["uf", "nome", "cod"])
    atual = larga[larga["ano"] == ano]
    anterior = larga[larga["ano"] == ano_base]

    secao_kpis(atual, anterior, ano, ano_base)
    secao_evolucao(base, sel_situacoes)

    if tem_quebra_por_uf(base) and base["uf"].nunique() > 1:
        if sel_situacoes:
            secao_por_uf(atual, sel_situacoes, ano)
        secao_mapa(atual)
        secao_outliers(atual, anterior, ano, ano_base)

    secao_capitais(ano)

    csv = io.StringIO()
    base.to_csv(csv, index=False)
    st.download_button("Baixar dados filtrados (CSV)", csv.getvalue(),
                       "indigenas_situacao_domicilio.csv", "text/csv")


if __name__ == "__main__":
    st.set_page_config(page_title="Pessoas indígenas – IBGE", layout="wide")
    render_indigenas()
