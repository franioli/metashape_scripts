import Metashape


def _ensure_camera_in_chunk(dst_chunk, src_cam):
    """Ensure camera with src_cam.label exists in dst_chunk; add photo if missing."""
    for cam in dst_chunk.cameras:
        if cam.label == src_cam.label:
            return cam

    # Not found: add photo
    photo = src_cam.photo
    if photo is None or photo.path is None:
        return None
    new_cams = dst_chunk.addPhotos([photo.path])
    return new_cams[0] if new_cams else None


def transfer_oriented_cameras_from_chunk(
    src_chunk, dst_chunk, downscale=2, generic_preselection=True, optimize=True
):
    """
    Transfer camera poses from src_chunk to dst_chunk for cameras that are aligned in src
    but not aligned in dst, then match+refine so they link to existing tie points.

    Assumes chunks are already aligned (e.g., via Workflow -> Align Chunks).
    Uses chunk.transform to convert coordinates between chunks.
    """
    print("\n" + "=" * 70)
    print("TRANSFERRING ORIENTED CAMERAS BETWEEN CHUNKS")
    print("=" * 70)

    # Find candidates to transfer
    src_aligned = {c.label: c for c in src_chunk.cameras if c.transform is not None}
    dst_by_label = {c.label: c for c in dst_chunk.cameras}
    to_transfer = []

    for label, s_cam in src_aligned.items():
        d_cam = dst_by_label.get(label, None)
        if d_cam is None or d_cam.transform is None:
            to_transfer.append(label)

    if not to_transfer:
        print("No cameras to transfer!")
        return {
            "transferred": 0,
            "matched": 0,
            "optimized": False,
        }

    print(f"\nFound {len(to_transfer)} cameras to transfer")

    # Create or update destination cameras with transformed poses
    transferred_cams = []
    for label in to_transfer:
        s_cam = src_aligned[label]
        d_cam = _ensure_camera_in_chunk(dst_chunk, s_cam)
        if d_cam is None:
            print(f"Warning: Could not add camera {label} to destination chunk")
            continue

        # Get camera position in source chunk's internal coordinates
        src_internal_pos = s_cam.center

        # Transform to geocentric (world) coordinates using source chunk transform
        world_pos = src_chunk.transform.matrix.mulp(src_internal_pos)

        # Transform from world to destination chunk's internal coordinates
        dst_internal_pos = dst_chunk.transform.matrix.inv().mulp(world_pos)

        # Get rotation in world coordinates
        src_rotation = (
            src_chunk.transform.matrix
            * s_cam.transform
            * Metashape.Matrix.Diag([1, 1, 1, 0])
        )
        dst_rotation = dst_chunk.transform.matrix.inv() * src_rotation

        # Build destination camera transform
        d_cam.transform = Metashape.Matrix.Translation(dst_internal_pos) * dst_rotation
        d_cam.enabled = True
        transferred_cams.append(d_cam)

        if len(transferred_cams) <= 5:
            print(f"Transferred: {label}")

    if len(transferred_cams) > 5:
        print(f"... and {len(transferred_cams) - 5} more")

    # Match these cameras against the already aligned block and refine
    if transferred_cams:
        print("\n" + "-" * 70)
        print("MATCHING TRANSFERRED CAMERAS")
        print("-" * 70)

        # Match without resetting existing matches
        match_unaligned_photos(
            dst_chunk,
            transferred_cams,
            downscale=downscale,
            generic_preselection=generic_preselection,
        )

        print("\n" + "-" * 70)
        print("REFINING ALIGNMENT")
        print("-" * 70)

        try:
            dst_chunk.alignCameras(
                cameras=transferred_cams, adaptive_fitting=True, reset_alignment=False
            )
            print("Alignment refinement complete!")
        except Exception as e:
            print(f"Warning: alignCameras on transferred set failed: {e}")

        if optimize:
            print("\n" + "-" * 70)
            print("OPTIMIZING CAMERAS")
            print("-" * 70)

            try:
                dst_chunk.optimizeCameras(
                    fit_f=True,
                    fit_cx=True,
                    fit_cy=True,
                    fit_k1=True,
                    fit_k2=True,
                    fit_k3=True,
                    fit_p1=True,
                    fit_p2=True,
                    adaptive_fitting=True,
                )
                print("Optimization complete!")
            except Exception as e:
                print(f"Warning: Optimization failed: {e}")

    print("\n" + "=" * 70)
    print("TRANSFER COMPLETE")
    print("=" * 70)

    return {
        "transferred": len(transferred_cams),
        "matched": len(transferred_cams),
        "optimized": bool(optimize),
    }


