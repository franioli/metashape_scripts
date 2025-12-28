import math
import statistics
from typing import Optional

import Metashape

from metashape_tools.utils import (
    ask_bool,
    ask_float,
    ask_int,
    ask_string,
    print_table,
    require_active_chunk,
)

# ---------------------------
# Tie-point covariance tools
# ---------------------------


def _chunk_transform_rotation_scale(chunk: Metashape.Chunk) -> Metashape.Matrix:
    """
    rotation*scale matrix used to transform covariance into chunk coordinates.
    (Same approach you already used.)
    """
    T = chunk.transform.matrix
    if (
        chunk.transform.translation
        and chunk.transform.rotation
        and chunk.transform.scale
    ):
        T = chunk.crs.localframe(T.mulp(chunk.region.center)) * T
    return T.rotation() * T.scale()


def compute_tiepoint_variances(chunk: Metashape.Chunk):
    """
    Returns list of (point_index, variance) for valid points with covariance.
    variance metric: sqrt(trace(R*cov*R^T))
    """
    R = _chunk_transform_rotation_scale(chunk)
    out = []
    points = chunk.tie_points.points

    for i, p in enumerate(points):
        if not getattr(p, "valid", True):
            continue
        cov = getattr(p, "cov", None)
        if cov is None:
            continue
        cov_t = R * cov * R.t()
        trace = float(cov_t[0, 0] + cov_t[1, 1] + cov_t[2, 2])
        trace = max(trace, 0.0)
        out.append((i, math.sqrt(trace)))
    return out


