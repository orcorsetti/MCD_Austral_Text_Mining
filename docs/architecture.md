# Arquitectura técnica

Detalle del pipeline RAG: mecánica de retrieval, scoring, decisiones de modelos y hallazgos.
Para el overview y cómo correrlo, ver el [README](../README.md).

---

## 1. Pipeline offline (construcción del índice)

Se corre una vez en los notebooks y produce los artefactos que consume la API.

1. **Descarga** (`02`): ClinicalTrials.gov API v2, ~84k estudios oncológicos, paginado.
   Campos crudos en `clinical_trials.parquet` (título, fases, criterios, locations, edades…).
2. **Parseo de elegibilidad** (`03`, `04`): separa el texto libre de `eligibilityCriteria`
   en listas de inclusión vs exclusión. **Regex primero; si falla, fallback a LLM.**
3. **Normalización clínica** (`05`): scispaCy + MeSH construye un `condition_text` unificado
   (mesh_terms > conditions > keywords) y enriquece los criterios.
4. **Embeddings** (`06`): un vector **por cada criterio individual** (no por estudio), lo que
   permite saber exactamente qué criterio matcheó. Se guardan como `.npy` + `_meta.parquet`
   alineados fila a fila.

| Artefacto | Shape | Una fila = | Modelo |
|---|---|---|---|
| `06_condition_embeddings.npy` | (83 962, 384) | condición de un estudio | bge-small-en-v1.5 |
| `06_inclusion_embeddings.npy` | (750 566, 768) | un criterio de inclusión | S-PubMedBert-MS-MARCO |
| `06_exclusion_embeddings.npy` | (678 985, 768) | un criterio de exclusión | S-PubMedBert-MS-MARCO |
| `05_trial_metadata.parquet`  | 83 962 filas | título/fases/intervenciones/países | — |

---

## 2. Pipeline online (por consulta)

Implementado en `src/pipeline.py::TrialMatcherEngine`. Es un **embudo retrieve-then-score**:
filtros baratos primero, scoring caro al final.

```
PatientProfile (form)
   │ patient_from_profile()   — pliega her2Status/hrStatus/… a biomarcadores
   ▼
2 queries → embeddings:  condición (384d)  +  criterios (768d)
   ▼
1. filter_studies()        status RECRUITING + edad (min_age + bucket std_ages)   [pandas]
2. condition_candidates()  dot(cond_q, condition_emb[eligibles]) → top-200         [exacto]
3. score_criteria()        dot(crit_q, inclusion_emb[candidatos]) → mean top-3     → reward
                           dot(crit_q, exclusion_emb[candidatos]) → mean top-3     → penalty
4. composite_score()       inclusión − 0.5·exclusión → shortlist top-50            [bi-encoder]
5. rerank (MedCPT)         dot conjunto (query, condición+criterios) → Score General
6. geo_score()             sitio en país del paciente → 1.0 ; en otro lado → 0.3
7. final = 0.8·reranker_norm + 0.2·geo  → top-10
8. /api/explain (on-demand) → explicación LLM por estudio
```

---

## 3. Mecánica de retrieval — *cómo se consultan los vectores*

**No hay base de datos vectorial ni índice ANN.** El retrieval es **búsqueda exacta por
producto punto en NumPy**: se codifica al paciente y se hace el dot product contra los
vectores guardados, ordenando por similitud.

Tres hechos lo hacen funcionar:

1. **El producto punto *es* la similitud coseno.** Todos los vectores se normalizan a norma 1
   al generarse (`normalize_embeddings=True`) y también la query. Para vectores unitarios,
   `cos(a, b) = a · b`. No hay paso de coseno aparte.

2. **Los vectores están en `.npy` memory-mapped.** `np.load(..., mmap_mode='r')` no carga todo
   a RAM; el SO pagina solo las filas que se tocan.

3. **Nunca se escanean los 750k vectores.** Por el embudo, los dot products corren sobre
   slices chicos. La operación real es una línea de álgebra:

```python
mask = meta['nct_id'].isin(candidate_ids).to_numpy()   # selector booleano (~200 estudios)
sims = np.asarray(emb[mask]) @ query_emb                # (n_subset, 768) · (768,) = (n_subset,)
# luego: agrupar por nct_id y promediar las top-3 similitudes
```

