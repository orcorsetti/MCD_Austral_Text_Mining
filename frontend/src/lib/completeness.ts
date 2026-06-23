import type { MatchConfidence, PatientProfile } from '../types';

interface ScoredField {
  label: string;
  weight: number;
  required: boolean;
  isFilled: (p: PatientProfile) => boolean;
}

const FIELDS: ScoredField[] = [
  { label: 'Country', weight: 15, required: true, isFilled: p => p.country !== '' },
  { label: 'Diagnosis', weight: 25, required: true, isFilled: p => p.diagnosis !== '' },
  { label: 'Disease setting', weight: 15, required: true, isFilled: p => p.diseaseSetting !== '' },
  { label: 'Treatment setting', weight: 15, required: true, isFilled: p => p.treatmentSetting !== '' },
  { label: 'ECOG PS', weight: 15, required: true, isFilled: p => p.ecog !== null },
  { label: 'Prior lines', weight: 5, required: false, isFilled: p => p.priorLines !== '' },
  { label: 'Age', weight: 5, required: false, isFilled: p => p.age.trim() !== '' },
  { label: 'Free-text details', weight: 5, required: false, isFilled: p => p.freeText.trim() !== '' },
];

export interface Completeness {
  /** 0–100 */
  percent: number;
  missingRequired: string[];
}

export function computeCompleteness(profile: PatientProfile): Completeness {
  let score = 0;
  const missingRequired: string[] = [];

  for (const field of FIELDS) {
    if (field.isFilled(profile)) score += field.weight;
    else if (field.required) missingRequired.push(field.label);
  }
  if (profile.biomarkers.length > 0) score += 5;

  return { percent: Math.min(score, 100), missingRequired };
}

/** Number of profile inputs counted toward match confidence (form fields + biomarkers). */
export function countFilledFields(profile: PatientProfile): { filled: number; total: number } {
  const filled =
    FIELDS.filter(f => f.isFilled(profile)).length + (profile.biomarkers.length > 0 ? 1 : 0);
  return { filled, total: FIELDS.length + 1 };
}

/** Overall confidence of a search given how complete the profile is. */
export function computeConfidence(profile: PatientProfile): MatchConfidence {
  const { filled, total } = countFilledFields(profile);
  const ratio = filled / total;
  if (ratio >= 0.8) return 'high';
  if (ratio >= 0.5) return 'mid';
  return 'low';
}
