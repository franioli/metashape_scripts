from __future__ import annotations

import Metashape

from metashape_tools.utils import (
    ask_bool,
    ask_open_file,
    ask_save_file,
    get_camera_by_label,
    get_marker_by_label,
    require_active_chunk,
)


def import_markers_images(chunk, path, header=False, separator=","):
    """
    Import marker image-coordinate projections from a CSV file.

    Expected format (one row per projection):
        camera_label,marker_label,img_x,img_y

    Returns:
        dict with added and skipped counts.
    """
    with open(path, "r") as f:
        lines = f.readlines()
    if header:
        lines = lines[1:]

    added = 0
    skipped = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split(separator)
        if len(parts) < 4:
            skipped += 1
            continue

        c_label, m_label = parts[0].strip(), parts[1].strip()
        x_proj, y_proj = float(parts[2]), float(parts[3])

        camera = get_camera_by_label(chunk, c_label)
        if not camera:
            print("Camera not found: {}".format(c_label))
            skipped += 1
            continue

        marker = get_marker_by_label(chunk, m_label)
        if not marker:
            marker = chunk.addMarker()
            marker.label = m_label

        marker.projections[camera] = Metashape.Marker.Projection(
            Metashape.Vector([x_proj, y_proj]), True
        )
        added += 1

    return {"added": added, "skipped": skipped}


def export_markers_images(chunk, path, header=True, separator=","):
    """
    Export marker image-coordinate projections to a CSV file.

    Output format:
        camera_label,marker_label,x,y

    Returns:
        int: number of projections exported.
    """
    exported = 0
    s = separator
    with open(path, "w") as f:
        if header:
            f.write("image_label{}marker_label{}x{}y\n".format(s, s, s))
        for marker in chunk.markers:
            for camera in chunk.cameras:
                if camera in marker.projections.keys():
                    coord = marker.projections[camera].coord
                    f.write(
                        "{}{}{}{}{}{}{}\n".format(
                            camera.label, s, marker.label, s, coord.x, s, coord.y
                        )
                    )
                    exported += 1
    return exported


# ----- dialogs -----


def import_markers_images_dialog():
    chunk = require_active_chunk()
    if not chunk:
        return

    path = ask_open_file(
        "Select marker projections CSV",
        filter="CSV files (*.csv *.txt);;All files (*.*)",
    )
    if not path:
        return

    header = ask_bool("Does the file have a header row?")

    res = import_markers_images(chunk, path, header=header)
    Metashape.app.messageBox(
        "Import complete.\nAdded: {}\nSkipped: {}".format(res["added"], res["skipped"])
    )


def export_markers_images_dialog():
    chunk = require_active_chunk()
    if not chunk:
        return

    if not chunk.markers:
        Metashape.app.messageBox("No markers in current chunk.")
        return

    path = ask_save_file(
        "Save marker projections CSV",
        filter="CSV files (*.csv);;All files (*.*)",
    )
    if not path:
        return

    n = export_markers_images(chunk, path)
    Metashape.app.messageBox("Exported {} projections.".format(n))
