import type { ReactNode } from 'react';

interface FormSectionProps {
  label: string;
  children: ReactNode;
}

export function FormSection({ label, children }: FormSectionProps) {
  return (
    <div className="form-section">
      <div className="section-header">
        <div className="section-dot" />
        <span className="section-label">{label}</span>
      </div>
      {children}
    </div>
  );
}
