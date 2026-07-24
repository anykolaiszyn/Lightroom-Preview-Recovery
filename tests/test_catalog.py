import sqlite3

import pytest

from lightroom_preview_recovery.catalog import CatalogReader
from lightroom_preview_recovery.sqlite_ro import connect_readonly
from tests.fixture_builders import build_catalog


def test_loads_file_folder_root_and_copy_name(tmp_path) -> None:
    catalog = build_catalog(tmp_path / "sample.lrcat")

    images = CatalogReader(catalog).load_images()

    assert images[7].base_name == "IMG_0007"
    assert images[7].extension == "CR2"
    assert images[7].root_name == "Pictures"
    assert images[7].folder_path == "2020/Trip"
    assert images[7].copy_name == "Monochrome"


def test_readonly_connection_enables_query_only_and_closes(tmp_path) -> None:
    catalog = build_catalog(tmp_path / "sample.lrcat")

    with connect_readonly(catalog) as connection:
        assert connection.execute("PRAGMA query_only").fetchone() == (1,)
        with pytest.raises(sqlite3.OperationalError, match="readonly|query only"):
            connection.execute("CREATE TABLE blocked (id INTEGER)")

    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        connection.execute("SELECT 1")


def test_readonly_connection_does_not_create_missing_database(tmp_path) -> None:
    missing_catalog = tmp_path / "missing.lrcat"

    with pytest.raises(sqlite3.OperationalError, match="unable to open database file"):
        with connect_readonly(missing_catalog):
            pass

    assert not missing_catalog.exists()
