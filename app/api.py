"""Servicio FastAPI que expone el pipeline RAG de matching al frontend trial-matcher.

Carga el motor (modelos + embeddings + metadata) una sola vez al arrancar y sirve
POST /api/match, devolviendo el contrato MatchResult que consume la UI.

Run:  uvicorn app.api:app --reload --port 8000   (desde la raiz del repo)
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
def match(profile: dict) -> dict:
    """Recibe un PatientProfile del frontend y devuelve un MatchResult rankeado (sin LLM)."""
    patient = patient_from_profile(profile)
    return engine.match(patient, missing_fields(profile))


@app.post('/api/explain')
def explain(payload: dict) -> dict:
    """Genera la explicacion LLM de un solo estudio: {profile, nctId} -> {explanation}."""
    profile = payload['profile']
    patient = patient_from_profile(profile)
    return {'explanation': engine.explain_one(patient, missing_fields(profile), payload['nctId'])}
