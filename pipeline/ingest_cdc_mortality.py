"""
State of Gender -- ingest script: suicide / homicide mortality, by sex,
all states + DC + US

Unlike every other script in this folder, this one does NOT call an API.
The source is CDC WONDER ("Underlying Cause of Death, 2018-2024, Single
Race"), and CDC's own documentation says its API cannot return state-level
mortality data -- only the website can. So the data arrives as two files
that a person exports from the WONDER website by hand, and this script
reads those files.

What this does:
  1. Reads two WONDER export files from the `data/` folder next to this
     script (see FILES below for the exact names):
       * "by state":  the query grouped by Sex, then State
       * "national":  the same query grouped by Sex only (the US row --
                      WONDER refuses to add totals to the by-state export
                      because some state values are suppressed)
  2. Checks each file's own footer -- WONDER writes the query settings
     into the file -- to confirm it really is the right cause of death,
     year and grouping before trusting any number in it.
  3. Takes the "Age Adjusted Rate" column (deaths per 100,000, adjusted to
     the 2000 U.S. standard population) for each sex.
  4. Writes one `sources` row and one `observations` row per state.

Suppression: CDC withholds any figure based on fewer than ten deaths, and
writes the word "Suppressed" in its place. It also flags some rates as
"Unreliable". Either way the value is stored as missing and the row is
marked suppressed -- the other sex's value is still kept.

Margin of error: left blank on purpose. These exports carry a 95%
confidence interval, but it is lopsided for small states (Wyoming women:
7.4, interval 4.6 to 11.6), so it cannot be honestly squeezed into the one
"plus or minus" number the `female_moe` / `male_moe` columns hold.

The column names and file layout used below were read off the real export
files, not assumed.

Safe to re-run: every insert is an upsert (insert-or-update).

Run it with:
    python3 ingest_cdc_mortality.py suicide
    python3 ingest_cdc_mortality.py homicide
"""

import csv
import os
import sys
from datetime import date
from pathlib import Path

import psycopg
from dotenv import load_dotenv

load_dotenv()

# --- About this specific release -------------------------------------------
DATA_YEAR = 2024
DATASET_NAME = "Underlying Cause of Death, 2018-2024, Single Race"
DATASET_URL = "https://wonder.cdc.gov/ucd-icd10-expanded.html"
PUBLISHER = "CDC WONDER (National Center for Health Statistics)"
DATA_DIR = Path(__file__).parent / "data"

# One entry per cause this script knows how to load. `intent` is the exact
# label WONDER writes in the file footer ("Injury Intent: Suicide").
CAUSES = {
    "suicide": {"metric_slug": "suicide_mortality", "intent": "Suicide"},
    "homicide": {"metric_slug": "homicide_mortality", "intent": "Homicide"},
}

RATE_COLUMN = "Age Adjusted Rate"
SEX_CODES = {"F": "female", "M": "male"}


def files_for(cause):
    return {
        "by_state": DATA_DIR / f"wonder_{cause}_{DATA_YEAR}_by_state.txt",
        "national": DATA_DIR / f"wonder_{cause}_{DATA_YEAR}_national.txt",
    }


def read_wonder_export(path):
    """Return (data_rows, footer_lines) from one WONDER export file.

    The file is tab-separated: a header line, then data rows, then a line
    containing only "---", then free-text notes describing the query."""
    with open(path, newline="", encoding="utf-8") as f:
        lines = list(csv.reader(f, delimiter="\t"))

    header = lines[0]
    data_rows = []
    footer_start = len(lines)
    for i, cells in enumerate(lines[1:], start=1):
        if cells and cells[0] == "---":
            footer_start = i
            break
        data_rows.append(dict(zip(header, cells)))

    footer_lines = [cells[0] for cells in lines[footer_start:] if cells]
    return data_rows, footer_lines


def check_footer(path, footer_lines, intent, group_by):
    """Stop with a clear message if this file is not the export we expect.
    This is the guard against loading, say, a homicide file as suicide."""
    expected = [
        f"Dataset: {DATASET_NAME}",
        f"Injury Intent: {intent}",
        f"Year/Month: {DATA_YEAR}",
        f"Group By: {group_by}",
        "Calculate Rates Per: 100,000",
    ]
    missing = [line for line in expected if line not in footer_lines]
    if missing:
        raise SystemExit(
            f"{path.name} is not the expected export. Its notes are missing:\n  "
            + "\n  ".join(missing)
        )


def to_rate_or_none(raw_value):
    """A real rate looks like '24.5'. Anything else -- 'Suppressed',
    'Unreliable', 'Not Applicable', or a rate with '(Unreliable)' attached
    -- is treated as missing."""
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return None


def _observation(state_code, rates):
    female_value = rates.get("female")
    male_value = rates.get("male")
    return {
        "state_code": state_code,
        "year": DATA_YEAR,
        "female_value": female_value,
        "male_value": male_value,
        "suppressed": female_value is None or male_value is None,
    }


