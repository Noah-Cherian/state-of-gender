"""
State of Gender -- ingest script: poverty rate, by sex, all states + DC + US

What this does:
  1. Calls the Census API for ACS 1-Year Estimates, SUBJECT table S1701
     (poverty status in the past 12 months, percent below poverty level, by sex).
  2. Looks up each state's postal code from your `states` table.
  3. Writes one `sources` row per state, with a Census deep link scoped to
     that state (same pattern as the median earnings script).
  4. Writes one `observations` row per state for the 'poverty_rate' metric.

This is a SUBJECT table, not a detailed table like median earnings' B20017 --
notice the dataset URL ends in `/subject`, the table id starts with "S" not
"B", and the values that come back are already percentages (e.g. 12.3), not
raw counts. Subject tables report that way because Census does the
population-weighted calculation for you; a detailed table like B17001 has
the same poverty data but as raw person counts broken out by ~9 age
brackets per sex, which you'd have to sum and divide yourself. Every
variable below was checked one at a time against api.census.gov's own
variable metadata before being used here -- see the project notes on why
that mattered for the labor force participation metric, which got shelved
for exactly this kind of table.

Safe to re-run: every insert is an upsert (insert-or-update).

Run it with:
    python3 ingest_poverty_rate.py
"""

import os
from datetime import date

import psycopg
import requests
from dotenv import load_dotenv

load_dotenv()

CENSUS_API_KEY = os.environ["CENSUS_API_KEY"]
DATABASE_URL = os.environ["DATABASE_URL"]

# --- About this specific release -------------------------------------------
ACS_YEAR = 2023
# Subject tables live under a different path than detailed tables (no
# "/subject" for B20017's dataset URL in the median earnings script).
ACS_DATASET_URL = f"https://api.census.gov/data/{ACS_YEAR}/acs/acs1/subject"
TABLE = "S1701"

# Confirmed against the Census variable metadata (one at a time, via
# api.census.gov/data/2023/acs/acs1/subject/variables/<code>.json):
#   S1701_C03_011E = percent below poverty level, population for whom
#                    poverty status is determined, male
#   S1701_C03_012E = same, female
#   predicateType for both is "float" -- these come back as percentages
#   like "12.3", not whole numbers, unlike B20017's dollar amounts.
MALE_VAR = "S1701_C03_011E"
MALE_MOE_VAR = "S1701_C03_011M"
FEMALE_VAR = "S1701_C03_012E"
FEMALE_MOE_VAR = "S1701_C03_012M"


def fetch_census_data():
    """Return (header, state_rows, us_header, us_rows) -- kept separate for
    the same reason as the median earnings script: the national query's
    "us" column value isn't a FIPS code, so it can't share a lookup with
    the state rows."""
    get_vars = ",".join(["NAME", MALE_VAR, MALE_MOE_VAR, FEMALE_VAR, FEMALE_MOE_VAR])

    state_resp = requests.get(
        ACS_DATASET_URL,
        params={"get": get_vars, "for": "state:*", "key": CENSUS_API_KEY},
        timeout=30,
    )
    state_resp.raise_for_status()
    header, *state_rows = state_resp.json()

    us_resp = requests.get(
        ACS_DATASET_URL,
        params={"get": get_vars, "for": "us:1", "key": CENSUS_API_KEY},
        timeout=30,
    )
    us_resp.raise_for_status()
    us_header, *us_rows = us_resp.json()

    return header, state_rows, us_header, us_rows


def to_number_or_none(raw_value):
    """Census sends numbers as strings. Subject tables use suppression
    sentinels too, but since this value is always a percentage (0-100),
    anything negative is unambiguously a placeholder rather than a real
    rate -- so that's the check, instead of matching exact sentinel
    constants the way the median earnings script does for dollar amounts
    (which legitimately *can* be large, so "negative" alone wouldn't be a
    safe check there)."""
    if raw_value is None:
        return None
    value = float(raw_value)
    return None if value < 0 else value


