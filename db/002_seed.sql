-- State of Gender: reference data
-- Run after 001_schema.sql. Fills the four hand-written reference tables.
-- sources, observations and laws stay empty; the data pipeline fills those.

BEGIN;

-- ---------------------------------------------------------------------------
-- categories
-- ---------------------------------------------------------------------------
INSERT INTO categories (slug, name, sort_order) VALUES
    ('law_policy',     'Law & Policy',                     1),
    ('economics',      'Economics',                        2),
    ('education',      'Education',                        3),
    ('health_safety',  'Health & Safety',                  4),
    ('representation', 'Representation & Social Outcomes', 5);

-- ---------------------------------------------------------------------------
-- states: 50 states, DC, and the nation
-- ---------------------------------------------------------------------------
INSERT INTO states (code, fips, name, kind) VALUES
    ('AL', '01', 'Alabama',              'state'),
    ('AK', '02', 'Alaska',               'state'),
    ('AZ', '04', 'Arizona',              'state'),
    ('AR', '05', 'Arkansas',             'state'),
    ('CA', '06', 'California',           'state'),
    ('CO', '08', 'Colorado',             'state'),
    ('CT', '09', 'Connecticut',          'state'),
    ('DE', '10', 'Delaware',             'state'),
    ('DC', '11', 'District of Columbia', 'district'),
    ('FL', '12', 'Florida',              'state'),
    ('GA', '13', 'Georgia',              'state'),
    ('HI', '15', 'Hawaii',               'state'),
    ('ID', '16', 'Idaho',                'state'),
    ('IL', '17', 'Illinois',             'state'),
    ('IN', '18', 'Indiana',              'state'),
    ('IA', '19', 'Iowa',                 'state'),
    ('KS', '20', 'Kansas',               'state'),
    ('KY', '21', 'Kentucky',             'state'),
    ('LA', '22', 'Louisiana',            'state'),
    ('ME', '23', 'Maine',                'state'),
    ('MD', '24', 'Maryland',             'state'),
    ('MA', '25', 'Massachusetts',        'state'),
    ('MI', '26', 'Michigan',             'state'),
    ('MN', '27', 'Minnesota',            'state'),
    ('MS', '28', 'Mississippi',          'state'),
    ('MO', '29', 'Missouri',             'state'),
    ('MT', '30', 'Montana',              'state'),
    ('NE', '31', 'Nebraska',             'state'),
    ('NV', '32', 'Nevada',               'state'),
    ('NH', '33', 'New Hampshire',        'state'),
    ('NJ', '34', 'New Jersey',           'state'),
    ('NM', '35', 'New Mexico',           'state'),
    ('NY', '36', 'New York',             'state'),
    ('NC', '37', 'North Carolina',       'state'),
    ('ND', '38', 'North Dakota',         'state'),
    ('OH', '39', 'Ohio',                 'state'),
    ('OK', '40', 'Oklahoma',             'state'),
    ('OR', '41', 'Oregon',               'state'),
    ('PA', '42', 'Pennsylvania',         'state'),
    ('RI', '44', 'Rhode Island',         'state'),
    ('SC', '45', 'South Carolina',       'state'),
    ('SD', '46', 'South Dakota',         'state'),
    ('TN', '47', 'Tennessee',            'state'),
    ('TX', '48', 'Texas',                'state'),
    ('UT', '49', 'Utah',                 'state'),
    ('VT', '50', 'Vermont',              'state'),
    ('VA', '51', 'Virginia',             'state'),
    ('WA', '53', 'Washington',           'state'),
    ('WV', '54', 'West Virginia',        'state'),
    ('WI', '55', 'Wisconsin',            'state'),
    ('WY', '56', 'Wyoming',              'state'),
    ('US', '00', 'United States',        'nation');

-- ---------------------------------------------------------------------------
-- metrics: the 12 numeric measures from Step 1
-- Definitions are working drafts; each is finalized when the pipeline step
-- picks the exact source table.
-- ---------------------------------------------------------------------------
INSERT INTO metrics (slug, category_slug, name, definition, unit, sort_order) VALUES
    ('median_earnings', 'economics', 'Median earnings',
     'Median annual earnings of full-time, year-round workers age 16 and over.',
     'usd', 1),
    ('labor_force_participation', 'economics', 'Labor force participation',
     'Share of people age 16 and over who are working or actively looking for work.',
     'percent', 2),
    ('poverty_rate', 'economics', 'Poverty rate',
     'Share of people whose family income in the past 12 months was below the federal poverty threshold.',
     'percent', 3),

    ('bachelors_degree_rate', 'education', 'Bachelor''s degree rate',
     'Share of adults age 25 and over who hold a bachelor''s degree or higher.',
     'percent', 1),
    ('college_enrollment', 'education', 'College enrollment',
     'Share of people age 18 to 24 enrolled in college or graduate school.',
     'percent', 2),
    ('stem_degree_share', 'education', 'STEM degrees',
     'Share of bachelor''s degree holders age 25 and over whose first major was in a science or engineering field.',
     'percent', 3),

    ('life_expectancy', 'health_safety', 'Life expectancy',
     'Life expectancy at birth.',
     'years', 1),
    ('suicide_mortality', 'health_safety', 'Suicide mortality',
     'Age-adjusted deaths by suicide per 100,000 residents of the same sex.',
     'per_100k', 2),
    ('homicide_mortality', 'health_safety', 'Homicide mortality',
     'Age-adjusted deaths by homicide per 100,000 residents of the same sex.',
     'per_100k', 3),

    ('state_legislative_seats', 'representation', 'State legislative seats',
     'Share of seats in the state legislature (both chambers combined).',
     'percent', 1),
    ('statewide_elected_officials', 'representation', 'Statewide elected officials',
     'Number of statewide elected executive offices held, such as governor and attorney general.',
     'count', 2),
    ('incarceration_rate', 'representation', 'Incarceration rate',
     'Sentenced prisoners under state or federal jurisdiction per 100,000 residents of the same sex.',
     'per_100k', 3);

-- ---------------------------------------------------------------------------
-- law_topics: the 3 legal topics from Step 1
-- ---------------------------------------------------------------------------
INSERT INTO law_topics (slug, category_slug, name, question, sort_order) VALUES
    ('parental_leave', 'law_policy', 'Parental leave',
     'Does state law guarantee workers paid or job-protected leave for a new child, beyond federal law?',
     1),
    ('equal_pay', 'law_policy', 'Equal pay protections',
     'What does state law require of employers on equal pay and pay transparency, beyond federal law?',
     2),
    ('reproductive_health', 'law_policy', 'Reproductive health law',
     'What does current state law provide on abortion and contraception access?',
     3);

COMMIT;
