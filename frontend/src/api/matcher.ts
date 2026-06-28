import type { MatchResult, PatientProfile } from '../types';

/** Scoring variant: 'v1' = original pipeline, 'v2' = disease-gated + MedCPT. */
export type ScoringVariant = 'v1' | 'v2';

/**
 * Contract every matching backend must implement.
 *
 * The app is wired against this interface, so the data source can be swapped
 * without touching any UI code:
 *  - `clinicalTrialsGov.ts` — queries the public ClinicalTrials.gov v2 API (current).
 *  - a future `mlBackend.ts` — POSTs the profile to a machine-learning service
 *    (e.g. FastAPI + RAG pipeline) and returns ranked, scored matches.
 */
export interface TrialMatcher {
  match(profile: PatientProfile, variant?: ScoringVariant, topN?: number): Promise<MatchResult>;
}
