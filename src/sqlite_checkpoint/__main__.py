"""Allow running as `python -m sqlite_checkpoint`."""

from sqlite_checkpoint.cli import main

raise SystemExit(main())
