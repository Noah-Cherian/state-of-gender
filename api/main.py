"""
State of Gender API.

Serves the data in Neon as JSON, for the frontend to call. Read-only on
purpose -- nothing here writes to the database; that's the pipeline's job.

Run locally with:
    uvicorn main:app --reload
Then open http://127.0.0.1:8000/docs for an interactive page that lists
every endpoint and lets you try them in the browser.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from psycopg.rows import dict_row

from database import pool

app = FastAPI(title="State of Gender API")

# The frontend will run on a different address (e.g. localhost:5173) than
# this API (localhost:8000). Browsers block requests between different
# addresses by default unless the server explicitly allows it -- that's
# what this does, for local development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """A simple endpoint to confirm the API and database are both up."""
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1")
        cur.fetchone()
    return {"status": "ok"}


@app.get("/api/metrics")
def list_metrics():
    """Every metric that has data loaded, grouped by category -- powers the
    dropdown. A metric with no observations yet (or one that was shelved,
    like statewide elected officials) is left out, so the dropdown never
    offers an empty map. It reappears on its own once data is loaded."""
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT m.slug, m.name, m.definition, m.unit,
                   c.slug AS category_slug, c.name AS category_name
            FROM metrics m
            JOIN categories c ON c.slug = m.category_slug
            WHERE EXISTS (
                SELECT 1 FROM observations o WHERE o.metric_slug = m.slug
            )
            ORDER BY c.sort_order, m.sort_order
            """
        )
        return cur.fetchall()


@app.get("/api/metrics/{slug}")
def metric_map(slug: str):
    """One metric's most recent value for every state -- powers the choropleth map."""
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT slug, name, definition, unit FROM metrics WHERE slug = %s",
            (slug,),
        )
        metric = cur.fetchone()
        if metric is None:
            raise HTTPException(status_code=404, detail=f"No metric named '{slug}'")

        cur.execute(
            """
            SELECT o.state_code, s.name AS state_name, o.year,
                   o.female_value::float AS female_value,
                   o.male_value::float AS male_value,
                   o.suppressed,
                   src.title AS source_title, src.url AS source_url,
                   src.release AS source_release
            FROM observations o
            JOIN states s ON s.code = o.state_code
            JOIN sources src ON src.id = o.source_id
            WHERE o.metric_slug = %s
            ORDER BY o.year DESC, s.code
            """,
            (slug,),
        )
        rows = cur.fetchall()

        # a metric could have more than one year loaded later; keep only
        # each state's most recent one for the map
        latest_by_state = {}
        for row in rows:
            latest_by_state.setdefault(row["state_code"], row)

        return {"metric": metric, "values": list(latest_by_state.values())}


@app.get("/api/states")
def list_states():
    """Every state (+ DC + US) -- powers the map's clickable regions and any state picker.

    Includes `fips`: the two-digit code standard US map data (like the one the
    frontend draws from) uses to identify each state -- that's what lets the
    map match its shapes to our rows without a separate lookup table.
    """
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT code, name, kind, fips FROM states ORDER BY name")
        return cur.fetchall()


@app.get("/api/states/{code}")
def state_profile(code: str):
    """One state's full profile: every metric it has data for, grouped by category."""
    code = code.upper()
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT code, name, kind FROM states WHERE code = %s", (code,))
        state = cur.fetchone()
        if state is None:
            raise HTTPException(status_code=404, detail=f"No state with code '{code}'")

        cur.execute(
            """
            SELECT c.slug AS category_slug, c.name AS category_name,
                   m.slug AS metric_slug, m.name AS metric_name,
                   m.unit, m.definition,
                   o.year,
                   o.female_value::float AS female_value,
                   o.male_value::float AS male_value,
                   o.suppressed,
                   src.title AS source_title, src.url AS source_url,
                   src.release AS source_release,
                   src.notes AS source_notes
            FROM observations o
            JOIN metrics m ON m.slug = o.metric_slug
            JOIN categories c ON c.slug = m.category_slug
            JOIN sources src ON src.id = o.source_id
            WHERE o.state_code = %s
            ORDER BY c.sort_order, m.sort_order, o.year DESC
            """,
            (code,),
        )
        observations = cur.fetchall()

        return {"state": state, "observations": observations}
