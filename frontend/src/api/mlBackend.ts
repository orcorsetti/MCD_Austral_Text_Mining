import type { MatchResult, PatientProfile } from '../types';
import type { ScoringVariant, TrialMatcher } from './matcher';

/**
 * ML backend: POSTs the patient profile to the RAG matching service
 * (FastAPI + semantic retrieval over ClinicalTrials.gov embeddings) and
 * returns ranked, real-scored matches conforming to MatchResult.
 *
 * The request is proxied to the Python service (see vite.config.ts -> /api).
 */
export const mlMatcher: TrialMatcher = {
  async match(profile: PatientProfile, variant: ScoringVariant = 'v2', topN = 10): Promise<MatchResult> {
    const res = await fetch(`/api/match?variant=${variant}&top_n=${topN}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(profile),
    });
    if (!res.ok) throw new Error(`API error ${res.status}`);
    return res.json();
  },
};

/**
 * Lazily fetch the LLM eligibility explanation for one trial. Kept separate from
 * match() so search returns fast and explanations stream in per card.
 */
export async function explainTrial(profile: PatientProfile, nctId: string): Promise<string> {
  const res = await fetch('/api/explain', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ profile, nctId }),
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  const data: { explanation: string } = await res.json();
  return data.explanation;
}
