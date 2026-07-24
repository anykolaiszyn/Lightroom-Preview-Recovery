from pathlib import Path

from lightroom_preview_recovery.models import (
    CatalogImage,
    RecoveryStatus,
)


def test_catalog_image_retains_virtual_copy_name() -> None:
    image = CatalogImage(
        image_id=42,
        base_name="IMG_0042",
        extension="CR2",
        original_filename="IMG_0042.CR2",
        root_name="Pictures",
        folder_path="2019/Trip",
        copy_name="Warm edit",
    )

    assert image.image_id == 42
    assert image.copy_name == "Warm edit"
    assert RecoveryStatus.RECOVERED.value == "recovered"
