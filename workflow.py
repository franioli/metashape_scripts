import threading
from pathlib import Path
from typing import Union

import Metashape

from utils import get_camera_by_label, get_marker_by_label

"""Project"""


def create_new_project(
    project_name: str,
    chunk_name: str = None,
    read_only: bool = False,
) -> Metashape.app.document:
    doc = Metashape.Document()
    doc.read_only = read_only
    create_new_chunk(doc, chunk_name)
    save_project(doc, project_name)

    return doc


def save_project_interactive(
    document: Metashape.app.document,
) -> None:
    try:
        document.save()
    except RuntimeError:
        Metashape.app.messageBox("Can't save project")


def save_project(
    doc: Metashape.app.document,
    path: Union[str, Path] = None,
    wait_saved: bool = True,
):
    def _save(doc, path=None):
        doc.read_only = False
        if path is not None:
            doc.save(str(path))
        else:
            doc.save()

    if doc.path is None and path is None:
        raise ValueError(
            "Document has not been saved yet and no path is specified. Please specify a path to save the document."
        )

    if path is not None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        x = threading.Thread(target=_save, args=(doc, path))
    else:
        x = threading.Thread(target=_save, args=(doc,))
    x.start()

    if wait_saved:
        x.join()

    return x


def create_new_chunk(doc: Metashape.app.document, chunk_name: str = None) -> None:
    chunk = doc.addChunk()
    if chunk_name is not None:
        chunk.label = chunk_name


def duplicate_chunk(
    chunk: Metashape.Chunk,
    new_name: str = None,
) -> Metashape.Chunk:
    new_chunk = chunk.copy()
    if new_name is not None:
        new_chunk.label = new_name
    return new_chunk


def expand_region(chunk, resize_fct: float) -> None:
    chunk.resetRegion()
    chunk.region.size = resize_fct * chunk.region.size


def clear_all_sensors(chunk) -> None:
    for sensor in chunk.sensors:
        chunk.remove(sensor)


"""Markers"""


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


"""BUndle Adjustment"""


def optimize_cameras(chunk: Metashape.Chunk, params: dict = {}) -> None:
    chunk.optimizeCameras(
        fit_f=params.get("f", True),
        fit_cx=params.get("cx", True),
        fit_cy=params.get("cy", True),
        fit_b1=params.get("b1", False),
        fit_b2=params.get("b2", False),
        fit_k1=params.get("k1", True),
        fit_k2=params.get("k2", True),
        fit_k3=params.get("k3", True),
        fit_k4=params.get("k4", False),
        fit_p1=params.get("p1", True),
        fit_p2=params.get("p2", True),
        tiepoint_covariance=params.get("tiepoint_covariance", True),
    )
