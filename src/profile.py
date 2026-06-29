"""Perfil del paciente y adaptacion desde el formulario del frontend (PatientProfile)."""
import re
from dataclasses import dataclass, field

# Diagnostico del form -> palabras clave que deben aparecer en condition_text/titulo (gate v2).
DISEASE_KEYWORDS = {
    'nsclc': ['lung'], 'sclc': ['lung'], 'lung': ['lung'], 'mesothelioma': ['mesotheli'],
    'breast': ['breast'],
    'colorectal': ['colorectal', 'colon', 'rectal'], 'crc': ['colorectal', 'colon', 'rectal'],
    'gastric': ['gastric', 'stomach', 'gastroesophageal'], 'gej': ['gastric', 'gastroesophageal'],
    'hepatocellular': ['hepatocellular', 'liver'], 'hcc': ['hepatocellular', 'liver'],
    'pancrea': ['pancrea'], 'cholangio': ['cholangio', 'biliary'], 'biliary': ['biliary', 'cholangio'],
    'esophageal': ['esophag'],
    'prostate': ['prostate'], 'urothelial': ['urotheli', 'bladder'], 'bladder': ['bladder', 'urotheli'],
    'renal': ['renal', 'kidney'], 'rcc': ['renal', 'kidney'],
    'cervical': ['cervic'], 'endometrial': ['endometrial', 'uterine'], 'uterine': ['uterine', 'endometrial'],
    'ovarian': ['ovarian', 'fallopian', 'peritoneal'],
    'melanoma': ['melanoma'], 'hnscc': ['head and neck', 'neck'],
    'thyroid': ['thyroid'], 'sarcoma': ['sarcoma'], 'glioblastoma': ['glioblastoma', 'glioma'], 'gbm': ['glioblastoma', 'glioma'],
    'neuroendocrine': ['neuroendocrine'], 'net': ['neuroendocrine'],
    'dlbcl': ['lymphoma'], 'lymphoma': ['lymphoma'], 'myeloma': ['myeloma'],
    'aml': ['myeloid leukemia'], 'cll': ['lymphocytic leukemia'], 'cml': ['myeloid leukemia'],
}


def disease_keywords(diagnosis: str) -> list:
    """Palabras clave de enfermedad para el gate lexico (mapa + fallback a palabras del diagnostico)."""
    d = diagnosis.lower()
    for key, kws in DISEASE_KEYWORDS.items():
        if key in d:
            return kws
    return [w for w in re.findall(r'[a-z]+', d) if len(w) > 3]

@dataclass
class Patient:
    """Perfil clinico del paciente para el matching (espeja el formulario del frontend)."""
    age: int
    sex: str = ''
    diagnosis: str = ''
    histology: str = ''
    setting: str = ''
    biomarkers: list[str] = field(default_factory=list)
    ecog: str = ''
    comorbidities: list[str] = field(default_factory=list)
    tx_setting: str = ''
    prior_lines: str = ''
    prior_treatment_classes: list[str] = field(default_factory=list)
    phases: list[str] = field(default_factory=list)
    intervention_types: list[str] = field(default_factory=list)
    free_text: str = ''
    country: str = ''


# Tipo de intervencion del form -> keywords a buscar en arm labels + titulo.
# Heuristico por texto (no tenemos el InterventionType estructurado de CT.gov).
# 'Drug / biologic' no tiene keywords a proposito: es demasiado amplio, no filtra.
INTERVENTION_KEYWORDS = {
    'Radiation': ['radiation', 'radiother', 'radiotherapy', 'sbrt', 'stereotactic', 'brachytherap', 'proton'],
    'Immunotherapy': [
        'immunother', 'immune checkpoint', 'checkpoint', 'pd-1', 'pd-l1', 'pd1', 'pdl1',
        'pembrolizumab', 'nivolumab', 'atezolizumab', 'durvalumab', 'ipilimumab', 'tremelimumab',
        'cemiplimab', 'tislelizumab', 'sintilimab', 'vaccine',
    ],
    'Cell therapy': ['car-t', 'car t', 'cart cell', 'cell therapy', 'tils', 'til ', 'nk cell', 'tcr-t', 'adoptive cell'],
}


