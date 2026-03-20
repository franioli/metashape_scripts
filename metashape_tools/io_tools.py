from __future__ import annotations

import math
from pathlib import Path
from typing import Union

import Metashape

from metashape_tools.utils import (
    ask_save_file,
    get_camera_by_label,
    get_marker_by_label,
    require_active_chunk,
)


# ----- export -----
def save_sparse(
    chunk,
    file_path,
    save_color=True,
    save_cov=True,
    sep=",",
    header=True,
):
    """
    Export valid tie points to CSV with optional colour and covariance.

    Returns:
        int: number of points exported.
    """
    tie_points = chunk.tie_points
    T = chunk.transform.matrix
    if (
        chunk.transform.translation
        and chunk.transform.rotation
        and chunk.transform.scale
    ):
        T = chunk.crs.localframe(T.mulp(chunk.region.center)) * T
    R = T.rotation() * T.scale()

    exported = 0
    with open(file_path, "w") as f:
        if header:
            cols = ["track_id", "x", "y", "z"]
            if save_color:
                cols.extend(["r", "g", "b"])
            if save_cov:
                cols.extend(
                    [
                        "sX",
                        "sY",
                        "sZ",
                        "covXX",
                        "covXY",
                        "covXZ",
                        "covYY",
                        "covYZ",
                        "covZZ",
                        "var",
                    ]
                )
            f.write("{}\n".format(sep.join(cols)))

        for point in tie_points.points:
            if not point.valid:
                continue

            coord = T * point.coord
            line = [point.track_id, coord.x, coord.y, coord.z]

            if save_color:
                color = tie_points.tracks[point.track_id].color
                line.extend([color[0], color[1], color[2]])

            if save_cov:
                cov = point.cov
                cov = R * cov * R.t()
                u, s, v = cov.svd()
                var = math.sqrt(sum(s))
                line.extend(
                    [
                        math.sqrt(cov[0, 0]),
                        math.sqrt(cov[1, 1]),
                        math.sqrt(cov[2, 2]),
                        cov[0, 0],
                        cov[0, 1],
                        cov[0, 2],
                        cov[1, 1],
                        cov[1, 2],
                        cov[2, 2],
                        var,
                    ]
                )

            f.write("{}\n".format(sep.join(str(x) for x in line)))
            exported += 1

    return exported


# ----- Project from bundler format -----


def cameras_from_bundler(
    chunk: Metashape.Chunk,
    fname: str,
    image_list: str,
) -> None:
    if image_list:
        chunk.importCameras(
            str(fname),
            format=Metashape.CamerasFormat.CamerasFormatBundler,
            load_image_list=True,
            image_list=str(image_list),
        )
        print("Cameras loaded successfully from Bundler .out, using image list file.")
    else:
        chunk.importCameras(
            str(fname),
            format=Metashape.CamerasFormat.CamerasFormatBundler,
        )
        print("Cameras loaded successfully from Bundler .out.")


def import_markers(
    marker_image_file: Union[str, Path],
    marker_world_file: Union[str, Path] = None,
    chunk: Metashape.Chunk = None,
) -> None:
    """Import markers from file. If no chunk is provided, the markers are added to the current chunk."""

    marker_image_file = Path(marker_image_file)
    if not marker_image_file.exists():
        raise FileNotFoundError(f"Marker image file {marker_image_file} not found.")
    else:
        with open(marker_image_file, "rt") as input:
            marker_img_content = input.readlines()

    if marker_world_file:
        marker_world_file = Path(marker_world_file)
        if not marker_world_file.exists():
            raise FileNotFoundError(f"Marker world file {marker_world_file} not found.")
        else:
            with open(marker_world_file, "rt") as input:
                input.readlines()

    if chunk is None:
        chunk = Metashape.app.document.chunk

    for line in marker_img_content:
        c_label, m_label, x_proj, y_proj = line.split(",")

        # Ignore image extension
        c_label = Path(c_label).stem

        camera = get_camera_by_label(chunk, c_label)
        if not camera:
            print(f"{c_label} camera not found in project")
            continue

        marker = get_marker_by_label(chunk, m_label)
        if not marker:
            marker = chunk.addMarker()
            marker.label = m_label

        marker.projections[camera] = Metashape.Marker.Projection(
            Metashape.Vector([float(x_proj), float(y_proj)]), True
        )
        print(f"Added projection for {m_label} on {c_label}")


def add_markers(
    chunk: Metashape.Chunk,
    marker_image_path: Path = None,
    marker_world_path: Path = None,
    marker_file_columns: str = "noxyz",
):
    # Import markers image coordinates
    if marker_image_path is not None:
        import_markers(
            marker_image_file=marker_image_path,
            chunk=chunk,
        )

    # Import markers world coordinates
    if marker_world_path is not None:
        chunk.importReference(
            path=str(marker_world_path),
            format=Metashape.ReferenceFormatCSV,
            delimiter=",",
            skip_rows=1,
            columns=marker_file_columns,
        )


def import_bundler(
    chunk: Metashape.Chunk,
    image_dir: Path,
    bundler_file_path: Path,
    bundler_im_list: Path = None,
) -> Metashape.Document:
    # Check paths
    bundler_file_path = Path(bundler_file_path)
    if not bundler_file_path.exists():
        raise FileNotFoundError(f"Bundler file {bundler_file_path} does not exist.")

    image_dir = Path(image_dir)
    if not image_dir.exists():
        raise FileNotFoundError(f"Images directory {image_dir} does not exist.")

    if bundler_im_list is None:
        bundler_im_list = bundler_file_path.parent / "bundler_list.txt"
    if not bundler_im_list.exists():
        raise FileNotFoundError(f"Bundler image list {bundler_im_list} does not exist.")

    # Get image list
    image_list = list(image_dir.glob("*"))
    images = [str(x) for x in image_list if x.is_file()]

    # Add photos to chunk
    chunk.addPhotos(images)
    cameras_from_bundler(
        chunk=chunk,
        fname=bundler_file_path,
        image_list=bundler_im_list,
    )

    return None


# --- calibration ---


# ----- dialog -----


def export_sparse_dialog():
    chunk = require_active_chunk()
    if not chunk:
        return

    if not chunk.tie_points or not chunk.tie_points.points:
        Metashape.app.messageBox("No tie points in current chunk.")
        return

    path = ask_save_file(
        "Save sparse points CSV", filter="CSV files (*.csv);;All files (*.*)"
    )
    if not path:
        return

    n = save_sparse(chunk, path)
    Metashape.app.messageBox("Exported {} sparse points.".format(n))


def import_from_bundler_dialog():
    chunk = require_active_chunk()
    if not chunk:
        return

    image_dir = ask_save_file(
        "Select directory containing images", filter="All files (*.*)"
    )
    if not image_dir:
        return

    bundler_file = ask_save_file(
        "Select Bundler .out file", filter="Text files (*.out *.txt);;All files (*.*)"
    )
    if not bundler_file:
        return

    bundler_im_list = ask_save_file(
        "Select Bundler image list file (optional)",
        filter="Text files (*.txt);;All files (*.*)",
    )

    res = import_bundler(
        chunk=chunk,
        image_dir=Path(image_dir),
        bundler_file_path=Path(bundler_file),
        bundler_im_list=Path(bundler_im_list) if bundler_im_list else None,
    )
    Metashape.app.messageBox("Import complete.")
