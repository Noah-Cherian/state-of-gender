# State of Gender

A source-first map of measurable gender differences across every US state — legal, economic, educational, health, and social. Every number on the map links back to the source where it came from (metadata like the publisher, the year, the precise definition, and (for laws) the statute itself).

**Live site:** (https://state-of-gender.vercel.app/)

## Why this exists

Gender gap debates and discussions have been widespread on the internet for a long time. However, most participants in arguments rely heavily on anecdotal evidence as compared to data. So, my goal was to compile and present data into a intuitive, unbiased map. It is a neutral, side-by-side comparison where colors show direction and size of gap for any given metric. My hope is to continue to organize and extract data into this project so more people have relatively easy access to the numbers for an issue that strains our society to this day.


## Status

This is a work in progress, being built incrementally. Current state:

- **Database schema** — deployed to Postgres (hosted on [Neon](https://neon.tech)). Covers categories, states, metrics, sources, observations, law topics, and laws, with constraints that enforce the sourcing rules above (e.g., a law can't have a status without a citation; a missing data point must be explicitly flagged, not just left blank).
- **Data pipeline** — eleven metrics live end-to-end: median earnings by sex, for all 50 states + DC + the US, from the Census Bureau's American Community Survey. Each state's data point links to its own state-scoped Census page, not a generic one.
- **API** — a FastAPI backend serving states, metrics, and per-state profiles.
- **Frontend** — a React app with an interactive, color-coded US map for the live metric, plus a details panel showing a clicked state's values and sourcing.

See [Roadmap](#roadmap) for what's next.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Database | PostgreSQL via [Neon](https://neon.tech) |
| Backend | [FastAPI](https://fastapi.tiangolo.com/) (Python) | Lightweight, typed, fast to iterate on for a handful of read-only JSON endpoints. |
| Data pipeline | Python scripts, `psycopg` | Idempotent ingest scripts that pull from public APIs (starting with the Census Bureau) and upsert into Postgres — safe to re-run as sources revise their data. |
| Frontend | React + [Vite](https://vitejs.dev/) | Fast dev loop; component model fits a map + detail-panel UI well. |
| Map rendering | [react-simple-maps](https://www.react-simple-maps.io/) + [d3-scale](https://d3js.org/d3-scale) | SVG-based US choropleth with a log scale centered on parity

## Project structure

```
db/        SQL schema and seed data (categories, states, metrics, law topics)
pipeline/  Ingest scripts — one per data source, methods include pulling from a public API and upserting into Postgres, load files from CDC database, Bureau of Justice Statistics, and Center for American Women and Politics
api/       FastAPI backend serving the frontend
web/       React + Vite frontend
```
## Data model

Every observation (a state's value for a metric, in a given year) points to a `sources` row describing exactly where it came from — publisher, title, release year, and a URL, scoped to that specific state wherever the source supports it. Nothing is stored pre-computed where it can be derived live instead: a gap between two values, for instance, is computed in a database view at query time, not written to a column that could drift out of sync with its inputs.

Laws work differently from numeric metrics — they're not something a public API hands you in bulk, so each state's current law on a topic (and its citation) has to be researched and entered individually rather than pulled by a pipeline script.

## Metrics tracked

**Economics:** median earnings, labor force participation, poverty rate
**Education:** bachelor's degree rate, college enrollment, STEM degree share
**Health & Safety:** life expectancy, suicide mortality, homicide mortality
**Representation:** state legislative seats, incarceration rate
**Law & Policy: (PLANNED)** parental leave, equal pay protections, reproductive health law

## Roadmap

- [ ] Legal tracker: research and enter each state's law on the 3 law topics, with citations

## License

See [LICENSE](LICENSE).
