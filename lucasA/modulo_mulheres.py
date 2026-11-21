from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

TABELA = 9514
SIDRA_URL = "https://apisidra.ibge.gov.br/values"
AGREGADOS_URL = "https://servicodados.ibge.gov.br/api/v3/agregados"
ARQUIVO_CACHE = Path(__file__).resolve().parent / "data" / "populacao_sexo_2022.csv"
FONTE = f"IBGE, Censo Demográfico 2022 (SIDRA, tabela {TABELA})"

UF = {
    "11": ("RO", "Norte"), "12": ("AC", "Norte"), "13": ("AM", "Norte"), "14": ("RR", "Norte"),
    "15": ("PA", "Norte"), "16": ("AP", "Norte"), "17": ("TO", "Norte"),
    "21": ("MA", "Nordeste"), "22": ("PI", "Nordeste"), "23": ("CE", "Nordeste"),
    "24": ("RN", "Nordeste"), "25": ("PB", "Nordeste"), "26": ("PE", "Nordeste"),
    "27": ("AL", "Nordeste"), "28": ("SE", "Nordeste"), "29": ("BA", "Nordeste"),
    "31": ("MG", "Sudeste"), "32": ("ES", "Sudeste"), "33": ("RJ", "Sudeste"), "35": ("SP", "Sudeste"),
    "41": ("PR", "Sul"), "42": ("SC", "Sul"), "43": ("RS", "Sul"),
    "50": ("MS", "Centro-Oeste"), "51": ("MT", "Centro-Oeste"), "52": ("GO", "Centro-Oeste"),
    "53": ("DF", "Centro-Oeste"),
}

INDICADORES = {
    "% de mulheres": ("pct_mulheres", "% de mulheres na população"),
    "Razão de sexo": ("razao_sexo", "Homens para cada 100 mulheres"),
}


def get_json(url: str):
    resposta = requests.get(url, timeout=60)
    resposta.raise_for_status()
    return resposta.json()


def id_por_nome(itens: list[dict], termo: str):
    return next(i["id"] for i in itens if termo in i["nome"].lower())


def consulta_sidra(nivel: str) -> pd.DataFrame:
    meta = get_json(f"{AGREGADOS_URL}/{TABELA}/metadados")
    variavel = id_por_nome(meta["variaveis"], "população residente")
    sexo = id_por_nome(meta["classificacoes"], "sexo")
    linhas = get_json(f"{SIDRA_URL}/t/{TABELA}/{nivel}/v/{variavel}/p/last/c{sexo}/all")
    cabecalho, dados = linhas[0], pd.DataFrame(linhas[1:])
    col_sexo = next(k for k, v in cabecalho.items()
                    if k.endswith("N") and "sexo" in v.lower() and "código" not in v.lower())
    return pd.DataFrame({
        "cod": dados["D1C"],
        "territorio": dados["D1N"],
        "sexo": dados[col_sexo],
        "pessoas": pd.to_numeric(dados["V"], errors="coerce"),
    })


def baixar_dados() -> pd.DataFrame:
    df = pd.concat([consulta_sidra("n1/all"), consulta_sidra("n3/all")], ignore_index=True)
    ARQUIVO_CACHE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ARQUIVO_CACHE, index=False)
    return df


@st.cache_data(show_spinner="Carregando dados do IBGE")
def carregar_dados() -> pd.DataFrame:
    if ARQUIVO_CACHE.exists():
        df = pd.read_csv(ARQUIVO_CACHE, dtype={"cod": str})
    else:
        df = baixar_dados()
    return montar_indicadores(df)


def montar_indicadores(df: pd.DataFrame) -> pd.DataFrame:
    tabela = df.pivot_table(index=["cod", "territorio"], columns="sexo",
                            values="pessoas", aggfunc="sum").reset_index()
    tabela.columns.name = None
    tabela = tabela.rename(columns={"Homens": "homens", "Mulheres": "mulheres", "Total": "total"})
    if "total" not in tabela:
        tabela["total"] = tabela["homens"] + tabela["mulheres"]
    tabela["pct_mulheres"] = tabela["mulheres"] / tabela["total"] * 100
    tabela["razao_sexo"] = tabela["homens"] / tabela["mulheres"] * 100
    tabela["sigla"] = tabela["cod"].map(lambda c: UF.get(c, ("BR", ""))[0])
    tabela["regiao"] = tabela["cod"].map(lambda c: UF.get(c, ("", "Brasil"))[1])
    return tabela


