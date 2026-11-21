from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

TABELA = 9543
SIDRA_URL = "https://apisidra.ibge.gov.br/values"
AGREGADOS_URL = "https://servicodados.ibge.gov.br/api/v3/agregados"
ARQUIVO_CACHE = Path(__file__).resolve().parent.parent / "data" / "alfabetizacao_2022.csv"
FONTE = f"IBGE, Censo Demográfico 2022 (SIDRA, tabela {TABELA})"
NIVEIS = {"n1": "Brasil", "n2": "Região", "n3": "UF"}

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


def get_json(url: str):
    resposta = requests.get(url, timeout=60)
    resposta.raise_for_status()
    return resposta.json()


def id_por_nome(itens: list[dict], termo: str):
    return next(i["id"] for i in itens if termo in i["nome"].lower())


def coluna_sidra(cabecalho: dict, termo: str) -> str:
    return next(k for k, v in cabecalho.items()
                if k.endswith("N") and termo in v.lower() and "código" not in v.lower())


def consulta_sidra(nivel: str) -> pd.DataFrame:
    meta = get_json(f"{AGREGADOS_URL}/{TABELA}/metadados")
    variavel = id_por_nome(meta["variaveis"], "taxa de alfabetização")
    sexo = id_por_nome(meta["classificacoes"], "sexo")
    raca = id_por_nome(meta["classificacoes"], "cor ou raça")
    url = f"{SIDRA_URL}/t/{TABELA}/{nivel}/all/v/{variavel}/p/last/c{sexo}/all/c{raca}/all"
    linhas = get_json(url)
    cabecalho, dados = linhas[0], pd.DataFrame(linhas[1:])
    return pd.DataFrame({
        "nivel": NIVEIS[nivel],
        "cod": dados["D1C"],
        "territorio": dados["D1N"],
        "sexo": dados[coluna_sidra(cabecalho, "sexo")],
        "raca": dados[coluna_sidra(cabecalho, "cor ou raça")],
        "taxa": pd.to_numeric(dados["V"], errors="coerce"),
    })


def baixar_dados() -> pd.DataFrame:
    df = pd.concat([consulta_sidra(n) for n in NIVEIS], ignore_index=True)
    ARQUIVO_CACHE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ARQUIVO_CACHE, index=False)
    return df


def carregar_dados() -> pd.DataFrame:
    if ARQUIVO_CACHE.exists():
        df = pd.read_csv(ARQUIVO_CACHE, dtype={"cod": str})
    else:
        df = baixar_dados()
    df = df.dropna(subset=["taxa"]).copy()
    df["sigla"] = df["cod"].map(lambda c: UF.get(c, (None, None))[0])
    df["regiao"] = df["cod"].map(lambda c: UF.get(c, (None, None))[1])
    df.loc[df["nivel"] != "UF", ["sigla", "regiao"]] = None
    return df
