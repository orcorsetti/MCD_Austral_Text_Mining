"""Explicacion de elegibilidad generada por un LLM local (LM Studio / Qwen).

Toma el paciente y los criterios que matchearon por estudio, y pide al LLM una
explicacion corta por ensayo. Una sola llamada batcheada para todos los estudios.
"""
import json
import os

import requests

LM_STUDIO_URL = os.environ.get('LM_STUDIO_URL', 'http://localhost:1234/v1/chat/completions')
LLM_MODEL     = os.environ.get('LM_STUDIO_MODEL', 'qwen/qwen3.6-27b')
LLM_TIMEOUT   = 120

# Prefill que desactiva el modo de razonamiento de Qwen3 (mucho mas rapido).
NO_THINK_PREFILL = '<think></think>'

SYSTEM_PROMPT = (
    'You are a clinical trial matching assistant. For each trial, write ONE sentence '
    '(max 30 words) on why it fits the patient, citing a matched criterion. '
    'If key patient data is missing, note what to confirm. '
    'Return ONLY a JSON object mapping each nctId to its explanation string, no prose.'
)


def _build_user_prompt(patient_summary: str, missing: list, trials: list) -> str:
    """Arma el prompt de usuario con el paciente y los criterios matcheados por estudio."""
    lines = [f'PATIENT: {patient_summary}']
    if missing:
        lines.append(f'MISSING PATIENT DATA: {", ".join(missing)}')
    lines.append('\nTRIALS:')
    for t in trials:
        inc = ' | '.join(c[:200] for c in t['matched_inclusion'])
        exc = ' | '.join(c[:200] for c in t['top_exclusion'])
        lines.append(f"\n[{t['nctId']}] {t['title']}")
        lines.append(f'  matched inclusion: {inc}')
        if exc:
            lines.append(f'  exclusion to check: {exc}')
    lines.append('\nReturn JSON: {"NCT...": "explanation", ...}')
    return '\n'.join(lines)


def _parse_json_object(content: str) -> dict:
    """Extrae el objeto JSON de la respuesta (tolera fences ```json)."""
    text = content.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
    start, end = text.find('{'), text.rfind('}')
    return json.loads(text[start : end + 1])


def explain_trials(patient_summary: str, missing: list, trials: list) -> dict:
    """Devuelve {nctId: explicacion} para los estudios dados via el LLM local."""
    response = requests.post(
        LM_STUDIO_URL,
        json={
            'model': LLM_MODEL,
            'messages': [
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': _build_user_prompt(patient_summary, missing, trials)},
                {'role': 'assistant', 'content': NO_THINK_PREFILL},
            ],
            'temperature': 0.3,
            'max_tokens': 1200,
        },
        timeout=LLM_TIMEOUT,
    )
    response.raise_for_status()
    return _parse_json_object(response.json()['choices'][0]['message']['content'])
