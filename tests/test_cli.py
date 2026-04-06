"""Tests for the CLI module."""

from sqlite_checkpoint.cli import build_parser


def test_parser_accepts_database_arg():
    parser = build_parser()
    args = parser.parse_args(["test.db"])
    assert args.database == "test.db"
