"""
State of Gender -- ingest script: life expectancy at birth, by sex, all states + DC

What this does:
  1. Calls the CDC's open-data API (data.cdc.gov) for the dataset
     "U.S. State Life Expectancy by Sex, 2021", published by the National
     Center for Health Statistics (NCHS). This is NOT Census data -- it's
     the first script in this project that talks to a different agency.
  2. Looks up each state's postal code from your `states` table, matching
     on the state's NAME (CDC labels rows "Georgia", not "13" or "GA").
  3. Writes one `sources` row per state, each linking to the CDC's page
     for this dataset (a readable table of all states -- see
     `_source_url_for` for why it isn't a state-specific link).
  4. Writes one `observations` row per state for the 'life_expectancy'
     metric.

Three things that differ from the Census scripts:

  * No API key. CDC's open-data API allows anonymous requests.

  * No national row. This dataset covers the 50 states and DC only -- there
    is no "United States" record in it -- so no 'US' observation is written.
    That is a gap in the source, not something this script skips.

  * The source publishes a STANDARD ERROR, not a margin of error. The
    Census numbers elsewhere in this project are 90%-confidence margins of
    error, so to keep the `female_moe` / `male_moe` columns meaning the same
    thing everywhere, this script converts: MOE = 1.645 x standard error.
    That is the standard definition of a 90% margin of error (it is the
    same multiplier Census itself uses), not an approximation. The
    conversion is also recorded in each source row's `notes`.

The field names used below (`area`, `sex`, `leb`, `se`) and the three `sex`
labels ("Total", "Male", "Female") were read off the live API response
before being used here, not assumed.

Safe to re-run: every insert is an upsert (insert-or-update).

Run it with:
    python3 ingest_life_expectancy.py
"""

import os
from datetime import date

import psycopg
import requests
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

# --- About this specific release -------------------------------------------
DATA_YEAR = 2021
DATASET_ID = "it4f-frdc"  # CDC's identifier for this exact dataset
DATASET_API_URL = f"https://data.cdc.gov/resource/{DATASET_ID}.json"
DATASET_PAGE_URL = (
    "https://data.cdc.gov/National-Center-for-Health-Statistics/"
    f"U-S-State-Life-Expectancy-by-Sex-2021/{DATASET_ID}"
)
DATASET_TITLE = "U.S. State Life Expectancy by Sex, 2021"
PUBLISHER = "National Center for Health Statistics (CDC)"

# Turns a standard error into a 90%-confidence margin of error.
SE_TO_MOE_90 = 1.645

SOURCE_NOTE = (
    "Life expectancy at birth from NCHS annual complete period life tables. "
    "The source publishes a standard error; the margin of error stored with "
    "each observation is 1.645 x that standard error (90% confidence)."
)


def fetch_cdc_data():
    """Return the dataset as a list of dicts, one per (state, sex) pair.
    The whole dataset is 153 rows (51 areas x 3 sex labels); the limit is
    set well above that so nothing is silently cut off."""
    resp = requests.get(DATASET_API_URL, params={"$limit": 1000}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def to_number_or_none(raw_value):
    """CDC sends numbers as strings. A missing or non-numeric value becomes
    None rather than crashing the whole run."""
    if raw_value is None:
        return None
    try:
        return float(raw_value)
    except ValueError:
        return None


def build_observations(records, name_to_code):
    """Group the flat (state, sex) rows into one observation per state."""
    by_area = {}
    for record in records:
        by_area.setdefault(record.get("area"), {})[record.get("sex")] = record

    observations = []
    for area, by_sex in sorted(by_area.items(), key=lambda item: str(item[0])):
        state_code = name_to_code.get(area)
        if state_code is None:
            print(f"  skipping unrecognized area name: {area!r}")
            continue

        male = by_sex.get("Male", {})
        female = by_sex.get("Female", {})

        male_value = to_number_or_none(male.get("leb"))
        female_value = to_number_or_none(female.get("leb"))
        male_se = to_number_or_none(male.get("se"))
        female_se = to_number_or_none(female.get("se"))

        observations.append(
            {
                "state_code": state_code,
                "area": area,
                "year": DATA_YEAR,
                "female_value": female_value,
                "male_value": male_value,
                "female_moe": None if female_se is None else round(female_se * SE_TO_MOE_90, 3),
                "male_moe": None if male_se is None else round(male_se * SE_TO_MOE_90, 3),
                "suppressed": male_value is None or female_value is None,
            }
        )

    return observations


def _source_url_for(area):
    """The CDC's own page for this dataset: a readable table of every
    state, which a visitor can sort or search for their state.

    This is the same page for every state. CDC's API can return just one
    state's rows, but only as raw JSON, which is not something a visitor
    can read -- so the readable page wins over the state-specific one."""
    return DATASET_PAGE_URL


def upsert_source(cur, state_code, area):
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
            "slug": f"nchs-life-expectancy-{DATA_YEAR}-{state_code.lower()}",
            "publisher": PUBLISHER,
            "title": DATASET_TITLE,
            "release": str(DATA_YEAR),
            "table_ref": DATASET_ID,
            "url": _source_url_for(area),
            "retrieved_on": date.today(),
            "notes": SOURCE_NOTE,
        },
    )
    return cur.fetchone()[0]


def upsert_all_sources(cur, observations):
    return {o["state_code"]: upsert_source(cur, o["state_code"], o["area"]) for o in observations}


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
            "life_expectancy",
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
    print(f"Fetching CDC/NCHS dataset {DATASET_ID} ({DATASET_TITLE})...")
    records = fetch_cdc_data()
    print(f"  received {len(records)} rows from the CDC API")

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT code, name FROM states")
            name_to_code = {name: code for code, name in cur.fetchall()}

            observations = build_observations(records, name_to_code)
            suppressed_count = sum(1 for o in observations if o["suppressed"])
            print(f"  built {len(observations)} observation rows ({suppressed_count} suppressed)")

            source_id_by_code = upsert_all_sources(cur, observations)
            print(f"  created/updated {len(source_id_by_code)} per-state source rows")

            n_loaded = upsert_observations(cur, observations, source_id_by_code)
            print(f"  loaded {n_loaded} observations into the database")
        conn.commit()

    print("Done. Check the `observations` table, or query `observation_gaps` to see the computed gap.")


if __name__ == "__main__":
    main()
