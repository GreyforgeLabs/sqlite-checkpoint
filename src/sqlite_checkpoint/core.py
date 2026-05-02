"""Core checkpoint and backup logic for SQLite databases."""

from __future__ import annotations

import contextlib
import hashlib
import os
import sqlite3
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class CheckpointMode(Enum):
    """SQLite WAL checkpoint modes."""

    PASSIVE = "PASSIVE"
    FULL = "FULL"
    RESTART = "RESTART"
    TRUNCATE = "TRUNCATE"


@dataclass(frozen=True)
class CheckpointResult:
    """Result of a WAL checkpoint operation."""

    mode: CheckpointMode
    busy: bool
    wal_pages: int
    checkpointed_pages: int
    database: str
    elapsed_ms: float

    @property
    def fully_checkpointed(self) -> bool:
        return not self.busy and self.wal_pages == self.checkpointed_pages


@dataclass(frozen=True)
class BackupResult:
    """Result of an atomic backup operation."""

    source: str
    destination: str
    size_bytes: int
    sha256: str
    elapsed_ms: float


@dataclass(frozen=True)
class SnapshotResult:
    """Result of a checkpoint-then-backup snapshot."""

    checkpoint: CheckpointResult
    backup: BackupResult


def checkpoint(
    db_path: str | Path,
    mode: CheckpointMode = CheckpointMode.PASSIVE,
) -> CheckpointResult:
    """Run a WAL checkpoint on the given SQLite database.

    Args:
        db_path: Path to the SQLite database file.
        mode: Checkpoint mode (PASSIVE, FULL, RESTART, TRUNCATE).

    Returns:
        CheckpointResult with page counts and timing.

    Raises:
        FileNotFoundError: If the database file does not exist.
        sqlite3.OperationalError: If the checkpoint fails.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    t0 = time.monotonic()
    conn = sqlite3.connect(str(db_path))
    try:
        # PRAGMA wal_checkpoint returns (result, wal_pages, checkpointed_pages).
        # result: 0 = success, 1 = blocked by concurrent reader (PASSIVE only).
        busy, wal_pages, checkpointed = conn.execute(
            f"PRAGMA wal_checkpoint({mode.value})"
        ).fetchone()
    finally:
        conn.close()
    elapsed = (time.monotonic() - t0) * 1000

    return CheckpointResult(
        mode=mode,
        busy=bool(busy),
        wal_pages=max(wal_pages, 0),
        checkpointed_pages=max(checkpointed, 0),
        database=str(db_path),
        elapsed_ms=round(elapsed, 2),
    )


def backup(
    db_path: str | Path,
    dest_path: str | Path,
    *,
    pages_per_step: int = -1,
    pause_ms: float = 0,
) -> BackupResult:
    """Create an atomic backup of a SQLite database using the online backup API.

    This is safe to run while the database is being written to. The backup
    will reflect a consistent snapshot even under concurrent writes.

    Args:
        db_path: Path to the source database.
        dest_path: Path for the backup file. Parent directory must exist.
        pages_per_step: Pages to copy per step (-1 = all at once).
        pause_ms: Milliseconds to sleep between steps (for throttling).

    Returns:
        BackupResult with size, checksum, and timing.

    Raises:
        FileNotFoundError: If the source database does not exist.
        FileExistsError: If the destination already exists.
    """
    db_path = Path(db_path)
    dest_path = Path(dest_path)

    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    if dest_path.exists():
        raise FileExistsError(f"Destination already exists: {dest_path}")

    tmp_path = dest_path.with_name(f".{dest_path.name}.tmp-{os.getpid()}-{time.time_ns()}")
    t0 = time.monotonic()
    source = sqlite3.connect(str(db_path))
    dest = sqlite3.connect(str(tmp_path))
    try:
        source.backup(dest, pages=pages_per_step, sleep=pause_ms / 1000)
        dest.close()
        source.close()
        _quick_check(tmp_path)
        # Atomic no-clobber publish: link succeeds only if dest_path does not exist.
        os.link(tmp_path, dest_path)
    except Exception:
        with contextlib.suppress(OSError):
            tmp_path.unlink()
        with contextlib.suppress(Exception):
            dest.close()
        with contextlib.suppress(Exception):
            source.close()
        raise
    finally:
        with contextlib.suppress(Exception):
            dest.close()
        with contextlib.suppress(Exception):
            source.close()
        with contextlib.suppress(OSError):
            tmp_path.unlink()

    elapsed = (time.monotonic() - t0) * 1000
    size = dest_path.stat().st_size
    sha = _sha256(dest_path)

    return BackupResult(
        source=str(db_path),
        destination=str(dest_path),
        size_bytes=size,
        sha256=sha,
        elapsed_ms=round(elapsed, 2),
    )


def snapshot(
    db_path: str | Path,
    dest_path: str | Path,
    *,
    checkpoint_mode: CheckpointMode = CheckpointMode.PASSIVE,
    pages_per_step: int = -1,
) -> SnapshotResult:
    """Checkpoint the WAL, then create an atomic backup.

    This is the recommended way to create a point-in-time backup: first flush
    the WAL into the main database file, then use the online backup API to
    copy the database atomically.

    Args:
        db_path: Path to the source database.
        dest_path: Path for the backup file.
        checkpoint_mode: WAL checkpoint mode to use before backup.
        pages_per_step: Pages per backup step (-1 = all at once).

    Returns:
        SnapshotResult containing both checkpoint and backup results.
    """
    cp = checkpoint(db_path, mode=checkpoint_mode)
    bk = backup(db_path, dest_path, pages_per_step=pages_per_step)
    return SnapshotResult(checkpoint=cp, backup=bk)


def db_info(db_path: str | Path) -> dict:
    """Return basic info about a SQLite database.

    Returns:
        Dict with keys: path, size_bytes, journal_mode, wal_file_exists,
        wal_size_bytes, page_size, page_count, freelist_count.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    wal_path = db_path.with_suffix(db_path.suffix + "-wal")

    conn = sqlite3.connect(str(db_path))
    try:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        page_size = conn.execute("PRAGMA page_size").fetchone()[0]
        page_count = conn.execute("PRAGMA page_count").fetchone()[0]
        freelist = conn.execute("PRAGMA freelist_count").fetchone()[0]
    finally:
        conn.close()

    return {
        "path": str(db_path),
        "size_bytes": db_path.stat().st_size,
        "journal_mode": journal_mode,
        "wal_file_exists": wal_path.exists(),
        "wal_size_bytes": wal_path.stat().st_size if wal_path.exists() else 0,
        "page_size": page_size,
        "page_count": page_count,
        "freelist_count": freelist,
    }


def _sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _quick_check(path: Path) -> None:
    """Validate a SQLite file before publishing it."""
    conn = sqlite3.connect(str(path))
    try:
        result = conn.execute("PRAGMA quick_check").fetchone()
    finally:
        conn.close()
    if not result or result[0] != "ok":
        raise sqlite3.DatabaseError(f"SQLite quick_check failed for temporary backup: {result!r}")
