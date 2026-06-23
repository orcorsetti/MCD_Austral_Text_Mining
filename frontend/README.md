# TrialMatch — Oncology Clinical Trial Finder

React + TypeScript webapp for matching oncology patients to recruiting clinical trials.
Converted from the original single-file HTML prototype.

## Run

```bash
npm install
npm run dev      # development server
npm run build    # production build (dist/)
```

## Architecture

```
src/
├── types.ts                     # PatientProfile, TrialMatch, MatchResult — the API contract
├── data/
│   └── formOptions.ts           # Diagnoses, biomarkers, comorbidities, treatment classes...
├── lib/
│   └── completeness.ts          # Profile completeness scoring + search confidence
├── api/
│   ├── matcher.ts               # TrialMatcher interface  ← ML backend swap point
│   └── clinicalTrialsGov.ts     # Current implementation: ClinicalTrials.gov v2 API
├── components/
│   ├── Header.tsx
│   ├── sidebar/                 # Patient profile form
│   │   ├── Sidebar.tsx
│   │   ├── CompletenessBar.tsx
│   │   ├── FormSection.tsx
│   │   ├── fields.tsx           # Field / SelectField / TextField
│   │   ├── ChipGroup.tsx        # Single- and multi-select chips
│   │   └── BiomarkerInput.tsx   # Tag-style biomarker input
│   └── results/                 # Search results
│       ├── ResultsPanel.tsx
│       ├── ConfidenceBanner.tsx
│       ├── TrialCard.tsx
│       ├── EmptyState.tsx
│       └── LoadingIndicator.tsx
└── App.tsx                      # State: profile + search lifecycle
```

## Connecting a machine-learning backend

The app is wired against the `TrialMatcher` interface (`src/api/matcher.ts`):

```ts
interface TrialMatcher {
  match(profile: PatientProfile): Promise<MatchResult>;
}
```

`App.tsx` currently uses `clinicalTrialsGovMatcher`, which queries the public
ClinicalTrials.gov API and assigns **placeholder** match scores based on profile
completeness.

To plug in an ML model (e.g. a RAG pipeline / fine-tuned matcher served by FastAPI):

1. Create `src/api/mlBackend.ts`:

   ```ts
   export const mlMatcher: TrialMatcher = {
     async match(profile) {
       const res = await fetch('/api/match', {
         method: 'POST',
         headers: { 'Content-Type': 'application/json' },
         body: JSON.stringify(profile),
       });
       if (!res.ok) throw new Error(`API error ${res.status}`);
       return res.json(); // must conform to MatchResult
     },
   };
   ```

2. Swap one line in `App.tsx`:

   ```ts
   const matcher = mlMatcher;
   ```

The backend's response must conform to `MatchResult` (`src/types.ts`): a ranked list of
trials, each with a real `matchScore` (0–1), `confidence`, and parsed inclusion/exclusion
criteria. Nothing else in the UI changes.
