"""Consistent SQLite backup before production migrations; never packaged in Git."""
from datetime import datetime, timezone
from pathlib import Path
import sqlite3


def main():
    base = Path(__file__).resolve().parents[1]
    source = base / "db.sqlite3"
    if not source.is_file():
        raise SystemExit("Production database is missing; deployment stopped.")
    directory = base / "tmp" / "deployment-backups"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / ("db-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f") + ".sqlite3")
    with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as incoming:
        with sqlite3.connect(target) as outgoing:
            incoming.backup(outgoing)
    target.chmod(0o600)
    print("Database backup completed.")


if __name__ == "__main__":
    main()
