"""Servicio FastAPI que expone el pipeline RAG de matching al frontend trial-matcher.

Carga el motor (modelos + embeddings + metadata) una sola vez al arrancar y sirve
POST /api/match, devolviendo el contrato MatchResult que consume la UI.

Run:  uvicorn app.api:app --reload --port 8000   (desde la raiz del repo)
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.pipeline import TrialMatcherEngine
from src.profile import missing_fields, patient_from_profile

app = FastAPI(title='TrialMatch RAG API')

# Permite el dev server de Vite (localhost:5173) si no se usa el proxy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)

engine = TrialMatcherEngine()


@app.get('/health')
def health() -> dict:
    """Chequeo de vida del servicio."""
    return {'status': 'ok', 'studies': len(engine.clinical_df)}


@app.post('/api/match')
def match(profile: dict, variant: str = 'v2', top_n: int = 10) -> dict:
    """PatientProfile -> MatchResult. variant 'v1'|'v2'; top_n = cantidad de estudios devueltos."""
    patient = patient_from_profile(profile)
    return engine.match(patient, missing_fields(profile), variant=variant, top_n=top_n)


@app.post('/api/explain')
def explain(payload: dict) -> dict:
    """Genera la explicacion LLM de un solo estudio: {profile, nctId} -> {explanation}."""
    profile = payload['profile']
    patient = patient_from_profile(profile)
    return {'explanation': engine.explain_one(patient, missing_fields(profile), payload['nctId'])}


# Sirve el frontend compilado (frontend/dist) en el mismo origen que la API, para
# poder exponer todo por un solo puerto (deploy via tunnel). Debe ir despues de las rutas.
_DIST = Path(__file__).resolve().parent.parent / 'frontend' / 'dist'
if _DIST.exists():
    app.mount('/', StaticFiles(directory=str(_DIST), html=True), name='frontend')
