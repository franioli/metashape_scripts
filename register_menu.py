import Metashape

from metashape_tools import (
    calibration_tools,
    camera_tools,
    chunk_tools,
    fiducials_tools,
    incremental_alignment,
    io_tools,
    markers_tools,
    tie_points_tools,
    triangulation,
)
from metashape_tools.utils import check_compatibility

check_compatibility(["2.0", "2.1", "2.2"])


if __name__ == "__main__":
    # Tie points
    Metashape.app.addMenuItem(
        "Custom/TiePoints/Show Statistics...", tie_points_tools.tiepoint_stats_dialog
    )
    Metashape.app.addMenuItem(
        "Custom/TiePoints/Filter by Covariance...",
        tie_points_tools.tiepoint_covariance_filter_dialog,
    )
    Metashape.app.addMenuItem(
        "Custom/TiePoints/Disable Outside Region...",
        tie_points_tools.tiepoints_disable_outside_region_dialog,
    )

    # Cameras
    Metashape.app.addMenuItem(
        "Custom/Cameras/Remove duplicates...",
        camera_tools.remove_duplicate_cameras_dialog,
    )
    Metashape.app.addMenuItem(
        "Custom/Cameras/Clear camera source coordinates...",
        camera_tools.clear_camera_coordinates_dialog,
    )
    Metashape.app.addMenuItem(
        "Custom/Cameras/Write estimated to source...",
        camera_tools.write_estimated_to_source_dialog,
    )
    Metashape.app.addMenuItem(
        "Custom/Cameras/Export selected images...",
        camera_tools.export_selected_images_dialog,
    )
    Metashape.app.addMenuItem(
        "Custom/Cameras/Export reference CSV...",
        camera_tools.export_camera_reference_dialog,
    )

    # Markers
    Metashape.app.addMenuItem(
        "Custom/Markers/Import projections...",
        markers_tools.import_markers_images_dialog,
    )
    Metashape.app.addMenuItem(
        "Custom/Markers/Export projections...",
        markers_tools.export_markers_images_dialog,
    )

    # Incremental alignment
    Metashape.app.addMenuItem(
        "Custom/Incremental Alignment/Align unaligned...",
        incremental_alignment.incremental_alignment_dialog,
    )
    Metashape.app.addMenuItem(
        "Custom/Incremental Alignment/Realign selected...",
        incremental_alignment.realign_selected_cameras_dialog,
    )
    Metashape.app.addMenuItem(
        "Custom/Incremental Alignment/Export unaligned list...",
        incremental_alignment.export_unaligned_list_dialog,
    )
    Metashape.app.addMenuItem(
        "Custom/Incremental Alignment/Transfer oriented from chunk...",
        incremental_alignment.transfer_oriented_cameras_dialog,
    )

    # Chunk
    Metashape.app.addMenuItem(
        "Custom/Chunk/Expand region...",
        chunk_tools.expand_region_dialog,
    )

    # FIducials
    Metashape.app.addMenuItem(
        "Custom/Fiducials/Import from CSV...",
        fiducials_tools.import_fiducials_from_file_dialog,
    )
    Metashape.app.addMenuItem(
        "Custom/Fiducials/Add manually...", fiducials_tools.add_fiducial_manual_dialog
    )

    # IO / export-import
    Metashape.app.addMenuItem(
        "Custom/IO/Export sparse points...", io_tools.export_sparse_dialog
    )
    Metashape.app.addMenuItem(
        "Custom/IO/Project from Bundler...", io_tools.import_from_bundler_dialog
    )

    # Other tools can be added here following the same pattern
    Metashape.app.addMenuItem(
        "Custom/Other/Convert OpenCV to COLMAP...",
        calibration_tools.convert_opencv_to_colmap,
    )
    Metashape.app.addMenuItem(
        "Custom/Other/Triangulate points from CSV...", triangulation.triangulate_points
    )

    print("Custom tools registered (Custom/*).")
    print("")
    print(
        "NOTE: this package is in early development and tools may not work as expected. Please report any issues to the developers."
    )
