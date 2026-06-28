"""Motor de matching: carga modelos + embeddings + metadata una vez y resuelve consultas.

Pipeline online: filtros -> prefiltro de condicion -> score bi-encoder -> rerank
cross-encoder -> score geografico -> composite ponderado -> explicacion LLM.
Devuelve directamente el shape MatchResult que consume el frontend trial-matcher.
"""
import os
import threading
from pathlib import Path

import numpy as np
import pandas as pd

from .embeddings import EmbeddingModel
from .llm_generation import explain_trials
from .profile import (
    Patient, build_condition_query, build_criteria_query, build_rerank_query,
    disease_keywords, patient_summary, requested_phase_tokens,
)
from .rerank import CrossEncoderReranker
from .retrieval import condition_candidates, filter_studies, score_criteria, top_criteria
from .scoring import composite_score, confidence_for, exclusion_pass, final_score, final_score_v2, geo_score

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'

CRITERIA_MODEL_NAME  = 'pritamdeka/S-PubMedBert-MS-MARCO'  # 768 dims -> criterios
CONDITION_MODEL_NAME = 'BAAI/bge-small-en-v1.5'            # 384 dims -> condicion

CONDITION_TOP_N      = 200  # candidatos tras el filtro semantico de condicion
INCLUSION_TOP_K      = 3    # criterios promediados por estudio (score bi-encoder)
MIN_INCLUSION_CRITERIA = 3  # descarta estudios muy genericos (pocos criterios de inclusion)
RERANK_POOL          = 50   # estudios que pasan al cross-encoder
RESULT_TOP_N         = 10   # estudios devueltos (default)
MAX_RESULT_TOP_N     = 50   # tope para el parametro top_n del request
EXPLAIN_INCLUSION_K  = 3    # criterios de inclusion citados al LLM
EXPLAIN_EXCLUSION_K  = 2    # criterios de exclusion citados al LLM
MAX_DISPLAY_CRITERIA = 4    # criterios mostrados por tarjeta

LLM_EXPLANATIONS = os.environ.get('LLM_EXPLANATIONS', '1') != '0'


