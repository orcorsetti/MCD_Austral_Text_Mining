# Sistema RAG para Matching de Pacientes a Ensayos Clínicos

> Proyecto integrador final — Materia de Text Mining / NLP
> Maestría en Ciencia de Datos · Universidad Austral

---

## 1. Contexto y objetivo

### Problema
Identificar, dado el perfil clínico de un paciente, cuáles son los ensayos clínicos disponibles a nivel mundial que mejor aplican a su caso. Actualmente este matching se hace de forma manual por médicos investigadores, lo que es lento, propenso a errores y difícil de escalar.

### Objetivo
Construir un sistema RAG (Retrieval Augmented Generation) que combine retrieval híbrido y generación contextualizada para producir recomendaciones explicables de estudios clínicos aplicables a un paciente.

### Por qué RAG
El sistema completo es un RAG clínico avanzado:
- **Retrieval** — búsqueda en la base de ensayos
- **Augmentation** — armado de contexto con los top candidatos
- **Generation** — LLM produce la explicación final

Va más allá de un RAG básico al incorporar filtros estructurados, parseo de criterios inclusión/exclusión, scoring compuesto y reranking — lo que se conoce como "hybrid RAG" o "agentic RAG".

---

## 2. Fuente de datos

### ClinicalTrials.gov API v2
Base pública del NIH (USA) con todos los ensayos clínicos registrados a nivel mundial.

- **Endpoint base:** `https://clinicaltrials.gov/api/v2/studies`
- **Sin autenticación** requerida
- **~439k estudios** disponibles
- **Datos 100% públicos** — no involucra información sensible

### Campos clave del dataset

| Campo | Uso en el pipeline |
|---|---|
| `EligibilityCriteria` | Texto completo de inclusión/exclusión — **el más crítico** |
| `MinimumAge` / `MaximumAge` | Filtros duros |
| `Sex` | Filtro duro |
| `OverallStatus` | Filtro duro (RECRUITING, etc.) |
| `Condition` | Indexado por diagnóstico |
| `Phase` | Componente del scoring |
| `LocationCountry` | Componente geográfico del scoring |
| `InterventionName` / `InterventionType` | Contexto del estudio |
| `BriefSummary` / `DetailedDescription` | Contexto adicional |
| `PrimaryOutcomeMeasure` | Información para el LLM |
| `LeadSponsorName` | Metadata |

---

## 3. Arquitectura general

### Separación offline / online

**Offline (una sola vez):**
- Descarga del dataset desde ClinicalTrials.gov API
- Normalización de diagnósticos (scispaCy → Condition, Keyword, MeSH)
- Parseo de criterios: separación inclusión vs exclusión
- Generación de embeddings de cada criterio individual
- Persistencia en vector store + dataset estructurado

**Online (por cada consulta):**
- Recepción del formulario del paciente
- Embedding del perfil
- Filtros duros
- Búsqueda semántica
- Penalización por exclusión semántica
- Re-ranking con cross-encoder
- Scoring compuesto
- Selección Top-N
- Generación de explicación con LLM
- Respuesta al frontend

---

## 4. Pipeline offline (indexado)

### 4.1 Descarga del dataset
Pipeline Python modular con tres funciones:
- `fetch_all_studies()` — paginación contra la API
- `parse_study()` — aplanado del JSON anidado a dict plano
- `to_dataframe()` — conversión a DataFrame

Output: parquet único con todos los estudios, subido a HuggingFace Hub como dataset versionado.

### 4.2 Normalización clínica
Usar **scispaCy** para normalizar terminología:
- Conditions estandarizadas
- Mapeo a MeSH (Medical Subject Headings)
- Keywords clínicos consistentes

Permite consultas estructuradas posteriores y mejora la calidad del retrieval.

### 4.3 Separación inclusión vs exclusión

**Estrategia en cascada:**

1. **Regex agresivo** — buscar headers "Inclusion Criteria:" y "Exclusion Criteria:" como anclas. Cubre ~85% de los casos.
2. **Parseo de items** — partir cada sección por bullets, saltos de línea o numeración. Cada criterio queda como item individual.
3. **Heurísticas fallback** — para textos sin headers claros: "patients must" → inclusión; "patients with X are excluded" → exclusión.
4. **Flag de calidad** — estudios mal parseados se marcan con `parse_status='failed'` y reciben penalización en el scoring.

