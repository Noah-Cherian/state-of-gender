# State of Gender


## What is it

A map of measurable gender differences across every US state — legal, economic, educational, health, and social. Every number on the map links back to the source where it came from (metadata like the publisher, the year, the precise definition, and (for laws) the statute itself).

**Live site:** (https://stateofgender.vercel.app/)

<img width="828" height="715" alt="image" src="https://github.com/user-attachments/assets/e3a20992-ac9c-40d7-a86d-e34c8162cccf" />

## Why this exists

Gender gap debates and discussions have been widespread on the internet for a long time. However, most participants in arguments rely heavily on anecdotal evidence as compared to data. So, my goal was to compile and present data into a intuitive, unbiased map. It is a neutral, side-by-side comparison where colors show direction and size of gap for any given metric. My hope is to continue to organize and extract data into this project so more people have relatively easy access to the numbers for an issue that strains our society to this day.

## Status

This is a work in progress, but here's where it's at right now:

- **Live site:** the frontend is hosted on Vercel and the API on Render, with the database on Neon
- **Database:** Postgres, hosted on [Neon](https://neon.tech). It has tables for categories, states, metrics, sources, observations, law topics and laws
- **Data:** eleven metrics are loaded, by sex, for all 50 states (plus DC and the US where the source has them). They come from five sources, each loaded by its own script:
  - U.S. Census Bureau (American Community Survey): earnings, labor force participation, poverty, bachelor's degrees, college enrollment, STEM degrees
  - CDC / National Center for Health Statistics: life expectancy
  - CDC WONDER: suicide and homicide mortality
  - Bureau of Justice Statistics: incarceration rate
  - Rutgers Center for American Women and Politics (CAWP): state legislative seats
- **API:** a FastAPI backend that serves the states, the metrics, each metric's values for the map, and each state's full profile.
- **Frontend:** React app with a switchable map/table view and a panel showing a clicked state's values next to the national figure

See [Roadmap](#roadmap) for what's next.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Database | PostgreSQL via [Neon](https://neon.tech) | Free hosted Postgres |
| Backend | [FastAPI](https://fastapi.tiangolo.com/) (Python) | Iterates fast for handful of read-only JSON endpoints. |
| Data pipeline | Python scripts, `psycopg` | Scripts that pull from public APIs and upsert into Postgres |
| Frontend | React + [Vite](https://vitejs.dev/) | Fast dev loop; component model fits a map + detail-panel UI well. |
| Map rendering | [react-simple-maps](https://www.react-simple-maps.io/) + [d3-scale](https://d3js.org/d3-scale) | Colors by how many times higher one sex's value is than the other's, on a log scale centered on parity |
| Hosting | [Vercel](https://vercel.com) (frontend), [Render](https://render.com) (API) | Automate git pushes |


## Project structure


```
db/          Db schema and seed data 
pipeline/    One script per data source; loads that source's figures into the database
  data/      Files for sources without a usable API (CDC WONDER exports, BJS and CAWP tables)
api/         FastAPI backend that serves data to the website
web/         React + Vite frontend
```
## Data model

Every data point has a `sources` row describing exactly where it came from scoped to that specific state wherever the source supports it. Nothing is stored pre-computed where it can be derived live instead: a gap between two values, for instance, is computed in a database view at query time, not written to a column that could drift out of sync with its inputs.

Laws work differently from numeric metrics. They must be researched and entered individually rather than pulled by a pipeline script.

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
