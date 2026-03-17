import psycopg

from app.core.config import PG_DSN


def get_conn():
    return psycopg.connect(PG_DSN)
