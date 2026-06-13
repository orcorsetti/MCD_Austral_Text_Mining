# Contexto del proyecto — MCD Austral Text Mining

## Proyecto: Sistema RAG para Matching de Pacientes a Ensayos Clínicos

Proyecto integrador final — Materia de Text Mining / NLP  
Maestría en Ciencia de Datos · Universidad Austral

### Objetivo
Sistema RAG (Retrieval Augmented Generation) que, dado el perfil clínico de un paciente, identifica los ensayos clínicos disponibles a nivel mundial que mejor aplican a su caso. Combina retrieval híbrido, scoring compuesto y generación contextualizada para producir recomendaciones explicables.

### Estado actual
- ✅ Dataset descargado desde ClinicalTrials.gov (~439k estudios)
- ✅ Pipeline modular de descarga implementado
- ✅ Dataset subido a HuggingFace Hub (`OrneCorsetti/mcd-austral-clinical-trials`)
- ✅ Script de descarga reutilizable desde notebooks
- ⏳ Próximo: normalización clínica y parseo inclusión/exclusión

---

## Arquitectura general

### Pipeline offline (una sola vez)
1. Descarga desde ClinicalTrials.gov API v2
2. Normalización clínica con scispaCy (→ MeSH)
3. Parseo de criterios: separación inclusión vs exclusión
4. Generación de embeddings por criterio individual (`neuml/pubmedbert-base-embeddings`)
5. Persistencia en ChromaDB + parquet en HuggingFace

### Pipeline online (por consulta)
1. Formulario del paciente (texto libre estructurado)
2. Embedding del perfil (mismo modelo que offline)
3. Filtros duros: edad, sexo, status RECRUITING
4. Búsqueda semántica contra colección de inclusión (→ top 50)
5. Penalización por exclusión semántica
6. Re-ranking con cross-encoder
7. Scoring compuesto: `score_final = w1 × score_reranker + w2 × score_geográfico`
8. Top-N estudios → LLM genera explicación
9. JSON de respuesta al frontend

---

## Stack tecnológico

| Componente | Tecnología |
|---|---|
| API de datos | ClinicalTrials.gov API v2 |
| Lenguaje | Python |
| Procesamiento | pandas, pyarrow |
| Normalización clínica | scispaCy + UMLS |
| Embeddings | sentence-transformers (`neuml/pubmedbert-base-embeddings`) |
| Vector store | ChromaDB (dos colecciones: inclusión / exclusión) |
| Reranking | cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) |
| LLM | API de Anthropic (Claude) / Mistral 7B local |
| Versionado de datos | HuggingFace Hub |
| Evaluación | RAGAS |
| Frontend (opcional) | Streamlit |

---

## Estructura del proyecto

```
clinical-trials-rag/
├── data/
│   └── clinical_trials.parquet
├── utils/
│   ├── 00_download_parquet.py
│   └── build_dataset.py
├── notebooks/
│   ├── 01_get_clinicaltrials.ipynb
│   ├── 02_parse_eligibility.ipynb
│   ├── 03_generate_embeddings.ipynb
│   ├── 04_build_vector_store.ipynb
│   ├── 05_retrieval_pipeline.ipynb
│   └── 06_evaluation.ipynb
├── src/
│   ├── retrieval.py
│   ├── scoring.py
│   ├── llm_generation.py
│   └── pipeline.py
└── app/
    └── streamlit_app.py
```

---

## Convenciones de código

### Filosofía
Código limpio y simple por sobre robusto. Proyecto académico: priorizar claridad sobre defensividad.

### Reglas guía
- Una función = una responsabilidad (si la descripción necesita "y", se parte)
- Separar I/O de lógica
- Funciones cortas (~30 líneas máximo)
- Funciones puras siempre que se pueda (inputs/outputs explícitos, sin estado global)
- Orquestación lineal al final del notebook/script

### Estilo
- Type hints en todos los parámetros y retornos
- Docstring de una línea por función
- Nombres descriptivos (`studies_df`, no `df` cuando hay varios DataFrames)
- Constantes en MAYÚSCULAS al principio del archivo

### Qué NO hacer
- Sin try/except defensivos (que crashee con stack trace claro)
- Sin validación de inputs innecesaria
- Sin clases si no hay estado real que mantener
- Sin patrones de diseño rebuscados
- Sin logging complejo (`print()` alcanza en notebooks)
- Sin configuración externa (constantes en el archivo)

### Excepciones
- try/except sí: bucles de paginación o retry intencional, datasets grandes
- Clases sí: cliente ChromaDB, modelo sentence-transformer cargado
- Variables de entorno: credenciales y paths que cambian entre máquinas

### Persistencia de datos
- **parquet** para todo (no CSV ni JSON salvo necesidad puntual)
- **HuggingFace Hub** para datasets grandes versionados
- **Paths** con `pathlib.Path`, no strings

### API calls
- `requests` directo, sin clientes envueltos
- `response.raise_for_status()` después de cada call
- Paginación en while loop, no recursión

### Modelos NLP
- Cargar el modelo una sola vez por notebook, no en cada función
- Batching cuando se procesan muchos textos

### ChromaDB
- Una colección por tipo lógico (inclusión, exclusión)
- Metadata mínima en el store, datos completos en parquet

### Ejemplo canónico de función
```python
def fetch_studies(condition: str, max_studies: int = 100) -> list[dict]:
    """Descarga estudios paginando hasta alcanzar el máximo."""
    all_studies = []
    page_token = None

    while len(all_studies) < max_studies:
        params = {
            "query.cond": condition,
            "pageSize":   min(100, max_studies),
            "format":     "json",
        }
        if page_token:
            params["pageToken"] = page_token

        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()

        studies = data.get("studies", [])
        if not studies:
            break

        all_studies.extend(studies)
        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return all_studies[:max_studies]
```

### Ejemplo canónico de pipeline
```python
raw = fetch_studies(condition="diabetes", max_studies=200)
df  = to_dataframe(raw)
df  = normalize_conditions(df)
df.to_parquet("../data/diabetes_studies.parquet", index=False)
print(f"Total: {len(df)} estudios")
```
