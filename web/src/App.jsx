import { useEffect, useState } from "react";
import { fetchStates, fetchMetrics, fetchMetricMap, fetchStateProfile } from "./api";
import ChoroplethMap from "./components/ChoroplethMap";
import Legend from "./components/Legend";
import StatePanel from "./components/StatePanel";
import StateTable from "./components/StateTable";
import "./index.css";

const DEFAULT_METRIC_SLUG = "median_earnings"; // shown first, before the dropdown is even touched

export default function App() {
  const [states, setStates] = useState([]);
  const [metrics, setMetrics] = useState([]); // every metric, for the dropdown
  const [selectedMetricSlug, setSelectedMetricSlug] = useState(DEFAULT_METRIC_SLUG);
  const [metric, setMetric] = useState(null);
  const [values, setValues] = useState([]);
  const [loadError, setLoadError] = useState(null);
  const [view, setView] = useState("map"); // "map" or "table" -- same data either way

  const [selectedCode, setSelectedCode] = useState(null);
  const [profile, setProfile] = useState(null);
  const [profileLoading, setProfileLoading] = useState(false);

  // load the state list and the full metric catalog once, when the page first opens
  useEffect(() => {
    Promise.all([fetchStates(), fetchMetrics()])
      .then(([statesData, metricsData]) => {
        setStates(statesData);
        setMetrics(metricsData);
      })
      .catch((err) => setLoadError(err.message));
  }, []);

  // (re)load the map's data whenever the selected metric changes
  useEffect(() => {
    fetchMetricMap(selectedMetricSlug)
      .then((metricData) => {
        setMetric(metricData.metric);
        setValues(metricData.values);
      })
      .catch((err) => setLoadError(err.message));
  }, [selectedMetricSlug]);

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
        {/* import.meta.env.DEV is true only under `npm run dev`, so
            visitors to the live site never see developer instructions. */}
        {import.meta.env.DEV ? (
          <p>Is it running? Start it with `uvicorn main:app --reload` in the api folder.</p>
        ) : (
          <p>The data server may be waking up after a quiet spell. Try refreshing in a minute.</p>
        )}
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
        <div className="metric-picker">
          <label htmlFor="metric-select">Metric</label>
          <select
            id="metric-select"
            value={selectedMetricSlug}
            onChange={(e) => setSelectedMetricSlug(e.target.value)}
          >
            {Object.entries(groupByCategory(metrics)).map(([categoryName, categoryMetrics]) => (
              <optgroup key={categoryName} label={categoryName}>
                {categoryMetrics.map((m) => (
                  <option key={m.slug} value={m.slug}>
                    {m.name}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>

        {metric && (
          <>
            <h2>{metric.name}</h2>
            <p className="metric-definition">{metric.definition}</p>
          </>
        )}
        <div className="view-toggle" role="group" aria-label="View">
          {["map", "table"].map((v) => (
            <button
              key={v}
              type="button"
              className={view === v ? "active" : ""}
              aria-pressed={view === v}
              onClick={() => setView(v)}
            >
              {v === "map" ? "Map" : "Table"}
            </button>
          ))}
        </div>

        {view === "map" ? (
          <>
            <Legend />
            <ChoroplethMap
              states={states}
              values={values}
              unit={metric?.unit}
              selectedCode={selectedCode}
              onSelectState={setSelectedCode}
            />
          </>
        ) : (
          <StateTable
            states={states}
            values={values}
            unit={metric?.unit}
            selectedCode={selectedCode}
            onSelectState={setSelectedCode}
          />
        )}
      </section>

      <section className="panel-section">
        <StatePanel profile={profile} loading={profileLoading} view={view} />
      </section>
    </div>
  );
}

// Turns the flat metric list from the API into { categoryName: [metrics] },
// preserving the order the API already sorted them in (by category, then
// by each metric's own sort_order).
function groupByCategory(metrics) {
  const groups = {};
  for (const m of metrics) {
    if (!groups[m.category_name]) groups[m.category_name] = [];
    groups[m.category_name].push(m);
  }
  return groups;
}
