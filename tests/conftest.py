from __future__ import annotations

import os


def pytest_addoption(parser) -> None:
    """Register opt-in paths for the user's real Lightroom backup.

    Neither option has a repository-specific default, so the live test remains
    skipped in ordinary test runs.  Environment variables are convenient for
    local automation without placing personal paths in source control.
    """

    parser.addoption(
        "--live-catalog",
        action="store",
        default=os.environ.get("LRPR_LIVE_CATALOG"),
        help="read-only path to a Lightroom .lrcat file",
    )
    parser.addoption(
        "--live-previews",
        action="store",
        default=os.environ.get("LRPR_LIVE_PREVIEWS"),
        help="read-only path to a Lightroom Catalog Previews.lrdata folder",
    )
