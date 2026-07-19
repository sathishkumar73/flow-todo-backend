"""Run any unapplied SQL migration files from ./migrations/ in filename order."""
import os
import sys
from pathlib import Path

import psycopg


def run() -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("migrate: DATABASE_URL not set — skipping", flush=True)
        return

    migrations_dir = Path(__file__).parent / "migrations"
    files = sorted(migrations_dir.glob("*.sql"))
    if not files:
        print("migrate: no migration files found", flush=True)
        return

    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)

        applied = {row[0] for row in conn.execute("SELECT filename FROM schema_migrations")}

        for path in files:
            name = path.name
            if name in applied:
                print(f"migrate: skip  {name} (already applied)", flush=True)
                continue
            print(f"migrate: apply {name} …", end=" ", flush=True)
            sql = path.read_text()
            conn.execute(sql)
            conn.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (name,))
            print("ok", flush=True)

    print("migrate: done", flush=True)


if __name__ == "__main__":
    run()
