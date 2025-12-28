import xml.etree.ElementTree as ET

import Metashape

from metashape_tools.utils import check_compatibility

check_compatibility(["2.0", "2.1"])


def read_xml_and_export_colmap_parameters(opencv_xml: str, output_paht: str):
    tree = ET.parse(opencv_xml)
    root = tree.getroot()

    # Extract camera matrix parameters
    camera_matrix = root.find(".//Camera_Matrix/data").text.split()
    fx, _, cx, _, fy, cy, _, _, _ = map(float, camera_matrix)

    # Extract distortion coefficients
    distortion_coeffs = root.find(".//Distortion_Coefficients/data").text.split()
    k1, k2, p1, p2, k3 = map(float, distortion_coeffs)

    # TODO: Determine the proper COLMAP model
    colmap_model = "FULL_OPENCV"

    # Prepare the COLMAP format string
    if colmap_model == "FULL_OPENCV":
        k4, k5, k6 = 0.0, 0.0, 0.0
        colmap_parameters = [fx, fy, cx, cy, k1, k2, p1, p2, k3, k4, k5, k6]
        out_str = ", ".join(map(str, colmap_parameters))

    # Write the results to the output file
    with open(output_paht, "w") as output_file:
        output_file.write(f"{colmap_model}\n")
        output_file.write(out_str)


def main():
    doc = Metashape.app.document

    dest_path = Metashape.app.getExistingDirectory("Select output folder:")

    sensors = doc.chunk.sensors
    print("Sensors number: ", len(sensors))
    print("Sensors: ", sensors)

    for sensor in sensors:
        sens_name = sensor.label.replace(" ", "_")
        opencv_fname = dest_path + "/" + sens_name + "_opencv.xml"
        colmap_fname = dest_path + "/" + sens_name + "_colmap.txt"
        sensor.calibration.save(opencv_fname, format=Metashape.CalibrationFormatOpenCV)
        read_xml_and_export_colmap_parameters(opencv_fname, colmap_fname)

    print(f"Calibration exported to {dest_path}.\n")


Metashape.app.addMenuItem("Scripts/Export/COLMAP calibration", main)
