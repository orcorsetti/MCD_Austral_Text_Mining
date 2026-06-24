/** Patient profile captured by the sidebar form. */
export interface PatientProfile {
  // Location & demographics
  country: string;
  age: string;
  sex: string;
  // Diagnosis
  diagnosis: string;
  histology: string;
  diseaseSetting: string;
  studyType: string;
  // Molecular profile
  biomarkers: string[];
  // Performance status
  ecog: string | null;
  comorbidities: string[];
  // Treatment history
  treatmentSetting: string;
  priorLines: string;
  priorTreatmentClasses: string[];
  // Trial preferences
  phases: string[];
  interventionTypes: string[];
  // Additional details
  freeText: string;
}

export const EMPTY_PROFILE: PatientProfile = {
  country: '',
  age: '',
  sex: '',
  diagnosis: '',
  histology: '',
  diseaseSetting: '',
  studyType: '',
  biomarkers: [],
  ecog: null,
  comorbidities: [],
  treatmentSetting: '',
  priorLines: '',
  priorTreatmentClasses: [],
  phases: ['Phase III'],
  interventionTypes: ['Drug / biologic'],
  freeText: '',
};

export type MatchConfidence = 'high' | 'mid' | 'low';

/** A single trial returned by a matcher backend. */
export interface TrialMatch {
  nctId: string;
  title: string;
  phase: string;
  enrollment: number | null;
  interventions: string[];
  inclusionCriteria: string[];
  exclusionCriteria: string[];
  sponsor: string;
  siteCount: number;
  /** Sites located in the patient's country. */
  localSiteCount: number;
  /** Distinct countries with sites (for the "no local sites" flag). */
  siteCountries?: string[];
  /** 0–1 relevance score for this patient profile. */
  matchScore: number;
  confidence: MatchConfidence;
  /** LLM-generated rationale for why this trial fits the patient. */
  explanation?: string;
  url: string;
}

/** Response shape every matcher backend must return. */
export interface MatchResult {
  totalCount: number;
  trials: TrialMatch[];
}

export type SearchState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'success'; result: MatchResult };
