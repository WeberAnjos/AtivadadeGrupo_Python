from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from matplotlib.ticker import FuncFormatter

FONTE_URL = (
    "https://www.ipece.ce.gov.br/wp-content/uploads/sites/45/2025/08/"
    "ipece_informe_272_05_ago2025.pdf"
)
FONTE_TEXTO = "IBGE, Censo Demográfico 2022; IPECE, Informe nº 272/2025, Tabela 1"

COL_RENDA = "Rendimento médio mensal (R$)"
ROTULO_EIXO = "Rendimento médio mensal dos responsáveis com rendimento (R$)"
TOP_DESTAQUE = 5

COR_DESTAQUE = "#136D7A"
COR_BARRA = "#76A3B2"
COR_MEDIA = "#B24739"
COR_TEXTO = "#243648"
COR_FONTE = "#4F5864"

DADOS = [
    ("SC", "Florianópolis", 6173.62),
    ("ES", "Vitória", 5961.05),
    ("DF", "Brasília", 5784.31),
    ("PR", "Curitiba", 5394.90),
    ("RS", "Porto Alegre", 5383.55),
    ("SP", "São Paulo", 4961.95),
    ("MG", "Belo Horizonte", 4770.03),
    ("GO", "Goiânia", 4654.22),
    ("MT", "Cuiabá", 4524.06),
    ("RJ", "Rio de Janeiro", 4479.70),
    ("TO", "Palmas", 4165.72),
    ("PE", "Recife", 4112.89),
    ("MS", "Campo Grande", 3824.26),
    ("SE", "Aracaju", 3791.01),
    ("RN", "Natal", 3679.65),
    ("PB", "João Pessoa", 3544.10),
    ("PA", "Belém", 3302.83),
    ("RO", "Porto Velho", 3171.37),
    ("BA", "Salvador", 3160.73),
    ("AL", "Maceió", 3087.00),
    ("CE", "Fortaleza", 3084.07),
    ("RR", "Boa Vista", 3025.65),
    ("PI", "Teresina", 2982.66),
    ("AP", "Macapá", 2943.42),
    ("MA", "São Luís", 2912.05),
    ("AM", "Manaus", 2853.44),
    ("AC", "Rio Branco", 2754.43),
]


def reais(valor: float) -> str:
    arredondado = Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"R$ {arredondado:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def milhar(x: float, _pos=None) -> str:
    return f"{x:,.0f}".replace(",", ".")


def carregar_dados() -> pd.DataFrame:
    return pd.DataFrame(DADOS, columns=["UF", "Capital", COL_RENDA])


def calcular_estatisticas(df: pd.DataFrame) -> dict:
    serie = df[COL_RENDA]
    q1, q3 = serie.quantile([0.25, 0.75])
    iqr = q3 - q1
    lim_inf, lim_sup = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return {
        "media": float(serie.mean()),
        "mediana": float(serie.median()),
        "q1": float(q1),
        "q3": float(q3),
        "iqr": float(iqr),
        "limite_inferior": float(lim_inf),
        "limite_superior": float(lim_sup),
        "maior": df.loc[serie.idxmax()],
        "menor": df.loc[serie.idxmin()],
        "outliers": df[(serie < lim_inf) | (serie > lim_sup)],
    }


def aplicar_estilo():
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.titlesize": 14,
        "axes.labelsize": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "savefig.facecolor": "white",
    })


def grafico_capitais(df: pd.DataFrame, estat: dict):
    aplicar_estilo()
    ordenado = df.sort_values(COL_RENDA)
    valores = ordenado[COL_RENDA]
    destaque = set(df.nlargest(TOP_DESTAQUE, COL_RENDA)["UF"])
    cores = [COR_DESTAQUE if uf in destaque else COR_BARRA for uf in ordenado["UF"]]
    rotulos = ordenado["Capital"] + " (" + ordenado["UF"] + ")"

    fig, ax = plt.subplots(figsize=(12, 11))
    barras = ax.barh(rotulos, valores, color=cores, height=0.74, zorder=2)
    ax.axvline(estat["media"], color=COR_MEDIA, ls="--", lw=1.6, zorder=3,
               label=f"Média das {len(df)} capitais: {reais(estat['media'])}")

    margem = valores.max() * 0.01
    for barra, valor in zip(barras, valores):
        ax.text(valor + margem, barra.get_y() + barra.get_height() / 2, reais(valor),
                va="center", fontsize=8.5, color=COR_TEXTO, zorder=4,
                bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.5})

    ax.set_xlim(0, valores.max() * 1.2)
    ax.xaxis.set_major_formatter(FuncFormatter(milhar))
    ax.set_xlabel(ROTULO_EIXO)
    ax.set_title("Rendimento médio dos responsáveis por capital – 2022",
                 loc="left", weight="bold", pad=14)
    ax.grid(axis="x", color="#E4E9ED", linewidth=0.75, zorder=0)
    ax.tick_params(axis="y", length=0)
    ax.margins(y=0.01)
    ax.legend(loc="lower right", frameon=False, fontsize=9)
    fig.text(0.01, 0.01, f"Fonte: {FONTE_TEXTO}.", fontsize=8, color=COR_FONTE)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    return fig


