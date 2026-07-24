from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath

from .models import CatalogImage, PreviewEntry


INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
    "COM\u00b9", "COM\u00b2", "COM\u00b3",
    "LPT\u00b9", "LPT\u00b2", "LPT\u00b3",
}


def windows_path_key(path: Path) -> str:
    """Return a normalized, case-insensitive key for Windows path reservations."""
    return str(path.resolve()).replace("/", "\\").casefold()


def _windows_units(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def _truncate_utf16(value: str, max_units: int) -> str:
    """Truncate without splitting a Unicode character in Windows path units."""
    result: list[str] = []
    used = 0
    for character in value:
        size = _windows_units(character)
        if used + size > max_units:
            break
        result.append(character)
        used += size
    return "".join(result)


def sanitize_component(value: str, max_length: int = 100) -> str:
    """Return a single Windows-safe file-system component."""
    cleaned = INVALID.sub("_", value).rstrip(" .") or "_"
    if cleaned.partition(".")[0].upper() in RESERVED:
        cleaned = "_" + cleaned
    if len(cleaned) > max_length:
        digest = hashlib.sha1(cleaned.encode("utf-8")).hexdigest()[:8]
        cleaned = f"{cleaned[:max_length - 9]}-{digest}"
    return cleaned


def _filename(image: CatalogImage) -> str:
    if image.base_name:
        stem = image.base_name
    elif image.original_filename:
        stem = Path(image.original_filename).stem
    else:
        stem = f"image-{image.image_id}"
    if image.copy_name:
        stem = f"{stem} - {image.copy_name}"
    return sanitize_component(stem) + ".jpg"


def planned_relative_path(
    image: CatalogImage | None,
    entry: PreviewEntry,
) -> Path:
    """Plan a safe, deterministic path below the recovery output root."""
    if image is None:
        name = sanitize_component(f"{entry.uuid}-{entry.digest}") + ".jpg"
        return Path("Unmapped") / name

    parts = ["Photos", sanitize_component(image.root_name or "Unknown Root")]
    folder = (image.folder_path or "").replace("\\", "/")
    for part in PurePosixPath(folder).parts:
        if part not in {"", ".", "..", "/"}:
            parts.append(sanitize_component(part))
    return Path(*parts) / _filename(image)


def contained_path(root: Path, relative: Path) -> Path:
    """Resolve a planned path and reject anything outside *root*."""
    resolved_root = root.resolve()
    destination = (resolved_root / relative).resolve()
    if not destination.is_relative_to(resolved_root):
        raise ValueError("planned output escapes the selected output root")
    return destination


def collision_path(
    path: Path,
    occupied: Callable[[Path], bool],
    max_chars: int = 239,
) -> Path:
    """Return the first unoccupied numbered variant of *path*."""
    if not occupied(path):
        return path
    for number in range(2, 100_000):
        suffix = f" ({number}){path.suffix}"
        available = max_chars - _windows_units(str(path.parent)) - 1 - _windows_units(suffix)
        if available < 1:
            raise OSError(f"selected output path is too long for {path.name}")
        stem = _truncate_utf16(path.stem, available)
        candidate = path.with_name(f"{stem}{suffix}")
        if not occupied(candidate):
            return candidate
    raise OSError(f"too many filename collisions for {path.name}")


def constrain_destination(
    root: Path,
    relative: Path,
    max_chars: int = 239,
) -> Path:
    """Contain a destination and collapse it deterministically when too long."""
    destination = contained_path(root, relative)
    if _windows_units(str(destination)) <= max_chars:
        return destination

    parts = relative.parts
    digest = hashlib.sha1(str(relative).encode("utf-8")).hexdigest()[:8]
    if len(parts) >= 4:
        relative = Path(parts[0], parts[1], f"_long_path_{digest}", parts[-1])
    else:
        relative = Path(f"_long_path_{digest}", parts[-1])
    destination = contained_path(root, relative)
    if _windows_units(str(destination)) <= max_chars:
        return destination

    overflow = _windows_units(str(destination)) - max_chars
    keep = max(12, _windows_units(destination.stem) - overflow - 9)
    shortened = f"{_truncate_utf16(destination.stem, keep)}-{digest}{destination.suffix}"
    destination = destination.with_name(shortened)
    if _windows_units(str(destination)) > max_chars:
        raise OSError("selected output path is too long for safe recovery")
    return destination
