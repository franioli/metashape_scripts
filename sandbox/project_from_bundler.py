from pathlib import Path

import Metashape

from metashape_tools.utils import check_compatibility
from workflow import (
    import_markers,
)

check_compatibility(["2.0", "2.1"])


def cameras_from_bundler(
    chunk: Metashape.Chunk,
    fname: str,
    image_list: str,
) -> None:
    if image_list:
        chunk.importCameras(
            str(fname),
            format=Metashape.CamerasFormat.CamerasFormatBundler,
            load_image_list=True,
            image_list=str(image_list),
        )
        print("Cameras loaded successfully from Bundler .out, using image list file.")
    else:
        chunk.importCameras(
            str(fname),
            format=Metashape.CamerasFormat.CamerasFormatBundler,
        )
        print("Cameras loaded successfully from Bundler .out.")


def add_markers(
    chunk: Metashape.Chunk,
    marker_image_path: Path = None,
    marker_world_path: Path = None,
    marker_file_columns: str = "noxyz",
):
    # Import markers image coordinates
    if marker_image_path is not None:
        import_markers(
            marker_image_file=marker_image_path,
            chunk=chunk,
        )

    # Import markers world coordinates
    if marker_world_path is not None:
        chunk.importReference(
            path=str(marker_world_path),
            format=Metashape.ReferenceFormatCSV,
            delimiter=",",
            skip_rows=1,
            columns=marker_file_columns,
        )


def import_bundler(
    chunk: Metashape.Chunk,
    image_dir: Path,
    bundler_file_path: Path,
    bundler_im_list: Path = None,
) -> Metashape.Document:
    # Check paths
    bundler_file_path = Path(bundler_file_path)
    if not bundler_file_path.exists():
        raise FileNotFoundError(f"Bundler file {bundler_file_path} does not exist.")

    image_dir = Path(image_dir)
    if not image_dir.exists():
        raise FileNotFoundError(f"Images directory {image_dir} does not exist.")

    if bundler_im_list is None:
        bundler_im_list = bundler_file_path.parent / "bundler_list.txt"
    if not bundler_im_list.exists():
        raise FileNotFoundError(f"Bundler image list {bundler_im_list} does not exist.")

    # Get image list
    image_list = list(image_dir.glob("*"))
    images = [str(x) for x in image_list if x.is_file()]

    # Add photos to chunk
    chunk.addPhotos(images)
    cameras_from_bundler(
        chunk=chunk,
        fname=bundler_file_path,
        image_list=bundler_im_list,
    )

    return None


def main():
    chunk = Metashape.app.document.chunk
    bundler_file_path = Metashape.app.getOpenFileName("Open Bundler file")
    image_dir = Metashape.app.getExistingDirectory("Open image directory")

    import_bundler(chunk, image_dir, bundler_file_path)


Metashape.app.addMenuItem("Scripts/Import/Bundler solution", main)
