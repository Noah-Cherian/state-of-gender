import { useMemo, useState } from "react";
import { describeGap, formatValue, logRatio } from "../gap";

// The same data as the map, as a sortable table. Easier to read exact
// values than colors, and usable by anyone who can't tell the colors
// apart. Click a column header to sort by it (click again to reverse);
// click a row to open that state's profile, same as clicking the map.
//
// The "Difference" column sorts by the same log ratio the map colors by
// (see ../gap.js): most "higher for women" at one end, most "higher for
// men" at the other.
const COLUMNS = [
  { key: "name", label: "State", sortValue: (row) => row.name },
  { key: "female", label: "Women", sortValue: (row) => row.female_value },
  { key: "male", label: "Men", sortValue: (row) => row.male_value },
  { key: "gap", label: "Difference", sortValue: (row) => logRatio(row) },
];

export default function StateTable({ states, values, unit, onSelectState, selectedCode }) {
  const [sortKey, setSortKey] = useState("name");
  const [ascending, setAscending] = useState(true);

  // one row per state that's on the map (50 states + DC), plus the
  // national row kept apart so sorting never moves it
  const { rows, national } = useMemo(() => {
    const valueByCode = new Map(values.map((v) => [v.state_code, v]));
    const rows = states
      .filter((s) => s.code !== "US")
      .map((s) => ({ ...s, ...valueByCode.get(s.code) }));
    const usState = states.find((s) => s.code === "US");
    const usValue = valueByCode.get("US");
    const national = usState && usValue ? { ...usState, ...usValue } : null;
    return { rows, national };
  }, [states, values]);

  const sortedRows = useMemo(() => {
    const column = COLUMNS.find((c) => c.key === sortKey);
    const direction = ascending ? 1 : -1;
    return [...rows].sort((a, b) => {
      const av = column.sortValue(a);
      const bv = column.sortValue(b);
      // rows with no value always go last, whichever way you sort
      if (av == null && bv == null) return a.name.localeCompare(b.name);
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === "string") return av.localeCompare(bv) * direction;
      return (av - bv) * direction;
    });
  }, [rows, sortKey, ascending]);

  function handleSort(key) {
    if (key === sortKey) {
      setAscending(!ascending);
    } else {
      setSortKey(key);
      setAscending(true);
    }
  }

  return (
    <div className="table-wrap">
      <table className="state-table">
        <thead>
          <tr>
            {COLUMNS.map((c) => (
              <th
                key={c.key}
                aria-sort={c.key === sortKey ? (ascending ? "ascending" : "descending") : "none"}
              >
                <button type="button" onClick={() => handleSort(c.key)}>
                  {c.label}
                  <span className="sort-arrow" aria-hidden="true">
                    {c.key === sortKey ? (ascending ? " ▲" : " ▼") : ""}
                  </span>
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {national && <TableRow row={national} unit={unit} className="national-row" />}
          {sortedRows.map((row) => (
            <TableRow
              key={row.code}
              row={row}
              unit={unit}
              className={row.code === selectedCode ? "selected-row" : ""}
              onClick={() => onSelectState(row.code)}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TableRow({ row, unit, className, onClick }) {
  const hasData = row.female_value != null || row.male_value != null;
  return (
    <tr className={className} onClick={onClick} style={onClick ? { cursor: "pointer" } : undefined}>
      <td>{row.name}</td>
      <td>{formatValue(row.female_value, unit)}</td>
      <td>{formatValue(row.male_value, unit)}</td>
      <td className="gap-cell">{describeGap(row) ?? (hasData ? "Not available" : "No data")}</td>
    </tr>
  );
}
