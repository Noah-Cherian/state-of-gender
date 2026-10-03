// A labeled gradient bar explaining the map's diverging color scale.
// Deliberately framed as a direction, not a verdict -- neither end is
// labeled "better." Kept generic ("higher for ...") rather than
// metric-specific wording ("earn more") since this same legend now has to
// make sense for every metric on the map, not just earnings -- "higher"
// is neutral even for a metric like poverty rate or mortality, where a
// bigger number is bad news, not good news.
export default function Legend({ vertical = false }) {
  const gradientDirection = vertical ? "to top" : "to right";
  return (
    <div className={vertical ? "legend legend-vertical" : "legend"}>
      <span className="legend-label">{vertical ? "Higher for men" : "Higher for women"}</span>
      <div
        className="legend-bar"
        style={{
          background: `linear-gradient(${gradientDirection}, #d6497e, #f0efec, #1f5fa8)`,
        }}
      />
      <span className="legend-label">{vertical ? "Higher for women" : "Higher for men"}</span>
    </div>
  );
}
