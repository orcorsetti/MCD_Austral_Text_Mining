"""Superficie de scoring del sandbox (v3): gate por enfermedad -> MedCPT -> elegibilidad.

Hallazgo: el bi-encoder (coseno) NO discrimina tipo de cancer (todo oncologia ~0.85-0.95),
asi que los criterios solos son "ciegos a la enfermedad". Pipeline v3:

  1. GATE lexico por enfermedad   (conditions + mesh + titulo vs diagnostico del paciente)
  2. MedCPT cross-encoder         (Score General de enfermedad/elegibilidad, discrimina)
  3. inclusion (bi-encoder)        refina elegibilidad dentro de la enfermedad
  4. exclusion                     penaliza; "sin exclusion parseada" = NEUTRAL (no premio)

Iteracion rapida: las senales caras (MedCPT + embeddings) se cachean por paciente; tocar
los PESOS re-rankea al instante. Cambiar la logica -> subir SIGNALS_VERSION.

  python sandbox/match.py
"""
import hashlib
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DATA_DIR  = Path(__file__).resolve().parent / 'data'
CACHE_Q   = DATA_DIR / 'query_cache'
CACHE_S   = DATA_DIR / 'signals_cache'
MODEL_NAME = 'pritamdeka/S-PubMedBert-MS-MARCO'
SIGNALS_VERSION = 'v3'

# --- pesos / parametros de scoring (iterar aca; re-run instantaneo) ---
W_DISEASE       = 1.0
W_INCLUSION     = 0.6
W_EXCLUSION     = 0.4
TOP_K_INCLUSION = 3
TOP_K_EXCLUSION = 3
RERANK_DOC_K    = 3     # criterios de inclusion en el documento que ve MedCPT
RESULT_TOP_N    = 10

# Diagnostico del form -> palabras clave que deben aparecer en conditions/mesh/titulo.
DISEASE_KEYWORDS = {
    'nsclc': ['lung'], 'sclc': ['lung'], 'lung': ['lung'], 'mesothelioma': ['mesotheli'],
    'breast': ['breast'],
    'colorectal': ['colorectal', 'colon', 'rectal'], 'crc': ['colorectal', 'colon', 'rectal'],
    'gastric': ['gastric', 'stomach', 'gastroesophageal'], 'gej': ['gastric', 'gastroesophageal'],
    'hepatocellular': ['hepatocellular', 'liver'], 'hcc': ['hepatocellular', 'liver'],
    'pancrea': ['pancrea'], 'cholangio': ['cholangio', 'biliary'], 'biliary': ['biliary', 'cholangio'],
    'esophageal': ['esophag'],
    'prostate': ['prostate'], 'urothelial': ['urotheli', 'bladder'], 'bladder': ['bladder', 'urotheli'],
    'renal': ['renal', 'kidney'], 'rcc': ['renal', 'kidney'],
    'cervical': ['cervic'], 'endometrial': ['endometrial', 'uterine'], 'uterine': ['uterine', 'endometrial'],
    'ovarian': ['ovarian', 'fallopian', 'peritoneal'],
    'melanoma': ['melanoma'], 'hnscc': ['head and neck', 'neck'],
    'thyroid': ['thyroid'], 'sarcoma': ['sarcoma'], 'glioblastoma': ['glioblastoma', 'glioma'], 'gbm': ['glioblastoma', 'glioma'],
    'neuroendocrine': ['neuroendocrine'], 'net': ['neuroendocrine'],
    'dlbcl': ['lymphoma'], 'lymphoma': ['lymphoma'], 'myeloma': ['myeloma'],
    'aml': ['myeloid leukemia'], 'cll': ['lymphocytic leukemia'], 'cml': ['myeloid leukemia'],
}

# --- paciente de prueba ---
TEST_PATIENT = {
    'diagnosis': 'NSCLC', 'histology': 'adenocarcinoma', 'setting': 'metastatic',
    'biomarkers': ['PD-L1 high', 'no driver mutations'], 'ecog': '1',
    'tx_setting': 'second line', 'prior_lines': '1',
    'prior_treatments': ['carboplatin', 'pemetrexed', 'pembrolizumab'],
    'free_text': 'Adenocarcinoma NSCLC without driver mutations, progressed on 1L carboplatin/pemetrexed/pembrolizumab, looking for 2L options.',
}


def disease_keywords(diagnosis: str) -> list:
    """Palabras clave de enfermedad para el gate (mapa + fallback a palabras del diagnostico)."""
    d = diagnosis.lower()
    for key, kws in DISEASE_KEYWORDS.items():
        if key in d:
            return kws
    return [w for w in re.findall(r'[a-z]+', d) if len(w) > 3]


def build_disease_query(p: dict) -> str:
    """Query enfocada en enfermedad (para MedCPT)."""
    return f"{p['diagnosis']} {p.get('histology', '')} {p.get('setting', '')}".strip()


def build_query(p: dict) -> str:
    """Perfil clinico completo (para los criterios de elegibilidad)."""
    parts = [
        f"{p['diagnosis']} {p.get('histology', '')} {p.get('setting', '')}".strip() + '.',
        f"Biomarkers: {', '.join(p['biomarkers'])}." if p.get('biomarkers') else '',
        f"ECOG {p['ecog']}." if p.get('ecog') else '',
        f"{p['tx_setting']} treatment; {p.get('prior_lines', '?')} prior lines." if p.get('tx_setting') else '',
        f"Prior therapies: {', '.join(p['prior_treatments'])}." if p.get('prior_treatments') else '',
        p.get('free_text', ''),
    ]
    return ' '.join(s for s in parts if s)