def transfer_oriented_cameras_dialog():
    """
    Dialog to transfer oriented cameras from one chunk (small) to another (main) and link them.
    Assumes chunks are already aligned manually.
    """
    doc = Metashape.app.document
    if not doc or len(doc.chunks) < 2:
        Metashape.app.messageBox("Need at least two chunks in the document.")
        return

    # List chunks for selection
    labels = [
        f"{i}: {c.label} (cams: {len(c.cameras)})" for i, c in enumerate(doc.chunks)
    ]

    msg = "Select SOURCE chunk (small subset):\n\n" + "\n".join(labels)
    src_idx = Metashape.app.getInt(msg, 1)
    if src_idx is None or src_idx < 0 or src_idx >= len(doc.chunks):
        return

    msg = "Select DESTINATION chunk (main block):\n\n" + "\n".join(labels)
    dst_idx = Metashape.app.getInt(msg, 0)
    if (
        dst_idx is None
        or dst_idx < 0
        or dst_idx >= len(doc.chunks)
        or dst_idx == src_idx
    ):
        return

    # Confirm chunks are aligned
    proceed = Metashape.app.getBool(
        "Have you already aligned the chunks?\n"
        "(Workflow → Align Chunks)\n\n"
        "This tool assumes chunks are already in the same\n"
        "coordinate system.\n\n"
        "Continue?"
    )

    if not proceed:
        return

    downscale = Metashape.app.getInt(
        "Downscale for matching:\n\n"
        "1 = Full resolution (slower, more accurate)\n"
        "2 = Half resolution (recommended)\n"
        "4 = Quarter resolution (faster)",
        2,
    )
    if downscale is None or downscale < 1:
        return

    generic_preselection = Metashape.app.getBool(
        "Use generic preselection for matching?\n\n"
        "Yes = Faster, may miss some matches\n"
        "No = Slower, more thorough"
    )

    optimize = Metashape.app.getBool(
        "Optimize cameras after transfer?\n\nYes = More accurate, slower\nNo = Faster"
    )

    src = doc.chunks[src_idx]
    dst = doc.chunks[dst_idx]

    try:
        res = transfer_oriented_cameras_from_chunk(
            src,
            dst,
            downscale=downscale,
            generic_preselection=generic_preselection,
            optimize=optimize,
        )
        Metashape.app.messageBox(
            f"Transfer complete!\n\n"
            f"Cameras transferred: {res['transferred']}\n"
            f"Matched: {res['matched']}\n"
            f"Optimized: {res['optimized']}\n\n"
            f"Transferred cameras are now linked\n"
            f"to the main block's tie points."
        )
    except Exception as e:
        Metashape.app.messageBox(f"Transfer failed:\n\n{str(e)}")
        print(f"\nError: {e}")


def get_alignment_stats(chunk):
    """
    Get statistics about camera alignment.

    Args:
        chunk: Metashape.Chunk

    Returns:
        dict: Statistics about aligned/unaligned cameras
    """
    aligned = []
    unaligned = []

    for camera in chunk.cameras:
        if camera.transform is None:
            unaligned.append(camera)
        else:
            aligned.append(camera)

    return {
        "total": len(chunk.cameras),
        "aligned": aligned,
        "unaligned": unaligned,
        "aligned_count": len(aligned),
        "unaligned_count": len(unaligned),
    }


def match_unaligned_photos(
    chunk, unaligned_cameras, downscale=2, generic_preselection=True
):
    """
    Match photos specifically for unaligned cameras.
    Does NOT reset existing matches to preserve the sparse point cloud.

    Args:
        chunk: Metashape.Chunk
        unaligned_cameras: List of unaligned cameras
        downscale: Downscale factor for matching (1=full, 2=half, 4=quarter)
        generic_preselection: Use generic preselection
    """
    print(f"\nMatching {len(unaligned_cameras)} cameras...")
    print(f"Downscale: {downscale}")
    print(f"Generic preselection: {generic_preselection}")
    print("Note: Preserving existing matches for already aligned cameras")

    try:
        # Match photos for unaligned cameras
        # reset_matches=False to preserve existing matches
        chunk.matchPhotos(
            cameras=unaligned_cameras,
            downscale=downscale,
            generic_preselection=generic_preselection,
            reference_preselection=False,
            filter_mask=False,
            mask_tiepoints=False,
            keep_keypoints=True,
            reset_matches=False,  # IMPORTANT: Don't reset existing matches
            tiepoint_limit=0,  # No limit on tie points
        )
        print("Matching complete!")
    except Exception as e:
        print(f"Matching failed: {e}")
        raise