**Salida por estudio:**
```
nct_id
eligibility_raw         (texto original)
inclusion_criteria      (lista de items)
exclusion_criteria      (lista de items)
parse_status            (clean / partial / failed)
```

### 4.4 Generación de embeddings

**Granularidad:** un embedding por criterio individual (no por bloque). Habilita explicabilidad fina — se puede identificar exactamente qué criterio matchea o contradice.

**Modelo recomendado:** `neuml/pubmedbert-base-embeddings`
- Entrenado sobre PubMed
- Entiende jerga clínica
- Buen balance calidad/costo

**Alternativas:**
- `pritamdeka/S-PubMedBert-MS-MARCO` — fine-tuned para retrieval clínico
- `BAAI/bge-large-en-v1.5` — mejor calidad general no biomédica

**Enriquecimiento del texto antes de embeddear:**
- Expandir abreviaturas: "eGFR" → "estimated glomerular filtration rate (eGFR)"
- Prefijar con contexto del estudio: condición + tipo de criterio
- Tags semánticos: `[lab value]`, `[medication]`, `[demographics]`

Ejemplo:
```
Crudo:        "eGFR < 60"
Enriquecido:  "[lab value] In type 2 diabetes study, exclusion:
               estimated glomerular filtration rate (eGFR) less than 60 mL/min"
```

### 4.5 Storage

**ChromaDB** con la siguiente estructura:
```
id:       {nct_id}_{tipo}_{idx}
vector:   embedding del criterio
metadata:
  - nct_id
  - tipo: 'inclusion' | 'exclusion'
  - criterio_idx
  - texto_original
  - condicion_estudio
  - min_age / max_age / sex / status
```

**Dos colecciones separadas:** una para inclusión, otra para exclusión. Permite búsquedas con semánticas opuestas (queremos match alto contra inclusión, bajo contra exclusión).

**Parquet en HuggingFace** como fuente de verdad de los datos estructurados completos.

---

## 5. Pipeline online (consulta)

### 5.1 Formulario del paciente
Campos a capturar:
- Edad
- Sexo
- Diagnóstico principal
- Comorbilidades
- Medicación actual
- Labs relevantes (HbA1c, eGFR, etc.)
- ECOG (estado funcional) — relevante en oncología
- País / ubicación
- Criterios de exclusión conocidos

**Formato:** texto libre estructurado, no campos rígidos. Funciona mejor con el embedding porque los criterios también son texto libre.

### 5.2 Embedding del perfil
Usar el **mismo modelo** que el indexado offline. Genera el vector del perfil del paciente.

**Mejora opcional (query rewriting):** pasar el perfil por un LLM que lo reescriba en formato optimizado para retrieval clínico antes de embeddear.

### 5.3 Filtros duros (Capa 1)
Reglas binarias instantáneas:
- Edad dentro de `min_age` / `max_age`
- Sexo compatible
- Status `RECRUITING` o `ENROLLING_BY_INVITATION`
- (Opcional) ECOG dentro de rango

**Reducción esperada:** 400k → ~50k estudios

### 5.4 Búsqueda semántica (Capa 2)
Query del vector del paciente contra la colección de inclusión en ChromaDB. Recupera top-50 estudios candidatos.

**Reducción esperada:** 50k → 50 estudios

### 5.5 Penalización por exclusión semántica
Para cada candidato, buscar similitud entre el perfil y sus criterios de exclusión. Si el match es alto, descartar o penalizar fuertemente.

Esta es una innovación respecto a un RAG estándar: usar la exclusión como señal **negativa** explícita, no solo como criterio descartado.

### 5.6 Re-ranking (Capa 3)

**Modelo:** cross-encoder.
- `cross-encoder/ms-marco-MiniLM-L-6-v2` — genérico, rápido
- `pritamdeka/PubMedBERT-MNLI-MedNLI` — biomédico, más preciso

**Diferencia clave con embedding:**
- Embedding lee perfil y estudio por separado → buena similitud temática
- Cross-encoder lee el par completo junto → detecta contradicciones explícitas

**Estrategia recomendada:** dos rerankings separados:
```
score_match    = reranker(paciente, criterios_inclusion)
score_conflict = reranker(paciente, criterios_exclusion)
score_reranker = score_match - α × score_conflict
```

