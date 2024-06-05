"""
This script imports/export GCPs from a CSV file into a Metashape project.
The CSV file have the following format:
image_name, gcp_name, image_u, image_v
IMG_0001.JPG,point 1,100,200
IMG_0001.JPG,point 2,345,400
IMG_0002.JPG,point 2,786,211
"""

import os

import Metashape

from utils import check_compatibility, get_camera_by_label, get_marker_by_label

check_compatibility(["2.0", "2.1"])


def import_markers_images(header: bool = False, separator: str = ",") -> None:
    """
    Imports marker image coordinates from a CSV file into the current Metashape project.

    The CSV file should have the following format:
    image_label,gcp_name,image_u,image_v
    Example:
    IMG_0001,point_1,100,200
    IMG_0001,point_2,345,400
    IMG_0002,point_2,786,211

    Prompts the user to select the CSV file, reads its contents, and adds the
    marker projections to the respective images in the chunk.
    """

    path = Metashape.app.getOpenFileName("Select file with marker image coordinates:")

    chunk = Metashape.app.document.chunk

    with open(path, "rt") as input:
        content = input.readlines()
        content = content[1:] if header else content

    for line in content:
        c_label, m_label, x_proj, y_proj = line.split(separator)

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


def export_markers_images(header: bool = False, separator: str = ",") -> None:
    """
    Exports marker image coordinates from the current Metashape project to a CSV file.

    Prompts the user to select a save location for the CSV file, and writes the
    marker projections in the following format:
    image_label,marker_label,image_u,image_v

    Example:
    image_label,marker_label,x,y
    IMG_0001.JPG,point_1,100,200
    IMG_0001.JPG,point_2,345,400
    IMG_0002.JPG,point_2,786,211
    """

    path = Metashape.app.getSaveFileName("Save file with marker image coordinates:")
    chunk = Metashape.app.document.chunk

    with open(path, "w") as output:
        s = separator
        if header:
            output.write(f"image_label{s}marker_label{s}x{s}y\n")
        for marker in chunk.markers:
            for camera in chunk.cameras:
                if camera in marker.projections.keys():
                    coord = marker.projections[camera].coord
                    output.write(
                        f"{camera.label}{s}{marker.label}{s}{coord.x}{s}{coord.y}\n"
                    )
                    print(f"Exported projection for {marker.label} on {camera.label}")


def write_markers_one_cam_per_file(to_opencv_rs: bool = True) -> None:
    """
    Write marker image coordinates to CSV files, with one file per camera, named with the camera label.

    Each file is formatted as follows:
    marker1, x, y
    marker2, x, y
    ...
    markerM, x, y

    Args:
        to_opencv_rs (bool): If True, subtracts 0.5 pixels from the image coordinates to convert from Metashape image reference system to OpenCV image reference system. Default is True.

    Returns:
        None
    """

    output_dir = Metashape.app.getExistingDirectory()
    doc = Metashape.app.document
    chunk = doc.chunk

    for camera in chunk.cameras:
        # Write header to file
        fname = os.path.join(output_dir, camera.label + ".csv")
        file = open(fname, "w")
        file.write("label,x,y\n")

        for marker in chunk.markers:
            projections = marker.projections  # list of marker projections
            marker_name = marker.label

            for cur_cam in marker.projections.keys():
                if cur_cam == camera:
                    x, y, _ = projections[cur_cam].coord

                    # subtract 0.5 px to image coordinates (metashape image RS)
                    if to_opencv_rs:
                        x -= 0.5
                        y -= 0.5

                    # writing output to file
                    file.write(f"{marker_name},{x:.4f},{y:.4f}\n")
        file.close()

    print("All targets exported successfully")


Metashape.app.addMenuItem("Scripts/Markers/Export projections", export_markers_images)

Metashape.app.addMenuItem("Scripts/Markers/Import projections", import_markers_images)

Metashape.app.addMenuItem(
    "Scripts/Markers/Export projections by camera", write_markers_one_cam_per_file
)
