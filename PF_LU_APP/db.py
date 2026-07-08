import psycopg2
from psycopg2.extras import RealDictCursor
from flask import g
from . import connect_local as connect

def get_db():
    """Gets a PostgreSQL database connection to use for the current Flask request."""
    if 'db' not in g:
        g.db = psycopg2.connect(
            user=connect.dbuser,
            password=connect.dbpass,
            host=connect.dbhost,
            port=connect.dbport,
            dbname=connect.dbname,
            sslmode=getattr(connect, "sslmode", "prefer")
        )
    return g.db

from contextlib import contextmanager

def get_cursor():
    """Gets a PostgreSQL cursor that returns rows as dictionaries."""
    conn = get_db()
    return conn.cursor(cursor_factory=RealDictCursor)

@contextmanager
def get_cursor_context():
    """Context manager for safely getting and closing a database cursor."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        yield cur
    finally:
        cur.close()

def close_db(e=None):
    """Closes the connection automatically at the end of each request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_app(app):
    """Registers the teardown function to clean up connections."""
    app.teardown_appcontext(close_db)