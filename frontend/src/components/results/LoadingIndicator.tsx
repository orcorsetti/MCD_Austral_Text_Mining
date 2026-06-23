export function LoadingIndicator() {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '2rem 0',
        color: 'var(--ink-tertiary)',
        fontSize: 14,
      }}
    >
      <span className="loading-dot" />
      <span className="loading-dot" />
      <span className="loading-dot" />
      <span>Querying ClinicalTrials.gov...</span>
    </div>
  );
}
