import { useState } from 'react';
import type { PatientProfile } from '../../types';
import {
  BIOMARKER_HINT,
  COMORBIDITIES,
  COUNTRIES,
  DIAGNOSIS_GROUPS,
  DISEASE_SETTINGS,
  ECOG_OPTIONS,
  HER2_OPTIONS,
  HR_OPTIONS,
  INTERVENTION_TYPES,
  MSI_OPTIONS,
  PDL1_OPTIONS,
  PRIOR_LINES_OPTIONS,
  SEX_OPTIONS,
  TREATMENT_CLASSES,
  TREATMENT_SETTINGS,
  TRIAL_PHASES,
} from '../../data/formOptions';
import { computeCompleteness } from '../../lib/completeness';
import { CompletenessBar } from './CompletenessBar';
import { FormSection } from './FormSection';
import { Field, SelectField, TextField } from './fields';
import { MultiChipGroup, SingleChipGroup } from './ChipGroup';
import { BiomarkerInput } from './BiomarkerInput';

interface SidebarProps {
  profile: PatientProfile;
  onProfileChange: (profile: PatientProfile) => void;
  onSearch: () => void;
  onReset: () => void;
}

export function Sidebar({ profile, onProfileChange, onSearch, onReset }: SidebarProps) {
  const [validationError, setValidationError] = useState<string | null>(null);
  const completeness = computeCompleteness(profile);

  /** Helper to update a single profile field immutably. */
  const set = <K extends keyof PatientProfile>(key: K, value: PatientProfile[K]) => {
    onProfileChange({ ...profile, [key]: value });
  };

  const handleSearch = () => {
    if (!profile.diagnosis) {
      setValidationError('Diagnosis is required to search. Please select a tumor type.');
      window.setTimeout(() => setValidationError(null), 4000);
      return;
    }
    setValidationError(null);
    onSearch();
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-inner">
        <CompletenessBar completeness={completeness} />

        <FormSection label="Location & demographics">
          <div className="field-grid-2">
            <SelectField
              label="Country"
              required
              value={profile.country}
              onChange={v => set('country', v)}
              options={COUNTRIES}
              placeholder="Select..."
            />
            <TextField
              label="Age"
              type="number"
              value={profile.age}
              onChange={v => set('age', v)}
              placeholder="e.g. 58"
              min={18}
              max={99}
            />
          </div>
          <SelectField
            label="Sex"
            value={profile.sex}
            onChange={v => set('sex', v)}
            options={SEX_OPTIONS}
            placeholder="Any"
          />
        </FormSection>

        <FormSection label="Diagnosis">
          <SelectField
            label="Primary tumor type"
            required
            value={profile.diagnosis}
            onChange={v => set('diagnosis', v)}
            options={[]}
            groups={DIAGNOSIS_GROUPS}
            placeholder="Select diagnosis..."
          />
          <div className="field-grid-2">
            <TextField
              label="Histology / subtype"
              value={profile.histology}
              onChange={v => set('histology', v)}
              placeholder="e.g. adenocarcinoma"
            />
            <SelectField
              label="Disease setting"
              required
              value={profile.diseaseSetting}
              onChange={v => set('diseaseSetting', v)}
              options={DISEASE_SETTINGS}
              placeholder="Select..."
            />
          </div>
        </FormSection>

        <FormSection label="Molecular profile">
          <Field label="Biomarkers / mutations" hint={BIOMARKER_HINT}>
            <BiomarkerInput
              biomarkers={profile.biomarkers}
              onChange={v => set('biomarkers', v)}
            />
          </Field>
          <div className="field-grid-2">
            <SelectField
              label="HER2 status"
              value={profile.her2Status}
              onChange={v => set('her2Status', v)}
              options={HER2_OPTIONS}
              placeholder="Unknown / N/A"
            />
            <SelectField
              label="HR status"
              value={profile.hrStatus}
              onChange={v => set('hrStatus', v)}
              options={HR_OPTIONS}
              placeholder="Unknown / N/A"
            />
            <SelectField
              label="MSI / MMR status"
              value={profile.msiStatus}
              onChange={v => set('msiStatus', v)}
              options={MSI_OPTIONS}
              placeholder="Unknown / N/A"
            />
            <SelectField
              label="PD-L1 expression"
              value={profile.pdl1Status}
              onChange={v => set('pdl1Status', v)}
              options={PDL1_OPTIONS}
              placeholder="Unknown / N/A"
            />
          </div>
        </FormSection>

        <FormSection label="Performance status">
          <Field
            label="ECOG PS"
            required
            hint="Most trials require ECOG 0–1. ECOG ≥2 will flag relevant exclusion criteria."
          >
            <SingleChipGroup
              options={ECOG_OPTIONS.map(o => ({ value: o.value, warn: o.warn }))}
              selected={profile.ecog}
              onChange={v => set('ecog', v)}
            />
          </Field>
          <Field label="Relevant comorbidities">
            <MultiChipGroup
              options={COMORBIDITIES}
              selected={profile.comorbidities}
              onChange={v => set('comorbidities', v)}
            />
          </Field>
        </FormSection>

        <FormSection label="Treatment history">
          <div className="field-grid-2">
            <SelectField
              label="Treatment setting"
              required
              value={profile.treatmentSetting}
              onChange={v => set('treatmentSetting', v)}
              options={TREATMENT_SETTINGS}
              placeholder="Select..."
            />
            <SelectField
              label="Prior lines of therapy"
              value={profile.priorLines}
              onChange={v => set('priorLines', v)}
              options={PRIOR_LINES_OPTIONS}
              placeholder="Unknown"
            />
          </div>
          <Field label="Prior treatment classes">
            <MultiChipGroup
              options={TREATMENT_CLASSES}
              selected={profile.priorTreatmentClasses}
              onChange={v => set('priorTreatmentClasses', v)}
            />
          </Field>
        </FormSection>

        <FormSection label="Trial preferences">
          <Field label="Phase">
            <MultiChipGroup
              options={TRIAL_PHASES}
              selected={profile.phases}
              onChange={v => set('phases', v)}
            />
          </Field>
          <Field label="Intervention type">
            <MultiChipGroup
              options={INTERVENTION_TYPES}
              selected={profile.interventionTypes}
              onChange={v => set('interventionTypes', v)}
            />
          </Field>
        </FormSection>

        <FormSection label="Additional details">
          <Field
            label="Free-text description"
            hint="Processed by NLP to extract additional matching criteria."
          >
            <textarea
              value={profile.freeText}
              onChange={e => set('freeText', e.target.value)}
              placeholder="Describe any other relevant clinical characteristics: specific mutation details, lab values, prior drug names, concurrent medications, patient preferences..."
            />
          </Field>
        </FormSection>

        {validationError && (
          <div className="missing-fields-note" style={{ display: 'block' }}>
            {validationError}
          </div>
        )}

        <button className="submit-btn" onClick={handleSearch}>
          Search matching trials →
        </button>
        <span className="reset-link" onClick={onReset}>
          Reset all fields
        </span>
      </div>
    </aside>
  );
}
