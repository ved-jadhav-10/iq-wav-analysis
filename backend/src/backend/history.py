"""The analyses kept in the workspace, so results survive a restart (PLAN §3, §5 M7 "Job store").

One SQLite file holds, for each finished analysis, its results document and run record exactly as
they were produced (the bytes the exports are made from, so a download after a restart equals the
one before it), with a few columns to list them by. It holds no samples and no paths: the document
names the recording's files by SHA-256 only. Deleting an entry deletes everything derived from it
(PLAN §2, "Data handling"): the row is the only copy.

Without a workspace the store is in memory and ends with the process (tests, `create_app(dist)`).
"""

import sqlite3
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

from dsp.results import Results, results_sha256

SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
    id TEXT PRIMARY KEY,
    created_utc TEXT NOT NULL,
    name TEXT NOT NULL,
    container TEXT NOT NULL,
    signals INTEGER NOT NULL,
    verified INTEGER NOT NULL,
    results_sha256 TEXT NOT NULL,
    results_json TEXT NOT NULL,
    run_json TEXT
)
"""


@dataclass(frozen=True)
class Entry:
    id: str
    created_utc: str
    name: str
    container: str
    signals: int
    verified: int  # signals whose headline is VERIFIED
    results_sha256: str


class History:
    """A thread-safe list of finished analyses, in SQLite."""

    def __init__(self, path: Path | None = None) -> None:
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path) if path else ":memory:", check_same_thread=False)
        with self._lock, self._db:
            # Deleted rows are overwritten with zeros, so deleting an entry leaves no copy of it in
            # the file's free pages.
            self._db.execute("PRAGMA secure_delete = ON")
            self._db.execute(SCHEMA)

    def save(self, name: str, results: Results, run_json: str | None, created_utc: str) -> Entry:
        """Keep one finished analysis; `name` is the recording's display name."""
        entry = Entry(
            id=uuid.uuid4().hex,
            created_utc=created_utc,
            name=name,
            container=results.recording.container,
            signals=len(results.signals),
            verified=sum(s.level.value == "VERIFIED" for s in results.signals),
            results_sha256=results_sha256(results),
        )
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO analyses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    entry.id,
                    entry.created_utc,
                    entry.name,
                    entry.container,
                    entry.signals,
                    entry.verified,
                    entry.results_sha256,
                    results.to_json(),
                    run_json,
                ),
            )
        return entry

    def entries(self) -> list[Entry]:
        """Newest first."""
        with self._lock:
            rows = self._db.execute(
                "SELECT id, created_utc, name, container, signals, verified, results_sha256 "
                "FROM analyses ORDER BY created_utc DESC, rowid DESC"
            ).fetchall()
        return [Entry(*row) for row in rows]

    def get(self, entry_id: str) -> tuple[Entry, Results, str | None] | None:
        """The entry, its results document and its run record's JSON, or None."""
        with self._lock:
            row = self._db.execute(
                "SELECT id, created_utc, name, container, signals, verified, results_sha256, "
                "results_json, run_json FROM analyses WHERE id = ?",
                (entry_id,),
            ).fetchone()
        if row is None:
            return None
        return Entry(*row[:7]), Results.model_validate_json(row[7]), row[8]

    def delete(self, entry_id: str) -> bool:
        with self._lock, self._db:
            cursor = self._db.execute("DELETE FROM analyses WHERE id = ?", (entry_id,))
        return cursor.rowcount > 0

    def close(self) -> None:
        with self._lock:
            self._db.close()
