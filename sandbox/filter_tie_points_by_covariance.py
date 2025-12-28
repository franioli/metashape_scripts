import math
import statistics
from typing import Dict, List, Optional, Tuple

import Metashape


def _chunk_transform_rotation_scale(chunk: Metashape.Chunk) -> Metashape.Matrix:
    """Return rotation*scale matrix to transform covariance into chunk coordinates (same approach as export)."""
    T = chunk.transform.matrix
    if (
        chunk.transform.translation
        and chunk.transform.rotation
        and chunk.transform.scale
    ):
        T = chunk.crs.localframe(T.mulp(chunk.region.center)) * T
    return T.rotation() * T.scale()


def compute_tiepoint_variances(chunk: Metashape.Chunk) -> List[Tuple[int, float]]:
    """
    Return a list of (point_index, variance_value) for valid tie points that have a covariance matrix.
    Variance metric used: sqrt(trace(cov_transformed))
    """
    R = _chunk_transform_rotation_scale(chunk)
    out: List[Tuple[int, float]] = []
    points = chunk.tie_points.points
    for i, p in enumerate(points):
        if not getattr(p, "valid", True):
            continue
        cov = getattr(p, "cov", None)
        if cov is None:
            continue
        try:
            cov_t = R * cov * R.t()
            trace = float(cov_t[0, 0] + cov_t[1, 1] + cov_t[2, 2])
            if trace < 0:
                # defensive: numerical issues should not create negative trace for covariance
                trace = max(trace, 0.0)
            var = math.sqrt(trace)
            out.append((i, var))
        except Exception:
            # skip malformed covariance entries
            continue
    return out


