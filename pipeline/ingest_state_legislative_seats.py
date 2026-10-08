"""
State of Gender -- ingest script: share of state legislative seats, by sex,
all 50 states + US

Source: the Center for American Women and Politics (CAWP) at Rutgers
University, which tracks every woman serving in a state legislature. CAWP
has no API or download for this, so its figures were copied from each
state's CAWP page into `data/cawp_state_legislatures.csv` (one row per
state, with the CAWP page each row came from listed in SOURCE_URL_BASE
below). This script reads that file.

What this does:
  1. Reads the CSV and checks every row adds up: senate + house women must
     equal the total, senate + house seats must equal the total, and the
     percentage must match women / seats. A copying mistake would break at
     least one of those, so the script refuses to load if any row fails.
  2. Women's value = CAWP's percent of seats held by women.
     Men's value   = the percent of seats NOT held by women. CAWP counts
     women only, so this also includes any seat that happened to be vacant
     -- usually zero to a few seats per state. That is stated on the site
     in each source note so it isn't hidden.
  3. US value = the 50 states added together (7,386 seats in total).
  4. Writes one `sources` row per state, linking to that state's own CAWP
     page, and one `observations` row per state.

Gaps, on purpose:
  * No DC row. DC has a city council, not a state legislature, and CAWP
    doesn't include it in these figures.
  * Oregon is 2025, not 2026. When the figures were collected, CAWP's
    Oregon page had no 2026 row yet, so the most recent year it shows is
    used and labeled as such.
  * No margin of error. These are head counts of actual legislators, not
    survey estimates, so there is no sampling error to report.

Safe to re-run: every insert is an upsert (insert-or-update).

Run it with:
    python3 ingest_state_legislative_seats.py
"""

import csv
import os
from datetime import date
from pathlib import Path

import psycopg
from dotenv import load_dotenv

load_dotenv()

DATA_FILE = Path(__file__).parent / "data" / "cawp_state_legislatures.csv"
PUBLISHER = "Center for American Women and Politics (CAWP), Rutgers University"
TITLE = "Women in State Legislatures"
SOURCE_URL_BASE = "https://cawp.rutgers.edu/data/state-state-information"
METRIC_SLUG = "state_legislative_seats"

MEN_NOTE = (
    "CAWP counts women legislators only. The share shown for men is every "
    "seat not held by a woman, so it also includes any seats that were "
    "vacant at the time."
)


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _int(value):
    return int(value) if value else 0  # Nebraska has no house: blank = 0


def check_rows(rows):
    """Stop with a clear message if any row doesn't add up."""
    problems = []
    for r in rows:
        women = _int(r["total_women"])
        seats = _int(r["total_seats"])
        if _int(r["senate_women"]) + _int(r["house_women"]) != women:
            problems.append(f"{r['state']}: senate + house women != total women")
        if _int(r["senate_seats"]) + _int(r["house_seats"]) != seats:
            problems.append(f"{r['state']}: senate + house seats != total seats")
        if round(women / seats * 100, 1) != float(r["pct_women"]):
            problems.append(f"{r['state']}: {women}/{seats} does not round to {r['pct_women']}%")
    if problems:
        raise SystemExit("The data file has rows that don't add up:\n  " + "\n  ".join(problems))


def state_page_url(state_name):
    """CAWP's page for one state: lowercase, spaces become hyphens."""
    return f"{SOURCE_URL_BASE}/{state_name.lower().replace(' ', '-')}"


def _shares(women, seats):
    female = round(women / seats * 100, 1)
    male = round((seats - women) / seats * 100, 1)
    return female, male


def build_observations(rows, name_to_code):
    observations = []
    for r in rows:
        state_code = name_to_code.get(r["state"])
        if state_code is None:
            print(f"  skipping unrecognized state name: {r['state']!r}")
            continue
        female, male = _shares(_int(r["total_women"]), _int(r["total_seats"]))
        year = int(r["year"])
        note = f"Figures for {year}, from the State Legislature table on CAWP's {r['state']} page. {MEN_NOTE}"
        if r["state"] == "Oregon" and year != 2026:
            note += " CAWP's Oregon page did not yet list 2026 when these figures were collected, so 2025 is shown."
        observations.append(
            {
                "state_code": state_code,
                "year": year,
                "female_value": female,
                "male_value": male,
                "url": state_page_url(r["state"]),
                "note": note,
            }
        )

    # national: add every state together
    total_women = sum(_int(r["total_women"]) for r in rows)
    total_seats = sum(_int(r["total_seats"]) for r in rows)
    female, male = _shares(total_women, total_seats)
    observations.append(
        {
            "state_code": "US",
            "year": max(int(r["year"]) for r in rows),
            "female_value": female,
            "male_value": male,
            "url": SOURCE_URL_BASE,
            "note": (
                f"All 50 state legislatures added together: {total_women:,} women "
                f"out of {total_seats:,} seats, using each state's figures from "
                f"CAWP (Oregon's are from 2025). {MEN_NOTE}"
            ),
        }
    )
    return observations


def upsert_source(cur, obs):
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
            "slug": f"cawp-state-legislatures-{obs['year']}-{obs['state_code'].lower()}",
            "publisher": PUBLISHER,
            "title": TITLE,
            "release": str(obs["year"]),
            "table_ref": "State Legislature",
            "url": obs["url"],
            "retrieved_on": date.today(),
            "notes": obs["note"],
        },
    )
    return cur.fetchone()[0]


def upsert_observations(cur, observations, source_id_by_code):
    sql = """
        INSERT INTO observations
            (state_code, metric_slug, year, female_value, male_value,
             female_moe, male_moe, suppressed, source_id)
        VALUES (%s, %s, %s, %s, %s, NULL, NULL, false, %s)
        ON CONFLICT (state_code, metric_slug, year) DO UPDATE SET
            female_value = EXCLUDED.female_value,
            male_value   = EXCLUDED.male_value,
            female_moe   = EXCLUDED.female_moe,
            male_moe     = EXCLUDED.male_moe,
            suppressed   = EXCLUDED.suppressed,
            source_id    = EXCLUDED.source_id
    """
    values = [
        (o["state_code"], METRIC_SLUG, o["year"], o["female_value"], o["male_value"],
         source_id_by_code[o["state_code"]])
        for o in observations
    ]
    cur.executemany(sql, values)
    return len(values)


def main():
    print(f"Reading {DATA_FILE.name} (CAWP state legislature figures)...")
    rows = read_rows(DATA_FILE)
    check_rows(rows)
    print(f"  read {len(rows)} state rows; every row adds up")

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT code, name FROM states")
            name_to_code = {name: code for code, name in cur.fetchall()}

            observations = build_observations(rows, name_to_code)
            print(f"  built {len(observations)} observation rows")

            source_id_by_code = {o["state_code"]: upsert_source(cur, o) for o in observations}
            print(f"  created/updated {len(source_id_by_code)} per-state source rows")

            n_loaded = upsert_observations(cur, observations, source_id_by_code)
            print(f"  loaded {n_loaded} observations into the database")
        conn.commit()

    print("Done. Check the `observations` table, or query `observation_gaps` to see the computed gap.")


if __name__ == "__main__":
    main()
