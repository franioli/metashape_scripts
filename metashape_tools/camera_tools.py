import os
from collections import defaultdict

import Metashape

from metashape_tools.utils import ask_bool, require_active_chunk


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
