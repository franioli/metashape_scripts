from typing import List, Union

import Metashape


def get_camera_by_label(chunk: Metashape.Chunk, label: str) -> Metashape.Camera:
    """
    Retrieves a camera from the chunk by its label.

    Args:
        chunk (Metashape.Chunk): The chunk containing the cameras.
        label (str): The label of the camera to retrieve.

    Returns:
        Metashape.Camera or None: The camera with the specified label, or None if not found.
    """

    # If the label has the extension, remove it
    label = label.split(".")[0]

    for camera in chunk.cameras:
        if camera.label == label:
            return camera
    print(f"camera {label} not found")
    return None


def get_marker_by_label(chunk: Metashape.Chunk, label: str) -> Metashape.Marker:
    """
    Retrieves a marker from the chunk by its label.

    Args:
        chunk (Metashape.Chunk): The chunk containing the markers.
        label (str): The label of the marker to retrieve.

    Returns:
        Metashape.Marker or None: The marker with the specified label, or None if not found.
    """
    for marker in chunk.markers:
        if marker.label == label:
            return marker
    return None


def get_sensor_id_by_label(
    chunk: Metashape.Chunk,
    sensor_label: str,
) -> int:
    """
    Retrieves the sensor ID from the chunk by its label.

    Args:
        chunk (Metashape.Chunk): The chunk containing the sensors.
        sensor_label (str): The label of the sensor to retrieve the ID for.

    Returns:
        int: The ID of the sensor with the specified label, or None if not found.
    """
    sensors = chunk.sensors
    for s_id in sensors:
        sensor = sensors[s_id]
        if sensor.label == sensor_label:
            return s_id


""" MISCELLANEOUS """


def check_compatibility(major_version: Union[str, List[str]]):
    """
    Checks if the current Metashape version is compatible with the specified major version(s).

    Args:
        major_version (Union[str, List[str]]): A single major version or a list of major versions to check against.
                                               The version should be in the format 'major.minor'.

    Raises:
        Exception: If the current Metashape version is not compatible with any of the specified major versions.

    Returns:
        None
    """
    if not isinstance(major_version, list):
        major_version = [major_version]

    ms_version = ".".join(Metashape.app.version.split(".")[:2])
    if ms_version not in major_version:
        raise Exception(
            f"Incompatible Metashape version: {ms_version} != {major_version}"
        )


def make_homogeneous(
    v: Metashape.Vector,
) -> Metashape.Vector:
    """
    Converts a vector to homogeneous coordinates.

    Args:
        v (Metashape.Vector): The vector to convert.

    Returns:
        Metashape.Vector: The homogeneous vector.
    """
    vh = Metashape.Vector([1.0 for x in range(v.size + 1)])
    for i, x in enumerate(v):
        vh[i] = x

    return vh


def make_inomogenous(
    vh: Metashape.Vector,
) -> Metashape.Vector:
    """
    Converts a homogeneous vector to inhomogeneous coordinates.

    Args:
        vh (Metashape.Vector): The homogeneous vector to convert.

    Returns:
        Metashape.Vector: The inhomogeneous vector.
    """
    v = vh / vh[vh.size - 1]
    return v[: v.size - 1]
