// Shared helpers for describing the difference between women's and men's
// values. Used by the map (for color and the tooltip) and the table (for
// the "Difference" column and its sort order), so both always agree.

// Formats a raw value for display based on the metric's unit, so text reads
// correctly whether it's dollars, a percentage, years, a per-100k rate, or
// a plain count -- instead of assuming every metric is money. Used by the
// map tooltip, the table and the state cards, so all three always match.
export function formatValue(value, unit) {
  if (value == null) return "—";
  switch (unit) {
    case "usd":
      return `$${Math.round(value).toLocaleString()}`;
    case "percent":
      // always one decimal, so 52% and 52.7% line up as 52.0% and 52.7%
      return `${value.toFixed(1)}%`;
    case "years":
      return `${value.toFixed(1)} years`;
    case "per_100k":
      // as published: whole numbers stay whole (855), decimals keep theirs (4.9)
      return `${value.toLocaleString()} per 100,000`;
    default:
      return value.toLocaleString();
  }
}

// True when both values exist and can be compared as a ratio.
export function hasComparableValues(entry) {
  return (
    entry != null &&
    !entry.suppressed &&
    entry.female_value != null &&
    entry.male_value != null &&
    entry.female_value > 0 &&
    entry.male_value > 0
  );
}

// How many times larger men's value is than women's, on a log scale:
//   0  = equal
//  +1  = men's value is 2x women's
//  -1  = women's value is 2x men's
// A log scale makes "twice as high" the same distance from zero in either
// direction, and the same strength of color on every metric -- whether the
// values are dollars, percentages or rates per 100,000. Coloring by the raw
// difference instead made metrics with very lopsided values (incarceration:
// men's rates are 10-40x women's) a single deep color everywhere.
export function logRatio(entry) {
  if (!hasComparableValues(entry)) return null;
  return Math.log2(entry.male_value / entry.female_value);
}

// Plain-language version of the same thing: "1.6× higher for men".
export function describeGap(entry) {
  if (!hasComparableValues(entry)) return null;
  const { female_value: f, male_value: m } = entry;
  const ratio = Math.max(f, m) / Math.min(f, m);
  if (ratio < 1.005) return "About equal";
  const digits = ratio < 2 ? 2 : 1;
  return `${ratio.toFixed(digits)}× higher for ${m > f ? "men" : "women"}`;
}
