import { useState } from 'react';
import type { PatientProfile, SearchState } from './types';
import { EMPTY_PROFILE } from './types';
import type { ScoringVariant } from './api/matcher';
import { mlMatcher } from './api/mlBackend';
import { Header } from './components/Header';
import { Sidebar } from './components/sidebar/Sidebar';
import { ResultsPanel } from './components/results/ResultsPanel';

// The active matching backend. `mlMatcher` calls the RAG service (FastAPI);
// `clinicalTrialsGovMatcher` is the original CT.gov fallback with placeholder scores.
const matcher = mlMatcher;

function App() {
  const [profile, setProfile] = useState<PatientProfile>(EMPTY_PROFILE);
  const [searchState, setSearchState] = useState<SearchState>({ status: 'idle' });
  // Snapshot of the profile at search time, so editing the form doesn't
  // retroactively change how the displayed results are annotated.
  const [searchedProfile, setSearchedProfile] = useState<PatientProfile | null>(null);
  // Scoring variant for A/B comparison: 'v2' = disease-gated (default), 'v1' = original.
  const [variant, setVariant] = useState<ScoringVariant>('v2');
  // Number of studies to return.
  const [topN, setTopN] = useState(10);

  const handleSearch = async () => {
    setSearchState({ status: 'loading' });
    setSearchedProfile(profile);
    try {
      const result = await matcher.match(profile, variant, topN);
      setSearchState({ status: 'success', result });
    } catch (error) {
      setSearchState({
        status: 'error',
        message: error instanceof Error ? error.message : String(error),
      });
    }
  };

  const handleReset = () => {
    setProfile(EMPTY_PROFILE);
    setSearchedProfile(null);
    setSearchState({ status: 'idle' });
  };

  return (
    <>
      <Header />
      <div className="app-layout">
        <Sidebar
          profile={profile}
          onProfileChange={setProfile}
          onSearch={handleSearch}
          onReset={handleReset}
          variant={variant}
          onVariantChange={setVariant}
          topN={topN}
          onTopNChange={setTopN}
        />
        <ResultsPanel searchState={searchState} searchedProfile={searchedProfile} />
      </div>
    </>
  );
}

export default App;
