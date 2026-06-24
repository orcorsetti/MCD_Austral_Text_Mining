import { useState } from 'react';
import type { PatientProfile, TrialMatch } from '../../types';
import { explainTrial } from '../../api/mlBackend';

interface TrialCardProps {
  trial: TrialMatch;
  /** The searched profile, used to lazily fetch this trial's explanation. */
  profile: PatientProfile;
}

const CONF_LABEL = {
  high: '✓ High confidence',
  mid: '⚠ Partial match',
  low: '? Unverified',
} as const;

const CONF_CLASS = {
  high: 'conf-high',
  mid: 'conf-mid',
  low: 'conf-low',
} as const;

export function TrialCard({ trial, profile }: TrialCardProps) {
  const country = profile.country;
  const scorePercent = Math.round(trial.matchScore * 100);

  const [explanation, setExplanation] = useState(trial.explanation ?? '');
  const [loadingExplanation, setLoadingExplanation] = useState(false);

  const handleExplain = () => {
    setLoadingExplanation(true);
    explainTrial(profile, trial.nctId)
      .then(setExplanation)
      .catch(() => setExplanation('Explanation unavailable — is the local LLM running?'))
      .finally(() => setLoadingExplanation(false));
  };

  return (
    <div className={`trial-card ${trial.confidence}-conf`}>
      <div className="card-top">
        <p className="card-title">{trial.title}</p>
        <span className={`conf-badge ${CONF_CLASS[trial.confidence]}`}>
          {CONF_LABEL[trial.confidence]}
        </span>
      </div>

      <div className="card-meta">
        <span className="badge badge-nct">{trial.nctId}</span>
        <span className="badge">{trial.phase}</span>
        <span className="badge">
          N = {trial.enrollment != null ? trial.enrollment.toLocaleString() : '—'}
        </span>
        {trial.siteCount > 0 && (
          <span className="badge">
            📍 {trial.siteCount} sites
            {trial.localSiteCount > 0 && ` · ${trial.localSiteCount} in ${country}`}
          </span>
        )}
        {trial.siteCount > 0 && trial.localSiteCount === 0 && (
          <span
            className="badge"
            style={{ background: 'rgba(217,119,6,0.12)', color: '#b45309', border: '1px solid rgba(217,119,6,0.3)' }}
          >
            🌐 No sites in {country || 'your country'}
            {trial.siteCountries?.length ? ` · ${trial.siteCountries.slice(0, 3).join(', ')}` : ''}
          </span>
        )}
      </div>

      <div className="score-bar-wrap">
        <span className="score-label">Match score</span>
        <div className="score-track">
          <div className="score-fill" style={{ width: `${scorePercent}%` }} />
        </div>
        <span className="score-pct">{scorePercent}%</span>
      </div>

      {explanation ? (
        <div
          style={{
            background: 'var(--accent-light, rgba(59,130,246,0.07))',
            border: '1px solid rgba(59,130,246,0.18)',
            borderRadius: 'var(--radius)',
            padding: '10px 12px',
            margin: '8px 0',
            fontSize: 13,
            lineHeight: 1.5,
            color: 'var(--ink-secondary)',
          }}
        >
          <span style={{ fontWeight: 600, color: 'var(--ink-primary)' }}>Why this matches · </span>
          {explanation}
        </div>
      ) : (
        <button
          onClick={handleExplain}
          disabled={loadingExplanation}
          style={{
            margin: '8px 0',
            padding: '6px 12px',
            fontSize: 12,
            fontWeight: 600,
            color: 'var(--accent, #3b82f6)',
            background: 'var(--accent-light, rgba(59,130,246,0.07))',
            border: '1px solid rgba(59,130,246,0.25)',
            borderRadius: 'var(--radius)',
            cursor: loadingExplanation ? 'default' : 'pointer',
          }}
        >
          {loadingExplanation ? 'Generating explanation…' : '✨ Why does this match? (AI)'}
        </button>
      )}

      {trial.interventions.length > 0 && (
        <>
          <p className="card-section-title" style={{ marginTop: 8 }}>
            Interventions
          </p>
          <p
            style={{
              fontSize: 12,
              color: 'var(--ink-secondary)',
              marginBottom: 8,
              lineHeight: 1.5,
            }}
          >
            {trial.interventions.join(' · ')}
          </p>
        </>
      )}

      {trial.inclusionCriteria.length > 0 && (
        <>
          <p className="card-section-title">Key inclusion criteria</p>
          <div className="criteria-list">
            {trial.inclusionCriteria.map((criterion, i) => (
              <div key={i} className="criteria-item crit-inc">
                {criterion}
              </div>
            ))}
          </div>
        </>
      )}

      {trial.exclusionCriteria.length > 0 && (
        <>
          <p className="card-section-title">Key exclusion criteria</p>
          <div className="criteria-list">
            {trial.exclusionCriteria.map((criterion, i) => (
              <div key={i} className="criteria-item crit-exc">
                {criterion}
              </div>
            ))}
          </div>
        </>
      )}

      <div className="card-footer">
        <span className="sponsor-text">{trial.sponsor}</span>
        <a className="card-link" href={trial.url} target="_blank" rel="noreferrer">
          View full trial ↗
        </a>
      </div>
    </div>
  );
}
