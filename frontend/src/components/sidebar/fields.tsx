import type { ReactNode } from 'react';
import type { DiagnosisGroup } from '../../data/formOptions';

interface FieldProps {
  label: string;
  required?: boolean;
  hint?: string;
  children: ReactNode;
}

/** Label + control + optional hint wrapper. */
export function Field({ label, required, hint, children }: FieldProps) {
  return (
    <div className="field">
      <label className="field-label">
        {label}
        {required && <span className="req">*</span>}
      </label>
      {children}
      {hint && <p className="field-hint">{hint}</p>}
    </div>
  );
}

interface SelectFieldProps {
  label: string;
  required?: boolean;
  hint?: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
  /** Grouped options (renders <optgroup>); takes precedence over `options`. */
  groups?: DiagnosisGroup[];
  placeholder: string;
}

export function SelectField({
  label,
  required,
  hint,
  value,
  onChange,
  options,
  groups,
  placeholder,
}: SelectFieldProps) {
  return (
    <Field label={label} required={required} hint={hint}>
      <select value={value} onChange={e => onChange(e.target.value)}>
        <option value="">{placeholder}</option>
        {groups
          ? groups.map(group => (
              <optgroup key={group.label} label={group.label}>
                {group.options.map(opt => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </optgroup>
            ))
          : options.map(opt => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
      </select>
    </Field>
  );
}

interface TextFieldProps {
  label: string;
  required?: boolean;
  hint?: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: 'text' | 'number';
  min?: number;
  max?: number;
}

export function TextField({
  label,
  required,
  hint,
  value,
  onChange,
  placeholder,
  type = 'text',
  min,
  max,
}: TextFieldProps) {
  return (
    <Field label={label} required={required} hint={hint}>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        min={min}
        max={max}
      />
    </Field>
  );
}