**Reducción esperada:** 50 → 5-10 estudios finales

### 5.7 Scoring compuesto

**Versión minimalista recomendada:**
```
score_final = w1 × score_reranker + w2 × score_geográfico
```

**Por qué solo dos componentes:**
- El reranker absorbe toda la compatibilidad clínica (mejor que el embedding crudo para esta tarea)
- La geografía es ortogonal — el reranker no la captura
- Componentes que miden lo mismo (embedding + reranker) suman ruido, no señal

**Extensiones opcionales:**
- Score de fase del estudio (fase 3 > fase 1)
- Score de urgencia (estudios que cierran pronto)
- Score de tipo de intervención

### 5.8 Selección Top-N
N parametrizado en el request del frontend (típicamente 3-5).

### 5.9 Generación con LLM

**Prompt incluye:**
- Perfil completo del paciente
- Top-N estudios con sus criterios completos (inclusión y exclusión)
- Scores y metadata relevante

**Output esperado:**
- Para cada estudio: justificación de por qué aplica
- Criterios que matchean
- Criterios que no se pudieron evaluar por falta de datos en el formulario
- Posibles incompatibilidades a verificar

**Modelos posibles:**
- API de Anthropic (Claude) — sin necesidad de GPU local
- `mistralai/Mistral-7B-Instruct-v0.3` — local, liviano
- `meta-llama/Meta-Llama-3-8B-Instruct` — local, mejor calidad

### 5.10 Respuesta al frontend
JSON con:
- Lista de estudios ordenados por score
- Link parametrizado a ClinicalTrials.gov
- País / coordenadas de sitios disponibles
- Explicación de elegibilidad generada por el LLM
- Score y desglose de componentes

---

## 6. Evaluación

### Métricas cuantitativas

**Para el retrieval:**
- Precision@K (K=5, 10)
- Recall@K
- MRR (Mean Reciprocal Rank)
- nDCG (Normalized Discounted Cumulative Gain)

**Para el RAG completo (usando RAGAS u otro framework):**
- Context Precision
- Context Recall
- Faithfulness — ¿la respuesta del LLM se sostiene en los documentos?
- Answer Relevance

### Ground truth
Tres estrategias posibles:
1. **Etiquetado manual** — 10-20 perfiles ficticios con estudios aplicables marcados manualmente
2. **LLM-as-judge** — usar un LLM independiente para juzgar relevancia
3. **Baseline comparativo** — comparar contra keyword matching simple para demostrar mejora

### Validación de cada componente
- **Parseo inclusión/exclusión:** muestra de 100 estudios, verificación manual del % bien parseado
- **Embeddings:** matches por similitud verificados clínicamente
- **Reranker:** Precision@5 con y sin reranker
- **Scoring:** sensibilidad de los pesos w1, w2

---

## 7. Stack tecnológico

| Componente | Tecnología |
|---|---|
| API de datos | ClinicalTrials.gov API v2 |
| Lenguaje | Python |
| Procesamiento de datos | pandas, pyarrow |
| Normalización clínica | scispaCy + UMLS |
| Embeddings | sentence-transformers + PubMedBERT |
| Vector store | ChromaDB |
| Reranking | cross-encoder (sentence-transformers) |
| LLM | API de Anthropic / Mistral 7B local |
| Versionado de datos | HuggingFace Hub |
| Evaluación | RAGAS |
| Frontend (opcional) | Streamlit / Gradio |

---

## 8. Estructura del proyecto

```
clinical-trials-rag/
├── data/
│   └── clinical_trials.parquet          (no versionado, viene de HF)
├── utils/
│   ├── 00_download_parquet.py           (descarga desde HF Hub)
│   └── build_dataset.py                 (pipeline completo descarga + upload)
├── notebooks/
│   ├── 01_get_clinicaltrials.ipynb      (descarga desde API)
│   ├── 02_parse_eligibility.ipynb       (separación inclusión/exclusión)
│   ├── 03_generate_embeddings.ipynb     (embeddings con PubMedBERT)
│   ├── 04_build_vector_store.ipynb      (carga en ChromaDB)
│   ├── 05_retrieval_pipeline.ipynb      (pipeline online completo)
│   └── 06_evaluation.ipynb              (métricas y comparaciones)
├── src/
│   ├── retrieval.py                     (filtros + búsqueda + reranking)
│   ├── scoring.py                       (scoring compuesto)
│   ├── llm_generation.py                (prompt + LLM)
│   └── pipeline.py                      (orquestador)
├── app/
│   └── streamlit_app.py                 (demo interactivo, opcional)
└── README.md
```

