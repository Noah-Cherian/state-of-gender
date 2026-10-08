"""
State of Gender -- ingest script: incarceration rate, by sex, all 50 states + US

Source: Bureau of Justice Statistics (BJS), "Prisoners in 2023 - Statistical
Tables" (NCJ 310197, September 2025), Table 7: imprisonment rates of
sentenced prisoners under state or federal jurisdiction, per 100,000
residents of the same sex, at December 31 of 2022 and 2023.

BJS publishes this as a PDF only. Table 7 was pulled out of the PDF's text
by a script (not retyped by hand) into `data/bjs_prisoners_2023_table7.csv`,
which keeps BJS's footnote letters for each state. This script reads that
file and loads the latest year (2023); the 2022 rows stay in the file.

What this does:
  1. Reads the CSV and sanity-checks every row: each rate must be a
     positive number, and the all-sexes total must sit between the women's
     and men's rates (it's a population-weighted average of the two, so a
     row that breaks this was misread).
  2. Writes one `sources` row per state. Every state links to the
     BJS publication page (BJS has no per-state pages); the source note
     names Table 7 and spells out any BJS footnote that applies to that
     state -- e.g. six states run prisons and jails as one system, so their
     numbers include jail populations and aren't strictly comparable.
  3. Writes one `observations` row per state.

Gaps, on purpose:
  * No DC row. Since 2001, people sentenced for a felony in DC have been
    the federal prison system's responsibility, so DC has no state figure.
  * No margin of error. These are counts of actual prisoners (divided by
    Census population), not survey estimates.

Safe to re-run: every insert is an upsert (insert-or-update).

Run it with:
    python3 ingest_incarceration_rate.py
"""

import csv
import os
from datetime import date
from pathlib import Path

import psycopg
from dotenv import load_dotenv

load_dotenv()

DATA_FILE = Path(__file__).parent / "data" / "bjs_prisoners_2023_table7.csv"
METRIC_SLUG = "incarceration_rate"
PUBLISHER = "Bureau of Justice Statistics"
TITLE = "Prisoners in 2023 - Statistical Tables"
PUBLICATION_URL = "https://bjs.ojp.gov/library/publications/prisoners-2023-statistical-tables"
NATIONAL_LABEL = "U.S. total"

# BJS's Table 7 footnotes, reworded for site visitors. Letters match the
# `footnotes` column in the CSV.
FOOTNOTES = {
    "b": "This state runs prisons and jails as one system, so its figures include jail populations as well as prisoners. That makes it not strictly comparable with most other states.",
    "c": "Does not count people held in federal prisons or other states' prisons.",
    "d": "Includes a small number of prisoners sentenced to 1 year or less.",
    "e": "Includes people waiting in county jail to be moved to state prison.",
    "f": "Includes people serving 1 to 2.5 years in local jails, which Massachusetts law treats as the line between prison and jail.",
    "g": "Excludes people serving time in residential confinement.",
}


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def check_rows(rows):
    problems = []
    for r in rows:
        total, male, female = int(r["total"]), int(r["male"]), int(r["female"])
        if min(total, male, female) <= 0:
            problems.append(f"{r['jurisdiction']} {r['year']}: a rate is zero or negative")
        if not (min(male, female) <= total <= max(male, female)):
            problems.append(f"{r['jurisdiction']} {r['year']}: total {total} is not between {female} and {male}")
        for letter in filter(None, r["footnotes"].split(",")):
            if letter not in FOOTNOTES:
                problems.append(f"{r['jurisdiction']}: unknown footnote '{letter}'")
    if problems:
        raise SystemExit("The data file has rows that don't check out:\n  " + "\n  ".join(problems))


def source_note(row):
    note = (
        f"From Table 7 of BJS's \"{TITLE}\" (the source link opens the "
        "publication page; the table is in the PDF there). Sentenced prisoners "
        f"per 100,000 residents of the same sex, December 31, {row['year']}."
    )
    for letter in filter(None, row["footnotes"].split(",")):
        note += " " + FOOTNOTES[letter]
    return note


def build_observations(rows, name_to_code):
    """Only the latest year in the file is loaded. The state page shows one
    card per stored row, so storing 2022 too would show two incarceration
    cards per state. The 2022 rows stay in the CSV for later use."""
    latest_year = max(int(r["year"]) for r in rows)
    observations = []
    for r in rows:
        if int(r["year"]) != latest_year:
            continue
        name = r["jurisdiction"]
        state_code = "US" if name == NATIONAL_LABEL else name_to_code.get(name)
        if state_code is None:
            print(f"  skipping unrecognized jurisdiction: {name!r}")
            continue
        observations.append(
            {
                "state_code": state_code,
                "year": int(r["year"]),
                "female_value": int(r["female"]),
                "male_value": int(r["male"]),
                "note": source_note(r),
            }
        )
    return observations


def upsert_source(cur, obs):
    cur.execute(
        """
        INSERT INTO sources (slug, kind, publisher, title, release, table_ref, url, retrieved_on, notes)
        VALUES (%(slug)s, 'report', %(publisher)s, %(title)s, %(release)s, %(table_ref)s, %(url)s, %(retrieved_on)s, %(notes)s)
        ON CONFLICT (slug) DO UPDATE SET
            url          = EXCLUDED.url,
            retrieved_on = EXCLUDED.retrieved_on,
            notes        = EXCLUDED.notes
        RETURNING id
        """,
        {
            "slug": f"bjs-p23st-table7-{obs['year']}-{obs['state_code'].lower()}",
            "publisher": PUBLISHER,
            "title": TITLE,
            "release": "2025",
            "table_ref": "Table 7",
            "url": PUBLICATION_URL,
            "retrieved_on": date.today(),
            "notes": obs["note"],
        },
    )
    return cur.fetchone()[0]


def upsert_observations(cur, observations, source_ids):
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
        (o["state_code"], METRIC_SLUG, o["year"], o["female_value"], o["male_value"], source_id)
        for o, source_id in zip(observations, source_ids)
    ]
    cur.executemany(sql, values)
    return len(values)


def main():
    print(f"Reading {DATA_FILE.name} (BJS Prisoners in 2023, Table 7)...")
    rows = read_rows(DATA_FILE)
    check_rows(rows)
    print(f"  read {len(rows)} rows; every row checks out")

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT code, name FROM states")
            name_to_code = {name: code for code, name in cur.fetchall()}

            observations = build_observations(rows, name_to_code)
            print(f"  built {len(observations)} observation rows for {observations[0]['year']}")

            source_ids = [upsert_source(cur, o) for o in observations]
            print(f"  created/updated {len(source_ids)} source rows")

            n_loaded = upsert_observations(cur, observations, source_ids)
            print(f"  loaded {n_loaded} observations into the database")
        conn.commit()

    print("Done. Check the `observations` table, or query `observation_gaps` to see the computed gap.")


if __name__ == "__main__":
    main()
