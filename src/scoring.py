"""Score compuesto por estudio y mapeo a confianza para el frontend."""
import pandas as pd

# Score bi-encoder (shortlist previo al reranker).
W_INCLUSION = 1.0
W_EXCLUSION = 0.5

# Score final compuesto: reranker (Score General) + geo + "pasa exclusiones".
W_RERANK = 0.6
W_GEO    = 0.2
W_EXCL   = 0.2  # premia que el paciente NO matchee criterios de exclusion


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


def confidence_for(score: float) -> str:
    """Mapea un score 0-1 a la confianza ('high'|'mid'|'low') que espera la UI."""
    if score >= 0.75:
        return 'high'
    if score >= 0.5:
        return 'mid'
    return 'low'
