"""Parsea criterios de inclusion/exclusion (+ titulo) y los embebe, tagueados por estudio.

Output (cacheado; re-correr no re-embebe si ya existe):
- sandbox/data/criteria.parquet  -- nct_id, kind (inclusion|exclusion|title), text
- sandbox/data/criteria_emb.npy  -- embeddings alineados fila a fila (768d)
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

DATA_DIR     = Path(__file__).resolve().parent / 'data'
STUDIES      = DATA_DIR / 'studies.parquet'
CRITERIA_OUT = DATA_DIR / 'criteria.parquet'
EMB_OUT      = DATA_DIR / 'criteria_emb.npy'

MODEL_NAME = 'pritamdeka/S-PubMedBert-MS-MARCO'  # 768d, dominio clinico + retrieval
MIN_LEN, MAX_LEN = 12, 500

HEADER_RE = re.compile(r'(?i)\b(key\s+)?(inclusion|exclusion)\s+criteria\s*:?')
BULLET_RE = re.compile(r'^\s*(?:[-*•]|\d+[.)]|[a-z][.)])\s*')


def split_sections(text: str) -> tuple[str, str]:
    """Separa el texto de elegibilidad en (seccion inclusion, seccion exclusion)."""
    lower = text.lower()
    exc = lower.find('exclusion criteria')
    inc = lower.find('inclusion criteria')
    if exc == -1:
        return (text[inc:] if inc != -1 else text), ''
    inc_text = text[inc:exc] if 0 <= inc < exc else text[:exc]
    return inc_text, text[exc:]


def split_items(section: str) -> list[str]:
    """Extrae criterios individuales de una seccion (por lineas / bullets)."""
    section = HEADER_RE.sub('', section, count=1)
    items = []
    for line in section.split('\n'):
        line = BULLET_RE.sub('', line).strip()
        if MIN_LEN <= len(line) <= MAX_LEN:
            items.append(line)
    return items


def study_rows(row: pd.Series) -> list[dict]:
    """Filas (nct_id, kind, text) de un estudio: titulo + criterios inc/exc."""
    inc_sec, exc_sec = split_sections(row['eligibility_criteria'])
    rows = [{'nct_id': row['nct_id'], 'kind': 'title', 'text': row['brief_title']}]
    rows += [{'nct_id': row['nct_id'], 'kind': 'inclusion', 'text': t} for t in split_items(inc_sec)]
    rows += [{'nct_id': row['nct_id'], 'kind': 'exclusion', 'text': t} for t in split_items(exc_sec)]
    return rows


studies = pd.read_parquet(STUDIES)
criteria = pd.DataFrame(r for _, row in studies.iterrows() for r in study_rows(row))
criteria = criteria[criteria['text'].str.len() >= MIN_LEN].reset_index(drop=True)

print(f'Estudios: {len(studies):,}')
print(criteria['kind'].value_counts().to_dict())

if EMB_OUT.exists():
    print('Embeddings ya existen; no se re-embebe.')
else:
    model = SentenceTransformer(MODEL_NAME, device='cuda')
    emb = model.encode(
        criteria['text'].tolist(), batch_size=256, normalize_embeddings=True,
        convert_to_numpy=True, show_progress_bar=True,
    )
    np.save(EMB_OUT, emb)
    print(f'Embeddings: {emb.shape} -> {EMB_OUT}')

criteria.to_parquet(CRITERIA_OUT, index=False)
print(f'Criterios: {len(criteria):,} -> {CRITERIA_OUT}')
