import { useEffect, useState } from "react";
import { fetchStates, fetchMetricMap, fetchStateProfile } from "./api";
import ChoroplethMap from "./components/ChoroplethMap";
import Legend from "./components/Legend";
import StatePanel from "./components/StatePanel";
import "./index.css";

const METRIC_SLUG = "median_earnings"; // the one metric loaded so far

export default function App() {
  const [states, setStates] = useState([]);
  const [metric, setMetric] = useState(null);
  const [values, setValues] = useState([]);
  const [loadError, setLoadError] = useState(null);

  const [selectedCode, setSelectedCode] = useState(null);
  const [profile, setProfile] = useState(null);
  const [profileLoading, setProfileLoading] = useState(false);

  // load the map's data once, when the page first opens
  useEffect(() => {
    Promise.all([fetchStates(), fetchMetricMap(METRIC_SLUG)])
      .then(([statesData, metricData]) => {
        setStates(statesData);
        setMetric(metricData.metric);
        setValues(metricData.values);
      })
      .catch((err) => setLoadError(err.message));
  }, []);

  // load one state's full profile whenever a new state is clicked
  useEffect(() => {
    if (!selectedCode) return;
    setProfileLoading(true);
    fetchStateProfile(selectedCode)
      .then(setProfile)
      .catch((err) => setLoadError(err.message))
      .finally(() => setProfileLoading(false));
  }, [selectedCode]);

  if (loadError) {
    return (
      <div className="error-banner">
        <p>Couldn't reach the API: {loadError}</p>
        <p>Is it running? Start it with `uvicorn main:app --reload` in the api folder.</p>
      </div>
    );
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1>State of Gender</h1>
        <p>A source-first map of measurable gender differences across every US state.</p>
      </header>

      <section className="map-section">
        {metric && (
          <>
            <h2>{metric.name}</h2>
            <p className="metric-definition">{metric.definition}</p>
          </>
        )}
        <Legend />
        <ChoroplethMap
          states={states}
          values={values}
          selectedCode={selectedCode}
          onSelectState={setSelectedCode}
        />
      </section>

      <section className="panel-section">
        <StatePanel profile={profile} loading={profileLoading} />
      </section>
    </div>
  );
}
