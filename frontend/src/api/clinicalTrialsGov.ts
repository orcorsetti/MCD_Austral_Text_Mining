import type { MatchConfidence, MatchResult, PatientProfile, TrialMatch } from '../types';
import { countFilledFields } from '../lib/completeness';
import type { TrialMatcher } from './matcher';

const API_BASE = 'https://clinicaltrials.gov/api/v2/studies';
const PAGE_SIZE = 10;

/** Maps form diagnosis labels to ClinicalTrials.gov search terms. */
const CONDITION_QUERY_MAP: Record<string, string> = {
  'Breast cancer – HR+/HER2–': 'breast cancer hormone receptor',
  'Breast cancer – HER2+': 'breast cancer HER2 positive',
  'Breast cancer – Triple negative (TNBC)': 'triple negative breast cancer',
  'NSCLC – adenocarcinoma': 'non-small cell lung cancer adenocarcinoma',
  'NSCLC – squamous': 'non-small cell lung cancer squamous',
  'Small cell lung cancer (SCLC)': 'small cell lung cancer',
  'Colorectal cancer (CRC)': 'colorectal cancer',
  'Gastric / GEJ cancer': 'gastric cancer',
  'Hepatocellular carcinoma (HCC)': 'hepatocellular carcinoma',
  'Pancreatic ductal adenocarcinoma (PDAC)': 'pancreatic cancer',
  'Ovarian / fallopian tube / peritoneal': 'ovarian cancer',
  'Prostate cancer – CRPC': 'castration-resistant prostate cancer',
  'Prostate cancer – HSPC': 'prostate cancer',
  'Urothelial / bladder cancer': 'urothelial carcinoma bladder',
  'Renal cell carcinoma (RCC)': 'renal cell carcinoma',
  'Melanoma – cutaneous': 'melanoma',
  'HNSCC': 'head neck squamous cell carcinoma',
  'Multiple myeloma': 'multiple myeloma',
  'DLBCL': 'diffuse large B-cell lymphoma',
};

/* ---- ClinicalTrials.gov v2 API response types (partial) ---- */

interface CtGovStudy {
  protocolSection?: {
    identificationModule?: { nctId?: string; briefTitle?: string };
    designModule?: { phases?: string[]; enrollmentInfo?: { count?: number } };
    eligibilityModule?: { eligibilityCriteria?: string };
    armsInterventionsModule?: { interventions?: { name?: string }[] };
    sponsorCollaboratorsModule?: { leadSponsor?: { name?: string } };
    contactsLocationsModule?: { locations?: { country?: string }[] };
  };
}

interface CtGovResponse {
  studies?: CtGovStudy[];
  totalCount?: number;
}

/* ---- Helpers ---- */

function buildConditionQuery(diagnosis: string): string {
  return (CONDITION_QUERY_MAP[diagnosis] || diagnosis || 'cancer').replace(/\s+/g, '+');
}

function parseCriteria(text: string, type: 'inclusion' | 'exclusion'): string[] {
  if (!text) return [];
  const lower = text.toLowerCase();
  const startKey = type === 'inclusion' ? 'inclusion criteria' : 'exclusion criteria';
  const endKey = type === 'inclusion' ? 'exclusion criteria' : null;
  const start = lower.indexOf(startKey);
  if (start === -1) return [];
  const end = endKey ? lower.indexOf(endKey, start + startKey.length) : undefined;
  const sub = text.slice(start + startKey.length, end === -1 ? undefined : end);
  return sub
    .split(/\n/)
    .map(s => s.replace(/^\s*[-*\d.]+\s*/, '').trim())
    .filter(s => s.length > 15 && s.length < 200)
    .slice(0, 6);
}

/**
 * Placeholder relevance scoring based on profile completeness plus per-card
 * variation. Real per-trial scores will come from the ML backend.
 */
const SCORE_NOISE = [0.15, -0.1, 0.05, -0.05, 0.1, -0.15, 0.08, -0.08, 0.12, -0.12];

function scoreTrial(profile: PatientProfile, index: number): number {
  const { filled, total } = countFilledFields(profile);
  const baseScore = filled / total;
  const noise = SCORE_NOISE[index % SCORE_NOISE.length];
  return Math.max(0.25, Math.min(0.98, baseScore + noise));
}

function confidenceForScore(score: number): MatchConfidence {
  if (score >= 0.75) return 'high';
  if (score >= 0.5) return 'mid';
  return 'low';
}

function toTrialMatch(study: CtGovStudy, profile: PatientProfile, index: number): TrialMatch {
  const proto = study.protocolSection ?? {};
  const id = proto.identificationModule ?? {};
  const design = proto.designModule ?? {};
  const criteria = proto.eligibilityModule?.eligibilityCriteria ?? '';
  const interventions = (proto.armsInterventionsModule?.interventions ?? [])
    .slice(0, 4)
    .map(i => i.name ?? '')
    .filter(Boolean);
  const locations = proto.contactsLocationsModule?.locations ?? [];
  const nctId = id.nctId ?? '';
  const score = scoreTrial(profile, index);

  return {
    nctId,
    title: id.briefTitle ?? 'Untitled study',
    phase: (design.phases ?? []).join(' / ') || '—',
    enrollment: design.enrollmentInfo?.count ?? null,
    interventions,
    inclusionCriteria: parseCriteria(criteria, 'inclusion').slice(0, 4),
    exclusionCriteria: parseCriteria(criteria, 'exclusion').slice(0, 3),
    sponsor: proto.sponsorCollaboratorsModule?.leadSponsor?.name ?? '—',
    siteCount: locations.length,
    localSiteCount: locations.filter(l => l.country === profile.country).length,
    matchScore: score,
    confidence: confidenceForScore(score),
    url: `https://clinicaltrials.gov/study/${nctId}`,
  };
}

/* ---- Matcher implementation ---- */

export const clinicalTrialsGovMatcher: TrialMatcher = {
  async match(profile: PatientProfile): Promise<MatchResult> {
    const params = new URLSearchParams({
      'query.cond': buildConditionQuery(profile.diagnosis),
      'filter.overallStatus': 'RECRUITING',
      pageSize: String(PAGE_SIZE),
      format: 'json',
      countTotal: 'true',
    });
    if (profile.biomarkers.length) {
      params.set('query.term', profile.biomarkers.join(' '));
    }

    const res = await fetch(`${API_BASE}?${params.toString()}`);
    if (!res.ok) throw new Error(`API error ${res.status}`);
    const data: CtGovResponse = await res.json();

    return {
      totalCount: data.totalCount ?? 0,
      trials: (data.studies ?? []).map((study, i) => toTrialMatch(study, profile, i)),
    };
  },
};
