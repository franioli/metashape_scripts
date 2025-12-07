import shutil

import Metashape


def write_estimated_to_source(
    chunk, offset=None, overwrite_existing=True, cameras=None
):
    """
    Write estimated camera positions to source (reference) coordinates.
    Properly transforms coordinates to chunk CRS if set.

    Args:
        chunk: Metashape.Chunk
        offset: Metashape.Vector with offset to apply (dx, dy, dz) or None
        overwrite_existing: If True, overwrite existing source coordinates

    Returns:
        dict: Statistics about written positions
    """
    print("\n" + "=" * 70)
    print("WRITING ESTIMATED POSITIONS TO SOURCE COORDINATES")
    print("=" * 70)

    if chunk.crs:
        print(f"Chunk CRS: {chunk.crs.name}")
    else:
        print("No CRS set - using internal coordinates")

    if offset:
        print(
            f"Applying offset: dx={offset.x:.3f}, dy={offset.y:.3f}, dz={offset.z:.3f}"
        )
    else:
        print("No offset applied")

    print(f"Overwrite existing: {overwrite_existing}")
    print("")

    total_cameras = 0
    written = 0
    skipped_unaligned = 0
    skipped_existing = 0

    # Choose which cameras to process: explicit list, else all cameras in chunk
    if cameras is None:
        cameras = list(chunk.cameras)

    for camera in cameras:
        total_cameras += 1

        # Skip if camera not aligned
        if camera.transform is None:
            skipped_unaligned += 1
            continue

        # Skip if source coordinates exist and overwrite is disabled
        if not overwrite_existing and camera.reference.location is not None:
            skipped_existing += 1
            continue

        # Get camera position in internal coordinate system
        camera_internal = camera.center

        # Transform to geocentric (ECEF) coordinates
        camera_geocentric = chunk.transform.matrix.mulp(camera_internal)

        # Transform from geocentric to chunk CRS if CRS is set
        if chunk.crs:
            estimated_pos = chunk.crs.project(camera_geocentric)
        else:
            # No CRS set, use geocentric coordinates directly
            estimated_pos = camera_geocentric

        # Apply offset if provided
        if offset:
            estimated_pos = Metashape.Vector(
                [
                    estimated_pos.x + offset.x,
                    estimated_pos.y + offset.y,
                    estimated_pos.z + offset.z,
                ]
            )

        # Write to source (reference) coordinates
        camera.reference.location = estimated_pos
        camera.reference.enabled = True

        written += 1

        if written <= 5:  # Show first 5 examples
            print(f"Camera: {camera.label}")
            print(
                f"  Position: ({estimated_pos.x:.3f}, {estimated_pos.y:.3f}, {estimated_pos.z:.3f})"
            )

    if written > 5:
        print(f"... and {written - 5} more cameras")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total cameras: {total_cameras}")
    print(f"Positions written: {written}")
    print(f"Skipped (not aligned): {skipped_unaligned}")
    print(f"Skipped (existing coordinates): {skipped_existing}")
    print("=" * 70)

    return {
        "total": total_cameras,
        "written": written,
        "skipped_unaligned": skipped_unaligned,
        "skipped_existing": skipped_existing,
    }


def clear_camera_source_coordinates(chunk, cameras=None):
    """
    Clear all camera source (reference) coordinates.

    Args:
        chunk: Metashape.Chunk

    Returns:
        int: Number of cameras cleared
    """
    print("\n" + "=" * 70)
    print("CLEARING CAMERA SOURCE COORDINATES")
    print("=" * 70)

    # If no explicit cameras list is supplied, operate on all cameras in the chunk
    if cameras is None:
        cameras = list(chunk.cameras)

    cleared = 0

    for camera in cameras:
        if camera.reference.location is not None:
            camera.reference.location = None
            camera.reference.enabled = False
            cleared += 1

    print(f"Cleared {cleared} camera source coordinates")
    print("=" * 70)

    return cleared


