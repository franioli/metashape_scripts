"""
Estimate tie-point projection statistics for cameras in the active chunk.
"""

import Metashape


def collect_camera_coords_from_tiepoints(chunk, cameras=None):
    """
    Return mapping camera -> list[(x,y)] using chunk.tie_points.
    Prefer stored projections (proj_map[cam]) if available; fallback to cam.project().

    Only counts projections whose tied tie-point is present and valid.
    """
    if chunk is None:
        raise ValueError("chunk must be provided")

    tie_points = chunk.tie_points
    if not tie_points:
        return {}

    cams = list(cameras) if cameras is not None else list(chunk.cameras)
    if not cams:
        return {}

    # build track_id -> tie point object map so we can check .valid
    pts = list(getattr(tie_points, "points", []))
    track_to_point = {
        getattr(p, "track_id", None): p
        for p in pts
        if getattr(p, "track_id", None) is not None
    }

    cam_coords = {cam: [] for cam in cams}
    for cam in cams:
        # use stored projections if present
        try:
            proj_list = tie_points.projections[cam]
        except Exception:
            # no stored projections for this camera
            proj_list = None

        if not proj_list:
            continue

        for proj in proj_list:
            # only count projections that reference an existing, valid tie-point
            track_id = getattr(proj, "track_id", None)
            if track_id is None:
                continue
            tp = track_to_point.get(track_id)
            if not tp or not getattr(tp, "valid", True):
                continue

            coord = getattr(proj, "coord", None)
            if coord is None:
                continue
            x = float(coord.x)
            y = float(coord.y)

            # bounds check (if dims available)
            w = cam.sensor.width
            h = cam.sensor.height
            if w and h and (x < 0 or x >= w or y < 0 or y >= h):
                continue

            cam_coords[cam].append((x, y))

    return cam_coords


def estimate_tiepoint_distribution(chunk, cameras=None, grid=8):
    """
    Simple, fast per-image tie-point / projection distribution estimator.
    Delegates coordinate collection to collect_camera_coords_from_tiepoints().
    """

    if chunk is None:
        raise ValueError("chunk must be provided")

    cams = list(cameras) if cameras is not None else list(chunk.cameras)

    # Exclude non-aligned cameras
    print("Filtering non-aligned cameras...")
    cams = [c for c in cams if c.transform is not None]
    print(f"Number of aligned cameras: {len(cams)}")
    if not cams:
        print("No cameras to analyze.")
        return {}

    tie_points = chunk.tie_points
    if not tie_points or not list(getattr(tie_points, "points", [])):
        print("No tie points found in chunk.")
        return {}

    cam_coords = collect_camera_coords_from_tiepoints(chunk, cameras=cams)

    results = {}
    print("\n" + "=" * 60)
    print("TIEPOINT DISTRIBUTION")
    print("=" * 60)
    for cam in cams:
        pts = cam_coords.get(cam, [])
        n = len(pts)

        # image dimensions
        w = cam.sensor.width
        h = cam.sensor.height
        area = w * h

        # bounding box coverage
        if n:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            bbox_w = max(xs) - min(xs)
            bbox_h = max(ys) - min(ys)
            bbox_area = max(0.0, bbox_w * bbox_h)
            bbox_ratio = (bbox_area / area) if area else 0.0
        else:
            bbox_area = 0.0
            bbox_ratio = 0.0

        # occupancy on a coarse grid
        if n and w and h:
            cells = set()
            for x, y in pts:
                gx = max(0, min(grid - 1, int(x * grid / float(w))))
                gy = max(0, min(grid - 1, int(y * grid / float(h))))
                cells.add((gx, gy))
            occupancy = len(cells) / float(grid * grid)
        else:
            occupancy = 0.0

        results[cam] = {
            "count": n,
            "occupancy": occupancy,
            "bbox_area": bbox_area,
            "bbox_ratio": bbox_ratio,
        }

        lab = getattr(cam, "label", str(cam))
        print(f"Image: {lab}")
        print(f"  projections: {n}")
        print(f"  occupancy ({grid}x{grid}): {occupancy:.3f}")
        print(f"  bbox_ratio: {bbox_ratio:.4f}")
        print("-" * 60)

    print("End of analysis.")
    print("=" * 60 + "\n")
    return results


def _print_compact_table(results, max_label=36):
    """
    Print results in a compact table suitable for large image counts.
    results: dict {camera: {count, occupancy, bbox_ratio, center_offset}}
    """
    # header
    hdr = f"{'Image':{max_label}} {'count':>7} {'occup':>7} {'bbox':>7} {'cent':>7}"
    print(hdr)
    print("-" * len(hdr))
    # sort by occupancy ascending so problem images appear first
    rows = sorted(
        results.items(),
        key=lambda kv: (kv[1].get("occupancy", 0.0), kv[1].get("count", 0)),
    )
    for cam, data in rows:
        lab = getattr(cam, "label", str(cam))[:max_label]
        print(
            f"{lab:{max_label}} {data.get('count', 0):7d} {data.get('occupancy', 0.0):7.3f} "
            f"{data.get('bbox_ratio', 0.0):7.3f} {data.get('center_offset', 0.0):7.3f}"
        )


