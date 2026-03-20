from __future__ import annotations

import os
import shutil
from collections import defaultdict

import Metashape

from metashape_tools.utils import (
    ask_bool,
    ask_save_file,
    require_active_chunk,
)


def _camera_basename(cam: Metashape.Camera) -> str:
    """
    Duplicate key: filename-like camera label without extension, case-insensitive.
    """
    lab = (cam.label or "").strip().lower()
    return os.path.splitext(lab)[0]


def _camera_valid_tiepoint_projection_count(
    chunk: Metashape.Chunk, cam: Metashape.Camera
) -> int:
    """
    Count projections in chunk.tie_points.projections[cam] whose tie point is valid.
    """
    tie = chunk.tie_points
    points = tie.points
    track_valid = {p.track_id: bool(getattr(p, "valid", True)) for p in points}
    cnt = 0
    for proj in tie.projections[cam]:
        if track_valid.get(proj.track_id, False):
            cnt += 1
    return cnt


def find_duplicate_cameras(chunk: Metashape.Chunk):
    """
    Returns list of groups: [[cam1, cam2, ...], ...]
    """
    groups = defaultdict(list)
    for cam in chunk.cameras:
        key = _camera_basename(cam)
        if key:
            groups[key].append(cam)
    return [g for g in groups.values() if len(g) > 1]


def remove_duplicate_cameras(chunk: Metashape.Chunk) -> dict:
    """
    Remove duplicates using rule:
      - prefer keeping an oriented (transform!=None) camera
      - if not oriented, prefer one that HAS tie points (valid projections > 0)
      - if both not oriented, remove the LAST one (keep earlier ones)

    Works for groups with >2: keeps the best candidate, removes the rest.
    """
    dups = find_duplicate_cameras(chunk)
    removed = 0

    for group in dups:
        # preserve original order as appears in chunk.cameras
        def quality(cam):
            aligned = 1 if cam.transform is not None else 0
            tp = _camera_valid_tiepoint_projection_count(chunk, cam)
            has_tp = 1 if tp > 0 else 0
            return (aligned, has_tp, tp)

        # keep best quality; if tie, keep earliest in group
        best = max(group, key=lambda c: (quality(c), -group.index(c)))
        # If all are unaligned (aligned==0), rule says "remove last" => keep first.
        if all(c.transform is None for c in group):
            best = group[0]

        for cam in group:
            if cam is best:
                continue
            chunk.remove(cam)
            removed += 1

    return {"duplicate_groups": len(dups), "removed": removed}


def clear_camera_source_coordinates(chunk, cameras=None):
    """
    Clear all camera source (reference) coordinates.

    Args:
        chunk: Metashape.Chunk

    Returns:
        int: Number of cameras cleared
    """
    print("\n" + "=" * 70)
    print("CLEARING CAMERA SOURCE COORDINATES")
    print("=" * 70)

    # If no explicit cameras list is supplied, operate on all cameras in the chunk
    if cameras is None:
        cameras = list(chunk.cameras)

    cleared = 0

    for camera in cameras:
        if camera.reference.location is not None:
            camera.reference.location = None
            camera.reference.enabled = False
            cleared += 1

    print(f"Cleared {cleared} camera source coordinates")
    print("=" * 70)

    return cleared


def write_estimated_to_source(
    chunk, offset=None, overwrite_existing=True, cameras=None
):
    """
    Write estimated camera positions to source (reference) coordinates.
    Transforms coordinates to chunk CRS if set.

    Returns:
        dict with total, written, skipped_unaligned, skipped_existing counts.
    """
    if cameras is None:
        cameras = list(chunk.cameras)

    written = 0
    skipped_unaligned = 0
    skipped_existing = 0

    for camera in cameras:
        if camera.transform is None:
            skipped_unaligned += 1
            continue

        if not overwrite_existing and camera.reference.location is not None:
            skipped_existing += 1
            continue

        camera_geocentric = chunk.transform.matrix.mulp(camera.center)
        if chunk.crs:
            estimated_pos = chunk.crs.project(camera_geocentric)
        else:
            estimated_pos = camera_geocentric

        if offset:
            estimated_pos = Metashape.Vector(
                [
                    estimated_pos.x + offset.x,
                    estimated_pos.y + offset.y,
                    estimated_pos.z + offset.z,
                ]
            )

        camera.reference.location = estimated_pos
        camera.reference.enabled = True
        written += 1

    return {
        "total": len(cameras),
        "written": written,
        "skipped_unaligned": skipped_unaligned,
        "skipped_existing": skipped_existing,
    }


def export_selected_images(chunk, dest_path, copy_metadata=True):
    """
    Export photos for selected cameras (or all if none selected) to dest_path.

    Returns:
        dict with total_selected, copied, skipped_missing counts.
    """
    cameras_to_export = [c for c in chunk.cameras if getattr(c, "selected", False)]
    if not cameras_to_export:
        cameras_to_export = list(chunk.cameras)

    copied = 0
    skipped_missing = 0

    for camera in cameras_to_export:
        src = getattr(camera, "photo", None)
        if not src:
            skipped_missing += 1
            continue
        src_path = getattr(src, "path", None)
        if not src_path:
            skipped_missing += 1
            continue

        try:
            if copy_metadata:
                shutil.copy2(src_path, dest_path)
            else:
                shutil.copy(src_path, dest_path)
            copied += 1
        except Exception as e:
            print("Failed to copy {}: {}".format(src_path, e))

    return {
        "total_selected": len(cameras_to_export),
        "copied": copied,
        "skipped_missing": skipped_missing,
    }


