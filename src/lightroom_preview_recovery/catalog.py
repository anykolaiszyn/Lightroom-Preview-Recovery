from pathlib import Path

from .models import CatalogImage
from .sqlite_ro import connect_readonly


CATALOG_QUERY = """
SELECT
    image.id_local,
    file.baseName,
    file.extension,
    file.originalFilename,
    root.name,
    folder.pathFromRoot,
    image.copyName
FROM Adobe_images AS image
LEFT JOIN AgLibraryFile AS file ON file.id_local = image.rootFile
LEFT JOIN AgLibraryFolder AS folder ON folder.id_local = file.folder
LEFT JOIN AgLibraryRootFolder AS root ON root.id_local = folder.rootFolder
ORDER BY image.id_local
"""


class CatalogReader:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load_images(self) -> dict[int, CatalogImage]:
        with connect_readonly(self.path) as connection:
            rows = connection.execute(CATALOG_QUERY).fetchall()
        return {
            int(row[0]): CatalogImage(
                image_id=int(row[0]),
                base_name=row[1],
                extension=row[2],
                original_filename=row[3],
                root_name=row[4],
                folder_path=row[5],
                copy_name=row[6],
            )
            for row in rows
        }