def incremental_align_cameras(
    chunk,
    batch_size=20,
    max_iterations=10,
    optimize_each_batch=True,
    adaptive_fitting=True,
):
    """
    Incrementally align unaligned cameras to already aligned ones.

    Args:
        chunk: Metashape.Chunk
        batch_size: Number of cameras to try aligning per iteration
        max_iterations: Maximum number of iterations
        adaptive_fitting: Use adaptive camera model fitting
        optimize_each_batch: Run optimization after each successful batch

    Returns:
        dict: Results of incremental alignment
    """
    print("\n" + "=" * 70)
    print("INCREMENTAL CAMERA ALIGNMENT")
    print("=" * 70)

    initial_stats = get_alignment_stats(chunk)

    if initial_stats["aligned_count"] == 0:
        print("ERROR: No aligned cameras found!")
        print("Run initial alignment first to get at least some cameras aligned.")
        return None

    if initial_stats["unaligned_count"] == 0:
        print("All cameras are already aligned!")
        return {
            "initial_aligned": initial_stats["aligned_count"],
            "initial_unaligned": 0,
            "final_aligned": initial_stats["aligned_count"],
            "final_unaligned": 0,
            "newly_aligned": 0,
            "iterations": 0,
        }

    print("\nInitial state:")
    print(f"  Aligned cameras: {initial_stats['aligned_count']}")
    print(f"  Unaligned cameras: {initial_stats['unaligned_count']}")
    print("\nIncremental alignment settings:")
    print(f"  Batch size: {batch_size} cameras")
    print(f"  Max iterations: {max_iterations}")
    print(f"  Adaptive fitting: {adaptive_fitting}")
    print(f"  Optimize each batch: {optimize_each_batch}")

    iteration = 0
    newly_aligned_total = 0
    unaligned_cameras = initial_stats["unaligned"].copy()

    while unaligned_cameras and iteration < max_iterations:
        iteration += 1

        print("\n" + "-" * 70)
        print(f"Iteration {iteration}:")
        print(f"  Remaining unaligned: {len(unaligned_cameras)}")

        # Select batch of cameras to align
        batch = unaligned_cameras[:batch_size]

        print(f"  Attempting to align {len(batch)} cameras...")

        # Try to align this batch
        try:
            chunk.alignCameras(
                cameras=batch, adaptive_fitting=adaptive_fitting, reset_alignment=False
            )
        except Exception as e:
            print(f"  Warning: Alignment failed - {e}")
            continue

        # Check which cameras got aligned
        newly_aligned = []
        still_unaligned = []

        for camera in batch:
            if camera.transform is not None:
                newly_aligned.append(camera)
            else:
                still_unaligned.append(camera)

        newly_aligned_count = len(newly_aligned)
        newly_aligned_total += newly_aligned_count

        print(f"  Newly aligned: {newly_aligned_count}")

        if newly_aligned_count > 0:
            # Show some camera names
            sample_names = [cam.label for cam in newly_aligned[:5]]
            print(f"  Examples: {', '.join(sample_names)}")

            if len(newly_aligned) > 5:
                print(f"  ... and {len(newly_aligned) - 5} more")

        # Update unaligned list
        unaligned_cameras = [
            cam for cam in unaligned_cameras if cam not in newly_aligned
        ]

        # If no cameras were aligned in this iteration, stop
        if newly_aligned_count == 0:
            print("\n  No cameras aligned in this iteration. Stopping.")
            break

        # Optional: Optimize after each batch
        if optimize_each_batch and newly_aligned_count > 0:
            print("  Optimizing alignment...")
            try:
                chunk.optimizeCameras(
                    fit_f=True,
                    fit_cx=True,
                    fit_cy=True,
                    fit_k1=True,
                    fit_k2=True,
                    fit_k3=True,
                    fit_p1=True,
                    fit_p2=True,
                    adaptive_fitting=adaptive_fitting,
                )
            except Exception as e:
                print(f"  Warning: Optimization failed - {e}")

    # Final statistics
    final_stats = get_alignment_stats(chunk)

    print("\n" + "=" * 70)
    print("INCREMENTAL ALIGNMENT COMPLETE")
    print("=" * 70)
    print(f"Initial aligned: {initial_stats['aligned_count']}")
    print(f"Newly aligned: {newly_aligned_total}")
    print(f"Final aligned: {final_stats['aligned_count']}")
    print(f"Still unaligned: {final_stats['unaligned_count']}")
    print(f"Iterations performed: {iteration}")
    if initial_stats["unaligned_count"] > 0:
        print(
            f"Success rate: {newly_aligned_total / initial_stats['unaligned_count'] * 100:.1f}%"
        )

    results = {
        "initial_aligned": initial_stats["aligned_count"],
        "initial_unaligned": initial_stats["unaligned_count"],
        "final_aligned": final_stats["aligned_count"],
        "final_unaligned": final_stats["unaligned_count"],
        "newly_aligned": newly_aligned_total,
        "iterations": iteration,
        "unaligned_cameras": final_stats["unaligned"],
    }

    return results


