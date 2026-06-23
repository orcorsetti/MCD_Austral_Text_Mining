import type { Completeness } from '../../lib/completeness';

interface CompletenessBarProps {
  completeness: Completeness;
}

export function CompletenessBar({ completeness }: CompletenessBarProps) {
  const { percent, missingRequired } = completeness;

  const hint =
    percent === 0
      ? 'Fill in the required fields to begin.'
      : missingRequired.length === 0
        ? 'All required fields complete — ready to search.'
        : `Required: ${missingRequired.join(' · ')}`;

  return (
    <div className="completeness-bar">
      <div className="completeness-header">
        <span className="completeness-label">Profile completeness</span>
        <span className="completeness-pct">{percent}%</span>
      </div>
      <div className="bar-track">
        <div className="bar-fill" style={{ width: `${percent}%` }} />
      </div>
      <div className="completeness-fields">{hint}</div>
    </div>
  );
}
