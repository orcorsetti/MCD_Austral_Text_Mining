interface ChipOption {
  value: string;
  /** Renders the chip in warning (red) style when active. */
  warn?: boolean;
}

interface MultiChipGroupProps {
  options: (string | ChipOption)[];
  selected: string[];
  onChange: (selected: string[]) => void;
}

function asOption(opt: string | ChipOption): ChipOption {
  return typeof opt === 'string' ? { value: opt } : opt;
}

/** Multi-select chip row (comorbidities, prior treatments, phases...). */
export function MultiChipGroup({ options, selected, onChange }: MultiChipGroupProps) {
  const toggle = (value: string) => {
    onChange(
      selected.includes(value) ? selected.filter(v => v !== value) : [...selected, value],
    );
  };

  return (
    <div className="chip-wrap">
      {options.map(opt => {
        const { value, warn } = asOption(opt);
        const active = selected.includes(value);
        return (
          <span
            key={value}
            className={`chip${warn ? ' warn' : ''}${active ? ' active' : ''}`}
            onClick={() => toggle(value)}
          >
            {value}
          </span>
        );
      })}
    </div>
  );
}

interface SingleChipGroupProps {
  options: (string | ChipOption)[];
  selected: string | null;
  onChange: (selected: string) => void;
}

/** Single-select chip row (ECOG). */
export function SingleChipGroup({ options, selected, onChange }: SingleChipGroupProps) {
  return (
    <div className="chip-wrap">
      {options.map(opt => {
        const { value, warn } = asOption(opt);
        const active = selected === value;
        return (
          <span
            key={value}
            className={`chip${warn ? ' warn' : ''}${active ? ' active' : ''}`}
            onClick={() => onChange(value)}
          >
            {value}
          </span>
        );
      })}
    </div>
  );
}