def estatisticas(serie: pd.Series) -> dict:
    q1, mediana, q3 = serie.quantile([0.25, 0.5, 0.75])
    iqr = q3 - q1
    desvio = serie.std(ddof=1)
    return {
        "n": len(serie), "media": serie.mean(), "mediana": mediana,
        "q1": q1, "q3": q3, "iqr": iqr,
        "minimo": serie.min(), "maximo": serie.max(), "amplitude": serie.max() - serie.min(),
        "desvio": desvio, "cv": desvio / serie.mean() * 100,
        "lim_inf": q1 - 1.5 * iqr, "lim_sup": q3 + 1.5 * iqr,
    }


def num(valor: float, casas: int = 2) -> str:
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def interpretacao(ufs: pd.DataFrame, col: str, e: dict, rotulo: str) -> list[str]:
    maior = ufs.loc[ufs[col].idxmax()]
    menor = ufs.loc[ufs[col].idxmin()]
    linhas = [
        f"Maior valor: **{maior['territorio']}** ({num(maior[col])}). "
        f"Menor valor: **{menor['territorio']}** ({num(menor[col])}).",
    ]
    diferenca = e["media"] - e["mediana"]
    if abs(diferenca) < 0.05 * e["desvio"]:
        linhas.append("Média e mediana praticamente iguais: distribuição aproximadamente simétrica.")
    elif diferenca > 0:
        linhas.append("Média acima da mediana: as UFs com valores altos puxam a média para cima.")
    else:
        linhas.append("Média abaixo da mediana: as UFs com valores baixos puxam a média para baixo.")
    linhas.append(f"Coeficiente de variação de {num(e['cv'])}%: "
                  + ("baixa dispersão entre as UFs." if e["cv"] < 15 else "dispersão relevante entre as UFs."))
    if col == "razao_sexo":
        acima = ufs[ufs[col] > 100]["sigla"].tolist()
        linhas.append("UFs com mais homens que mulheres: " + (", ".join(acima) if acima else "nenhuma") + ".")
    else:
        abaixo = ufs[ufs[col] < 50]["sigla"].tolist()
        linhas.append("UFs com menos de 50% de mulheres: " + (", ".join(abaixo) if abaixo else "nenhuma") + ".")
    return linhas


