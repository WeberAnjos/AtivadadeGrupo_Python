from __future__ import annotations

import pandas as pd


def calcular_estatisticas(serie: pd.Series) -> dict:
    serie = serie.dropna()
    if serie.empty:
        return {}
    q1, mediana, q3 = serie.quantile([0.25, 0.5, 0.75])
    iqr = q3 - q1
    limite_inferior = q1 - 1.5 * iqr
    limite_superior = q3 + 1.5 * iqr
    return {
        "n": len(serie),
        "media": float(serie.mean()),
        "mediana": float(mediana),
        "q1": float(q1),
        "q3": float(q3),
        "iqr": float(iqr),
        "minimo": float(serie.min()),
        "maximo": float(serie.max()),
        "amplitude": float(serie.max() - serie.min()),
        "desvio_padrao": float(serie.std(ddof=1)) if len(serie) > 1 else 0.0,
        "limite_inferior": float(limite_inferior),
        "limite_superior": float(limite_superior),
        "outliers": (serie < limite_inferior) | (serie > limite_superior),
    }