---

## 9. Plan de implementación sugerido

### Fase 1 — Datos (semana 1)
- Descarga del dataset desde la API
- Análisis exploratorio
- Subida a HuggingFace Hub
- Definición del formulario del paciente

### Fase 2 — Indexado offline (semana 2)
- Normalización clínica con scispaCy
- Parseo inclusión/exclusión
- Generación de embeddings (muestra primero, luego completo)
- Carga en ChromaDB

### Fase 3 — Pipeline de retrieval (semana 3)
- Filtros duros
- Búsqueda semántica
- Penalización por exclusión
- Reranking
- Scoring compuesto

### Fase 4 — Generación y evaluación (semana 4)
- Diseño del prompt
- Integración con LLM
- Métricas de evaluación
- Comparación con baseline

### Fase 5 — Frontend y entrega (semana 5)
- App demo con Streamlit
- Informe final
- Presentación

---

## 10. Trabajo futuro / mejoras

Cosas para mencionar en la sección "trabajo futuro" del informe:

- **Query rewriting** con LLM antes del embedding
- **Fine-tuning** del reranker con feedback de médicos
- **Loop de feedback activo** — el médico marca relevancia y se reentrenan los pesos
- **Multi-idioma** — soporte para criterios en español
- **Integración con historia clínica electrónica** — auto-completado del formulario desde HCE
- **Notificaciones proactivas** — alertar cuando un nuevo estudio aplica a un paciente seguido

---

## 11. Justificación del valor académico

Este proyecto cubre todo el espectro del NLP moderno:
- Procesamiento de texto crudo (scraping, parsing, normalización)
- Modelos de embedding biomédicos (transformers especializados)
- Búsqueda semántica vectorial
- Reranking con cross-encoders
- Generación con LLM
- Arquitectura RAG completa
- Evaluación cuantitativa con métricas establecidas

Además tiene relevancia real: el matching de pacientes a ensayos es un problema activo en oncología y farmacéutica, donde herramientas de este tipo pueden acelerar el reclutamiento y mejorar el acceso a tratamientos innovadores.

---

## Anexos

### Anexo A — Endpoints útiles de ClinicalTrials API

```
# Versión de la API
GET https://clinicaltrials.gov/api/v2/version

# Buscar por condición
GET https://clinicaltrials.gov/api/v2/studies?query.cond=diabetes&pageSize=10

# Un estudio específico
GET https://clinicaltrials.gov/api/v2/studies/NCT04280705

# Con campos específicos
GET https://clinicaltrials.gov/api/v2/studies?query.cond=diabetes&fields=NCTId,BriefTitle,EligibilityCriteria
```

### Anexo B — Modelos a evaluar

**Embeddings:**
- `neuml/pubmedbert-base-embeddings` (primera opción)
- `pritamdeka/S-PubMedBert-MS-MARCO`
- `BAAI/bge-large-en-v1.5`

**Reranking:**
- `cross-encoder/ms-marco-MiniLM-L-6-v2`
- `BAAI/bge-reranker-large`
- `pritamdeka/PubMedBERT-MNLI-MedNLI`

**NER biomédico (para normalización):**
- `d4data/biomedical-ner-all`
- `pruas/BENT-PubMedBERT-NER-Disease`

**LLM para generación:**
- API Anthropic (Claude)
- `mistralai/Mistral-7B-Instruct-v0.3`
- `meta-llama/Meta-Llama-3-8B-Instruct`

### Anexo C — Estado actual del proyecto

- ✅ Dataset descargado desde ClinicalTrials.gov (~439k estudios)
- ✅ Pipeline modular de descarga implementado
- ✅ Dataset subido a HuggingFace Hub (`OrneCorsetti/mcd-austral-clinical-trials`)
- ✅ Script de descarga reutilizable desde notebooks
- ✅ Diagrama de arquitectura definido
- ⏳ Próximo: normalización clínica y parseo inclusión/exclusión
