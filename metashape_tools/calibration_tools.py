from __future__ import annotations

import xml.etree.ElementTree as ET

import Metashape


def read_xml_and_export_colmap_parameters(
    opencv_xml: str, output_path: str, colmap_model: str = "FULL_OPENCV"
) -> None:
    """Read an OpenCV XML calibration file and write COLMAP-format parameters.

    Args:
        opencv_xml: Path to the OpenCV XML calibration file.
        output_path: Path where the COLMAP calibration text file will be written.
        colmap_model: The COLMAP model to use.
    """
    tree = ET.parse(opencv_xml)
    root = tree.getroot()

    # Extract camera matrix parameters
    camera_matrix = root.find(".//Camera_Matrix/data").text.split()
    fx, _, cx, _, fy, cy, _, _, _ = map(float, camera_matrix)

    # Extract distortion coefficients
    distortion_coeffs = root.find(".//Distortion_Coefficients/data").text.split()
    k1, k2, p1, p2, k3 = map(float, distortion_coeffs)

    # TODO: Implement support for other COLMAP models

    # Prepare the COLMAP format string
    if colmap_model == "FULL_OPENCV":
        k4, k5, k6 = 0.0, 0.0, 0.0
        colmap_parameters = [fx, fy, cx, cy, k1, k2, p1, p2, k3, k4, k5, k6]
        out_str = ", ".join(map(str, colmap_parameters))
    else:
        raise ValueError(f"Other COLMAP models not implemented yet: {colmap_model}")

    # Write the results to the output file
    with open(output_path, "w") as output_file:
        output_file.write(f"{colmap_model}\n")
        output_file.write(out_str)


def convert_opencv_to_colmap() -> None:
    """Export all sensor calibrations in the active chunk to COLMAP format.

    Prompts the user for an output folder, then saves each sensor's calibration
    as both an OpenCV XML and a COLMAP text file.
    """

    dest_path = Metashape.app.getExistingDirectory("Select output folder:")
    sensors = Metashape.app.document.chunk.sensors
    print("Sensors number: ", len(sensors))
    print("Sensors: ", sensors)

    for sensor in sensors:
        sens_name = sensor.label.replace(" ", "_")
        opencv_fname = dest_path + "/" + sens_name + "_opencv.xml"
        colmap_fname = dest_path + "/" + sens_name + "_colmap.txt"
        sensor.calibration.save(opencv_fname, format=Metashape.CalibrationFormatOpenCV)
        read_xml_and_export_colmap_parameters(opencv_fname, colmap_fname, "FULL_OPENCV")

    print(f"Calibration exported to {dest_path}.\n")


if __name__ == "__main__":
    Metashape.app.addMenuItem(
        "Custom/Other/Convert OpenCV to COLMAP...",
        convert_opencv_to_colmap,
    )