def _minmax(values: list) -> list:
    """Normaliza scores a 0-1 dentro del shortlist (todos iguales o vacio -> 1.0)."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi == lo:
        return [1.0] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


class TrialMatcherEngine:
    """Carga el indice una sola vez y matchea perfiles de paciente a ensayos."""

    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        self.clinical_df    = pd.read_parquet(data_dir / '05_clinical_trials_normalized.parquet')
        self.eligibility_df = pd.read_parquet(data_dir / '05_eligibility_normalized.parquet').set_index('nct_id')
        self.metadata_df    = pd.read_parquet(data_dir / '05_trial_metadata.parquet').set_index('nct_id')

        self.inclusion_meta = pd.read_parquet(data_dir / '06_inclusion_meta.parquet')
        self.exclusion_meta = pd.read_parquet(data_dir / '06_exclusion_meta.parquet')
        self.condition_meta = pd.read_parquet(data_dir / '06_condition_meta.parquet')

        self.inclusion_emb = np.load(data_dir / '06_inclusion_embeddings.npy', mmap_mode='r')
        self.exclusion_emb = np.load(data_dir / '06_exclusion_embeddings.npy', mmap_mode='r')
        self.condition_emb = np.load(data_dir / '06_condition_embeddings.npy')

        self.condition_text = dict(zip(self.condition_meta['nct_id'], self.condition_meta['condition_text']))

        # Blob de enfermedad por estudio (condition_text + titulo, lowercased) para el gate v2.
        titles = self.metadata_df['brief_title'].to_dict()
        self.disease_blob = {
            n: (str(ct) + ' ' + str(titles.get(n, ''))).lower()
            for n, ct in self.condition_text.items()
        }

        # Estudios con suficientes criterios de inclusion (descarta los muy genericos).
        inc_counts = self.inclusion_meta.groupby('nct_id').size()
        self.studies_min_criteria = set(inc_counts[inc_counts >= MIN_INCLUSION_CRITERIA].index)

        # Fases por estudio (para el filtro de fase del formulario).
        self.study_phases = {n: set(p) for n, p in self.metadata_df['phases'].items()}

        self.criteria_model  = EmbeddingModel(CRITERIA_MODEL_NAME)
        self.condition_model = EmbeddingModel(CONDITION_MODEL_NAME)
        self.reranker        = CrossEncoderReranker()
        self._lock = threading.Lock()  # serializa el acceso a GPU entre requests

    def match(self, patient: Patient, missing: list = None, variant: str = 'v2', top_n: int = RESULT_TOP_N) -> dict:
        """Pipeline online completo. variant 'v1' = original; 'v2' = gate por enfermedad + MedCPT."""
        top_n = max(1, min(int(top_n), MAX_RESULT_TOP_N))
        with self._lock:
            return self._match_v2(patient, top_n) if variant == 'v2' else self._match(patient, top_n)

    def _match(self, patient: Patient, top_n: int) -> dict:
        cond_q = self.condition_model.encode([build_condition_query(patient)])[0]
        crit_q = self.criteria_model.encode([build_criteria_query(patient)])[0]

        eligible_ids  = filter_studies(self.clinical_df, patient.age) & self.studies_min_criteria
        eligible_ids  = self._phase_filter(eligible_ids, patient)
        candidate_ids = condition_candidates(
            cond_q, self.condition_meta, self.condition_emb, eligible_ids, CONDITION_TOP_N
        )

        inclusion_scores = score_criteria(crit_q, self.inclusion_meta, self.inclusion_emb, candidate_ids, INCLUSION_TOP_K)
        exclusion_scores = score_criteria(crit_q, self.exclusion_meta, self.exclusion_emb, candidate_ids, INCLUSION_TOP_K)

        shortlist_ids = composite_score(inclusion_scores, exclusion_scores, candidate_ids).head(max(RERANK_POOL, top_n))['nct_id'].tolist()
        ranked = self._rerank(shortlist_ids, build_rerank_query(patient), crit_q, patient.country, exclusion_scores, top_n)

        # La explicacion LLM se genera por separado (POST /api/explain) para no bloquear la busqueda.
        trials = [self._to_trial_match(row, patient.country) for _, row in ranked.iterrows()]
        return {'totalCount': len(eligible_ids), 'trials': trials}

    def _rerank_doc(self, nct_id: str, crit_q: np.ndarray) -> str:
        """Documento del estudio para el cross-encoder: titulo + condicion + top criterios de inclusion."""
        title = self.metadata_df.loc[nct_id, 'brief_title'] or ''
        inc = top_criteria(crit_q, self.inclusion_meta, self.inclusion_emb, nct_id, EXPLAIN_INCLUSION_K)
        return f"{title}. {self.condition_text.get(nct_id, '')} {' '.join(inc)}"[:1500]

    def _rerank(self, shortlist_ids: list, rerank_query: str, crit_q: np.ndarray,
                country: str, exclusion_scores: dict, top_n: int) -> pd.DataFrame:
        """Cross-encoder (Score General) + geo + 'pasa exclusiones' -> composite ponderado."""
        logits = self.reranker.score([(rerank_query, self._rerank_doc(n, crit_q)) for n in shortlist_ids])
        general = _minmax(logits)  # Score General normalizado a 0-1 dentro del shortlist
        # exclusion_pass: 1.0 si el paciente es el MENOS parecido a las exclusiones (no se excluye).
        exclusion_pass = [1.0 - e for e in _minmax([exclusion_scores.get(n, 0.0) for n in shortlist_ids])]

        rows = []
        for nct_id, gen, exc_pass in zip(shortlist_ids, general, exclusion_pass):
            geo = geo_score(list(self.metadata_df.loc[nct_id, 'location_countries']), country)
            rows.append({
                'nct_id': nct_id, 'reranker_score': gen, 'geo_score': geo,
                'exclusion_pass': exc_pass, 'final_score': final_score(gen, geo, exc_pass),
            })
        return (
            pd.DataFrame(rows)
            .sort_values('final_score', ascending=False)
            .head(top_n)
            .reset_index(drop=True)
        )

    def _phase_filter(self, ids, patient: Patient) -> set:
        """Filtra por fase si el formulario pidio fases (interseccion con la fase del estudio)."""
        wanted = requested_phase_tokens(patient.phases)
        if not wanted:
            return set(ids)
        return {n for n in ids if self.study_phases.get(n, set()) & wanted}

    # --- v2: gate por enfermedad (lexico) + MedCPT + exclusion neutral ---

    def _disease_gate(self, patient: Patient, eligible_ids: set) -> list:
        """nct_ids elegibles cuyo condition_text/titulo contiene la enfermedad del paciente."""
        kws = disease_keywords(patient.diagnosis)
        gated = [n for n in eligible_ids if any(k in self.disease_blob.get(n, '') for k in kws)]
        return gated or list(eligible_ids)  # fallback: si el gate queda vacio, no filtra

    def _match_v2(self, patient: Patient, top_n: int) -> dict:
        crit_q = self.criteria_model.encode([build_criteria_query(patient)])[0]
        eligible_ids = filter_studies(self.clinical_df, patient.age) & self.studies_min_criteria
        eligible_ids = self._phase_filter(eligible_ids, patient)
        gated = self._disease_gate(patient, eligible_ids)

        inclusion_scores = score_criteria(crit_q, self.inclusion_meta, self.inclusion_emb, gated, INCLUSION_TOP_K)
        exclusion_scores = score_criteria(crit_q, self.exclusion_meta, self.exclusion_emb, gated, INCLUSION_TOP_K)

        shortlist_ids = sorted(gated, key=lambda n: inclusion_scores.get(n, 0.0), reverse=True)[:max(RERANK_POOL, top_n)]
        ranked = self._rerank_v2(shortlist_ids, build_rerank_query(patient), crit_q, patient.country, inclusion_scores, exclusion_scores, top_n)
        trials = [self._to_trial_match(row, patient.country) for _, row in ranked.iterrows()]
        return {'totalCount': len(gated), 'trials': trials}

    def _rerank_v2(self, shortlist_ids: list, rerank_query: str, crit_q: np.ndarray,
                   country: str, inclusion_scores: dict, exclusion_scores: dict, top_n: int) -> pd.DataFrame:
        """MedCPT (enfermedad) + inclusion + exclusion-pass (neutral) + geo -> score final v2."""
        logits  = self.reranker.score([(rerank_query, self._rerank_doc(n, crit_q)) for n in shortlist_ids])
        disease = _minmax(logits)
        inc     = _minmax([inclusion_scores.get(n, 0.0) for n in shortlist_ids])
        exc     = exclusion_pass([exclusion_scores.get(n, float('nan')) for n in shortlist_ids])

        rows = []
        for nct_id, d, i, e in zip(shortlist_ids, disease, inc, exc):
            geo = geo_score(list(self.metadata_df.loc[nct_id, 'location_countries']), country)
            rows.append({
                'nct_id': nct_id, 'reranker_score': d, 'inclusion_norm': i,
                'exclusion_pass': e, 'geo_score': geo, 'final_score': final_score_v2(d, i, e, geo),
            })
        return (
            pd.DataFrame(rows)
            .sort_values('final_score', ascending=False)
            .head(top_n)
            .reset_index(drop=True)
        )

    def explain_one(self, patient: Patient, missing: list, nct_id: str) -> str:
        """Explicacion LLM de un solo estudio (POST /api/explain); fail-soft."""
        if not LLM_EXPLANATIONS:
            return ''
        with self._lock:
            crit_q = self.criteria_model.encode([build_criteria_query(patient)])[0]
            info = {
                'nctId': nct_id,
                'title': self.metadata_df.loc[nct_id, 'brief_title'] or '',
                'matched_inclusion': top_criteria(crit_q, self.inclusion_meta, self.inclusion_emb, nct_id, EXPLAIN_INCLUSION_K),
                'top_exclusion':     top_criteria(crit_q, self.exclusion_meta, self.exclusion_emb, nct_id, EXPLAIN_EXCLUSION_K),
            }
        try:
            return explain_trials(patient_summary(patient), missing, [info]).get(nct_id, '')
        except Exception as e:
            print(f'LLM explanation unavailable: {e}')
            return ''

    def _to_trial_match(self, row: pd.Series, country: str) -> dict:
        """Arma un TrialMatch (contrato del frontend) para un estudio rankeado."""
        nct_id    = row['nct_id']
        meta      = self.metadata_df.loc[nct_id]
        elig      = self.eligibility_df.loc[nct_id]
        countries = list(meta['location_countries'])
        score     = float(np.clip(row['final_score'], 0.0, 1.0))
        return {
            'nctId':             nct_id,
            'title':             meta['brief_title'] or 'Untitled study',
            'phase':             ' / '.join(meta['phases']) or '—',
            'enrollment':        None,                                   # no descargado offline
            'interventions':     list(meta['interventions'])[:4],
            'inclusionCriteria': list(elig['enriched_inclusion'])[:MAX_DISPLAY_CRITERIA],
            'exclusionCriteria': list(elig['enriched_exclusion'])[:MAX_DISPLAY_CRITERIA - 1],
            'sponsor':           '—',                                    # no descargado offline
            'siteCount':         len(countries),
            'localSiteCount':    sum(c == country for c in countries),
            'siteCountries':     list(dict.fromkeys(countries))[:5],   # paises unicos (para el flag)
            'matchScore':        score,
            'confidence':        confidence_for(score),
            'url':               f'https://clinicaltrials.gov/study/{nct_id}',
        }
