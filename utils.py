from typing import List, Union

import Metashape


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


def find_camera_by_label(chunk: Metashape.Chunk, label: str):
    """
    Finds a camera in the given chunk by its label.

    Args:
        chunk (Metashape.Chunk): The chunk containing the cameras.
        label (str): The label of the camera to find.

    Returns:
        Metashape.Camera or None: The camera with the specified label, or None if not found.

    Prints:
        A message if the camera with the specified label is not found.
    """
    cameras = chunk.cameras
    for cam in cameras:
        if cam.label == label:
            return cam
    print(f"camera {label} not found")


def getMarker(chunk: Metashape.Chunk, label: str) -> Metashape.Marker:
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


def getCamera(chunk: Metashape.Chunk, label: str) -> Metashape.Camera:
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
    return None
