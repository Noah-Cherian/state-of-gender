"""
State of Gender -- ingest script: STEM degree share, by sex, all states + DC + US

What this does:
  1. Calls the Census API for ACS 1-Year Estimates, DETAILED table B15011
     (sex by age by field of bachelor's degree for first major, population
     25 years and over).
  2. For each sex, sums the "Science and Engineering" count across all
     three age brackets (25-39, 40-64, 65+), and divides by that sex's
     total bachelor's-degree-holder population, to get "share of bachelor's
     degree holders whose first major was Science and Engineering" as a
     percentage. Like bachelor's degree rate, B15011 only gives raw counts
     per age-bracket/field combination -- no ready-made percentage -- so
     the rate has to be computed here.
  3. Writes one `sources` row per state, with a Census deep link scoped to
     that state (same pattern as the other ingest scripts).
  4. Writes one `observations` row per state for the 'stem_degree_share'
     metric.

A deliberate gap, same as bachelor's degree rate: this script does NOT
compute a margin of error for the resulting percentage. Combining each
bracket's MOE into one derived-ratio MOE requires Census's own compound-MOE
approximation formula -- getting that subtly wrong would be worse than
leaving it blank, so female_moe/male_moe are left NULL here on purpose.

Every variable code below was checked one at a time against api.census.gov's
own variable metadata before being used -- same discipline as every other
script in this project. B15011 turned out to have a clean, regular
structure once checked (unlike B23001, which didn't, and got shelved for
exactly that reason): each sex's block is 3 age brackets x 6 lines each
(bracket total, then 5 field categories in a fixed order -- Science and
Engineering is always first, at +1 from the bracket total).

Safe to re-run: every insert is an upsert (insert-or-update).

Run it with:
    python3 ingest_stem_degree_share.py
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
# A detailed table, like median earnings' B20017 and bachelor's degree
# rate's B15002 -- no "/subject" in the URL.
ACS_DATASET_URL = f"https://api.census.gov/data/{ACS_YEAR}/acs/acs1"
TABLE = "B15011"

# Confirmed one at a time against the Census variable metadata
# (api.census.gov/data/2023/acs/acs1/variables/<code>.json):
#   B15011_003E / 009E / 015E = Male: 25-39 / 40-64 / 65+ (bracket total)
#   B15011_004E / 010E / 016E = Male: same brackets, Science and Engineering
#   B15011_022E / 028E / 034E = Female: 25-39 / 40-64 / 65+ (bracket total)
#   B15011_023E / 029E / 035E = Female: same brackets, Science and Engineering
MALE_TOTAL_VARS = ["B15011_003E", "B15011_009E", "B15011_015E"]
MALE_STEM_VARS = ["B15011_004E", "B15011_010E", "B15011_016E"]
FEMALE_TOTAL_VARS = ["B15011_022E", "B15011_028E", "B15011_034E"]
FEMALE_STEM_VARS = ["B15011_023E", "B15011_029E", "B15011_035E"]

ALL_VARS = [*MALE_TOTAL_VARS, *MALE_STEM_VARS, *FEMALE_TOTAL_VARS, *FEMALE_STEM_VARS]

# Census uses large negative numbers as placeholders when an estimate
# couldn't be computed (too few respondents in that state for that year).
SUPPRESSED_SENTINELS = {-666666666, -222222222, -999999999}


def fetch_census_data():
    """Return (header, state_rows, us_header, us_rows) -- kept separate for
    the same reason as the other scripts: the national query's "us" column
    value isn't a FIPS code, so it can't share a lookup with the state rows."""
    get_vars = ",".join(["NAME", *ALL_VARS])

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


def to_count_or_none(raw_value):
    """Census sends counts as strings; some are 'not available' sentinels."""
    value = int(raw_value)
    return None if value in SUPPRESSED_SENTINELS else value


def _rate_for_sex(row, col, total_vars, stem_vars):
    """Sum Science-and-Engineering counts across all three age brackets,
    divide by the sum of each bracket's total across the same brackets.
    Returns None (and the caller treats the row as suppressed) if any one
    of the six values involved is missing -- a partial sum would distort
    the real rate, so a missing component suppresses the whole calculation
    rather than silently using an incomplete total."""
    totals = [to_count_or_none(row[col[v]]) for v in total_vars]
    stem_counts = [to_count_or_none(row[col[v]]) for v in stem_vars]

    if any(t is None for t in totals) or any(s is None for s in stem_counts):
        return None

    total = sum(totals)
    if total == 0:
        return None

    return round(sum(stem_counts) / total * 100, 1)


def _row_to_observation(row, col, state_code):
    male_value = _rate_for_sex(row, col, MALE_TOTAL_VARS, MALE_STEM_VARS)
    female_value = _rate_for_sex(row, col, FEMALE_TOTAL_VARS, FEMALE_STEM_VARS)

    suppressed = male_value is None or female_value is None

    return {
        "state_code": state_code,
        "year": ACS_YEAR,
        "female_value": female_value,
        "male_value": male_value,
        "female_moe": None,  # see the module docstring for why
        "male_moe": None,
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
            "stem_degree_share",
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
    print(f"Fetching ACS {ACS_YEAR} 1-year estimates, table {TABLE} (STEM degree share by sex)...")
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
