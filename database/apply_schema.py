from __future__ import annotations

import sqlite3
from pathlib import Path


DATABASE_PATH = Path(__file__).with_name("water.db")
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def apply_schema(
    database_path: Path = DATABASE_PATH,
    schema_path: Path = SCHEMA_PATH,
) -> None:
    schema = schema_path.read_text(encoding="utf-8")
    conn = sqlite3.connect(database_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(schema)
        integrity = conn.execute("PRAGMA quick_check").fetchone()[0]
        foreign_key_failures = conn.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != "ok" or foreign_key_failures:
            raise ValueError(
                f"Schema validation failed: quick_check={integrity!r}, "
                f"foreign_keys={foreign_key_failures}"
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    apply_schema()
    print(f"Applied {SCHEMA_PATH} to {DATABASE_PATH}")


if __name__ == "__main__":
    main()
