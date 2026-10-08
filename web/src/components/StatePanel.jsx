import { formatValue } from "../gap";

// Shows one state's loaded observations below the map. Reads whatever
// `/api/states/{code}` returns, so as more metrics get loaded by the
// pipeline, more cards appear here automatically -- nothing here needs
// to change.
export default function StatePanel({ profile, loading }) {
  if (loading) {
    return <div className="state-panel">Loading…</div>;
  }
  if (!profile) {
    return (
      <div className="state-panel state-panel-empty">
        <p>Click a state on the map to see its profile.</p>
      </div>
    );
  }

  const { state, observations } = profile;

  return (
    <div className="state-panel">
      <h2>{state.name}</h2>
      {observations.length === 0 && <p>No data loaded for this state yet.</p>}
      {observations.map((o) => (
        <div className="metric-card" key={o.metric_slug}>
          <div className="metric-card-header">
            <span className="metric-category">{o.category_name}</span>
            <h3>{o.metric_name}</h3>
          </div>

          {o.suppressed || o.female_value == null ? (
            <p>No reliable estimate for {state.name}.</p>
          ) : (
            <dl className="metric-values">
              <div>
                <dt>Women</dt>
                <dd>{formatValue(o.female_value, o.unit)}</dd>
              </div>
              <div>
                <dt>Men</dt>
                <dd>{formatValue(o.male_value, o.unit)}</dd>
              </div>
            </dl>
          )}

          {/* The national figure for context. Skipped on the US's own
              profile, and when no national figure was loaded. */}
          {state.code !== "US" && o.us_female_value != null && (
            <p className="metric-national">
              United States: Women {formatValue(o.us_female_value, o.unit)} · Men{" "}
              {formatValue(o.us_male_value, o.unit)}
              {o.us_year !== o.year && ` (${o.us_year})`}
            </p>
          )}

          <details className="metric-source">
            <summary>Source &amp; definition</summary>
            <p>{o.definition}</p>
            <p>
              {o.source_title} ({o.source_release}), {o.year}.{" "}
              <a href={o.source_url} target="_blank" rel="noreferrer">
                View source
              </a>
            </p>
            {/* Only some sources carry a note -- e.g. when the link can't
                open the exact figure and the reader needs to know how to
                find it. Sources without one show nothing extra. */}
            {o.source_notes && <p className="metric-source-note">{o.source_notes}</p>}
          </details>
        </div>
      ))}
    </div>
  );
}
