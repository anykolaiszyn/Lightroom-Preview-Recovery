import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def connect_readonly(path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(
        path.resolve().as_uri() + "?mode=ro",
        uri=True,
    )
    try:
        connection.execute("PRAGMA query_only=ON")
        yield connection
    finally:
        connection.close()
