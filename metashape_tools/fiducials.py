import os

import Metashape

from metashape_tools.utils import (
    ask_bool,
    ask_float,
    ask_int,
    ask_open_file,
    ask_string,
    require_active_chunk,
)


def _find_camera(chunk: Metashape.Chunk, cam_key: str) -> Metashape.Camera | None:
    key = cam_key.strip().upper()
    for c in chunk.cameras:
        if (c.label or "").strip().upper() == key:
            return c
    for c in chunk.cameras:
        if key in (c.label or "").strip().upper():
            return c
    return None


def add_fiducial(
    chunk: Metashape.Chunk,
    camera: Metashape.Camera | str,
    label: str,
    img_x: float,
    img_y: float,
    world_x: float | None = None,
    world_y: float | None = None,
    world_z: float = 1.0,
) -> Metashape.Marker:
    """
    Create a fiducial marker with an image projection (pixels).
    Optionally set reference.location (mm), with default world_z=1.0.
    """
    cam = camera if not isinstance(camera, str) else _find_camera(chunk, camera)
    if cam is None:
        raise ValueError("Camera not found")

    m = chunk.addMarker()
    m.type = Metashape.Marker.Type.Fiducial
    m.sensor = cam.sensor
    m.label = label

    x = float(img_x)
    y = float(img_y)
    m.projections[cam] = Metashape.Marker.Projection(Metashape.Vector([x, y]), True)

    if world_x is not None and world_y is not None:
        m.reference.location = Metashape.Vector(
            [float(world_x), float(world_y), float(world_z)]
        )
        m.reference.enabled = True

    return m


def read_fiducials_file(path: str, sep: str = ","):
    """
    Reads lines:
      label,camera_label,img_x,img_y[,world_x,world_y[,world_z]]
    Returns list of dicts.
    """
    out = []
    with open(path, "r") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(sep)]
            if len(parts) < 4:
                continue

            rec = {
                "label": parts[0],
                "camera": parts[1],
                "img_x": float(parts[2]),
                "img_y": float(parts[3]),
                "world_x": None,
                "world_y": None,
                "world_z": 1.0,
            }
            if len(parts) >= 6:
                rec["world_x"] = float(parts[4])
                rec["world_y"] = float(parts[5])
            if len(parts) >= 7:
                rec["world_z"] = float(parts[6])
            out.append(rec)
    return out


def import_fiducials_from_file(path: str, chunk: Metashape.Chunk) -> dict:
    """
    Imports fiducials from a file into chunk.
    """
    if not os.path.isfile(path):
        raise ValueError("File not found")

    recs = read_fiducials_file(path)
    created = 0
    skipped = 0

    for r in recs:
        cam = _find_camera(chunk, r["camera"])
        if cam is None:
            skipped += 1
            continue
        add_fiducial(
            chunk,
            cam,
            r["label"],
            r["img_x"],
            r["img_y"],
            r["world_x"],
            r["world_y"],
            r["world_z"],
        )
        created += 1

    return {"created": created, "skipped": skipped}


# ----------------
# GUI dialogs
# ----------------


def import_fiducials_from_file_dialog():
    chunk = require_active_chunk()
    if not chunk:
        return
    path = ask_open_file(
        "Select fiducials file", filter="Text/CSV (*.txt *.csv);;All files (*.*)"
    )
    if not path:
        return
    res = import_fiducials_from_file(path, chunk)
    Metashape.app.messageBox(
        f"Import complete.\nCreated: {res['created']}\nSkipped: {res['skipped']}"
    )


def add_fiducial_manual_dialog():
    chunk = require_active_chunk()
    if not chunk:
        return
    if not chunk.cameras:
        Metashape.app.messageBox("No cameras in chunk.")
        return

    idx = ask_int(f"Camera index (0..{len(chunk.cameras) - 1})", 0)
    if idx is None or idx < 0 or idx >= len(chunk.cameras):
        return
    cam = chunk.cameras[idx]

    label = ask_string("Fiducial label", "fid_1")
    if not label:
        return

    img_x = ask_float("Image X (pixels)", 0.0)
    if img_x is None:
        return
    img_y = ask_float("Image Y (pixels)", 0.0)
    if img_y is None:
        return

    use_world = ask_bool("Set fiducial reference location (mm)?")
    wx = wy = None
    wz = 1.0
    if use_world:
        wx = ask_float("World X (mm)", 0.0)
        if wx is None:
            return
        wy = ask_float("World Y (mm)", 0.0)
        if wy is None:
            return
        wz = ask_float("World Z (mm)", 1.0)
        if wz is None:
            return

    add_fiducial(chunk, cam, label, img_x, img_y, wx, wy, wz)
    Metashape.app.messageBox(f"Created fiducial '{label}' on '{cam.label}'.")
