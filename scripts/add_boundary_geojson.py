from PF_LU_APP import create_app

app = create_app()

with app.app_context():
    from PF_LU_APP.db import get_db, get_cursor
    conn = get_db()
    cur = get_cursor()
    try:
        cur.execute("ALTER TABLE groups ADD COLUMN IF NOT EXISTS boundary_geojson TEXT")
        conn.commit()
        print("Migration applied: boundary_geojson column ensured on groups table")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
    finally:
        try:
            cur.close()
        except Exception:
            pass
