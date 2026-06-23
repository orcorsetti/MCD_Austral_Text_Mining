import type { MatchConfidence } from '../../types';

interface ConfidenceBannerProps {
  confidence: MatchConfidence;
  missingFields: string[];
}

const BANNERS: Record<
  MatchConfidence,
  { className: string; icon: string; title: string; message: (missing: string[]) => string }
> = {
  high: {
    className: 'banner-high',
    icon: '✓',
    title: 'High-confidence results',
    message: () =>
      'All required fields were provided. Results are well-filtered to this patient profile.',
  },
  mid: {
    className: 'banner-mid',
    icon: '⚠',
    title: 'Partial match — review carefully',
    message: missing =>
      `Some fields were not provided (${missing.join(', ')}). Results may include trials for which the patient is ineligible.`,
  },
  low: {
    className: 'banner-low',
    icon: '!',
    title: 'Low-confidence results',
    message: missing =>
      `Several key fields are missing (${missing.join(', ')}). Results are broad and require manual eligibility review.`,
  },
};

export function ConfidenceBanner({ confidence, missingFields }: ConfidenceBannerProps) {
  const banner = BANNERS[confidence];
  return (
    <div className={`confidence-banner ${banner.className}`}>
      <span className="banner-icon">{banner.icon}</span>
      <div className="banner-text">
        <strong>{banner.title}</strong>
        {banner.message(missingFields)}
      </div>
    </div>
  );
}
