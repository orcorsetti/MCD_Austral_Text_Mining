export function EmptyState() {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <svg viewBox="0 0 24 24">
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.35-4.35" />
          <path d="M11 8v6M8 11h6" />
        </svg>
      </div>
      <p className="empty-title">No search yet</p>
      <p className="empty-sub">
        Fill in the patient profile and click "Search matching trials" to find eligible studies.
      </p>
    </div>
  );
}
