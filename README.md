# MCD Austral — RAG para Matching de Pacientes a Ensayos Clínicos

Sistema RAG (Retrieval Augmented Generation) que, dado el perfil clínico de un paciente,
recupera y rankea los ensayos clínicos oncológicos disponibles que mejor aplican a su caso,
con una explicación de elegibilidad generada por un LLM.

Proyecto integrador — Text Mining / NLP · Maestría en Ciencia de Datos · Universidad Austral.

---

## Arquitectura

El sistema tiene un **pipeline offline** (se corre una vez, construye el índice) y un
**pipeline online** (por consulta del paciente, servido por una API).

```
OFFLINE (notebooks/)                          ONLINE (src/ + app/ + frontend/)
ClinicalTrials.gov v2                          Formulario del paciente (React)
   │ 02_get_clinicaltrials                         │  POST /api/match
   ▼                                                ▼
normalización scispaCy + MeSH (05)            filtros duros (status + edad)
   │                                                ▼
parseo inclusión/exclusión (03, 04)           prefiltro de condición (top-200)
   │  regex + fallback LLM                         ▼
   ▼                                          score bi-encoder inclusión − exclusión
embeddings por criterio (06)                       ▼  (shortlist top-50)
   │  S-PubMedBert + bge-small                 rerank cross-encoder MedCPT (Score General)
   ▼                                                ▼
06_*_embeddings.npy + _meta.parquet           score geográfico + composite ponderado
05_trial_metadata.parquet                          ▼  final = 0.8·reranker + 0.2·geo
                                              top-10  →  explicación LLM on-demand (Qwen local)
```

Para el detalle técnico (mecánica de retrieval, decisiones de modelos, hallazgos), ver
**[docs/architecture.md](docs/architecture.md)**.

---

## Estructura del repositorio

```
MCD_Austral_Text_Mining/
├── notebooks/            # pipeline offline (descarga → parseo → normalización → embeddings)
│   ├── 02_get_clinicaltrials.ipynb
│   ├── 03_parse_eligibility.ipynb / 04_parse_eligibility_llm.ipynb
│   ├── 05_normalize_clinical.ipynb
│   ├── 06_generate_embeddings.ipynb
│   └── 09_retrieval_pipeline.ipynb     # versión notebook del pipeline online
├── src/                  # pipeline online (production)
│   ├── embeddings.py     # wrapper SentenceTransformer (encoding normalizado)
│   ├── profile.py        # Patient + adaptación desde el form + query builders
│   ├── retrieval.py      # filtros + búsqueda por dot-product (cosine)
│   ├── rerank.py         # cross-encoder biomédico MedCPT
│   ├── scoring.py        # composite (reranker + geo) + confianza
│   ├── llm_generation.py # explicación de elegibilidad (LM Studio / Qwen local)
│   └── pipeline.py       # TrialMatcherEngine: carga todo una vez y resuelve consultas
├── app/
│   └── api.py            # FastAPI: POST /api/match, POST /api/explain, GET /health
├── frontend/             # webapp React + TypeScript + Vite (formulario y resultados)
├── utils/
│   ├── build_trial_metadata.py   # genera 05_trial_metadata.parquet
│   └── download_parquet.py       # descarga el dataset crudo desde HuggingFace
└── data/                 # parquets + embeddings (gitignored; ver más abajo)
```

---

## Cómo correrlo

### 1. Datos
Los embeddings y parquets viven fuera de git (son grandes). Necesitás en `data/`:
- `05_clinical_trials_normalized.parquet`, `05_eligibility_normalized.parquet`
- `05_trial_metadata.parquet` (generado con `utils/build_trial_metadata.py`)
- `06_{inclusion,exclusion,condition}_embeddings.npy` + `_meta.parquet`

El dataset crudo se baja con `python utils/download_parquet.py` (HuggingFace:
`OrneCorsetti/mcd-austral-clinical-trials`); los `05_/06_` se regeneran corriendo los notebooks.

### 2. Backend (API)
Entorno conda `ldi2_cuda` (torch+CUDA, sentence-transformers, fastapi). Desde la raíz:
```bash
uvicorn app.api:app --port 8000
```
La primera vez descarga 3 modelos (S-PubMedBert, bge-small, MedCPT). Carga el índice una vez al arrancar.

### 3. LLM local (opcional, para las explicaciones)
[LM Studio](https://lmstudio.ai) sirviendo `qwen/qwen3.6-27b` en `localhost:1234`
(API OpenAI-compatible). Si no está corriendo, la búsqueda funciona igual y las
explicaciones quedan deshabilitadas (fail-soft). Se puede apagar con `LLM_EXPLANATIONS=0`.

### 4. Frontend
```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxy /api → :8000)
```

---

## Stack y modelos

| Componente | Modelo / tecnología |
|---|---|
| Embeddings de criterios | `pritamdeka/S-PubMedBert-MS-MARCO` (768d) |
| Embeddings de condición | `BAAI/bge-small-en-v1.5` (384d) |
| Reranker (Score General) | `ncbi/MedCPT-Cross-Encoder` (biomédico) |
| LLM de explicación | `qwen/qwen3.6-27b` local vía LM Studio |
| Vector search | dot-product exacto sobre `.npy` memory-mapped (no ANN/vector DB) |
| API | FastAPI + uvicorn · Frontend: React + Vite |

---

## Estado vs. el diseño (diagrama drawio)

**Completo:** descarga, normalización clínica, parseo inclusión/exclusión, embeddings,
filtros duros (status + edad), prefiltro de condición, score inclusión−exclusión,
**rerank cross-encoder**, **score geográfico + composite ponderado**, **explicación LLM**,
y la webapp conectada end-to-end.

**Pendiente:** filtro duro por ECOG (requiere extracción offline desde el texto),
`enrollment`/`sponsor` (2 campos a re-descargar), N-por-request, ChromaDB (reemplazo del
índice numpy), y evaluación con RAGAS (requiere ground truth). Ver detalle en docs.