def estimate_tiepoint_distribution_dialog():
    """
    GUI wrapper for estimate_tiepoint_distribution().
    Runs analysis on selected cameras (if any) or all cameras in the active chunk.
    After analysis, asks user if they want to move images below a chosen threshold
    to a new image group.
    """
    doc = Metashape.app.document
    if not doc:
        Metashape.app.messageBox("No active document.")
        return

    chunk = doc.chunk
    if not chunk:
        Metashape.app.messageBox("No active chunk.")
        return

    # chosen cameras = selected if any else all
    selected = [c for c in chunk.cameras if c.selected]
    cams = selected if selected else list(chunk.cameras)
    if not cams:
        Metashape.app.messageBox("No cameras found to analyze.")
        return

    # ask grid
    grid = Metashape.app.getInt("Grid size for occupancy (e.g. 8 or 10)", 10)
    if grid is None:
        return

    # run backend
    results = estimate_tiepoint_distribution(chunk, cameras=cams, grid=grid)
    if not results:
        Metashape.app.messageBox("No results - no tie points or projections found.")
        return

    # show compact table in console
    print("\nCompact results (sorted by occupancy):")
    _print_compact_table(results)

    # Ask to move low scoring images
    move = Metashape.app.getBool(
        "Move images below a threshold to a new image group?\n\n"
        "If Yes, you will choose a metric and a numeric threshold.\n"
        "Selected images will be moved to a new camera group.\n"
        "If No, the script will end here and you can inspect results in the console (suggested the first time)."
    )
    if not move:
        return

    # metric choice
    metric = Metashape.app.getString(
        "Choose metric (occupancy, bbox_ratio, center_offset, count)", "occupancy"
    )
    if metric is None:
        return
    metric = metric.strip().lower()
    if metric not in ("occupancy", "bbox_ratio", "center_offset", "count"):
        Metashape.app.messageBox("Unsupported metric.")
        return

    # threshold
    if metric == "count":
        default = 50
        thr = Metashape.app.getInt(
            f"Move images with {metric} < threshold (integer)", default
        )
        if thr is None:
            return
    else:
        default = 0.5 if metric == "occupancy" else 0.02
        thr = Metashape.app.getFloat(
            f"Move images with {metric} < threshold (float)", default
        )
        if thr is None:
            return

    # collect candidates
    to_move = [cam for cam, d in results.items() if d.get(metric, 0.0) < thr]
    if not to_move:
        Metashape.app.messageBox("No images fall below the selected threshold.")
        return

    # ask group name
    group_name = Metashape.app.getString(
        f"{len(to_move)} images will be moved. Enter new camera group name:",
        "low_tiepoints",
    )
    if not group_name:
        return

    moved = []
    try:
        new_group = chunk.addCameraGroup()
        new_group.label = group_name
        for cam in to_move:
            cam.group = new_group
            moved.append(cam)

    except Exception as e:
        print("Failed to create/add camera group:", e)

    Metashape.app.messageBox(
        f"Moved {len(moved)} of {len(to_move)} images to '{group_name}'."
    )
    print("Moved cameras:", [getattr(c, "label", str(c)) for c in moved])
    return {"moved": moved, "candidates": to_move}


# register menu item
def add_menu_item():
    Metashape.app.addMenuItem(
        "Custom/Tie Points/Estimate tie-point distribution...",
        estimate_tiepoint_distribution_dialog,
    )
    print("Registered menu item: Custom/Tie Points/Estimate tie-point distribution...")


# only register on import
add_menu_item()


# Keep console-run behavior under main guard to avoid running at import time
if __name__ == "__main__":
    chunk = Metashape.app.document.chunk
    if not chunk:
        raise RuntimeError("No active chunk in the open document.")

    selected = [c for c in chunk.cameras if c.selected]
    cameras_to_analyze = selected if selected else list(chunk.cameras)
    print(
        f"\nRunning tie-point distribution analysis on "
        f"{'selected cameras' if selected else 'all cameras'} ({len(cameras_to_analyze)}) in chunk: {getattr(chunk, 'label', '<unnamed>')}"
    )

    results = estimate_tiepoint_distribution(chunk, cameras=cameras_to_analyze, grid=20)

    if results:
        _print_compact_table(results)
        # basic aggregates
        counts = [v["count"] for v in results.values()]
        occ = [v["occupancy"] for v in results.values()]
        bbox = [v["bbox_ratio"] for v in results.values()]
        print(
            "\nAggregate: images=%d count_min=%d count_mean=%.1f count_max=%d occupancy_mean=%.3f bbox_mean=%.3f"
            % (
                len(results),
                min(counts),
                sum(counts) / len(counts),
                max(counts),
                sum(occ) / len(occ),
                sum(bbox) / len(bbox),
            )
        )