def requested_intervention_keywords(types: list) -> list:
    """Keywords de las modalidades especificas pedidas (Drug/biologic se ignora: no filtra)."""
    kws = []
    for t in types:
        kws += INTERVENTION_KEYWORDS.get(t, [])
    return kws


# Fase del form -> tokens de fase de ClinicalTrials.gov (en metadata_df['phases']).
FORM_PHASE_MAP = {
    'Phase I':   {'PHASE1', 'EARLY_PHASE1'},
    'Phase II':  {'PHASE2'},
    'Phase III': {'PHASE3'},
    'Phase IV':  {'PHASE4'},
}


def requested_phase_tokens(phases: list) -> set:
    """Tokens de fase pedidos (vacio = sin filtro de fase)."""
    tokens = set()
    for p in phases:
        tokens |= FORM_PHASE_MAP.get(p, set())
    return tokens


def patient_from_profile(profile: dict) -> Patient:
    """Adapta el PatientProfile del frontend al Patient del pipeline."""
    age_raw = str(profile.get('age', '')).strip()
    return Patient(
        age=int(age_raw) if age_raw.isdigit() else 0,
        sex=profile.get('sex', ''),
        diagnosis=profile.get('diagnosis', ''),
        histology=profile.get('histology', ''),
        setting=profile.get('diseaseSetting', ''),
        biomarkers=profile.get('biomarkers', []),
        ecog=profile.get('ecog') or '',
        comorbidities=profile.get('comorbidities', []),
        tx_setting=profile.get('treatmentSetting', ''),
        prior_lines=profile.get('priorLines', ''),
        prior_treatment_classes=profile.get('priorTreatmentClasses', []),
        phases=profile.get('phases', []),
        intervention_types=profile.get('interventionTypes', []),
        free_text=profile.get('freeText', ''),
        country=profile.get('country', ''),
    )


# Campos clave del formulario para la explicacion del LLM (label -> getter).
KEY_FIELDS = {
    'country': 'country', 'age': 'age', 'sex': 'sex', 'diagnosis': 'diagnosis',
    'disease setting': 'diseaseSetting', 'ECOG': 'ecog',
    'treatment setting': 'treatmentSetting', 'prior lines': 'priorLines',
}


def missing_fields(profile: dict) -> list:
    """Campos clave del formulario que el paciente dejo vacios (para el LLM)."""
    return [label for label, key in KEY_FIELDS.items() if not str(profile.get(key) or '').strip()]


def patient_summary(patient: Patient) -> str:
    """Resumen compacto del paciente para el prompt del LLM."""
    return build_criteria_query(patient)


def build_condition_query(patient: Patient) -> str:
    """Texto para el filtro de condicion: diagnostico + histologia + biomarcadores."""
    parts = [patient.diagnosis, patient.histology, *patient.biomarkers]
    return ' '.join(p for p in parts if p)


def build_rerank_query(patient: Patient) -> str:
    """Consulta concisa para el cross-encoder (diagnostico + histologia + setting + biomarcadores)."""
    parts = [patient.diagnosis, patient.histology, patient.setting, *patient.biomarkers]
    return ' '.join(p for p in parts if p)


def build_criteria_query(patient: Patient) -> str:
    """Perfil clinico en lenguaje natural para matchear contra criterios de elegibilidad."""
    lines = [
        f'{patient.age} year old {patient.sex.lower()} patient.'.strip(),
        f'Diagnosis: {patient.diagnosis}.',
    ]
    if patient.histology:               lines.append(f'Histology: {patient.histology}.')
    if patient.setting:                 lines.append(f'Disease setting: {patient.setting}.')
    if patient.biomarkers:              lines.append(f'Biomarkers: {", ".join(patient.biomarkers)}.')
    if patient.ecog:                    lines.append(f'ECOG performance status {patient.ecog}.')
    if patient.comorbidities:           lines.append(f'Comorbidities: {", ".join(patient.comorbidities)}.')
    if patient.tx_setting:              lines.append(f'Treatment intent: {patient.tx_setting}.')
    if patient.prior_lines:             lines.append(f'Prior therapy lines: {patient.prior_lines}.')
    if patient.prior_treatment_classes: lines.append(f'Prior treatments: {", ".join(patient.prior_treatment_classes)}.')
    if patient.free_text:               lines.append(patient.free_text)
    return ' '.join(lines)