def disable_unaligned_cameras(chunk):
    """
    Disable all unaligned cameras to exclude them from processing.

    Args:
        chunk: Metashape.Chunk

    Returns:
        int: Number of cameras disabled
    """
    stats = get_alignment_stats(chunk)

    for camera in stats["unaligned"]:
        camera.enabled = False

    print(f"\nDisabled {stats['unaligned_count']} unaligned cameras")
    return stats["unaligned_count"]


def enable_all_cameras(chunk):
    """
    Enable all cameras in the chunk.

    Args:
        chunk: Metashape.Chunk

    Returns:
        int: Number of cameras enabled
    """
    count = 0
    for camera in chunk.cameras:
        if not camera.enabled:
            camera.enabled = True
            count += 1

    print(f"\nEnabled {count} cameras")
    return count


def show_alignment_statistics(chunk):
    """
    Display detailed alignment statistics.

    Args:
        chunk: Metashape.Chunk
    """
    stats = get_alignment_stats(chunk)

    print("\n" + "=" * 70)
    print("CAMERA ALIGNMENT STATISTICS")
    print("=" * 70)
    print(f"Total cameras: {stats['total']}")
    print(
        f"Aligned cameras: {stats['aligned_count']} ({stats['aligned_count'] / stats['total'] * 100:.1f}%)"
    )
    print(
        f"Unaligned cameras: {stats['unaligned_count']} ({stats['unaligned_count'] / stats['total'] * 100:.1f}%)"
    )

    # Group by sensor
    if stats["unaligned_count"] > 0:
        print("\nUnaligned cameras by sensor:")
        sensor_groups = {}
        for camera in stats["unaligned"]:
            sensor_label = camera.sensor.label if camera.sensor else "Unknown"
            if sensor_label not in sensor_groups:
                sensor_groups[sensor_label] = []
            sensor_groups[sensor_label].append(camera)

        for sensor_label, cameras in sensor_groups.items():
            print(f"  {sensor_label}: {len(cameras)} cameras")

    print("=" * 70)


def export_unaligned_camera_list(chunk, output_path):
    """
    Export list of unaligned cameras to a text file.

    Args:
        chunk: Metashape.Chunk
        output_path: Path to output text file
    """
    stats = get_alignment_stats(chunk)

    with open(output_path, "w") as f:
        f.write("=" * 70 + "\n")
        f.write("UNALIGNED CAMERAS LIST\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Total cameras: {stats['total']}\n")
        f.write(f"Aligned cameras: {stats['aligned_count']}\n")
        f.write(f"Unaligned cameras: {stats['unaligned_count']}\n\n")
        f.write("=" * 70 + "\n")
        f.write("UNALIGNED CAMERA NAMES\n")
        f.write("=" * 70 + "\n\n")

        for camera in stats["unaligned"]:
            f.write(f"{camera.label}\n")

    print(f"\nUnaligned camera list exported to: {output_path}")


# ============================================================================
# GUI DIALOG FUNCTIONS
# ============================================================================


