"""Tests for the core checkpoint module."""

import sqlite3

import pytest

from sqlite_checkpoint.core import (
    BackupResult,
    CheckpointMode,
    CheckpointResult,
    SnapshotResult,
    backup,
    checkpoint,
    db_info,
    snapshot,
)


class TestCheckpoint:
    def test_passive_checkpoint(self, wal_db):
        result = checkpoint(wal_db)
        assert isinstance(result, CheckpointResult)
        assert result.mode == CheckpointMode.PASSIVE
        assert result.busy is False
        assert result.elapsed_ms >= 0

    def test_truncate_checkpoint(self, wal_db):
        result = checkpoint(wal_db, mode=CheckpointMode.TRUNCATE)
        assert result.fully_checkpointed
        # After TRUNCATE the WAL file should be empty or removed.
        wal_file = wal_db.with_suffix(".db-wal")
        assert not wal_file.exists() or wal_file.stat().st_size == 0

    def test_missing_database(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            checkpoint(tmp_path / "nope.db")


class TestBackup:
    def test_basic_backup(self, wal_db, tmp_path):
        dest = tmp_path / "backup.db"
        result = backup(wal_db, dest)
        assert isinstance(result, BackupResult)
        assert dest.exists()
        assert result.size_bytes > 0
        assert len(result.sha256) == 64

    def test_backup_is_valid_database(self, wal_db, tmp_path):
        dest = tmp_path / "backup.db"
        backup(wal_db, dest)
        conn = sqlite3.connect(str(dest))
        rows = conn.execute("SELECT name FROM items ORDER BY id").fetchall()
        conn.close()
        assert rows == [("alpha",), ("bravo",)]

    def test_backup_refuses_overwrite(self, wal_db, tmp_path):
        dest = tmp_path / "backup.db"
        dest.write_bytes(b"existing")
        with pytest.raises(FileExistsError):
            backup(wal_db, dest)

    def test_backup_leaves_no_temp_file(self, wal_db, tmp_path):
        dest = tmp_path / "backup.db"
        backup(wal_db, dest)
        assert dest.exists()
        assert not list(tmp_path.glob(".backup.db.tmp-*"))

    def test_missing_source(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            backup(tmp_path / "nope.db", tmp_path / "out.db")


class TestSnapshot:
    def test_snapshot_creates_valid_backup(self, wal_db, tmp_path):
        dest = tmp_path / "snap.db"
        result = snapshot(wal_db, dest)
        assert isinstance(result, SnapshotResult)
        assert dest.exists()
        # Verify data integrity.
        conn = sqlite3.connect(str(dest))
        rows = conn.execute("SELECT count(*) FROM items").fetchone()
        conn.close()
        assert rows[0] == 2


class TestDbInfo:
    def test_info_returns_expected_keys(self, wal_db):
        info = db_info(wal_db)
        assert info["journal_mode"] == "wal"
        assert info["page_count"] >= 1
        assert info["size_bytes"] > 0

    def test_missing_database(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            db_info(tmp_path / "nope.db")
