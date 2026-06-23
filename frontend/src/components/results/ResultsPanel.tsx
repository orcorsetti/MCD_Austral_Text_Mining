import type { PatientProfile, SearchState } from '../../types';
import { computeCompleteness, computeConfidence } from '../../lib/completeness';
import { EmptyState } from './EmptyState';
import { LoadingIndicator } from './LoadingIndicator';
import { ConfidenceBanner } from './ConfidenceBanner';
import { TrialCard } from './TrialCard';

interface ResultsPanelProps {
  searchState: SearchState;
  /** The profile snapshot used for the last search. */
  searchedProfile: PatientProfile | null;
}

export function ResultsPanel({ searchState, searchedProfile }: ResultsPanelProps) {
  return (
    <main className="results-panel">
      {searchState.status === 'idle' && <EmptyState />}

      {searchState.status === 'loading' && <LoadingIndicator />}

      {searchState.status === 'error' && (
        <div
          style={{
            background: 'var(--red-light)',
            color: 'var(--red)',
            border: '1px solid rgba(192,57,43,0.2)',
            borderRadius: 'var(--radius)',
            padding: '14px 16px',
            fontSize: 13,
          }}
        >
          <strong>Connection error:</strong> Could not reach ClinicalTrials.gov API. Please check
          your internet connection and try again.
          <br />
          <span style={{ fontSize: 11, opacity: 0.7, marginTop: 4, display: 'block' }}>
            {searchState.message}
          </span>
        </div>
      )}

      {searchState.status === 'success' && searchedProfile && (
        <>
          <div className="results-header">
            <div>
              <p className="results-title">
                Found <em>{searchState.result.totalCount.toLocaleString()}</em> recruiting trials
              </p>
              <p style={{ fontSize: 13, color: 'var(--ink-tertiary)', marginTop: 4 }}>
                Showing {searchState.result.trials.length} · {searchedProfile.diagnosis}
              </p>
            </div>
          </div>

          <ConfidenceBanner
            confidence={computeConfidence(searchedProfile)}
            missingFields={computeCompleteness(searchedProfile).missingRequired}
          />

          {searchState.result.trials.length === 0 && (
            <p style={{ color: 'var(--ink-tertiary)', fontSize: 13 }}>
              No recruiting trials found for this query. Try broadening the search criteria.
            </p>
          )}

          {searchState.result.trials.map(trial => (
            <TrialCard key={trial.nctId} trial={trial} profile={searchedProfile} />
          ))}
        </>
      )}
    </main>
  );
}
