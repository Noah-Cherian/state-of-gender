-- State of Gender: database schema, version 1
-- Standard PostgreSQL (15 or newer). Runs unchanged on Neon, Supabase or a local install.
--
-- Naming rule used throughout:
--   * Small, hand-written reference tables use a readable text key ('GA', 'median_earnings').
--   * Tables the data pipeline fills use a numeric id.
--
-- Everything runs inside one transaction: if any statement fails, nothing is created.

BEGIN;

-- ---------------------------------------------------------------------------
-- categories: the five groupings shown as cards on a state page
-- ---------------------------------------------------------------------------
CREATE TABLE categories (
    slug        text      PRIMARY KEY,           -- 'economics'
    name        text      NOT NULL UNIQUE,       -- 'Economics'
    sort_order  smallint  NOT NULL UNIQUE        -- display order on the page
);

-- ---------------------------------------------------------------------------
-- states: 50 states, DC, and one 'US' row for national figures
-- ---------------------------------------------------------------------------
CREATE TABLE states (
    code  char(2)  PRIMARY KEY,                  -- postal code: 'GA', 'DC', 'US'
    fips  char(2)  NOT NULL UNIQUE,              -- Census code: '13'; joins to Census data and the map file
    name  text     NOT NULL UNIQUE,              -- 'Georgia'
    kind  text     NOT NULL
          CHECK (kind IN ('state', 'district', 'nation'))
);

-- ---------------------------------------------------------------------------
-- metrics: one row per thing we measure (the methodology lives here)
-- ---------------------------------------------------------------------------
CREATE TABLE metrics (
    slug           text      PRIMARY KEY,        -- 'median_earnings'
    category_slug  text      NOT NULL REFERENCES categories (slug),
    name           text      NOT NULL UNIQUE,    -- 'Median earnings'
    definition     text      NOT NULL,           -- exactly what is counted, and for whom
    unit           text      NOT NULL
                   CHECK (unit IN ('usd', 'percent', 'years', 'per_100k', 'count')),
    sort_order     smallint  NOT NULL
);

-- ---------------------------------------------------------------------------
-- sources: one row per specific, checkable release (not just "Census")
-- ---------------------------------------------------------------------------
CREATE TABLE sources (
    id            integer  GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    slug          text     NOT NULL UNIQUE,      -- 'acs1-2024-b20017'; the pipeline upserts on this
    kind          text     NOT NULL
                  CHECK (kind IN ('dataset', 'statute', 'report')),
    publisher     text     NOT NULL,             -- 'U.S. Census Bureau'
    title         text     NOT NULL,             -- 'American Community Survey 1-Year Estimates'
    release       text,                          -- '2024'
    table_ref     text,                          -- 'B20017'
    url           text     NOT NULL,
    retrieved_on  date     NOT NULL,             -- the day we pulled it
    notes         text
);

-- ---------------------------------------------------------------------------
-- observations: one measured value pair (women, men) for a state, metric, year
-- ---------------------------------------------------------------------------
CREATE TABLE observations (
    id            bigint    GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    state_code    char(2)   NOT NULL REFERENCES states (code),
    metric_slug   text      NOT NULL REFERENCES metrics (slug),
    year          smallint  NOT NULL             -- for multi-year data, the last year of the period
                  CHECK (year BETWEEN 1900 AND 2100),
    female_value  numeric,
    male_value    numeric,
    female_moe    numeric   CHECK (female_moe >= 0),   -- margin of error, where the source gives one
    male_moe      numeric   CHECK (male_moe >= 0),
    suppressed    boolean   NOT NULL DEFAULT false,    -- true when the source withheld a value
    source_id     integer   NOT NULL REFERENCES sources (id),
    note          text,

    -- one row per state, metric and year
    CONSTRAINT observations_one_per_state_metric_year
        UNIQUE (state_code, metric_slug, year),

    -- a missing value is only allowed when the row says it was suppressed
    CONSTRAINT observations_missing_must_be_flagged
        CHECK (suppressed OR (female_value IS NOT NULL AND male_value IS NOT NULL))
);

-- The map asks "every state for one metric in one year"; this index answers that fast.
-- (The UNIQUE constraint above already covers "everything for one state".)
CREATE INDEX observations_metric_year_idx ON observations (metric_slug, year);

-- ---------------------------------------------------------------------------
-- law_topics: the questions the legal tracker answers
-- ---------------------------------------------------------------------------
CREATE TABLE law_topics (
    slug           text      PRIMARY KEY,        -- 'parental_leave'
    category_slug  text      NOT NULL REFERENCES categories (slug),
    name           text      NOT NULL UNIQUE,    -- 'Parental leave'
    question       text      NOT NULL,           -- what each state's entry answers
    sort_order     smallint  NOT NULL
);

-- ---------------------------------------------------------------------------
-- laws: one state's position on one topic
-- ---------------------------------------------------------------------------
CREATE TABLE laws (
    id              bigint   GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    state_code      char(2)  NOT NULL REFERENCES states (code),
    topic_slug      text     NOT NULL REFERENCES law_topics (slug),
    status          text     NOT NULL
                    CHECK (status IN (
                        'none',        -- the state has no law on this topic
                        'enacted',     -- passed, not yet in effect
                        'in_effect',
                        'blocked'      -- on the books but halted by a court
                    )),
    headline        text     NOT NULL,           -- one line for the card
    summary         text,                        -- a few neutral sentences
    citation        text,                        -- 'O.C.G.A. § 34-5-3'
    effective_date  date,
    last_verified   date     NOT NULL,           -- the day a person last checked this
    source_id       integer  NOT NULL REFERENCES sources (id),   -- even "no law" needs a source
    is_current      boolean  NOT NULL DEFAULT true,              -- false = kept for history

    -- an actual law must carry its citation
    CONSTRAINT laws_citation_required
        CHECK (status = 'none' OR citation IS NOT NULL)
);

-- Only one current entry per state and topic; older entries stay as history.
CREATE UNIQUE INDEX laws_one_current_per_state_topic
    ON laws (state_code, topic_slug)
    WHERE is_current;

-- ---------------------------------------------------------------------------
-- observation_gaps: the gap is calculated here, never stored
-- ---------------------------------------------------------------------------
CREATE VIEW observation_gaps AS
SELECT
    o.id,
    o.state_code,
    o.metric_slug,
    o.year,
    o.female_value,
    o.male_value,
    o.female_value - o.male_value                             AS difference,          -- women minus men
    round(o.female_value / NULLIF(o.male_value, 0), 4)        AS female_to_male_ratio,
    o.suppressed,
    o.source_id
FROM observations AS o;

COMMIT;