def render():
    st.header("Mulheres na população residente")
    st.caption(f"Fonte: {FONTE}")

    try:
        dados = carregar_dados()
    except (requests.RequestException, ValueError, KeyError, StopIteration):
        st.error("Não foi possível obter os dados do SIDRA/IBGE. Verifique a conexão e recarregue a página.")
        return

    with st.sidebar:
        st.subheader("Filtros")
        nome_indicador = st.radio("Indicador", list(INDICADORES), key="mu_indicador")
        regioes = sorted(dados.loc[dados["regiao"] != "Brasil", "regiao"].unique())
        sel_regioes = st.multiselect("Região", regioes, default=regioes, key="mu_regioes")
        destacar = st.checkbox("Destacar outliers", value=True, key="mu_outliers")

    col, rotulo = INDICADORES[nome_indicador]
    brasil = dados[dados["regiao"] == "Brasil"]
    ufs = dados[dados["regiao"].isin(sel_regioes)].reset_index(drop=True)
    if len(ufs) < 4:
        st.warning("Selecione regiões que somem pelo menos 4 UFs.")
        return

    e = estatisticas(ufs[col])
    ufs["outlier"] = (ufs[col] < e["lim_inf"]) | (ufs[col] > e["lim_sup"])
    valor_brasil = brasil[col].iloc[0] if not brasil.empty else None

    k = st.columns(5)
    k[0].metric("Brasil", num(valor_brasil) if valor_brasil is not None else "-")
    k[1].metric("Média das UFs", num(e["media"]))
    k[2].metric("Mediana", num(e["mediana"]))
    k[3].metric("Desvio padrão", num(e["desvio"]))
    k[4].metric("Outliers", int(ufs["outlier"].sum()))

    aba_ranking, aba_dist, aba_estat, aba_out, aba_dados = st.tabs(
        ["Ranking", "Distribuição", "Estatísticas", "Outliers", "Dados"])

    with aba_ranking:
        ordem = ufs.sort_values(col, ascending=False).copy()
        ordem["classe"] = ordem["outlier"].map({True: "Outlier", False: "Dentro do padrão"})
        fig = px.bar(ordem, x="sigla", y=col, color="classe" if destacar else "regiao",
                     hover_name="territorio",
                     color_discrete_map={"Outlier": "#dc2626", "Dentro do padrão": "#6366f1"},
                     category_orders={"sigla": ordem["sigla"].tolist()},
                     labels={col: rotulo, "sigla": "UF", "regiao": "Região", "classe": ""})
        if valor_brasil is not None:
            fig.add_hline(y=valor_brasil, line_dash="dash", annotation_text="Brasil")
        if col == "razao_sexo":
            fig.add_hline(y=100, line_dash="dot", line_color="gray", annotation_text="Equilíbrio")
        margem = (ordem[col].max() - ordem[col].min()) * 0.3
        fig.update_yaxes(range=[ordem[col].min() - margem, ordem[col].max() + margem])
        fig.update_layout(separators=",.")
        st.plotly_chart(fig, width="stretch")

    with aba_dist:
        c1, c2 = st.columns(2)
        box = px.box(ufs, y=col, points="all", hover_name="territorio", labels={col: rotulo})
        box.update_layout(separators=",.")
        c1.plotly_chart(box, width="stretch")
        hist = px.histogram(ufs, x=col, nbins=10, labels={col: rotulo, "count": "UFs"})
        hist.update_layout(separators=",.", yaxis_title="Número de UFs")
        c2.plotly_chart(hist, width="stretch")
        box_reg = px.box(ufs, x="regiao", y=col, points="all", hover_name="territorio",
                         labels={col: rotulo, "regiao": "Região"})
        box_reg.update_layout(separators=",.")
        st.plotly_chart(box_reg, width="stretch")

    with aba_estat:
        tabela = pd.DataFrame({
            "Medida": ["UFs", "Média", "Mediana", "Q1", "Q3", "IQR", "Mínimo", "Máximo",
                       "Amplitude", "Desvio padrão", "Coeficiente de variação (%)"],
            "Valor": [str(e["n"])] + [num(e[c]) for c in
                      ("media", "mediana", "q1", "q3", "iqr", "minimo", "maximo",
                       "amplitude", "desvio", "cv")],
        })
        st.dataframe(tabela, hide_index=True, width="stretch")
        for linha in interpretacao(ufs, col, e, rotulo):
            st.markdown(f"- {linha}")

    with aba_out:
        st.markdown(f"Critério 1,5 × IQR: limite inferior **{num(e['lim_inf'])}**, "
                    f"limite superior **{num(e['lim_sup'])}**.")
        outliers = ufs[ufs["outlier"]]
        if outliers.empty:
            st.success("Nenhum outlier nas UFs selecionadas.")
        else:
            st.dataframe(outliers[["territorio", "regiao", col]]
                         .rename(columns={"territorio": "UF", "regiao": "Região", col: rotulo}),
                         hide_index=True, width="stretch")
            media_sem = ufs.loc[~ufs["outlier"], col].mean()
            st.markdown(f"Média com outliers: **{num(e['media'])}** · sem outliers: "
                        f"**{num(media_sem)}** (diferença de {num(e['media'] - media_sem)}).")

    with aba_dados:
        exibicao = ufs.sort_values(col, ascending=False)[
            ["territorio", "sigla", "regiao", "mulheres", "homens", "total", "pct_mulheres", "razao_sexo"]
        ].rename(columns={"territorio": "UF", "sigla": "Sigla", "regiao": "Região",
                          "mulheres": "Mulheres", "homens": "Homens", "total": "Total",
                          "pct_mulheres": "% mulheres", "razao_sexo": "Razão de sexo"})
        st.dataframe(exibicao, hide_index=True, width="stretch",
                     column_config={c: st.column_config.NumberColumn(format="%.2f")
                                    for c in ("% mulheres", "Razão de sexo")})
        st.download_button("Baixar CSV", exibicao.to_csv(index=False, sep=";", decimal=","),
                           "mulheres_uf_2022.csv", "text/csv")


if __name__ == "__main__":
    st.set_page_config(page_title="Mulheres – Censo 2022", layout="wide")
    render()
