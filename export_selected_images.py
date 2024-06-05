import shutil

import Metashape

from utils import check_compatibility

check_compatibility(["2.0", "2.1"])


def main():
    """
    Exports the photos of selected cameras from the current Metashape project to a user-specified directory.

    This function performs the following steps:
    1. Checks if a document is loaded in Metashape. If no document is loaded, it prints an error message and exits.
    2. Prompts the user to select an output folder. If no folder is selected, it exits.
    3. Iterates through the cameras in the current chunk and copies the photos of selected cameras to the output folder.

    Args:
        None

    Returns:
        None
    """
    doc = Metashape.app.document
    if not doc:
        print("No document loaded.")
        return

    dest_path = Metashape.app.getExistingDirectory("Select output folder:")
    if not dest_path:
        return
    print("Exporting selected cameras ...")
    chunk = doc.chunk
    for camera in chunk.cameras:
        if camera.selected:
            print(camera.photo.path)
            shutil.copy2(camera.photo.path, dest_path)

    print(f"Images exported to {dest_path}.\n")


Metashape.app.addMenuItem("Scripts/Export selected images", main)
