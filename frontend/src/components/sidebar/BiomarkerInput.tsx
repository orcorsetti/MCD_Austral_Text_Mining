import { useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';

interface BiomarkerInputProps {
  biomarkers: string[];
  onChange: (biomarkers: string[]) => void;
}

/** Tag-style input for biomarkers / mutations. */
export function BiomarkerInput({ biomarkers, onChange }: BiomarkerInputProps) {
  const [draft, setDraft] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    const value = draft.trim().replace(/,$/, '');

    if ((e.key === 'Enter' || e.key === ',') && value) {
      e.preventDefault();
      if (!biomarkers.includes(value)) {
        onChange([...biomarkers, value]);
      }
      setDraft('');
    } else if (e.key === 'Backspace' && !draft && biomarkers.length) {
      onChange(biomarkers.slice(0, -1));
    }
  };

  const remove = (index: number) => {
    onChange(biomarkers.filter((_, i) => i !== index));
  };

  return (
    <div className="biomarker-box" onClick={() => inputRef.current?.focus()}>
      {biomarkers.map((biomarker, i) => (
        <span key={biomarker} className="bm-tag">
          {biomarker}{' '}
          <button onClick={() => remove(i)} aria-label={`Remove ${biomarker}`}>
            ×
          </button>
        </span>
      ))}
      <input
        ref={inputRef}
        className="bm-input"
        value={draft}
        onChange={e => setDraft(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Type and press Enter (e.g. BRCA2, PD-L1 >50%)"
      />
    </div>
  );
}