def grafico_boxplot(df: pd.DataFrame, estat: dict):
    aplicar_estilo()
    valores = df[COL_RENDA].to_numpy()
    fig, ax = plt.subplots(figsize=(12, 4.2))
    ax.boxplot(
        valores, orientation="horizontal", widths=0.35, patch_artist=True, showmeans=True,
        boxprops={"facecolor": "#98CAD0", "edgecolor": "#206775", "linewidth": 1.5},
        medianprops={"color": COR_MEDIA, "linewidth": 2.3},
        whiskerprops={"color": "#206775", "linewidth": 1.4},
        capprops={"color": "#206775", "linewidth": 1.4},
        meanprops={"marker": "D", "markerfacecolor": "#183B5A",
                   "markeredgecolor": "white", "markersize": 8},
        flierprops={"marker": "o", "markerfacecolor": COR_MEDIA, "markeredgecolor": COR_MEDIA},
    )

    for _, linha in estat["outliers"].iterrows():
        ax.annotate(linha["UF"], (linha[COL_RENDA], 1), xytext=(0, 8),
                    textcoords="offset points", ha="center", fontsize=8, color=COR_MEDIA)

    for x, nome, cor in [(estat["q1"], "Q1", "#206775"),
                         (estat["mediana"], "Mediana", COR_MEDIA),
                         (estat["q3"], "Q3", "#206775")]:
        ax.text(x, 0.72, f"{nome}\n{reais(x)}", ha="center", va="top",
                fontsize=9, color=cor, fontweight="bold")
    ax.text(estat["media"], 1.25, f"Média: {reais(estat['media'])}",
            ha="center", va="bottom", fontsize=9, color="#183B5A")

    folga = (valores.max() - valores.min()) * 0.08
    ax.set_xlim(valores.min() - folga, valores.max() + folga)
    ax.set_ylim(0.45, 1.45)
    ax.set_yticks([])
    ax.grid(axis="x", alpha=0.25)
    ax.xaxis.set_major_formatter(FuncFormatter(milhar))
    ax.set_xlabel(ROTULO_EIXO)
    ax.set_title(f"Distribuição das médias entre as {len(df)} capitais",
                 loc="left", weight="bold", pad=12)
    fig.text(0.01, 0.01,
             f"IQR = {reais(estat['iqr'])}  |  Outliers (1,5 × IQR): {len(estat['outliers'])}"
             f"  |  Fonte: {FONTE_TEXTO}.", fontsize=8, color=COR_FONTE)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    return fig


def texto_interpretacao(df: pd.DataFrame, estat: dict) -> str:
    maior, menor = estat["maior"], estat["menor"]
    razao = f"{maior[COL_RENDA] / menor[COL_RENDA]:.2f}".replace(".", ",")
    if estat["media"] > estat["mediana"]:
        assimetria = "Média acima da mediana: as capitais de renda mais alta puxam a média para cima."
    elif estat["media"] < estat["mediana"]:
        assimetria = "Média abaixo da mediana: as capitais de renda mais baixa puxam a média para baixo."
    else:
        assimetria = "Média e mediana iguais: distribuição simétrica."

    outliers = estat["outliers"]
    if outliers.empty:
        texto_outliers = "Nenhuma capital fica fora do intervalo de 1,5 × IQR."
    else:
        nomes = ", ".join(outliers["Capital"])
        texto_outliers = f"Outliers pelo critério de 1,5 × IQR: {nomes}."

    return (
        f"- Maior rendimento: **{maior['Capital']} ({maior['UF']})**, {reais(maior[COL_RENDA])}.\n"
        f"- Menor rendimento: **{menor['Capital']} ({menor['UF']})**, {reais(menor[COL_RENDA])}.\n"
        f"- A maior média é {razao} vezes a menor.\n"
        f"- {assimetria}\n"
        f"- IQR de {reais(estat['iqr'])}, faixa que concentra a metade central das capitais.\n"
        f"- {texto_outliers}"
    )


def mostrar_figura(fig):
    st.pyplot(fig, clear_figure=True)
    plt.close(fig)


def pagina_rendimento():
    df = carregar_dados()
    estat = calcular_estatisticas(df)

    st.header("5. Rendimento dos responsáveis pelo domicílio")
    st.caption(f"Censo Demográfico 2022 (IBGE) · {len(df)} capitais brasileiras")
    st.markdown(
        "Rendimento médio mensal das pessoas responsáveis por domicílios, "
        "considerando apenas responsáveis com rendimento, por capital."
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Média", reais(estat["media"]))
    c2.metric("Mediana", reais(estat["mediana"]))
    c3.metric("Q1 (25%)", reais(estat["q1"]))
    c4.metric("Q3 (75%)", reais(estat["q3"]))
    c5.metric("IQR", reais(estat["iqr"]))

    st.subheader("Comparação por capital")
    mostrar_figura(grafico_capitais(df, estat))

    st.subheader("Distribuição e outliers")
    mostrar_figura(grafico_boxplot(df, estat))

    st.subheader("Resultados")
    st.markdown(texto_interpretacao(df, estat))
    st.caption(
        "Os quartis e outliers referem-se às médias das capitais, não à distribuição "
        "de renda das pessoas. Responsáveis sem rendimento não entram no cálculo."
    )

    with st.expander("Tabela completa"):
        tabela = df.sort_values(COL_RENDA, ascending=False).reset_index(drop=True)
        tabela.index += 1
        tabela[COL_RENDA] = tabela[COL_RENDA].map(reais)
        st.dataframe(tabela, width="stretch")
        st.download_button("Baixar CSV", df.to_csv(index=False, sep=";", decimal=","),
                           "rendimento_capitais_2022.csv", "text/csv")

    st.markdown(f"Fonte: [{FONTE_TEXTO}]({FONTE_URL})")


if __name__ == "__main__":
    st.set_page_config(page_title="Rendimento dos responsáveis – Censo 2022", layout="wide")
    pagina_rendimento()
