"""Command-line interface for sqlite-checkpoint."""

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sqlite-checkpoint",
        description="Lightweight SQLite WAL checkpoint manager.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {_get_version()}")
    parser.add_argument("database", help="Path to the SQLite database file")
    return parser


def _get_version() -> str:
    from sqlite_checkpoint import __version__

    return __version__


def main() -> None:
    parser = build_parser()
    _args = parser.parse_args()


if __name__ == "__main__":
    main()
