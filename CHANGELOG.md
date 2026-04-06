# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-04-06

### Added

- WAL checkpoint with all four modes (PASSIVE, FULL, RESTART, TRUNCATE)
- Atomic backup via SQLite online backup API, safe under concurrent writes
- Snapshot command combining checkpoint + backup in one operation
- Database info command (journal mode, WAL state, page counts, freelist)
- JSON output mode for scripting and pipelines
- CLI with subcommands: checkpoint, backup, snapshot, info
- Python API: `checkpoint()`, `backup()`, `snapshot()`, `db_info()`
- Zero runtime dependencies (stdlib `sqlite3` only)
