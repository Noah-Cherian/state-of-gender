"""
Database connection pool.

A pool keeps a handful of connections to Neon open and ready, so each
request reuses one instead of paying the cost of opening a brand-new
connection every time (that round trip is slow compared to a query itself).

load_dotenv(find_dotenv()) searches upward from wherever this is run,
so this reads the same .env file at the repo root that the pipeline
script uses -- one DATABASE_URL, shared by both.
"""

import os

from dotenv import find_dotenv, load_dotenv
from psycopg_pool import ConnectionPool

load_dotenv(find_dotenv())

DATABASE_URL = os.environ["DATABASE_URL"]

# min_size=1: always keep at least one connection open
# max_size=5: never open more than 5 at once (Neon's free plan has a limit)
pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=5, open=True)
