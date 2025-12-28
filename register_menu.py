import Metashape
from metashape_tools.io import bundler, calibration, sparse

from metashape_tools import (
    camera_tools,
    incremental_alignment,
    markers_tools,
    tie_points_tools,
)
from metashape_tools.utils import check_compatibility

check_compatibility(["2.0", "2.1"])


def register_menu_items() -> None:
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
        "Custom/Cameras/Write estimated to source...",
        camera_tools.write_estimated_to_source_dialog,
    )
    Metashape.app.addMenuItem(
        "Custom/Cameras/Export selected images...",
        camera_tools.export_selected_images_dialog,
    )
    Metashape.app.addMenuItem(
        "Custom/Cameras/Remove duplicates...",
        camera_tools.remove_duplicate_cameras_dialog,
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
    Metashape.app.addMenuItem(
        "Custom/Markers/Triangulate from projections...",
        markers_tools.triangulate_markers_dialog,
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

    # IO / export-import
    Metashape.app.addMenuItem(
        "Custom/IO/Export sparse points...", sparse.export_sparse_dialog
    )
    Metashape.app.addMenuItem(
        "Custom/IO/Export COLMAP calibration...",
        calibration.export_colmap_calibration_dialog,
    )
    Metashape.app.addMenuItem(
        "Custom/IO/Import Bundler solution...", bundler.import_bundler_dialog
    )


if __name__ == "__main__":
    register_menu_items()
    print("Custom tools registered (Custom/*).")