def export_selected_images(chunk, dest_path, copy_metadata=True):
    """
    Core function: export photos for selected cameras from a given chunk to dest_path.

    Args:
        chunk: Metashape.Chunk instance to read cameras from
        dest_path: str destination directory (should already exist)
        copy_metadata: bool whether to also copy file metadata (uses shutil.copy2 when True)

    Returns:
        dict: {total_selected: int, copied: int, skipped_missing: int}
    """

    if chunk is None:
        raise ValueError("chunk must be provided")

    total_selected = 0
    copied = 0
    skipped_missing = 0

    # If no selection provided, prefer exported selected cameras; if none selected, export all
    cameras_to_export = [c for c in chunk.cameras if getattr(c, "selected", False)]
    if not cameras_to_export:
        cameras_to_export = list(chunk.cameras)

    for camera in cameras_to_export:
        total_selected += 1
        src = getattr(camera, "photo", None)
        if not src:
            skipped_missing += 1
            continue

        src_path = getattr(src, "path", None)
        if not src_path:
            skipped_missing += 1
            continue

        # Decide which copy function to use
        try:
            if copy_metadata:
                shutil.copy2(src_path, dest_path)
            else:
                shutil.copy(src_path, dest_path)
            copied += 1
            # show first few as feedback
            if copied <= 5:
                print(f"Exported: {src_path}")
        except Exception as e:
            print(f"Failed to copy {src_path}: {e}")

    if total_selected > 5 and copied > 0:
        print(f"... and {copied - min(copied, 5)} more copied")

    print(f"Images exported to {dest_path}.\n")

    return {
        "total_selected": total_selected,
        "copied": copied,
        "skipped_missing": skipped_missing,
    }


# ============================================================================
# GUI DIALOG FUNCTIONS
# ============================================================================


def write_estimated_to_source_dialog():
    """
    Dialog to write estimated positions to source coordinates.
    """
    chunk = Metashape.app.document.chunk

    if not chunk:
        Metashape.app.messageBox("No active chunk!")
        return

    # Prefer processing selected cameras when present
    selected_cameras = [cam for cam in chunk.cameras if getattr(cam, "selected", False)]
    cameras_to_process = selected_cameras if selected_cameras else list(chunk.cameras)

    # Count aligned cameras in the chosen set
    aligned = sum(1 for cam in cameras_to_process if cam.transform is not None)
    has_source = sum(
        1 for cam in cameras_to_process if cam.reference.location is not None
    )

    if aligned == 0:
        Metashape.app.messageBox("No aligned cameras found!")
        return

    # Show current state and ask to proceed
    crs_info = f"Chunk CRS: {chunk.crs.name}" if chunk.crs else "No CRS set"

    # Message explaining what will be processed
    target_scope = (
        f"selected cameras ({len(cameras_to_process)})"
        if selected_cameras
        else f"all cameras ({len(cameras_to_process)})"
    )

    message = (
        f"Current state:\n\n"
        f"Target: {target_scope}\n"
        f"Aligned cameras: {aligned}\n"
        f"Cameras with source coordinates: {has_source}\n"
        f"{crs_info}\n\n"
        f"This will write estimated positions to source coordinates.\n"
        f"Only positions will be written (no rotation angles).\n\n"
        f"Continue?"
    )

    proceed = Metashape.app.getBool(message)
    if not proceed:
        return

    # Ask if should apply offset
    use_offset = Metashape.app.getBool(
        "Apply offset to positions?\n\n"
        "If Yes, you will enter offset values manually.\n\n"
        "Apply offset?"
    )

    offset = None

    if use_offset:
        # Manual offset entry
        dx = Metashape.app.getFloat("Enter X offset (dx):", 0.0)
        if dx is None:
            return

        dy = Metashape.app.getFloat("Enter Y offset (dy):", 0.0)
        if dy is None:
            return

        dz = Metashape.app.getFloat("Enter Z offset (dz):", 0.0)
        if dz is None:
            return

        offset = Metashape.Vector([dx, dy, dz])

        # Confirm offset
        confirm = Metashape.app.getBool(
            f"Confirm offset values?\n\n"
            f"dx = {offset.x:.3f}\n"
            f"dy = {offset.y:.3f}\n"
            f"dz = {offset.z:.3f}\n\n"
            f"Apply this offset?"
        )

        if not confirm:
            return

    # Ask if should overwrite existing
    overwrite = True
    if has_source > 0:
        overwrite = Metashape.app.getBool(
            f"{has_source} of the target cameras already have source coordinates.\n\n"
            f"Overwrite existing coordinates?"
        )

    # Write positions
    results = write_estimated_to_source(
        chunk, offset, overwrite, cameras=cameras_to_process
    )

    # Show results
    message = (
        f"Writing Complete!\n\n"
        f"Total cameras: {results['total']}\n"
        f"Positions written: {results['written']}\n"
        f"Skipped (not aligned): {results['skipped_unaligned']}\n"
        f"Skipped (existing): {results['skipped_existing']}\n\n"
        f"Source coordinates updated in Metashape.\n"
        f"(Image EXIF not modified)"
    )

    Metashape.app.messageBox(message)


