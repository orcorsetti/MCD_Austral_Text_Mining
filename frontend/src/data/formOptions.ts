export const COUNTRIES = [
  'Argentina', 'Australia', 'Brazil', 'Canada', 'Chile', 'Colombia',
  'France', 'Germany', 'Israel', 'Italy', 'Japan', 'Mexico',
  'Netherlands', 'South Korea', 'Spain', 'United Kingdom', 'United States',
];

export const SEX_OPTIONS = ['Female', 'Male'];

export interface DiagnosisGroup {
  label: string;
  options: string[];
}

export const DIAGNOSIS_GROUPS: DiagnosisGroup[] = [
  {
    label: 'Breast',
    options: [
      'Breast cancer – HR+/HER2–',
      'Breast cancer – HER2+',
      'Breast cancer – Triple negative (TNBC)',
      'Breast cancer – inflammatory',
    ],
  },
  {
    label: 'Thoracic',
    options: [
      'NSCLC',
      'Small cell lung cancer (SCLC)',
      'Mesothelioma',
    ],
  },
  {
    label: 'GI',
    options: [
      'Colorectal cancer (CRC)',
      'Gastric / GEJ cancer',
      'Hepatocellular carcinoma (HCC)',
      'Pancreatic ductal adenocarcinoma (PDAC)',
      'Cholangiocarcinoma / biliary tract',
      'Esophageal cancer',
    ],
  },
  {
    label: 'GU',
    options: [
      'Prostate cancer – HSPC',
      'Prostate cancer – CRPC',
      'Urothelial / bladder cancer',
      'Renal cell carcinoma (RCC)',
      'Cervical cancer',
      'Endometrial / uterine cancer',
      'Ovarian / fallopian tube / peritoneal',
    ],
  },
  {
    label: 'Hematologic',
    options: [
      'DLBCL', 'Follicular lymphoma', 'Hodgkin lymphoma', 'Mantle cell lymphoma',
      'Multiple myeloma', 'AML', 'CLL', 'CML',
    ],
  },
  {
    label: 'Other solid tumors',
    options: [
      'Melanoma – cutaneous',
      'Melanoma – uveal',
      'HNSCC',
      'Thyroid cancer',
      'Soft tissue sarcoma',
      'Glioblastoma (GBM)',
      'Neuroendocrine tumor (NET)',
    ],
  },
  {
    label: 'Agnostic',
    options: [
      'Tumor agnostic – MSI-H / dMMR',
      'Tumor agnostic – NTRK fusion',
    ],
  },
  {
    label: 'Other',
    options: ['Other (rare / not listed)'],
  },
];

export const DISEASE_SETTINGS = ['Localized', 'Locally advanced', 'Metastatic / advanced'];

// Tipo de estudio / propósito. Por ahora solo es campo de formulario (no filtra todavía).
export const STUDY_TYPES = [
  'Treatment',
  'Diagnostic',
  'Palliative / supportive care',
  'Rehabilitation',
  'Chemotherapy',
  'Surgery',
  'Prevention',
  'Screening',
  'Other',
];

export const BIOMARKER_HINT =
  'EGFR · ALK · KRAS G12C · BRCA1/2 · HER2 · PD-L1 · MSI-H · BRAF V600E · PIK3CA · NTRK · RET';

export interface EcogOption {
  value: string;
  warn: boolean;
}

export const ECOG_OPTIONS: EcogOption[] = [
  { value: '0', warn: false },
  { value: '1', warn: false },
  { value: '2', warn: false },
  { value: '3', warn: true },
  { value: '4', warn: true },
];

export const COMORBIDITIES = [
  'Active CNS metastases',
  'Leptomeningeal disease',
  'Autoimmune disease',
  'Prior organ transplant',
  'Hepatic impairment',
  'Renal impairment',
  'HIV / HBV / HCV',
  'Cardiac disease',
  'Prior ILD / pneumonitis',
  'Pregnancy',
];

export const TREATMENT_SETTINGS = [
  'Neoadjuvant',
  'Adjuvant',
  'Consolidative',
  'Metastatic – 1L (naive)',
  'Metastatic – 2L',
  'Metastatic – 3L+',
];

export const PRIOR_LINES_OPTIONS = ['0 (treatment-naive)', '1', '2', '3+'];

export const TREATMENT_CLASSES = [
  'Platinum', 'Taxane', 'Anthracycline', 'Anti-HER2', 'CDK4/6i', 'Anti-VEGF',
  'Checkpoint inhibitor', 'PARP inhibitor', 'ADC', 'EGFR TKI',
  'ALK / ROS1 inhibitor', 'CAR-T', 'Stem cell transplant', 'Radiation',
];

export const TRIAL_PHASES = ['Phase I', 'Phase II', 'Phase III', 'Phase IV'];

export const INTERVENTION_TYPES = ['Drug / biologic', 'Immunotherapy', 'Cell therapy', 'Radiation'];
