from pathlib import Path

from .models import PreviewEntry
from .sqlite_ro import connect_readonly


def preview_record_path(root: Path, uuid: str, digest: str) -> Path:
    canonical_uuid = uuid.upper()
    return (
        root
        / canonical_uuid[0]
        / canonical_uuid[:4]
        / f"{canonical_uuid}-{digest}.lrprev"
    )


class PreviewIndex:
    def __init__(self, root: Path) -> None:
        self.root = root

    def load_entries(self) -> list[PreviewEntry]:
        with connect_readonly(self.root / "previews.db") as connection:
            rows = connection.execute(
                "SELECT imageId, uuid, digest, orientation "
                "FROM ImageCacheEntry ORDER BY imageId"
            ).fetchall()
        return [
            PreviewEntry(
                image_id=int(image_id),
                uuid=str(uuid),
                digest=str(digest),
                orientation=orientation,
                record_path=preview_record_path(self.root, str(uuid), str(digest)),
            )
            for image_id, uuid, digest, orientation in rows
        ]