def clear_camera_coordinates_dialog():
    """
    Dialog to clear camera source coordinates.
    """
    chunk = Metashape.app.document.chunk

    if not chunk:
        Metashape.app.messageBox("No active chunk!")
        return

    # Prefer processing selected cameras when present
    selected_cameras = [cam for cam in chunk.cameras if getattr(cam, "selected", False)]
    cameras_to_clear = selected_cameras if selected_cameras else list(chunk.cameras)

    has_source = sum(
        1 for cam in cameras_to_clear if cam.reference.location is not None
    )

    if has_source == 0:
        Metashape.app.messageBox(
            "No cameras with source coordinates found in the chosen set!"
        )
        return

    response = Metashape.app.getBool(
        f"Clear source coordinates for {has_source} cameras?\n\n"
        f"This will only clear coordinates in Metashape,\n"
        f"not modify image EXIF data.\n\n"
        f"Continue?"
    )

    if response:
        count = clear_camera_source_coordinates(chunk, cameras=cameras_to_clear)
        Metashape.app.messageBox(f"Cleared {count} camera source coordinates.")


def export_camera_reference_dialog():
    """
    Dialog to export camera reference data using Metashape's built-in export.
    """
    chunk = Metashape.app.document.chunk

    if not chunk:
        Metashape.app.messageBox("No active chunk!")
        return

    # Ask for output path
    output_path = Metashape.app.getSaveFileName("Export camera reference data")

    if output_path:
        try:
            # Use Metashape's built-in export function
            chunk.exportReference(
                path=output_path,
                format=Metashape.ReferenceFormatCSV,
                items=Metashape.ReferenceItemsCameras,
                columns="nxyzXYZ",  # Label, estimated XYZ, source XYZ (positions only)
            )
            Metashape.app.messageBox(
                f"Camera reference data exported to:\n{output_path}\n\n"
                f"Format: CSV with estimated and source positions"
            )
            print(f"\nCamera reference data exported to: {output_path}")
        except Exception as e:
            Metashape.app.messageBox(f"Export failed:\n{str(e)}")
            print(f"Export error: {e}")


def export_selected_images_dialog():
    """
    GUI dialog wrapper for exporting selected camera images.

    Prompts the user for a destination directory and optional metadata copying.
    Calls export_selected_images(chunk, dest_path, copy_metadata)
    """
    doc = Metashape.app.document
    if not doc:
        Metashape.app.messageBox("No document loaded.")
        return

    chunk = doc.chunk
    if not chunk:
        Metashape.app.messageBox("No active chunk!")
        return

    dest_path = Metashape.app.getExistingDirectory("Select output folder:")
    if not dest_path:
        return

    # Ask whether to copy metadata (copy2) or not
    copy_meta = Metashape.app.getBool(
        "Copy filesystem metadata (timestamps) when exporting images?\n\n"
        "Yes = preserve metadata, No = do a plain copy"
    )

    try:
        results = export_selected_images(
            chunk, dest_path, copy_metadata=bool(copy_meta)
        )
    except Exception as e:
        Metashape.app.messageBox(f"Export failed:\n{e}")
        return

    Metashape.app.messageBox(
        f"Export complete!\n\nTotal selected: {results['total_selected']}\nCopied: {results['copied']}\nSkipped (missing files): {results['skipped_missing']}"
    )


# ============================================================================
# ADD TO METASHAPE MENU
# ============================================================================


def add_menu_items():
    """
    Add custom menu items to Metashape.
    """
    Metashape.app.addMenuItem(
        "Custom/Camera Positions/Write Estimated to Source...",
        write_estimated_to_source_dialog,
    )

    Metashape.app.addMenuItem(
        "Custom/Camera Positions/Clear Source Coordinates...",
        clear_camera_coordinates_dialog,
    )

    Metashape.app.addMenuItem(
        "Custom/Camera Positions/Export Reference Data...",
        export_camera_reference_dialog,
    )

    Metashape.app.addMenuItem(
        "Custom/Camera Positions/Export Selected Images...",
        export_selected_images_dialog,
    )

    print("Camera position tools added to menu: Custom -> Camera Positions")


# ============================================================================
# INITIALIZATION
# ============================================================================

label = "Custom/Camera Positions"
add_menu_items()

print("\n" + "=" * 70)
print("CAMERA POSITION TOOLS LOADED")
print("=" * 70)
print("Available in menu: Custom -> Camera Positions")
print("  - Write Estimated to Source...")
print("  - Clear Source Coordinates...")
print("  - Export Reference Data...")
print("  - Export Selected Images...")
print("=" * 70)
