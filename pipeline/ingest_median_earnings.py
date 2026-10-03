"""
State of Gender -- ingest script: median earnings, by sex, all states + DC + US

What this does:
  1. Calls the Census API for ACS 1-Year Estimates, table B20017
     (median earnings of full-time, year-round workers, by sex).
  2. Looks up each state's postal code from your `states` table, so this
     script never has to guess at FIPS-to-state mapping on its own.
  3. Writes one `sources` row describing exactly where this data came from.
  4. Writes one `observations` row per state for the 'median_earnings' metric.

Safe to re-run: every insert is an upsert (insert-or-update), so running this
script twice updates the existing rows instead of creating duplicates. That
matters because Census revises estimates and you'll want to refresh later.

Run it with:
    python3 ingest_median_earnings.py
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
# ACS 1-Year Estimates only cover states (and the nation), not counties,
# and only areas with 65,000+ people -- which is every state and DC.
ACS_YEAR = 2023
ACS_DATASET_URL = f"https://api.census.gov/data/{ACS_YEAR}/acs/acs1"
TABLE = "B20017"

# Confirmed against the Census variable definitions:
#   B20017_003E = median earnings, male,   worked full-time year-round
#   B20017_006E = median earnings, female, worked full-time year-round
#   the _M suffix on each is that estimate's margin of error
MALE_VAR = "B20017_003E"
MALE_MOE_VAR = "B20017_003M"
FEMALE_VAR = "B20017_006E"
FEMALE_MOE_VAR = "B20017_006M"

# Census uses large negative numbers as placeholders when an estimate
# couldn't be computed (too few respondents in that state for that year).
SUPPRESSED_SENTINELS = {-666666666, -222222222, -999999999}


def fetch_census_data():
    """Return (header, state_rows, us_rows) as two separate groups.

    They're kept separate on purpose: the states query tags each row with a
    "state" column holding a two-digit FIPS code (e.g. '13' for Georgia),
    but the national query tags its one row with a different column, "us",
    whose value ('1') isn't a FIPS code at all -- it's just the Census API's
    way of saying "the whole country" and happens to share no numbering
    scheme with the state codes. Mixing them into one lookup caused the
    national row to get silently dropped in the first version of this
    script. Keeping them separate means we never need to reconcile the two.
    """
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
    """Census sends numbers as strings; some are 'not available' sentinels."""
    value = int(raw_value)
    return None if value in SUPPRESSED_SENTINELS else value


def _row_to_observation(row, col, state_code):
    """Shared logic for turning one Census row into an observation dict,
    once we already know which state (or 'US') it belongs to."""
    male_value = to_number_or_none(row[col[MALE_VAR]])
    female_value = to_number_or_none(row[col[FEMALE_VAR]])
    male_moe = to_number_or_none(row[col[MALE_MOE_VAR]])
    female_moe = to_number_or_none(row[col[FEMALE_MOE_VAR]])

    # the schema requires: if either value is missing, the row must be
    # flagged suppressed (see observations_missing_must_be_flagged)
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
    """Turn raw Census rows into dicts ready to insert into `observations`."""
    state_col = {name: i for i, name in enumerate(header)}
    observations = []

    for row in state_rows:
        fips = row[state_col["state"]]
        state_code = fips_to_code.get(fips)
        if state_code is None:
            print(f"  skipping unrecognized FIPS code: {fips}")
            continue
        observations.append(_row_to_observation(row, state_col, state_code))

    # the national row always means 'US' -- no lookup needed, no risk of
    # a mismatched code silently dropping it
    us_col = {name: i for i, name in enumerate(us_header)}
    for row in us_rows:
        observations.append(_row_to_observation(row, us_col, "US"))

    return observations


def upsert_source(cur):
    """Insert this release's source row, or update its retrieved_on if it
    already exists. Returns the source's id either way."""
    cur.execute(
        """
        INSERT INTO sources (slug, kind, publisher, title, release, table_ref, url, retrieved_on)
        VALUES (%(slug)s, 'dataset', %(publisher)s, %(title)s, %(release)s, %(table_ref)s, %(url)s, %(retrieved_on)s)
        ON CONFLICT (slug) DO UPDATE SET retrieved_on = EXCLUDED.retrieved_on
        RETURNING id
        """,
        {
            "slug": f"acs1-{ACS_YEAR}-{TABLE.lower()}",
            "publisher": "U.S. Census Bureau",
            "title": "American Community Survey 1-Year Estimates",
            "release": str(ACS_YEAR),
            "table_ref": TABLE,
            "url": f"https://data.census.gov/table?q={TABLE}&y={ACS_YEAR}",
            "retrieved_on": date.today(),
        },
    )
    return cur.fetchone()[0]


def upsert_observations(cur, observations, source_id):
    """Insert all observation rows, updating any that already exist."""
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
            "median_earnings",
            o["year"],
            o["female_value"],
            o["male_value"],
            o["female_moe"],
            o["male_moe"],
            o["suppressed"],
            source_id,
        )
        for o in observations
    ]
    cur.executemany(sql, values)
    return len(values)


def main():
    print(f"Fetching ACS {ACS_YEAR} 1-year estimates, table {TABLE} (median earnings by sex)...")
    header, state_rows, us_header, us_rows = fetch_census_data()
    print(f"  received {len(state_rows)} state rows + {len(us_rows)} national row(s) from the Census API")

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT code, fips FROM states")
            fips_to_code = {fips: code for code, fips in cur.fetchall()}

            observations = build_observations(header, state_rows, us_header, us_rows, fips_to_code)
            suppressed_count = sum(1 for o in observations if o["suppressed"])
            print(f"  built {len(observations)} observation rows ({suppressed_count} suppressed)")

            source_id = upsert_source(cur)
            print(f"  source row id: {source_id}")

            n_loaded = upsert_observations(cur, observations, source_id)
            print(f"  loaded {n_loaded} observations into the database")
        conn.commit()

    print("Done. Check the `observations` table, or query `observation_gaps` to see the computed gap.")


if __name__ == "__main__":
    main()
