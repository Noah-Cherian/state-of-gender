// A labeled gradient bar explaining the map's diverging color scale.
// Deliberately framed as a direction, not a verdict -- neither end is
// labeled "better."
//
// `vertical` renders the bar top-to-bottom (for sitting beside the map)
// instead of the original left-to-right strip.
export default function Legend({ vertical = false }) {
  const gradientDirection = vertical ? "to top" : "to right";
  return (
    <div className={vertical ? "legend legend-vertical" : "legend"}>
      <span className="legend-label">{vertical ? "Men earn more" : "Women earn more"}</span>
      <div
        className="legend-bar"
        style={{
          background: `linear-gradient(${gradientDirection}, #0d366b, #f0efec, #d03b3b)`,
        }}
      />
      <span className="legend-label">{vertical ? "Women earn more" : "Men earn more"}</span>
    </div>
  );
}