def _percentile(sorted_values: List[float], p: float) -> Optional[float]:
    """Return quantile value p in [0..100] for a sorted list. Simple interpolation."""
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
    Disable (valid=False) tie points whose variance >= percentile threshold.
    percentile_to_remove: number in 0..100 representing the percentile cutoff value (e.g. 90 -> remove points >= 90th percentile).
    Returns summary dict with counts.
    """
    data = compute_tiepoint_variances(chunk)
    if not data:
        return {"total_considered": 0, "threshold": None, "disabled": 0}

    values = sorted([v for (_i, v) in data])
    threshold = _percentile(values, percentile_to_remove)
    if threshold is None:
        return {"total_considered": 0, "threshold": None, "disabled": 0}

    # find indices to disable (variance >= threshold)
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


def compute_tiepoint_stats(chunk: Metashape.Chunk) -> Dict[str, Optional[float]]:
    """
    Compute simple statistics for tie points in `chunk`.
    Returns a dict with counts and simple metrics:
      - total_points, valid_points, points_with_cov
      - mean_variance, median_variance, p90_variance (computed from covariance)
      - mean_reproj, median_reproj, p90_reproj (from reprojection error filter values)
      - mean_images_per_point
    """
    stats: Dict[str, Optional[float]] = {
        "total_points": 0,
        "valid_points": 0,
        "points_with_cov": 0,
        "mean_variance": None,
        "median_variance": None,
        "p90_variance": None,
        "mean_reproj": None,
        "median_reproj": None,
        "p90_reproj": None,
        "mean_images_per_point": None,
    }

    points = chunk.tie_points.points
    stats["total_points"] = len(points)
    valid_idx = [i for i, p in enumerate(points) if getattr(p, "valid", True)]
    stats["valid_points"] = len(valid_idx)

    # variance list (use compute_tiepoint_variances)
    var_list = [v for (_i, v) in compute_tiepoint_variances(chunk)]
    stats["points_with_cov"] = len(var_list)
    if var_list:
        stats["mean_variance"] = statistics.mean(var_list)
        stats["median_variance"] = statistics.median(var_list)
        stats["p90_variance"] = _percentile(sorted(var_list), 90.0)

    # reprojection errors using TiePoints.Filter.ReprojectionError
    try:
        f = Metashape.TiePoints.Filter()
        f.init(chunk.tie_points, criterion=Metashape.TiePoints.Filter.ReprojectionError)
        reproj_values = [
            v
            for i, v in enumerate(f.values)
            if i < len(points) and getattr(points[i], "valid", True)
        ]
        if reproj_values:
            stats["mean_reproj"] = statistics.mean(reproj_values)
            stats["median_reproj"] = statistics.median(reproj_values)
            stats["p90_reproj"] = _percentile(sorted(reproj_values), 90.0)
    except Exception:
        # ignore if filter cannot be evaluated
        pass

    # average number of images (projections) per valid point
    images_per = []
    for i in valid_idx:
        p = points[i]
        count = 0
        try:
            for proj in p.projections:
                # projection objects normally have enabled attribute
                if getattr(proj, "enabled", True):
                    count += 1
        except Exception:
            # fallback: ignore malformed projection structures
            continue
        images_per.append(count)
    if images_per:
        stats["mean_images_per_point"] = statistics.mean(images_per)

    return stats


def _format_stats_report(stats: Dict[str, Optional[float]]) -> str:
    """Small helper to format stats into a readable text block."""
    lines = []
    lines.append(f"Total tie points: {int(stats.get('total_points', 0) or 0)}")
    lines.append(f"Valid points: {int(stats.get('valid_points', 0) or 0)}")
    lines.append(f"Points with covariance: {int(stats.get('points_with_cov', 0) or 0)}")
    if stats.get("mean_variance") is not None:
        lines.append(
            f"Variance (mean/median/p90): "
            f"{stats['mean_variance']:.6g} / {stats['median_variance']:.6g} / {stats['p90_variance']:.6g}"
        )
    else:
        lines.append("Variance: (no covariance data)")
    if stats.get("mean_reproj") is not None:
        lines.append(
            f"Reprojection error (mean/median/p90): "
            f"{stats['mean_reproj']:.6g} / {stats['median_reproj']:.6g} / {stats['p90_reproj']:.6g}"
        )
    else:
        lines.append("Reprojection error: (no reprojection data)")
    if stats.get("mean_images_per_point") is not None:
        lines.append(
            f"Avg images per valid point: {stats['mean_images_per_point']:.3g}"
        )
    else:
        lines.append("Avg images per valid point: (no data)")
    return "\n".join(lines)


def tiepoint_stats_dialog():
    """GUI: compute and print tie point statistics for the active chunk."""
    doc = Metashape.app.document
    if not doc:
        Metashape.app.messageBox("No active Metashape document.")
        return
    chunk = doc.chunk
    if not chunk:
        Metashape.app.messageBox("No active chunk.")
        return

    stats = compute_tiepoint_stats(chunk)
    Metashape.app.messageBox("Tie point statistics:\n\n" + _format_stats_report(stats))


def tiepoint_covariance_filter_dialog():
    """GUI dialog to run covariance-based tie-point filtering."""
    doc = Metashape.app.document
    if not doc:
        Metashape.app.messageBox("No active Metashape document.")
        return
    chunk = doc.chunk
    if not chunk:
        Metashape.app.messageBox("No active chunk.")
        return

    data = compute_tiepoint_variances(chunk)
    if not data:
        Metashape.app.messageBox(
            "No valid tie points with covariance found in this chunk."
        )
        return

    # collect before stats (no message box here)
    before_stats = compute_tiepoint_stats(chunk)

    # let user pick percentile to *remove*
    p = Metashape.app.getFloat(
        "Percentile threshold to REMOVE (points with variance >= threshold will be disabled, 0..100)",
        90.0,
    )
    if p is None:
        return
    p = max(0.0, min(100.0, float(p)))

    values_sorted = sorted([v for (_i, v) in data])
    thresh = _percentile(values_sorted, p)
    sample_high = values_sorted[-10:][::-1] if values_sorted else []
    sample_msg = "\n".join([f"{x:.6g}" for x in sample_high[:10]])

    msg = (
        f"Found {len(values_sorted)} tie points with covariance.\n"
        f"{p:.2f} percentile threshold value = {thresh:.6g}\n\n"
        f"Sample highest variances:\n{sample_msg}\n\n"
        "Proceed to disable all points with variance >= threshold?"
    )
    proceed = Metashape.app.getBool(msg)
    if not proceed:
        return

    res = filter_tiepoints_by_covariance(chunk, p)

    # compute after stats
    after_stats = compute_tiepoint_stats(chunk)

    # print both stats to console (BEFORE and AFTER)
    print("\n=== Tie-point statistics BEFORE filtering ===")
    print(_format_stats_report(before_stats))
    print("\n=== Tie-point statistics AFTER filtering ===")
    print(_format_stats_report(after_stats))

    # concise completion message; point user to console for full reports
    Metashape.app.messageBox(
        "Filtering complete.\n\n"
        f"Summary: Considered: {res['total_considered']} Threshold: {res['threshold']:.6g} Disabled: {res['disabled']}\n\n"
        "Full before/after statistics were printed to the console."
    )


# Register menu items
if __name__ == "__main__":
    Metashape.app.addMenuItem(
        "Custom/TiePoints/Filter by Covariance...", tiepoint_covariance_filter_dialog
    )
    Metashape.app.addMenuItem(
        "Custom/TiePoints/Show Statistics...", tiepoint_stats_dialog
    )