def query_embedding(text: str) -> np.ndarray:
    """Embedding de query con cache (carga S-PubMedBert solo si es nueva)."""
    CACHE_Q.mkdir(parents=True, exist_ok=True)
    path = CACHE_Q / (hashlib.md5(text.encode()).hexdigest() + '.npy')
    if path.exists():
        return np.load(path)
    from sentence_transformers import SentenceTransformer
    print('(embedding query: cargando S-PubMedBert...)')
    model = SentenceTransformer(MODEL_NAME, device='cuda')
    emb = model.encode([text], normalize_embeddings=True, convert_to_numpy=True)[0]
    np.save(path, emb)
    return emb


def topk_mean(s: pd.Series, k: int) -> float:
    return float(s.nlargest(k).mean()) if len(s) else np.nan


def gate(patient: dict, blobs: dict) -> list:
    """nct_ids cuya condicion/mesh/titulo contiene alguna palabra clave de la enfermedad."""
    kws = disease_keywords(patient['diagnosis'])
    matched = [n for n, blob in blobs.items() if any(k in blob for k in kws)]
    return matched or list(blobs)  # si el gate queda vacio, no filtra


def compute_signals(patient: dict, criteria: pd.DataFrame, emb: np.ndarray, blobs: dict) -> pd.DataFrame:
    """Senales caras por estudio gateado (MedCPT + inc/exc bi-encoder), cacheadas por paciente."""
    key = hashlib.md5((SIGNALS_VERSION + '|' + build_query(patient) + '|' + build_disease_query(patient)).encode()).hexdigest()
    CACHE_S.mkdir(parents=True, exist_ok=True)
    path = CACHE_S / (key + '.parquet')
    if path.exists():
        return pd.read_parquet(path)

    gated = gate(patient, blobs)
    elig_q = query_embedding(build_query(patient))
    df = criteria[criteria.nct_id.isin(gated)].assign(sim=emb[criteria.nct_id.isin(gated).to_numpy()] @ elig_q)

    inc = df[df.kind == 'inclusion'].groupby('nct_id')['sim'].apply(lambda s: topk_mean(s, TOP_K_INCLUSION))
    exc = df[df.kind == 'exclusion'].groupby('nct_id')['sim'].apply(lambda s: topk_mean(s, TOP_K_EXCLUSION))

    # Documento que ve MedCPT: titulo + top criterios de inclusion (por similitud).
    def doc(nct_id: str) -> str:
        title = blobs[nct_id].split(' || ')[0]
        sub = df[(df.nct_id == nct_id) & (df.kind == 'inclusion')].nlargest(RERANK_DOC_K, 'sim')
        return f"{title}. {' '.join(sub['text'])}"[:1500]

    from src.rerank import CrossEncoderReranker
    print(f'(MedCPT: rerankeando {len(gated)} estudios gateados...)')
    reranker = CrossEncoderReranker()
    disease_text = build_disease_query(patient)
    medcpt = reranker.score([(disease_text, doc(n)) for n in gated])

    out = pd.DataFrame({'medcpt': medcpt}, index=gated)
    out['inclusion'] = inc
    out['exclusion'] = exc            # NaN si el estudio no tiene exclusion parseada
    out.index.name = 'nct_id'
    out.to_parquet(path)
    return out


def minmax(s: pd.Series) -> pd.Series:
    lo, hi = s.min(), s.max()
    return (s - lo) / (hi - lo) if hi > lo else s * 0 + 1.0


def score(sig: pd.DataFrame) -> pd.DataFrame:
    """Combina enfermedad (MedCPT) + elegibilidad (inclusion) - exclusion -> score final."""
    out = sig.copy()
    out['disease']   = minmax(out['medcpt'])
    out['inc_norm']  = minmax(out['inclusion'].fillna(out['inclusion'].median()))
    # exclusion: alto sim = mas excluible. pass = 1 - norm. Sin exclusion parseada = NEUTRAL (0.5).
    present = out['exclusion'].dropna()
    exc_norm = minmax(out['exclusion']) if len(present) > 1 else out['exclusion'] * 0
    out['exc_pass']  = (1 - exc_norm).fillna(0.5)
    out['final'] = W_DISEASE * out['disease'] + W_INCLUSION * out['inc_norm'] + W_EXCLUSION * out['exc_pass']
    return out.sort_values('final', ascending=False)


studies  = pd.read_parquet(DATA_DIR / 'studies.parquet')
criteria = pd.read_parquet(DATA_DIR / 'criteria.parquet')
emb      = np.load(DATA_DIR / 'criteria_emb.npy')
titles   = dict(zip(studies.nct_id, studies.brief_title))
# blob por estudio: titulo || conditions || mesh (lowercased) para el gate.
blobs = {
    r.nct_id: (str(r.brief_title) + ' || ' + ' '.join(map(str, r.conditions)) + ' ' + ' '.join(map(str, r.mesh_terms))).lower()
    for r in studies.itertuples()
}

sig = compute_signals(TEST_PATIENT, criteria, emb, blobs)
ranked = score(sig).head(RESULT_TOP_N)

print(f'\nDisease: {build_disease_query(TEST_PATIENT)}   |   gated: {len(sig)} estudios\n')
for nct_id, r in ranked.iterrows():
    exc = 'n/a' if pd.isna(r['exclusion']) else f"{r['exclusion']:.2f}"
    print(f"{nct_id}  final={r['final']:.3f}  disease={r['disease']:.2f} inc={r['inc_norm']:.2f} excPass={r['exc_pass']:.2f} (excSim={exc})")
    print(f"   {str(titles.get(nct_id, ''))[:94]}")
