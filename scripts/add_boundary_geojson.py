from PF_LU_APP import create_app

app = create_app()

with app.app_context():
    from PF_LU_APP.db import get_db, get_cursor
    conn = get_db()
    cur = get_cursor()
    try:
        # MySQL doesn't support ADD COLUMN IF NOT EXISTS, so check first
        cur.execute("SHOW COLUMNS FROM groups LIKE 'boundary_geojson'")
        if cur.fetchone():
            print("Migration skipped: boundary_geojson column already exists on groups table")
        else:
            cur.execute("ALTER TABLE groups ADD COLUMN boundary_geojson TEXT")
            conn.commit()
            print("Migration applied: boundary_geojson column added to groups table")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
    finally:
        try:
            cur.close()
        except Exception:
            pass
