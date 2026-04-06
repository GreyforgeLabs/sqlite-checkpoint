"""Tests for the CLI module."""

import json

from sqlite_checkpoint.cli import main


class TestCLI:
    def test_checkpoint_command(self, wal_db, capsys):
        rc = main(["checkpoint", str(wal_db)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "checkpoint PASSIVE" in out

    def test_backup_command(self, wal_db, tmp_path, capsys):
        dest = tmp_path / "cli_backup.db"
        rc = main(["backup", str(wal_db), str(dest)])
        assert rc == 0
        assert dest.exists()
        out = capsys.readouterr().out
        assert "sha256" in out

    def test_snapshot_command(self, wal_db, tmp_path, capsys):
        dest = tmp_path / "cli_snap.db"
        rc = main(["snapshot", str(wal_db), str(dest)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "snapshot complete" in out

    def test_info_command(self, wal_db, capsys):
        rc = main(["info", str(wal_db)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "wal" in out

    def test_json_output(self, wal_db, capsys):
        rc = main(["--json", "info", str(wal_db)])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["command"] == "info"
        assert data["journal_mode"] == "wal"

    def test_missing_database_returns_error(self, tmp_path, capsys):
        rc = main(["info", str(tmp_path / "nope.db")])
        assert rc == 1

    def test_alias_cp(self, wal_db, capsys):
        rc = main(["cp", str(wal_db)])
        assert rc == 0