def build_observations(state_rows, national_rows, fips_to_code):
    # state rows: collect {fips: {"female": rate, "male": rate}}
    rates_by_fips = {}
    for row in state_rows:
        # When WONDER can add totals (it could for homicide, not for
        # suicide), it appends rows marked "Total" in the Notes column with
        # no state. The national figure comes from the separate national
        # file instead, so these are skipped either way.
        if row.get("Notes") == "Total":
            continue
        sex = SEX_CODES.get(row.get("Sex Code"))
        if sex is None:
            continue
        rates_by_fips.setdefault(row["State Code"], {})[sex] = to_rate_or_none(row[RATE_COLUMN])

    observations = []
    for fips, rates in sorted(rates_by_fips.items()):
        state_code = fips_to_code.get(fips)
        if state_code is None:
            print(f"  skipping unrecognized FIPS code: {fips}")
            continue
        observations.append(_observation(state_code, rates))

    # national rows: the same, but there is no state column at all
    us_rates = {}
    for row in national_rows:
        sex = SEX_CODES.get(row.get("Sex Code"))
        if sex is not None:
            us_rates[sex] = to_rate_or_none(row[RATE_COLUMN])
    observations.append(_observation("US", us_rates))

    return observations


def upsert_source(cur, cause, intent, state_code):
    grouping = "Sex" if state_code == "US" else "Sex; State"
    cur.execute(
        """
        INSERT INTO sources (slug, kind, publisher, title, release, table_ref, url, retrieved_on, notes)
        VALUES (%(slug)s, 'dataset', %(publisher)s, %(title)s, %(release)s, %(table_ref)s, %(url)s, %(retrieved_on)s, %(notes)s)
        ON CONFLICT (slug) DO UPDATE SET
            url          = EXCLUDED.url,
            retrieved_on = EXCLUDED.retrieved_on,
            notes        = EXCLUDED.notes
        RETURNING id
        """,
        {
            "slug": f"cdc-wonder-ucd-{DATA_YEAR}-{cause}-{state_code.lower()}",
            "publisher": PUBLISHER,
            "title": DATASET_NAME,
            "release": str(DATA_YEAR),
            "table_ref": f"Injury Intent: {intent}",
            "url": DATASET_URL,
            "retrieved_on": date.today(),
            # Shown to site visitors under "Source & definition", so it is
            # written for them: the link can only open CDC's query form,
            # and this says how to get from that form to the figure.
            "notes": (
                "Note: the source link opens CDC WONDER's query page, not a "
                "finished table. CDC does not offer a direct link to these "
                "figures. To reproduce this number there: accept the data use "
                f"terms, group results by {grouping.replace('; ', ', then ')}, tick "
                f"\"Age Adjusted Rate\", choose year {DATA_YEAR}, and under cause of "
                f"death choose Injury Intent: {intent}. Rates are age-adjusted to "
                "the 2000 U.S. standard population. CDC withholds any figure "
                "based on fewer than ten deaths."
            ),
        },
    )
    return cur.fetchone()[0]


def upsert_observations(cur, metric_slug, observations, source_id_by_code):
    sql = """
        INSERT INTO observations
            (state_code, metric_slug, year, female_value, male_value,
             female_moe, male_moe, suppressed, source_id)
        VALUES (%s, %s, %s, %s, %s, NULL, NULL, %s, %s)
        ON CONFLICT (state_code, metric_slug, year) DO UPDATE SET
            female_value = EXCLUDED.female_value,
            male_value   = EXCLUDED.male_value,
            female_moe   = EXCLUDED.female_moe,
            male_moe     = EXCLUDED.male_moe,
            suppressed   = EXCLUDED.suppressed,
            source_id    = EXCLUDED.source_id
    """
    values = [
        (
            o["state_code"],
            metric_slug,
            o["year"],
            o["female_value"],
            o["male_value"],
            o["suppressed"],
            source_id_by_code[o["state_code"]],
        )
        for o in observations
    ]
    cur.executemany(sql, values)
    return len(values)


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in CAUSES:
        raise SystemExit("Usage: python3 ingest_cdc_mortality.py [suicide|homicide]")
    cause = sys.argv[1]
    metric_slug = CAUSES[cause]["metric_slug"]
    intent = CAUSES[cause]["intent"]
    files = files_for(cause)

    for path in files.values():
        if not path.exists():
            raise SystemExit(f"Missing export file: {path}")

    print(f"Reading CDC WONDER exports for {cause} mortality, {DATA_YEAR}...")
    state_rows, state_footer = read_wonder_export(files["by_state"])
    check_footer(files["by_state"], state_footer, intent, "Sex; State")
    national_rows, national_footer = read_wonder_export(files["national"])
    check_footer(files["national"], national_footer, intent, "Sex")
    print(f"  read {len(state_rows)} state rows + {len(national_rows)} national row(s)")

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT code, fips FROM states")
            fips_to_code = {fips: code for code, fips in cur.fetchall()}

            observations = build_observations(state_rows, national_rows, fips_to_code)
            suppressed_count = sum(1 for o in observations if o["suppressed"])
            print(f"  built {len(observations)} observation rows ({suppressed_count} suppressed)")

            source_id_by_code = {
                o["state_code"]: upsert_source(cur, cause, intent, o["state_code"])
                for o in observations
            }
            print(f"  created/updated {len(source_id_by_code)} per-state source rows")

            n_loaded = upsert_observations(cur, metric_slug, observations, source_id_by_code)
            print(f"  loaded {n_loaded} observations into the database")
        conn.commit()

    print("Done. Check the `observations` table, or query `observation_gaps` to see the computed gap.")


if __name__ == "__main__":
    main()