def incremental_alignment_dialog():
    """
    Main dialog for incremental camera alignment with photo matching.
    """
    chunk = Metashape.app.document.chunk

    if not chunk:
        Metashape.app.messageBox("No active chunk!")
        return

    stats = get_alignment_stats(chunk)

    if stats["aligned_count"] == 0:
        Metashape.app.messageBox(
            "No aligned cameras found!\n\n"
            "Run initial alignment first (Workflow -> Align Photos)\n"
            "to get at least some cameras aligned."
        )
        return

    if stats["unaligned_count"] == 0:
        Metashape.app.messageBox("All cameras are already aligned!")
        return

    # Show current status
    message = (
        f"Current alignment status:\n\n"
        f"Total cameras: {stats['total']}\n"
        f"Aligned: {stats['aligned_count']}\n"
        f"Unaligned: {stats['unaligned_count']}\n\n"
        f"This will:\n"
        f"1. Match unaligned cameras against ALL cameras\n"
        f"2. Incrementally align them to existing cameras\n\n"
        f"Existing matches and sparse cloud will be preserved.\n\n"
        f"Continue?"
    )

    proceed = Metashape.app.getBool(message)
    if not proceed:
        return

    # Ask for downscale for matching
    downscale = Metashape.app.getInt(
        "Enter downscale factor for photo matching:\n\n"
        "1 = Full resolution (slower, more accurate)\n"
        "2 = Half resolution (recommended)\n"
        "4 = Quarter resolution (faster)\n",
        2,
    )

    if downscale is None or downscale < 1:
        return

    # Ask if should use generic preselection
    generic_preselection = Metashape.app.getBool(
        "Use generic preselection for matching?\n\n"
        "Yes = Faster, may miss some matches\n"
        "No = Slower, more thorough"
    )

    # Ask for batch size
    batch_size = Metashape.app.getInt(
        "Enter batch size (cameras per iteration):\n\n"
        "Smaller = more conservative, slower\n"
        "Larger = more aggressive, faster\n\n"
        "Recommended: 10-50",
        20,
    )

    if batch_size is None or batch_size < 1:
        return

    # Ask for max iterations
    max_iterations = Metashape.app.getInt(
        "Enter maximum number of iterations:\n\n"
        "Stop after this many attempts even if\n"
        "some cameras remain unaligned.\n\n"
        "Recommended: 10-50",
        20,
    )

    if max_iterations is None or max_iterations < 1:
        return

    # Ask if should optimize each batch
    optimize_each_batch = Metashape.app.getBool(
        "Optimize alignment after each batch?\n\n"
        "Yes = More accurate, slower\n"
        "No = Faster, may be less stable"
    )

    try:
        # Step 1: Match photos for unaligned cameras
        print("\n" + "=" * 70)
        print("STEP 1: MATCHING PHOTOS FOR UNALIGNED CAMERAS")
        print("=" * 70)

        match_unaligned_photos(
            chunk, stats["unaligned"], downscale, generic_preselection
        )

        # Step 2: Incremental alignment
        print("\n" + "=" * 70)
        print("STEP 2: INCREMENTAL ALIGNMENT")
        print("=" * 70)

        results = incremental_align_cameras(
            chunk,
            batch_size=batch_size,
            max_iterations=max_iterations,
            optimize_each_batch=optimize_each_batch,
            adaptive_fitting=True,
        )

        if results:
            # Show results
            message = (
                f"Incremental Alignment Complete!\n\n"
                f"Initial aligned: {results['initial_aligned']}\n"
                f"Newly aligned: {results['newly_aligned']}\n"
                f"Final aligned: {results['final_aligned']}\n"
                f"Still unaligned: {results['final_unaligned']}\n"
                f"Iterations: {results['iterations']}\n\n"
            )

            if results["initial_unaligned"] > 0:
                success_rate = (
                    results["newly_aligned"] / results["initial_unaligned"] * 100
                )
                message += f"Success rate: {success_rate:.1f}%"

            Metashape.app.messageBox(message)

            # Ask what to do with remaining unaligned cameras
            if results["final_unaligned"] > 0:
                response = Metashape.app.getBool(
                    f"{results['final_unaligned']} cameras remain unaligned.\n\n"
                    f"Disable them to exclude from further processing?"
                )

                if response:
                    disable_unaligned_cameras(chunk)
                    Metashape.app.messageBox(
                        f"Disabled {results['final_unaligned']} unaligned cameras.\n\n"
                        f"You can re-enable them later from the Photos pane."
                    )
    except Exception as e:
        Metashape.app.messageBox(f"Error during incremental alignment:\n\n{str(e)}")
        print(f"\nError: {e}")


