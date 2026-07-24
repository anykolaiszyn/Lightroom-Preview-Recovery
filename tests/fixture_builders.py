import sqlite3
from pathlib import Path


def build_catalog(path: Path) -> Path:
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE Adobe_images (
            id_local INTEGER PRIMARY KEY, rootFile INTEGER, copyName TEXT
        );
        CREATE TABLE AgLibraryFile (
            id_local INTEGER PRIMARY KEY, baseName TEXT, extension TEXT,
            originalFilename TEXT, folder INTEGER
        );
        CREATE TABLE AgLibraryFolder (
            id_local INTEGER PRIMARY KEY, pathFromRoot TEXT, rootFolder INTEGER
        );
        CREATE TABLE AgLibraryRootFolder (
            id_local INTEGER PRIMARY KEY, name TEXT
        );
        INSERT INTO AgLibraryRootFolder VALUES (1, 'Pictures');
        INSERT INTO AgLibraryFolder VALUES (2, '2020/Trip', 1);
        INSERT INTO AgLibraryFile VALUES
            (3, 'IMG_0007', 'CR2', 'IMG_0007.CR2', 2);
        INSERT INTO Adobe_images VALUES (7, 3, 'Monochrome');
        """
    )
    con.commit()
    con.close()
    return path


def build_previews(root: Path, record_data: bytes = b"record") -> Path:
    root.mkdir(parents=True)
    uuid = "ABCD1234-0000-0000-0000-000000000000"
    digest = "deadbeef"
    con = sqlite3.connect(root / "previews.db")
    con.execute(
        "CREATE TABLE ImageCacheEntry "
        "(imageId INTEGER, uuid TEXT, digest TEXT, orientation INTEGER)"
    )
    con.execute(
        "INSERT INTO ImageCacheEntry VALUES (?, ?, ?, ?)",
        (7, uuid, digest, 1),
    )
    con.commit()
    con.close()
    record_dir = root / "A" / "ABCD"
    record_dir.mkdir(parents=True)
    (record_dir / f"{uuid}-{digest}.lrprev").write_bytes(record_data)
    return root
