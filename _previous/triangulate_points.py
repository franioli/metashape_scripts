"""
This script is part of a workflow to import Ground Control Points (GCPs) from a CSV file into a Metashape project. The CSV file should follow this format:

image_name, gcp_name, image_u, image_v
IMG_0001,point 1,100,200
IMG_0001,point 2,345,400
IMG_0002,point 2,786,211

Note that the image_name must match the image label in Metashape, without the file extension.

The function processes the image coordinates of markers detected on multiple images, writes these coordinates to separate CSV files for each camera, and optionally adjusts the coordinates to the OpenCV reference system. This data can then be used to triangulate the markers and obtain their 3D coordinates within the chunk space.
"""

import os

import Metashape

from metashape_tools.utils import check_compatibility, get_camera_by_label, get_marker_by_label

check_compatibility(["2.0", "2.1"])


def main():
    """
    Imports marker image coordinates from a CSV file into the current Metashape project,
    updates the transformation matrix, and exports the triangulated 3D coordinates.

    The CSV file should have the following format:
    image_name,gcp_name,image_u,image_v
    Example:
    IMG_0001,point 1,100,200
    IMG_0001,point 2,345,400
    IMG_0002,point 2,786,211

    Prompts the user to select the CSV file, reads its contents, and adds the
    marker projections to the respective images in the chunk. The transformation
    matrix of the chunk is then updated, and the triangulated coordinates of the
    markers are exported to a CSV file.
    """
    path = Metashape.app.getOpenFileName("Select file with image coordinates:")

    chunk = Metashape.app.document.chunk

    with open(path, "rt") as input:
        content = input.readlines()

    # Iterate through each line in the CSV file and add the marker projections to the corresponding cameras
    for line in content:
        c_label, m_label, x_proj, y_proj = line.split(",")

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

    # Call Metashape UpateTransform() to update the transformation matrix of the chunk
    chunk.updateTransform()

    # Export the triangulated 3D coordinates ("estimated") of the markers
    out_dir = os.path.dirname(path)
    with open(os.path.join(out_dir, "triangulated.csv"), "wt") as output:
        for marker in chunk.markers:
            coord = chunk.transform.matrix.mulp(marker.position)
            output.write(f"{marker.label},{coord.x:.6f},{coord.y:.6f},{coord.z:.6f}\n")
    print("Triangulated coordinates exported to triangulated.csv")


Metashape.app.addMenuItem("Scripts/Triangulate points", main)