`emb[mask]` materializa solo las filas de los criterios candidatos desde el memmap; `@ query_emb`
da una similitud por criterio.

**Frase para el informe:** *el retrieval es búsqueda exacta por dot-product (coseno) sobre
embeddings normalizados guardados como arrays NumPy memory-mapped, aplicada a un conjunto de
candidatos producido por un filtro duro + un prefiltro grueso de condición — un embudo
retrieve-then-score, no un índice ANN.*

**vs. una vector DB (ChromaDB/FAISS):** agregarían un índice de vecinos **aproximados** (HNSW)
para evitar escanear todo — optimización de velocidad a escala de corpus completo, a cambio de
exactitud. Acá el prefiltro ya achica la búsqueda a ~200 estudios antes del scoring de 768d, así
que no hay nada que optimizar y se conservan scores exactos (recall 100%).

---

## 4. Scoring compuesto

- **Score bi-encoder (shortlist):** `inclusión − 0.5·exclusión`, donde cada término es el
  promedio de las top-3 similitudes de criterio del estudio. Selecciona los 50 candidatos a rerankear.
- **Score General (reranker):** logit de MedCPT-Cross-Encoder sobre el par
  (query concisa, `condition_text + top-3 criterios de inclusión`), normalizado min-max a 0-1
  dentro del shortlist.
- **Score geográfico:** tier por país (1.0 en país del paciente, 0.3 si recluta en otro lado, 0 si no).
- **Final:** `0.8 · reranker + 0.2 · geo`, clampeado a [0,1]. La confianza (high/mid/low) se deriva del final.

---

## 5. Explicación LLM (Qwen local)

Desacoplada de la búsqueda: `/api/match` vuelve rápido (~3-4s) y cada tarjeta pide su explicación
on-demand a `/api/explain` (botón "Why does this match?"). Razones y detalles en
[hallazgos](#6-hallazgos-y-decisiones).

El prompt incluye el resumen del paciente, los criterios de inclusión/exclusión que matchearon,
y los **campos faltantes del formulario** (para que el LLM sugiera qué confirmar). Es fail-soft:
si el LLM local no responde, la búsqueda igual devuelve resultados sin explicación.

---

## 6. Hallazgos y decisiones

- **Reranker:** el `cross-encoder/ms-marco-MiniLM` del diagrama **no discrimina sobre texto
  clínico** (colapsa a ~0 o satura a 0.99). Se reemplazó por **`ncbi/MedCPT-Cross-Encoder`**
  (reranker biomédico query→artículo), que sí da un spread real de relevancia.
- **LLM Qwen3.6:** el razonamiento está ON por defecto y `/no_think`, `enable_thinking:false` y
  `reasoning_effort` **se ignoran** (razona hasta agotar `max_tokens`). La única forma confiable de
  desactivarlo es **prefillear el turno del assistant con `<think></think>`** (66s → 2s).
- **Explicaciones on-demand:** una sola GPU + un LLM 27B local no sirven explicaciones en paralelo
  (4 requests concurrentes a `/api/explain` dieron timeout). Por eso no se auto-generan en la
  búsqueda; cada tarjeta las pide por botón, y un `threading.Lock` serializa el acceso a GPU.

---

## 7. Limitaciones de datos

- `05_clinical_trials_normalized.parquet` **no tiene columna de sexo ni de país/coordenadas**, así
  que el filtro por sexo y un geo-score por distancia no son posibles con los datos actuales
  (el geo-score usa los países de los sitios).
- `enrollment` y `sponsor` no se descargaron en el notebook 02 (faltan en `FIELDS`); las tarjetas
  los muestran como `—`. Se completan agregando 2 campos y re-corriendo la descarga.
- El reranker es aproximado a nivel de qué criterios representan al estudio (top-3), no exhaustivo.

---

## 8. Pendientes (vs. diagrama)

| Gap | Qué falta |
|---|---|
| Filtro duro por ECOG | extraer el umbral de ECOG del texto de criterios (offline, regex+LLM) |
| `enrollment` / `sponsor` | agregar `EnrollmentCount`/`LeadSponsorName` a `FIELDS` (nb 02) y re-bajar |
| N-por-request | pasar `topN` desde el form al endpoint |
| ChromaDB | reemplazar el índice numpy por colecciones persistentes (lateral; ver §3) |
| Evaluación RAGAS | requiere un set de ground truth paciente→ensayo |
