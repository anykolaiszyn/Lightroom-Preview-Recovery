from lightroom_preview_recovery.previews import PreviewIndex, preview_record_path
from tests.fixture_builders import build_previews


def test_resolves_uuid_digest_record_path(tmp_path) -> None:
    root = build_previews(tmp_path / "Catalog Previews.lrdata")

    entries = PreviewIndex(root).load_entries()

    assert entries[0].image_id == 7
    assert entries[0].record_path.name == (
        "ABCD1234-0000-0000-0000-000000000000-deadbeef.lrprev"
    )
    assert entries[0].record_path.exists()


def test_preview_record_path_canonicalizes_uuid_for_cache_folders(tmp_path) -> None:
    root = tmp_path / "Catalog Previews.lrdata"

    record_path = preview_record_path(
        root,
        "abcd1234-0000-0000-0000-000000000000",
        "deadbeef",
    )

    assert record_path == (
        root
        / "A"
        / "ABCD"
        / "ABCD1234-0000-0000-0000-000000000000-deadbeef.lrprev"
    )
