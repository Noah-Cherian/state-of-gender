// A labeled gradient bar explaining the map's diverging color scale.
// Deliberately framed as a direction, not a verdict -- neither end is
// labeled "better." Kept generic ("higher for ...") rather than
// metric-specific wording ("earn more") since this same legend has to make
// sense for every metric on the map -- "higher" is neutral even for a
// metric like poverty rate or mortality, where a bigger number is bad news.
//
// The caption explains that color strength is relative ("how many times
// higher"), and that full color means the most lopsided state for the
// metric currently shown -- not a fixed amount shared by every metric.
export default function Legend() {
  return (
    <div className="legend-block">
      <div className="legend">
        <span className="legend-label">Higher for women</span>
        <div
          className="legend-bar"
          style={{ background: "linear-gradient(to right, #d6497e, #f0efec, #1f5fa8)" }}
        />
        <span className="legend-label">Higher for men</span>
      </div>
      <p className="legend-caption">
        Color shows how many times higher one value is than the other. Gray is
        parity; the strongest color is the most uneven state for this metric.
      </p>
    </div>
  );
}