def show_alignment_stats_dialog():
    """
    Show alignment statistics dialog.
    """
    chunk = Metashape.app.document.chunk

    if not chunk:
        Metashape.app.messageBox("No active chunk!")
        return

    show_alignment_statistics(chunk)

    stats = get_alignment_stats(chunk)

    message = (
        f"Camera Alignment Statistics:\n\n"
        f"Total cameras: {stats['total']}\n"
        f"Aligned: {stats['aligned_count']} ({stats['aligned_count'] / stats['total'] * 100:.1f}%)\n"
        f"Unaligned: {stats['unaligned_count']} ({stats['unaligned_count'] / stats['total'] * 100:.1f}%)\n\n"
        f"See console for detailed breakdown."
    )

    Metashape.app.messageBox(message)


def disable_unaligned_cameras_dialog():
    """
    Dialog to disable unaligned cameras.
    """
    chunk = Metashape.app.document.chunk

    if not chunk:
        Metashape.app.messageBox("No active chunk!")
        return

    stats = get_alignment_stats(chunk)

    if stats["unaligned_count"] == 0:
        Metashape.app.messageBox("No unaligned cameras to disable!")
        return

    response = Metashape.app.getBool(
        f"Disable {stats['unaligned_count']} unaligned cameras?\n\n"
        f"This will exclude them from processing but\n"
        f"you can re-enable them later.\n\n"
        f"Continue?"
    )

    if response:
        count = disable_unaligned_cameras(chunk)
        Metashape.app.messageBox(f"Disabled {count} unaligned cameras.")


def enable_all_cameras_dialog():
    """
    Dialog to enable all cameras.
    """
    chunk = Metashape.app.document.chunk

    if not chunk:
        Metashape.app.messageBox("No active chunk!")
        return

    response = Metashape.app.getBool("Enable all cameras in the chunk?\n\nContinue?")

    if response:
        count = enable_all_cameras(chunk)
        if count > 0:
            Metashape.app.messageBox(f"Enabled {count} cameras.")
        else:
            Metashape.app.messageBox("All cameras were already enabled.")


def export_unaligned_list_dialog():
    """
    Dialog to export unaligned camera list.
    """
    chunk = Metashape.app.document.chunk

    if not chunk:
        Metashape.app.messageBox("No active chunk!")
        return

    stats = get_alignment_stats(chunk)

    if stats["unaligned_count"] == 0:
        Metashape.app.messageBox("No unaligned cameras to export!")
        return

    # Ask for output path
    output_path = Metashape.app.getSaveFileName(
        "Save unaligned camera list", filter="Text files (*.txt);;All files (*.*)"
    )

    if output_path:
        export_unaligned_camera_list(chunk, output_path)
        Metashape.app.messageBox(
            f"Exported {stats['unaligned_count']} camera names to:\n{output_path}"
        )


# ============================================================================
# ADD TO METASHAPE MENU
# ============================================================================


def add_menu_items():
    """
    Add custom menu items to Metashape.
    """
    Metashape.app.addMenuItem(
        "Custom/Incremental Alignment/Align Unaligned Cameras...",
        incremental_alignment_dialog,
    )
    Metashape.app.addMenuItem(
        "Custom/Incremental Alignment/Show Alignment Statistics",
        show_alignment_stats_dialog,
    )
    Metashape.app.addMenuItem(
        "Custom/Incremental Alignment/Disable Unaligned Cameras",
        disable_unaligned_cameras_dialog,
    )
    Metashape.app.addMenuItem(
        "Custom/Incremental Alignment/Enable All Cameras", enable_all_cameras_dialog
    )
    Metashape.app.addMenuItem(
        "Custom/Incremental Alignment/Export Unaligned Camera List...",
        export_unaligned_list_dialog,
    )
    Metashape.app.addMenuItem(
        "Custom/Incremental Alignment/Transfer Oriented Cameras From Chunk...",
        transfer_oriented_cameras_dialog,
    )

    print("Incremental alignment tools added to menu: Custom -> Incremental Alignment")


# ============================================================================
# INITIALIZATION
# ============================================================================

label = "Custom/Incremental Alignment"
add_menu_items()

print("\n" + "=" * 70)
print("INCREMENTAL ALIGNMENT TOOLS LOADED")
print("=" * 70)
print("Available in menu: Custom -> Incremental Alignment")
print("  - Align Unaligned Cameras...")
print("  - Show Alignment Statistics")
print("  - Disable Unaligned Cameras")
print("  - Enable All Cameras")
print("  - Export Unaligned Camera List...")
print("  - Transfer Oriented Cameras From Chunk...")
print("=" * 70)
