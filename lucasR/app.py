import pandas as pd
import plotly.express as px
import requests
import streamlit as st

from src.data_loader import FONTE, carregar_dados
from src.stats import calcular_estatisticas

CORES_REGIAO = {
    "Norte": "#16a34a", "Nordeste": "#ea580c", "Sudeste": "#2563eb",
    "Sul": "#7c3aed", "Centro-Oeste": "#ca8a04",
}
ORDEM_RACA = ["Branca", "Preta", "Amarela", "Parda", "Indígena"]
ROTULO_TAXA = "Taxa de alfabetização (%)"


def pct(valor: float) -> str:
    return f"{valor:.2f}%".replace(".", ",")


def pp(valor: float) -> str:
    return f"{valor:.2f}".replace(".", ",") + " p.p."


@st.cache_data(show_spinner="Carregando dados do IBGE")
def dados() -> pd.DataFrame:
    return carregar_dados()


def opcoes(serie: pd.Series, ordem: list[str]) -> list[str]:
    valores = set(serie) - {"Total"}
    return ["Total"] + [v for v in ordem if v in valores] + sorted(valores - set(ordem))


def grafico_ranking(ufs: pd.DataFrame, valor_brasil):
    ordem = ufs.sort_values("taxa", ascending=False)
    fig = px.bar(ordem, x="sigla", y="taxa", color="regiao", hover_name="territorio",
                 color_discrete_map=CORES_REGIAO,
                 category_orders={"sigla": ordem["sigla"].tolist(), "regiao": list(CORES_REGIAO)},
                 labels={"taxa": ROTULO_TAXA, "sigla": "UF", "regiao": "Região"})
    if valor_brasil is not None:
        fig.add_hline(y=valor_brasil, line_dash="dash", annotation_text="Brasil")
    minimo = ordem["taxa"].min()
    fig.update_yaxes(range=[max(minimo - 5, 0), 100])
    fig.update_layout(separators=",.", legend_title_text="")
    return fig


def grafico_boxplot(ufs: pd.DataFrame):
    fig = px.box(ufs, x="regiao", y="taxa", color="regiao", points="all", hover_name="territorio",
                 color_discrete_map=CORES_REGIAO,
                 labels={"taxa": ROTULO_TAXA, "regiao": "Região"})
    fig.update_layout(separators=",.", showlegend=False)
    return fig


def grafico_raca_sexo(brasil: pd.DataFrame):
    base = brasil[brasil["raca"] != "Total"]
    fig = px.bar(base, x="raca", y="taxa", color="sexo", barmode="group", text_auto=".1f",
                 category_orders={"raca": ORDEM_RACA, "sexo": ["Total", "Homens", "Mulheres"]},
                 labels={"taxa": ROTULO_TAXA, "raca": "Cor ou raça", "sexo": "Sexo"})
    fig.update_yaxes(range=[max(base["taxa"].min() - 10, 0), 100])
    fig.update_layout(separators=",.", legend_title_text="")
    return fig


def leitura_dos_dados(brasil: pd.DataFrame, regioes: pd.DataFrame, sexo: str, raca: str) -> list[str]:
    linhas = []
    por_raca = brasil[(brasil["sexo"] == sexo) & (brasil["raca"] != "Total")]
    if len(por_raca) > 1:
        alta = por_raca.loc[por_raca["taxa"].idxmax()]
        baixa = por_raca.loc[por_raca["taxa"].idxmin()]
        linhas.append(f"No Brasil, a maior taxa é da população {alta['raca'].lower()} "
                      f"({pct(alta['taxa'])}) e a menor, da população {baixa['raca'].lower()} "
                      f"({pct(baixa['taxa'])}): diferença de {pp(alta['taxa'] - baixa['taxa'])}.")
    por_sexo = brasil[(brasil["raca"] == raca) & (brasil["sexo"].isin(["Homens", "Mulheres"]))]
    if len(por_sexo) == 2:
        h = por_sexo.loc[por_sexo["sexo"] == "Homens", "taxa"].iloc[0]
        m = por_sexo.loc[por_sexo["sexo"] == "Mulheres", "taxa"].iloc[0]
        grupo = "" if raca == "Total" else f" (cor ou raça {raca.lower()})"
        linhas.append(f"Homens{grupo}: {pct(h)}; mulheres: {pct(m)}. "
                      f"Diferença de {pp(abs(m - h))} a favor "
                      f"{'das mulheres' if m > h else 'dos homens'}.")
    reg = regioes[(regioes["sexo"] == sexo) & (regioes["raca"] == raca)]
    if len(reg) > 1:
        alta = reg.loc[reg["taxa"].idxmax()]
        baixa = reg.loc[reg["taxa"].idxmin()]
        linhas.append(f"Entre as regiões, {alta['territorio']} tem a maior taxa ({pct(alta['taxa'])}) "
                      f"e {baixa['territorio']} a menor ({pct(baixa['taxa'])}).")
    return linhas


