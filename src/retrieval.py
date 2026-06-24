"""Funciones puras de retrieval semantico contra los embeddings de estudios."""
import numpy as np
import pandas as pd

# Estados de reclutamiento que se consideran "abiertos" para el matching.
ACTIVE_STATUSES = {'RECRUITING', 'NOT_YET_RECRUITING'}


def parse_min_age(min_age) -> int:
    """Extrae anios de min_age ('18 Years' -> 18); sin minimo -> 0."""
    if not isinstance(min_age, str):
        return 0
    return int(min_age.split()[0])


def age_bucket(age: int) -> str:
    """Mapea edad al bucket std_ages de ClinicalTrials."""
    if age < 18:
        return 'CHILD'
    if age < 65:
        return 'ADULT'
    return 'OLDER_ADULT'


def filter_studies(clinical_df: pd.DataFrame, age: int) -> set:
    """nct_ids con status abierto (recruiting / not yet) y edad compatible."""
    bucket = age_bucket(age)
    eligible = clinical_df[
        (clinical_df['overall_status'].isin(ACTIVE_STATUSES))
        & (clinical_df['min_age'].map(parse_min_age) <= age)
        & (clinical_df['std_ages'].map(lambda b: b is None or bucket in b))
    ]
    return set(eligible['nct_id'])


def condition_candidates(
    query_emb: np.ndarray,
    condition_meta: pd.DataFrame,
    condition_emb: np.ndarray,
    eligible_ids: set,
    top_n: int,
) -> list:
    """Top-N estudios por similitud de condicion, restringido a los elegibles."""
    mask = condition_meta['nct_id'].isin(eligible_ids).to_numpy()
    sims = np.asarray(condition_emb[mask]) @ query_emb
    ids  = condition_meta.loc[mask, 'nct_id'].to_numpy()
    top_idx = np.argsort(-sims)[:top_n]
    return ids[top_idx].tolist()


def score_criteria(
    query_emb: np.ndarray,
    meta: pd.DataFrame,
    emb: np.ndarray,
    candidate_ids: list,
    top_k: int,
) -> dict:
    """Score por estudio = promedio de las top_k similitudes de criterio (0 si no tiene)."""
    mask = meta['nct_id'].isin(set(candidate_ids)).to_numpy()
    sub_ids = meta.loc[mask, 'nct_id'].to_numpy()
    sims = np.asarray(emb[mask]) @ query_emb
    scored = {}
    for nct_id, group in pd.Series(sims, index=sub_ids).groupby(level=0):
        top = np.sort(group.to_numpy())[::-1][:top_k]
        scored[nct_id] = float(top.mean())
    return scored


def top_criteria(
    query_emb: np.ndarray,
    meta: pd.DataFrame,
    emb: np.ndarray,
    nct_id: str,
    k: int,
) -> list:
    """Top-k criterios mas similares de un estudio (texto), para rerank y explicacion."""
    mask  = (meta['nct_id'] == nct_id).to_numpy()
    texts = meta.loc[mask, 'criterion_text'].to_numpy()
    sims  = np.asarray(emb[mask]) @ query_emb
    order = np.argsort(-sims)[:k]
    return texts[order].tolist()