def _percentile(sorted_values, p: float) -> Optional[float]:
    if not sorted_values:
        return None
    n = len(sorted_values)
    if p <= 0:
        return sorted_values[0]
    if p >= 100:
        return sorted_values[-1]
    pos = (p / 100.0) * (n - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_values[lo]
    frac = pos - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def filter_tiepoints_by_covariance(
    chunk: Metashape.Chunk, percentile_to_remove: float
) -> dict:
    """
    Disable points with variance >= percentile threshold.
    """
    data = compute_tiepoint_variances(chunk)
    if not data:
        return {"total_considered": 0, "threshold": None, "disabled": 0, "failed": 0}

    values = sorted(v for (_i, v) in data)
    threshold = _percentile(values, percentile_to_remove)
    if threshold is None:
        return {"total_considered": 0, "threshold": None, "disabled": 0, "failed": 0}

    to_disable = [idx for (idx, v) in data if v >= threshold]
    disabled = 0
    failed = 0
    for idx in to_disable:
        try:
            chunk.tie_points.points[idx].valid = False
            disabled += 1
        except Exception:
            failed += 1

    return {
        "total_considered": len(data),
        "threshold": float(threshold),
        "disabled": disabled,
        "failed": failed,
    }


def _mean_images_per_valid_point(chunk: Metashape.Chunk) -> Optional[float]:
    """
    TiePoints.Point has no .projections in your Metashape version.
    Compute "images per point" via tie_points.projections[*].track_id.
    """
    tie = chunk.tie_points
    points = tie.points
    if not points:
        return None

    track_valid = {p.track_id: bool(getattr(p, "valid", True)) for p in points}
    counts = {}  # track_id -> count

    for cam in chunk.cameras:
        proj_list = tie.projections[cam]
        for proj in proj_list:
            tid = proj.track_id
            if not track_valid.get(tid, False):
                continue
            counts[tid] = counts.get(tid, 0) + 1

    if not counts:
        return None
    return statistics.mean(counts.values())


def compute_tiepoint_stats(chunk: Metashape.Chunk) -> dict:
    """
    Simple tie-point stats:
      - total_points, valid_points
      - variance stats (from covariance)
      - reprojection error stats (Metashape filter)
      - mean_images_per_point (computed from tie_points.projections)
    """
    points = chunk.tie_points.points
    total = len(points)
    valid = sum(1 for p in points if getattr(p, "valid", True))

    var_list = [v for (_i, v) in compute_tiepoint_variances(chunk)]
    var_sorted = sorted(var_list)

    stats = {
        "total_points": total,
        "valid_points": valid,
        "points_with_cov": len(var_list),
        "mean_variance": statistics.mean(var_list) if var_list else None,
        "median_variance": statistics.median(var_list) if var_list else None,
        "p90_variance": _percentile(var_sorted, 90.0) if var_list else None,
        "mean_reproj": None,
        "median_reproj": None,
        "p90_reproj": None,
        "mean_images_per_point": _mean_images_per_valid_point(chunk),
    }

    # reprojection error stats
    f = Metashape.TiePoints.Filter()
    f.init(chunk.tie_points, criterion=Metashape.TiePoints.Filter.ReprojectionError)
    reproj = [
        v
        for i, v in enumerate(f.values)
        if i < len(points) and getattr(points[i], "valid", True)
    ]
    if reproj:
        r_sorted = sorted(reproj)
        stats["mean_reproj"] = statistics.mean(reproj)
        stats["median_reproj"] = statistics.median(reproj)
        stats["p90_reproj"] = _percentile(r_sorted, 90.0)

    return stats


def format_tiepoint_stats(stats: dict) -> str:
    lines = [
        f"Total tie points: {int(stats.get('total_points', 0) or 0)}",
        f"Valid points: {int(stats.get('valid_points', 0) or 0)}",
        f"Points with covariance: {int(stats.get('points_with_cov', 0) or 0)}",
    ]
    if stats.get("mean_variance") is not None:
        lines.append(
            "Variance (mean/median/p90): "
            f"{stats['mean_variance']:.6g} / {stats['median_variance']:.6g} / {stats['p90_variance']:.6g}"
        )
    else:
        lines.append("Variance: (no covariance)")

    if stats.get("mean_reproj") is not None:
        lines.append(
            "Reproj (mean/median/p90): "
            f"{stats['mean_reproj']:.6g} / {stats['median_reproj']:.6g} / {stats['p90_reproj']:.6g}"
        )
    else:
        lines.append("Reproj: (no reprojection data)")

    if stats.get("mean_images_per_point") is not None:
        lines.append(
            f"Avg images per valid point: {stats['mean_images_per_point']:.3g}"
        )
    else:
        lines.append("Avg images per valid point: (no data)")
    return "\n".join(lines)


# ---------------------------------------------
# Tie-point projection distribution per camera
# ---------------------------------------------


def collect_valid_camera_image_coords(chunk: Metashape.Chunk, cameras=None):
    """
    camera -> list[(x,y)] using chunk.tie_points.projections[cam],
    counting only projections whose tie point is valid.
    """
    tie = chunk.tie_points
    points = tie.points
    track_valid = {p.track_id: bool(getattr(p, "valid", True)) for p in points}

    cams = list(cameras) if cameras is not None else list(chunk.cameras)
    out = {cam: [] for cam in cams}

    for cam in cams:
        proj_list = tie.projections[cam]
        w = getattr(getattr(cam, "sensor", None), "width", None) or getattr(
            getattr(cam, "photo", None), "width", None
        )
        h = getattr(getattr(cam, "sensor", None), "height", None) or getattr(
            getattr(cam, "photo", None), "height", None
        )

        for proj in proj_list:
            if not track_valid.get(proj.track_id, False):
                continue
            c = proj.coord
            x = float(c.x)
            y = float(c.y)
            if w and h and (x < 0 or x >= w or y < 0 or y >= h):
                continue
            out[cam].append((x, y))

    return out


def estimate_tiepoint_distribution(
    chunk: Metashape.Chunk, cameras=None, grid=10
) -> dict:
    """
    Simple fast metrics per image:
      - count (valid tie-point projections)
      - occupancy (grid occupancy)
      - bbox_ratio (coverage ratio)
      - center_offset (centroid vs center, normalized by diagonal)
    Prints a compact table and returns dict keyed by camera.
    """
    cams = list(cameras) if cameras is not None else list(chunk.cameras)
    cam_coords = collect_valid_camera_image_coords(chunk, cams)

    results = {}
    rows = []
    for cam in cams:
        pts = cam_coords.get(cam, [])
        n = len(pts)

        w = getattr(getattr(cam, "sensor", None), "width", None) or getattr(
            getattr(cam, "photo", None), "width", None
        )
        h = getattr(getattr(cam, "sensor", None), "height", None) or getattr(
            getattr(cam, "photo", None), "height", None
        )
        area = (w * h) if (w and h) else None

        # bbox_ratio
        if n and area:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            bbox_area = max(0.0, (max(xs) - min(xs)) * (max(ys) - min(ys)))
            bbox_ratio = bbox_area / float(area)
        else:
            bbox_ratio = 0.0

        # occupancy
        if n and w and h:
            cells = set()
            for x, y in pts:
                gx = max(0, min(grid - 1, int(x * grid / float(w))))
                gy = max(0, min(grid - 1, int(y * grid / float(h))))
                cells.add((gx, gy))
            occupancy = len(cells) / float(grid * grid)
        else:
            occupancy = 0.0

        # center_offset
        if n and w and h:
            cx = sum(p[0] for p in pts) / n
            cy = sum(p[1] for p in pts) / n
            center_dist = math.hypot(cx - w / 2.0, cy - h / 2.0)
            diag = math.hypot(w, h) or 1.0
            center_offset = center_dist / diag
        else:
            center_offset = 0.0

        results[cam] = {
            "count": n,
            "occupancy": occupancy,
            "bbox_ratio": bbox_ratio,
            "center_offset": center_offset,
        }

        lab = (cam.label or "")[:36]
        rows.append(
            [
                lab,
                str(n),
                f"{occupancy:.3f}",
                f"{bbox_ratio:.3f}",
                f"{center_offset:.3f}",
            ]
        )

    # Sort by occupancy (worst first)
    rows.sort(key=lambda r: float(r[2]))
    print_table(["Image", "count", "occup", "bbox", "cent"], rows)
    return results


# ---------------------------
# Region / bbox filtering
# ---------------------------


def disable_tiepoints_outside_region(chunk: Metashape.Chunk) -> dict:
    """
    Disable tie points outside chunk.region box.
    Simple and fast: point is tested in region's rotated frame.
    """
    region = chunk.region
    center = region.center
    size = region.size
    R = region.rot  # rotation matrix

    points = chunk.tie_points.points
    disabled = 0
    considered = 0

    half = Metashape.Vector([size.x / 2.0, size.y / 2.0, size.z / 2.0])

    for p in points:
        if not getattr(p, "valid", True):
            continue
        considered += 1
        v = R.t() * (p.coord - center)
        inside = (abs(v.x) <= half.x) and (abs(v.y) <= half.y) and (abs(v.z) <= half.z)
        if not inside:
            p.valid = False
            disabled += 1

    return {"considered": considered, "disabled": disabled}


# ---------------------------
# GUI dialogs (thin wrappers)
# ---------------------------


def tiepoint_stats_dialog():
    chunk = require_active_chunk()
    if not chunk:
        return
    stats = compute_tiepoint_stats(chunk)
    Metashape.app.messageBox("Tie point statistics:\n\n" + format_tiepoint_stats(stats))


def tiepoint_covariance_filter_dialog():
    chunk = require_active_chunk()
    if not chunk:
        return

    p = ask_float(
        "Percentile to REMOVE (0..100). Points with variance >= threshold will be disabled.",
        90.0,
    )
    if p is None:
        return
    p = max(0.0, min(100.0, float(p)))

    before = compute_tiepoint_stats(chunk)
    res = filter_tiepoints_by_covariance(chunk, p)
    after = compute_tiepoint_stats(chunk)

    print("\n=== BEFORE ===")
    print(format_tiepoint_stats(before))
    print("\n=== AFTER ===")
    print(format_tiepoint_stats(after))

    Metashape.app.messageBox(
        "Filtering complete.\n\n"
        f"Considered: {res['total_considered']}\n"
        f"Threshold: {res['threshold']}\n"
        f"Disabled: {res['disabled']}\n\n"
        "See console for before/after."
    )


def tiepoints_disable_outside_region_dialog():
    chunk = require_active_chunk()
    if not chunk:
        return

    proceed = ask_bool("Disable tie points outside the current region?")
    if not proceed:
        return

    res = disable_tiepoints_outside_region(chunk)
    Metashape.app.messageBox(
        f"Done.\nConsidered: {res['considered']}\nDisabled: {res['disabled']}"
    )


def tiepoint_distribution_dialog():
    chunk = require_active_chunk()
    if not chunk:
        return

    selected = [c for c in chunk.cameras if getattr(c, "selected", False)]
    cams = selected if selected else list(chunk.cameras)

    grid = ask_int("Occupancy grid size (e.g. 8 or 10)", 10)
    if grid is None:
        return

    results = estimate_tiepoint_distribution(chunk, cameras=cams, grid=grid)

    move = ask_bool("Move images below a threshold into a new camera group?")
    if not move:
        return

    metric = ask_string(
        "Metric (occupancy, bbox_ratio, center_offset, count)", "occupancy"
    )
    if not metric:
        return
    metric = metric.lower()
    if metric not in ("occupancy", "bbox_ratio", "center_offset", "count"):
        Metashape.app.messageBox("Unsupported metric.")
        return

    if metric == "count":
        thr = ask_int("Move cameras with count < threshold", 200)
        if thr is None:
            return
        thr_val = int(thr)
        bad = [cam for cam, d in results.items() if int(d.get("count", 0)) < thr_val]
    else:
        thr = ask_float(f"Move cameras with {metric} < threshold", 0.10)
        if thr is None:
            return
        thr_val = float(thr)
        bad = [cam for cam, d in results.items() if float(d.get(metric, 0.0)) < thr_val]

    if not bad:
        Metashape.app.messageBox("No cameras below threshold.")
        return

    name = ask_string(
        f"New camera group name ({len(bad)} cameras)", "low_tiepoint_distribution"
    )
    if not name:
        return

    group = chunk.addCameraGroup(name)
    for cam in bad:
        group.add(cam)

    Metashape.app.messageBox(f"Moved {len(bad)} cameras into group: {name}")
