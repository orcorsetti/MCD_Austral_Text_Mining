"""Score compuesto por estudio y mapeo a confianza para el frontend."""
import numpy as np
import pandas as pd

# Score bi-encoder (shortlist previo al reranker).
W_INCLUSION = 1.0
W_EXCLUSION = 0.5

# v1 - Score final compuesto: reranker (Score General) + geo + "pasa exclusiones".
W_RERANK = 0.6
W_GEO    = 0.2
W_EXCL   = 0.2  # premia que el paciente NO matchee criterios de exclusion

# v2 - Score final con gate por enfermedad: reranker + inclusion + exclusion + geo.
W2_DISEASE   = 0.50
W2_INCLUSION = 0.25
W2_EXCL      = 0.15
W2_GEO       = 0.10


def composite_score(
    inclusion_scores: dict,
    exclusion_scores: dict,
    candidate_ids: list,
) -> pd.DataFrame:
    """Combina inclusion (+) y exclusion (-) en un score final por estudio candidato."""
    rows = []
    for nct_id in candidate_ids:
        inc = inclusion_scores.get(nct_id, 0.0)
        exc = exclusion_scores.get(nct_id, 0.0)
        rows.append({
            'nct_id': nct_id,
            'inclusion_score': inc,
            'exclusion_penalty': exc,
            'final_score': W_INCLUSION * inc - W_EXCLUSION * exc,
        })
    return (
        pd.DataFrame(rows)
        .sort_values('final_score', ascending=False)
        .reset_index(drop=True)
    )


def geo_score(countries: list, patient_country: str) -> float:
    """Score geografico 0-1: sitio en el pais del paciente -> 1.0; en otro lado -> 0.3."""
    if not patient_country:
        return 0.5                       # sin pais declarado: neutro
    if patient_country in countries:
        return 1.0
    return 0.3 if countries else 0.0     # recluta, pero no en su pais


def final_score(reranker: float, geo: float, exclusion_pass: float) -> float:
    """Combina Score General (reranker), geo y 'pasa exclusiones' (0-1) en el score final."""
    return W_RERANK * reranker + W_GEO * geo + W_EXCL * exclusion_pass


def exclusion_pass(values: list) -> list:
    """1 - exclusion normalizada; estudios SIN exclusion (NaN) -> NEUTRAL 0.5 (no premio gratis)."""
    arr = np.array(values, dtype=float)
    present = arr[~np.isnan(arr)]
    if len(present) < 2:
        return [0.5] * len(arr)
    lo, hi = present.min(), present.max()
    return [0.5 if np.isnan(v) else 1.0 - (v - lo) / (hi - lo) for v in arr]


def final_score_v2(disease: float, inclusion: float, exclusion_pass: float, geo: float) -> float:
    """Score final v2 (post gate por enfermedad): reranker + inclusion + exclusion + geo."""
    return W2_DISEASE * disease + W2_INCLUSION * inclusion + W2_EXCL * exclusion_pass + W2_GEO * geo


def confidence_for(score: float) -> str:
    """Mapea un score 0-1 a la confianza ('high'|'mid'|'low') que espera la UI."""
    if score >= 0.75:
        return 'high'
    if score >= 0.5:
        return 'mid'
    return 'low'
