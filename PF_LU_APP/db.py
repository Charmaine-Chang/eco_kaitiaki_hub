import pymysql
from flask import g
from . import connect_local as connect

# Export DBAPI-compatible error types so controllers don't import driver-specific modules
DatabaseError = pymysql.err.DatabaseError
IntegrityError = pymysql.err.IntegrityError


def get_db():
    """Gets a MySQL database connection to use for the current Flask request."""
    if 'db' not in g:
        g.db = pymysql.connect(
            user=connect.dbuser,
            password=connect.dbpass,
            host=connect.dbhost,
            port=int(connect.dbport),
            db=connect.dbname,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )
    return g.db


from contextlib import contextmanager


def get_cursor():
    """Gets a MySQL cursor that returns rows as dictionaries."""
    conn = get_db()
    return conn.cursor()


@contextmanager
def get_cursor_context():
    """Context manager for safely getting and closing a database cursor."""
    conn = get_db()
    cur = conn.cursor()
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
