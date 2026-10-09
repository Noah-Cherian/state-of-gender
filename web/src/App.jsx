import { useEffect, useState } from "react";
import { fetchStates, fetchMetrics, fetchMetricMap, fetchStateProfile } from "./api";
import ChoroplethMap from "./components/ChoroplethMap";
import Legend from "./components/Legend";
import StatePanel from "./components/StatePanel";
import StateTable from "./components/StateTable";
import "./index.css";

const DEFAULT_METRIC_SLUG = "median_earnings"; // shown first, if it has data; otherwise the first metric listed

export default function App() {
  const [states, setStates] = useState([]);
  const [metrics, setMetrics] = useState([]); // every metric, for the dropdown
  const [selectedMetricSlug, setSelectedMetricSlug] = useState(null); // chosen once the metric list arrives
  const [metric, setMetric] = useState(null);
  const [values, setValues] = useState([]);
  const [loadError, setLoadError] = useState(null);
  const [mapLoading, setMapLoading] = useState(true); // true while the selected metric's data is on its way
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
        // Only pick a metric once we know which ones exist, so the page
        // never asks for one that has no data.
        const hasDefault = metricsData.some((m) => m.slug === DEFAULT_METRIC_SLUG);
        setSelectedMetricSlug(hasDefault ? DEFAULT_METRIC_SLUG : metricsData[0]?.slug ?? null);
      })
      .catch((err) => setLoadError(err.message));
  }, []);

  // (re)load the map's data whenever the selected metric changes
  useEffect(() => {
    if (!selectedMetricSlug) return; // still waiting for the metric list
    setMapLoading(true);
    fetchMetricMap(selectedMetricSlug)
      .then((metricData) => {
        setMetric(metricData.metric);
        setValues(metricData.values);
      })
      .catch((err) => setLoadError(err.message))
      .finally(() => setMapLoading(false));
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
        <p>Couldn't load the data: {loadError}</p>
        {/* import.meta.env.DEV is true only under `npm run dev`, so
            visitors to the live site never see developer instructions. */}
        {import.meta.env.DEV ? (
          <p>
            Have you run `python3 export_static.py` in the api folder? (Or, with
            VITE_USE_LIVE_API=true, is the API running?)
          </p>
        ) : (
          <p>Try refreshing the page in a moment.</p>
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
            value={selectedMetricSlug ?? ""}
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

        <div className="view-area" aria-busy={mapLoading}>
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
          {/* Sits over the map or table until the data arrives, so the
              page never looks broken while it waits. */}
          {mapLoading && (
            <div className="loading-overlay" role="status">
              <p>Loading data…</p>
            </div>
          )}
        </div>
      </section>

      <section className="panel-section">
        <StatePanel profile={profile} loading={profileLoading} view={view} />
      </section>
    </div>
  );
}

// Turns the flat metric list into { categoryName: [metrics] },
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