def _row_to_observation(row, col, state_code):
    male_value = to_number_or_none(row[col[MALE_VAR]])
    female_value = to_number_or_none(row[col[FEMALE_VAR]])
    male_moe = to_number_or_none(row[col[MALE_MOE_VAR]])
    female_moe = to_number_or_none(row[col[FEMALE_MOE_VAR]])

    suppressed = male_value is None or female_value is None

    return {
        "state_code": state_code,
        "year": ACS_YEAR,
        "female_value": female_value,
        "male_value": male_value,
        "female_moe": female_moe,
        "male_moe": male_moe,
        "suppressed": suppressed,
    }


def build_observations(header, state_rows, us_header, us_rows, fips_to_code):
    state_col = {name: i for i, name in enumerate(header)}
    observations = []

    for row in state_rows:
        fips = row[state_col["state"]]
        state_code = fips_to_code.get(fips)
        if state_code is None:
            print(f"  skipping unrecognized FIPS code: {fips}")
            continue
        observations.append(_row_to_observation(row, state_col, state_code))

    us_col = {name: i for i, name in enumerate(us_header)}
    for row in us_rows:
        observations.append(_row_to_observation(row, us_col, "US"))

    return observations


def _source_url_for(fips):
    """Same deep-linking approach as the median earnings script: the
    confirmed `g=0400000US{fips}` geography-scope parameter, plus the
    table id and year. `fips=None` (the national row) falls back to the
    unscoped table URL."""
    base = f"https://data.census.gov/table?q={TABLE}&y={ACS_YEAR}"
    if fips is None:
        return base
    return f"{base}&g=0400000US{fips}"


def upsert_source(cur, state_code, fips):
    cur.execute(
        """
        INSERT INTO sources (slug, kind, publisher, title, release, table_ref, url, retrieved_on)
        VALUES (%(slug)s, 'dataset', %(publisher)s, %(title)s, %(release)s, %(table_ref)s, %(url)s, %(retrieved_on)s)
        ON CONFLICT (slug) DO UPDATE SET
            url          = EXCLUDED.url,
            retrieved_on = EXCLUDED.retrieved_on
        RETURNING id
        """,
        {
            "slug": f"acs1-{ACS_YEAR}-{TABLE.lower()}-{state_code.lower()}",
            "publisher": "U.S. Census Bureau",
            "title": "American Community Survey 1-Year Estimates",
            "release": str(ACS_YEAR),
            "table_ref": TABLE,
            "url": _source_url_for(fips),
            "retrieved_on": date.today(),
        },
    )
    return cur.fetchone()[0]


def upsert_all_sources(cur, observations, code_to_fips):
    source_id_by_code = {}
    for state_code in sorted({o["state_code"] for o in observations}):
        fips = None if state_code == "US" else code_to_fips.get(state_code)
        source_id_by_code[state_code] = upsert_source(cur, state_code, fips)
    return source_id_by_code


def upsert_observations(cur, observations, source_id_by_code):
    sql = """
        INSERT INTO observations
            (state_code, metric_slug, year, female_value, male_value,
             female_moe, male_moe, suppressed, source_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            "poverty_rate",
            o["year"],
            o["female_value"],
            o["male_value"],
            o["female_moe"],
            o["male_moe"],
            o["suppressed"],
            source_id_by_code[o["state_code"]],
        )
        for o in observations
    ]
    cur.executemany(sql, values)
    return len(values)


def main():
    print(f"Fetching ACS {ACS_YEAR} 1-year estimates, subject table {TABLE} (poverty rate by sex)...")
    header, state_rows, us_header, us_rows = fetch_census_data()
    print(f"  received {len(state_rows)} state rows + {len(us_rows)} national row(s) from the Census API")

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT code, fips FROM states")
            rows = cur.fetchall()
            fips_to_code = {fips: code for code, fips in rows}
            code_to_fips = {code: fips for code, fips in rows}

            observations = build_observations(header, state_rows, us_header, us_rows, fips_to_code)
            suppressed_count = sum(1 for o in observations if o["suppressed"])
            print(f"  built {len(observations)} observation rows ({suppressed_count} suppressed)")

            source_id_by_code = upsert_all_sources(cur, observations, code_to_fips)
            print(f"  created/updated {len(source_id_by_code)} per-state source rows")

            n_loaded = upsert_observations(cur, observations, source_id_by_code)
            print(f"  loaded {n_loaded} observations into the database")
        conn.commit()

    print("Done. Check the `observations` table, or query `observation_gaps` to see the computed gap.")


if __name__ == "__main__":
    main()
