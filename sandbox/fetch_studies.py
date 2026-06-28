"""Descarga ~5k estudios oncologicos abiertos para iterar rapido el pipeline.

Subset chico (RECRUITING + NOT_YET_RECRUITING, condicion cancer) con los campos
necesarios para extraer criterios de inclusion/exclusion + titulo.
"""
from pathlib import Path

import pandas as pd
import requests

BASE_URL    = 'https://clinicaltrials.gov/api/v2/studies'
OUT_PARQUET = Path(__file__).resolve().parent / 'data' / 'studies.parquet'
MAX_STUDIES = 5000
PAGE_SIZE   = 1000
STATUSES    = ['RECRUITING', 'NOT_YET_RECRUITING']
FIELDS = [
    'NCTId', 'BriefTitle', 'OfficialTitle', 'OverallStatus',
    'Condition', 'ConditionMeshTerm', 'Phase',
    'EligibilityCriteria', 'MinimumAge', 'StdAge', 'LocationCountry',
]


def fetch_studies(max_studies: int) -> list[dict]:
    """Descarga estudios paginando hasta alcanzar el maximo."""
    all_studies: list[dict] = []
    page_token = None

    while len(all_studies) < max_studies:
        params = {
            'query.cond':            'cancer',
            'filter.overallStatus':  ','.join(STATUSES),
            'fields':                ','.join(FIELDS),
            'pageSize':              PAGE_SIZE,
            'format':                'json',
        }
        if page_token:
            params['pageToken'] = page_token

        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()

        studies = data.get('studies', [])
        if not studies:
            break

        all_studies.extend(studies)
        print(f'Descargados: {len(all_studies)}')
        page_token = data.get('nextPageToken')
        if not page_token:
            break

    return all_studies[:max_studies]


def parse_study(study: dict) -> dict:
    """Aplana un estudio crudo a los campos que usa el sandbox."""
    proto   = study.get('protocolSection', {})
    derived = study.get('derivedSection', {})
    id_mod    = proto.get('identificationModule', {})
    status    = proto.get('statusModule', {})
    cond_mod  = proto.get('conditionsModule', {})
    design    = proto.get('designModule', {})
    eligib    = proto.get('eligibilityModule', {})
    locs      = proto.get('contactsLocationsModule', {}).get('locations', [])
    meshes    = derived.get('conditionBrowseModule', {}).get('meshes', [])

    return {
        'nct_id':               id_mod.get('nctId'),
        'brief_title':          id_mod.get('briefTitle', ''),
        'overall_status':       status.get('overallStatus'),
        'conditions':           cond_mod.get('conditions', []),
        'mesh_terms':           [m.get('term') for m in meshes if m.get('term')],
        'phases':               design.get('phases', []),
        'eligibility_criteria': eligib.get('eligibilityCriteria', ''),
        'min_age':              eligib.get('minimumAge'),
        'std_ages':             eligib.get('stdAges', []),
        'countries':            sorted({l.get('country') for l in locs if l.get('country')}),
    }


raw = fetch_studies(MAX_STUDIES)
df = pd.DataFrame(parse_study(s) for s in raw)
df = df[df['eligibility_criteria'].str.len() > 0].reset_index(drop=True)

OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
df.to_parquet(OUT_PARQUET, index=False)
print(f'\nGuardado: {OUT_PARQUET} -- {len(df)} estudios con criterios')
print(df[['nct_id', 'brief_title', 'overall_status']].head(3).to_string())
