import { useMemo, useState } from "react";
import {
  ComposableMap,
  Geographies,
  Geography,
} from "react-simple-maps";
import { scaleDiverging } from "d3-scale";
import { interpolateRgb, piecewise } from "d3-interpolate";

// US state boundaries, bundled from the us-atlas npm package rather than
// fetched from a CDN at runtime -- one less thing that can go down or get
// blocked later. Each shape's "id" is a two-digit FIPS code as a string
// (e.g. "13" for Georgia), the same format our states table's `fips`
// column uses, so no extra lookup table is needed to match a shape to
// our data.
import usStatesTopoJSON from "us-atlas/states-10m.json";

// Diverging pair: blue for men, pink for women, with a neutral gray at the
// midpoint (never a hue at zero -- zero has to read as "no gap," not as a
// color of its own). Deliberately blue/pink rather than blue/red -- red
// and blue read as a US political-party cue before they read as "a sex
// has a higher value here," which isn't a message this map intends to
// send. Validated against the project's accessibility checks (CVD
// separation, contrast, lightness) as a pair before use.
const COLOR_WOMEN_HIGHER = "#d6497e"; // pink: women have the higher value
const COLOR_NEUTRAL = "#f0efec"; // gray: at or near parity
const COLOR_MEN_HIGHER = "#1f5fa8"; // blue: men have the higher value
const COLOR_NO_DATA = "#e1e0d9"; // light gray: nothing loaded yet for this metric

/**
 * A clickable US choropleth map, colored by the gap between two values.
 *
 * Deliberately agnostic about which value is "good": the color scale is
 * centered on zero (parity) and extends equally in both directions, so
 * a viewer reads direction and size, not a verdict.
 */
// Formats a raw value for display based on the metric's unit, so the
// tooltip reads correctly whether it's dollars, a percentage, a per-100k
// rate, or a plain count -- instead of assuming every metric is money.
function formatValue(value, unit) {
  switch (unit) {
    case "usd":
      return `$${value.toLocaleString()}`;
    case "percent":
      return `${value.toLocaleString()}%`;
    case "per_100k":
      return `${value.toLocaleString()} per 100k`;
    default:
      return value.toLocaleString();
  }
}

export default function ChoroplethMap({
  states, // [{ code, name, fips }]
  values, // [{ state_code, female_value, male_value, suppressed }]
  unit, // the selected metric's unit -- controls tooltip formatting
  onSelectState,
  selectedCode,
}) {
  const [hovered, setHovered] = useState(null);

  // one lookup, built once per data change, instead of searching the
  // array again for every one of the ~52 shapes on every render
  const byFips = useMemo(() => {
    const valueByCode = new Map(values.map((v) => [v.state_code, v]));
    const map = new Map();
    for (const state of states) {
      const value = valueByCode.get(state.code);
      map.set(state.fips, { ...state, ...value });
    }
    return map;
  }, [states, values]);

  const colorScale = useMemo(() => {
    const gaps = values
      .filter((v) => !v.suppressed && v.female_value != null && v.male_value != null)
      .map((v) => v.male_value - v.female_value);
    const maxAbsGap = Math.max(1, ...gaps.map(Math.abs));
    // Two straight blends -- pink to gray, then gray to blue -- that meet
    // exactly at gray. (The previous smooth-curve blend never actually
    // reached gray in the middle, so near-parity states on both sides came
    // out the same lavender and you couldn't tell which way they leaned.)
    // This also matches the legend, which is the same three-stop gradient.
    const blend = piecewise(interpolateRgb, [COLOR_WOMEN_HIGHER, COLOR_NEUTRAL, COLOR_MEN_HIGHER]);
    return scaleDiverging(blend).domain([-maxAbsGap, 0, maxAbsGap]);
  }, [values]);

  function colorFor(entry) {
    if (!entry || entry.suppressed || entry.female_value == null || entry.male_value == null) {
      return COLOR_NO_DATA;
    }
    return colorScale(entry.male_value - entry.female_value);
  }

  return (
    <div className="map-wrap">
      <ComposableMap projection="geoAlbersUsa" width={960} height={600}>
        <Geographies geography={usStatesTopoJSON}>
          {({ geographies }) => {
            // Rendered in two passes instead of one. Every state's base
            // fill + thin border is drawn first, in topojson order -- the
            // same way it always was. The emphasized (hovered/selected)
            // state's thicker, darker outline is then drawn again as a
            // *second* pass, after everything else, so it paints on top of
            // whichever neighboring states happen to share that border
            // instead of being partly covered by them. That overlap, not
            // the stroke itself, was what made the border look "grainy" --
            // a state later in draw order was painting over part of an
            // earlier state's emphasis outline.
            let emphasizedGeo = null;
            const baseLayer = geographies.map((geo) => {
              const entry = byFips.get(geo.id);
              const isSelected = entry && entry.code === selectedCode;
              const isHovered = entry && hovered && entry.code === hovered.code;
              const emphasized = isSelected || isHovered;
              if (emphasized) emphasizedGeo = geo;
              return (
                <Geography
                  key={geo.rsmKey}
                  geography={geo}
                  onMouseEnter={() => setHovered(entry ?? null)}
                  onMouseLeave={() => setHovered(null)}
                  onClick={() => entry && onSelectState(entry.code)}
                  fill={colorFor(entry)}
                  stroke="#fcfcfb"
                  strokeWidth={0.5}
                  style={{
                    outline: "none",
                    cursor: entry ? "pointer" : "default",
                    vectorEffect: "non-scaling-stroke",
                  }}
                />
              );
            });

            return (
              <>
                {baseLayer}
                {emphasizedGeo && (
                  <Geography
                    key={`${emphasizedGeo.rsmKey}-emphasis`}
                    geography={emphasizedGeo}
                    fill="none"
                    stroke="#0b0b0b"
                    strokeWidth={1.75}
                    strokeLinejoin="round"
                    style={{
                      outline: "none",
                      pointerEvents: "none",
                      vectorEffect: "non-scaling-stroke",
                    }}
                  />
                )}
              </>
            );
          }}
        </Geographies>
      </ComposableMap>

      {hovered && (
        <div className="map-tooltip">
          <strong>{hovered.name}</strong>
          {hovered.suppressed || hovered.female_value == null ? (
            <p>No reliable estimate for this state.</p>
          ) : (
            <>
              <p>Women: {formatValue(hovered.female_value, unit)}</p>
              <p>Men: {formatValue(hovered.male_value, unit)}</p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
