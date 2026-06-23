"""Construye data/05_trial_metadata.parquet con los campos de display para el frontend.

Extrae de la descarga cruda (clinical_trials.parquet) los campos que el pipeline de
scoring no produce pero la UI necesita: titulo, fases, intervenciones (labels de arms)
y paises de los sitios. enrollment y sponsor no se descargaron en el notebook 02.
"""
import json
from pathlib import Path

import pandas as pd

DATA_DIR    = Path(__file__).resolve().parent.parent / 'data'
RAW_PARQUET = DATA_DIR / 'clinical_trials.parquet'
OUT_PARQUET = DATA_DIR / '05_trial_metadata.parquet'


def arm_labels(arm_groups_json: str) -> list[str]:
    """Labels de los brazos del estudio (proxy de intervenciones)."""
    arms = json.loads(arm_groups_json or '[]')
    return [a['label'] for a in arms if a.get('label')]


def site_countries(locations_json: str) -> list[str]:
    """Paises de los sitios del estudio (para siteCount / localSiteCount)."""
    locs = json.loads(locations_json or '[]')
    return [l['country'] for l in locs if l.get('country')]


def build_metadata(raw: pd.DataFrame) -> pd.DataFrame:
    """Arma la tabla de metadata de display por estudio."""
    return pd.DataFrame({
        'nct_id':             raw['nct_id'],
        'brief_title':        raw['brief_title'].fillna(''),
        'phases':             raw['phases'].map(lambda s: json.loads(s or '[]')),
        'interventions':      raw['arm_groups'].map(arm_labels),
        'location_countries': raw['locations'].map(site_countries),
    })


raw_df      = pd.read_parquet(RAW_PARQUET)
metadata_df = build_metadata(raw_df)
metadata_df.to_parquet(OUT_PARQUET, index=False)
print(f'Escrito: {OUT_PARQUET} -- {len(metadata_df):,} estudios')
print(metadata_df.head(3).to_string())
