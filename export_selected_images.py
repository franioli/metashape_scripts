import shutil

import Metashape

from utils import check_compatibility

check_compatibility(["2.0", "2.1"])

def main():
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