def analise_matematica(stats: dict, outliers: pd.DataFrame) -> list[str]:
    diferenca = stats["media"] - stats["mediana"]
    if abs(diferenca) < 0.1:
        forma = "Média e mediana praticamente iguais: distribuição aproximadamente simétrica."
    elif diferenca < 0:
        forma = ("Média abaixo da mediana: as UFs com taxas mais baixas puxam a média para baixo, "
                 "então a mediana representa melhor o centro da distribuição.")
    else:
        forma = ("Média acima da mediana: as UFs com taxas mais altas puxam a média para cima, "
                 "então a mediana representa melhor o centro da distribuição.")
    texto_out = ("Nenhuma UF fora do intervalo de 1,5 × IQR." if outliers.empty else
                 "Outliers (1,5 × IQR): " + ", ".join(
                     f"{r.territorio} ({pct(r.taxa)})" for r in outliers.itertuples()) + ".")
    return [
        f"Média {pct(stats['media'])} e mediana {pct(stats['mediana'])}. {forma}",
        f"IQR de {pp(stats['iqr'])}: a metade central das UFs está entre "
        f"{pct(stats['q1'])} e {pct(stats['q3'])}.",
        f"Desvio padrão de {pp(stats['desvio_padrao'])} e amplitude de {pp(stats['amplitude'])}.",
        texto_out,
    ]


st.set_page_config(page_title="Alfabetização por sexo e cor ou raça – Censo 2022", layout="wide")
st.title("Taxa de alfabetização por sexo e cor ou raça")
st.caption(f"Pessoas de 15 anos ou mais · Fonte: {FONTE} · "
           "Projeto Integrador: Números que Falam – Tema 2")

try:
    df = dados()
except (requests.RequestException, ValueError, KeyError, StopIteration):
    st.error("Não foi possível obter os dados do SIDRA/IBGE. Verifique a conexão e recarregue a página.")
    st.stop()

ufs_todas = df[df["nivel"] == "UF"]
brasil = df[df["nivel"] == "Brasil"]
regioes_df = df[df["nivel"] == "Região"]

st.sidebar.header("Filtros")
sexo = st.sidebar.selectbox("Sexo", opcoes(df["sexo"], ["Homens", "Mulheres"]))
raca = st.sidebar.selectbox("Cor ou raça", opcoes(df["raca"], ORDEM_RACA))
lista_regioes = list(CORES_REGIAO)
sel_regioes = st.sidebar.multiselect("Região", lista_regioes, default=lista_regioes)

ufs = ufs_todas[(ufs_todas["sexo"] == sexo) & (ufs_todas["raca"] == raca)
                & ufs_todas["regiao"].isin(sel_regioes)].reset_index(drop=True)

if len(ufs) < 4:
    st.warning("Os filtros deixaram menos de 4 UFs. Amplie a seleção de regiões.")
    st.stop()

stats = calcular_estatisticas(ufs["taxa"])
outliers = ufs[stats["outliers"].values]
linha_brasil = brasil[(brasil["sexo"] == sexo) & (brasil["raca"] == raca)]
valor_brasil = linha_brasil["taxa"].iloc[0] if not linha_brasil.empty else None

st.subheader("Medidas estatísticas entre as UFs")
c = st.columns(4)
c[0].metric("Brasil", pct(valor_brasil) if valor_brasil is not None else "-")
c[1].metric("Média", pct(stats["media"]))
c[2].metric("Mediana", pct(stats["mediana"]))
c[3].metric("Outliers", len(outliers))
c = st.columns(4)
c[0].metric("Q1", pct(stats["q1"]))
c[1].metric("Q3", pct(stats["q3"]))
c[2].metric("IQR", pp(stats["iqr"]))
c[3].metric("Desvio padrão", pp(stats["desvio_padrao"]))
st.caption(f"Amplitude: {pp(stats['amplitude'])} "
           f"(de {pct(stats['minimo'])} a {pct(stats['maximo'])}) · {stats['n']} UFs")

st.subheader("Ranking por UF")
st.plotly_chart(grafico_ranking(ufs, valor_brasil), width="stretch")

g1, g2 = st.columns(2)
with g1:
    st.subheader("Distribuição por região")
    st.plotly_chart(grafico_boxplot(ufs), width="stretch")
with g2:
    st.subheader("Brasil: cor ou raça e sexo")
    st.plotly_chart(grafico_raca_sexo(brasil), width="stretch")

st.subheader("Interpretação")
col_mat, col_soc = st.columns(2)
with col_mat:
    st.markdown("**Análise matemática** (EM13MAT316, EM13MAT104)")
    for linha in analise_matematica(stats, outliers):
        st.markdown(f"- {linha}")
with col_soc:
    st.markdown("**Leitura socioeconômica** (EM13CHS402)")
    for linha in leitura_dos_dados(brasil, regioes_df, sexo, raca):
        st.markdown(f"- {linha}")

with st.expander("Dados das UFs"):
    tabela = (ufs.sort_values("taxa", ascending=False)
              [["territorio", "sigla", "regiao", "taxa"]]
              .rename(columns={"territorio": "UF", "sigla": "Sigla", "regiao": "Região",
                               "taxa": ROTULO_TAXA}))
    tabela["Outlier"] = tabela["UF"].isin(outliers["territorio"]).map({True: "Sim", False: ""})
    st.dataframe(tabela, hide_index=True, width="stretch",
                 column_config={ROTULO_TAXA: st.column_config.NumberColumn(format="%.2f")})
    st.download_button("Baixar CSV", tabela.to_csv(index=False, sep=";", decimal=","),
                       "alfabetizacao_uf_2022.csv", "text/csv")