def export_camera_reference(chunk, file_path, sep=","):
    """
    Export camera reference coordinates to CSV.

    Returns:
        int: number of cameras exported.
    """
    exported = 0
    with open(file_path, "w") as f:
        f.write(
            "{}label{}x{}y{}z\n".format(
                "",
                sep,
                sep,
                sep,
            )
        )
        for cam in chunk.cameras:
            loc = cam.reference.location
            if loc is None:
                continue
            f.write(
                "{}{}{}{}{}{}{}\n".format(cam.label, sep, loc.x, sep, loc.y, sep, loc.z)
            )
            exported += 1
    return exported


# ----- camera dialogs -----


def remove_duplicate_cameras_dialog():
    chunk = require_active_chunk()
    if not chunk:
        return
    dups = find_duplicate_cameras(chunk)
    if not dups:
        Metashape.app.messageBox("No duplicate images found.")
        return

    proceed = ask_bool(f"Found {len(dups)} duplicate group(s). Remove duplicates?")
    if not proceed:
        return

    res = remove_duplicate_cameras(chunk)
    Metashape.app.messageBox(
        f"Done.\nGroups: {res['duplicate_groups']}\nRemoved: {res['removed']}"
    )


def clear_camera_coordinates_dialog():
    """
    Dialog to clear camera source coordinates.
    """
    chunk = Metashape.app.document.chunk

    if not chunk:
        Metashape.app.messageBox("No active chunk!")
        return

    # Prefer processing selected cameras when present
    selected_cameras = [cam for cam in chunk.cameras if getattr(cam, "selected", False)]
    cameras_to_clear = selected_cameras if selected_cameras else list(chunk.cameras)

    has_source = sum(
        1 for cam in cameras_to_clear if cam.reference.location is not None
    )

    if has_source == 0:
        Metashape.app.messageBox(
            "No cameras with source coordinates found in the chosen set!"
        )
        return

    response = Metashape.app.getBool(
        f"Clear source coordinates for {has_source} cameras?\n\n"
        f"This will only clear coordinates in Metashape,\n"
        f"not modify image EXIF data.\n\n"
        f"Continue?"
    )

    if response:
        count = clear_camera_source_coordinates(chunk, cameras=cameras_to_clear)
        Metashape.app.messageBox(f"Cleared {count} camera source coordinates.")


def write_estimated_to_source_dialog():
    chunk = require_active_chunk()
    if not chunk:
        return

    selected = [c for c in chunk.cameras if getattr(c, "selected", False)]
    cameras = selected if selected else list(chunk.cameras)
    aligned = sum(1 for c in cameras if c.transform is not None)
    has_source = sum(1 for c in cameras if c.reference.location is not None)

    if aligned == 0:
        Metashape.app.messageBox("No aligned cameras found.")
        return

    scope = (
        "selected ({})".format(len(cameras))
        if selected
        else "all ({})".format(len(cameras))
    )
    if not ask_bool(
        "Write estimated positions to source for {} cameras?\n"
        "Aligned: {}\nWith source coords: {}".format(scope, aligned, has_source)
    ):
        return

    use_offset = ask_bool("Apply an offset to positions?")
    offset = None
    if use_offset:
        from metashape_tools.utils import ask_float

        dx = ask_float("X offset (dx)", 0.0)
        if dx is None:
            return
        dy = ask_float("Y offset (dy)", 0.0)
        if dy is None:
            return
        dz = ask_float("Z offset (dz)", 0.0)
        if dz is None:
            return
        offset = Metashape.Vector([dx, dy, dz])

    overwrite = True
    if has_source > 0:
        overwrite = ask_bool(
            "{} cameras already have source coords. Overwrite?".format(has_source)
        )

    res = write_estimated_to_source(chunk, offset, overwrite, cameras=cameras)
    Metashape.app.messageBox(
        "Done.\nWritten: {}\nSkipped (unaligned): {}\nSkipped (existing): {}".format(
            res["written"], res["skipped_unaligned"], res["skipped_existing"]
        )
    )


def export_selected_images_dialog():
    chunk = require_active_chunk()
    if not chunk:
        return

    dest = Metashape.app.getExistingDirectory("Select destination folder")
    if not dest:
        return

    res = export_selected_images(chunk, dest)
    Metashape.app.messageBox(
        "Export complete.\nCopied: {}\nSkipped: {}".format(
            res["copied"], res["skipped_missing"]
        )
    )


def export_camera_reference_dialog():
    chunk = require_active_chunk()
    if not chunk:
        return

    path = ask_save_file(
        "Save camera reference CSV", filter="CSV files (*.csv);;All files (*.*)"
    )
    if not path:
        return

    n = export_camera_reference(chunk, path)
    Metashape.app.messageBox("Exported {} camera references.".format(n))
